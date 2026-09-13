#!/usr/bin/env python3
"""風險–覆蓋率表：同一批配對題目上，每種「機制 x 拒絕閘」的
   覆蓋率（有交件的比例）、選擇性正確率、漏出數、以及被丟掉的好答案數。

零模型呼叫，只讀 rows.jsonl。用法：ops/gain/replay/risk_coverage.py [run ...]
"""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]


def ce(r):
    return sum(1 for e in (r.get("review_evidence") or []) if e.get("counterexample_confirmed"))


def nf(r):
    return sum(1 for e in (r.get("review_evidence") or []) if not e["raw_pass"])


CFG = [
    ("OFF   ship-all",                                   "OFF",  lambda r: True, 1),
    ("OFF   + visible gate",                             "OFF",  lambda r: r["visible_ok"], 1),
    ("OFF5  ship-all (as run)",                          "OFF5", lambda r: True, 5),
    ("OFF5  + visible gate",                             "OFF5", lambda r: r["visible_ok"], 5),
    ("OFF5  + visible + agree>=4",                       "OFF5", lambda r: r["visible_ok"] and r.get("vote_agreement", 0) >= 4, 5),
    ("OFF5  + visible + agree==5",                       "OFF5", lambda r: r["visible_ok"] and r.get("vote_agreement", 0) == 5, 5),
    ("ON    ship-all",                                   "ON",   lambda r: True, 5),
    ("ON    + visible gate (= ON minus oracle)",         "ON",   lambda r: r["visible_ok"], 5),
    ("ON    + visible + peer-review majority",           "ON",   lambda r: r["visible_ok"] and r["passed_review"], 5),
    ("ON    + visible + no confirmed counterexample",    "ON",   lambda r: r["visible_ok"] and ce(r) == 0, 5),
    ("ON    + visible + zero raw FAIL vote",             "ON",   lambda r: r["visible_ok"] and nf(r) == 0, 5),
    ("ON    AS RUN (visible + 20% hidden audit) ORACLE", "ON",   lambda r: r["accepted"], 5),
]


def main(runs):
    for run in runs:
        by = {}
        for l in (ROOT / "runs" / run / "rows.jsonl").read_text().splitlines():
            if not l.strip():
                continue
            r = json.loads(l)
            by.setdefault(r["arm"], {})[r["task_id"]] = r
        arms = [a for a in ("OFF", "ON", "OFF5") if a in by]
        common = sorted(set.intersection(*[set(by[a]) for a in arms]))
        n = len(common)
        print(f"=== {run} === arms={arms} paired n={n}")
        print(f"{'config':52s} {'calls':>5s} {'ship':>5s} {'cov':>6s} {'selacc':>7s} {'leak':>5s} {'lost':>5s} {'good/n':>7s}")
        for lab, arm, pred, bud in CFG:
            if arm not in by:
                continue
            rs = [by[arm][t] for t in common]
            if rs[0].get("visible_ok") is None:
                continue
            sh = [r for r in rs if pred(r)]
            g = sum(1 for r in sh if r["meets_demand"])
            lost = sum(1 for r in rs if not pred(r) and r["meets_demand"])
            print(f"{lab:52s} {bud:5d} {len(sh):5d} {len(sh)/n:6.3f} "
                  f"{g/len(sh) if sh else float('nan'):7.4f} {len(sh)-g:5d} {lost:5d} {g/n:7.4f}")
        print()


if __name__ == "__main__":
    main(sys.argv[1:] or ["g_r441_gemma_only_mbpp_b", "g_r356_3arm_20260830"])
