#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""五組工作區題庫的量具：先用已知答案試過尺，才拿去量 agent（零模型呼叫）。

這支在架構裡承重什麼
--------------------
「判成 0 之前先證明量得動」。`build_banks.py` 渲染出來的每一題，在進 Colab 的 A/B 之前
先量三件事，全部走**閘門實際用的那一份判準**——`vacant_network/vrun/acceptance.py::run_suite`
（`python3 driver.py <ws> <testfile> <nonce>`，每個測試檔一個子行程），後端 `none`、
逾時 30 秒＝`gateshim.py` 呼叫 launcher 時的預設（`VACANT_TEST_TIMEOUT` 未設＝30），
記憶體＝`sandbox.DEFAULT_MEMORY_BYTES`（未設 `VACANT_ACCEPT_MEMORY_MB`＝512 MiB）。
沒有另寫第二套判準。

1. **參考解**（有的話）⇒ 可見全過、隱藏全過（隱藏跑 `--hidden-reps` 次，抓不穩的題）。
   - MBPP+：官方 `canonical_solution`；HumanEval+：`prompt + canonical_solution`
     （`EvalPlusHumanEvalLoader.canonical_source`，拼法只有一處）；
   - LCB：沒有官方參考解，用 repo 既有的手寫探針解
     （`ops/gain/data/lcb_probe_solutions.json`＝v1/v2、`lcb_v3_probe_solutions.json`＝v3，
     各 12 題，R441／R461 逐題用真的 hidden_check 驗過）。其餘題**無參考解、只驗樁**。
2. **退化樁** `def <entry>(*a, **k): return None` ⇒ 可見至少擋下一條（隱藏也記）。
3. **與既有判準逐份比對**（`--equiv K`，選配但建議跑）：從已歸檔 run 的 `calls.jsonl`
   抽**模型真的寫過的**候選碼，同一份碼同時餵
     (a) 既有判準 `gain_run.meets_demand(code, loader 的 visible_check/hidden_check, 10)`
     (b) 渲染出來的 `tests_visible/`、`hidden/`（經 `run_suite`）
   兩邊逐一比對。只比沙箱 AST 政策收得下的候選（R534 `gauge_bank.py` 的同一條理由：
   被政策擋掉的碼，既有判準連跑都不跑就判 False，比到的會是政策而不是 case 集合）。
   兩邊都判隱藏過的候選另外計數＝「歷史候選正控制」（LCB 沒參考解的題靠它補證據）。

排除規則（依序，第一個命中的就是理由）：
    reference_fails_timeout／reference_fails_memory／reference_fails_other／reference_flaky
        參考解沒有全過（逾時、記憶體、其他；隱藏重跑結果不一致＝flaky）
    stub_not_blocked
        退化樁在可見一條都沒被擋下（可見測試連 return None 都擋不住）

誠實邊界（`vacant_network/suitegauge.py` 那句逐字適用）
------------------------------------------------------
「參考解全過＋樁被擋」是**單邊**保證：擋得住 return None 不等於可見測試涵蓋真需求。

用法
----
    .venv/bin/python ops/vacantrun/colab_banks_20260927/gauge_banks.py --bank lcb_v2 --equiv 3
    .venv/bin/python ops/vacantrun/colab_banks_20260927/gauge_banks.py --bank all --equiv 3 --prune
