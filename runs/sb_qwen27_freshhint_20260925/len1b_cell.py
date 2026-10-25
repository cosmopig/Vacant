#!/usr/bin/env python3
"""lcb_3487 length-variant control cell (round 31).

Background. Five a2 cells rescued lcb_3487 (fresh_hint 275 B detail,
neutral sentence 175 B, noise seed 20261024 175 B ×2 labels, noise seed
20261025 175 B) while the content-free resample a2 did not. Round 26
closed "this content vs any content" (two independent noise bytes) and
named the residual confound:

    body length (175 B; fresh_hint 275 B) and the alphanumeric alphabet
    are held constant across all five rescued cells, so they are not
    separated from "content exists". A length-variant cell is the
    natural next control.

This cell closes it at the minimum boundary: attempt 2 gets a **1-byte**
feedback body ("x") under the SAME neutral header ("## Note", via
agent_qwen_neu.py), same agent, scaffold, suite, argv and grading as the
seed2neu cell. The prompt diff versus the clean-start prompt is the
entire feedback section: "## Note\\n\\nx\\n\\n" (12 bytes) — the
smallest possible "content exists" case.

Outcomes (n=1 either way, stated as such; attribution only, no statistics):
  rescue  -> "any extra prompt content" holds even at the minimum
             boundary (12-byte section); the demonstrated factor is
             "the prompt is no longer a clean start", independent of
             content length across 1 B … 275 B.
  no rescue -> the effect requires a minimum content length; "any extra
             content" is NOT established; the demonstrated factor is
             "substantial content" (>=175 B in this evidence set).

Single-factor claim (verifiable offline after the run): the a2 request
bodies of cells/lcb_3487__seed2neu and cells/lcb_3487__len1b differ only
in the feedback section (175 noise bytes vs the single byte "x");
model/max_tokens/temperature/header label/task text are identical.

Self-test (no model calls; discriminating — a naive copy of seed2_cell.py
that reuses the 175 B noise FAILS the length assertion):
  python3 len1b_cell.py selftest

Usage (one attempt per command; keeps each command under the 10-minute
limit and leaves a1 evidence behind if the round is cut):
  python3 len1b_cell.py a1   # clean origin; expect the same no-delivery signature
  python3 len1b_cell.py a2   # clean origin + 1-byte body under the SAME neutral header
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[2]
PY = sys.executable
VACANT = REPO / ".venv" / "bin" / "vacant"
OUT = REPO / "runs" / "sb_qwen27_freshhint_20260925"
TID = os.environ.get("SB_TID", "lcb_3487")
UPSTREAM = os.environ.get("SB_UPSTREAM", "http://100.119.113.56:1234")

CELL = f"{TID}__len1b"
SUFFIX = "__len1b"

# Must match name_cell.py / seed2_cell.py exactly: label held constant, so
# the ONLY factor differing from the seed2neu cell is the body length.
NEUTRAL_HEADER = "## Note"
AGENT = OUT / "agent_qwen_neu.py"

BODY = b"x"  # 1 byte — the minimum possible non-empty feedback body


def scaffold() -> pathlib.Path:
    """Clean origin: exactly the ws the other arms started from (TASK.md only)."""
    ws = OUT / "ws" / CELL
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    t = json.loads((OUT / "tasks" / f"{TID}.json").read_text(encoding="utf-8"))
    import make_batch
    (ws / "TASK.md").write_text(make_batch.task_md(t), encoding="utf-8")
    return ws


def run_attempt(cell: pathlib.Path, ws: pathlib.Path, tag: str) -> dict:
    cmd = [str(VACANT), "run",
           "--workspace", str(ws),
           "--run-dir", str(cell),
           "--suite", str(OUT / "suites" / TID),
           "--task-id", f"sb_qwen27_{TID}{SUFFIX}",
           "--", str(PY), str(AGENT)]
    env = dict(os.environ)
    env["VACANT_RUN_UPSTREAM_OPENAI"] = UPSTREAM
    env.setdefault("VACANT_SB_MODEL", "qwen/qwen3.8-27b")
    t0 = time.time()
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True,
                          timeout=1800)
    rc = proc.returncode
    wall = round(time.time() - t0, 1)
    print(f"[len1b {tag}] rc={rc} wall={wall}s", flush=True)
    return {"rc": rc, "wall_s": wall,
            "stdout_tail": proc.stdout[-400:], "stderr_tail": proc.stderr[-400:]}


def log_path(cell: pathlib.Path) -> pathlib.Path:
    return cell / "len1b_cell_log.json"


def load_log(cell: pathlib.Path) -> dict:
    p = log_path(cell)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    import presence_cell
    import seed2_cell
    n = presence_cell.neutral_hint_bytes()
    return {"cell": CELL,
            "arm": "length-variant control: resample + 1-byte body under the "
                   f"SAME neutral header {NEUTRAL_HEADER!r} (labelneu/presence/"
                   "seed2neu used 175 B; fresh_hint 275 B)",
            "agent": "agent_qwen_neu.py (byte-identical to agent_qwen.py except "
                     "the one header line; file name never reaches the model)",
            "agent_sha256": hashlib.sha256(AGENT.read_bytes()).hexdigest(),
            "header_label": NEUTRAL_HEADER,
            "body_bytes": len(BODY),
            "body_sha256": hashlib.sha256(BODY).hexdigest(),
            "reference_lengths": {
                "fresh_hint_detail": 275,
                "neutral_sentence": n,
                "noise_seed_20261024": n,
                "noise_seed_20261025": n},
            "reference_sha256": {
                "noise_seed_20261024":
                    hashlib.sha256(presence_cell.noise_file_bytes(n)).hexdigest(),
                "noise_seed_20261025":
                    hashlib.sha256(seed2_cell.noise_file_bytes(n)).hexdigest()},
            "max_tokens": os.environ.get("VACANT_SB_MAX_TOKENS", "32768")}


def save_log(cell: pathlib.Path, log: dict) -> None:
    log_path(cell).write_text(
        json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")


def selftest() -> int:
    """Offline checks (no model calls).

    The length assertion is the discriminating one: a naive copy of
    seed2_cell.py (which reuses the 175 B noise) fails it.
    """
    import presence_cell
    import name_cell
    import seed2_cell
    n = presence_cell.neutral_hint_bytes()
    checks = [
        ("body is exactly 1 byte (the point of this cell)",
         len(BODY) == 1, f"{len(BODY)} bytes"),
        ("body length differs from BOTH prior noise lengths (no reuse)",
         len(BODY) != n and len(BODY) != len(seed2_cell.noise_file_bytes(n)),
         f"{len(BODY)} B equals the 175 B noise length — same shape, not a length variant"),
        ("neutral header identical to the labelneu/seed2neu cells",
         NEUTRAL_HEADER == name_cell.NEUTRAL_HEADER
         and NEUTRAL_HEADER == seed2_cell.NEUTRAL_HEADER,
         f"{NEUTRAL_HEADER!r} mismatch"),
        ("same neutral-label agent variant as the labelneu/seed2neu cells",
         AGENT == name_cell.AGENT == seed2_cell.AGENT,
         f"{AGENT} mismatch"),
    ]
    ok = True
    for name, passed, detail in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}"
              + ("" if passed else f"  ({detail})"))
        ok = ok and passed
    print("selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("a1", "a2", "selftest"):
        print(__doc__)
        return 2
    tag = sys.argv[1]
    if tag == "selftest":
        return selftest()
    cell = OUT / "cells" / CELL
    cell.mkdir(parents=True, exist_ok=True)
    log = load_log(cell)

    if tag == "a1":
        ws = scaffold()
        log["attempt1"] = run_attempt(cell, ws, "a1")
    else:
        ws = scaffold()
        (ws / "VACANT_FEEDBACK.md").write_bytes(BODY)
        fb = (ws / "VACANT_FEEDBACK.md").read_bytes()
        assert fb == BODY
        log["feedback_redelivered"] = {
            "path": "VACANT_FEEDBACK.md", "bytes": len(fb),
            "sha256": hashlib.sha256(fb).hexdigest(),
            "header_label": NEUTRAL_HEADER}
        log["attempt2"] = run_attempt(cell, ws, "a2")
        log["rc"] = log["attempt2"]["rc"]

    sol = (OUT / "ws" / CELL) / "solution.py"
    if sol.exists():
        shutil.copy(sol, cell / "final_solution.py")
    save_log(cell, log)
    print(f"[len1b {tag}] final rc={log.get('rc', 'n/a')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
