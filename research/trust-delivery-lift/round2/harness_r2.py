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
    d1, d2 = parse_json_delivery(r1.text), parse_json_delivery(r2.text)
    return _row(task, "BLIND", d1, doc, [r1, r2], vis, ora, draft_docs=[d1, d2])


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
    return _row(task, "MAJ3", docs[0], merged, rs, vis, ora, draft_docs=docs)


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
    return _row(task, "LPB3", docs[0], doc, rs, vis, ora, draft_docs=docs)


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


def run_vacant(task: dict[str, Any], lm: SmallLM, max_micro: int = 4) -> dict[str, Any]:
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


def _deliverable_dict(d: dict) -> bool:
    """Parsed JSON with all invoice fields present (non-empty); blocks {} parse-fail equality."""
    return bool(d) and all(str(d.get(f, "")).strip() for f in FIELDS)


def _gating_ship(arm: str, calls: list[GenResult], doc: dict, draft_docs: list[dict], visible_pass: bool) -> bool:
    """Exploratory secondary gate (no extra model calls). LPB3 τ quarantined — see amendment."""
    if arm == "VACANT":
        return visible_pass
    if arm == "BLIND" and len(draft_docs) >= 2:
        if not all(_deliverable_dict(x) for x in draft_docs[:2]):
            return False
        return draft_docs[0] == draft_docs[1]
    if arm == "MAJ3" and len(draft_docs) >= 3:
        if not all(_deliverable_dict(x) for x in draft_docs[:3]):
            return False
        return draft_docs[0] == draft_docs[1] == draft_docs[2]
    # LPB3 gate DISABLED (invalid τ) — always no-ship until dev logprob artifact exists.
    if arm == "LPB3":
        return False
    return False


def _row(
    task: dict,
    arm: str,
    draft: dict,
    final: dict,
    calls: list[GenResult],
    visible_pass: bool,
    oracle_pass: bool,
    extra: dict | None = None,
    *,
    draft_docs: list[dict] | None = None,
) -> dict:
    pt = sum(c.prompt_tokens for c in calls)
    ct = sum(c.completion_tokens for c in calls)
    cpu = sum(c.latency_s for c in calls)
    c0 = parse_json_delivery(calls[0].text) if calls else {}
    draft_vis, _ = visible_all_pass(c0, task) if calls else (False, {})
    draft_ora = oracle_whole(c0, task) if calls and task.get("answerable", True) else False
    gated = _gating_ship(arm, calls, final, draft_docs or [draft], visible_pass)
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
        "draft_visible_pass": draft_vis,
        "draft_oracle_success": draft_ora,
        "draft_prompt_tokens": calls[0].prompt_tokens if calls else 0,
        "draft_completion_tokens": calls[0].completion_tokens if calls else 0,
        "draft_cpu_seconds": calls[0].latency_s if calls else 0.0,
        "gated_ship_exploratory": gated,
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
    ap.add_argument("--exclude-ids", type=Path, help="JSON list of task_ids to skip (pilot_excluded)")
    args = ap.parse_args()

    bank = json.loads(args.bank.read_text(encoding="utf-8"))
    if args.split == "all_holdout":
        ids = bank["split"]["holdout_answerable_ids"] + bank["split"]["holdout_unanswerable_ids"]
    else:
        ids = bank["split"][args.split]
    if args.exclude_ids and args.exclude_ids.is_file():
        ex = set(json.loads(args.exclude_ids.read_text(encoding="utf-8"))["task_ids"])
        ids = [i for i in ids if i not in ex]
    by_id = {t["task_id"]: t for t in bank["tasks"]}
    tasks = [by_id[i] for i in ids]
    if args.limit:
        tasks = tasks[: args.limit]

    lm = SmallLM(args.model)
    rng = random.Random(args.seed)
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]

    args.out.mkdir(parents=True, exist_ok=True)
    rows_path = args.out / "rows.jsonl"
    done: set[tuple[str, str]] = set()
    if rows_path.is_file():
        for line in rows_path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                done.add((r["task_id"], r["arm"]))
    n = 0
    with rows_path.open("a", encoding="utf-8") as fout:
        for task in tasks:
            for arm in arms:
                if (task["task_id"], arm) in done:
                    continue
                fn = ARM_FN[arm]
                row = fn(task, lm, rng)
                (args.out / f"{task['task_id']}__{arm}.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
                fout.write(json.dumps(row, ensure_ascii=False) + "\n")
                fout.flush()
                n += 1
                print(f"{task['task_id']} {arm} ora={row['oracle_whole_success']}", flush=True)
    total = sum(1 for _ in rows_path.open()) if rows_path.is_file() else n
    print(f"wrote {total} rows -> {args.out}")


if __name__ == "__main__":
    main()