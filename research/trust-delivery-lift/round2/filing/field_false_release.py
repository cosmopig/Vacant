#!/usr/bin/env python3
"""Per-question false-release (delivered & oracle wrong) vs BLIND with cost."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--compare", default="BLIND,PLAIN,TYPED_REFUSE")
    args = ap.parse_args()
    rows = load_jsonl(args.rows)
    arms = [a.strip() for a in args.compare.split(",")]
    by_arm: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["arm"] in arms:
            by_arm[r["arm"]].append(r)

    out: dict = {}
    for arm, rs in sorted(by_arm.items()):
        n_del = sum(1 for r in rs if r.get("delivered"))
        n_wrong = sum(1 for r in rs if r.get("delivered") and not r.get("oracle_ok"))
        out[arm] = {
            "n_questions": len(rs),
            "n_delivered": n_del,
            "n_false_release": n_wrong,
            "false_release_rate_among_delivered": n_wrong / n_del if n_del else 0,
            "mean_cpu_s": sum(r.get("cpu_seconds", 0) for r in rs) / len(rs) if rs else 0,
            "mean_tokens": sum(r.get("prompt_tokens", 0) + r.get("completion_tokens", 0) for r in rs)
            / len(rs)
            if rs
            else 0,
            "mean_calls": sum(r.get("n_calls", 0) for r in rs) / len(rs) if rs else 0,
        }
    args.out.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()