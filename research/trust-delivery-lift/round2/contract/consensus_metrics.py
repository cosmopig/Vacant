#!/usr/bin/env python3
"""Primary vs consensus contract on qwen C1 (checker validity); opcode decomposition."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from contract.consensus import build_consensus, compile_three_authors
from contract.executor import execute_contract
from contract.filing_contract import compile_contract_primary

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "filing"))
from offline_audit import load_jsonl, page_text_for_question, quote_passed  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", type=Path, default=Path(__file__).parent.parent / "filing" / "data" / "questions.jsonl")
    ap.add_argument("--answers", type=Path, default=Path(__file__).parent.parent / "filing" / "data" / "qwen_c1_answers.jsonl")
    ap.add_argument("--out", type=Path, default=Path(__file__).parent.parent / "filing" / "data" / "consensus_metrics_qwen_c1.json")
    args = ap.parse_args()

    qs = {q["id"]: q for q in load_jsonl(args.questions)}
    rows = load_jsonl(args.answers)

    opcode_pool: dict = defaultdict(lambda: {"in_1": 0, "in_2": 0, "in_3": 0, "param_split": 0})
    delivery_agree = 0
    n = 0
    disagree_reasons: Counter = Counter()

    primary_catch = primary_false_reject = primary_false_release = 0
    cons_catch = cons_false_reject = cons_false_release = 0
    n_wrong = n_correct = 0
    n_pass_primary = n_pass_cons = 0

    for row in rows:
        qid = row.get("id")
        if qid not in qs:
            continue
        q = qs[qid]
        page = page_text_for_question(q)
        cons = build_consensus(compile_three_authors(q))
        for op, meta in cons["decomposition"].items():
            c = meta["authors_including"]
            if c == 1:
                opcode_pool[op]["in_1"] += 1
            elif c == 2:
                opcode_pool[op]["in_2"] += 1
            else:
                opcode_pool[op]["in_3"] += 1
            if meta.get("in_consensus") and not meta.get("param_agreement", True):
                opcode_pool[op]["param_split"] += 1

        rp = execute_contract(compile_contract_primary(q), row, page)
        rc = execute_contract(cons, row, page)
        n += 1
        if (rp.aggregate == "PASS") == (rc.aggregate == "PASS"):
            delivery_agree += 1
        elif rc.aggregate == "ESCALATE" and rp.aggregate == "PASS":
            disagree_reasons["consensus_escalate_vs_primary_pass"] += 1
        elif rc.aggregate == "PASS" and rp.aggregate != "PASS":
            disagree_reasons["consensus_pass_vs_primary_fail"] += 1
        else:
            disagree_reasons["other_aggregate_mismatch"] += 1

        if not quote_passed(row) or row.get("value_matches_gold") is None:
            continue
        vo = bool(row.get("value_matches_gold"))
        d_p = rp.aggregate == "PASS"
        d_c = rc.aggregate == "PASS"
        if not vo:
            n_wrong += 1
            if not d_p:
                primary_catch += 1
            if not d_c:
                cons_catch += 1
            if d_p:
                primary_false_release += 1
                n_pass_primary += 1
            if d_c:
                cons_false_release += 1
                n_pass_cons += 1
        else:
            n_correct += 1
            if d_p:
                n_pass_primary += 1
            if d_c:
                n_pass_cons += 1
            if not d_p:
                primary_false_reject += 1
            if not d_c:
                cons_false_reject += 1

    primary_fr = primary_false_release / n_pass_primary if n_pass_primary else 0
    cons_fr = cons_false_release / n_pass_cons if n_pass_cons else 0
    primary_cr = primary_catch / n_wrong if n_wrong else 0
    cons_cr = cons_catch / n_wrong if n_wrong else 0
    falsified = (cons_cr < primary_cr - 0.10) or (cons_fr > primary_fr + 0.02)

    out = {
        "label": "qwen3.5-9b C1 — consensus vs primary (checker validity)",
        "n_rows": n,
        "delivery_decision_agreement_primary_vs_consensus": delivery_agree / n if n else 0,
        "opcode_decomposition_pooled": dict(opcode_pool),
        "disagree_reasons_top": disagree_reasons.most_common(15),
        "quote_pass_wrong_n": n_wrong,
        "catch_rate_primary": primary_cr,
        "catch_rate_consensus": cons_cr,
        "catch_delta_pp": (cons_cr - primary_cr) * 100,
        "false_reject_primary": primary_false_reject,
        "false_reject_consensus": cons_false_reject,
        "false_release_rate_primary": primary_fr,
        "false_release_rate_consensus": cons_fr,
        "falsifier_triggered": falsified,
        "falsifier_rule": "consensus catch < primary-10pp OR consensus false_release > primary+2pp",
    }
    args.out.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()