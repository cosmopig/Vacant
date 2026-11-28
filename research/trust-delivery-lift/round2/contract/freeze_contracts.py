#!/usr/bin/env python3
"""Freeze per-task contracts to disk BEFORE any online model run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from contract.filing_contract import compile_contract_independent, compile_contract_primary


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", type=Path, required=True)
    ap.add_argument("--subset", type=Path, default=None)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    qs = {q["id"]: q for q in load_jsonl(args.questions)}
    qids = list(qs)
    if args.subset and args.subset.is_file():
        qids = json.loads(args.subset.read_text())["question_ids"]
    args.out.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, str] = {}
    for qid in qids:
        q = qs[qid]
        primary = compile_contract_primary(q)
        independent = compile_contract_independent(q)
        (args.out / f"{qid}__primary.json").write_text(json.dumps(primary, indent=2), encoding="utf-8")
        (args.out / f"{qid}__independent.json").write_text(json.dumps(independent, indent=2), encoding="utf-8")
        manifest[qid] = primary["sha256"]
    (args.out / "MANIFEST_SHA256.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"froze {len(qids)} contracts -> {args.out}")


if __name__ == "__main__":
    main()