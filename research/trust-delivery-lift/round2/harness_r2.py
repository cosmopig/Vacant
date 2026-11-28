#!/usr/bin/env python3
"""Round 2 primary arms: field-locked VACANT vs Maj3/LPB3."""
from __future__ import annotations

import argparse
import json
import random
import time
from collections import Counter
from pathlib import Path
from typing import Any

from backends_r2 import GenResult, SmallLM
from checks import FIELDS, check_field, check_global, oracle_whole, parse_json_delivery, visible_all_pass

SYSTEM = "Extract invoice fields into one JSON object with keys: " + ", ".join(FIELDS) + ". Output JSON only."

MICRO = {
    "vendor": 'Extract only vendor name from the text. One short string:',
    "invoice_date": 'Extract invoice_date as YYYY-MM-DD only:',
    "due_date": 'Extract due_date as YYYY-MM-DD only:',
    "currency": 'Extract 3-letter ISO currency code only:',
    "subtotal": 'Extract subtotal number only (two decimals, no symbol):',
    "tax": 'Extract tax number only (two decimals):',
    "total": 'Extract total number only (two decimals):',
    "order_id": 'Extract order/purchase id exactly as in text:',
}


def full_prompt(task: dict[str, Any]) -> str:
    return f"TEXT:\n{task['source_text']}\n\nJSON:"


def run_blind(task: dict[str, Any], lm: SmallLM, rng: random.Random) -> dict[str, Any]:
    """Equal-cost baseline: second independent full JSON sample is delivered (call-1 logged only as draft)."""
    r1 = lm.generate(SYSTEM, full_prompt(task), max_new_tokens=220)
    r2 = lm.generate(SYSTEM, full_prompt(task), max_new_tokens=220, temperature=0.7)
    doc = parse_json_delivery(r2.text)
    vis, _ = visible_all_pass(doc, task)
    ora = oracle_whole(doc, task) if task.get("answerable", True) else False
    return _row(task, "BLIND", parse_json_delivery(r1.text), doc, [r1, r2], vis, ora)


def run_one(task: dict[str, Any], lm: SmallLM) -> dict[str, Any]:
    r = lm.generate(SYSTEM, full_prompt(task), max_new_tokens=220, with_logprob=True)
    doc = parse_json_delivery(r.text)
    vis, _ = visible_all_pass(doc, task)
    ora = oracle_whole(doc, task) if task.get("answerable", True) else False
    return _row(task, "ONE", doc, doc, [r], vis, ora)


def run_maj3(task: dict[str, Any], lm: SmallLM, rng: random.Random) -> dict[str, Any]:
    rs: list[GenResult] = []
    docs: list[dict[str, str]] = []
    for _ in range(3):
        r = lm.generate(SYSTEM, full_prompt(task), max_new_tokens=220, temperature=0.7)
        rs.append(r)
        docs.append(parse_json_delivery(r.text))
    merged: dict[str, str] = {}
    for f in FIELDS:
        vals = [d.get(f, "") for d in docs if d.get(f)]
        merged[f] = Counter(vals).most_common(1)[0][0] if vals else ""
    vis, _ = visible_all_pass(merged, task)
    ora = oracle_whole(merged, task) if task.get("answerable", True) else False
    return _row(task, "MAJ3", docs[0], merged, rs, vis, ora)


def run_lpb3(task: dict[str, Any], lm: SmallLM) -> dict[str, Any]:
    rs: list[GenResult] = []
    docs: list[dict[str, str]] = []
    best_i = 0
    best_lp = -1e9
    for i in range(3):
        r = lm.generate(SYSTEM, full_prompt(task), max_new_tokens=220, temperature=0.7, with_logprob=True)
        rs.append(r)
        doc = parse_json_delivery(r.text)
        docs.append(doc)
        lp = r.mean_logprob if r.mean_logprob is not None else -1e9
        if lp > best_lp:
            best_lp, best_i = lp, i
    doc = docs[best_i]
    vis, _ = visible_all_pass(doc, task)
    ora = oracle_whole(doc, task) if task.get("answerable", True) else False
    return _row(task, "LPB3", docs[0], doc, rs, vis, ora)


def run_stitch(task: dict[str, Any], lm: SmallLM) -> dict[str, Any]:
    rs: list[GenResult] = []
    docs: list[dict[str, str]] = []
    for _ in range(3):
        r = lm.generate(SYSTEM, full_prompt(task), max_new_tokens=220, temperature=0.7)
        rs.append(r)
        docs.append(parse_json_delivery(r.text))
    merged: dict[str, str] = {}
    for f in FIELDS:
        picked = ""
        for d in docs:
            trial = dict(merged)
            trial[f] = d.get(f, "")
            ok, _ = check_field(f, trial.get(f), task, trial)
            if ok:
                gok, _ = check_global(trial, task) if all(trial.get(x) for x in FIELDS if x == f or trial.get(x)) else (True, "ok")
                if gok:
                    picked = trial[f]
                    break
        merged[f] = picked or docs[0].get(f, "")
    vis, _ = visible_all_pass(merged, task)
    ora = oracle_whole(merged, task) if task.get("answerable", True) else False
    return _row(task, "STITCH", docs[0], merged, rs, vis, ora)


