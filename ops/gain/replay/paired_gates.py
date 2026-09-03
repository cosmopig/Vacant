#!/usr/bin/env python3
"""配對比較：同一批 task_id 上，四種「機制 x 閘門」組合的交付表。

零模型呼叫、零沙箱執行（只讀 rows.jsonl 已落盤欄位）。
每一格的模型呼叫預算都標出來，等預算比較才成立。
"""
from __future__ import annotations
import json, sys, math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def load(run):
    return [json.loads(l) for l in (ROOT / "runs" / run / "rows.jsonl").read_text().splitlines() if l.strip()]


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n))


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def main(run):
    rows = load(run)
    by = {}
    for r in rows:
        by.setdefault(r["arm"], {})[r["task_id"]] = r
    arms = [a for a in ("OFF", "ON", "OFF5") if a in by]
    common = set.intersection(*[set(by[a]) for a in arms])
    print(f"=== {run} === arms={arms} paired n={len(common)}")

    # (label, arm, ship-predicate, model-call budget)
    CFG = [
        ("OFF   as run      (no gate)", "OFF", lambda r: True, 1),
        ("OFF   + visible gate       ", "OFF", lambda r: bool(r.get("visible_ok")), 1),
        ("OFF5  as run      (no gate)", "OFF5", lambda r: True, 5),
        ("OFF5  + visible gate       ", "OFF5", lambda r: bool(r.get("visible_ok")), 5),
        ("ON    minus oracle audit   ", "ON", lambda r: bool(r.get("visible_ok")), 5),
        ("ON    as run (visible+audit)", "ON", lambda r: bool(r.get("accepted")), 5),
    ]
    cells = {}
    print(f"{'config':30s} {'calls':>5s} {'ship':>5s} {'good':>5s} {'leak':>5s} {'lost':>5s} "
          f"{'cov':>6s} {'selacc':>7s} {'good/n':>7s}")
    for label, arm, pred, budget in CFG:
        if arm not in by:
            continue
        rs = [by[arm][t] for t in sorted(common)]
        ship = [r for r in rs if pred(r)]
        good = sum(1 for r in ship if r["meets_demand"])
        leak = len(ship) - good
        lost = sum(1 for r in rs if not pred(r) and r["meets_demand"])
        n = len(rs)
        cells[label] = {t: (pred(by[arm][t]), by[arm][t]["meets_demand"]) for t in common}
        print(f"{label:30s} {budget:5d} {len(ship):5d} {good:5d} {leak:5d} {lost:5d} "
              f"{len(ship)/n:6.3f} {good/len(ship) if ship else float('nan'):7.4f} {good/n:7.4f}")

    def paired(a, b, what):
        A, B = cells[a], cells[b]
        if what == "leak":
            fa = {t: (A[t][0] and not A[t][1]) for t in common}
            fb = {t: (B[t][0] and not B[t][1]) for t in common}
        else:  # delivered good
            fa = {t: (A[t][0] and A[t][1]) for t in common}
            fb = {t: (B[t][0] and B[t][1]) for t in common}
        bb = sum(1 for t in common if fa[t] and not fb[t])
        cc = sum(1 for t in common if fb[t] and not fa[t])
        print(f"  [{what}] {a.strip()} vs {b.strip()}: b={bb} c={cc} p={mcnemar_exact(bb,cc):.4f}")

    print("\npaired McNemar (b = first-only, c = second-only):")
    for what in ("leak", "good"):
        paired("ON    as run (visible+audit)", "OFF5  + visible gate       ", what)
        paired("ON    minus oracle audit   ", "OFF5  + visible gate       ", what)
        paired("OFF5  + visible gate       ", "OFF   + visible gate       ", what)
        paired("ON    minus oracle audit   ", "OFF   + visible gate       ", what)
        print()


if __name__ == "__main__":
    for r in (sys.argv[1:] or ["g_r441_gemma_only_mbpp_b", "g_r356_3arm_20260830"]):
        main(r); print()
