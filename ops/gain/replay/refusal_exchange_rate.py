#!/usr/bin/env python3
"""每多擋下一個壞答案，要賠掉幾個好答案？（拒絕閘的匯率）

拒絕本身不是免費的：拒絕一個本來會對的答案＝把好東西丟掉。
所以「漏出變少」不能單獨當成成效，必須跟「丟掉的好答案」一起看。

基準線固定為**免費的可見測資閘**（0 次模型呼叫）。所有更嚴的閘門都跟它比：
    exchange = Δ(丟掉的好答案) / Δ(擋下的壞答案)
exchange < 1 代表這道閘門在把價值變高（假設漏出與空手而歸等價）；
exchange > λ 代表只有當「漏出比空手而歸嚴重 λ 倍」時才划算。

零模型呼叫、只讀 rows.jsonl。
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def rows(run, arm):
    return [json.loads(l) for l in (ROOT / "runs" / run / "rows.jsonl").read_text().splitlines()
            if l.strip() and json.loads(l)["arm"] == arm]


def ce(r):
    return sum(1 for e in (r.get("review_evidence") or []) if e.get("counterexample_confirmed"))


def tally(rs, pred):
    ship = [r for r in rs if pred(r)]
    good = sum(1 for r in ship if r["meets_demand"])
    return len(ship), good, len(ship) - good


def report(title, rs, base_pred, gates):
    n = len(rs)
    s0, g0, l0 = tally(rs, base_pred)
    print(f"\n{title}  n={n}")
    print(f"  BASELINE free visible gate (0 model calls): ship={s0} good={g0} leak={l0}")
    print(f"  {'gate':40s} {'calls':>5s} {'ship':>5s} {'good':>5s} {'leak':>5s} "
          f"{'-leak':>6s} {'-good':>6s} {'exchange':>9s}")
    for name, pred, calls in gates:
        s, g, lk = tally(rs, pred)
        dl, dg = l0 - lk, g0 - g
        ex = (dg / dl) if dl > 0 else float("inf") if dg > 0 else float("nan")
        print(f"  {name:40s} {calls:5d} {s:5d} {g:5d} {lk:5d} {dl:6d} {dg:6d} {ex:9.2f}")


def main(runs):
    for run in runs:
        on = rows(run, "ON")
        if on and "passed_review" in on[0]:
            report(f"[{run}] ON arm — every gate applied to the SAME shipped code", on,
                   lambda r: bool(r.get("visible_ok")),
                   [("+ peer-review PASS required", lambda r: r.get("visible_ok") and r.get("passed_review"), 3),
                    ("+ no machine-confirmed counterexample", lambda r: r.get("visible_ok") and ce(r) == 0, 3),
                    ("+ ALL 3 reviewers PASS", lambda r: r.get("visible_ok") and all(v for _, v in (r.get("votes") or [])), 3),
                    ("+ 20% hidden-test audit [ORACLE]", lambda r: bool(r.get("accepted")), 0)])
        o5 = rows(run, "OFF5")
        if o5 and o5[0].get("vote_agreement") is not None:
            report(f"[{run}] OFF5 arm", o5, lambda r: bool(r.get("visible_ok")),
                   [("+ 5/5 behavioral consensus", lambda r: r.get("visible_ok") and r["vote_agreement"] == 5, 0),
                    ("+ >=4/5 consensus", lambda r: r.get("visible_ok") and r["vote_agreement"] >= 4, 0),
                    ("+ >=3/5 consensus", lambda r: r.get("visible_ok") and r["vote_agreement"] >= 3, 0)])


if __name__ == "__main__":
    main(sys.argv[1:] or ["g_r441_gemma_only_mbpp_b", "g_r356_3arm_20260830", "g_onoff5_371_r123_20260825"])
