#!/usr/bin/env python3
"""Exploratory: VACANT confirmatory oracle-failure anatomy (not primary)."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from checks import FIELDS, _float, visible_all_pass

ROOT = Path(__file__).parent


def oracle_mismatch_fields(task: dict, doc: dict) -> list[str]:
    wrong: list[str] = []
    gold = task["gold"]
    for f in FIELDS:
        gv, dv = str(gold[f]).strip(), str(doc.get(f, "")).strip()
        if f == "currency":
            if dv.upper() != gv.upper():
                wrong.append(f)
        elif f in ("subtotal", "tax", "total"):
            if _float(gv) != _float(dv):
                wrong.append(f)
        elif gv != dv:
            wrong.append(f)
    return wrong


def main() -> None:
    bank = json.loads((ROOT / "tasks_r2.json").read_text(encoding="utf-8"))
    by_id = {t["task_id"]: t for t in bank["tasks"]}
    rows_path = ROOT / "data/holdout_05b_confirmatory/rows.jsonl"
    rows = [json.loads(l) for l in rows_path.read_text().splitlines() if l.strip()]
    vac = [r for r in rows if r["arm"] == "VACANT"]
    fails = [r for r in vac if not r.get("oracle_whole_success")]

    goodhart: list[tuple[dict, list[str]]] = []
    vis_fail: list[tuple[dict, dict]] = []
    for r in fails:
        task = by_id[r["task_id"]]
        doc = r["final"]
        vis, per = visible_all_pass(doc, task)
        if vis:
            goodhart.append((r, oracle_mismatch_fields(task, doc)))
        else:
            vis_fail.append((r, per))

    all_vis_pass = [r for r in vac if r.get("visible_all_pass")]
    false_release = [r for r in all_vis_pass if not r.get("oracle_whole_success")]

    out = {
        "label": "exploratory_confirmatory_failure_anatomy",
        "n_vacant": len(vac),
        "oracle_failures": len(fails),
        "bucket_A_goodhart_visible_pass_oracle_fail": {
            "n": len(goodhart),
            "fraction_of_oracle_fails": len(goodhart) / len(fails) if fails else 0.0,
            "oracle_wrong_field_counts": dict(Counter(f for _, ws in goodhart for f in ws)),
            "clause_note": "Visible 'vendor' clause = provenance in source + min length — not exact match to gold.",
        },
        "bucket_B_visible_fail_oracle_fail_unrepaired": {
            "n": len(vis_fail),
            "fraction_of_oracle_fails": len(vis_fail) / len(fails) if fails else 0.0,
            "failing_clause_reasons": dict(
                Counter(f"{k}:{reason}" for _, per in vis_fail for k, (ok, reason) in per.items() if not ok)
            ),
        },
        "release_safety_exploratory": {
            "n_shipped_by_visible_gate": len(all_vis_pass),
            "n_false_release_visible_pass_oracle_fail": len(false_release),
            "false_release_rate_among_visible_pass": len(false_release) / len(all_vis_pass) if all_vis_pass else float("nan"),
        },
    }
    out_path = ROOT / "data/holdout_05b_confirmatory/FAILURE_ANATOMY_VACANT_EXPLORATORY.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()