"""Run the pi coding agent on the process-baseline tasks and record trajectories.

Condition `baseline` = no Vacant: pi's stock system prompt, task prompt only.
Condition `vacant`   = same harness, plus `--append-system-prompt <profile>` (see
WITH_VACANT.md). Nothing else differs (same tasks, model, tools, budget).

Prereqs: `proxy.py` running on --proxy-port (it injects reasoning_effort=none and
the upstream token), and a pi agent dir whose models.json defines provider
`vacantproxy` (this script writes one if missing).

Output per run under <out>/<run_id>/: events.jsonl (raw pi stream), trajectory.jsonl
(normalized), diff.patch, metrics.json, meta.json, stderr.txt.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import metrics
import trajectory

HERE = Path(__file__).resolve().parent
TOOLS = "read,bash,edit,write,grep,find,ls"


def write_models_json(agent_dir: Path, port: int, model: str) -> None:
    agent_dir.mkdir(parents=True, exist_ok=True)
    cfg = {"providers": {"vacantproxy": {
        "baseUrl": f"http://127.0.0.1:{port}/v1", "api": "openai-completions", "apiKey": "local",
        "compat": {"supportsDeveloperRole": False, "supportsReasoningEffort": False},
        "models": [{"id": model, "contextWindow": 32768, "maxTokens": 4096}]}}}
    (agent_dir / "models.json").write_text(json.dumps(cfg, indent=1))


def git(ws: Path, *a: str) -> str:
    return subprocess.run(["git", *a], cwd=ws, capture_output=True, text=True).stdout


def score(rdir: Path, task: dict, run_id: str, condition: str, t0: float, t1: float, args, rc=None) -> dict:
    """Post-process a finished run (also used by --rescore on existing runs)."""
    ws = rdir / "ws"
    git(ws, "add", "-A")
    diff = git(ws, "diff", "--cached")
    numstat = git(ws, "diff", "--cached", "--numstat")
    (rdir / "diff.patch").write_text(diff)
    added = removed = 0
    for line in numstat.splitlines():
        a, r, *_ = line.split("\t")
        added += int(a) if a.isdigit() else 0
        removed += int(r) if r.isdigit() else 0
    steps = trajectory.normalize(trajectory.load_events(str(rdir / "events.jsonl")), run_id, task["task_id"], condition)
    prefix = str(ws.resolve()) + "/"
    for s in steps:  # workspace-relative paths so runs are comparable
        s["files_read"] = [x.replace(prefix, "") for x in s["files_read"]]
        s["files_written"] = [x.replace(prefix, "") for x in s["files_written"]]
        if s["command"]:
            s["command"] = s["command"].replace(prefix, "").replace(prefix[:-1], ".")
    with open(rdir / "trajectory.jsonl", "w") as f:
        for s in steps:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    feats = metrics.order_features(steps)
    feats["diff_added"], feats["diff_removed"] = added, removed
    feats["diff_files"] = len(numstat.splitlines())
    calls = []
    if args.call_log and Path(args.call_log).exists():
        for line in open(args.call_log):
            c = json.loads(line)
            if t0 <= c["ts_start"] <= t1:
                calls.append(c)
    tok_in = sum((c.get("usage") or {}).get("prompt_tokens", 0) or 0 for c in calls)
    tok_out = sum((c.get("usage") or {}).get("completion_tokens", 0) or 0 for c in calls)
    final = next((s["text"] for s in reversed(steps) if s["kind"] == "final"), None)
    m = {"run_id": run_id, "task_id": task["task_id"], "condition": condition,
         "sequence": metrics.action_sequence(steps), "features": feats,
         "llm_calls": len(calls), "llm_call_errors": sum(1 for c in calls if c["status"] != 200),
         "tokens_in": tok_in, "tokens_out": tok_out, "wall_s": round(t1 - t0, 1), "rc": rc,
         "final_text": (final or "")[:2000]}
    if args.personas:
        refs = json.loads(Path(args.personas).read_text())
        m["persona_similarity"] = {
            name: metrics.compare(steps, p["by_family"][task["family"]])
            for name, p in refs["personas"].items() if task["family"] in p["by_family"]}
    (rdir / "metrics.json").write_text(json.dumps(m, ensure_ascii=False, indent=1))
    return m


def run_one(task_dir: Path, out: Path, run_id: str, args) -> dict:
    task = json.loads((task_dir / "task.json").read_text())
    rdir = out / run_id
    ws = rdir / "ws"
    if rdir.exists():
        shutil.rmtree(rdir)
    shutil.copytree(task_dir / "repo", ws)
    (ws / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n*.pyc\n")
    git(ws, "init", "-q")
    git(ws, "-c", "user.email=x@x", "-c", "user.name=x", "add", "-A")
    git(ws, "-c", "user.email=x@x", "-c", "user.name=x", "commit", "-qm", "fixture")
    cmd = ["pi", "--mode", "json", "-p", "--no-session", "--offline", "--no-extensions", "--no-skills",
           "--no-context-files", "--no-prompt-templates", "--tools", TOOLS,
           "--provider", "vacantproxy", "--model", args.model]
    if args.condition == "vacant":
        if not args.profile:
            raise SystemExit("--profile required for condition=vacant")
        cmd += ["--append-system-prompt", str(Path(args.profile).resolve())]
    cmd.append(task["prompt"])
    env = dict(os.environ, PI_CODING_AGENT_DIR=str(args.agent_dir),
               PATH=f"{args.agent_bin}:{os.environ['PATH']}", PI_OFFLINE="1")
    t0 = time.time()
    with open(rdir / "events.jsonl", "w") as fo, open(rdir / "stderr.txt", "w") as fe:
        try:
            rc = subprocess.run(cmd, cwd=ws, stdout=fo, stderr=fe, env=env, timeout=args.timeout).returncode
        except subprocess.TimeoutExpired:
            rc = "timeout"
    t1 = time.time()
    m = score(rdir, task, run_id, args.condition, t0, t1, args, rc)
    pi_ver = subprocess.run(["pi", "--version"], capture_output=True, text=True).stdout.strip()
    meta = {"run_id": run_id, "task": task, "condition": args.condition, "model": args.model,
            "upstream": args.upstream_label, "cli": "pi", "cli_version": pi_ver, "tools": TOOLS,
            "reasoning_effort": "none (injected by proxy.py)", "t_start": t0, "t_end": t1,
            "profile": args.profile, "cmd": cmd[:-1] + ["<prompt>"]}
    (rdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", nargs="*", default=None)
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--condition", choices=["baseline", "vacant"], default="baseline")
    ap.add_argument("--profile", help="profile file appended to system prompt (vacant condition)")
    ap.add_argument("--model", default="qwen3.8:27b")
    ap.add_argument("--out", default="/workspace/process_baseline/runs")
    ap.add_argument("--proxy-port", type=int, default=18080)
    ap.add_argument("--agent-dir", default="/workspace/process_baseline/pi_agent_dir")
    ap.add_argument("--agent-bin", default="/workspace/process_baseline/agentenv/bin",
                    help="dir prepended to PATH so `python`/`pytest` exist for the agent")
    ap.add_argument("--call-log", default=os.environ.get("CALL_LOG"))
    ap.add_argument("--upstream-label", required=True, help="e.g. kaggle-qwen3.8:27b or MOCK")
    ap.add_argument("--personas", default=str(HERE / "personas" / "examples.json"))
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--tag", default="")
    ap.add_argument("--start-rep", type=int, default=0)
    ap.add_argument("--rescore", action="store_true", help="recompute trajectory/metrics for existing runs in --out")
    args = ap.parse_args()
    args.agent_dir = Path(args.agent_dir)
    write_models_json(args.agent_dir, args.proxy_port, args.model)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.rescore:
        for md in sorted(out.glob("*/meta.json")):
            meta = json.loads(md.read_text())
            old = md.parent / "metrics.json"
            rc = json.loads(old.read_text()).get("rc") if old.exists() else None
            score(md.parent, meta["task"], meta["run_id"], meta["condition"], meta["t_start"], meta["t_end"], args, rc)
            print("rescored", meta["run_id"])
        return
    task_dirs = sorted(p for p in (HERE / "tasks").iterdir() if (p / "task.json").exists())
    if args.tasks:
        task_dirs = [p for p in task_dirs if p.name in args.tasks]
    for rep in range(args.start_rep, args.start_rep + args.repeats):
        for td in task_dirs:
            run_id = f"{args.condition}{args.tag}_{td.name}_r{rep}"
            m = run_one(td, out, run_id, args)
            print(json.dumps({k: m[k] for k in ("run_id", "sequence", "llm_calls", "wall_s", "rc")}), flush=True)


if __name__ == "__main__":
    main()
