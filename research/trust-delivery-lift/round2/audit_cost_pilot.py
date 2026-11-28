#!/usr/bin/env python3
"""Cost parity audit on pilot_excluded rows only (broken-checker exploratory; not confirmatory)."""
from __future__ import annotations

import json
import statistics
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
    out = {"source": "pilot_excluded hold_000-021 only", "n_tasks": len(ex), "arms": {}}
    for arm, rs in sorted(by.items()):
        cpus = [r["cpu_seconds"] for r in rs]
        toks = [r["prompt_tokens"] + r["completion_tokens"] for r in rs]
        calls = [r["n_calls"] for r in rs]
        out["arms"][arm] = {
            "n": len(rs),
            "cpu_seconds": {"mean": statistics.mean(cpus), "median": statistics.median(cpus), "min": min(cpus), "max": max(cpus)},
            "tokens": {"mean": statistics.mean(toks), "median": statistics.median(toks)},
            "n_calls": {"mean": statistics.mean(calls), "counts": dict(sorted({c: calls.count(c) for c in set(calls)}.items()))},
        }
    Path(__file__).parent.joinpath("COST_PARITY_AUDIT.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()