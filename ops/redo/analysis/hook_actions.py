#!/usr/bin/env python3
"""rfh4 H 臂的操作檢查（2026-11-25，冒煙前用假端點看過檔案格式後寫的）：掛鉤有沒有載入、檢查有沒有跑、退回幾次、哪幾類。

每一格 H 的每一次嘗試讀 `attempt_*/logs/vacant-home/trace/projects/*/chain.ndjson`（掛鉤的簽章病歷）：
- 事件數（全部、`step`）、`review` 事件（agent 說做完時的那一次檢查；payload.mode 應為 evidence）；
- 退回＝review 的 payload.action 不是 "allow"；類別取每個 finding 的 kind／category／check／type 第一個有的欄位；
- 沒有任何病歷＝掛鉤沒載入（那一格照計，這裡列出）。
只讀。用法：python3 ops/redo/analysis/hook_actions.py --root <run root> [--arm H]
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys


def _cat(f: dict) -> str:
    for k in ("kind", "category", "check", "type"):
        if isinstance(f, dict) and f.get(k):
            return str(f[k])
    return "?"


def scan(root: pathlib.Path, arm: str = "H") -> dict:
    cells = attempts = no_trace = reviews = non_evidence = blocks = steps = events = 0
    cats: collections.Counter = collections.Counter()
    actions: collections.Counter = collections.Counter()
    cells_with_block = 0
    missing: list[str] = []
    for cj in sorted(root.glob(f"cells/*/r*/{arm}/cell.json")):
        cells += 1
        blocked_here = False
        for ad in sorted(cj.parent.glob("attempt_*")):
            attempts += 1
            chains = list((ad / "logs" / "vacant-home" / "trace" / "projects").glob("*/chain.ndjson"))
            if not chains:
                no_trace += 1
                missing.append(str(ad.relative_to(root)))
                continue
            for ch in chains:
                for line in ch.read_text(errors="replace").splitlines():
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    events += 1
                    if e.get("type") == "step":
                        steps += 1
                    if e.get("type") != "review":
                        continue
                    reviews += 1
                    p = e.get("payload") or {}
                    if p.get("mode") != "evidence":
                        non_evidence += 1
                    act = str(p.get("action"))
                    actions[act] += 1
                    if act != "allow":
                        blocks += 1
                        blocked_here = True
                        for f in p.get("findings") or []:
                            cats[_cat(f)] += 1
        cells_with_block += blocked_here
    return {"arm": arm, "cells": cells, "attempts": attempts, "attempts_without_trace": no_trace,
            "missing_trace": missing[:50], "events": events, "steps": steps, "reviews": reviews,
            "reviews_not_evidence_mode": non_evidence, "review_actions": dict(actions), "blocks": blocks,
            "cells_with_block": cells_with_block, "block_finding_categories": dict(cats)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--arm", default="H")
    a = ap.parse_args(argv)
    print(json.dumps(scan(pathlib.Path(a.root).expanduser(), a.arm), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