def run_vacant(task: dict[str, Any], lm: SmallLM, max_micro: int = 8) -> dict[str, Any]:
    calls: list[GenResult] = []
    r1 = lm.generate(SYSTEM, full_prompt(task), max_new_tokens=220)
    calls.append(r1)
    doc = parse_json_delivery(r1.text)
    locked: set[str] = set()
    for f in FIELDS:
        ok, _ = check_field(f, doc.get(f), task, doc)
        if ok:
            locked.add(f)
    micro_budget = max_micro
    for f in FIELDS:
        if f in locked:
            continue
        if micro_budget <= 0:
            break
        micro_budget -= 1
        u = f"TEXT:\n{task['source_text']}\n\n{MICRO[f]}"
        r = lm.generate(SYSTEM, u, max_new_tokens=48, temperature=0.3)
        calls.append(r)
        val = r.text.strip().split("\n")[0].strip().strip('"')
        trial = dict(doc)
        trial[f] = val
        ok, _ = check_field(f, val, task, trial)
        if ok:
            gok, _ = check_global(trial, task)
            if gok:
                doc[f] = val
                locked.add(f)
    vis, per = visible_all_pass(doc, task)
    ora = oracle_whole(doc, task) if task.get("answerable", True) else False
    return _row(task, "VACANT", parse_json_delivery(r1.text), doc, calls, vis, ora, extra={"locked_fields": sorted(locked), "visible_detail": {k: v[1] for k, v in per.items()}})


def _row(
    task: dict,
    arm: str,
    draft: dict,
    final: dict,
    calls: list[GenResult],
    visible_pass: bool,
    oracle_pass: bool,
    extra: dict | None = None,
) -> dict:
    pt = sum(c.prompt_tokens for c in calls)
    ct = sum(c.completion_tokens for c in calls)
    cpu = sum(c.latency_s for c in calls)
    row = {
        "task_id": task["task_id"],
        "template_id": task["template_id"],
        "answerable": task.get("answerable", True),
        "arm": arm,
        "draft": draft,
        "final": final,
        "visible_all_pass": visible_pass,
        "oracle_whole_success": oracle_pass,
        "visible_x_oracle": f"{'V+' if visible_pass else 'V-'}_{'O+' if oracle_pass else 'O-'}",
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "cpu_seconds": cpu,
        "n_calls": len(calls),
    }
    if extra:
        row.update(extra)
    return row


ARM_FN = {
    "BLIND": lambda t, lm, r: run_blind(t, lm, r),
    "ONE": lambda t, lm, r: run_one(t, lm),
    "MAJ3": lambda t, lm, r: run_maj3(t, lm, r),
    "LPB3": lambda t, lm, r: run_lpb3(t, lm),
    "STITCH": lambda t, lm, r: run_stitch(t, lm),
    "VACANT": lambda t, lm, r: run_vacant(t, lm),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", type=Path, default=Path(__file__).parent / "tasks_r2.json")
    ap.add_argument("--split", choices=("dev_ids", "holdout_answerable_ids", "holdout_unanswerable_ids", "all_holdout"), default="dev_ids")
    ap.add_argument("--arms", default="ONE,VACANT,MAJ3")
    ap.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    bank = json.loads(args.bank.read_text(encoding="utf-8"))
    if args.split == "all_holdout":
        ids = bank["split"]["holdout_answerable_ids"] + bank["split"]["holdout_unanswerable_ids"]
    else:
        ids = bank["split"][args.split]
    by_id = {t["task_id"]: t for t in bank["tasks"]}
    tasks = [by_id[i] for i in ids]
    if args.limit:
        tasks = tasks[: args.limit]

    lm = SmallLM(args.model)
    rng = random.Random(args.seed)
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]

    args.out.mkdir(parents=True, exist_ok=True)
    rows = []
    for task in tasks:
        for arm in arms:
            fn = ARM_FN[arm]
            rows.append(fn(task, lm, rng))
            (args.out / f"{task['task_id']}__{arm}.json").write_text(json.dumps(rows[-1], indent=2), encoding="utf-8")

    with (args.out / "rows.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} rows -> {args.out}")


if __name__ == "__main__":
    main()