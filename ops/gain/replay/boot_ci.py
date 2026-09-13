#!/usr/bin/env python3
"""配對 bootstrap 信賴區間（題目層級重抽），只讀 rows.jsonl，零模型呼叫。"""
from __future__ import annotations
import json, random, sys
import numpy as np
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]

def rows(run):
    out = {}
    for l in (ROOT / "runs" / run / "rows.jsonl").read_text().splitlines():
        if not l.strip(): continue
        r = json.loads(l); out.setdefault(r["arm"], {})[r["task_id"]] = r
    return out

CFG = {
    "OFF+gate(1call)":  ("OFF",  lambda r: bool(r.get("visible_ok"))),
    "OFF5 nogate(5)":   ("OFF5", lambda r: True),
    "OFF5+gate(5call)": ("OFF5", lambda r: bool(r.get("visible_ok"))),
    "ON-minus-oracle":  ("ON",   lambda r: bool(r.get("visible_ok"))),
    "ON as-run":        ("ON",   lambda r: bool(r.get("accepted"))),
}

def boot(run, a, b, metric, B=20000, seed=17):
    by = rows(run)
    common = sorted(set(by["ON"]) & set(by["OFF5"]) & set(by.get("OFF", by["OFF5"])))
    aa, pa = CFG[a]; bb, pb = CFG[b]
    def val(arm, pred, t):
        r = by[arm][t]
        s = pred(r)
        if metric == "leak":  return 1.0 if (s and not r["meets_demand"]) else 0.0
        if metric == "good":  return 1.0 if (s and r["meets_demand"]) else 0.0
        if metric == "ship":  return 1.0 if s else 0.0
    d = np.array([val(aa, pa, t) - val(bb, pb, t) for t in common], dtype=float)
    n = len(d); point = float(d.mean())
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(B, n))
    ds = d[idx].mean(axis=1)
    lo, hi = np.percentile(ds, [2.5, 97.5])
    return point, float(lo), float(hi), n

if __name__ == "__main__":
    for run in (sys.argv[1:] or ["g_r441_gemma_only_mbpp_b", "g_r356_3arm_20260830"]):
        print(f"=== {run} (paired, task-level bootstrap B=20000) ===")
        for metric in ("leak", "good", "ship"):
            for a, b in [("ON as-run", "OFF5+gate(5call)"),
                         ("ON-minus-oracle", "OFF5+gate(5call)"),
                         ("ON-minus-oracle", "OFF+gate(1call)"),
                         ("OFF5+gate(5call)", "OFF5 nogate(5)")]:
                p, lo, hi, n = boot(run, a, b, metric)
                print(f"  {metric:5s} {a:17s} - {b:17s} = {100*p:+7.2f}pp  95%CI [{100*lo:+6.2f},{100*hi:+6.2f}]  n={n}")
            print()
