#!/usr/bin/env python3
"""Offline audit: typed check on Filing-Evidence rows that passed quote check (failed_check=None)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from typed_filing_check import check_answer_typed


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def page_text_for_question(q: dict) -> str:
    gold = q.get("gold") or {}
    lines = [e.get("line", "") for e in (gold.get("evidence") or []) if e.get("line")]
    scale = gold.get("scale", 6)
    header = "(in millions)" if int(scale) >= 6 else "(in thousands)"
    rd = q.get("report_date") or ""
    cols = f" {rd} " if rd else " "
    return header + cols + " ".join(lines)


def quote_passed(row: dict) -> bool:
    return row.get("failed_check") is None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", type=Path, required=True)
    ap.add_argument("--answers", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    questions = {q["id"]: q for q in load_jsonl(args.questions)}
    answers = load_jsonl(args.answers)

    n_pass = 0
    n_pass_wrong = 0
    n_pass_correct = 0
    n_catch_wrong = 0
    n_false_reject = 0
    examples: list[dict] = []

    for row in answers:
        qid = row.get("id")
        if qid not in questions:
            continue
        if not quote_passed(row):
            continue
        q = questions[qid]
        gold = q.get("gold") or {}
        page = page_text_for_question(q)
        oracle_ok = row.get("value_matches_gold")
        if oracle_ok is None:
            continue
        n_pass += 1
        if oracle_ok:
            n_pass_correct += 1
        else:
            n_pass_wrong += 1

        typed = check_answer_typed(row, page)
        if oracle_ok is False and not typed.ok:
            n_catch_wrong += 1
        if oracle_ok is True and not typed.ok:
            n_false_reject += 1
        if len(examples) < 30:
            examples.append(
                {
                    "id": qid,
                    "outcome": row.get("outcome"),
                    "oracle_ok": oracle_ok,
                    "typed_ok": typed.ok,
                    "reason": typed.reason,
                }
            )

    catch_rate = n_catch_wrong / n_pass_wrong if n_pass_wrong else 0.0
    false_reject_rate = n_false_reject / n_pass_correct if n_pass_correct else 0.0
    stop_ineffective = n_pass_wrong > 0 and (
        catch_rate < 0.30 or false_reject_rate > 0.05
    )

    results = {
        "dataset": "pramana-research/filing-evidence",
        "model_answers": str(args.answers.name),
        "n_quote_pass": n_pass,
        "n_pass_value_wrong": n_pass_wrong,
        "n_pass_value_correct": n_pass_correct,
        "n_typed_catch_wrong": n_catch_wrong,
        "n_typed_false_reject_correct": n_false_reject,
        "catch_rate_among_quote_pass_wrong": catch_rate,
        "false_reject_rate_among_quote_pass_correct": false_reject_rate,
        "stop_rule_ineffective": stop_ineffective,
        "stop_rule_detail": "ineffective if catch<30% on pass-but-wrong OR false_reject>5% on correct",
        "examples": examples,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps({k: results[k] for k in results if k != "examples"}, indent=2))


if __name__ == "__main__":
    main()