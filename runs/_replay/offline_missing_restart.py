#!/usr/bin/env python3
"""Offline analysis: how often is a "missing" (no-delivery) failure rescuable by a re-run?

Input: c37_final.json — 1187 archived cells (C37 era, Antigravity harness),
fields per cell: cell, task_dir, pass, status, findings, num_reviews.

`status == "missing"` = the expected deliverable was not present at scoring time.
This is the archived signature of the same no-delivery pattern observed on
qwen3.8-27b lcb_3487 (reasoning-only 32k-token loop, finish_reason=length,
content="").

Question answered here (lower bound / upper bound, no LLM calls):
  - what share of groups ever produce a missing attempt;
  - of those, how many have ANY passing attempt in the same
    (condition, task) group  => "rescuable in the archive";
  - policy ceiling: pass@1  vs  pass@1 or (missing@1 and any later pass).

Caveats (state with the numbers):
  - archived re-runs carried NO hint file; this measures "plain re-run rescues",
    which is the floor for a hint-assisted retry;
  - "any later pass" credits the best remaining attempt (oracle-like selection),
    so the delta is a CEILING, not a measured effect;
  - different model/era (C37), so the direction transfers, the magnitude may not;
  - "missing" comes from the archived scorer's `status` field; dabstep cells do
    not emit "missing" at all (the pattern is only visible on the other 3 banks).

Re-run:  python3 offline_missing_restart.py
"""
import collections
import json
import re
from pathlib import Path

SRC = Path(__file__).with_name("c37_final.json")


def main() -> None:
    d = json.loads(SRC.read_text(encoding="utf-8"))
    groups: dict[str, list[tuple[int, dict]]] = collections.defaultdict(list)
    for c in d:
        m = re.match(r"^(.*-s)(\d+)$", c["cell"])
        key = m.group(1) if m else c["cell"]
        groups[key].append((int(m.group(2)) if m else 1, c))

    n_groups = len(groups)
    miss_groups = miss_rescued = miss_alone = later = 0
    rescued_by_bank: dict[str, int] = collections.Counter()
    for key, cells in groups.items():
        cells.sort(key=lambda t: t[0])
        statuses = [c["status"] for _, c in cells]
        passes = [bool(c["pass"]) for _, c in cells]
        if "missing" not in statuses:
            continue
        miss_groups += 1
        if any(passes):
            miss_rescued += 1
            rescued_by_bank[key.split("-C37-")[1].split("-")[0]] += 1
        else:
            miss_alone += 1
        idx_m = [i for i, s in enumerate(statuses) if s == "missing"]
        if any(passes[j] for i in idx_m for j in range(i + 1, len(statuses))):
            later += 1

    pass1 = sum(1 for cells in groups.values() if cells[0][1]["pass"])
    restart = sum(1 for cells in groups.values()
                  if cells[0][1]["pass"] or any(c[1]["pass"] for c in cells[1:]))

    out = {
        "source": str(SRC),
        "n_cells": len(d),
        "n_groups": n_groups,
        "fail_cells": sum(1 for c in d if not c["pass"]),
        "missing_cells": sum(1 for c in d if c["status"] == "missing"),
        "missing_share_of_failures": None,
        "groups_with_missing": miss_groups,
        "groups_rescuable_in_archive": miss_rescued,
        "groups_never_delivered": miss_alone,
        "missing_with_strictly_later_pass": later,
        "rescued_groups_by_bank": dict(rescued_by_bank),
        "pass1_groups": pass1,
        "pass1_rate": round(pass1 / n_groups, 4),
        "restart_ceiling_groups": restart,
        "restart_ceiling_rate": round(restart / n_groups, 4),
        "delta_pp_ceiling": round((restart - pass1) / n_groups * 100, 2),
        "caveats": [
            "plain re-runs, no hint file; floor for hint-assisted retry",
            "any-later-pass = oracle-like ceiling, not a measured effect",
            "C37-era model; direction transfers, magnitude may not",
            "dabstep cells do not emit status=missing",
        ],
    }
    out["missing_share_of_failures"] = round(
        out["missing_cells"] / out["fail_cells"], 4)
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
