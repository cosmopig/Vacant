#!/usr/bin/env python3
"""Dev-only: gold-as-delivery must pass visible checks (no holdout)."""
from __future__ import annotations

import json
from pathlib import Path

from checks import FIELDS, visible_all_pass, oracle_whole


def main() -> None:
    bank = json.loads(Path(__file__).parent.joinpath("tasks_r2.json").read_text(encoding="utf-8"))
    fails = []
    for split in ("dev_ids", "holdout_answerable_ids"):
        for tid in bank["split"][split]:
            task = next(t for t in bank["tasks"] if t["task_id"] == tid)
            if not task.get("answerable", True):
                continue
            doc = {f: str(task["gold"][f]) for f in FIELDS}
            vis, per = visible_all_pass(doc, task)
            ora = oracle_whole(doc, task)
            if not vis or not ora:
                fails.append((tid, split, per, vis, ora))
    if fails:
        for f in fails[:5]:
            print("FAIL", f)
        raise SystemExit(1)
    print(f"OK: {len(bank['split']['dev_ids']) + len(bank['split']['holdout_answerable_ids'])} gold docs pass visible+oracle")


if __name__ == "__main__":
    main()