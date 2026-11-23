"""以隔離的 OpenCode 執行及獨立評分重驗 R3；承接 PROTOCOL.md 的 Arms、Ordering 與 Outcome。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
from queue import Queue
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
from threading import Event, Lock
import time
import uuid

import bank

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))
import redo  # noqa: E402

IMAGE = "python@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df"
LLAMA_IMAGE = "ghcr.io/ggml-org/llama.cpp@sha256:c2cf6c72d913b6c89a5f0929f2a866e6161e09e7dc187e0f3b0f21e923e26db3"
VERSION = "1.18.33"
BINARY_SHA = "0abbb7c32ab0294c0a7bfa2705f9ff0df5dce5ab721d1f00cccfe393f2a11427"
RG_SHA = "c2e9783ac04b502122a78ad2154c992719d4a73b5001b19202853a4106738b03"
MODEL = "local/qwen3-coder-30b-a3b"
MODEL_SHA = "fadc3e5f8d42bf7e894a785b05082e47daee4df26680389817e2093056f088ad"
NETWORK = "hard-r3-inference"
TRACE_HOST = "http://hard-r3-trace:8080"
SLOTS = 4
DOCKER_LABEL = f"vacant.hard-r3={uuid.uuid4().hex}"
DOCKER_STOP = Event()
DOCKER_LAUNCH = Lock()
SERVER_ARGS = (
    "--host 0.0.0.0 --port 8080 --model /model/model.gguf --alias qwen3-coder-30b-a3b "
    f"--n-gpu-layers 0 --ctx-size 65536 --parallel {SLOTS} --threads 8 --threads-batch 8 "
    "--jinja --n-predict 4096 --no-cache-prompt --cache-ram 0 --ctx-checkpoints 0 "
    "--temp 0.7 --top-p 0.8 --top-k 20 --min-p 0 --repeat-penalty 1.05 --seed -1 --no-webui"
).split()
SCRIPTS = [HERE / f for f in ("run.py", "bank.py", "plan.json", "judge.py", "trace_proxy.py", "archive.py",
                              "PROTOCOL.md")] + [HERE.parent / "redo.py"]
CONFIG = {
    "autoupdate": False, "share": "disabled", "enabled_providers": ["local"],
    "permission": {"*": "deny", "bash": "allow", "read": "allow"},
    "agent": {"build": {"prompt": "Implement the user's task in the current workspace. "
                                 "Use the bash tool to write the solution before running the provided test. "
                                 "Use only local files and commands; do not edit the test."}},
}
PROMPT = """Implement the specified solution in solution.py. Use only Python 3.12 standard library.
Do not modify tests or create other deliverables. The final deliverable is only solution.py.
Provide solve(data), which receives decoded JSON and returns the requested JSON-serializable value.
Do not use the network. Run python test_visible.py locally to check your work.
The visible examples are not exhaustive. Each grading case has a 4-second process time limit
on one CPU. Times and memory required by your algorithm count toward grading.

