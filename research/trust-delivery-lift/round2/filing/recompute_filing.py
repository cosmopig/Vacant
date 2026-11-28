#!/usr/bin/env python3
"""Filing-level zero-wrong rate + bootstrap CI; cost per arm."""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def filing_perfect(rows: list[dict]) -> dict[str, bool]:
    """Filing perfect iff every delivered answer is oracle_ok; no wrong deliveries."""
    by_filing: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if not r.get("delivered"):
            continue
        by_filing[r["filing_id"]].append(r)
    out: dict[str, bool] = {}
    for fid, rs in by_filing.items():
        out[fid] = all(r.get("oracle_ok") for r in rs)
    return out


def bootstrap_filing_rate(filings: list[str], perfect: dict[str, bool], *, n_boot: int = 10000, seed: int = 0) -> dict:
    rng = random.Random(seed)
    n = len(filings)
    if n == 0:
        return {"point": 0.0, "ci95": [0.0, 0.0]}
    k = sum(1 for f in filings if perfect.get(f, False))
    rates = []
    for _ in range(n_boot):
        sample = [filings[rng.randrange(n)] for __ in range(n)]
        kk = sum(1 for f in sample if perfect.get(f, False))
        rates.append(kk / n)
    rates.sort()
    return {"point": k / n, "ci95": [rates[int(0.025 * n_boot)], rates[int(0.975 * n_boot)]]}


def summarize(rows: list[dict]) -> dict:
    by_arm: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_arm[r["arm"]].append(r)
    out = {}
    all_filings = sorted({r["filing_id"] for r in rows})
    for arm, rs in sorted(by_arm.items()):
        perfect = filing_perfect(rs)
        # include filings with zero deliveries as imperfect? prereg: share delivered with zero wrong
        # denominator: filings that had at least one delivery from this arm
        arms_filings = sorted({r["filing_id"] for r in rs if r.get("delivered")})
        n_delivered_filings = len(arms_filings)
        n_perfect = sum(1 for f in arms_filings if perfect.get(f, False))
        boot = bootstrap_filing_rate(arms_filings, perfect)
        n_del = sum(1 for r in rs if r.get("delivered"))
        n_wrong = sum(1 for r in rs if r.get("delivered") and not r.get("oracle_ok"))
        out[arm] = {
            "n_questions": len(rs),
            "n_delivered_answers": n_del,
            "n_wrong_delivered": n_wrong,
            "filings_with_any_delivery": n_delivered_filings,
            "filings_zero_wrong": n_perfect,
            "filing_zero_wrong_rate": boot,
            "mean_cpu_s_per_question": sum(r.get("cpu_seconds", 0) for r in rs) / len(rs) if rs else 0,
            "mean_tokens_per_question": sum(
                r.get("prompt_tokens", 0) + r.get("completion_tokens", 0) for r in rs
            )
            / len(rs)
            if rs
            else 0,
            "mean_calls_per_question": sum(r.get("n_calls", 0) for r in rs) / len(rs) if rs else 0,
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    rows = load_jsonl(args.rows)
    summary = summarize(rows)
    args.out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()