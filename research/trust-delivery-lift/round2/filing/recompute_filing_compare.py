#!/usr/bin/env python3
"""Exploratory: 0.5B vs 1.5B on same prereg subset; false-release among deliveries."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from recompute_filing import bootstrap_filing_rate, filing_perfect, load_jsonl


def arm_delivery_stats(rows: list[dict]) -> dict:
    by: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by[r["arm"]].append(r)
    out = {}
    for arm, rs in sorted(by.items()):
        deliv = [r for r in rs if r.get("delivered")]
        n_del = len(deliv)
        n_correct = sum(1 for r in deliv if r.get("oracle_ok"))
        n_wrong = n_del - n_correct
        filings_delivered = sorted({r["filing_id"] for r in deliv})
        perfect = filing_perfect(rs)
        n_zero_wrong = sum(1 for f in filings_delivered if perfect.get(f, False))
        boot = bootstrap_filing_rate(filings_delivered, perfect) if filings_delivered else {"point": 0.0, "ci95": [0.0, 0.0]}
        out[arm] = {
            "n_questions": len(rs),
            "released_correct": n_correct,
            "released_wrong": n_wrong,
            "released_total": n_del,
            "false_release_rate_given_delivered": n_wrong / n_del if n_del else float("nan"),
            "filings_with_any_delivery": len(filings_delivered),
            "filings_zero_wrong": n_zero_wrong,
            "filing_zero_wrong_rate": boot,
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows-05b", type=Path, required=True)
    ap.add_argument("--rows-15b", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--label-gate-arms", default="TYPED_REFUSE,RULE")
    args = ap.parse_args()
    r05 = load_jsonl(args.rows_05b)
    r15 = load_jsonl(args.rows_15b)
    gate_arms = {a.strip() for a in args.label_gate_arms.split(",") if a.strip()}
    out = {
        "label": "exploratory_filing_05b_vs_15b_same_subset",
        "n_rows_05b": len(r05),
        "n_rows_15b": len(r15),
        "model_05b": "Qwen/Qwen2.5-0.5B-Instruct",
        "model_15b": "Qwen/Qwen2.5-1.5B-Instruct",
        "per_arm_05b": arm_delivery_stats(r05),
        "per_arm_15b": arm_delivery_stats(r15),
        "gate_false_release_note": "Arms treated as contract-gated ship candidates",
    }
    for label, stats in [("0.5B", out["per_arm_05b"]), ("1.5B", out["per_arm_15b"])]:
        agg = {"released_wrong": 0, "released_total": 0}
        for arm in gate_arms:
            if arm in stats:
                agg["released_wrong"] += stats[arm]["released_wrong"]
                agg["released_total"] += stats[arm]["released_total"]
        out[f"gate_arms_combined_{label}"] = {
            "arms": sorted(gate_arms),
            **agg,
            "false_release_rate_given_delivered": agg["released_wrong"] / agg["released_total"] if agg["released_total"] else float("nan"),
        }
    args.out.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()