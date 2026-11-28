#!/usr/bin/env python3
"""One shared call-1 draft per task (paired arms)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from arms import SYSTEM, build_call1_user, parse_delivery
from backends import StubBackend, TransformersBackend
from harness import load_bank, select_tasks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", type=Path, default=Path(__file__).parent / "tasks_bank.json")
    ap.add_argument("--split", default="pilot_ids")
    ap.add_argument("--backend", choices=("stub", "qwen0.5b"), default="qwen0.5b")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    bank = load_bank(args.bank)
    tasks = select_tasks(bank, args.split)
    backend = StubBackend() if args.backend == "stub" else TransformersBackend()

    rows = []
    for task in tasks:
        r = backend.complete(SYSTEM, build_call1_user(task, upfront=False))
        draft = parse_delivery(r.text)
        rows.append(
            {
                "task_id": task["task_id"],
                "draft": draft,
                "raw_call1": r.text,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
            }
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} drafts -> {args.out}")


if __name__ == "__main__":
    main()