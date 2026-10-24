#!/usr/bin/env python3
"""Small batch: fresh_hint vs resample vs none, driven by REAL acceptance.

Design (see runs/sb_qwen27_freshhint_20260925/README.md):
- 6 tasks: the FIRST 6 rows of ops/gain/data/lcb_bank_v2.jsonl.
  Deterministic selection, no cherry-picking; the bank file sha256 is pinned.
- Arms:
    none       — 1 attempt (pass@1 baseline)
    resample   — up to 2 attempts, workspace reset, no hint
    fresh_hint — up to 2 attempts, workspace reset + <=400B key-failure hint
  The retry is driven by the VISIBLE test suite (real executable acceptance),
  never by a scorer. Hidden tests are NOT part of the gate and never enter
  the prompt or the feedback; they are graded afterwards by grade.py.
- Agent: agent_qwen.py (one-shot, identical across arms; reads
  VACANT_FEEDBACK.md if present).
- Mediation: the agent talks to $OPENAI_BASE_URL, which under `vacant run`
  is the tee proxy; the upstream is pinned via VACANT_RUN_UPSTREAM_OPENAI.

Usage:
  python3 make_batch.py setup        # build suites + workspaces + meta.json
  python3 make_batch.py run          # run all cells (arms x tasks), sequential
  python3 make_batch.py run --cell lcb_3026__fresh_hint   # one cell
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
BANK = REPO / "ops/gain/data/lcb_bank_v2.jsonl"
OUT = REPO / "runs" / "sb_qwen27_freshhint_20260925"
N_TASKS = int(os.environ.get("SB_N_TASKS", "6"))
MAX_ATTEMPTS = int(os.environ.get("SB_MAX_ATTEMPTS", "2"))
ARMS = ("none", "resample", "fresh_hint")
UPSTREAM = os.environ.get("SB_UPSTREAM", "http://100.119.113.56:1234")


def fmt_call(entry: dict, ep: str) -> str:
    args = [repr(a) for a in entry["args"]]
    return f"{ep}({', '.join(args)})"


def task_md(t: dict) -> str:
    ep = t["entry_point"]
    vis = "\n".join(
        f"- `{fmt_call(c, ep)} == {c['expected']!r}`" for c in t["visible"])
    return f"""# Task

{t['prompt'].strip()}

## Entry point

Define a function named `{ep}` in a file called `solution.py` in the
current directory. It must handle the argument types shown in the checks
below.

## Visible acceptance checks

The following checks are run against `solution.py` when this process exits:

```
{vis}
```

## Instructions

- Write the complete `solution.py` in the current directory.
- If a file named `VACANT_FEEDBACK.md` exists in the current directory,
  read it first: it is acceptance feedback from a previous attempt.
- Do not write any other files.
"""


def setup() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    lines = BANK.read_text(encoding="utf-8").splitlines()[:N_TASKS]
    tasks = [json.loads(l) for l in lines]
    bank_sha = hashlib.sha256(BANK.read_bytes()).hexdigest()
    (OUT / "bank_sha256.txt").write_text(f"{bank_sha}  {BANK}\n")

    meta = []
    (OUT / "tasks").mkdir(parents=True, exist_ok=True)
    for t in tasks:
        tid, ep = t["task_id"], t["entry_point"]
        sd = OUT / "suites" / tid
        sd.mkdir(parents=True, exist_ok=True)
        checks = "\n\n".join(
            f"def check_{i}():\n    assert {fmt_call(c, ep)} == {c['expected']!r}"
            for i, c in enumerate(t["visible_tests"], 1))
        src = (f'"""Visible acceptance checks for {tid}."""\n'
               f"from solution import {ep}  # noqa: F401\n\n"
               + checks + "\n")
        (sd / "test_visible.py").write_text(src, encoding="utf-8")
        full = {"task_id": tid, "entry_point": ep, "prompt": t["prompt"],
                "visible": t["visible_tests"], "hidden": t["hidden_tests"]}
        (OUT / "tasks" / f"{tid}.json").write_text(
            json.dumps(full, ensure_ascii=False, indent=1), encoding="utf-8")
        meta.append({"task_id": tid, "entry_point": ep,
                     "n_visible": len(t["visible_tests"]),
                     "n_hidden": len(t["hidden_tests"])})

    (OUT / "meta.json").write_text(json.dumps({
        "bank": str(BANK), "bank_sha256": bank_sha, "n_tasks": N_TASKS,
        "arms": list(ARMS), "max_attempts_retry_arms": MAX_ATTEMPTS,
        "none_arm_attempts": 1,
        "upstream": UPSTREAM,
        "model": os.environ.get("VACANT_SB_MODEL", "qwen/qwen3.8-27b"),
        "note": ("thinking mode could not be disabled in this LM Studio build "
                 "(enable_thinking:false and /no_think both still produced "
                 "reasoning_content); all arms ran with thinking on"),
        "tasks": meta,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("setup done:", [(m["task_id"], m["n_visible"], m["n_hidden"])
                          for m in meta])


def scaffold(tid: str, arm: str) -> pathlib.Path:
    ws = OUT / "ws" / f"{tid}__{arm}"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)
    t = json.loads((OUT / "tasks" / f"{tid}.json").read_text(encoding="utf-8"))
    (ws / "TASK.md").write_text(task_md(t), encoding="utf-8")
    return ws


def run_cell(name: str) -> dict:
    tid, arm = name.split("__")
    ws = scaffold(tid, arm)
    cell = OUT / "cells" / name
    if cell.exists():
        shutil.rmtree(cell)
    cell.mkdir(parents=True, exist_ok=True)
    # retry flags must precede the `--` separator
    base = [str(VACANT), "run",
            "--workspace", str(ws),
            "--run-dir", str(cell),
            "--suite", str(OUT / "suites" / tid),
            "--task-id", f"sb_qwen27_{name}"]
    if arm in ("resample", "fresh_hint"):
        base += ["--retry", arm, "--max-attempts", str(MAX_ATTEMPTS)]
    base += ["--", str(PY), str(OUT / "agent_qwen.py")]
    env = dict(os.environ)
    env["VACANT_RUN_UPSTREAM_OPENAI"] = UPSTREAM
    env.setdefault("VACANT_SB_MODEL", "qwen/qwen3.8-27b")
    t0 = time.time()
    proc = subprocess.run(base, env=env, capture_output=True, text=True,
                          timeout=3600)
    wall = round(time.time() - t0, 1)
    rec = {"cell": name, "rc": proc.returncode, "wall_s": wall,
           "stdout_tail": proc.stdout[-400:], "stderr_tail": proc.stderr[-400:]}
    (cell / "make_batch_log.json").write_text(
        json.dumps({"cmd": base, **rec}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    # snapshot the final workspace solution (if any) into the cell
    sol = ws / "solution.py"
    if sol.exists():
        shutil.copy(sol, cell / "final_solution.py")
    print(f"[{name}] rc={proc.returncode} wall={wall}s", flush=True)
    return rec


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    mode = sys.argv[1]
    if mode == "setup":
        setup()
        return 0
    if mode == "run":
        if len(sys.argv) > 2:
            cells = sys.argv[2:]
        else:
            meta = json.loads((OUT / "meta.json").read_text(encoding="utf-8"))
            cells = [f"{m['task_id']}__{arm}"
                     for m in meta["tasks"] for arm in ARMS]
        for name in cells:
            run_cell(name)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
