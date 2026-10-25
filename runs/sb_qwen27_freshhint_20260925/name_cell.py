#!/usr/bin/env python3
"""lcb_3487 label-neutral control cell (round 21).

Background. The neutral-hint (round 13) and pure-presence (round 16) controls
both rescued lcb_3487 attempt 2 with a 175-byte seeded-noise file delivered
as VACANT_FEEDBACK.md. The agent (agent_qwen.py) embeds that file's CONTENT
in the model prompt under the header line

    "## Acceptance feedback from the previous attempt"

The file NAME never reaches the model (the agent reads the file and passes
only its content into the prompt), so the factor the model can actually
react to is that HEADER LABEL, which tells it a previous attempt failed
acceptance. (The round 18 backlog item "name-neutral control" targeted the
file name; this design note corrects that framing — the label is the
testable factor.)

This cell isolates the label: attempt 2 gets the SAME 175-byte seeded noise
(same seed, byte-identical, same sha256 as the presence cell — imported
from presence_cell.py) embedded under a neutral header "## Note". The agent
variant (agent_qwen_neu.py) is byte-identical to agent_qwen.py except that
one header line. The single-factor claim is verifiable offline: the wire
captures of the a2 requests in cells/lcb_3487__presence and
cells/lcb_3487__labelneu can be diffed byte-for-byte.

Outcomes (n=1 either way, stated as such):
  rescue   (rc=0, full=True)  -> the label is not needed; any extra prompt
           content breaks the deterministic no-delivery loop. Attribution:
           "prompt/workspace no longer a clean start", label-agnostic.
  no rescue (no deliverable)  -> the label "acceptance feedback from the
           previous attempt" carries the effect: the model must be told a
           previous attempt failed. Attribution: failure-knowledge, not
           mere perturbation.

Usage (one attempt per command; keeps each command under the 10-minute
limit and leaves a1 evidence behind if the round is cut):
  python3 name_cell.py a1   # clean origin; expect the same no-delivery signature
  python3 name_cell.py a2   # clean origin + SAME noise under NEUTRAL header
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

NEUTRAL_HEADER = "## Note"
LABEL = "## Acceptance feedback from the previous attempt"
AGENT = OUT / "agent_qwen_neu.py"


def noise_file_bytes(n: int) -> bytes:
    """Byte-identical to the presence cell's noise (imported, not re-derived)."""
    import presence_cell
    return presence_cell.noise_file_bytes(n)


def noise_size() -> int:
    import presence_cell
    return presence_cell.neutral_hint_bytes()


def scaffold() -> pathlib.Path:
    """Clean origin: exactly the ws the other arms started from (TASK.md only)."""
    ws = OUT / "ws" / f"{TID}__labelneu"
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
           "--task-id", f"sb_qwen27_{TID}__labelneu",
           "--", str(PY), str(AGENT)]
    env = dict(os.environ)
    env["VACANT_RUN_UPSTREAM_OPENAI"] = UPSTREAM
    env.setdefault("VACANT_SB_MODEL", "qwen/qwen3.8-27b")
    t0 = time.time()
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True,
                          timeout=1800)
    rc = proc.returncode
    wall = round(time.time() - t0, 1)
    print(f"[labelneu {tag}] rc={rc} wall={wall}s", flush=True)
    return {"rc": rc, "wall_s": wall,
            "stdout_tail": proc.stdout[-400:], "stderr_tail": proc.stderr[-400:]}


def log_path(cell: pathlib.Path) -> pathlib.Path:
    return cell / "labelneu_cell_log.json"


def load_log(cell: pathlib.Path) -> dict:
    p = log_path(cell)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"cell": f"{TID}__labelneu",
            "arm": "label-neutral control: resample + same 175B noise under header "
                   f"{NEUTRAL_HEADER!r} (presence cell used {LABEL!r})",
            "agent": "agent_qwen_neu.py (byte-identical to agent_qwen.py except "
                     "the one header line; file name never reaches the model)",
            "agent_sha256": hashlib.sha256(AGENT.read_bytes()).hexdigest(),
            "header_label": NEUTRAL_HEADER,
            "max_tokens": os.environ.get("VACANT_SB_MAX_TOKENS", "32768")}


def save_log(cell: pathlib.Path, log: dict) -> None:
    log_path(cell).write_text(
        json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("a1", "a2"):
        print(__doc__)
        return 2
    tag = sys.argv[1]
    cell = OUT / "cells" / f"{TID}__labelneu"
    cell.mkdir(parents=True, exist_ok=True)
    log = load_log(cell)

    if tag == "a1":
        ws = scaffold()
        log["attempt1"] = run_attempt(cell, ws, "a1")
    else:
        ws = scaffold()
        n = noise_size()
        noise = noise_file_bytes(n)
        (ws / "VACANT_FEEDBACK.md").write_bytes(noise)  # same name: invisible to
        # the model; keeping it identical removes any agent-reading difference
        fb = (ws / "VACANT_FEEDBACK.md").read_bytes()
        assert fb == noise
        log["feedback_redelivered"] = {
            "path": "VACANT_FEEDBACK.md", "bytes": len(fb),
            "sha256": hashlib.sha256(fb).hexdigest(),
            "header_label": NEUTRAL_HEADER}
        log["attempt2"] = run_attempt(cell, ws, "a2")
        log["rc"] = log["attempt2"]["rc"]

    sol = (OUT / "ws" / f"{TID}__labelneu") / "solution.py"
    if sol.exists():
        shutil.copy(sol, cell / "final_solution.py")
    save_log(cell, log)
    print(f"[labelneu {tag}] final rc={log.get('rc', 'n/a')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
