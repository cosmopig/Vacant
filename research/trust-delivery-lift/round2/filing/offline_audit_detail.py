#!/usr/bin/env python3
"""Bootstrap CI + category breakdown for offline typed audit (checker validity on 9b C1)."""
from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from offline_audit import load_jsonl, page_text_for_question, quote_passed
from typed_filing_check import check_answer_typed, _numbers_in_line

_NUM = re.compile(r"(-?\d[\d,]*(?:\.\d+)?)")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * ((p * (1 - p) + z * z / (4 * n)) / n) ** 0.5
    return ((c - m) / d, (c + m) / d)


def bootstrap_prop(k: int, n: int, *, n_boot: int = 20000, seed: int = 0) -> dict:
    rng = random.Random(seed)
    if n == 0:
        return {"point": 0.0, "ci95": [0.0, 0.0]}
    rates = []
    for _ in range(n_boot):
        s = sum(rng.random() < (k / n) for __ in range(n))
        rates.append(s / n)
    rates.sort()
    lo = rates[int(0.025 * n_boot)]
    hi = rates[int(0.975 * n_boot)]
    return {"point": k / n, "ci95": [lo, hi], "wilson_ci95": list(wilson(k, n))}


def gold_value_match(ans: dict, gold: dict) -> bool:
    if str(gold.get("status")) != "found":
        return False
    try:
        shown = float(ans.get("value"))
    except (TypeError, ValueError):
        return False
    g = float(gold.get("shown_value") or 0)
    if g == 0 and gold.get("display"):
        g = float(str(gold["display"]).replace(",", ""))
    return abs(shown - g) <= max(0.5, 0.002 * abs(g))


def classify_false_reject(row: dict, q: dict, reason: str) -> str:
    ans = row.get("answer") or {}
    gold = q.get("gold") or {}
    if reason == "provenance_fail":
        span = str(ans.get("span", ""))
        page = page_text_for_question(q)
        if span and span in page:
            return "checker_provenance_bug"
        return "span_missing_from_evidence_page"
    if reason == "value_not_in_span":
        if gold_value_match(ans, gold):
            nums = _numbers_in_line(str(ans.get("span", "")))
            if nums and any(abs(float(ans.get("value", 0))) - abs(n) <= 0.5 for n in nums):
                return "checker_tolerance"
        return "value_not_in_cited_span_model_err"
    if reason == "scale_mismatch":
        return "checker_scale_heuristic"
    if reason == "not_found":
        return "checker_status"
    return f"checker_{reason}"


def classify_missed(row: dict, q: dict, reason_if_passed: str) -> str:
    ans = row.get("answer") or {}
    oc = row.get("outcome") or ""
    if oc == "missed":
        return "model_not_found_or_abstain"
    if oc == "confident_wrong":
        return "wrong_column_or_value_in_span"
    if typed := check_answer_typed(row, page_text_for_question(q)):
        if typed.ok:
            return "checker_missed_despite_wrong_gold"
    return f"outcome_{oc}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", type=Path, default=Path(__file__).parent / "data" / "questions.jsonl")
    ap.add_argument("--answers", type=Path, default=Path(__file__).parent / "data" / "qwen_c1_answers.jsonl")
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "data" / "offline_audit_detail.json")
    args = ap.parse_args()

    qs = {q["id"]: q for q in load_jsonl(args.questions)}
    rows = load_jsonl(args.answers)

    false_reject_cats: Counter = Counter()
    missed_cats: Counter = Counter()
    false_reject_examples: list[dict] = []
    missed_examples: list[dict] = []

    n_pass_correct = 0
    n_false = 0
    n_pass_wrong = 0
    n_missed_catch = 0

    for row in rows:
        qid = row.get("id")
        if qid not in qs or not quote_passed(row):
            continue
        q = qs[qid]
        oracle_ok = row.get("value_matches_gold")
        if oracle_ok is None:
            continue
        page = page_text_for_question(q)
        typed = check_answer_typed(row, page)
        if oracle_ok:
            n_pass_correct += 1
            if not typed.ok:
                n_false += 1
                cat = classify_false_reject(row, q, typed.reason)
                false_reject_cats[cat] += 1
                if len(false_reject_examples) < 12:
                    false_reject_examples.append(
                        {"id": qid, "reason": typed.reason, "category": cat, "outcome": row.get("outcome")}
                    )
        else:
            n_pass_wrong += 1
            if typed.ok:
                n_missed_catch += 1
                cat = classify_missed(row, q, typed.reason)
                missed_cats[cat] += 1
                if len(missed_examples) < 12:
                    missed_examples.append({"id": qid, "outcome": row.get("outcome"), "category": cat})

    out = {
        "label": "Checker validity on qwen3.5-9b C1 answers (not small-model delivery)",
        "n_pass_correct": n_pass_correct,
        "n_false_reject": n_false,
        "false_reject_rate_bootstrap": bootstrap_prop(n_false, n_pass_correct),
        "n_pass_wrong": n_pass_wrong,
        "n_missed_catch": n_missed_catch,
        "miss_rate_bootstrap": bootstrap_prop(n_missed_catch, n_pass_wrong),
        "catch_rate_bootstrap": bootstrap_prop(n_pass_wrong - n_missed_catch, n_pass_wrong),
        "false_reject_by_category": dict(false_reject_cats),
        "missed_by_category": dict(missed_cats),
        "interpretation_notes": [
            "Categories starting with checker_ attribute failure to visible typed rules, not HF gold.",
            "value_not_in_cited_span_model_err: span cites line but numeric answer is wrong column (gold agrees with HF).",
            "gold is HF release field value_matches_gold; disagree only if our oracle helper differs.",
        ],
        "examples_false_reject": false_reject_examples,
        "examples_missed": missed_examples,
    }
    args.out.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in out if k not in ("examples_false_reject", "examples_missed")}, indent=2))


if __name__ == "__main__":
    main()