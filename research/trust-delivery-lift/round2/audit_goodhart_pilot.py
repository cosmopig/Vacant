#!/usr/bin/env python3
"""Goodhart gap on pilot_excluded rows only: P(oracle_fail | visible_pass) + gated coverage."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

PILOT = Path(__file__).parent / "data/holdout_05b/pilot_excluded_tasks.json"
ROWS = Path(__file__).parent / "data/holdout_05b/rows.jsonl"


def main() -> None:
    ex = set(json.loads(PILOT.read_text(encoding="utf-8"))["task_ids"])
    by: dict[str, list[dict]] = defaultdict(list)
    for line in ROWS.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["task_id"] not in ex:
            continue
        by[r["arm"]].append(r)
    out = {}
    for arm, rs in sorted(by.items()):
        vp = [r for r in rs if r.get("visible_all_pass")]
        cov = len(vp) / len(rs) if rs else 0
        p_fail_given_vis = sum(1 for r in vp if not r.get("oracle_whole_success")) / len(vp) if vp else float("nan")
        out[arm] = {"n": len(rs), "visible_pass_coverage": cov, "p_oracle_fail_given_visible_pass": p_fail_given_vis}
    Path(__file__).parent.joinpath("GOODHART_PILOT_EXCLUDED.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()