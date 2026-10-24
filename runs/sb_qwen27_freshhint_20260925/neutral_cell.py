#!/usr/bin/env python3
"""Neutral-hint control cell (2026-10-24, round 13) — decompose the lcb_3487 rescue.

The v2 batch showed fresh_hint rescuing lcb_3487 on attempt 2 while `none` and
`resample` produced no deliverable at all (rc=3, finish_reason=length). That
confounds two variables that both changed between the failing attempts and the
rescuing one:

  (a) the workspace contained a VACANT_FEEDBACK.md file at all (the retry nudge)
  (b) that file named the actual failure (ModuleNotFoundError: 'solution')

This cell adds the missing arm: clean resample + a feedback file of the SAME
SHAPE that carries NO failure detail (the neutral sentence is the exact
fallback line of `retry.render_fresh_hint`). Nothing arm-specific beyond the
file content; the agent, suite, bank row and invocation are byte-identical to
the other arms (each attempt is a plain `vacant run --retry none` invocation).

Outcome reading (n=1 cell — no statistical claim, this is attribution only):
  - neutral a2 passes  -> the nudge/presence is sufficient here; the specific
                          failure detail is NOT demonstrated to be the driver.
  - neutral a2 no-deliverable (like none/resample a2) -> the specific signal
                          ("no module named 'solution'") is what carried a2,
                          i.e. the real acceptance signal drove the rescue.

Usage:
  python3 neutral_cell.py            # default: lcb_3487
  SB_TID=lcb_3487 python3 neutral_cell.py
"""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

REPO = pathlib.Path(os.environ.get("VACANT_REPO", "/home/user1/dev/Vacant"))
PY = REPO / ".venv" / "bin" / "python"
VACANT = REPO / ".venv" / "bin" / "vacant"
OUT = REPO / "runs" / "sb_qwen27_freshhint_20260925"
TID = os.environ.get("SB_TID", "lcb_3487")
UPSTREAM = os.environ.get("SB_UPSTREAM", "http://100.119.113.56:1234")

#: Same header/footer/shape as retry.render_fresh_hint; the body is its own
#: neutral fallback sentence, verbatim. No failure detail, no test data.
NEUTRAL_HINT = (
    "<!-- Attempt 1 failed; workspace restored to clean origin -->\n"
    "Previous attempt did not pass visible test assertions.\n"
    "Avoid repeating that failure in your clean implementation."
)


def scaffold() -> pathlib.Path:
    """Clean origin: exactly the ws the other arms started from (TASK.md only)."""
    ws = OUT / "ws" / f"{TID}__neutral_hint"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    t = json.loads((OUT / "tasks" / f"{TID}.json").read_text(encoding="utf-8"))
    # Reuse make_batch.task_md so TASK.md is byte-identical to the other arms.
    import make_batch
    (ws / "TASK.md").write_text(make_batch.task_md(t), encoding="utf-8")
    return ws


def run_attempt(cell: pathlib.Path, ws: pathlib.Path) -> tuple[int, float, str, str]:
    cmd = [str(VACANT), "run",
           "--workspace", str(ws),
           "--run-dir", str(cell),
           "--suite", str(OUT / "suites" / TID),
           "--task-id", f"sb_qwen27_{TID}__neutral_hint",
           "--", str(PY), str(OUT / "agent_qwen.py")]
    env = dict(os.environ)
    env["VACANT_RUN_UPSTREAM_OPENAI"] = UPSTREAM
    env.setdefault("VACANT_SB_MODEL", "qwen/qwen3.8-27b")
    t0 = time.time()
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True,
                          timeout=1800)
    return proc.returncode, round(time.time() - t0, 1), proc.stdout, proc.stderr


def main() -> int:
    cell = OUT / "cells" / f"{TID}__neutral_hint"
    if cell.exists():
        shutil.rmtree(cell)
    cell.mkdir(parents=True)
    log = {"cell": f"{TID}__neutral_hint",
           "arm": "neutral_hint (control: resample + no-detail feedback file)",
           "neutral_hint": NEUTRAL_HINT,
           "agent_sha256": hashlib.sha256(
               (OUT / "agent_qwen.py").read_bytes()).hexdigest(),
           "max_tokens": os.environ.get("VACANT_SB_MAX_TOKENS", "32768")}

    ws = scaffold()
    log["ws_origin_sha256"] = None
    rc1, w1, so1, se1 = run_attempt(cell, ws)
    log["attempt1"] = {"rc": rc1, "wall_s": w1,
                       "stdout_tail": so1[-400:], "stderr_tail": se1[-400:]}
    print(f"[neutral a1] rc={rc1} wall={w1}s", flush=True)

    if rc1 != 0:
        # Restore the clean origin (a1 left no deliverable or a partial one),
        # then deliver the NEUTRAL file — same delivery point as fresh_hint's
        # hint_redelivered, same file name, different content.
        ws = scaffold()
        (ws / "VACANT_FEEDBACK.md").write_text(NEUTRAL_HINT, encoding="utf-8")
        fb = (ws / "VACANT_FEEDBACK.md").read_bytes()
        log["feedback_redelivered"] = {"path": "VACANT_FEEDBACK.md",
                                       "bytes": len(fb),
                                       "sha256": hashlib.sha256(fb).hexdigest()}
        rc2, w2, so2, se2 = run_attempt(cell, ws)
        log["attempt2"] = {"rc": rc2, "wall_s": w2,
                           "stdout_tail": so2[-400:], "stderr_tail": se2[-400:]}
        print(f"[neutral a2] rc={rc2} wall={w2}s", flush=True)
        log["rc"] = rc2
    else:
        log["attempt2"] = None
        log["rc"] = rc1

    sol = (OUT / "ws" / f"{TID}__neutral_hint") / "solution.py"
    if sol.exists():
        shutil.copy(sol, cell / "final_solution.py")
    (cell / "neutral_cell_log.json").write_text(
        json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[neutral] final rc={log['rc']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
