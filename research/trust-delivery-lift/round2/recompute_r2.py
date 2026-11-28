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


def _cost_means(rows: list[dict]) -> dict:
    by: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by[r["arm"]].append(r)
    return {
        arm: {
            "mean_cpu_s": sum(x["cpu_seconds"] for x in rs) / len(rs),
            "mean_tokens": sum(x["prompt_tokens"] + x["completion_tokens"] for x in rs) / len(rs),
            "mean_calls": sum(x["n_calls"] for x in rs) / len(rs),
        }
        for arm, rs in sorted(by.items())
    }


def selective_2x2(rows: list[dict]) -> dict:
    """Released/held × correct/wrong. Invoice primary arms always ship → held cells 0."""
    out = {}
    for arm in sorted({r["arm"] for r in rows}):
        rs = [r for r in rows if r["arm"] == arm]
        rc = sum(1 for r in rs if r.get("oracle_whole_success"))
        rw = sum(1 for r in rs if not r.get("oracle_whole_success"))
        out[arm] = {
            "released_correct": rc,
            "released_wrong": rw,
            "held_correct": 0,
            "held_wrong": 0,
            "escalate_rate": 0.0,
            "n": len(rs),
        }
    return out


def utility_grid(rows: list[dict], arm: str) -> dict:
    rs = [r for r in rows if r["arm"] == arm]
    if not rs:
        return {}
    out = {}
    for lam in (1, 3, 10):
        for c in (0, 0.5):
            u = 0.0
            for r in rs:
                rel_c = 1.0 if r.get("oracle_whole_success") else 0.0
                rel_w = 1.0 - rel_c
                u += rel_c - lam * rel_w  # escalate 0 on invoice holdout
            out[f"lambda_{lam}_c_{c}"] = u / len(rs)
    return out


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
        primary = summarize_primary(rows)
        summary = {
            "primary": primary,
            "selective_2x2": selective_2x2(rows),
            "utility_grid_vacant": utility_grid(rows, args.primary_arm),
            "mcnemar_vacant_vs_maj3": mcnemar_pair(rows, args.primary_arm, "MAJ3"),
            "mcnemar_vacant_vs_blind": mcnemar_pair(rows, args.primary_arm, "BLIND"),
            "mcnemar_vacant_vs_lpb3": mcnemar_pair(rows, args.primary_arm, "LPB3"),
            "mcnemar_primary_frozen": mcnemar_pair(rows, args.primary_arm, args.baseline),
            "cost_means": _cost_means(rows),
        }
    args.out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()