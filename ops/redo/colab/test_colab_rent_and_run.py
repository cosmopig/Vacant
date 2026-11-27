#!/usr/bin/env python3
"""Unit & integration tests for colab_rent_and_run.sh, colab_queue.json, and launch_batch.sh --reuse-session.

Uses a stateful fake `colab` binary placed ahead of system PATH (zero network, zero real Colab calls).
Covers:
  1. Static checks: bash -n syntax, no hardcoded /home/ paths, no `colab pay`, repo colab_queue.json valid.
  2. Dry-run mode with a trap `colab` binary (never invokes `colab`; tests both fresh launch & --reuse-session).
  3. Launch failure after `colab new` created an assignment => recorded in colab_registry.jsonl,
     `colab stop -s <session>` called, assignment count drop verified.
  4. Account-level usage watchdog:
     - usage_rate > 0 / active_assignments > 0 with empty registry => ALERT written, NO auto-stop.
     - unknown session in `colab sessions` => ALERT written, NO auto-stop.
     - registered live session matching assignments => NO alert.
     - excess assignments (e.g. another machine's VM) => ALERT written, NO auto-stop.
  5. Queue mode: GPU preference order A100->G4->L4, too-many-assignments graceful fallback on 2nd VM,
     periodic partial fetch (`fetch_batch.sh --force --no-stop`), BATCH_DONE fetch + `--reuse-session`
     for next batch without releasing VM, release + verify usage 0 when queue empty.
  6. Concurrent 2nd VM rental when account allows 2 assignments.
  7. Spend cap (180 CU) and balance floor (20 CU) breaches => partial fetch, stop, ALERT, exit 10.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
ORCH = HERE / "colab_rent_and_run.sh"
LAUNCH = HERE / "launch_batch.sh"
QUEUE_TEMPLATE = HERE / "colab_queue.json"

FAKE_COLAB_PY = r'''#!/usr/bin/env python3
"""Stateful fake `colab` CLI for offline unit/integration tests."""
import hashlib
import json
import os
import pathlib
import shutil
import sys
import tarfile

STATE_PATH = pathlib.Path(os.environ["FAKE_COLAB_STATE"])
LOG_PATH = pathlib.Path(os.environ["FAKE_COLAB_LOG"])


def load_state():
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_state(st):
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, STATE_PATH)


def log_call(argv):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(argv) + "\n")


def make_run_tar(tar_path: pathlib.Path, include_report: bool = True):
    tar_path.parent.mkdir(parents=True, exist_ok=True)
    stage = tar_path.parent / (tar_path.name + ".stage")
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    (stage / "RUN.json").write_text(json.dumps({"schema": "vacant.redo.run/1"}) + "\n", encoding="utf-8")
    if include_report:
        (stage / "REPORT.json").write_text(json.dumps({"pairs_complete": 1}) + "\n", encoding="utf-8")
    with tarfile.open(tar_path, "w:gz") as tf:
        for p in sorted(stage.iterdir()):
            tf.add(p, arcname=p.name)
    sha = hashlib.sha256(tar_path.read_bytes()).hexdigest()
    (pathlib.Path(str(tar_path) + ".sha256")).write_text(f"{sha}  {tar_path.name}\n", encoding="utf-8")
    shutil.rmtree(stage)
    return sha


def main():
    argv = sys.argv[1:]
    log_call(argv)

    # Strip global options (--auth=..., --config <p>).
    i = 0
    while i < len(argv):
        if argv[i].startswith("--auth="):
            i += 1
        elif argv[i] in ("--auth", "--config"):
            i += 2
        else:
            break
    args = argv[i:]
    if not args:
        sys.exit(2)
    cmd = args[0]
    rest = args[1:]
    st = load_state()

    if cmd == "usage":
        # Optional dynamic balance schedule per usage call.
        sched = st.get("balance_schedule") or []
        if sched:
            st["balance"] = sched.pop(0)
            save_state(st)
        extra_asgn = int(st.get("extra_assignments", 0))
        active_n = len(st["sessions"]) + extra_asgn
        rate = float(st.get("override_usage_rate")) if st.get("override_usage_rate") is not None else (active_n * 2.33)
        print(f"Current balance: {float(st['balance']):.2f} compute units")
        print(f"Usage rate: {rate:.2f}/hr")
        print(f"Active assignments: {active_n}")
        sys.exit(0)

    if cmd == "sessions":
        if not st["sessions"]:
            print("No active sessions.")
            sys.exit(0)
        for name, info in st["sessions"].items():
            print(f"[{name}] {info['endpoint']} | Hardware: {info['gpu']} | Shape: Standard | Variant: GPU")
        sys.exit(0)

    if cmd == "new":
        sess = ""
        gpu = "G4"
        j = 0
        while j < len(rest):
            if rest[j] == "-s":
                sess = rest[j + 1]
                j += 2
            elif rest[j] == "--gpu":
                gpu = rest[j + 1]
                j += 2
            else:
                j += 1
        if gpu in set(st.get("reject_gpus") or []):
            print(f"Error: GPU {gpu} currently unavailable", file=sys.stderr)
            sys.exit(1)
        max_asgn = int(st.get("max_assignments", 1))
        if len(st["sessions"]) + int(st.get("extra_assignments", 0)) >= max_asgn:
            print("Error: TooManyAssignments: maximum number of concurrent assignments reached", file=sys.stderr)
            sys.exit(1)
        st["ep_seq"] = int(st.get("ep_seq", 0)) + 1
        ep = f"gpu-{gpu.lower()}-s-fake-{st['ep_seq']:04d}"
        st["sessions"][sess] = {
            "endpoint": ep,
            "gpu": gpu,
            "polls": 0,
            "remote_root": "/srv/redo/run",
            "tar_path": "/content/redo_results.tar.gz",
            "done": False,
        }
        save_state(st)
        print(f"Created session {sess} ({ep})")
        sys.exit(0)

    if cmd == "upload":
        sess = ""
        src = ""
        dst = ""
        j = 0
        pos = []
        while j < len(rest):
            if rest[j] == "-s":
                sess = rest[j + 1]
                j += 2
            else:
                pos.append(rest[j])
                j += 1
        if len(pos) >= 2:
            src, dst = pos[0], pos[1]
        if int(st.get("fail_upload_remaining", 0)) > 0:
            st["fail_upload_remaining"] = int(st["fail_upload_remaining"]) - 1
            save_state(st)
            print("Error: simulated upload failure after assignment created", file=sys.stderr)
            sys.exit(1)
        # Inspect bootstrap script to capture exact remote_run_root & tar_path for this batch.
        if sess in st["sessions"] and "redo_bootstrap_" in dst and os.path.isfile(src):
            txt = pathlib.Path(src).read_text(encoding="utf-8", errors="replace")
            for tok_flag, key in (("--root ", "remote_root"), ("--tar-out ", "tar_path")):
                for line in txt.splitlines():
                    if tok_flag in line:
                        val = line.split(tok_flag, 1)[1].strip().rstrip("\\").strip()
                        st["sessions"][sess][key] = val
            st["sessions"][sess]["polls"] = 0
            st["sessions"][sess]["done"] = False
            save_state(st)
        sys.exit(0)

    if cmd == "ssh":
        sess = ""
        j = 0
        cmd_parts = []
        while j < len(rest):
            if rest[j] == "-s":
                sess = rest[j + 1]
                j += 2
            elif rest[j] == "--":
                cmd_parts = rest[j + 1:]
                break
            else:
                j += 1
        cmd_str = " ".join(cmd_parts)
        info = st["sessions"].get(sess)
        if not info:
            print(f"Error: session {sess} not found", file=sys.stderr)
            sys.exit(1)
        fs_root = STATE_PATH.parent / "fake_vm_fs" / sess
        # Handle split command from fetch_batch.sh
        if "split -b" in cmd_str:
            tar_rel = info["tar_path"].lstrip("/")
            tar_file = fs_root / tar_rel
            if not tar_file.is_file():
                make_run_tar(tar_file, include_report=info.get("done", False))
            part = pathlib.Path(str(tar_file) + ".part.0000")
            shutil.copyfile(tar_file, part)
            print(f"{info['tar_path']}.part.0000")
            sys.exit(0)
        # Handle partial snapshot tar command from fetch_batch.sh --force
        if "tar -czf" in cmd_str:
            tar_rel = info["tar_path"].lstrip("/")
            tar_file = fs_root / tar_rel
            make_run_tar(tar_file, include_report=False)
            sys.exit(0)
        # Otherwise bootstrap ssh command
        print("BATCH_STARTED pid=12345")
        sys.exit(0)

    if cmd == "download":
        sess = ""
        j = 0
        pos = []
        while j < len(rest):
            if rest[j] == "-s":
                sess = rest[j + 1]
                j += 2
            else:
                pos.append(rest[j])
                j += 1
        remote, local = pos[0], pos[1]
        info = st["sessions"].get(sess)
        if not info:
            sys.exit(1)
        fs_root = STATE_PATH.parent / "fake_vm_fs" / sess
        pathlib.Path(local).parent.mkdir(parents=True, exist_ok=True)

        if remote.endswith("/VM_READY.json"):
            pathlib.Path(local).write_text(json.dumps({
                "ready_utc": "2026-11-27T06:00:00Z",
                "gpu": info["gpu"],
                "vllm_version": "0.30.0",
                "pi_version": "0.87.1",
                "served_model_name": "fake-model",
            }) + "\n", encoding="utf-8")
            sys.exit(0)

        if remote.endswith("/STATUS.txt"):
            info["polls"] = int(info.get("polls", 0)) + 1
            polls_needed = int(st.get("polls_until_done", 2))
            if info["polls"] >= polls_needed:
                info["done"] = True
            save_state(st)
            pathlib.Path(local).write_text(f"2026-11-27T06:05:00Z fake_batch: poll={info['polls']}/{polls_needed}\n", encoding="utf-8")
            sys.exit(0)

        if remote.endswith("/BATCH_DONE.json"):
            if not info.get("done"):
                sys.exit(1)
            tar_file = fs_root / info["tar_path"].lstrip("/")
            sha = make_run_tar(tar_file, include_report=True)
            pathlib.Path(local).write_text(json.dumps({
                "schema": "vacant.redo.colab.done/1",
                "ended_utc": "2026-11-27T06:10:00Z",
                "redo_rc": 0,
                "status": "COMPLETE",
                "tarball_path": info["tar_path"],
                "tarball_sha256": sha,
            }) + "\n", encoding="utf-8")
            sys.exit(0)

        if remote.endswith("/runner.log"):
            pathlib.Path(local).write_text("2026-11-27T06:05:00Z fake runner log\n", encoding="utf-8")
            sys.exit(0)

        if ".part." in remote or remote.endswith(".sha256"):
            src_f = fs_root / remote.lstrip("/")
            if not src_f.is_file():
                sys.exit(1)
            shutil.copyfile(src_f, local)
            sys.exit(0)

        sys.exit(1)

    if cmd == "stop":
        sess = ""
        j = 0
        while j < len(rest):
            if rest[j] == "-s":
                sess = rest[j + 1]
                j += 2
            else:
                j += 1
        st["sessions"].pop(sess, None)
        save_state(st)
        print(f"Stopped session {sess}")
        sys.exit(0)

    print(f"Unknown fake colab subcommand: {cmd}", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
'''


def run_cmd(argv: list[str], *, env: dict[str, str] | None = None, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, env=env, timeout=timeout)


def write_executable(path: pathlib.Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def make_smoke_fixtures(root: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    """Create minimal valid plan.json, bank dir, and vllm_config.json in a temp dir."""
    bank = root / "bank"
    (bank / "t1" / "workspace").mkdir(parents=True)
    (bank / "t1" / "workspace" / "sol.py").write_text("def f(x): return x\n", encoding="utf-8")

    vcfg = root / "vllm.json"
    vcfg.write_text(json.dumps({
        "model_id": "fake/model",
        "served_model_name": "fake-model",
        "max_model_len": 32768,
        "max_tokens": 1024,
        "max_num_seqs": 2,
    }) + "\n", encoding="utf-8")

    plan = root / "plan.json"
    plan.write_text(json.dumps({
        "schema": "vacant.redo.plan/1",
        "id": "smoke_q",
        "tasks": ["t1"],
        "reps": 1,
        "arms": {"A": {"attempts": 1}, "R": {"attempts": 1}},
        "pair": ["A", "R"],
        "agent": "pi",
        "providers": [{"provider": "colab-vllm-nothink", "model": "fake-model", "jobs": 1}],
        "attempt_timeout_s": 60,
    }) + "\n", encoding="utf-8")
    return plan, bank, vcfg


def make_fake_env(tmp: pathlib.Path, state: dict[str, Any]) -> tuple[dict[str, str], pathlib.Path, pathlib.Path]:
    bin_dir = tmp / "fake_bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    fake_colab = bin_dir / "colab"
    write_executable(fake_colab, FAKE_COLAB_PY)
    state_p = tmp / "fake_colab_state.json"
    log_p = tmp / "fake_colab_calls.jsonl"
    state_p.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    log_p.write_text("", encoding="utf-8")
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
        "FAKE_COLAB_STATE": str(state_p),
        "FAKE_COLAB_LOG": str(log_p),
    }
    return env, state_p, log_p


def read_calls(log_p: pathlib.Path) -> list[list[str]]:
    if not log_p.is_file():
        return []
    return [json.loads(line) for line in log_p.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_jsonl(p: pathlib.Path) -> list[dict[str, Any]]:
    if not p.is_file():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    checks: list[tuple[bool, str]] = []

    def chk(cond: bool, msg: str) -> None:
        checks.append((cond, msg))
        print(f"  [{'PASS' if cond else 'FAIL'}] {msg}")

    # 1. Static checks (syntax, no hardcoded /home/ paths, no `colab pay`).
    print("1) Static & syntax checks")
    for sh in (ORCH, LAUNCH):
        r = run_cmd(["bash", "-n", str(sh)])
        chk(r.returncode == 0, f"bash -n passes on {sh.name}")
        txt = sh.read_text(encoding="utf-8")
        chk(not re.search(r"/home/[A-Za-z0-9_.-]+", txt), f"no hardcoded /home/<user> path in {sh.name}")
        # Allow comments mentioning "Never runs `colab pay`", disallow executable invocation.
        non_comment = "\n".join(ln for ln in txt.splitlines() if not ln.lstrip().startswith("#"))
        chk("colab pay" not in non_comment, f"no `colab pay` invocation in {sh.name}")

    q_txt = QUEUE_TEMPLATE.read_text(encoding="utf-8")
    chk(not re.search(r"/home/[A-Za-z0-9_.-]+", q_txt), "no hardcoded /home/<user> path in colab_queue.json")
    q_doc = json.loads(q_txt)
    chk(q_doc.get("schema") == "vacant.redo.colab.queue/1" and len(q_doc.get("batches", [])) >= 1,
        "colab_queue.json has valid schema and at least one example batch")

    tmp_root = pathlib.Path(tempfile.mkdtemp(prefix="test_colab_rent_"))
    try:
        plan, bank, vcfg = make_smoke_fixtures(tmp_root)

        # 2. Dry-run mode with a failing trap `colab` binary.
        print("2) Dry-run mode (trap colab binary must never be called)")
        trap_dir = tmp_root / "trap_bin"
        trap_dir.mkdir()
        write_executable(trap_dir / "colab", "#!/usr/bin/env bash\necho TRAP_COLAB_CALLED >&2\nexit 99\n")
        trap_env = {**os.environ, "PATH": f"{trap_dir}:{os.environ.get('PATH', '')}"}

        r = run_cmd([
            "bash", str(LAUNCH), str(plan), str(bank),
            "--gpu", "L4", "--vllm-config", str(vcfg),
            "--reuse-session", "redo-existing-123456",
            "--batch-name", "reused_b2",
            "--allow-uncommitted-plan", "--dry-run",
        ], env=trap_env)
        chk(
            r.returncode == 0
            and "--reuse-session set: skipping colab new" in r.stdout
            and "colab new" not in "\n".join(ln for ln in r.stdout.splitlines() if "skipping colab new" not in ln)
            and "remote_run_root=/srv/redo/runs/reused_b2" in r.stdout
            and "TRAP_COLAB_CALLED" not in r.stderr,
            "launch_batch.sh --reuse-session --dry-run skips `colab new` and isolates remote_run_root",
        )

        q_dry = tmp_root / "queue_dry.json"
        q_dry.write_text(json.dumps({
            "schema": "vacant.redo.colab.queue/1",
            "defaults": {"preferred_gpus": ["A100", "G4", "L4"], "max_spend_cu": 180, "balance_floor_cu": 20},
            "batches": [
                {"id": "b1", "plan": str(plan), "bank": str(bank), "vllm_config": str(vcfg), "allow_uncommitted_plan": True},
                {"id": "b2", "plan": str(plan), "bank": str(bank), "vllm_config": str(vcfg), "allow_uncommitted_plan": True},
            ],
        }, indent=2) + "\n", encoding="utf-8")
        r = run_cmd([
            "bash", str(ORCH), "--queue", str(q_dry),
            "--registry", str(tmp_root / "dry_reg.jsonl"),
            "--alerts-log", str(tmp_root / "dry_alerts.log"),
            "--log", str(tmp_root / "dry.log"),
            "--out-root", str(tmp_root / "dry_out"),
            "--dry-run",
        ], env=trap_env)
        chk(
            r.returncode == 0
            and "colab new -s redo-b1-DRYRUN --gpu A100" in r.stdout
            and "--reuse-session redo-b1-DRYRUN" in r.stdout
            and "TRAP_COLAB_CALLED" not in r.stderr
            and not (tmp_root / "dry_reg.jsonl").exists()
            and not (tmp_root / "dry_alerts.log").exists(),
            "colab_rent_and_run.sh --dry-run prints fresh + reuse plan, never runs colab, writes no state",
        )

        # Also check repo template colab_queue.json works with --dry-run (even if $HOME bank doesn't exist).
        r = run_cmd(["bash", str(ORCH), "--queue", str(QUEUE_TEMPLATE), "--dry-run"], env=trap_env)
        chk(r.returncode == 0 and "TRAP_COLAB_CALLED" not in r.stderr,
            "repo ops/redo/colab/colab_queue.json passes colab_rent_and_run.sh --dry-run")

        # 3. Assignment created then launch fails => registry recorded + `colab stop` called + drop verified.
        print("3) Launch fails after assignment created => registry + stop + verify")
        d3 = tmp_root / "case3"
        d3.mkdir()
        env3, state3_p, log3_p = make_fake_env(d3, {
            "balance": 220.0,
            "sessions": {},
            "max_assignments": 1,
            "fail_upload_remaining": 1,  # 1st launch creates assignment via `colab new`, then fails on `upload`!
            "polls_until_done": 1,
        })
        q3 = d3 / "queue.json"
        q3.write_text(json.dumps({
            "schema": "vacant.redo.colab.queue/1",
            "batches": [
                {"id": "c3_b1", "plan": str(plan), "bank": str(bank), "vllm_config": str(vcfg),
                 "preferred_gpus": ["L4", "G4"], "allow_uncommitted_plan": True},
            ],
        }) + "\n", encoding="utf-8")
        reg3 = d3 / "colab_registry.jsonl"
        alerts3 = d3 / "colab_alerts.log"
        r = run_cmd([
            "bash", str(ORCH), "--queue", str(q3),
            "--registry", str(reg3), "--alerts-log", str(alerts3),
            "--log", str(d3 / "run.log"), "--out-root", str(d3 / "out"),
            "--rent-interval", "0", "--poll-interval", "0", "--partial-fetch-interval", "9999",
            "--tick-interval", "0", "--stop-retry-delay", "0", "--no-watchdog",
        ], env=env3)
        calls3 = read_calls(log3_p)
        regs3 = read_jsonl(reg3)
        failed_assign_recs = [x for x in regs3 if x.get("event") == "launch_failed_assignment"]
        stopped_fail_recs = [x for x in regs3 if x.get("event") == "stopped_after_launch_failure"]
        stop_calls3 = [c for c in calls3 if c and c[0] == "stop"]
        chk(r.returncode == 0, f"case3 exited 0 after recovering on next GPU (rc={r.returncode})")
        chk(
            len(failed_assign_recs) == 1
            and failed_assign_recs[0]["endpoint"].startswith("gpu-l4-")
            and all(k in failed_assign_recs[0] for k in ("ts", "session", "endpoint", "gpu", "batch", "state")),
            "failed launch assignment recorded in colab_registry.jsonl with ts/session/endpoint/gpu/batch/state",
        )
        chk(
            len(stopped_fail_recs) == 1
            and stopped_fail_recs[0]["status"] == "stopped"
            and any(failed_assign_recs[0]["session"] in c for c in stop_calls3),
            "colab stop -s <failed_session> called and assignment drop verified",
        )
        chk(json.loads(state3_p.read_text())["sessions"] == {}, "no leaked sessions remain in fake colab")

        # 4. Account-level usage watchdog (empty registry + usage>0 => ALERT, no auto-stop).
        print("4) Account-level usage watchdog")
        d4 = tmp_root / "case4"
        d4.mkdir()
        # 4a: empty registry, usage > 0, no local sessions (other machine's VM!)
        env4a, _, log4a = make_fake_env(d4 / "a", {
            "balance": 200.0, "sessions": {}, "extra_assignments": 1, "override_usage_rate": 2.33,
        })
        alerts4a = d4 / "a" / "colab_alerts.log"
        r = run_cmd([
            "bash", str(ORCH), "--watchdog-once",
            "--registry", str(d4 / "a" / "empty_registry.jsonl"),
            "--alerts-log", str(alerts4a),
            "--log", str(d4 / "a" / "w.log"),
        ], env=env4a)
        calls4a = read_calls(log4a)
        chk(
            r.returncode == 0
            and alerts4a.is_file()
            and "ALERT" in alerts4a.read_text(encoding="utf-8")
            and "usage_or_assignments_without_live_registered_session" in alerts4a.read_text(encoding="utf-8")
            and not any(c and c[0] == "stop" for c in calls4a),
            "watchdog: usage>0 with empty registry writes ALERT and NEVER calls colab stop",
        )

        # 4b: unknown session visible in `colab sessions` -> ALERT, no auto-stop
        env4b, _, log4b = make_fake_env(d4 / "b", {
            "balance": 200.0,
            "sessions": {"owner-notebook": {"endpoint": "gpu-a100-owner-1", "gpu": "A100"}},
        })
        alerts4b = d4 / "b" / "colab_alerts.log"
        r = run_cmd([
            "bash", str(ORCH), "--watchdog-once",
            "--registry", str(d4 / "b" / "empty_registry.jsonl"),
            "--alerts-log", str(alerts4b),
            "--log", str(d4 / "b" / "w.log"),
        ], env=env4b)
        calls4b = read_calls(log4b)
        chk(
            r.returncode == 0
            and alerts4b.is_file()
            and "ALERT" in alerts4b.read_text(encoding="utf-8")
            and "owner-notebook" in alerts4b.read_text(encoding="utf-8")
            and not any(c and c[0] == "stop" for c in calls4b),
            "watchdog: unknown live session writes ALERT and NEVER auto-stops it",
        )

        # 4c: registered active session matches `colab sessions` and assignments == 1 -> NO alert
        env4c, _, _ = make_fake_env(d4 / "c", {
            "balance": 200.0,
            "sessions": {"redo-known-1": {"endpoint": "gpu-l4-known-1", "gpu": "L4"}},
        })
        reg4c = d4 / "c" / "reg.jsonl"
        reg4c.write_text(json.dumps({
            "ts": "2026-11-27T06:00:00Z", "event": "launched", "status": "active",
            "session": "redo-known-1", "endpoint": "gpu-l4-known-1", "gpu": "L4",
            "batch": "b1", "state": "/tmp/s.json",
        }) + "\n", encoding="utf-8")
        alerts4c = d4 / "c" / "colab_alerts.log"
        r = run_cmd([
            "bash", str(ORCH), "--watchdog-once",
            "--registry", str(reg4c), "--alerts-log", str(alerts4c),
            "--log", str(d4 / "c" / "w.log"),
        ], env=env4c)
        chk(r.returncode == 0 and not alerts4c.exists(),
            "watchdog: matching active registered session emits NO alert")

        # 4d: 1 registered session + 1 extra unknown assignment => ALERT, no auto-stop
        env4d, _, log4d = make_fake_env(d4 / "d", {
            "balance": 200.0,
            "sessions": {"redo-known-1": {"endpoint": "gpu-l4-known-1", "gpu": "L4"}},
            "extra_assignments": 1,
        })
        reg4d = d4 / "d" / "reg.jsonl"
        shutil.copyfile(reg4c, reg4d)
        alerts4d = d4 / "d" / "colab_alerts.log"
        r = run_cmd([
            "bash", str(ORCH), "--watchdog-once",
            "--registry", str(reg4d), "--alerts-log", str(alerts4d),
            "--log", str(d4 / "d" / "w.log"),
        ], env=env4d)
        calls4d = read_calls(log4d)
        chk(
            r.returncode == 0
            and alerts4d.is_file()
            and "active_assignments_exceed_live_registered_sessions" in alerts4d.read_text(encoding="utf-8")
            and not any(c and c[0] == "stop" for c in calls4d),
            "watchdog: excess account assignments emits ALERT and NEVER auto-stops",
        )

        # 5. Queue mode + A100->G4->L4 fallback + TooManyAssignments + partial fetch + --reuse-session + release.
        print("5) Queue mode: GPU order, TooManyAssignments fallback, partial fetch, --reuse-session, release")
        d5 = tmp_root / "case5"
        d5.mkdir()
        env5, state5_p, log5_p = make_fake_env(d5, {
            "balance": 240.0,
            "sessions": {},
            "reject_gpus": ["A100", "G4"],  # Forces fallback order A100 -> G4 -> L4
            "max_assignments": 1,           # Forces 2nd concurrent VM attempt to hit TooManyAssignments
            "polls_until_done": 2,          # Poll 1: not done -> partial fetch runs; Poll 2: BATCH_DONE!
        })
        q5 = d5 / "queue.json"
        q5.write_text(json.dumps({
            "schema": "vacant.redo.colab.queue/1",
            "defaults": {"preferred_gpus": ["A100", "G4", "L4"], "max_concurrent_vms": 2},
            "batches": [
                {"id": "q5_b1", "plan": str(plan), "bank": str(bank), "vllm_config": str(vcfg), "allow_uncommitted_plan": True},
                {"id": "q5_b2", "plan": str(plan), "bank": str(bank), "vllm_config": str(vcfg), "allow_uncommitted_plan": True},
            ],
        }) + "\n", encoding="utf-8")
        reg5 = d5 / "colab_registry.jsonl"
        alerts5 = d5 / "colab_alerts.log"
        runlog5 = d5 / "run.log"
        r = run_cmd([
            "bash", str(ORCH), "--queue", str(q5),
            "--registry", str(reg5), "--alerts-log", str(alerts5),
            "--log", str(runlog5), "--out-root", str(d5 / "out"),
            "--rent-interval", "0", "--poll-interval", "0", "--partial-fetch-interval", "0",
            "--tick-interval", "0", "--stop-retry-delay", "0", "--watchdog-interval", "2",
        ], env=env5)
        calls5 = read_calls(log5_p)
        regs5 = read_jsonl(reg5)
        q5_after = json.loads(q5.read_text(encoding="utf-8"))
        log5_txt = runlog5.read_text(encoding="utf-8")
        new_gpus = [c[c.index("--gpu") + 1] for c in calls5 if c and c[0] == "new" and "--gpu" in c]
        chk(r.returncode == 0, f"case5 completed 2-batch queue cleanly (rc={r.returncode})")
        chk(new_gpus[:3] == ["A100", "G4", "L4"], f"rent order respected A100->G4->L4 (saw {new_gpus[:3]})")
        chk("too-many-assignments" in log5_txt.lower(), "TooManyAssignments on 2nd concurrent VM logged gracefully")
        chk("partial fetch OK" in log5_txt, "periodic partial fetch (`fetch_batch.sh --force --no-stop`) ran and succeeded")
        chk(
            q5_after["batches"][0]["status"] == "done"
            and q5_after["batches"][1]["status"] == "done"
            and q5_after["batches"][0]["session"] == q5_after["batches"][1]["session"],
            "batch 2 reused the EXACT same session as batch 1 without releasing VM",
        )
        chk(
            [x["event"] for x in regs5] == ["launched", "reused", "released_queue_empty"],
            f"registry lifecycle recorded launched -> reused -> released_queue_empty (got {[x['event'] for x in regs5]})",
        )
        chk("verified account usage is 0" in log5_txt and json.loads(state5_p.read_text())["sessions"] == {},
            "VM released only after queue empty and usage verified 0")

        # 6. Two concurrent VMs when account allows max_assignments=2.
        print("6) Concurrent 2nd VM rental")
        d6 = tmp_root / "case6"
        d6.mkdir()
        env6, state6_p, _ = make_fake_env(d6, {
            "balance": 240.0,
            "sessions": {},
            "max_assignments": 2,
            "polls_until_done": 1,
        })
        q6 = d6 / "queue.json"
        q6.write_text(json.dumps({
            "schema": "vacant.redo.colab.queue/1",
            "defaults": {"preferred_gpus": ["A100", "G4", "L4"], "max_concurrent_vms": 2},
            "batches": [
                {"id": "c6_b1", "plan": str(plan), "bank": str(bank), "vllm_config": str(vcfg), "allow_uncommitted_plan": True},
                {"id": "c6_b2", "plan": str(plan), "bank": str(bank), "vllm_config": str(vcfg), "allow_uncommitted_plan": True},
            ],
        }) + "\n", encoding="utf-8")
        reg6 = d6 / "colab_registry.jsonl"
        r = run_cmd([
            "bash", str(ORCH), "--queue", str(q6),
            "--registry", str(reg6), "--alerts-log", str(d6 / "alerts.log"),
            "--log", str(d6 / "run.log"), "--out-root", str(d6 / "out"),
            "--rent-interval", "0", "--poll-interval", "0", "--partial-fetch-interval", "9999",
            "--tick-interval", "0", "--stop-retry-delay", "0", "--no-watchdog",
        ], env=env6)
        q6_after = json.loads(q6.read_text(encoding="utf-8"))
        chk(
            r.returncode == 0
            and q6_after["batches"][0]["status"] == "done"
            and q6_after["batches"][1]["status"] == "done"
            and q6_after["batches"][0]["session"] != q6_after["batches"][1]["session"]
            and json.loads(state6_p.read_text())["sessions"] == {},
            "2 concurrent VMs rented simultaneously, both completed, both released",
        )

        # 7a. Spend cap breach (180 CU spent from start balance) => partial fetch + stop + ALERT + exit 10.
        print("7) Spend cap (180 CU) and balance floor (20 CU) enforcement")
        d7a = tmp_root / "case7a"
        d7a.mkdir()
        # usage calls: 1=startup(250), 2=loop1 budget(250), 3=pre-rent budget(250), 4=before_usage(250), 5=after_usage(250), 6=loop2 budget(69 -> spent 181 >= 180!)
        env7a, state7a_p, log7a_p = make_fake_env(d7a, {
            "balance": 250.0,
            "balance_schedule": [250.0, 250.0, 250.0, 250.0, 250.0, 69.0, 69.0, 69.0],
            "sessions": {},
            "max_assignments": 1,
            "polls_until_done": 99,
        })
        q7a = d7a / "queue.json"
        q7a.write_text(json.dumps({
            "schema": "vacant.redo.colab.queue/1",
            "batches": [
                {"id": "c7a_b1", "plan": str(plan), "bank": str(bank), "vllm_config": str(vcfg),
                 "preferred_gpus": ["A100"], "allow_uncommitted_plan": True},
            ],
        }) + "\n", encoding="utf-8")
        alerts7a = d7a / "colab_alerts.log"
        runlog7a = d7a / "run.log"
        r = run_cmd([
            "bash", str(ORCH), "--queue", str(q7a),
            "--registry", str(d7a / "reg.jsonl"), "--alerts-log", str(alerts7a),
            "--log", str(runlog7a), "--out-root", str(d7a / "out"),
            "--max-spend", "180", "--balance-floor", "20",
            "--rent-interval", "0", "--poll-interval", "0", "--partial-fetch-interval", "9999",
            "--tick-interval", "0", "--stop-retry-delay", "0", "--no-watchdog",
        ], env=env7a)
        calls7a = read_calls(log7a_p)
        chk(
            r.returncode == 10
            and alerts7a.is_file()
            and "budget_breach" in alerts7a.read_text(encoding="utf-8")
            and "spent=181.0>=max_spend=180.0" in alerts7a.read_text(encoding="utf-8")
            and any(c and c[0] == "stop" for c in calls7a)
            and "emergency partial fetch before stop" in runlog7a.read_text(encoding="utf-8")
            and json.loads(state7a_p.read_text())["sessions"] == {},
            "spend cap 180 CU breach triggers partial fetch, stop, ALERT, and exit 10",
        )

        # 7b. Balance floor breach (<= 20 CU) => partial fetch + stop + ALERT + exit 10.
        d7b = tmp_root / "case7b"
        d7b.mkdir()
        env7b, state7b_p, log7b_p = make_fake_env(d7b, {
            "balance": 100.0,
            "balance_schedule": [100.0, 100.0, 100.0, 100.0, 100.0, 19.5, 19.5, 19.5],
            "sessions": {},
            "max_assignments": 1,
            "polls_until_done": 99,
        })
        q7b = d7b / "queue.json"
        q7b.write_text(json.dumps({
            "schema": "vacant.redo.colab.queue/1",
            "batches": [
                {"id": "c7b_b1", "plan": str(plan), "bank": str(bank), "vllm_config": str(vcfg),
                 "preferred_gpus": ["L4"], "allow_uncommitted_plan": True},
            ],
        }) + "\n", encoding="utf-8")
        alerts7b = d7b / "colab_alerts.log"
        r = run_cmd([
            "bash", str(ORCH), "--queue", str(q7b),
            "--registry", str(d7b / "reg.jsonl"), "--alerts-log", str(alerts7b),
            "--log", str(d7b / "run.log"), "--out-root", str(d7b / "out"),
            "--max-spend", "180", "--balance-floor", "20",
            "--rent-interval", "0", "--poll-interval", "0", "--partial-fetch-interval", "9999",
            "--tick-interval", "0", "--stop-retry-delay", "0", "--no-watchdog",
        ], env=env7b)
        calls7b = read_calls(log7b_p)
        chk(
            r.returncode == 10
            and alerts7b.is_file()
            and "balance=19.5<=floor=20.0" in alerts7b.read_text(encoding="utf-8")
            and any(c and c[0] == "stop" for c in calls7b)
            and json.loads(state7b_p.read_text())["sessions"] == {},
            "balance floor 20 CU breach triggers partial fetch, stop, ALERT, and exit 10",
        )
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    failed = [m for ok, m in checks if not ok]
    print(f"\nVERDICT: {'COLAB_RENT_AND_RUN_OK' if not failed else 'COLAB_RENT_AND_RUN_FAIL'} ({len(checks) - len(failed)}/{len(checks)})")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
