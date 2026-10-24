#!/usr/bin/env python3
"""lcb_3487 pure-presence control cell (round 15).

Question (the residual confound named in round 13): the neutral-hint cell
showed a RESCUE with a file that says "Previous attempt did not pass visible
test assertions" (no failure detail). That cell still mixes two factors:
  (i) a file is present in the workspace at attempt 2, and
  (ii) the file says something about the previous attempt.

This cell isolates (i): attempt 2 gets a file of the SAME size as the
neutral hint, but with no task-relevant or failure-relevant content at all
(seeded random ASCII, sha256 recorded). Delivery point, file name, argv,
scaffold and grading are identical to neutral_cell.py.

Outcomes:
  rescue  -> mere presence (any content, even noise) breaks the
             deterministic no-delivery loop; the failure signal is not needed
  no      -> the "previous attempt failed acceptance" message itself is what
             carries the effect; noise is not enough

Each attempt is a plain `vacant run --retry none` invocation, argv
byte-identical to the other arms; only the workspace file differs.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import random
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


def neutral_hint_bytes() -> int:
    from neutral_cell import NEUTRAL_HINT
    return len(NEUTRAL_HINT.encode("utf-8"))


def noise_file_bytes(n: int) -> bytes:
    """n bytes of seeded random ASCII letters/digits: no words, no structure,
    no task or failure relevance. Deterministic; sha256 is logged."""
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(random.Random(20261024).choices(alphabet, k=n)).encode("ascii")


def scaffold() -> pathlib.Path:
    """Clean origin: exactly the ws the other arms started from (TASK.md only)."""
    ws = OUT / "ws" / f"{TID}__presence"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    t = json.loads((OUT / "tasks" / f"{TID}.json").read_text(encoding="utf-8"))
    import make_batch
    (ws / "TASK.md").write_text(make_batch.task_md(t), encoding="utf-8")
    return ws


def run_attempt(cell: pathlib.Path, ws: pathlib.Path) -> tuple[int, float, str, str]:
    cmd = [str(VACANT), "run",
           "--workspace", str(ws),
           "--run-dir", str(cell),
           "--suite", str(OUT / "suites" / TID),
           "--task-id", f"sb_qwen27_{TID}__presence",
           "--", str(PY), str(OUT / "agent_qwen.py")]
    env = dict(os.environ)
    env["VACANT_RUN_UPSTREAM_OPENAI"] = UPSTREAM
    env.setdefault("VACANT_SB_MODEL", "qwen/qwen3.8-27b")
    t0 = time.time()
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True,
                          timeout=1800)
    return proc.returncode, round(time.time() - t0, 1), proc.stdout, proc.stderr


def main() -> int:
    cell = OUT / "cells" / f"{TID}__presence"
    if cell.exists():
        shutil.rmtree(cell)
    cell.mkdir(parents=True)
    n = neutral_hint_bytes()
    noise = noise_file_bytes(n)
    log = {"cell": f"{TID}__presence",
           "arm": "presence (control: resample + meaningless same-size file)",
           "noise_bytes": noise.decode("ascii"),
           "noise_sha256": hashlib.sha256(noise).hexdigest(),
           "size_matched_to_neutral_hint": n,
           "agent_sha256": hashlib.sha256(
               (OUT / "agent_qwen.py").read_bytes()).hexdigest(),
           "max_tokens": os.environ.get("VACANT_SB_MAX_TOKENS", "32768")}

    ws = scaffold()
    rc1, w1, so1, se1 = run_attempt(cell, ws)
    log["attempt1"] = {"rc": rc1, "wall_s": w1,
                       "stdout_tail": so1[-400:], "stderr_tail": se1[-400:]}
    print(f"[presence a1] rc={rc1} wall={w1}s", flush=True)

    if rc1 != 0:
        # Restore the clean origin, then deliver the NOISE file — same file
        # name, same delivery point, same size, zero task/failure content.
        ws = scaffold()
        (ws / "VACANT_FEEDBACK.md").write_bytes(noise)
        fb = (ws / "VACANT_FEEDBACK.md").read_bytes()
        assert fb == noise
        log["feedback_redelivered"] = {"path": "VACANT_FEEDBACK.md",
                                       "bytes": len(fb),
                                       "sha256": hashlib.sha256(fb).hexdigest()}
        rc2, w2, so2, se2 = run_attempt(cell, ws)
        log["attempt2"] = {"rc": rc2, "wall_s": w2,
                           "stdout_tail": so2[-400:], "stderr_tail": se2[-400:]}
        print(f"[presence a2] rc={rc2} wall={w2}s", flush=True)
        log["rc"] = rc2
    else:
        log["attempt2"] = None
        log["rc"] = rc1

    sol = (OUT / "ws" / f"{TID}__presence") / "solution.py"
    if sol.exists():
        shutil.copy(sol, cell / "final_solution.py")
    (cell / "presence_cell_log.json").write_text(
        json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[presence] final rc={log['rc']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
