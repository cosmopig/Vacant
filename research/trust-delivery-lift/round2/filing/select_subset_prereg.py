#!/usr/bin/env python3
"""Pre-registered random subset: seed=42, 20 filings, max 220 questions."""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path


def filing_key(q: dict) -> str:
    return f"{q.get('ticker','')}::{q.get('accession','')}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", type=Path, default=Path(__file__).parent / "data" / "questions.jsonl")
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "data" / "subset_prereg_seed42.json")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n_filings", type=int, default=20)
    ap.add_argument("--max_questions", type=int, default=220)
    args = ap.parse_args()
    rows = [json.loads(l) for l in args.questions.read_text().splitlines() if l.strip()]
    by_filing: dict[str, list[dict]] = defaultdict(list)
    for q in rows:
        if (q.get("gold") or {}).get("status") != "found":
            continue
        by_filing[filing_key(q)].append(q)
    keys = sorted(by_filing.keys())
    rng = random.Random(args.seed)
    rng.shuffle(keys)
    picked = keys[: args.n_filings]
    qids: list[str] = []
    for k in sorted(picked):
        for q in sorted(by_filing[k], key=lambda x: x["id"]):
            qids.append(q["id"])
            if len(qids) >= args.max_questions:
                break
        if len(qids) >= args.max_questions:
            break
    out = {
        "prereg_seed": args.seed,
        "n_filings": len(picked),
        "n_questions": len(qids),
        "filings": sorted(picked),
        "question_ids": qids,
    }
    args.out.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()