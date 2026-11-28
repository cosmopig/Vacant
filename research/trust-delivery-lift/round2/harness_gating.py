#!/usr/bin/env python3
"""Round 2 secondary: gating arms (Rank 4)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from backends_r2 import SmallLM
from checks import oracle_whole, parse_json_delivery, visible_all_pass
from harness_r2 import SYSTEM, full_prompt


def gate_vacant(task, lm):
    r = lm.generate(SYSTEM, full_prompt(task), max_new_tokens=220)
    doc = parse_json_delivery(r.text)
    vis, _ = visible_all_pass(doc, task)
    shipped = vis
    return doc, shipped, [r]


def gate_logprob(task, lm, threshold: float):
    r = lm.generate(SYSTEM, full_prompt(task), max_new_tokens=220, with_logprob=True)
    doc = parse_json_delivery(r.text)
    lp = r.mean_logprob if r.mean_logprob is not None else -999.0
    shipped = lp >= threshold
    return doc, shipped, [r]


def gate_sc2(task, lm):
    r1 = lm.generate(SYSTEM, full_prompt(task), max_new_tokens=220, temperature=0.7)
    r2 = lm.generate(SYSTEM, full_prompt(task), max_new_tokens=220, temperature=0.7)
    d1, d2 = parse_json_delivery(r1.text), parse_json_delivery(r2.text)
    shipped = d1 == d2 and bool(d1)
    doc = d1 if shipped else d1
    return doc, shipped, [r1, r2]


def gate_sv(task, lm):
    r1 = lm.generate(SYSTEM, full_prompt(task), max_new_tokens=220)
    d1 = parse_json_delivery(r1.text)
    vprompt = f"TEXT:\n{task['source_text']}\n\nJSON:\n{json.dumps(d1)}\n\nDoes this JSON satisfy all invoice fields with values from the text? Answer only YES or NO."
    r2 = lm.generate(SYSTEM, vprompt, max_new_tokens=8)
    shipped = r2.text.strip().upper().startswith("YES")
    return d1, shipped, [r1, r2]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", type=Path, default=Path(__file__).parent / "tasks_r2.json")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    ap.add_argument("--logprob-threshold", type=float, default=-0.35)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    bank = json.loads(args.bank.read_text(encoding="utf-8"))
    ids = bank["split"]["holdout_answerable_ids"] + bank["split"]["holdout_unanswerable_ids"]
    by_id = {t["task_id"]: t for t in bank["tasks"]}
    tasks = [by_id[i] for i in ids]
    if args.limit:
        tasks = tasks[: args.limit]

    lm = SmallLM(args.model)
    arms = [
        ("GATE_VACANT", lambda t: gate_vacant(t, lm)),
        ("GATE_LOGPROB", lambda t: gate_logprob(t, lm, args.logprob_threshold)),
        ("GATE_SC2", lambda t: gate_sc2(t, lm)),
        ("GATE_SV", lambda t: gate_sv(t, lm)),
    ]

    args.out.mkdir(parents=True, exist_ok=True)
    rows = []
    for task in tasks:
        for name, fn in arms:
            doc, shipped, calls = fn(task)
            wrong_ship = shipped and task.get("answerable", True) and not oracle_whole(doc, task)
            wrong_ship |= shipped and not task.get("answerable", True)
            correct_ship = shipped and task.get("answerable", True) and oracle_whole(doc, task)
            row = {
                "task_id": task["task_id"],
                "answerable": task.get("answerable", True),
                "arm": name,
                "shipped": shipped,
                "correct_ship": correct_ship,
                "wrong_ship": wrong_ship,
                "oracle_whole_success": oracle_whole(doc, task) if shipped else False,
                "prompt_tokens": sum(c.prompt_tokens for c in calls),
                "cpu_seconds": sum(c.latency_s for c in calls),
                "n_calls": len(calls),
            }
            rows.append(row)

    with (args.out / "rows.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"gating rows: {len(rows)} -> {args.out}")


if __name__ == "__main__":
    main()