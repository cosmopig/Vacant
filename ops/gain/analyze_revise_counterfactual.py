#!/usr/bin/env python3
"""反事實分析：ON 臂被丟掉的修訂稿，如果交付了會怎樣？

round55 量到 `revision_transition` 在 52 題裡 improved=0/harmed=0。這支工具
回答那是「機制無效」還是「選版邏輯把好修訂丟掉」——把 calls.jsonl 裡
**實際存在但未被交付**的 revised_code 拿去跑 hidden_check。

判準寫在 ops/gain/DECISION_20260824_REVISE_COUNTERFACTUAL.md（量測之前寫的）。

⚠ 這支只讀已落盤的 run 目錄，不發任何模型呼叫、不改任何 run 檔案。
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ops.gain.gain_run import extract_code, load_tasks, meets_demand, InfraVoid  # noqa: E402


def load_calls(run_dir: pathlib.Path) -> dict[str, dict[str, str]]:
    """task_id -> {"initial": 回應全文, "revise": 回應全文}（取最後一筆成功的）。"""
    out: dict[str, dict[str, str]] = collections.defaultdict(dict)
    for line in (run_dir / "calls.jsonl").open():
        if not line.strip():
            continue
        c = json.loads(line)
        if not c.get("ok"):
            continue
        meta = c.get("meta") or {}
        if meta.get("arm") != "ON":
            continue
        tid = meta.get("task_id")
        if not tid:
            continue
        if c.get("role") == "gen" and meta.get("phase") == "initial":
            out[tid]["initial"] = c.get("response") or ""
        elif c.get("role") == "revise":
            out[tid]["revise"] = c.get("response") or ""
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--seed", required=True)
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--bank", default="evalplus")
    ap.add_argument("--json-out", default="")
    args = ap.parse_args()

    run_dir = pathlib.Path(args.run)
    tasks = {t["task_id"]: t for t in load_tasks(args.bank, args.seed, args.n)}
    calls = load_calls(run_dir)
    rows = [json.loads(l) for l in (run_dir / "rows.jsonl").open() if l.strip()]
    rows = [r for r in rows if r.get("arm") == "ON"]

    fence_missing = 0
    harness_mismatch = []
    recs = []
    for r in rows:
        tid = r["task_id"]
        t = tasks.get(tid)
        c = calls.get(tid, {})
        if t is None or "initial" not in c or "revise" not in c:
            recs.append({"task_id": tid, "status": "missing_call_or_task"})
            continue
        icode = extract_code(c["initial"])
        rcode = extract_code(c["revise"])
        if "```" not in c["revise"]:
            fence_missing += 1
        try:
            i_v, _ = meets_demand(icode, t["visible_check"]["code"], entry_point=t.get("entry_point"))
            i_h, _ = meets_demand(icode, t["hidden_check"]["code"], entry_point=t.get("entry_point"))
            r_v, _ = meets_demand(rcode, t["visible_check"]["code"], entry_point=t.get("entry_point"))
            r_h, _ = meets_demand(rcode, t["hidden_check"]["code"], entry_point=t.get("entry_point"))
        except InfraVoid as e:
            recs.append({"task_id": tid, "status": f"infra_void: {e}"})
            continue

        sel = r.get("selected_version", "")
        trans = r.get("revision_transition")
        # harness 自我驗證：重算的初稿真值必須與 rows 記的 transition 一致
        implied = {"stayed_correct": True, "harmed": True,
                   "stayed_wrong": False, "improved": False}.get(trans)
        if implied is not None and implied != i_h:
            harness_mismatch.append({"task_id": tid, "transition": trans, "recomputed_i_h": i_h})

        kept_initial = sel.startswith("initial")
        if sel == "revised_both_visible_fail":
            cat = "dead_branch"
        elif kept_initial and not i_h and r_h:
            cat = "discarded_win"
        elif kept_initial and i_h and not r_h:
            cat = "discarded_harm_avoid"
        elif i_h == r_h:
            cat = "no_opportunity"
        else:
            cat = "other"
        recs.append({"task_id": tid, "status": "ok", "selected_version": sel,
                     "transition": trans, "i_v": i_v, "i_h": i_h,
                     "r_v": r_v, "r_h": r_h, "category": cat,
                     "identical_code": icode.strip() == rcode.strip()})

    ok = [x for x in recs if x.get("status") == "ok"]
    cats = collections.Counter(x["category"] for x in ok)
    out = {
        "run": str(run_dir), "rows_on": len(rows), "analyzed": len(ok),
        "skipped": [x for x in recs if x.get("status") != "ok"],
        "fence_missing": fence_missing,
        "fence_missing_frac": (fence_missing / len(ok)) if ok else None,
        "harness_mismatch": harness_mismatch,
        "categories": dict(cats),
        "identical_code_count": sum(1 for x in ok if x["identical_code"]),
        "revised_hidden_pass": sum(1 for x in ok if x["r_h"]),
        "initial_hidden_pass": sum(1 for x in ok if x["i_h"]),
        "detail": ok,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if args.json_out:
        pathlib.Path(args.json_out).write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
