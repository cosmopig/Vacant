"""離線解剖 reviewer 角色：它到底吐出什麼、哪些訊號被丟掉、留著還有沒有用。

零模型呼叫。只讀 runs/<run>/calls.jsonl 裡已經落盤的 review 回應，
重放 gain_run 自己的 `_review_vote` / `parse_review_claim` /
`verify_review_counterexample`（不重寫判準）。

V/GT 分離：`hidden_check` 與 canonical solution 只在**分析側**使用
（算「reviewer 的 FAIL 是否對應隱藏失敗」「宣稱的 EXPECTED 對不對」），
不進任何選擇規則、不進任何 prompt。
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ops" / "gain"))

os.environ.setdefault(
    "VACANT_EVALPLUS_PATH", str(ROOT / ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"))

import gain_run as G  # noqa: E402
from vacant.codebench import EvalPlusMBPPLoader  # noqa: E402

SEED = "g-r212-route-20260828"


def load_tasks():
    return {t["task_id"]: t for t in EvalPlusMBPPLoader(expose_contract=True).iter_tasks(SEED)}


def candidate_from_prompt(prompt: str) -> str | None:
    marker = "候選解答："
    if marker not in prompt:
        return None
    return G.extract_code(prompt.split(marker, 1)[1])


def safe_meets(code, check, entry_point):
    try:
        ok, _ = G.meets_demand(code, check, entry_point=entry_point)
        return ok
    except Exception:
        return None


def verdict_class(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return "empty"
    first = s.splitlines()[0].strip().upper()
    if first == "VERDICT: PASS":
        return "PASS"
    if first == "VERDICT: FAIL":
        return "FAIL"
    return "malformed"


def analyze(run: str, tasks, canon, out):
    path = ROOT / "runs" / run / "calls.jsonl"
    rows = []
    agent_model = {}
    for line in path.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("role") == "gen":
            agent_model.setdefault(r.get("agent_id"), r.get("model"))
        rows.append(r)

    code_cache: dict[tuple[str, str], tuple] = {}

    def code_status(task_id, code):
        key = (task_id, code)
        if key not in code_cache:
            t = tasks[task_id]
            ep = t.get("entry_point")
            code_cache[key] = (
                safe_meets(code, t["visible_check"]["code"], ep),
                safe_meets(code, t["hidden_check"]["code"], ep),
            )
        return code_cache[key]

    recs = []
    for r in rows:
        if r.get("role") != "review":
            continue
        meta = r.get("meta") or {}
        task_id = meta.get("task_id")
        if task_id not in tasks:
            continue
        t = tasks[task_id]
        ep = t.get("entry_point")
        text = r.get("response") or ""
        ok_call = bool(r.get("ok"))
        code = candidate_from_prompt(r.get("prompt") or "")
        rec = {
            "run": run,
            "task_id": task_id,
            "reviewer": r.get("agent_id"),
            "reviewer_model": r.get("model"),
            "target": meta.get("target"),
            "target_model": agent_model.get(meta.get("target")),
            "ok_call": ok_call,
            "vclass": verdict_class(text) if ok_call else "call_failed",
            "raw_pass": G._review_vote(text) if ok_call else None,
        }
        if not ok_call or code is None:
            rec["claim"] = "n/a"
            recs.append(rec)
            continue
        rec["cand_visible_ok"], rec["cand_hidden_ok"] = code_status(task_id, code)
        claim = G.parse_review_claim(text)
        if rec["vclass"] == "PASS":
            rec["claim"] = "pass_no_claim"
        elif claim is None:
            # distinguish "explicit NONE" from "junk"
            has_fields = any(
                ln.partition(":")[0].strip().upper() in {"TEST_ARGS", "EXPECTED"}
                for ln in text.strip().splitlines())
            rec["claim"] = "fail_none_or_missing" if has_fields else "fail_no_fields"
        else:
            rec["claim"] = "fail_parsed"
            args, expected = claim
            confirmed, status = G.verify_review_counterexample(
                code, ep, text,
                input_contract=t.get("input_contract", ""),
                input_parameters=t.get("input_parameters", []),
            )
            rec["confirmed"] = confirmed
            rec["ce_status"] = status
            # ANALYSIS ONLY: is the claimed EXPECTED the ground-truth value?
            sol = canon.get(task_id, "")
            if sol:
                chk = G.counterexample_check(ep, args, expected)
                rec["expected_matches_gt"] = safe_meets(sol, chk, ep)
            else:
                rec["expected_matches_gt"] = None
        recs.append(rec)

    with (ROOT / "ops/gain/replay" / out).open("w", encoding="utf-8") as f:
        for rec in recs:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return recs


if __name__ == "__main__":
    tasks = load_tasks()
    canon = G._canonical_solutions("evalplus")
    for run in sys.argv[1:]:
        recs = analyze(run, tasks, canon, f"reviewer_anatomy_{run}.jsonl")
        print(run, "review calls:", len(recs))
        print("  vclass:", dict(Counter(r["vclass"] for r in recs)))
        print("  claim:", dict(Counter(r.get("claim") for r in recs)))