"""

from __future__ import annotations

import argparse
import ast
import concurrent.futures as cf
import glob
import hashlib
import json
import pathlib
import platform
import shutil
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))

from ops.vacantrun.colab_banks_20260927 import build_banks as BB  # noqa: E402

GAUGE = "ops/vacantrun/colab_banks_20260927/gauge_banks.py"

#: 候選碼從哪些已歸檔 run 抽（glob，相對 repo）。只讀、零模型呼叫。
CANDIDATE_GLOBS = {
    "lcb": ("runs/g_*lcb*/calls.jsonl",),
    "mbpp": ("runs/g_r529_mbpp_*/calls.jsonl", "runs/g_r532_mbpp_*/calls.jsonl"),
    "he": ("runs/g_r529_hep_*/calls.jsonl", "runs/g_r532_hep_*/calls.jsonl"),
}
LEGACY_TIMEOUT_S = 10          # gain_run.meets_demand 的預設（主流程就是用預設值呼叫）
LEGACY_MEMORY_BYTES = 128 * 1024 * 1024   # vacant_network/checks.py::_cpu_limits 的預設
LEGACY_CALL_TIMEOUT_S = LEGACY_TIMEOUT_S * 0.9   # checks.py:580 call_timeout = timeout*0.9

MEMORY_MARKERS = ("MemoryError", "Cannot allocate memory", "failed to map segment")


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tree_state(root: pathlib.Path) -> dict[str, str]:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.is_symlink() and "__pycache__" not in p.parts:
            out[str(p.relative_to(root))] = sha256_file(p)
    return out


def summarize(res: dict, *, private: bool) -> dict:
    files = res.get("files", [])
    failing = []
    for f in files:
        for c in f.get("cases", []):
            if not c.get("ok"):
                failing.append({"case": c.get("case"), "kind": c.get("kind"),
                                "message": (c.get("message") or "")[:300]})
    return {
        "passed": res.get("passed"), "total": res.get("total"), "all_pass": res.get("all_pass"),
        "timed_out": any(f.get("timed_out") for f in files),
        "wall_ms": max([f.get("wall_ms") or 0 for f in files] or [0]),
        "result_sha256": res.get("result_sha256"),
        "failing_first": failing[:4],
        "n_failing": len(failing),
        "empty_reason": res.get("empty_reason"),
    }


def strip_messages(obj):
    """私有題庫的 manifest 要進版控：失敗訊息裡有 `args=… want=…`（＝測資），一律拿掉。
    完整訊息只留在私有樹裡的 `gauge_detail.json`。"""
    if isinstance(obj, dict):
        return {k: strip_messages(v) for k, v in obj.items() if k != "message"}
    if isinstance(obj, list):
        return [strip_messages(v) for v in obj]
    return obj


def _text(res: dict) -> str:
    parts = []
    for f in res.get("files", []):
        parts.append(f.get("stderr_tail") or "")
        for c in f.get("cases", []):
            if not c.get("ok"):
                parts += [c.get("kind") or "", c.get("message") or ""]
    return "\n".join(parts)


def references(bank: str, src: dict) -> dict[str, tuple[str, str]]:
    """task_id → (參考解原始碼, 種類)。"""
    kind = BB.BANKS[bank]["kind"]
    if kind == "lcb":
        name = "lcb_v3_probe_solutions.json" if bank == "lcb_v3" else "lcb_probe_solutions.json"
        probes = json.loads((REPO / "ops" / "gain" / "data" / name).read_text(encoding="utf-8"))
        return {t: (code, f"probe:ops/gain/data/{name}") for t, code in probes.items() if t in src["tasks"]}
    from vacant_network import codebench as cb
    out = {}
    for tid, rec in src["records"].items():
        if kind == "mbpp":
            out[tid] = (rec["canonical_solution"], "canonical:MBPP+ canonical_solution")
        else:
            out[tid] = (cb.EvalPlusHumanEvalLoader.canonical_source(rec),
                        "canonical:HumanEval+ prompt+canonical_solution")
    return out


def entry_of(bank: str, src: dict, tid: str) -> str:
    return src["tasks"][tid]["entry_point"]


def run_pair(acc, sb, tpl: pathlib.Path, hid: pathlib.Path, work: pathlib.Path, code: str, *,
             timeout_s: float, hidden_reps: int, tag: str) -> dict:
    ws = work / tag / "ws"
    shutil.rmtree(work / tag, ignore_errors=True)
    shutil.copytree(tpl, ws)
    (ws / "solution.py").write_text(code, encoding="utf-8")
    before = tree_state(ws)
    vis = acc.run_suite(sb, ws, tpl / "tests_visible", suite="visible", task_id=tag,
                        verify_root=work / tag / "_verify", timeout_s=timeout_s)
    hids = [acc.run_suite(sb, ws, hid, suite="hidden", task_id=tag,
                          verify_root=work / tag / "_verify", timeout_s=timeout_s)
            for _ in range(hidden_reps)]
    after = tree_state(ws)
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    shutil.rmtree(work / tag, ignore_errors=True)
    return {"visible": vis, "hidden": hids, "ws_changed": changed}


def gauge_one(bank: str, tid: str, m: dict, *, root: pathlib.Path, ref, ep: str, acc, sb,
              timeout_s: float, hidden_reps: int, private: bool) -> dict:
    d = m["dir"]
    tpl, hid = root / "templates" / d, root / "hidden" / d
    work = root / "_gauge_work" / d
    rec: dict = {"task_id": tid, "dir": d}
    t0 = time.time()
    if ref is not None:
        r = run_pair(acc, sb, tpl, hid, work, ref[0], timeout_s=timeout_s,
                     hidden_reps=hidden_reps, tag="reference")
        rec["reference"] = {
            "source": ref[1],
            "visible": summarize(r["visible"], private=private),
            "hidden": [summarize(x, private=private) for x in r["hidden"]],
            "ws_changed": r["ws_changed"],
        }
        rec["_ref_text"] = "\n".join(_text(x) for x in [r["visible"], *r["hidden"]])
    else:
        rec["reference"] = None
    stub = f"def {ep}(*a, **k):\n    return None\n"
    s = run_pair(acc, sb, tpl, hid, work, stub, timeout_s=timeout_s, hidden_reps=1, tag="stub")
    rec["stub"] = {"visible": summarize(s["visible"], private=private),
                   "hidden": summarize(s["hidden"][0], private=private)}
    shutil.rmtree(work, ignore_errors=True)

    reason = None
    if ref is not None:
        rv = rec["reference"]["visible"]
        rh = rec["reference"]["hidden"]
        ok = rv["all_pass"] and all(h["all_pass"] for h in rh)
        if not ok:
            passes = [h["all_pass"] for h in rh]
            txt = rec["_ref_text"]
            if rv["timed_out"] or any(h["timed_out"] for h in rh):
                reason = "reference_fails_timeout"
            elif any(mk in txt for mk in MEMORY_MARKERS):
                reason = "reference_fails_memory"
            elif any(passes) and not all(passes):
                reason = "reference_flaky"
            else:
                reason = "reference_fails_other"
    rec.pop("_ref_text", None)
    sv = rec["stub"]["visible"]
    stub_blocked = not sv["all_pass"]
    if reason is None and not stub_blocked:
        reason = "stub_not_blocked"
    rec.update({
        "has_reference": ref is not None,
        "reference_ok": (None if ref is None else reason is None or reason == "stub_not_blocked"),
        "stub_blocked_visible": stub_blocked,
        "stub_visible_failed": (sv["total"] or 0) - (sv["passed"] or 0),
        "stub_visible_total": sv["total"],
        "stub_blocked_hidden": not rec["stub"]["hidden"]["all_pass"],
        "usable": reason is None,
        "exclude_reason": reason,
        "reference_max_file_wall_ms": (None if ref is None else
                                       max([rec["reference"]["visible"]["wall_ms"]]
                                           + [h["wall_ms"] for h in rec["reference"]["hidden"]])),
        "gauge_seconds": round(time.time() - t0, 1),
    })
    return rec


# ─────────────────────────────────────────────────────────────────────────────
# 與既有判準逐份比對
# ─────────────────────────────────────────────────────────────────────────────

#: 每題先收這麼多份不重複、政策收得下的候選，再從中**等距**挑 `--equiv` 份
#: （檔名排序＋行序下等距 ⇒ 確定性，而且跨 run／跨臂，過與不過的都挑得到）。
POOL_CAP = 40


def collect_candidates(bank: str, src: dict, per_task: int) -> tuple[dict[str, list[str]], dict[str, int], list[str]]:
    """task_id → 候選碼（確定性：檔名排序＋行序；去重；只收政策收得下的）。"""
    import re
    from ops.gain.gain_run import _GAIN_ALLOWED_IMPORTS, extract_code
    from vacant_network.checks import _candidate_functions
    kind = BB.BANKS[bank]["kind"]
    tasks = src["tasks"]
    by_ep: dict[str, list[str]] = {}
    for tid, t in tasks.items():
        by_ep.setdefault(t["entry_point"], []).append(tid)
    ep_set = set(by_ep)
    out: dict[str, list[str]] = {t: [] for t in tasks}
    seen: dict[str, set] = {t: set() for t in tasks}
    blocked: dict[str, int] = {t: 0 for t in tasks}
    paths = sorted({p for g in CANDIDATE_GLOBS[kind] for p in glob.glob(str(REPO / g))})
    ident = re.compile(r"[A-Za-z_]\w*")
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if '"role": "gen"' not in line:
                    continue
                rec = json.loads(line)
                if rec.get("role") != "gen" or not rec.get("ok"):
                    continue
                prompt = rec.get("prompt") or ""
                hits = set(ident.findall(prompt)) & ep_set
                for ep in sorted(hits):
                    for tid in by_ep[ep]:
                        if len(out[tid]) >= POOL_CAP or tasks[tid]["prompt"] not in prompt:
                            continue
                        code = extract_code(rec.get("response") or "")
                        if not code or code in seen[tid]:
                            continue
                        seen[tid].add(code)
                        try:
                            ast.parse(code)
                            okp = _candidate_functions(code, allowed_imports=_GAIN_ALLOWED_IMPORTS,
                                                       allowed_entry_points=(ep,)) is not None
                        except SyntaxError:
                            okp = False
                        if not okp:
                            blocked[tid] += 1
                            continue
                        out[tid].append(code)
    picked: dict[str, list[str]] = {}
    for tid, pool in out.items():
        if len(pool) <= per_task:
            picked[tid] = pool
        else:
            idx = sorted({round(i * (len(pool) - 1) / (per_task - 1)) for i in range(per_task)}) \
                if per_task > 1 else [0]
            picked[tid] = [pool[i] for i in idx]
    return picked, blocked, [str(pathlib.Path(p).relative_to(REPO)) for p in paths]


#: 分歧的解釋（依序，第一個成立的就是）。都不成立＝`UNEXPLAINED`，要人來看。
EXPLANATIONS = {
    "envelope": "同一份碼、同一個渲染檔，改用既有判準的信封（10 秒、128 MiB）重跑就回到既有判準的判決"
                "⇒ 分歧來自逾時／記憶體信封（閘門 30 秒、512 MiB 比較寬），不是 case 集合或比對器。",
    "legacy_entry_not_exported": "既有判準（checks.py::_candidate_functions）只把頂層 `def`／lambda 指派的名字"
                                 "交給 verifier；候選用 `別名 = 函式` 定義入口 ⇒ 既有判準找不到入口判 False，"
                                 "渲染檔是 import 整個 solution.py，找得到。是既有判準的投影限制，不是 case 或比對器。",
    "legacy_timeout_inline_canonical": "既有判準逾時（牆鐘 ≥ 8.5 秒；checks.py:580 的 call_timeout＝10×0.9＝9 秒），"
                                       "而渲染檔在同樣 10 秒信封下過得了："
                                       "EvalPlus 的既有判準在檢查當下**每一條都再跑一次 canonical**，渲染檔的期望值"
                                       "是建庫時算好的字面值 ⇒ 同一份候選在既有判準要多花 canonical 那一份時間。",
    "timing_borderline": "既有判準逾時（牆鐘 ≥ 8.5 秒；它的 call_timeout 實際是 9 秒），渲染檔跑同一份碼本身就要"
                         " ≥ 4.5 秒（沒有 2× 餘裕）⇒ 判決落在逾時線上，由負載與執行框架的開銷決定（既有判準另有 verifier proxy 的"
                         "逐次呼叫開銷），不是 case 集合或比對器。重跑一次可能翻面。",
}


def _legacy_near_timeout(row: dict) -> bool:
    """既有判準有沒有撞到自己的逾時：`checks.py:580` 的 `call_timeout = max(0.1, timeout*0.9)`
    ⇒ 10 秒的檢查實際在 9 秒就截斷。牆鐘 ≥ 8.5 秒算撞到（留 0.5 秒給子行程啟動的誤差）。"""
    lg = row.get("legacy") or {}
    return max(lg.get("visible_wall_s") or 0, lg.get("hidden_wall_s") or 0) >= LEGACY_CALL_TIMEOUT_S - 0.5


def _explain_row(row: dict, *, evalplus: bool) -> str:
    """只看已落盤欄位就判得出來的解釋（`reexplain` 也用這一份）。"""
    if row.get("explained_by_envelope"):
        return "envelope"
    env = row.get("rendered_in_legacy_envelope") or {}
    same_in_env = bool(env) and env.get("hidden") == row["rendered"]["hidden"] \
        and env.get("visible") == row["rendered"]["visible"]
    near = _legacy_near_timeout(row)
    if evalplus and near and same_in_env:
        return "legacy_timeout_inline_canonical"
    if near and (row["rendered"].get("hidden_wall_ms") or 0) >= LEGACY_CALL_TIMEOUT_S * 1000 / 2:
        return "timing_borderline"
    return "UNEXPLAINED"


def _explain(row: dict, code: str, ep: str, *, evalplus: bool) -> str:
    from ops.gain.gain_run import _GAIN_ALLOWED_IMPORTS
    from vacant_network.checks import _candidate_functions
    if row.get("explained_by_envelope"):
        return "envelope"
    exported = _candidate_functions(code, allowed_imports=_GAIN_ALLOWED_IMPORTS,
                                    allowed_entry_points=(ep,)) or []
    if ep not in exported:
        return "legacy_entry_not_exported"
    return _explain_row(row, evalplus=evalplus)


def reexplain(bank: str, a) -> int:
    """解釋規則新增一條之後，**只用已落盤的欄位**重新歸類 `UNEXPLAINED` 的分歧（不重跑任何碼）。
    其餘判決欄位一個都不動；manifest 記下 `equivalence.reexplained_by`。"""
    private_root = pathlib.Path(a.private_root) if a.private_root else BB.default_private_root()
    private = BB.BANKS[bank]["private"]
    path = HERE / bank / "bank_manifest.json"
    man = json.loads(path.read_text(encoding="utf-8"))
    eq = man.get("equivalence")
    if not eq:
        print(f"[{bank}] 沒有等價比對，略過")
        return 0
    evalplus = BB.BANKS[bank]["kind"] != "lcb"

    def reclassify(eq: dict) -> int:
        n = 0
        for d in eq["disagreements"]:
            d["legacy_near_timeout"] = _legacy_near_timeout(d)
            if d.get("explanation") in (None, "UNEXPLAINED"):
                new = _explain_row(d, evalplus=evalplus)
                if new != d.get("explanation"):
                    d["explanation"] = new
                    n += 1
        eq["explanations"] = EXPLANATIONS
        eq["n_disagree_legacy_near_timeout"] = sum(1 for d in eq["disagreements"] if d["legacy_near_timeout"])
        eq["n_disagree_by_explanation"] = {k: sum(1 for d in eq["disagreements"] if d.get("explanation") == k)
                                           for k in (*EXPLANATIONS, "UNEXPLAINED")}
        eq["reexplained_by"] = f"{GAUGE} --reexplain（只用已落盤欄位；改了 {n} 筆的 explanation）"
        return n

    changed = reclassify(eq)
    # gauge_detail.json 的 equivalence 是同一批列（外加失敗訊息）⇒ 同一套規則一起改，免得兩份說法不同
    detail_path = BB.tree_root(bank, private_root) / "gauge_detail.json"
    if detail_path.exists():
        det = json.loads(detail_path.read_text(encoding="utf-8"))
        if det.get("equivalence"):
            reclassify(det["equivalence"])
            detail_path.write_text(json.dumps(det, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    text = json.dumps(man, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    targets = [HERE / bank]
    if private:
        targets.append(BB.tree_root(bank, private_root))
    for t in targets:
        (t / "bank_manifest.json").write_text(text, encoding="utf-8")
        (t / "bank_manifest.sha256").write_text(f"{digest}  bank_manifest.json\n", encoding="utf-8")
    print(f"[{bank}] reexplain：改 {changed} 筆；{eq['n_disagree_by_explanation']}；manifest sha256 {digest}")
    return 0


def equiv_one(tid: str, m: dict, codes: list[str], *, task: dict, root: pathlib.Path, acc, sb,
              timeout_s: float, private: bool, sb_env=None) -> dict:
    from ops.gain.gain_run import meets_demand
    ep = task["entry_point"]
    d = m["dir"]
    tpl, hid = root / "templates" / d, root / "hidden" / d
    work = root / "_equiv_work" / d
    rows = []
    for i, code in enumerate(codes):
        t0 = time.perf_counter()
        lv, _ = meets_demand(code, task["visible_check"]["code"], LEGACY_TIMEOUT_S, entry_point=ep)
        t1 = time.perf_counter()
        lh, _ = meets_demand(code, task["hidden_check"]["code"], LEGACY_TIMEOUT_S, entry_point=ep)
        t2 = time.perf_counter()
        r = run_pair(acc, sb, tpl, hid, work, code, timeout_s=timeout_s, hidden_reps=1, tag=f"c{i}")
        rv, rh = r["visible"]["all_pass"], r["hidden"][0]["all_pass"]
        row = {"code_sha256": hashlib.sha256(code.encode()).hexdigest()[:16],
               "legacy": {"visible": lv, "hidden": lh,
                          "visible_wall_s": round(t1 - t0, 2), "hidden_wall_s": round(t2 - t1, 2)},
               "rendered": {"visible": rv, "hidden": rh,
                            "hidden_wall_ms": r["hidden"][0]["files"][0]["wall_ms"]
                            if r["hidden"][0].get("files") else None},
               "agree": (lv == rv and lh == rh)}
        if not row["agree"]:
            row["rendered_visible_detail"] = summarize(r["visible"], private=private)
            row["rendered_hidden_detail"] = summarize(r["hidden"][0], private=private)
            row["legacy_near_timeout"] = _legacy_near_timeout(row)
            # 分歧是 case 集合／比對器造成的，還是**信封**（既有判準 10 秒＋128 MiB，閘門 30 秒＋512 MiB）
            # 造成的？直接量：同一份碼、同一個渲染檔，改用既有判準的信封再跑一次。
            # 結果回到既有判準那一邊 ⇒ 分歧完全由信封解釋。
            if sb_env is not None:
                r2 = run_pair(acc, sb_env, tpl, hid, work, code, timeout_s=LEGACY_TIMEOUT_S,
                              hidden_reps=1, tag=f"e{i}")
                ev, eh = r2["visible"]["all_pass"], r2["hidden"][0]["all_pass"]
                row["rendered_in_legacy_envelope"] = {
                    "visible": ev, "hidden": eh,
                    "hidden_timed_out": summarize(r2["hidden"][0], private=private)["timed_out"]}
                row["explained_by_envelope"] = (ev == lv and eh == lh)
            # 既有檢查碼裡有 `__canon(` ⇒ 它在檢查當下跑 canonical（EvalPlus 的 _check_code）
            row["explanation"] = _explain(row, code, ep, evalplus="__canon(" in task["hidden_check"]["code"])
        rows.append(row)
    shutil.rmtree(work, ignore_errors=True)
    return {"task_id": tid, "rows": rows}


# ─────────────────────────────────────────────────────────────────────────────

def _pct(xs: list[float], q: float):
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]


def gauge_bank(bank: str, a) -> int:
    private_root = pathlib.Path(a.private_root) if a.private_root else BB.default_private_root()
    private = BB.BANKS[bank]["private"]
    root = BB.tree_root(bank, private_root)
    rm = json.loads((root / "render_manifest.json").read_text(encoding="utf-8"))
    src = BB.load_source(bank, private_root)
    refs = references(bank, src)
    from vacant_network.vrun import acceptance as acc
    from vacant_network.vrun import sandbox as sbx
    probe_dir = root / "_gauge_work" / "_probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    sb, meta = sbx.make_sandbox(a.backend, workdir=str(probe_dir))
    pyv = sb.run("command -v python3; python3 -V", workspace=probe_dir, timeout_s=30)
    tasks = rm["tasks"]
    ids = [t for t in tasks if (not a.only or t in a.only)]
    results: dict[str, dict] = {}
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(gauge_one, bank, t, tasks[t], root=root, ref=refs.get(t),
                          ep=src["tasks"][t]["entry_point"], acc=acc, sb=sb, timeout_s=a.timeout_s,
                          hidden_reps=a.hidden_reps, private=private): t for t in ids}
        for i, fu in enumerate(cf.as_completed(futs), 1):
            t = futs[fu]
            try:
                results[t] = fu.result()
            except Exception as e:  # noqa: BLE001 - 量具自己壞 ≠ 題目壞，照實記
                results[t] = {"task_id": t, "usable": False, "exclude_reason": "gauge_infra_error",
                              "error": f"{type(e).__name__}: {e}"}
            r = results[t]
            if i % 25 == 0 or not r.get("usable"):
                print(f"[{bank} {i}/{len(ids)}] {t} usable={r.get('usable')} reason={r.get('exclude_reason')} "
                      f"ref_wall={r.get('reference_max_file_wall_ms')}ms ({time.time() - t0:.0f}s)", flush=True)

    equiv = None
    if a.equiv:
        cands, blocked, sources = collect_candidates(bank, src, a.equiv)
        # 既有判準的信封（checks.py：RLIMIT_DATA 128 MiB、逾時 10 秒）——只給分歧重跑用
        sb_env, _ = sbx.make_sandbox(a.backend, workdir=str(probe_dir), memory_bytes=LEGACY_MEMORY_BYTES)
        eq_rows: dict[str, dict] = {}
        with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
            futs = {ex.submit(equiv_one, t, tasks[t], cands[t], task=src["tasks"][t], root=root, acc=acc,
                              sb=sb, timeout_s=a.timeout_s, private=private, sb_env=sb_env): t
                    for t in ids if cands.get(t)}
            for fu in cf.as_completed(futs):
                t = futs[fu]
                try:
                    eq_rows[t] = fu.result()
                except Exception as e:  # noqa: BLE001
                    eq_rows[t] = {"task_id": t, "error": f"{type(e).__name__}: {e}", "rows": []}
        allrows = [r for v in eq_rows.values() for r in v["rows"]]
        dis = [(t, r) for t, v in eq_rows.items() for r in v["rows"] if not r["agree"]]
        equiv = {
            "judge_legacy": "ops/gain/gain_run.py::meets_demand(code, loader 的 visible_check／hidden_check, 10)",
            "judge_rendered": "acceptance.run_suite（tests_visible/、hidden/）",
            "candidate_sources": sources,
            "per_task_cap": a.equiv,
            "n_tasks_with_candidates": len(eq_rows),
            "n_compared": len(allrows),
            "n_agree": sum(1 for r in allrows if r["agree"]),
            "n_disagree": len(dis),
            "n_disagree_legacy_near_timeout": sum(1 for _, r in dis if r.get("legacy_near_timeout")),
            "n_disagree_explained_by_envelope": sum(1 for _, r in dis if r.get("explained_by_envelope")),
            "n_disagree_by_explanation": {k: sum(1 for _, r in dis if r.get("explanation") == k)
                                          for k in (*EXPLANATIONS, "UNEXPLAINED")},
            "explanations": EXPLANATIONS,
            "envelope_note": ("分歧重跑：同一份碼、同一個渲染檔，改用既有判準的信封（逾時 10 秒、"
                              "RLIMIT_DATA 128 MiB）再跑一次；結果回到既有判準那一邊＝explained_by_envelope"
                              "（分歧來自信封，不是 case 集合或比對器）。"),
            "n_policy_blocked_not_compared": sum(blocked.get(t, 0) for t in ids),
            "n_hidden_pass_both": sum(1 for r in allrows if r["legacy"]["hidden"] and r["rendered"]["hidden"]),
            "n_hidden_fail_both": sum(1 for r in allrows if not r["legacy"]["hidden"] and not r["rendered"]["hidden"]),
            "disagreements": [{"task_id": t, **{k: v for k, v in r.items()
                                                 if k in ("code_sha256", "legacy", "rendered", "legacy_near_timeout",
                                                          "rendered_in_legacy_envelope", "explained_by_envelope",
                                                          "explanation",
                                                          "rendered_visible_detail", "rendered_hidden_detail")}}
                              for t, r in dis],
        }
        for t, v in eq_rows.items():
            rs = v["rows"]
            results[t]["equiv"] = {
                "n_compared": len(rs), "n_agree": sum(1 for r in rs if r["agree"]),
                "n_hidden_pass_both": sum(1 for r in rs if r["legacy"]["hidden"] and r["rendered"]["hidden"]),
                "n_policy_blocked": blocked.get(t, 0),
            }
        print(f"[{bank}] 等價比對：{equiv['n_agree']}/{equiv['n_compared']} 一致，"
              f"不一致 {equiv['n_disagree']}（其中既有判準逼近 10 秒 {equiv['n_disagree_legacy_near_timeout']}），"
              f"政策擋掉 {equiv['n_policy_blocked_not_compared']}", flush=True)

    if a.only:
        print(json.dumps(results, ensure_ascii=False, indent=1)[:20000])
        return 0

    # ── 彙整成 bank_manifest.json ─────────────────────────────────────────────
    per: dict[str, dict] = {}
    for tid in BB._task_order(bank, tasks):
        m = dict(tasks[tid])
        g = results[tid]
        if private:
            m.pop("entry_point", None)
        g_clean = {k: v for k, v in g.items() if k not in ("task_id", "dir")}
        ref_ok = g.get("reference_ok")
        eq = g.get("equiv") or {}
        if ref_ok:
            pc = "reference"
        elif eq.get("n_hidden_pass_both"):
            pc = "archived_candidate"
        else:
            pc = "none"
        per[tid] = {**m, "gauge": g_clean, "positive_control": pc,
                    "usable": g.get("usable"), "exclude_reason": g.get("exclude_reason")}
    usable = [t for t, p in per.items() if p["usable"]]
    gauge_excl = {t: p["exclude_reason"] for t, p in per.items() if not p["usable"]}
    ref_walls = [p["gauge"]["reference_max_file_wall_ms"] for p in per.values()
                 if p["usable"] and p["gauge"].get("reference_max_file_wall_ms") is not None]
    stub_walls = [max(p["gauge"]["stub"]["visible"]["wall_ms"], p["gauge"]["stub"]["hidden"]["wall_ms"])
                  for p in per.values() if p["gauge"].get("stub")]
    summary = {
        "n_upstream": rm["n_upstream"],
        "n_policy_excluded": len(rm["policy_excluded"]),
        "n_build_excluded": len(rm["build_excluded"]),
        "n_rendered": rm["n_rendered"],
        "n_gauge_excluded": len(gauge_excl),
        "n_usable": len(usable),
        "n_usable_with_reference": sum(1 for t in usable if per[t]["gauge"]["has_reference"]),
        "n_usable_positive_control": {k: sum(1 for t in usable if per[t]["positive_control"] == k)
                                      for k in ("reference", "archived_candidate", "none")},
        "stub_blocked_visible": sum(1 for t in usable if per[t]["gauge"]["stub_blocked_visible"]),
        "stub_blocked_hidden": sum(1 for t in usable if per[t]["gauge"]["stub_blocked_hidden"]),
        "stub_visible_all_blocked": sum(1 for t in usable if per[t]["gauge"]["stub_visible_failed"]
                                        == per[t]["gauge"]["stub_visible_total"]),
        "n_visible_total": sum(per[t]["n_visible"] for t in usable),
        "n_hidden_file_total": sum(per[t]["n_hidden_file"] for t in usable),
        "reference_file_wall_ms": {"n": len(ref_walls), "median": _pct(ref_walls, .5), "p90": _pct(ref_walls, .9),
                                   "p99": _pct(ref_walls, .99), "max": max(ref_walls) if ref_walls else None},
        "stub_file_wall_ms_max": max(stub_walls) if stub_walls else None,
        "reference_over_half_timeout": sorted(t for t in usable if (per[t]["gauge"].get("reference_max_file_wall_ms")
                                                                     or 0) > a.timeout_s * 1000 / 2),
        "reference_wrote_to_workspace": sorted(t for t in per if (per[t]["gauge"].get("reference") or {})
                                               .get("ws_changed")),
    }
    manifest = {
        "bank": bank, "run_id": BB.RUN_ID,
        "generated_by": [BB.GENERATOR, GAUGE],
        "source": rm["source"],
        "split_rule": rm["split_rule"],
        "trees": {
            "root": (f".vacant-private/{BB.RUN_ID}/{bank}/（私有、不進版控；Colab 用 tar.gz 上傳）"
                     if private else f"ops/vacantrun/{BB.RUN_ID}/{bank}/"),
            "workspace_template": "templates/<dir>/", "scoring_only": "hidden/<dir>/",
            "red_line": "hidden/ 不是工作區的子目錄，永遠不複製進工作區；任何把隱藏測資或其失敗訊息"
                        "回饋給模型的路徑都作廢那一批資料。",
        },
        "privacy": ("本 manifest 不含任何題目、測資或參考解的位元組（只有題號、條數、sha256、量具結果）。"
                    if private else "LCB 題庫檔本身已在 ops/gain/data/ 進版控。"),
        "policy_excluded": rm["policy_excluded"],
        "build_excluded": rm["build_excluded"],
        "gauge_excluded": gauge_excl,
        "summary": summary,
        "gauge": {
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "host": platform.node(), "platform": platform.platform(),
            "judge": "vacant_network/vrun/acceptance.py::run_suite（python3 driver.py <ws> <testfile> <nonce>），"
                     "與閘門同一份原始碼",
            "vrun_sources_sha256": {n: sha256_file(REPO / "vacant_network" / "vrun" / f"{n}.py")
                                    for n in ("acceptance", "sandbox")},
            "backend_meta": {k: meta.get(k) for k in ("backend", "network_isolated", "write_confined",
                                                       "memory_bytes", "honest_bound", "tried")},
            "accept_path": sbx.accept_path(),
            "python_in_sandbox": pyv.stdout.strip(),
            "timeout_s_per_test_file": a.timeout_s,
            "timeout_source": "gateshim.py 呼叫 launcher 時 test_timeout_s=VACANT_TEST_TIMEOUT（預設 30）",
            "hidden_reps_reference": a.hidden_reps,
            "workers": a.workers,
            "wall_note": "牆鐘是在本機 6 條並行＋其他工作的負載下量的，只當量級參考。",
            "stub": "def <entry>(*a, **k):\n    return None",
        },
        "equivalence": equiv,
        "honesty_bounds": [
            "參考解全過＋樁被擋是單邊保證：擋得住 return None 不等於可見測試涵蓋真需求"
            "（vacant_network/suitegauge.py 那句逐字適用）。",
            "positive_control=none 的題：沒有任何證據證明一個正確解會被判過（LCB 沒有官方參考解）。",
        ],
        "tasks": per,
    }
    if private:
        manifest = strip_messages(manifest)
    text = json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    out_dir = HERE / bank
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "bank_manifest.json").write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    (out_dir / "bank_manifest.sha256").write_text(f"{digest}  bank_manifest.json\n", encoding="utf-8")
    if private:
        (root / "bank_manifest.json").write_text(text, encoding="utf-8")
        (root / "bank_manifest.sha256").write_text(f"{digest}  bank_manifest.json\n", encoding="utf-8")
    detail = {t: results[t] for t in ids}
    (root / "gauge_detail.json").write_text(json.dumps(
        {"bank": bank, "results": detail, "equivalence": equiv}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    if a.prune:
        for t, p in per.items():
            if not p["usable"]:
                for sub in ("templates", "hidden"):
                    shutil.rmtree(root / sub / p["dir"], ignore_errors=True)
    shutil.rmtree(root / "_gauge_work", ignore_errors=True)
    shutil.rmtree(root / "_equiv_work", ignore_errors=True)
    print(f"[{bank}] 可用 {len(usable)}／渲染 {rm['n_rendered']}／上游 {rm['n_upstream']}；"
          f"量具排除 {gauge_excl}；manifest sha256 {digest}")
    return 0


def selfcheck(bank: str, a) -> int:
    """**不需要題庫原始檔**的重驗（給 Colab）：在實驗那台機器、那個 python3 上，
    用已知答案再試一次尺——參考解（有的話）可見與隱藏全過、退化樁在可見被擋。

    參考解從哪來：LCB＝repo 的 `ops/gain/data/lcb*_probe_solutions.json`；
    MBPP+／HumanEval+＝私有樹的 `reference/<dir>/solution.py`（另一個 tar，跑完就刪）。
    沒有參考解的題只驗樁。不寫 manifest；結果寫到 `<tree>/selfcheck_<host>.json`。
    """
    import re
    private_root = pathlib.Path(a.private_root) if a.private_root else BB.default_private_root()
    private = BB.BANKS[bank]["private"]
    root = BB.tree_root(bank, private_root)
    man = json.loads((root / "bank_manifest.json").read_text(encoding="utf-8"))
    from vacant_network.vrun import acceptance as acc
    from vacant_network.vrun import sandbox as sbx
    probe_dir = root / "_gauge_work" / "_probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    sb, meta = sbx.make_sandbox(a.backend, workdir=str(probe_dir))
    pyv = sb.run("command -v python3; python3 -V", workspace=probe_dir, timeout_s=30).stdout.strip()
    usable = [t for t, p in man["tasks"].items() if p.get("usable")]
    refs: dict[str, tuple[str, str]] = {}
    eps: dict[str, str] = {}
    if private:
        for t in usable:
            d = root / "reference" / man["tasks"][t]["dir"]
            if (d / "solution.py").exists():
                refs[t] = ((d / "solution.py").read_text(encoding="utf-8"), "reference/")
            stub = (d / "stub.py").read_text(encoding="utf-8") if (d / "stub.py").exists() else ""
            mm = re.match(r"def (\w+)\(", stub)
            if mm:
                eps[t] = mm.group(1)
        if not refs:
            print(f"[{bank}] ⚠ 沒有 reference/（參考解包沒解開？）⇒ 參考解與樁都驗不了——量不到不是通過。")
            return 1
    else:
        name = "lcb_v3_probe_solutions.json" if bank == "lcb_v3" else "lcb_probe_solutions.json"
        probes = json.loads((REPO / "ops" / "gain" / "data" / name).read_text(encoding="utf-8"))
        refs = {t: (c, f"probe:{name}") for t, c in probes.items() if t in usable}
        eps = {t: man["tasks"][t]["entry_point"] for t in usable}
    missing_ep = [t for t in usable if t not in eps]
    if missing_ep:
        print(f"[{bank}] ⚠ {len(missing_ep)} 題找不到函式名，樁建不起來：{missing_ep[:5]}")
        return 1
    results: dict[str, dict] = {}
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(gauge_one, bank, t, man["tasks"][t], root=root, ref=refs.get(t), ep=eps[t],
                          acc=acc, sb=sb, timeout_s=a.timeout_s, hidden_reps=a.hidden_reps,
                          private=private): t for t in usable}
        for fu in cf.as_completed(futs):
            t = futs[fu]
            try:
                results[t] = fu.result()
            except Exception as e:  # noqa: BLE001
                results[t] = {"usable": False, "exclude_reason": "gauge_infra_error", "error": repr(e)}
    shutil.rmtree(root / "_gauge_work", ignore_errors=True)
    bad = {t: r.get("exclude_reason") for t, r in results.items() if not r.get("usable")}
    walls = [r["reference_max_file_wall_ms"] for r in results.values() if r.get("reference_max_file_wall_ms")]
    out = {
        "bank": bank, "host": platform.node(), "platform": platform.platform(),
        "python_in_sandbox": pyv, "accept_path": sbx.accept_path(),
        "backend": meta.get("backend"), "memory_bytes": meta.get("memory_bytes"),
        "timeout_s": a.timeout_s, "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "n_usable": len(usable), "n_with_reference": len(refs),
        "n_reference_ok": sum(1 for t in refs if results[t].get("reference_ok")),
        "n_stub_blocked_visible": sum(1 for r in results.values() if r.get("stub_blocked_visible")),
        "reference_file_wall_ms_max": max(walls) if walls else None,
        "failures": bad,
        "manifest_sha256_expected_from_file": (root / "bank_manifest.sha256").read_text().split()[0]
        if (root / "bank_manifest.sha256").exists() else None,
    }
    (root / f"selfcheck_{platform.node() or 'host'}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[{bank}] selfcheck：參考解 {out['n_reference_ok']}/{out['n_with_reference']} 全過、"
          f"樁在可見被擋 {out['n_stub_blocked_visible']}/{len(usable)}、失敗 {len(bad)} {dict(list(bad.items())[:5])}"
          f"；python3＝{pyv.splitlines()[-1] if pyv else '?'}；參考解最慢單檔 {out['reference_file_wall_ms_max']} ms")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="五組工作區題庫的量具（零模型呼叫）")
    ap.add_argument("--selfcheck", action="store_true",
                    help="不需要題庫原始檔的重驗（Colab 用）：參考解＋樁，不寫 manifest")
    ap.add_argument("--reexplain", action="store_true",
                    help="只用已落盤欄位重新歸類 UNEXPLAINED 的等價分歧（不重跑任何碼）")
    ap.add_argument("--bank", default="all")
    ap.add_argument("--private-root", default=None)
    ap.add_argument("--backend", default="none", help="閘門（gateshim）固定用 none")
    ap.add_argument("--timeout-s", type=float, default=30.0)
    ap.add_argument("--hidden-reps", type=int, default=2)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--equiv", type=int, default=0, help="每題最多比對幾份已歸檔候選碼（0＝不比）")
    ap.add_argument("--only", nargs="*", default=None, help="只量這幾題（偵錯用；不寫 manifest）")
    ap.add_argument("--prune", action="store_true", help="把量具排除的題從兩棵樹刪掉（manifest 仍具名記錄）")
    a = ap.parse_args(argv)
    banks = list(BB.BANKS) if a.bank == "all" else a.bank.split(",")
    unknown = [b for b in banks if b not in BB.BANKS]
    if unknown:
        raise SystemExit(f"未知的 bank {unknown}")
    rc = 0
    for b in banks:
        if a.selfcheck:
            rc |= selfcheck(b, a)
        elif a.reexplain:
            rc |= reexplain(b, a)
        else:
            rc |= gauge_bank(b, a)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
