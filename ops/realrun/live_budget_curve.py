#!/usr/bin/env python3
"""live_budget_curve.py — descriptive per-attempt budget breakdown of the
registered live resample rows (v4/v6 on qwen, v7 on gemma).

WHAT THIS IS
  The registered B_resample3 arm (visible-test-failure-driven clean resample,
  max 3 attempts) records `n_attempts` per cell. A cell accepted with
  n_attempts=K passed on its K-th clean draw (draws 1..K-1 failed the
  visible suite). This script decomposes the B-arm acceptance rate into
  "solved on draw 1 / draw 2 / draw 3" per registered batch, i.e. the
  live-row budget curve: cap K = at most K attempts.

WHAT THIS IS NOT
  - Descriptive only. No decision state, no p-value, no effect claim.
  - B's cap-1 is an independent single draw; it is NOT arm A (A is its own
    draws). The registered A-vs-B comparison is the McNemar row in
    prereg_analyze.py; this file only decomposes the B arm.
  - Batches are separate models/banks-of-draws: NOT pooled.
  - scorer_used=false for all three batches (polyglot_py: visible==grader).

Read-only. Zero model calls. Idempotent.

Usage:
  python3 live_budget_curve.py \
      --batch v4 --roots-group "r1 r2 r3" --meta "model=qwen/prereg_id=v4..." \
      --batch v6 --roots-group "r1 ... r5" \
      --batch v7 --roots-group "r1 ... r5" \
      --out live_budget_curve.json
  python3 live_budget_curve.py --selftest
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

SCHEMA = "vacant.realrun.live_budget_curve/1"


def load_cells(roots: list[str]) -> list[dict]:
    rows = []
    for root in roots:
        p = Path(root) / "progress.jsonl"
        if not p.exists():
            raise SystemExit(f"missing progress.jsonl in {root}")
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            r["rep_root"] = str(root)
            rows.append(r)
    return rows


def input_pins(roots: list[str]) -> list[dict]:
    """sha256 of every progress.jsonl the batch was computed from."""
    return [
        {
            "root": str(root),
            "progress_sha256": hashlib.sha256(
                (Path(root) / "progress.jsonl").read_bytes()
            ).hexdigest(),
        }
        for root in roots
    ]


def _pct(n: int, d: int) -> float:
    return round(100.0 * n / d, 2) if d else 0.0


def curve(batch: str, rows: list[dict], meta: dict) -> dict:
    a = [r for r in rows if r.get("arm") == "A_none"]
    b = [r for r in rows if r.get("arm") == "B_resample3"]
    voids = [r for r in rows if r.get("infra_void")]
    a = [r for r in a if not r.get("infra_void")]
    b = [r for r in b if not r.get("infra_void")]

    acc_a = sum(1 for r in a if r.get("accepted"))
    acc_by_attempt: dict[int, int] = {}
    rej_by_attempt: dict[int, int] = {}
    for r in b:
        k = int(r.get("n_attempts") or 1)
        if r.get("accepted"):
            acc_by_attempt[k] = acc_by_attempt.get(k, 0) + 1
        else:
            rej_by_attempt[k] = rej_by_attempt.get(k, 0) + 1

    max_k = max(list(acc_by_attempt) + list(rej_by_attempt) + [1])
    caps: dict[int, dict] = {}
    for k in range(1, max_k + 1):
        acc_le_k = sum(v for kk, v in acc_by_attempt.items() if kk <= k)
        caps[k] = {
            "accepted": acc_le_k,
            "n_cells": len(b),
            "pct": _pct(acc_le_k, len(b)),
        }
    margins_pp = {
        f"cap{k+1}_minus_cap{k}": _pct(
            caps[k + 1]["accepted"] - caps[k]["accepted"], len(b)
        )
        for k in range(1, max_k)
        if k + 1 in caps
    }
    return {
        "batch": batch,
        "roots": sorted({r["rep_root"] for r in rows}),
        "input": input_pins(sorted({r["rep_root"] for r in rows})),
        "n_reps": len({r["rep_root"] for r in rows}),
        "n_cells": len(rows),
        "n_voids_excluded": len(voids),
        "arm_a": {"n": len(a), "accepted": acc_a, "pct": _pct(acc_a, len(a))},
        "arm_b": {
            "n": len(b),
            "accepted": sum(acc_by_attempt.values()),
            "pct": _pct(sum(acc_by_attempt.values()), len(b)),
            "accepted_by_attempt": {str(k): v for k, v in sorted(acc_by_attempt.items())},
            "rejected_by_attempt": {str(k): v for k, v in sorted(rej_by_attempt.items())},
        },
        "caps": {str(k): v for k, v in sorted(caps.items())},
        "margins_pp": {k: v for k, v in sorted(margins_pp.items())},
        "descriptive_only": True,
        "decision_state": None,
        "scorer_used": False,
        "meta": meta,
    }


def selftest() -> int:
    ok = True

    def fail(msg: str) -> None:
        nonlocal ok
        ok = False
        print(f"FAIL: {msg}")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "rep1"
        root.mkdir()
        rows = [
            # A: t1 pass, t2 fail, t3 pass
            {"task": "t1", "arm": "A_none", "accepted": True, "n_attempts": 1, "infra_void": None},
            {"task": "t2", "arm": "A_none", "accepted": False, "n_attempts": 1, "infra_void": None},
            {"task": "t3", "arm": "A_none", "accepted": True, "n_attempts": 1, "infra_void": None},
            # B: t1 solved on draw 1; t2 solved on draw 3; t3 exhausted (3 fails)
            {"task": "t1", "arm": "B_resample3", "accepted": True, "n_attempts": 1, "infra_void": None},
            {"task": "t2", "arm": "B_resample3", "accepted": True, "n_attempts": 3, "infra_void": None},
            {"task": "t3", "arm": "B_resample3", "accepted": False, "n_attempts": 3, "infra_void": None},
            # infra void: excluded from denominators
            {"task": "t4", "arm": "B_resample3", "accepted": False, "n_attempts": 1,
             "infra_void": "model_call_failed"},
            {"task": "t4", "arm": "A_none", "accepted": False, "n_attempts": 1,
             "infra_void": "model_call_failed"},
        ]
        (root / "progress.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n"
        )
        got = curve("selftest", load_cells([str(root)]), {"note": "selftest"})
        exp = {
            ("arm_a", "n"): 3, ("arm_a", "accepted"): 2,
            ("arm_b", "n"): 3, ("arm_b", "accepted"): 2,
            ("caps", "1", "accepted"): 1, ("caps", "2", "accepted"): 1,
            ("caps", "3", "accepted"): 2,
        }
        for path, want in exp.items():
            node = got
            for k in path[:-1]:
                node = node[k]
            have = node[path[-1]]
            if have != want:
                fail(f"{'.'.join(map(str, path))} = {have!r}, want {want!r}")
        if got["n_voids_excluded"] != 2:
            fail(f"n_voids_excluded = {got['n_voids_excluded']!r}, want 2")
        m = got["margins_pp"]
        if m.get("cap3_minus_cap2") != round(100.0 / 3, 2):
            fail(f"margins cap3-cap2 = {m.get('cap3_minus_cap2')!r}, want {round(100/3,2)}")
        if m.get("cap2_minus_cap1") != 0.0:
            fail(f"margins cap2-cap1 = {m.get('cap2_minus_cap1')!r}, want 0.0")
        # monotonic caps
        if not (got["caps"]["1"]["pct"] <= got["caps"]["2"]["pct"] <= got["caps"]["3"]["pct"]):
            fail("caps not monotone")
        # no decision state, ever
        if got.get("decision_state") is not None or got.get("descriptive_only") is not True:
            fail("must be descriptive-only")

    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--batch", action="append", default=[],
                    help="batch label; pairs positionally with one --roots-group")
    ap.add_argument("--roots-group", action="append", default=[],
                    help="space-separated rep roots for the matching --batch")
    ap.add_argument("--meta", action="append", default=[],
                    help="optional comma-joined 'k=v' metadata for the matching --batch")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.batch:
        ap.error("need --batch/--roots-group (or --selftest)")
    if len(args.roots_group) != len(args.batch):
        ap.error(f"--roots-group count {len(args.roots_group)} != --batch count {len(args.batch)}")
    groups = [g.split() for g in args.roots_group]
    metas = [dict(kv.split("=", 1) for kv in m.split(",")) if m else {}
             for m in (args.meta or [""] * len(args.batch))]
    if len(metas) != len(args.batch):
        ap.error(f"--meta count {len(metas)} != --batch count {len(args.batch)}")
    out = {"schema": SCHEMA, "descriptive_only": True,
           "note": "per-attempt decomposition of the registered B_resample3 arm; "
                   "no decision state; batches not pooled; scorer_used=false",
           "batches": []}
    for i, (label, roots) in enumerate(zip(args.batch, groups)):
        out["batches"].append(curve(label, load_cells(roots), metas[i]))
    text = json.dumps(out, indent=1, ensure_ascii=False, sort_keys=False)
    if args.out:
        Path(args.out).write_text(text + "\n")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
