#!/usr/bin/env python3
"""Recompute summary metrics from rows.jsonl (no model)."""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    lo = (centre - margin) / denom
    hi = (centre + margin) / denom
    return (lo, hi)


def load_rows(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def summarize(rows: list[dict]) -> dict:
    by_arm: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_arm[r["arm"]].append(r)

    arms_out = {}
    for arm, rs in sorted(by_arm.items()):
        n = len(rs)
        succ = sum(1 for r in rs if r["whole_success_final"])
        succ_draft = sum(1 for r in rs if r["whole_success_draft"])
        wrong_to_right = sum(
            1 for r in rs if (not r["whole_success_draft"]) and r["whole_success_final"]
        )
        right_to_wrong = sum(
            1 for r in rs if r["whole_success_draft"] and (not r["whole_success_final"])
        )
        pt = sum(r.get("prompt_tokens", 0) for r in rs)
        ct = sum(r.get("completion_tokens", 0) for r in rs)
        lat = sum(r.get("latency_s", 0.0) for r in rs)
        lo, hi = wilson_ci(succ, n)
        arms_out[arm] = {
            "n_tasks": n,
            "whole_success_final": succ,
            "whole_success_rate": succ / n if n else 0.0,
            "ci95_whole_success": [lo, hi],
            "whole_success_draft_rate": succ_draft / n if n else 0.0,
            "net_gain_pp": 100.0 * (wrong_to_right - right_to_wrong) / n if n else 0.0,
            "wrong_to_right": wrong_to_right,
            "right_to_wrong": right_to_wrong,
            "prompt_tokens_total": pt,
            "completion_tokens_total": ct,
            "mean_latency_s": lat / n if n else 0.0,
        }

    return {"arms": arms_out, "n_rows": len(rows)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    rows = load_rows(args.rows)
    summary = summarize(rows)
    args.out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()