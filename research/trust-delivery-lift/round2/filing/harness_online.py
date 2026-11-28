#!/usr/bin/env python3
"""Filing-Evidence online arms on CPU small LMs (<=2 calls/question, shared call-1 cache)."""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backends_r2 import SmallLM, GenResult  # noqa: E402

from offline_audit import page_text_for_question, load_jsonl
from quote_check import quote_check
from rule_baseline import rule_answer
from typed_filing_check import check_answer_typed, _numbers_in_line

SYSTEM = (
    "You extract financial facts from SEC filing excerpts. "
    'Reply with one JSON object: {"status":"found"|"not_found","value":number,"scale":"in millions"|"in billions",'
    '"page":int,"span":"verbatim line from text"}.'
)


def parse_answer(text: str) -> dict[str, Any]:
    s = text.strip()
    m = re.search(r"\{.*\}", s, re.DOTALL)
    if not m:
        return {"status": "not_found", "parse_error": True}
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"status": "not_found", "parse_error": True}
    if not isinstance(obj, dict):
        return {"status": "not_found"}
    return obj


def prompt_for(q: dict, page_text: str) -> str:
    return f"Company: {q.get('company', q.get('ticker'))}\nForm: {q.get('form')}\nDate: {q.get('report_date')}\n\nTEXT:\n{page_text}\n\nQuestion: {q['question']}\n\nJSON:"


def oracle_ok(answer: dict, gold: dict) -> bool:
    if str(gold.get("status")) != "found":
        return False
    if str(answer.get("status")).lower() == "not_found":
        return False
    try:
        v = float(answer.get("value"))
    except (TypeError, ValueError):
        return False
    g = float(gold.get("shown_value") or 0)
    if g == 0 and gold.get("display"):
        g = float(str(gold["display"]).replace(",", ""))
    return abs(v - g) <= max(0.5, 0.002 * abs(g))


def filing_key(q: dict) -> str:
    return f"{q.get('ticker','')}::{q.get('accession','')}"


def call1_cache_path(out: Path, qid: str) -> Path:
    return out / "cache" / f"{qid}__call1.json"


def get_call1(q: dict, page_text: str, lm: SmallLM, out: Path, reuse: bool) -> tuple[dict, list[GenResult]]:
    cp = call1_cache_path(out, q["id"])
    if reuse and cp.is_file():
        blob = json.loads(cp.read_text(encoding="utf-8"))
        return blob["answer"], [GenResult(**c) for c in blob["calls"]]
    r = lm.generate(SYSTEM, prompt_for(q, page_text), max_new_tokens=96)
    ans = parse_answer(r.text)
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(
        json.dumps({"answer": ans, "calls": [r.__dict__]}, indent=2),
        encoding="utf-8",
    )
    return ans, [r]


def row_base(q: dict, arm: str, model: str, answer: dict, calls: list[GenResult], delivered: bool) -> dict:
    gold = q.get("gold") or {}
    ok = oracle_ok(answer, gold) if delivered else False
    return {
        "question_id": q["id"],
        "filing_id": filing_key(q),
        "arm": arm,
        "model": model,
        "delivered": delivered,
        "oracle_ok": ok,
        "answer": answer,
        "prompt_tokens": sum(c.prompt_tokens for c in calls),
        "completion_tokens": sum(c.completion_tokens for c in calls),
        "cpu_seconds": sum(c.latency_s for c in calls),
        "n_calls": len(calls),
    }


def run_plain(q, page, lm, model, out) -> dict:
    a1, c1 = get_call1(q, page, lm, out, True)
    delivered = str(a1.get("status", "")).lower() != "not_found"
    return row_base(q, "PLAIN", model, a1, c1, delivered)


def run_quote_retry(q, page, lm, model, out) -> dict:
    a1, c1 = get_call1(q, page, lm, out, True)
    calls = list(c1)
    ok, _ = quote_check({"answer": a1}, page)
    if ok and str(a1.get("status", "")).lower() != "not_found":
        return row_base(q, "QUOTE_RETRY", model, a1, calls, True)
    r2 = lm.generate(SYSTEM, prompt_for(q, page) + "\nYour prior answer failed quote check. Fix span and value.\nJSON:", max_new_tokens=120)
    calls.append(r2)
    a2 = parse_answer(r2.text)
    delivered = str(a2.get("status", "")).lower() != "not_found"
    return row_base(q, "QUOTE_RETRY", model, a2, calls, delivered)


