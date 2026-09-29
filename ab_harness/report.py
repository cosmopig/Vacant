#!/usr/bin/env python3
"""report.py — aggregate the paired A/B batch. Denominators are not optional.

Every rate printed here carries its denominator, and refusals stay in the
denominator. A rate that quietly drops refused cells is not comparable to
anything and is not printed.

Primary metric   correct = delivered AND hidden_pass, denominator = tasks graded
                 in BOTH arms (paired complete cases only, reported as such).
Secondary        hidden_pass ignoring delivery ("what would have shipped")
                 accepted (vacant arm only): how often the gate said yes.
                 The gap between accepted and correct is the false-delivery
                 count: files the gate passed that the hidden checks rejected.
Paired test      exact McNemar on the discordant pairs, two-sided.
                 With 20 tasks the smallest reachable p is bounded; if the
                 discordant count is too small this prints "not enough discordant
                 pairs", not a number that invites reading.
"""
from __future__ import annotations

import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar. b = A right/B wrong, c = B right/A wrong."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) * (0.5 ** n)
    return min(1.0, 2.0 * tail)


def load(root: pathlib.Path) -> dict:
    g = {}
    for p in sorted(root.iterdir()):
        f = p / "grade.json"
        if p.is_dir() and f.is_file():
            g[p.name] = json.loads(f.read_text())
    return g


def main() -> int:
    ap_root = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else RUNS
    g = load(ap_root)
    if not g:
        print("no graded cells yet")
        return 1
    by_task: dict[str, dict] = {}
    for cell, r in g.items():
        by_task.setdefault(r["task"], {})[r["arm"]] = r

    paired = {t: v for t, v in by_task.items() if "A" in v and "B" in v}
    unpaired = {t: v for t, v in by_task.items() if t not in paired}

    A = [v["A"] for v in paired.values()]
    B = [v["B"] for v in paired.values()]
    n = len(paired)

    a_ok = sum(1 for r in A if r["correct"])
    b_ok = sum(1 for r in B if r["correct"])
    a_hp = sum(1 for r in A if r["hidden_pass"])
    b_hp = sum(1 for r in B if r["hidden_pass"])
    b_del = sum(1 for r in B if r["delivered"])
    b_ref = sum(1 for r in B if not r["delivered"])
    b_acc_false = sum(1 for r in B if r["delivered"] and not r["hidden_pass"])
    a_acc_false = sum(1 for r in A if r["delivered"] and not r["hidden_pass"])

    b_only = sum(1 for v in paired.values()
                 if v["B"]["correct"] and not v["A"]["correct"])
    a_only = sum(1 for v in paired.values()
                 if v["A"]["correct"] and not v["B"]["correct"])

    p = mcnemar_exact(a_only, b_only)

    def pct(k, d):
        return f"{k}/{d} ({100.0*k/d:.1f}%)" if d else "n/a"

    print("=" * 78)
    print("PAIRED A/B — vacant gate vs plain agent, identical prompt + workspace")
    print("=" * 78)
    print(f"paired complete cases (both arms graded) : n = {n}")
    print(f"cells present but not pairable           : {len(unpaired)}"
          + (f"  {sorted(unpaired)}" if unpaired else ""))
    print(f"model                                    : "
          f"{ {r.get('model') for r in []} or ''}", end="")
    print()
    print()
    print("PRIMARY  correct = delivered AND hidden_pass")
    print(f"  A  plain   {pct(a_ok, n)}")
    print(f"  B  vacant  {pct(b_ok, n)}")
    print(f"  delta B-A  {100.0*(b_ok-a_ok)/n:+.1f} pp" if n else "")
    print()
    print("SECONDARY  hidden_pass ignoring delivery (what would have shipped)")
    print(f"  A  plain   {pct(a_hp, n)}")
    print(f"  B  vacant  {pct(b_hp, n)}")
    print()
    print("GATE BEHAVIOUR (arm B)")
    print(f"  delivered / accepted by gate   {pct(b_del, n)}")
    print(f"  refused (counted as failure)   {pct(b_ref, n)}")
    print(f"  FALSE DELIVERY: gate said yes,")
    print(f"    hidden said no               {b_acc_false}/{n} ({100.0*b_acc_false/n:.1f}%)" if n else "")
    print(f"  (arm A, ungated, same quantity) {a_acc_false}/{n} ({100.0*a_acc_false/n:.1f}%)" if n else "")
    print()
    print("PAIRED TEST  exact McNemar, two-sided")
    print(f"  discordant: B-only-correct = {b_only}, A-only-correct = {a_only}")
    if b_only + a_only == 0:
        print("  p = not computable (zero discordant pairs) — "
              "this run cannot distinguish the arms")
    elif b_only + a_only < 6:
        print(f"  p = {p:.4f}  ⚠ only {b_only+a_only} discordant pairs; "
              "treat as unresolved, not as a result")
    else:
        print(f"  p = {p:.4f}")
    print()
    print("PER-TASK")
    print(f"  {'task':<10} {'A pass':>7} {'B pass':>7} {'B deliv':>8} "
          f"{'A corr':>7} {'B corr':>7}  B refusal")
    for t in sorted(paired):
        a, b = paired[t]["A"], paired[t]["B"]
        print(f"  {t:<10} {str(a['hidden_pass']):>7} {str(b['hidden_pass']):>7} "
              f"{str(b['delivered']):>8} {str(a['correct']):>7} "
              f"{str(b['correct']):>7}  {b.get('refusal_reason') or ''}")

    out = {
        "n_paired": n, "unpaired_tasks": sorted(unpaired),
        "A_correct": a_ok, "B_correct": b_ok,
        "A_hidden_pass": a_hp, "B_hidden_pass": b_hp,
        "B_delivered": b_del, "B_refused": b_ref,
        "B_false_delivery": b_acc_false, "A_false_delivery": a_acc_false,
        "B_only_correct": b_only, "A_only_correct": a_only,
        "mcnemar_exact_two_sided_p": p,
        "discordant_total": b_only + a_only,
        "per_task": {t: paired[t] for t in sorted(paired)},
    }
    (ap_root / "report.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"\nmachine-readable: {ap_root / 'report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
