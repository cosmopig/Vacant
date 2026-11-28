#!/usr/bin/env python3
"""Summaries, McNemar, 2x2, gating utility."""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from vacant_network.research import mcnemar_exact


def load_rows(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return ((c - m) / d, (c + m) / d)


def summarize_primary(rows: list[dict], answerable_only: bool = True) -> dict:
    if answerable_only:
        rows = [r for r in rows if r.get("answerable", True)]
    by_arm: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_arm[r["arm"]].append(r)
    out = {}
    for arm, rs in sorted(by_arm.items()):
        n = len(rs)
        succ = sum(1 for r in rs if r["oracle_whole_success"])
        vis = sum(1 for r in rs if r["visible_all_pass"])
        cross = defaultdict(int)
        for r in rs:
            cross[r["visible_x_oracle"]] += 1
        lo, hi = wilson(succ, n)
        out[arm] = {
            "n": n,
            "oracle_success": succ,
            "oracle_rate": succ / n if n else 0,
            "ci95": [lo, hi],
            "visible_pass_rate": vis / n if n else 0,
            "confusion_visible_x_oracle": dict(cross),
            "mean_cpu_s": sum(r["cpu_seconds"] for r in rs) / n if n else 0,
            "mean_tokens": sum(r["prompt_tokens"] + r["completion_tokens"] for r in rs) / n if n else 0,
        }
    return out


def mcnemar_pair(rows: list[dict], arm_a: str, arm_b: str) -> dict:
    by_task: dict[str, dict[str, bool]] = defaultdict(dict)
    for r in rows:
        if not r.get("answerable", True):
            continue
        by_task[r["task_id"]][r["arm"]] = bool(r["oracle_whole_success"])
    b = c = 0
    for tid, arms in by_task.items():
        if arm_a not in arms or arm_b not in arms:
            continue
        a_ok, b_ok = arms[arm_a], arms[arm_b]
        if not a_ok and b_ok:
            b += 1
        if a_ok and not b_ok:
            c += 1
    return {"arm_a": arm_a, "arm_b": arm_b, "b_a_fail_b_ok": b, "c_a_ok_b_fail": c, "mcnemar_p": mcnemar_exact(b, c)}


def gating_summary(rows: list[dict]) -> dict:
    by_arm: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_arm[r["arm"]].append(r)
    out = {}
    for arm, rs in sorted(by_arm.items()):
        shipped = [r for r in rs if r["shipped"]]
        sfr = sum(1 for r in shipped if r["wrong_ship"]) / len(shipped) if shipped else float("nan")
        cov = len(shipped) / len(rs) if rs else 0
        for lam in (1, 2, 5):
            util = sum(
                (1 if r["correct_ship"] else 0) - lam * (1 if r["wrong_ship"] else 0) for r in rs
            ) / len(rs) if rs else 0
            out.setdefault(arm, {})[f"U_lambda_{lam}"] = util
        out[arm].update(
            {
                "n": len(rs),
                "coverage": cov,
                "silent_failure_rate": sfr,
                "mean_cpu_s": sum(r["cpu_seconds"] for r in rs) / len(rs),
            }
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--baseline", default="MAJ3")
    ap.add_argument("--primary-arm", default="VACANT")
    ap.add_argument("--gating", action="store_true")
    args = ap.parse_args()
    rows = load_rows(args.rows)
    if args.gating:
        summary = {"gating": gating_summary(rows)}
    else:
        summary = {
            "primary": summarize_primary(rows),
            "mcnemar": mcnemar_pair(rows, args.primary_arm, args.baseline),
        }
    args.out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()