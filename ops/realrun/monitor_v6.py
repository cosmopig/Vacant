#!/usr/bin/env python3
"""Interim health monitor for the v6 batch (prereg_v6.json); round 109 adds
--batch v7 (prereg_v7.json, cross-model replication) reusing the same 68-cell
grid. The pair/statistic logic is batch-agnostic; only the run-root, prereg
and analyze file names follow the batch.

Read-only. Prints per-rep completeness and INTERIM descriptive tallies.
It NEVER assigns a decision state: per the pre-registered INCOMPLETE rule,
a decision exists only after all 5 reps are complete, via prereg_analyze.py.
Interim (b, c, p) figures are descriptive only and must not be quoted as a
result (same discipline as v4/v5 interim tallies in STATE.md).

Usage:
  python3 ops/realrun/monitor_v6.py [--runs-root ~/dev/ops/realrun] [--batch v6|v7]
Exit: 0 always (monitoring, not gating); 2 if the runs root is missing.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
try:
    import vacant_network  # noqa: F401
except ImportError:
    sys.path.insert(0, str(HERE.parent.parent))
from vacant_network.research import mcnemar_exact  # noqa: E402

CELLS_PER_REP = 68  # 34 tasks x 2 arms
REPS = 5


def read_progress(root: Path) -> list[dict]:
    p = root / "progress.jsonl"
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            out.append({"task": None, "arm": None, "accepted": None,
                        "infra_void": "bad_line", "stop_reason": "bad_line"})
    return out


def pairs(rows: list[dict]) -> tuple[int, int, int, int]:
    """(b, c, a, d) per the pre-registered (task, rep) pair definition."""
    bytask: dict[str, dict] = {}
    for r in rows:
        if r.get("task") is None:
            continue
        bytask.setdefault(r["task"], {})[r.get("arm")] = r
    b = c = a = d = 0
    for t, arms in bytask.items():
        A = arms.get("A_none", {}).get("accepted")
        B = arms.get("B_resample3", {}).get("accepted")
        if A is None or B is None:
            continue
        if A and not B:
            b += 1
        elif B and not A:
            c += 1
        elif A and B:
            a += 1
        else:
            d += 1
    return b, c, a, d


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs-root", default="~/dev/ops/realrun")
    # round 109: v7 (cross-model replication, prereg_v7.json) reuses this
    # monitor; default stays v6 so existing pinned behavior is unchanged.
    ap.add_argument("--batch", choices=("v6", "v7"), default="v6")
    args = ap.parse_args()
    base = Path(args.runs_root).expanduser()
    if not base.is_dir():
        print(f"ERROR: runs root not found: {base}", file=sys.stderr)
        return 2

    batch = args.batch
    done_cells = 0
    ready = True
    for k in range(1, REPS + 1):
        root = base / f"runs_{batch}_r{k}"
        rows = read_progress(root)
        cells = len(rows)
        done_cells += cells
        complete = cells == CELLS_PER_REP
        ready = ready and complete
        void = sum(1 for r in rows if r.get("infra_void"))
        bad = sum(1 for r in rows if r.get("arm") is None)
        if not root.exists():
            print(f"r{k}: not started")
            continue
        byarm: dict[str, dict] = {}
        for r in rows:
            arm = r.get("arm") or "?"
            agg = byarm.setdefault(arm, {"pass": 0, "fail": 0, "void": 0})
            if r.get("accepted"):
                agg["pass"] += 1
            else:
                agg["fail"] += 1
            if r.get("infra_void"):
                agg["void"] += 1
        arms_txt = "  ".join(
            f"{a}: {v['pass']}pass/{v['fail']}fail" + (f"/{v['void']}void" if v["void"] else "")
            for a, v in sorted(byarm.items())
        )
        status = "COMPLETE" if complete else f"in progress ({cells}/{CELLS_PER_REP})"
        line = f"r{k}: {status}  {arms_txt}"
        if complete:
            b, c, a, d = pairs(rows)
            n = a + b + c + d
            p = mcnemar_exact(b, c) if (b + c) > 0 else None
            p_txt = f"p={p:.4f}" if p is not None else "p=n/a(no discordant)"
            line += f"  INTERIM(b={b},c={c},a={a},d={d},n={n}, {p_txt})  # descriptive only"
        if bad:
            line += f"  WARNING: {bad} malformed progress lines"
        print(line)

    print(f"TOTAL: {done_cells}/{REPS * CELLS_PER_REP} cells")
    if ready:
        print("READY_TO_ANALYZE: all 5 reps complete.")
        print(f"  cd {Path.home()}/dev/Vacant && "
              f"python3 ops/realrun/prereg_analyze.py --prereg ops/realrun/prereg_{batch}.json "
              " --roots " + " ".join(f"{base}/runs_{batch}_r{k}" for k in range(1, REPS + 1))
              + f" --json ops/realrun/analyze_{batch}.json")
    else:
        print("NOT_READY: decision only after 5 reps (prereg INCOMPLETE rule). "
              f"Resume is infra, not a design change: re-run launch_{batch}.sh (idempotent).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
