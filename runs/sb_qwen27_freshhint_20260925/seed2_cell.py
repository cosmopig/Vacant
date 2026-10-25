#!/usr/bin/env python3
"""lcb_3487 second-seed neutral-label control cell (round 26).

Background. Rounds 16 and 21 (presence_cell.py, name_cell.py) both rescued
lcb_3487 attempt 2 by delivering a 175-byte seeded-noise file as
VACANT_FEEDBACK.md — but BOTH cells used the SAME noise content (seed
20261024, sha256 6c9b58cf…, imported from presence_cell.py). The residual
confound named in round 21 (and kept in the ops backlog as the next step):

    "this content" vs "any extra content" — a second seed under the same
    neutral label must be run to separate the two.

This cell closes it: attempt 2 gets noise of a DIFFERENT seed (20261025),
SAME length (175 B), SAME neutral header ("## Note", via agent_qwen_neu.py),
SAME agent, scaffold, suite, argv and grading as the labelneu cell.

Outcomes (n=1 either way, stated as such; attribution only, no statistics):
  rescue  -> the specific bytes of the round-16/21 noise are NOT the driver;
             any extra prompt content breaks the deterministic no-delivery
             loop. Attribution: "prompt no longer a clean start" confirmed
             across two independent noise contents.
  no rescue -> the round-16/21 rescue was specific to that noise content
             (seed 20261024); "any extra content" is NOT established.

Single-factor claim (verifiable offline after the run): the a2 request bodies
of cells/lcb_3487__labelneu and cells/lcb_3487__seed2neu differ only in the
175 noise bytes embedded in the prompt; model/max_tokens/temperature/header/
task text are identical.

Self-test (no model calls; discriminating — a naive copy of name_cell.py
that reuses the seed-20261024 noise FAILS the sha256-distinct assertion):
  python3 seed2_cell.py selftest

Usage (one attempt per command; keeps each command under the 10-minute
limit and leaves a1 evidence behind if the round is cut):
  python3 seed2_cell.py a1   # clean origin; expect the same no-delivery signature
  python3 seed2_cell.py a2   # clean origin + SECOND-seed noise under the SAME neutral header
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

CELL = f"{TID}__seed2neu"
SUFFIX = "__seed2neu"

# Must match name_cell.py exactly: the label factor is held constant so that
# the ONLY factor differing from the labelneu cell is the noise content.
NEUTRAL_HEADER = "## Note"
AGENT = OUT / "agent_qwen_neu.py"

SEED2 = 20261025  # different from presence_cell's 20261024 — that is the point


def noise_size() -> int:
    import presence_cell
    return presence_cell.neutral_hint_bytes()


def noise_file_bytes(n: int) -> bytes:
    """n bytes of seeded random ASCII letters/digits, seed SEED2.

    Same alphabet and length as the round-16/21 noise, different seed —
    so the bytes are (with overwhelming probability) different content.
    """
    import random
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(random.Random(SEED2).choices(alphabet, k=n)).encode("ascii")


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
    print(f"[seed2neu {tag}] rc={rc} wall={wall}s", flush=True)
    return {"rc": rc, "wall_s": wall,
            "stdout_tail": proc.stdout[-400:], "stderr_tail": proc.stderr[-400:]}


def log_path(cell: pathlib.Path) -> pathlib.Path:
    return cell / "seed2neu_cell_log.json"


def load_log(cell: pathlib.Path) -> dict:
    p = log_path(cell)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    import presence_cell
    n = presence_cell.neutral_hint_bytes()
    seed1_sha = hashlib.sha256(presence_cell.noise_file_bytes(n)).hexdigest()
    return {"cell": CELL,
            "arm": "second-seed neutral-label control: resample + 175B noise, "
                   f"seed {SEED2} (labelneu/presence used seed 20261024, "
                   f"sha256 {seed1_sha[:16]}…), SAME neutral header "
                   f"{NEUTRAL_HEADER!r}",
            "agent": "agent_qwen_neu.py (byte-identical to agent_qwen.py except "
                     "the one header line; file name never reaches the model)",
            "agent_sha256": hashlib.sha256(AGENT.read_bytes()).hexdigest(),
            "header_label": NEUTRAL_HEADER,
            "noise_seed": SEED2,
            "max_tokens": os.environ.get("VACANT_SB_MAX_TOKENS", "32768")}


def save_log(cell: pathlib.Path, log: dict) -> None:
    log_path(cell).write_text(
        json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")


def selftest() -> int:
    """Offline checks (no model calls).

    The sha256-distinct assertion is the discriminating one: a naive copy of
    name_cell.py (which imports presence_cell's noise) fails it.
    """
    import presence_cell
    import name_cell
    n = presence_cell.neutral_hint_bytes()
    noise2 = noise_file_bytes(n)
    noise1 = presence_cell.noise_file_bytes(n)
    checks = [
        ("noise size matches the 175B of round 16/21",
         len(noise2) == n, f"{len(noise2)} vs {n}"),
        ("noise bytes are pure ASCII letters/digits (no words, no structure)",
         noise2.decode("ascii").isalnum(), "non-alnum bytes present"),
        ("noise sha256 DIFFERS from the seed-20261024 noise (the point of this cell)",
         hashlib.sha256(noise2).hexdigest() != hashlib.sha256(noise1).hexdigest(),
         "sha256 identical to round 16/21 noise — same content, not a second seed"),
        ("neutral header identical to the labelneu cell",
         NEUTRAL_HEADER == name_cell.NEUTRAL_HEADER,
         f"{NEUTRAL_HEADER!r} vs {name_cell.NEUTRAL_HEADER!r}"),
        ("same neutral-label agent variant as the labelneu cell",
         AGENT == name_cell.AGENT, f"{AGENT} vs {name_cell.AGENT}"),
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
        noise = noise_file_bytes(noise_size())
        (ws / "VACANT_FEEDBACK.md").write_bytes(noise)  # same name: invisible to
        # the model; only the CONTENT differs from the labelneu cell
        fb = (ws / "VACANT_FEEDBACK.md").read_bytes()
        assert fb == noise
        log["feedback_redelivered"] = {
            "path": "VACANT_FEEDBACK.md", "bytes": len(fb),
            "sha256": hashlib.sha256(fb).hexdigest(),
            "noise_seed": SEED2,
            "header_label": NEUTRAL_HEADER}
        log["attempt2"] = run_attempt(cell, ws, "a2")
        log["rc"] = log["attempt2"]["rc"]

    sol = (OUT / "ws" / CELL) / "solution.py"
    if sol.exists():
        shutil.copy(sol, cell / "final_solution.py")
    save_log(cell, log)
    print(f"[seed2neu {tag}] final rc={log.get('rc', 'n/a')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
