#!/usr/bin/env python3
"""Uncontested vs contested split metrics (pre-registered; qwen9b then small-model)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contract.executor import execute_contract
from contract.filing_contract import (
    compile_contract_independent,
    compile_contract_primary,
    compile_contract_question_only,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "filing"))
from offline_audit import load_jsonl, page_text_for_question, quote_passed  # noqa: E402


def unanimous_region(q: dict, row: dict, page: str) -> tuple[str, list[str]]:
    contracts = [
        compile_contract_primary(q),
        compile_contract_independent(q),
        compile_contract_question_only(q),
    ]
    aggs = [execute_contract(c, row, page).aggregate for c in contracts]
    if len(set(aggs)) == 1:
        return "uncontested", aggs
    return "contested", aggs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", type=Path, required=True)
    ap.add_argument("--answers", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--label", default="qwen3.5-9b C1")
    args = ap.parse_args()
    qs = {q["id"]: q for q in load_jsonl(args.questions)}
    rows = load_jsonl(args.answers)

    n = 0
    n_uncontested = 0
    n_contested = 0
    n_uncontested_unanimous_pass = 0
    auto_pass_oracle_ok = 0
    auto_pass_oracle_wrong = 0
    uncontested_wrong = 0
    uncontested_catch = 0

    contested_reasons: dict[str, int] = {}

    for row in rows:
        qid = row.get("id")
        if qid not in qs:
            continue
        q = qs[qid]
        page = page_text_for_question(q)
        region, aggs = unanimous_region(q, row, page)
        n += 1
        vo = row.get("value_matches_gold")
        if region == "uncontested":
            n_uncontested += 1
            if aggs[0] == "PASS":
                n_uncontested_unanimous_pass += 1
                if vo is True:
                    auto_pass_oracle_ok += 1
                elif vo is False:
                    auto_pass_oracle_wrong += 1
            if quote_passed(row) and vo is False:
                uncontested_wrong += 1
                if aggs[0] != "PASS":
                    uncontested_catch += 1
        else:
            n_contested += 1
            contested_reasons["|".join(aggs)] = contested_reasons.get("|".join(aggs), 0) + 1

    out = {
        "label": args.label,
        "n_tasks": n,
        "coverage_uncontested": n_uncontested / n if n else 0,
        "coverage_auto_pass_eligible": n_uncontested_unanimous_pass / n if n else 0,
        "n_uncontested_unanimous_pass": n_uncontested_unanimous_pass,
        "false_release_uncontested_auto_pass": {
            "n_shipped": n_uncontested_unanimous_pass,
            "n_wrong": auto_pass_oracle_wrong,
            "n_right": auto_pass_oracle_ok,
            "rate": auto_pass_oracle_wrong / n_uncontested_unanimous_pass if n_uncontested_unanimous_pass else 0,
        },
        "contested_share": n_contested / n if n else 0,
        "contested_aggregate_patterns_top10": sorted(
            contested_reasons.items(), key=lambda x: -x[1]
        )[:10],
        "uncontested_quote_pass_wrong_n": uncontested_wrong,
        "uncontested_catch_rate_on_wrong": uncontested_catch / uncontested_wrong if uncontested_wrong else 0,
        "interpretation": (
            "High contested share + low auto_pass_eligible = honest coverage, not refuse-everything "
            "unless uncontested false-release is also low."
        ),
    }
    args.out.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()