def run_blind(q, page, lm, model, out) -> dict:
    _, c1 = get_call1(q, page, lm, out, True)
    r2 = lm.generate(SYSTEM, prompt_for(q, page), max_new_tokens=120, temperature=0.7)
    a2 = parse_answer(r2.text)
    delivered = str(a2.get("status", "")).lower() != "not_found"
    return row_base(q, "BLIND", model, a2, c1 + [r2], delivered)


def alternatives_from_page(page: str) -> str:
    nums = []
    for line in page.splitlines()[:40]:
        for n in _numbers_in_line(line):
            nums.append(str(int(n)) if n == int(n) else str(n))
    uniq = list(dict.fromkeys(nums))[:8]
    return ", ".join(uniq) if uniq else "none listed"


def run_typed_reask(q, page, lm, model, out) -> dict:
    a1, c1 = get_call1(q, page, lm, out, True)
    calls = list(c1)
    typed = check_answer_typed({"answer": a1}, page, question=q)
    if typed.ok and str(a1.get("status", "")).lower() != "not_found":
        return row_base(q, "TYPED_REASK", model, a1, calls, True)
    alts = alternatives_from_page(page)
    u = prompt_for(q, page) + f"\nTyped check failed ({typed.reason}). Choose value from: {alts}. JSON:"
    r2 = lm.generate(SYSTEM, u, max_new_tokens=120, temperature=0.3)
    calls.append(r2)
    a2 = parse_answer(r2.text)
    t2 = check_answer_typed({"answer": a2}, page, question=q)
    delivered = t2.ok and str(a2.get("status", "")).lower() != "not_found"
    return row_base(q, "TYPED_REASK", model, a2, calls, delivered)


def run_typed_refuse(q, page, lm, model, out) -> dict:
    a1, c1 = get_call1(q, page, lm, out, True)
    typed = check_answer_typed({"answer": a1}, page, question=q)
    if typed.ok and str(a1.get("status", "")).lower() != "not_found":
        return row_base(q, "TYPED_REFUSE", model, a1, c1, True)
    return row_base(q, "TYPED_REFUSE", model, {"status": "not_certified", "reason": typed.reason}, c1, False)


def run_rule(q, page, _lm, model, _out) -> dict:
    ans = rule_answer(q, page)
    delivered = str(ans.get("status", "")).lower() == "found"
    return row_base(q, "RULE", model, ans, [], delivered)


ARM_FN = {
    "PLAIN": run_plain,
    "QUOTE_RETRY": run_quote_retry,
    "BLIND": run_blind,
    "TYPED_REASK": run_typed_reask,
    "TYPED_REFUSE": run_typed_refuse,
    "RULE": run_rule,
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", type=Path, default=Path(__file__).parent / "data" / "questions.jsonl")
    ap.add_argument("--subset", type=Path, default=Path(__file__).parent / "data" / "subset_20filings.json")
    ap.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    ap.add_argument("--arms", default="PLAIN,QUOTE_RETRY,BLIND,TYPED_REASK,TYPED_REFUSE,RULE")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    qs = {q["id"]: q for q in load_jsonl(args.questions)}
    subset = json.loads(args.subset.read_text(encoding="utf-8"))
    qids = subset["question_ids"]
    if args.limit:
        qids = qids[: args.limit]

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    lm = None if "RULE" in arms and len(arms) == 1 else SmallLM(args.model)
    if "RULE" in arms and any(a != "RULE" for a in arms):
        lm = lm or SmallLM(args.model)

    args.out.mkdir(parents=True, exist_ok=True)
    rows_path = args.out / "rows.jsonl"
    done = set()
    if rows_path.is_file():
        for line in rows_path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                done.add((r["question_id"], r["arm"]))

    with rows_path.open("a", encoding="utf-8") as fout:
        for qid in qids:
            q = qs[qid]
            page = page_text_for_question(q)
            for arm in arms:
                if (qid, arm) in done:
                    continue
                t0 = time.perf_counter()
                fn = ARM_FN[arm]
                use_lm = lm if arm != "RULE" else None
                row = fn(q, page, use_lm, args.model, args.out)  # type: ignore[arg-type]
                row["elapsed_s"] = time.perf_counter() - t0
                fout.write(json.dumps(row, ensure_ascii=False) + "\n")
                fout.flush()
                print(f"{qid} {arm} delivered={row['delivered']} ok={row['oracle_ok']}", flush=True)

    print(f"done -> {rows_path}")


if __name__ == "__main__":
    main()