"""
STARTER = "def solve(data):\n    raise NotImplementedError\n"
INFRA = re.compile(r"usage limit|rate.?limit|too many requests|cannot connect to API|ECONN[A-Z]+|"
                   r"ENOTFOUND|(?:internal|unexpected) server error|service (?:overloaded|unavailable)|"
                   r"bad gateway|gateway timeout|loading model", re.I)


def runtime(binary: Path, rg: Path) -> list[str]:
    if not binary.is_file() or hashlib.sha256(binary.read_bytes()).hexdigest() != BINARY_SHA:
        raise SystemExit(f"Use the pinned OpenCode {VERSION} baseline binary; SHA-256 must be {BINARY_SHA}")
    image = subprocess.run(["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"],
                           check=True, capture_output=True, text=True).stdout.strip()
    if not image:
        raise SystemExit("Pinned Docker image is not installed")
    if hashlib.sha256(rg.read_bytes()).hexdigest() != RG_SHA:
        raise SystemExit(f"Use the pinned ripgrep binary ({RG_SHA})")
    info = subprocess.run(["docker", "inspect", "hard-r3-model"], check=True, capture_output=True, text=True)
    server = json.loads(info.stdout)[0]
    if server["Config"]["Image"] != LLAMA_IMAGE or not server["State"]["Running"]:
        raise SystemExit("The pinned local inference container must be running")
    if server["Args"] != SERVER_ARGS:
        raise SystemExit(f"Unexpected local inference configuration: {server['Args']}")
    internal = subprocess.check_output(["docker", "network", "inspect", NETWORK, "--format", "{{.Internal}}"],
                                       text=True).strip()
    if internal != "true":
        raise SystemExit("Agent network must be internal")
    weights = next(m for m in server["Mounts"] if m["Destination"] == "/model/model.gguf")
    with Path(weights["Source"]).open("rb") as gguf:
        if hashlib.file_digest(gguf, "sha256").hexdigest() != MODEL_SHA:
            raise SystemExit("Model weights do not match the pinned GGUF SHA-256")
    return [f"runtime: Docker image {image}", f"runtime: OpenCode {VERSION} sha256 {BINARY_SHA}",
            f"runtime: {platform.machine()} uid {os.getuid()}", f"runtime: llama.cpp args {server['Args']}"]


def agent_config(trace_id: str, slot: int) -> dict:
    return {
        **CONFIG,
        "model": MODEL,
        "small_model": MODEL,
        "provider": {"local": {
            "npm": "@ai-sdk/openai-compatible", "name": "Local llama.cpp",
            "options": {"baseURL": f"{TRACE_HOST}/{trace_id}/{slot}/v1", "includeUsage": True},
            "models": {MODEL.split("/")[1]: {
                "name": "Qwen3-Coder-30B-A3B-Instruct", "limit": {"context": 16384, "output": 4096},
            }},
        }},
    }


def docker(work: Path, command: list[str], timeout: float, log: Path, *,
           binary: Path | None = None, rg: Path = Path("/usr/bin/rg"),
           config: dict | None = None, stdin: bytes | None = None) -> dict:
    name = f"hard-r3-{uuid.uuid4().hex}"
    agent = binary is not None
    cmd = ["docker", "run", "--rm", "--name", name, "--label", DOCKER_LABEL, "--pull", "never", "--read-only",
           "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--pids-limit", "128",
           "--memory", "1g", "--cpus", "1", "--user", f"{os.getuid()}:{os.getgid()}",
           "--network", NETWORK if agent else "none", "--tmpfs", "/tmp:rw,nosuid,nodev,size=256m",
           "-e", "HOME=/tmp", "-e", "XDG_CONFIG_HOME=/tmp/config",
           "-e", "XDG_DATA_HOME=/tmp/data", "-e", "PYTHONHASHSEED=0",
           "-v", f"{work}:/work:{'rw' if agent else 'ro'}", "-w", "/work"]
    if agent:
        cmd += ["-v", f"{binary}:/usr/local/bin/opencode:ro", "-e", "OPENCODE_DISABLE_AUTOUPDATE=1",
                "-v", f"{rg}:/usr/local/bin/rg:ro",
                "-e", "OPENCODE_DISABLE_LSP_DOWNLOAD=1", "-e", "OPENCODE_DISABLE_MODELS_FETCH=1",
                "-e", "OPENCODE_CONFIG_CONTENT=" + json.dumps(config)]
    if stdin is not None:
        cmd += ["-i"]
    start = time.monotonic()
    with log.open("wb") as stdout, log.with_suffix(log.suffix + ".stderr").open("wb") as stderr:
        with DOCKER_LAUNCH:
            if DOCKER_STOP.is_set():
                raise RuntimeError("experiment interrupted")
            proc = subprocess.Popen([*cmd, IMAGE, *command], stdout=stdout, stderr=stderr,
                                    stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                                    start_new_session=True)
            redo._track(proc, True)
        try:
            proc.communicate(input=stdin, timeout=timeout)
            return {"rc": proc.returncode, "timed_out": False, "wall_s": round(time.monotonic() - start, 3)}
        except subprocess.TimeoutExpired:
            wall = time.monotonic() - start
            proc.kill()
            proc.communicate()
            remove_containers([name])
            return {"rc": None, "timed_out": True, "wall_s": round(wall, 3)}
        finally:
            redo._track(proc, False)


def remove_containers(names: list[str]):
    if names:
        subprocess.run(["docker", "rm", "-f", *names], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=15, check=False)


def stop_docker():
    with DOCKER_LAUNCH:
        DOCKER_STOP.set()
        redo.kill_all_live()
    active = subprocess.check_output(["docker", "ps", "-aq", "--filter", f"label={DOCKER_LABEL}"],
                                     text=True, timeout=15)
    remove_containers(active.split())


def emit_json(path: Path, val) -> None:
    path.write_text(json.dumps(val, ensure_ascii=True, sort_keys=True, allow_nan=False), encoding="utf-8")


def canonical(val):
    return json.dumps(val, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def visible_script(task: str) -> str:
    encoded = canonical(bank.suite(task, False))
    return (
        "import json\nfrom solution import solve\n\n"
        f"cases = json.loads({encoded!r})\n"
        "n = 0\nfor example, expected in cases:\n"
        "    actual = solve(example)\n"
        "    assert json.dumps(actual, sort_keys=True) == json.dumps(expected, sort_keys=True), "
        "(example, expected, actual)\n"
        "    n += 1\nprint(f'{n} checks passed')\n"
    )


def usage_from_events(log: Path) -> tuple[dict | None, list[dict]]:
    steps, errors = [], []
    for line in log.read_bytes().splitlines():
        try:
            event = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if event.get("type") == "step_finish" and event.get("part", {}).get("tokens") is not None:
            steps.append(event["part"])
        elif event.get("type") == "error":
            errors.append(event["error"])
    if not steps and not errors:
        return None, errors
    keys = ("input", "output", "reasoning", "total")
    tokens = {k: sum(step["tokens"].get(k) or 0 for step in steps) for k in keys}
    for k in ("read", "write"):
        tokens[f"cache_{k}"] = sum((step["tokens"].get("cache") or {}).get(k) or 0 for step in steps)
    return {"calls": len(steps) or None, "calls_are_observed_completed_steps": True,
            "tokens": tokens if steps else None,
            "reported_cost": sum(step.get("cost") or 0 for step in steps) if steps else None,
            "final_error": errors[-1].get("name", "AgentError") if errors else None}, errors


def attempt_void(result: dict, usage: dict | None, errors: list[dict]) -> bool:
    if result["rc"] in (125, 126, 127):
        return True
    if errors:
        data = errors[-1].get("data") or {}
        status = str(data.get("statusCode", ""))
        return status == "429" or bool(re.fullmatch(r"5[0-9]{2}", status)) or bool(
            INFRA.search(str(data.get("message", "")))
        )
    return usage is None and not result["timed_out"]


def safe_solution(path: Path) -> bytes | None:
    try:
        meta = path.lstat()
        if not stat.S_ISREG(meta.st_mode) or meta.st_size > 256_000:
            return None
        return path.read_bytes()
    except FileNotFoundError:
        return None


def evaluate(task: str, candidate: bytes | None, out: Path, hidden: bool) -> dict:
    name = "hidden" if hidden else "visible"
    cases = bank.suite(task, hidden)
    if candidate is None:
        return {"status": "no_solution", "passed": 0, "total": len(cases), "pass": False}
    with tempfile.TemporaryDirectory(prefix="r3-score-") as tmp:
        work = Path(tmp)
        (work / "solution.py").write_bytes(candidate)
        stdin = canonical([case for case, _ in cases]).encode()
        log = out / f"{name}.json"
        result = docker(work, ["python", "-I", "-B", "-c", (HERE / "judge.py").read_text()],
                        len(cases) * 5 + 15, log, stdin=stdin)
        if result["rc"] != 0:
            return {"status": "judge_infra", "passed": None, "total": len(cases), "pass": None, **result}
        try:
            actual = json.loads(log.read_bytes())
            if len(actual) != len(cases):
                raise ValueError("result length differs from cases")
            checks = [{"case": i, "status": a["status"],
                       "pass": a["status"] == "ok" and canonical(a["value"]) == canonical(expected)}
                      for i, (a, (_, expected)) in enumerate(zip(actual, cases, strict=True))]
        except (ValueError, TypeError, KeyError) as exc:
            return {"status": "judge_infra", "passed": None, "total": len(cases), "pass": None,
                    "error": str(exc), **result}
        n = sum(c["pass"] for c in checks)
        return {"status": "scored", "passed": n, "total": len(cases), "pass": n == len(cases),
                "checks": checks, **result}


def one_attempt(binary: Path, rg: Path, slot: int, plan, arm, tdir, provider, adir, timeout_s, hint,
                cell_id, attempt_no):
    del arm, provider, hint, cell_id, attempt_no
    task = tdir.name
    prompt = PROMPT + bank.SPECS[task]
    adir.mkdir(parents=True)
    started = redo.now()
    log = adir / "agent.jsonl"
    trace_id = uuid.uuid4().hex
    config = agent_config(trace_id, slot)
    emit_json(adir / "agent_input.json", {"model": MODEL, "config": config, "prompt": prompt, "trace_id": trace_id,
                                         "timeout_s": timeout_s, "started": started})
    with tempfile.TemporaryDirectory(prefix="r3-agent-") as tmp:
        work = Path(tmp)
        (work / "solution.py").write_text(STARTER, encoding="utf-8")
        visible = visible_script(task)
        (work / "test_visible.py").write_text(visible, encoding="utf-8")
        result = docker(work, plan["agent"]["argv"] + [prompt], timeout_s, log, binary=binary, rg=rg, config=config)
        candidate = safe_solution(work / "solution.py")
        tampered = safe_solution(work / "test_visible.py") != visible.encode()
    usage, errors = usage_from_events(log)
    meta = {"started": started, "timeout_s": timeout_s, "usage": usage, "trace_id": trace_id,
            "workspace_changed": candidate != STARTER.encode(), "agent_errors": errors, **result}
    if attempt_void(result, usage, errors):
        out = {**meta, "void": "docker_or_provider_error"}
        emit_json(adir / "attempt.json", out)
        return out

    if candidate is not None:
        (adir / "solution.py").write_bytes(candidate)
    visible = evaluate(task, candidate, adir, False)
    if visible["pass"] is None:
        out = {**meta, "void": "visible_judge_infra", "visible": visible}
        emit_json(adir / "attempt.json", out)
        return out
    hidden = evaluate(task, candidate, adir, True)
    acc = {"accept": visible["pass"], "passed": visible["passed"], "run": visible["total"],
           "tests_tampered": ["test_visible.py"] if tampered else [],
           "status": visible["status"], "visible_detail": visible}
    grade = {"pass": hidden["pass"], "grader_kind": "independent_hidden_cases", "detail": hidden}
    return {**meta, "void": None, "acc": acc, "grade": grade}


def preflight(out: Path):
    manual = {
        "mesh": [True, 2, False],
        "cache": [True, True, False, 2, None, True],
        "intervals": [9, ["a", "x"]],
        "route": [5, 4, ["a", "b"]],
        "spans": {"a": 5, "b": 7},
        "patch": {"text": "aöXQ!d", "rejected": []},
        "rank": [[2, -3, 0, "-3/2"], [1, 0, None, "0"], [0, 0, None, None]],
        "reconcile": {"a": 0, "b": 1, "d": 2},
    }
    summaries = {}

    def fixture_stub(cases):
        return (
            f"import json\nrows = json.loads({canonical(cases)!r})\n"
            "def solve(data):\n"
            "    for case, expected in rows:\n"
            "        if data == case:\n"
            "            return expected\n"
            "    return None\n"
        ).encode()

    for task in bank.SPECS:
        visible = bank.suite(task, False)
        hidden = bank.suite(task, True)
        positive_stub = fixture_stub(visible)
        dest = out / task
        dest.mkdir()
        assert canonical(visible[0][1]) == canonical(manual[task]), task
        assert not {canonical(x) for x, _ in visible}.intersection(canonical(x) for x, _ in hidden), task
        assert evaluate(task, positive_stub, dest, False)["pass"] is True, task
        assert evaluate(task, positive_stub, dest, True)["pass"] is False, task
        negative = dest / "unimplemented"
        negative.mkdir()
        assert evaluate(task, STARTER.encode(), negative, False)["pass"] is False, task
        hidden_dest = dest / "hidden_fixture"
        hidden_dest.mkdir()
        assert evaluate(task, fixture_stub(hidden), hidden_dest, True)["pass"] is True, task
        summaries[task] = {"manual_example_match": True, "visible_cases": len(visible),
                           "hidden_cases": len(hidden), "visible_fixture_stub_pass": True,
                           "visible_fixture_stub_hidden_pass": False, "unimplemented_stub_pass": False,
                           "hidden_fixture_stub_pass": True,
                           "visible_hash": hashlib.sha256(canonical(visible).encode()).hexdigest(),
                           "hidden_hash": hashlib.sha256(canonical(hidden).encode()).hexdigest()}
    emit_json(out / "PREFLIGHT.json", summaries)
    print(f"Preflight controls passed: {len(summaries)} tasks")


def run(out: Path, binary: Path, rg: Path):
    msgs = runtime(binary, rg)
    dirty = redo._git(["status", "--porcelain", "--", *(str(p) for p in SCRIPTS)], REPO)
    if dirty is None or dirty:
        raise SystemExit("Commit every experiment input before running")
    redo.HARNESS_SHA = redo.sha256_bytes(redo.canonical({p.name: redo.sha256_bytes(p.read_bytes()) for p in SCRIPTS}))
    slots = Queue()
    for slot in range(SLOTS):
        slots.put(slot)

    def slotted_attempt(*args):
        slot = slots.get()
        try:
            return one_attempt(binary, rg, slot, *args)
        finally:
            slots.put(slot)

    redo.one_attempt = slotted_attempt
    out.mkdir(parents=True, exist_ok=False)
    controls = out / "preflight"
    controls.mkdir()
    preflight(controls)
    emit_json(out / "runtime.json", {"runtime": msgs, "image": IMAGE, "agent_version": VERSION,
                                    "llama_image": LLAMA_IMAGE, "gguf_sha256": MODEL_SHA, "rg_sha256": RG_SHA,
                                    "opencode_sha256": BINARY_SHA, "model_alias": MODEL,
                                    "files": {str(p.relative_to(REPO)): redo.sha256_bytes(p.read_bytes()) for p in SCRIPTS}})
    with tempfile.TemporaryDirectory(prefix="r3-bank-") as tmp:
        for task in bank.SPECS:
            (Path(tmp) / task / "workspace").mkdir(parents=True)
        rc = redo.cmd_run(argparse.Namespace(plan=str(HERE / "plan.json"), root=str(out), bank=tmp,
                                            only_tasks=None, only_reps=None, max_pairs=None,
                                            allow_uncommitted_plan=False))
    report_path = out / "REPORT.json"
    if rc == 0 and report_path.is_file():
        report = json.loads(report_path.read_bytes())
        if report["pairs_scored"] != report["pairs_planned"]:
            report["state"] = "INCOMPLETE"
            redo.write_json(report_path, report)
            (out / "REPORT.md").write_text(redo.render_md(report), encoding="utf-8")
    return rc


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["preflight", "run", "regrade", "server-args"])
    p.add_argument("out", type=Path, nargs="?")
    p.add_argument("--opencode", type=Path)
    p.add_argument("--rg", default=Path("/usr/bin/rg"), type=Path)
    p.add_argument("--verify-output", type=Path, help="Output directory for offline replay")
    a = p.parse_args()
    if a.action == "server-args":
        print(" ".join(SERVER_ARGS))
        return 0
    if a.out is None:
        p.error("an output directory is required")
    out = a.out.resolve()
    if a.action == "preflight":
        out.mkdir(parents=True, exist_ok=False)
        preflight(out)
    elif a.action == "run":
        if a.opencode is None:
            p.error("--opencode is required for a live run")
        return run(out, a.opencode.resolve(), a.rg.resolve())
    else:
        if a.verify_output is None:
            p.error("--verify-output is required to keep evidence immutable")
        a.verify_output.mkdir(parents=True, exist_ok=False)
        mismatches, verified = [], []
        count = 0
        for attempt in sorted(out.glob("cells/*/r*/[AR]*/attempt_*/attempt.json")):
            task = attempt.relative_to(out).parts[1]
            original = json.loads(attempt.read_bytes())
            if original["void"]:
                continue
            dest = a.verify_output / attempt.parent.relative_to(out)
            dest.mkdir(parents=True)
            candidate = safe_solution(attempt.with_name("solution.py"))
            vis, hidden = evaluate(task, candidate, dest, False), evaluate(task, candidate, dest, True)
            count += 1
            verified.append(str(attempt.relative_to(out)))
            if (vis["pass"], vis["passed"], hidden["pass"], hidden["passed"]) != (
                original["acc"]["accept"], original["acc"]["passed"], original["grade"]["pass"],
                original["grade"]["detail"]["passed"]
            ):
                mismatches.append(str(attempt.relative_to(out)))
        emit_json(a.verify_output / "REPLAY.json", {"attempts": count, "verified": verified,
                                                   "mismatches": mismatches})
        print(f"Regraded {count} attempts; {len(mismatches)} mismatches")
        return int(not count or bool(mismatches))


def interrupt(signum, frame):
    raise KeyboardInterrupt


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("preflight", "run", "regrade"):
        signal.signal(signal.SIGTERM, interrupt)
        signal.signal(signal.SIGHUP, interrupt)
        try:
            sys.exit(main())
        except KeyboardInterrupt:
            sys.exit(130)
        finally:
            stop_docker()
    sys.exit(main())
