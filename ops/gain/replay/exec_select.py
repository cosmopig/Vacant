"""離線重放：把「執行落地選擇」當成 OFF5 的替代選法，等預算比對。

這支**不打任何模型端點**。候選答案全部來自 runs/<run>/calls.jsonl 已落盤的
response 文字；選擇只用 visible_check（V 側，等同 arm_off5 已經在跑的
behavior_signature 所用的資訊），計分只用 hidden_check（GT，永不進選擇）。

V/GT 分離（codebench.py §「GT 只進 hidden_check」）在這裡的操作化：
  - `visible_grade()` 只讀 task['visible_check']，回傳逐筆 base input 的通過與否
    ＋候選行為簽名。它是 arm_off5 現行 behavior_signature 的**更細粒度**讀法，
    資訊量沒有增加（同一份 base inputs、同一個內嵌 canonical 只算 base 期望值）。
  - `hidden_ok` 由 gain_run.meets_demand 產生，**只寫進計分欄位**，任何 policy
    函式都拿不到它（policies 只吃 CandidateFacts 的 V 側欄位）。

呼叫預算：所有 policy 都在 OFF5 那 5 次 gen 呼叫的**同一批候選**上選，
沙箱執行是本機免費的，不計入預算 ⇒ 與 OFF5／ON 同為 5 呼叫／題。
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ops" / "gain"))
os.environ.setdefault(
    "VACANT_EVALPLUS_PATH", str(REPO / ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"))

from ops.gain.gain_run import (  # noqa: E402
    _GAIN_ALLOWED_IMPORTS, InfraVoid, extract_code, meets_demand,
)
from vacant.codebench import EvalPlusMBPPLoader  # noqa: E402

SEED = "g-r212-route-20260828"
CACHE = pathlib.Path(__file__).resolve().parent / "cache"


# ── V 側：逐筆 base input 的通過與否 ────────────────────────────────
def _split_visible(vcode: str):
    """把 visible_check 拆成 (preamble, [(call, inp_expr, atol), ...])。

    解析後**逐行還原比對**，還原不出原句就回 None ⇒ 該題退回二元 visible_ok。
    """
    pre, items = [], []
    for line in vcode.split("\n"):
        if not line.startswith("assert __aeq("):
            pre.append(line)
            continue
        body = line[len("assert __aeq("):]
        if not body.endswith(")"):
            return None
        body = body[:-1]
        marker = ", __canon(*"
        if marker not in body:
            return None
        call, rest = body.split(marker, 1)
        if ", " not in rest:
            return None
        inp_close, atol = rest.rsplit(", ", 1)
        if not inp_close.endswith(")"):
            return None
        inp = inp_close[:-1]
        if f"assert __aeq({call}, __canon(*{inp}), {atol})" != line:
            return None
        items.append((call, inp, atol))
    return (pre, items) if items else None


MARK = "__VACANT_GRADE__"


def _grade_probe(pre, items) -> str:
    out = list(pre)
    out += ["import json as __vacant_json", "__vres = []", "__vbeh = []"]
    for call, inp, atol in items:
        out += [
            "try:",
            f"    __got = {call}",
            f"    __ok = bool(__aeq(__got, __canon(*{inp}), {atol}))",
            "    __vbeh.append(['ok', type(__got).__name__, repr(__got)])",
            "except BaseException as __e:",
            "    __ok = False",
            "    __vbeh.append(['err', type(__e).__name__, str(__e)])",
            "__vres.append(__ok)",
        ]
    out.append(
        f"print({MARK!r} + __vacant_json.dumps([__vres, __vbeh], sort_keys=True))")
    return "\n".join(out)


def visible_grade(code: str, task: dict) -> tuple[int, int, str, bool]:
    """回傳 (通過筆數, 總筆數, 行為簽名, visible_ok)。只讀 visible_check。"""
    from vacant.checks import CheckInfraError, run_python_capture
    parsed = _split_visible(task["visible_check"]["code"])
    ep = task.get("entry_point")
    if parsed is None:
        ok, _ = meets_demand(code, task["visible_check"]["code"], entry_point=ep)
        return (1 if ok else 0), 1, ("VISIBLE_PASS" if ok else "VISIBLE_FAIL"), ok
    pre, items = parsed
    try:
        out = run_python_capture(
            code, _grade_probe(pre, items), timeout=10,
            allowed_imports=_GAIN_ALLOWED_IMPORTS,
            allowed_entry_points=(ep,) if ep else (),
        )
    except CheckInfraError as exc:                                # pragma: no cover
        raise InfraVoid(str(exc)) from exc
    if out is None:
        return 0, len(items), "EXEC_FAIL", False
    lines = [ln for ln in out.splitlines() if ln.startswith(MARK)]
    if not lines:
        return 0, len(items), "EXEC_FAIL", False
    res, beh = json.loads(lines[-1][len(MARK):])
    return sum(1 for r in res if r), len(items), json.dumps(beh, sort_keys=True), all(res)


# ── 候選抽取 ────────────────────────────────────────────────────────
def load_candidates(run: str) -> dict:
    """(arm, task_id) -> [ {role, agent_id, model, code, ts_ms}, ... ]（只取 ok=True）。"""
    out: dict = {}
    p = REPO / "runs" / run / "calls.jsonl"
    for ln in p.open(encoding="utf-8"):
        r = json.loads(ln)
        if not r.get("ok"):
            continue
        m = r.get("meta") or {}
        arm, tid = m.get("arm"), m.get("task_id")
        if not arm or not tid or r.get("role") not in ("gen", "revise"):
            continue
        out.setdefault((arm, tid), []).append({
            "role": r["role"], "agent_id": r.get("agent_id"), "model": r.get("model"),
            "ts_ms": r.get("ts_ms"), "phase": m.get("phase"),
            "code": extract_code(r.get("response") or ""),
        })
    for v in out.values():
        v.sort(key=lambda d: d["ts_ms"])
    return out


def load_rows(run: str) -> dict:
    out = {}
    for ln in (REPO / "runs" / run / "rows.jsonl").open(encoding="utf-8"):
        r = json.loads(ln)
        out[(r["arm"], r["task_id"])] = r
    return out


# ── 執行階段 ────────────────────────────────────────────────────────
_TASKS: dict = {}


def _init():
    global _TASKS
    _TASKS = {t["task_id"]: t
              for t in EvalPlusMBPPLoader(expose_contract=True).iter_tasks(SEED)}


def _work(job):
    run, arm, tid, idx, cand = job
    t = _TASKS[tid]
    rec = {"run": run, "arm": arm, "task_id": tid, "idx": idx,
           "agent_id": cand["agent_id"], "model": cand["model"], "role": cand["role"],
           "code_len": len(cand["code"]),
           "sha": hashlib.sha256(cand["code"].encode()).hexdigest()[:16]}
    try:
        vp, vt, sig, vok = visible_grade(cand["code"], t)
        rec.update(visible_pass=vp, visible_total=vt, sig=sig, visible_ok=vok)
    except InfraVoid as e:
        rec.update(err=f"visible_void:{e}")
        return rec
    try:                                     # 只寫計分欄位，policy 拿不到
        hok, _ = meets_demand(cand["code"], t["hidden_check"]["code"],
                              entry_point=t.get("entry_point"))
        rec["hidden_ok"] = hok
    except InfraVoid as e:
        rec["err"] = f"hidden_void:{e}"
    return rec


def cmd_execute(runs, workers, arms=()):
    CACHE.mkdir(parents=True, exist_ok=True)
    _init()
    for run in runs:
        cands = load_candidates(run)
        jobs = [(run, arm, tid, i, c)
                for (arm, tid), lst in sorted(cands.items())
                if tid in _TASKS and (not arms or arm in arms)
                for i, c in enumerate(lst)]
        outp = CACHE / f"{run}.jsonl"
        done = set()
        if outp.exists():
            for ln in outp.open():
                r = json.loads(ln)
                done.add((r["arm"], r["task_id"], r["idx"]))
        jobs = [j for j in jobs if (j[1], j[2], j[3]) not in done]
        print(f"{run}: {len(jobs)} candidates to execute", flush=True)
        with outp.open("a", encoding="utf-8") as f, \
                cf.ProcessPoolExecutor(workers, initializer=_init) as ex:
            for n, rec in enumerate(ex.map(_work, jobs, chunksize=4), 1):
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                if n % 50 == 0:
                    f.flush()
                    print(f"  {n}/{len(jobs)}", flush=True)
        print(f"{run}: done -> {outp}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["execute"])
    ap.add_argument("--runs", required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--arms", default="")
    a = ap.parse_args()
    cmd_execute(a.runs.split(","), a.workers,
                tuple(x for x in a.arms.split(",") if x))
