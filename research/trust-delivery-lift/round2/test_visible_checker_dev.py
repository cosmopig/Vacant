#!/usr/bin/env python3
"""Dev-only checker tests (dev_ids gold); must not iterate holdout split."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from checks import FIELDS, visible_all_pass, oracle_whole


def main() -> None:
    bank = json.loads(Path(__file__).parent.joinpath("tasks_r2.json").read_text(encoding="utf-8"))
    fails = []
    n_gold = 0
    for tid in bank["split"]["dev_ids"]:
        task = next(t for t in bank["tasks"] if t["task_id"] == tid)
        if not task.get("answerable", True):
            continue
        doc = {f: str(task["gold"][f]) for f in FIELDS}
        vis, per = visible_all_pass(doc, task)
        ora = oracle_whole(doc, task)
        n_gold += 1
        if not vis or not ora:
            fails.append((tid, per, vis, ora))
    # Specificity: deliberate wrong field values must fail visible (dev only).
    spec_fails = []
    for tid in bank["split"]["dev_ids"][:40]:
        task = next(t for t in bank["tasks"] if t["task_id"] == tid)
        if not task.get("answerable", True):
            continue
        doc = {f: str(task["gold"][f]) for f in FIELDS}
        bad = copy.deepcopy(doc)
        bad["vendor"] = "ZZZ_NOT_IN_SOURCE_9f3c"
        vis, _ = visible_all_pass(bad, task)
        if vis:
            spec_fails.append(tid)
    if fails:
        for f in fails[:5]:
            print("GOLD_FAIL", f)
        raise SystemExit(1)
    if spec_fails:
        print("SPEC_FAIL", spec_fails[:5])
        raise SystemExit(2)
    print(f"OK: dev_ids gold visible+oracle n={n_gold}; specificity perturbations fail n=40")


if __name__ == "__main__":
    main()