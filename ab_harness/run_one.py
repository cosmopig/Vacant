#!/usr/bin/env python3
"""run_one.py — execute ONE (task, arm) cell and capture every raw byte.

Arms
----
A  plain    opencode runs the task. Nothing else is in the path.
B  vacant   the SAME opencode command, wrapped by `vacant run --suite <auth>`.
            Defaults only. The single extra flag is --allow-public-upstream,
            because the model channel is a public API (OpenRouter) and vacant's
            default is a local sink that refuses; without it arm B cannot make a
            single model call and would measure nothing.

Both arms get the byte-identical prompt and the byte-identical starting
workspace. The ONLY differences are: (1) the wrapper, (2) the exit code, and
(3) arm B leaves a signed receipt chain behind.

What is written
---------------
<out>/<task>__<arm>/
    meta.json          run configuration + versions + prompt sha256
    workspace/         the agent's workspace, exactly as it was handed over
    agent.jsonl        opencode raw JSON event stream (--format json)
    agent.stderr       opencode stderr
    agent.stdout       opencode stdout (human format, for eyeballing)
    exit.txt           agent process exit code
    vacant/            arm B only: `vacant run` summary + receipt dir
    timing.json        wall clock
Nothing is filtered, truncated, or summarised here. Scoring is a separate
step (grade.py) that happens strictly after both arms of a task are done.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
BANK_T = ROOT / "bank_templates"
AUTH_SUITE = ROOT / "auth_suites"          # outside every workspace, read-only
OUT = ROOT / "runs"

#: Byte-identical across arms. Taken verbatim from the repo's own cross-agent
#: smoke protocol (decisions/reviews/C5_NATIVE_ACCEPTANCE_20260928/
#: PI_LUNA_PAIR_SMOKE_20260928.md) so this experiment does not invent its own
#: prompt. It names the task's own test entry point and nothing else: no plan
#: scaffolding, no persona, no planning mode.
PROMPT = ("Read goal.md. Implement solution.py with the requested top-level "
          "function. You may use the visible tests and run_tests.sh. Finish "
          "with the file saved.")


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sha256_tree(root: pathlib.Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def stage_workspace(task: str, dest: pathlib.Path) -> None:
    """Copy the bank template verbatim. The hidden tree is NOT touched."""
    src = BANK_T / task
    if not src.is_dir():
        raise SystemExit(f"no such task template: {src}")
    dest.mkdir(parents=True)
    for item in src.iterdir():
        if item.is_dir():
            shutil.copytree(item, dest / item.name)
        else:
            shutil.copy2(item, dest / item.name)


def make_auth_suite(task: str) -> pathlib.Path:
    """The authoritative suite: a read-only copy OUTSIDE every workspace.

    vacant refuses `--suite` when it lives under the workspace ("agent 改得到的
    驗收不是驗收"). The workspace keeps its own readable copy because the task's
    run_tests.sh and the agent both need one; the gate grades the pinned one.
    """
    d = AUTH_SUITE / task
    src = BANK_T / task / "tests_visible"
    if not d.exists():
        d.mkdir(parents=True)
        for f in src.iterdir():
            if f.is_file():
                shutil.copy2(f, d / f.name)
        for f in sorted(d.rglob("*"), reverse=True):
            f.chmod(0o555 if f.is_dir() else 0o444)
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--agent-cmd", default=None,
                    help="override the agent command (for mock validation)")
    ap.add_argument("--arm", required=True, choices=["A", "B"])
    ap.add_argument("--timeout", type=float, default=1800.0)
    ap.add_argument("--opencode", default=os.path.expanduser("~/.opencode/bin/opencode"))
    ap.add_argument("--out", default=None,
                    help="output root (default runs/). Used to keep mock "
                         "pipeline validation out of the real batch.")
    a = ap.parse_args()

    out_root = pathlib.Path(a.out) if a.out else OUT
    cell = out_root / f"{a.task}__{a.arm}"
    if cell.exists():
        raise SystemExit(f"refusing to overwrite an existing cell: {cell}")
    cell.mkdir(parents=True)

    ws = cell / "workspace"
    stage_workspace(a.task, ws)
    ws_start = sha256_tree(ws)

    # Arms A and B run the BYTE-IDENTICAL command. The only difference between
    # them is whether `vacant install` has put Vacant's native opencode plugin in
    # the agent's global config -- which is outside this function's control and
    # is why batch.sh sequences arm B into its own phase.
    #
    # (There was a third shape here, `vacant run --suite <pinned> -- <cmd>`,
    # which mediates the model channel. It does not work with opencode's
    # openrouter provider: vacant strips OPENROUTER_API_KEY and only hands the
    # agent a sentinel on OPENAI_API_KEY/ANTHROPIC_API_KEY
    # (envmap.build_child_env), and it only holds a real key for the `openai`
    # wire. Routing opencode through a fixed-port openai-compatible provider
    # does get requests_seen>0, but opencode then still exits non-zero. The
    # executable-acceptance semantics that arm needed are provided by arm C,
    # the branch's own native acceptance bridge, which does not touch the wire.)
    wrapped = a.agent_cmd or (
        f"{a.opencode} run --format json -m {a.model} {json.dumps(PROMPT)}")

    env = dict(os.environ)
    env["PATH"] = os.path.expanduser("~/.opencode/bin") + ":" + env.get("PATH", "")
    kf = ROOT / ".openrouter_key"
    if kf.exists():
        key = kf.read_text().strip()
        env["OPENROUTER_API_KEY"] = key
        # vacant strips BOTH key vars from the agent and substitutes a sentinel;
        # on the way out it swaps the sentinel for the key it holds for the
        # `openai` wire, which envmap.discover_keys() reads from OPENAI_API_KEY
        # only. Without this the proxy forwards an unauthenticated request.
        env["OPENAI_API_KEY"] = key

    started = time.time()
    # A hung agent is a RESULT, not a crash. Record it as its own outcome and
    # keep going: dropping the cell would quietly shrink the denominator, and
    # scoring it as "wrong answer" would be a different claim than "did not
    # finish". Both are recorded; the report carries them separately.
    timed_out = False
    try:
        proc = subprocess.run(wrapped, shell=True, cwd=ws, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=a.timeout)
        out, err, rc = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as e:
        timed_out = True
        out = e.stdout or b""
        err = (e.stderr or b"") + b"\n[harness] wall-clock timeout reached\n"
        rc = 124
    wall = time.time() - started

    # arm B writes a JSON summary to stdout; arm A writes JSONL events there.
    (cell / "agent.jsonl").write_bytes(out)
    (cell / "agent.stderr").write_bytes(err)
    (cell / "exit.txt").write_text(str(rc) + "\n")

    # arm B leaves Vacant's per-project records outside the workspace; copy them
    # in so the raw data is self-contained. Never written into the workspace.
    for name in ("trace", "intake"):
        src = Path.home() / ".vacant" / name
        if src.exists():
            shutil.copytree(src, cell / f"vacant_home_{name}", dirs_exist_ok=True)

    tokens = {"steps": 0, "input": 0, "output": 0, "reasoning": 0,
              "cache_read": 0, "cache_write": 0, "context_peak": 0, "cost_usd": 0.0}
    src = cell / "agent.jsonl"
    for line in src.read_text(errors="replace").splitlines():
        try:
            o = json.loads(line)
        except Exception:
            continue
        if not isinstance(o, dict):
            continue
        t = o.get("tokens") or (o.get("part") or {}).get("tokens") or {}
        if t:
            tokens["steps"] += 1
            for k in ("input", "output", "reasoning"):
                tokens[k] += int(t.get(k) or 0)
            c = t.get("cache") or {}
            tokens["cache_read"] += int(c.get("read") or 0)
            tokens["cache_write"] += int(c.get("write") or 0)
            tokens["context_peak"] = max(tokens["context_peak"],
                                         int(t.get("total") or 0))
        if o.get("cost") is not None:
            tokens["cost_usd"] += float(o["cost"])
    tools = {}
    for line in src.read_text(errors="replace").splitlines():
        try:
            o = json.loads(line)
        except Exception:
            continue
        if isinstance(o, dict) and o.get("type") == "tool_use":
            n = (o.get("part") or {}).get("tool") or (o.get("part") or {}).get("name") or "?"
            tools[n] = tools.get(n, 0) + 1

    meta = {
        "cell": cell.name, "task": a.task, "arm": a.arm, "model": a.model,
        "prompt": PROMPT, "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
        "wrapped_cmd": wrapped,
        "agent_rc": rc, "timed_out": timed_out, "wall_s": round(wall, 3),
        "ws_start_sha256": ws_start, "ws_end_sha256": sha256_tree(ws),
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "bank_template_sha256": sha256_tree(BANK_T / a.task),
        "tokens": tokens, "tool_calls": tools,
        "tool_calls_total": sum(tools.values()),
    }
    if a.arm == "B":
        ij = Path.home() / ".vacant" / "adapters" / "install.json"
        meta["vacant_install_json"] = json.loads(ij.read_text()) if ij.exists() else None
        meta["vacant_plugin_present"] = (
            Path.home() / ".config/opencode/plugin/vacant.js").exists()
    (cell / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    print(json.dumps({"cell": cell.name, "rc": rc, "timed_out": timed_out, "wall_s": round(wall, 1)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
