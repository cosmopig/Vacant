#!/usr/bin/env python3
"""單票層級：在候選**已經通過可見測資**的前提下，一位評審投 FAIL
   到底能不能預測它會在隱藏測資上掛掉？（＝評審在免費閘之外還剩多少資訊）

條件在 visible_ok 上，是因為決策上只有這些列還需要人判斷；
沒過可見測資的列免費閘已經擋掉了。零模型呼叫。
"""
from __future__ import annotations
import json, sys, collections
from math import comb
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]


def fisher(a, b, c, d):
    n = a + b + c + d
    if n == 0 or (a + b) == 0 or (c + d) == 0:
        return float("nan")
    def p(x):
        return comb(a + b, x) * comb(c + d, a + c - x) / comb(n, a + c)
    lo, hi, p0 = max(0, a + c - (c + d)), min(a + b, a + c), p(a)
    return min(1.0, sum(p(x) for x in range(lo, hi + 1) if p(x) <= p0 * (1 + 1e-9)))


def main(runs):
    print(f"{'run':30s} {'reviewer model':24s} {'votes':>6s} {'FAILs':>6s} {'FAILrate':>9s} "
          f"{'P(bad|FAIL)':>12s} {'P(bad|PASS)':>12s} {'fisher':>8s}")
    for run in runs:
        fam = {a["agent_id"]: a["model"] for a in json.loads((ROOT / "runs" / run / "summary.json").read_text())["pool"]}
        on = [json.loads(l) for l in (ROOT / "runs" / run / "rows.jsonl").read_text().splitlines()
              if l.strip() and json.loads(l)["arm"] == "ON"]
        tab = collections.Counter()
        for r in on:
            if not r.get("visible_ok"):
                continue
            for e in (r.get("review_evidence") or []):
                tab[(fam.get(e["agent_id"], "?"), not e["raw_pass"], r["meets_demand"])] += 1
        for m in sorted({k[0] for k in tab}):
            a, b = tab[(m, True, False)], tab[(m, True, True)]
            c, d = tab[(m, False, False)], tab[(m, False, True)]
            n = a + b + c + d
            print(f"{run[:30]:30s} {m:24s} {n:6d} {a+b:6d} {(a+b)/n:9.3f} "
                  f"{(a/(a+b)) if a+b else float('nan'):12.3f} {c/(c+d) if c+d else float('nan'):12.3f} "
                  f"{fisher(a,b,c,d):8.4f}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["g_r441_gemma_only_mbpp_b", "g_r356_3arm_20260830", "g_onoff5_371_r123_20260825"])
