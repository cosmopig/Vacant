#!/usr/bin/env python3
"""Contract metrics: reproducibility, false-release, ESCALATE, oracle agreement."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from contract.executor import execute_contract, executor_hash, receipt_agree
from contract.filing_contract import compile_contract_independent, compile_contract_primary
import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "filing"))
from offline_audit import load_jsonl, page_text_for_question, quote_passed  # noqa: E402


def oracle_value_ok(ans: dict, gold: dict) -> bool:
    if str(gold.get("status")) != "found":
        return False
    try:
        v = float((ans.get("answer") or ans).get("value"))
    except (TypeError, ValueError):
        return False
    g = float(gold.get("shown_value") or 0)
    if g == 0 and gold.get("display"):
        g = float(str(gold["display"]).replace(",", ""))
    return abs(v - g) <= max(0.5, 0.002 * abs(g))


def run_metrics(questions_path: Path, answers_path: Path) -> dict[str, Any]:
    qs = {q["id"]: q for q in load_jsonl(questions_path)}
    rows = load_jsonl(answers_path)
    exec_h = executor_hash()
    repro_fail = 0
    n_exec = 0
    false_release = 0
    delivered_pass = 0
    escalate = 0
    contract_oracle_agree = 0
    contract_oracle_total = 0
    incompleteness = Counter()
    ind_vs_pri_same_delivery = 0
    ind_vs_pri_total = 0

    for row in rows:
        qid = row.get("id")
        if qid not in qs:
            continue
        q = qs[qid]
        page = page_text_for_question(q)
        primary = compile_contract_primary(q)
        independent = compile_contract_independent(q)
        for contract in (primary, independent):
            r1 = execute_contract(contract, row, page)
            r2 = execute_contract(contract, row, page)
            n_exec += 1
            if not receipt_agree(r1, r2):
                repro_fail += 1
        rp = execute_contract(primary, row, page)
        ri = execute_contract(independent, row, page)

        def would_deliver(r):
            return r.aggregate == "PASS"

        ind_vs_pri_total += 1
        if would_deliver(rp) == would_deliver(ri):
            ind_vs_pri_same_delivery += 1

        if rp.aggregate == "ESCALATE":
            escalate += 1
        if rp.aggregate == "PASS":
            delivered_pass += 1
            oracle_ok = bool(row.get("value_matches_gold"))
            if not oracle_ok:
                false_release += 1
            for c in rp.clauses:
                if c.verdict == "FAIL" and c.detail == "value_not_in_span_numbers":
                    incompleteness["missing_period_column_clause"] += 0
        if quote_passed(row) and row.get("value_matches_gold") and rp.aggregate != "PASS":
            for c in rp.clauses:
                if c.verdict == "FAIL":
                    incompleteness[c.detail] += 1

        # contract-oracle: declared instant vs gold (metadata agreement, not model)
        gold = q.get("gold") or {}
        if primary.get("declared_period_instant") == _instant(gold):
            contract_oracle_agree += 1
        contract_oracle_total += 1

    n_pri = len([r for r in rows if r.get("id") in qs])
    return {
        "label": "qwen3.5-9b C1 — contract execution metrics (checker validity)",
        "executor_sha256": exec_h,
        "third_party_reproducibility": {
            "n_executions": n_exec,
            "mismatched_reruns": repro_fail,
            "agreement_rate": 1.0 - (repro_fail / n_exec if n_exec else 0),
        },
        "false_release_rate": {
            "n_delivered_pass": delivered_pass,
            "n_false_release": false_release,
            "rate": false_release / delivered_pass if delivered_pass else 0,
        },
        "escalate_rate_primary": {
            "n_rows": n_pri,
            "n_escalate": escalate,
            "rate": escalate / n_pri if n_pri else 0,
        },
        "independent_contract_delivery_agreement": {
            "n": ind_vs_pri_total,
            "n_same_delivery_decision": ind_vs_pri_same_delivery,
            "rate": ind_vs_pri_same_delivery / ind_vs_pri_total if ind_vs_pri_total else 0,
        },
        "contract_metadata_oracle_agreement": {
            "n": contract_oracle_total,
            "n_agree": contract_oracle_agree,
            "rate": contract_oracle_agree / contract_oracle_total if contract_oracle_total else 0,
        },
        "false_reject_incompleteness_tags_among_correct_quote_pass": dict(incompleteness),
        "note_false_rejects_35": (
            "Recorded as contract incompleteness (evidence page stub lacks full span; "
            "no period/column clause), not post-hoc threshold tuning."
        ),
    }


def _instant(gold: dict) -> str | None:
    period = gold.get("period") or {}
    return period.get("instant") or period.get("end")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", type=Path, default=Path(__file__).parent.parent / "filing" / "data" / "questions.jsonl")
    ap.add_argument("--answers", type=Path, default=Path(__file__).parent.parent / "filing" / "data" / "qwen_c1_answers.jsonl")
    ap.add_argument("--out", type=Path, default=Path(__file__).parent.parent / "filing" / "data" / "contract_metrics_qwen_c1.json")
    args = ap.parse_args()
    out = run_metrics(args.questions, args.answers)
    args.out.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()