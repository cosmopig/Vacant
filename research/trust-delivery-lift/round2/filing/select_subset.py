#!/usr/bin/env python3
"""Pick ~20 filings (~220 questions) for online CPU runs."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def filing_key(q: dict) -> str:
    return f"{q.get('ticker','')}::{q.get('accession','')}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", type=Path, default=Path(__file__).parent / "data" / "questions.jsonl")
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "data" / "subset_20filings.json")
    ap.add_argument("--n_filings", type=int, default=20)
    args = ap.parse_args()
    rows = [json.loads(l) for l in args.questions.read_text().splitlines() if l.strip()]
    by_filing: dict[str, list[dict]] = defaultdict(list)
    for q in rows:
        if (q.get("gold") or {}).get("status") != "found":
            continue
        by_filing[filing_key(q)].append(q)
    # stable order: filings with most questions first, then key
    keys = sorted(by_filing.keys(), key=lambda k: (-len(by_filing[k]), k))
    picked = keys[: args.n_filings]
    qids = []
    for k in picked:
        for q in sorted(by_filing[k], key=lambda x: x["id"]):
            qids.append(q["id"])
    out = {
        "n_filings": len(picked),
        "n_questions": len(qids),
        "filings": picked,
        "question_ids": qids,
    }
    args.out.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("n_filings", "n_questions", "filings")}, indent=2))


if __name__ == "__main__":
    main()