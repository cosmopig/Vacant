#!/usr/bin/env python3
"""全庫掃描：ON 的接受決策跟「免費可見測資閘」有沒有差過？差在哪？

gain_run.py:611 是 `accepted = visible_ok and (audit_ok is not False)`
——`passed_review` 根本不在裡面。這支把那件事在全部 runs/ 的 ON 列上驗一遍，
並確認「可見測資失敗但隱藏測資通過」（＝免費閘會誤殺好答案）一次也沒發生。

零模型呼叫。用法：ops/gain/replay/gate_identity_scan.py
"""
from __future__ import annotations
import json, collections
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]

tot = diff = viol = 0
by = collections.Counter()
runs = 0
fr_tot = fr_bad = 0
for p in sorted((ROOT / "runs").glob("*/rows.jsonl")):
    rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    on = [r for r in rows if r.get("arm") == "ON" and "accepted" in r and "visible_ok" in r]
    if on:
        runs += 1
    for r in on:
        tot += 1
        if bool(r["accepted"]) != (bool(r["visible_ok"]) and (r.get("audit_ok") is not False)):
            viol += 1
        if bool(r["accepted"]) != bool(r["visible_ok"]):
            diff += 1
            by[(r.get("audited"), r.get("audit_ok"), bool(r.get("passed_review")))] += 1
    for r in rows:
        if r.get("visible_ok") is None or r.get("meets_demand") is None:
            continue
        fr_tot += 1
        fr_bad += int((not r["visible_ok"]) and r["meets_demand"])
print(f"runs with ON rows: {runs}   ON rows scanned: {tot}")
print(f"ON accept-decision != free 0-call visible gate: {diff} rows ({100*diff/tot:.1f}%)")
print(f"  breakdown (audited, audit_ok, passed_review): {dict(by)}")
print(f"rows violating accepted == visible_ok and (audit_ok is not False): {viol}")
print(f"rows across ALL arms with visible FAIL but hidden PASS (free gate false refusal): "
      f"{fr_bad} / {fr_tot}")
