#!/usr/bin/env python3
"""Run equal-budget delivery-lift experiment."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arms import ARMS, SYSTEM, build_call1_user, build_call2_user, frozen_correct_fields, merge_delivery, parse_delivery
from backends import CallResult, ChatBackend, StubBackend, TransformersBackend
from scorer import assert_scorer_controls, grade_task


def _visible_grade(task: dict[str, Any], delivery: dict[str, str]) -> dict[str, Any]:
    g = grade_task(task, delivery)
  # Drop hidden signal from feedback path: rebuild visible flags only.
    for fr in g["fields"]:
        if not fr["visible_ok"]:
            pass
    return g


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_bank(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def select_tasks(bank: dict[str, Any], split: str) -> list[dict[str, Any]]:
    ids = bank["split"][split]
    by_id = {t["task_id"]: t for t in bank["tasks"]}
    return [by_id[i] for i in ids]


def run_task(
    task: dict[str, Any],
    arm: str,
    backend: ChatBackend,
    rng: random.Random,
    *,
    upfront_call1: bool,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    calls: list[dict[str, Any]] = []

    c1_user = build_call1_user(task, upfront=(upfront_call1 or arm == "UPFRONT"))
    r1: CallResult = backend.complete(SYSTEM, c1_user)
    calls.append({"phase": "call1", "arm": arm, **r1.__dict__})
    draft = parse_delivery(r1.text)

    vis0 = _visible_grade(task, draft)
    c2_user = build_call2_user(task, arm, r1.text, rng=rng, visible_grade=vis0)
    r2: CallResult = backend.complete(SYSTEM, c2_user)
    calls.append({"phase": "call2", "arm": arm, **r2.__dict__})

    new = parse_delivery(r2.text)
    if arm in ("BLANKS", "EVR", "RAND"):
        frozen = frozen_correct_fields(vis0)
        final = merge_delivery(draft, new, frozen)
    else:
        final = new if new else draft

    g0 = grade_task(task, draft)
    g1 = grade_task(task, final)
    elapsed = time.perf_counter() - t0
    pt = sum(c["prompt_tokens"] for c in calls)
    ct = sum(c["completion_tokens"] for c in calls)

    return {
        "task_id": task["task_id"],
        "arm": arm,
        "draft": draft,
        "final": final,
        "grade_draft": g0,
        "grade_final": g1,
        "whole_success_draft": g0["whole_success"],
        "whole_success_final": g1["whole_success"],
        "calls": calls,
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "latency_s": elapsed,
    }


def run_batch(
    tasks: list[dict[str, Any]],
    arms: list[str],
    backend: ChatBackend,
    seed: int,
    out_dir: Path,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    rows = []
    for task in tasks:
        for arm in arms:
            row = run_task(task, arm, backend, rng, upfront_call1=(arm == "UPFRONT"))
            rows.append(row)
            (out_dir / f"{task['task_id']}__{arm}.json").write_text(
                json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8"
            )
    manifest = {
        "schema": "vacant.trust_delivery_lift.run/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "n_tasks": len(tasks),
        "arms": arms,
        "rows": rows,
    }
    out = out_dir / "rows.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", type=Path, default=Path(__file__).parent / "tasks_bank.json")
    ap.add_argument("--split", choices=("pilot_ids", "confirm_ids"), default="pilot_ids")
    ap.add_argument("--arms", default="KEEP,BLIND,BLANKS,EVR,RAND")
    ap.add_argument("--backend", choices=("stub", "qwen0.5b"), default="qwen0.5b")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--selftest-scorer", action="store_true")
    args = ap.parse_args()

    if args.selftest_scorer:
        assert_scorer_controls()
        print("scorer controls: OK")
        return

    if not args.out:
        ap.error("--out is required unless --selftest-scorer")
    bank = load_bank(args.bank)
    tasks = select_tasks(bank, args.split)
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]

    if args.backend == "stub":
        backend: ChatBackend = StubBackend()
    else:
        backend = TransformersBackend()

    run_batch(tasks, arms, backend, args.seed, args.out)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()