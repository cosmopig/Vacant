#!/usr/bin/env python3
"""Offline (zero LLM calls) simulation of "verifier-guided restart" policies on archived runs.

Input: c37_final.json (this directory) — the 2026-10-25 replay snapshot of 1187 archived
C37-era cells (Antigravity harness), one row per cell with keys:
  cell, task_dir, pass, status, findings_final, ...
`pass` comes from the archived scorer (the grader). `findings_final` is Vacant's
record-based evidence run over the cell's own record (NO grader input) — that is the
"real signal" column.
Cells are grouped by (suite, batch prefix, task) so that only runs of the same
condition are mixed.

Policies (each attempt = one full independent agent run, taken in cell-name order, cyclic):
  pass@1                      : expected pass rate of a single run
  restart-if-flagged (cap K)  : rerun while Vacant's final findings are non-empty
                                = the REAL-SIGNAL column (driven by Vacant, not the grader)
  restart-if-test-fail (cap K): rerun while the run fails — valid proxy ONLY when the
                                visible tests are identical to the grader (polyglot_py);
                                on the other banks this is an UPPER BOUND, not an effect
  oracle@k                    : at least one run of the group passes

Usage:
  python3 offline_restart_sim.py                # the cited table (cap=3)
  python3 offline_restart_sim.py --cap K        # another cap
  python3 offline_restart_sim.py --signal-stats # precision/recall/rescue of the real signal
  python3 offline_restart_sim.py --json         # machine output of both tables

Provenance: the raw C37 archive (the tar chunks the replay read) no longer exists on
this machine (checked 2026-10-25: /srv/eval empty, no *.tar.xz under /home, /tmp,
/var/tmp). c37_final.json is therefore a FROZEN snapshot of the replay as computed on
2026-10-25 with the Vacant evidence code of that day. The numbers below are
reproducible from this file + this script only.
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_SRC = HERE / "c37_final.json"
SUITES = ("dabench", "dabstep", "databench", "polyglot_py")


def load_rows(src: str | pathlib.Path | None = None) -> list[dict]:
    p = pathlib.Path(src) if src is not None else DEFAULT_SRC
    return [r for r in json.loads(p.read_text(encoding="utf-8")) if "error" not in r]


def group_cells(rows: list[dict]) -> dict[tuple[str, str, str], list[dict]]:
    """Group by (suite, batch prefix, task_dir); keep groups with >= 2 runs; sort by cell name."""
    groups: dict[tuple[str, str, str], list[dict]] = collections.defaultdict(list)
    for r in rows:
        batch = r["cell"].split("-")[0]
        suite = r["task_dir"].rstrip("/").split("/")[-2]
        groups[(suite, batch, r["task_dir"])].append(r)
    out = {}
    for key, cells in groups.items():
        if len(cells) < 2:
            continue
        cells.sort(key=lambda c: c["cell"])
        out[key] = cells
    return out


def simulate(cells: list[dict], stop_ok, cap: int) -> tuple[float, float]:
    """Average over every starting offset: returns (expected pass, expected #runs)."""
    tp = tc = 0.0
    n = len(cells)
    for i in range(n):
        seq = [cells[(i + j) % n] for j in range(min(cap, n))]
        for j, c in enumerate(seq):
            if stop_ok(c) or j == len(seq) - 1:
                tp += c["pass"]
                tc += j + 1
                break
    return tp / n, tc / n


def columns(rows: list[dict], cap: int = 3) -> dict[str, dict]:
    """Recompute the cited table. One entry per suite + 'ALL'.

    Per entry: units (groups), n (cells in those groups), pass1, flag, flag_runs,
    test, test_runs, oracle — all rates in [0,1].
    """
    agg: dict[str, list[float]] = collections.defaultdict(lambda: [0.0] * 7)
    for (suite, _batch, _t), cells in group_cells(rows).items():
        p1 = sum(c["pass"] for c in cells) / len(cells)
        fp, fc = simulate(cells, lambda c: not c.get("findings_final"), cap)
        tp, tc = simulate(cells, lambda c: c["pass"], cap)
        for key in (suite, "ALL"):
            a = agg[key]
            a[0] += 1; a[1] += p1; a[2] += fp; a[3] += fc; a[4] += tp; a[5] += tc
            a[6] += any(c["pass"] for c in cells)
    out = {}
    for k in sorted(agg, key=lambda s: (s != "ALL", s)):
        n, p1, fp, fc, tp, tc, orc = agg[k]
        out[k] = {"units": int(n), "n": None, "pass1": p1 / n, "flag": fp / n,
                  "flag_runs": fc / n, "test": tp / n, "test_runs": tc / n,
                  "oracle": orc / n}
    return out


def _fill_n(out: dict[str, dict], rows: list[dict]) -> None:
    for (suite, _b, _t), cells in group_cells(rows).items():
        out[suite]["n"] = (out[suite]["n"] or 0) + len(cells)
        out["ALL"]["n"] = (out["ALL"]["n"] or 0) + len(cells)


def signal_stats(rows: list[dict]) -> dict[str, dict]:
    """Precision/recall of the REAL SIGNAL (findings) against the archived scorer.

    Per suite + 'ALL' (only groups with >= 2 runs, the same population as columns()):
      pass_cells    : scorer-pass cells
      fail_cells    : scorer-fail cells
      fp            : pass cells with non-empty findings  (signal fires, nothing wrong)
      fail_flagged  : fail cells with non-empty findings  (signal fires, something wrong)
      recall        : fail_flagged / fail_cells
      rescue_ub     : flagged fail cells whose group contains ANY passing cell
                      (upper bound on what a re-run could have fixed; the policy
                      number in columns() is the offset-constrained version)
    """
    agg: dict[str, dict] = collections.defaultdict(
        lambda: {"pass_cells": 0, "fail_cells": 0, "fp": 0,
                 "fail_flagged": 0, "rescue_ub": 0})
    for (suite, _b, _t), cells in group_cells(rows).items():
        for key in (suite, "ALL"):
            a = agg[key]
            for c in cells:
                flagged = bool(c.get("findings_final"))
                if c["pass"]:
                    a["pass_cells"] += 1
                    if flagged:
                        a["fp"] += 1
                else:
                    a["fail_cells"] += 1
                    if flagged:
                        a["fail_flagged"] += 1
                        if any(o["pass"] for o in cells if o is not c):
                            a["rescue_ub"] += 1
    out = {}
    for k in sorted(agg, key=lambda s: (s != "ALL", s)):
        a = agg[k]
        a = dict(a)
        a["recall"] = (a["fail_flagged"] / a["fail_cells"]) if a["fail_cells"] else None
        out[k] = a
    return out


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    cap = int(args[0]) if args else 3
    rows = load_rows()
    col = columns(rows, cap)
    _fill_n(col, rows)
    sig = signal_stats(rows)

    if "--json" in flags:
        print(json.dumps({"cap": cap, "n_rows": len(rows), "columns": col,
                          "signal_stats": sig}, indent=2, ensure_ascii=False))
        return

    print(f"cap={cap}  (units = (suite, batch, task) groups with >=2 independent runs; "
          f"n rows = {len(rows)})")
    print(f"{'suite':<12}{'units':>6}{'n':>6}{'pass@1':>9}{'flag-restart':>14}"
          f"{'runs':>6}{'test-restart':>14}{'runs':>6}{'oracle@k':>10}")
    for k, v in col.items():
        print(f"{k:<12}{v['units']:>6}{v['n']:>6}{100*v['pass1']:>8.1f}%"
              f"{100*v['flag']:>13.1f}%{v['flag_runs']:>6.2f}"
              f"{100*v['test']:>13.1f}%{v['test_runs']:>6.2f}{100*v['oracle']:>9.1f}%")

    if "--signal-stats" in flags:
        print()
        print("REAL SIGNAL quality (findings vs archived scorer; FP = pass cell that is flagged):")
        print(f"{'suite':<12}{'pass':>6}{'fail':>6}{'FP':>5}{'flagged':>8}"
              f"{'recall':>9}{'rescue_ub':>10}{'rescue%':>9}")
        for k, a in sig.items():
            rec = f"{100*a['recall']:.1f}%" if a["recall"] is not None else "  n/a"
            rct = (100 * a["rescue_ub"] / a["fail_flagged"]
                   if a["fail_flagged"] else float("nan"))
            rcs = f"{rct:.1f}%" if a["fail_flagged"] else "  n/a"
            print(f"{k:<12}{a['pass_cells']:>6}{a['fail_cells']:>6}{a['fp']:>5}"
                  f"{a['fail_flagged']:>8}{rec:>9}{a['rescue_ub']:>10}{rcs:>9}")


if __name__ == "__main__":
    main()
