#!/usr/bin/env python3
"""探索批次敏感度（事後）：在原評分與第二正規化器重評下，算 B48 字面判定（expT_escape_v4_b48literal_runs.jsonl）的
「整對排除任何越界」版本，和同一份 score_cell＋paired_comparison（同 expT_escape.py）。用法：expT_regrade_b48.py ROOT OUT.json"""
import json, pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import regrade_sensitivity as RS  # noqa: E402
M = RS.M
root = pathlib.Path(sys.argv[1]); REPO = HERE.parents[2]
runs = [json.loads(l) for l in (REPO / "ops/redo/audit/expT_exam37_20261128/expT/expT_escape_v4_b48literal_runs.jsonl").read_text().splitlines()]
excl = {(r["set"], int(r["rep"])) for r in runs if r.get("escape")}
run = json.loads((root / "RUN.json").read_text()); plan = run["plan_body"]; truth = M.load_manifests_with_truth(plan)
reps = int(plan.get("reps") or 2); arms = list(plan["arms"]); sets = list(truth)


def score_all():
    bk = {}
    for sid, st in truth.items():
        for rep in range(1, reps + 1):
            rd = root / "cells" / sid / f"r{rep}"; c0 = (rd / "c0" / "report.md").read_text(errors="replace")
            for arm in arms:
                cd = json.loads((rd / arm / "cell.json").read_text())
                bk[(sid, rep, arm)] = M.score_cell(cd, c0, (rd / arm / "report.md").read_text(errors="replace"), st, chain_path=None, verify_chain=False)
    return bk


out = {"note": "事後；B48 字面判定的越界對整對排除（v4 清單）；原評分與第二正規化器重評並列。", "excluded_pairs": len(excl), "versions": {}}
for mode in ("original", "regraded"):
    M.strict_status = RS._ORIG if mode == "original" else RS.lenient_status
    bk = score_all(); bk2 = {k: v for k, v in bk.items() if (k[0], k[1]) not in excl}
    res = {}
    for t, c in (("T", "G"), ("T", "TB"), ("T", "A"), ("G", "A")):
        pc_ = M.paired_comparison(bk2, sets, reps, treatment=t, control=c)
        res[f"{t}_vs_{c}"] = {"pairs": pc_["paired_cells"], "diff": pc_["per_set_correct_prop_diff"], "ci95": pc_["per_set_correct_prop_diff_ci95"]}
    out["versions"][mode] = res
pathlib.Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=1)); print(json.dumps(out, ensure_ascii=False))
