#!/usr/bin/env python3
"""hint_diagnostic_loss.py — measure diagnostic-tail loss in v5 fresh_hint delivery.

Background
----------
The v5 prereg (prereg_v5.json) registered C_fresh_hint3 as the treatment arm.
The delivery audit (audit_v5_hint_delivery.json, all 204 cells pass) confirms the
hint was on the wire, byte-exact. This script asks a further question:

  Of the diagnostic content available in the original failure text
  (test name, error type+message, assertion values), how much survived
  into the delivered hint?

This is a descriptive measurement of a delivery/mechanics defect, not a
new analysis or a change to the v5 verdict. It motivates the v6 prereg.

Checks
------
L1  For every treatment-arm cell with a delivered hint (feedback.text present),
    extract diagnostic fragments from the original failures string:
      - failing test name (test_xxx)
      - error type + message (e.g., "AssertionError: 'X' != ''")
      - assertion values (e.g., "'X' != ''")
L2  Check whether each fragment is present verbatim in the delivered hint.
L3  Classify: "kept" (all fragments present) vs "lost_tail" (any fragment missing).
L4  Report per-cell details and aggregate counts.

Exit codes: 0 = ran OK (regardless of loss count), 1 = anomaly (e.g., no data),
            2 = usage/read error.

Usage:
  python hint_diagnostic_loss.py --selftest
  python hint_diagnostic_loss.py --roots runs_v5_r1 runs_v5_r2 runs_v5_r3
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent  # ~/dev/Vacant
OPS = REPO.parent / "realrun"  # ~/dev/ops/realrun

SCHEMA = "vacant.audit/v5_hint_diagnostic_loss/1"
ARM = "C_fresh_hint3"

# Diagnostic fragment patterns
RE_TEST_NAME = re.compile(r"in (test_[a-z0-9_]+)")
RE_ERROR = re.compile(r"(\w+Error: .+)")
RE_ASSERT_VALS = re.compile(r"([\"'][^\"']*[\"']\s*[!=<>]+\s*[\"'][^\"']*[\"'])")


def extract_fragments(failures: str) -> list[str]:
    """Extract diagnostic fragments from the original failure text.

    The failure text uses ' | ' as a separator between traceback segments.
    We split on that first, then extract from each segment.
    """
    segments = [s.strip() for s in failures.split(" | ") if s.strip()]
    frags: list[str] = []
    seen: set[str] = set()

    def _add(frag: str) -> None:
        frag = frag.strip()
        if frag and frag not in seen and len(frag) >= 4:
            seen.add(frag)
            frags.append(frag)

    for seg in segments:
        # Test name: "in test_xxx" pattern
        for m in RE_TEST_NAME.finditer(seg):
            _add(m.group(1))
        # Error type + message: e.g., "AssertionError: 'X' != ''"
        for m in RE_ERROR.finditer(seg):
            _add(m.group(1))
        # Assertion values: e.g., "'X' != ''"
        for m in RE_ASSERT_VALS.finditer(seg):
            _add(m.group(1))

    return frags


def check_hint(failures: str, hint: str) -> dict:
    """Check which diagnostic fragments survived into the hint."""
    frags = extract_fragments(failures)
    results = []
    for f in frags:
        present = f in hint
        results.append({"fragment": f, "present": present})
    kept = all(r["present"] for r in results) if results else True
    return {
        "n_fragments": len(frags),
        "fragments": results,
        "kept": kept,
        "lost_tail": not kept,
    }


def audit_root(root: Path) -> dict:
    """Audit one run root."""
    cells = {}
    for jf in sorted((root / ARM).glob("*/run/run_RUN-ON.json")):
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"WARN: cannot read {jf}: {exc}", file=sys.stderr)
            continue
        task = jf.parent.parent.name  # runs_v5_rX/C_fresh_hint3/<task>/run/
        for i, att in enumerate(data.get("attempts", [])):
            fb = att.get("feedback") or {}
            hint = fb.get("text")
            if not hint:
                continue
            failures = att.get("failures", "")
            if not failures:
                continue
            result = check_hint(failures, hint)
            cells.setdefault(task, []).append({
                "attempt": att.get("attempt", i + 1),
                **result,
            })
    return {"root": str(root), "cells": cells, "n_cells": len(cells)}


def selftest() -> int:
    """Self-test with synthetic data."""
    # Case 1: hint that KEEPS the diagnostic tail
    failures_good = (
        "test_visible.py::check — assert: 2/5 failed. first: "
        "Traceback (most recent call last): | File \"x.py\", line 10, in test_foo | "
        "AssertionError: 'a' != 'b' | - a"
    )
    hint_good = (
        "Previous attempt failed acceptance check:\n"
        "test_foo\n"
        "AssertionError: 'a' != 'b'\n"
        "Avoid this failure."
    )
    r = check_hint(failures_good, hint_good)
    assert r["kept"], f"expected kept, got {r}"
    assert r["n_fragments"] >= 2, f"expected >=2 fragments, got {r['n_fragments']}"

    # Case 2: hint that LOSES the diagnostic tail (the v5 defect)
    failures_bad = failures_good
    hint_bad = (
        "Previous attempt failed acceptance check:\n"
        "test_visible.py::check — assert: 2/5 failed. first: Traceback (most\n"
        "Avoid this failure."
    )
    r2 = check_hint(failures_bad, hint_bad)
    assert r2["lost_tail"], f"expected lost_tail, got {r2}"

    # Case 3: empty failures → no fragments → kept (vacuously)
    r3 = check_hint("", "some hint")
    assert r3["kept"], f"empty failures should be kept, got {r3}"

    print("selftest: PASS (3/3)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true", help="run synthetic self-test and exit")
    ap.add_argument("--roots", nargs="*", default=None, help="run root directories")
    ap.add_argument("--out", default=None, help="output mirror JSON path")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    roots = args.roots
    if roots is None:
        roots = [str(OPS / f"runs_v5_r{i}") for i in (1, 2, 3)]

    per_root = []
    total_kept = 0
    total_lost = 0
    total_hints = 0

    for root_s in roots:
        root = Path(root_s)
        if not root.is_dir():
            print(f"ERROR: root not found: {root}", file=sys.stderr)
            return 2
        audit = audit_root(root)
        per_root.append(audit)
        for task, hints in audit["cells"].items():
            for h in hints:
                total_hints += 1
                if h["kept"]:
                    total_kept += 1
                else:
                    total_lost += 1

    summary = {
        "schema": SCHEMA,
        "arm": ARM,
        "roots": roots,
        "n_hints": total_hints,
        "kept": total_kept,
        "lost_tail": total_lost,
        "loss_rate": round(total_lost / total_hints, 4) if total_hints else None,
        "purpose": "descriptive measurement of diagnostic-tail loss in v5 fresh_hint; "
                   "boundary condition for the UNRESOLVED verdict; motivates v6 prereg",
        "out_of_prereg": True,
        "decision_state": None,
        "per_root": per_root,
    }

    out_path = Path(args.out) if args.out else REPO / "ops" / "realrun" / "hint_diagnostic_loss.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"hints audited: {total_hints}")
    print(f"kept diagnostic tail: {total_kept}")
    print(f"lost diagnostic tail: {total_lost}")
    if total_hints:
        print(f"loss rate: {total_lost/total_hints:.1%}")
    print(f"mirror: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
