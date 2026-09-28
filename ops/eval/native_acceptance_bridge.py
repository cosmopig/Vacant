#!/usr/bin/env python3
"""Bridge an existing native coding agent to Vacant's executable acceptance path.

This is an evaluator/receiver-side helper. It never calls a model and it does
not replace Pi, Claude Code, Codex, OpenCode, or another agent platform.

The bridge registers a machine-readable contract whose visible suite is pinned
*before* the agent runs. The normal native-agent hook can then call
`flow.check` at settle time (repair mode), while the outer evaluator performs
the authoritative synchronous `submit` / `release`.

Recommended C5 layout:

- /app/tests_visible: agent-readable copy used by run_tests.sh;
- --receiver-home: a fresh evaluator-owned home per run, outside /app, held by
  a separate OS account. The bridge pins a readable suite beside this home.

Repair arm:

    python ops/eval/native_acceptance_bridge.py prepare \
      --workspace /app --task-id "$TASK" --mode repair \
      --receiver-home "/srv/eval/receiver/$TASK/vacant"
    # run the normal native agent in /app
    python ops/eval/native_acceptance_bridge.py judge \
      --workspace /app --attempt 1 \
      --receiver-home "/srv/eval/receiver/$TASK/vacant"
    python ops/eval/native_acceptance_bridge.py release \
      --workspace /app --artifact "<sha from accepting judge>" \
      --receiver-home "/srv/eval/receiver/$TASK/vacant"

For CONFORM, prepare with --mode conform. The *outer harness* must start a
fresh full native-agent session after every non-accepting judge result, passing
--attempt 1..N. This helper deliberately has no model API or router.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import pathlib
import re
import shutil
import sys
import uuid
from typing import Any, Iterator

from vacant_network.intake import contract as C
from vacant_network.intake import flow
from vacant_network.intake import approval
from vacant_network.vrun.acceptance import declared_cases, test_files

EXIT = {"accept": 0, "reject": 40, "hold": 41, "escalate": 42, "void": 43,
        "release_refused": 44}
MODES = ("gate", "repair", "conform")


def _task_id(raw: str) -> str:
    out = re.sub(r"[^A-Za-z0-9._-]+", "-", raw.strip()).strip("-._")
    if not out:
        raise ValueError("task id is empty after normalization")
    if len(out) > 128:
        out = out[:128].rstrip("-._")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", out):
        raise ValueError(f"invalid task id {out!r}")
    return out


def _receiver_root(receiver_home: pathlib.Path | None) -> pathlib.Path | None:
    """The receiver's signing home is mandatory, never Vacant's ambient home."""
    if receiver_home is None:
        raise ValueError("--receiver-home is required for every bridge operation")
    return receiver_home.resolve() / "intake"


@contextlib.contextmanager
def _serialized(receiver_home: pathlib.Path | None) -> Iterator[None]:
    if receiver_home is None:
        raise ValueError("--receiver-home is required")
    with (receiver_home.resolve() / "bridge.lock").open("a+b") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _inside(path: pathlib.Path, directory: pathlib.Path) -> bool:
    return path.resolve().is_relative_to(directory.resolve())


def _boundary(workspace: pathlib.Path, receiver_home: pathlib.Path,
              *, insecure_same_account: bool = False) -> None:
    if _inside(receiver_home, workspace) or _inside(workspace, receiver_home):
        raise ValueError("receiver home and agent workspace must be separate")
    # The receiver must be a different OS account. Workspace ownership is the
    # default agent identity; an evaluator can opt into a non-adversarial run.
    if (workspace.stat().st_uid == os.geteuid() and not insecure_same_account):
        raise ValueError("same-account bridge requires --insecure-same-account; "
                         "run the receiver as a separate OS account for enforcement")


def _destination(value: str | None, workspace: pathlib.Path,
                 receiver_home: pathlib.Path) -> str:
    value = value or f"dir:{receiver_home / 'released'}"
    if not value.startswith("dir:"):
        raise ValueError("bridge destination must be an evaluator-owned dir:")
    path = pathlib.Path(value[4:]).expanduser()
    path = (path if path.is_absolute() else workspace / path).resolve()
    if not _inside(path, receiver_home) or _inside(receiver_home, path):
        raise ValueError("release destination must be inside receiver home")
    return f"dir:{path}"


def _suite_files(suite: pathlib.Path) -> list[pathlib.Path]:
    files = test_files(suite)
    nested = [p for p in suite.rglob("test_*.py") if p.is_file() and p.parent != suite]
    if nested:
        raise ValueError(f"nested test files would not run: {nested[0]}")
    if not files:
        raise ValueError(f"visible suite has no top-level test_*.py files: {suite}")
    for p in files:
        if not declared_cases(p):
            raise ValueError(f"test file needs top-level check_* or main: {p}")
    return files


def _snapshot_suite(suite: pathlib.Path, receiver_home: pathlib.Path) -> pathlib.Path:
    """Copy before pinning; publish a read-only agent-readable suite beside home."""
    source_hash = C.path_sha256(suite)
    if any(p.is_symlink() for p in suite.rglob("*")):
        raise ValueError("suite symlinks are not allowed")
    target = receiver_home.with_name(receiver_home.name + "-suite")
    if target.exists():
        raise ValueError(f"receiver suite already exists: {target}; use a fresh receiver home")
    temp = target.with_name(target.name + f".tmp-{uuid.uuid4().hex}")
    try:
        shutil.copytree(suite, temp, symlinks=False)
        if C.path_sha256(temp) != source_hash or C.path_sha256(suite) != source_hash:
            raise ValueError("suite changed while being snapshotted")
        _suite_files(temp)
        for p in temp.rglob("*"):
            p.chmod(0o555 if p.is_dir() else 0o444)
        temp.chmod(0o555)
        temp.rename(target)
    finally:
        if temp.exists():
            shutil.rmtree(temp)
    return target


def _readable_by_agent(suite: pathlib.Path) -> bool:
    """Conservative check for the repair hook running under another UID."""
    if any(not p.stat().st_mode & 0o004 for p in suite.rglob("*") if p.is_file()):
        return False
    return all(p.stat().st_mode & 0o001 for p in (suite, *suite.parents))


def _input_path(workspace: pathlib.Path, suite: pathlib.Path) -> str:
    """Prefer a stable relative path; receiver-owned external suites stay absolute."""
    try:
        return suite.resolve().relative_to(workspace.resolve()).as_posix()
    except ValueError:
        return str(suite.resolve())


def build_contract(*, workspace: pathlib.Path, task_id: str,
                   suite: pathlib.Path | None = None,
                   deliverable: str = "solution.py", mode: str = "repair",
                   attempts: int | None = None, feedback_rounds: int = 3,
                   suite_timeout_s: float = 60.0,
                   destination: str = "dir:.vacant/native-release") -> dict[str, Any]:
    """Build the benchmark contract. Pinning/signing is a separate receiver action."""
    workspace = workspace.resolve()
    suite = (suite or (workspace / "tests_visible")).resolve()
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    if not workspace.is_dir():
        raise ValueError(f"workspace does not exist: {workspace}")
    if not suite.is_dir():
        raise ValueError(f"visible suite does not exist: {suite}")
    _suite_files(suite)
    dpath = pathlib.PurePosixPath(deliverable)
    if not deliverable or dpath.is_absolute() or ".." in dpath.parts:
        raise ValueError("deliverable must be a safe workspace-relative path/glob")
    if attempts is None:
        attempts = 5 if mode == "conform" else 1
    if not 1 <= attempts <= 10:
        raise ValueError("attempts must be in 1..10")
    if feedback_rounds < 0:
        raise ValueError("feedback_rounds must be >= 0")
    if suite_timeout_s <= 0:
        raise ValueError("suite_timeout_s must be > 0")

    raw = C.scaffold(_task_id(task_id), deliverable=[deliverable],
                     destination=destination)
    raw["deliverable"]["exclude"].extend(["**/identity.key", "**/intake/keys/**"])
    raw["objective"] = "Produce the requested coding deliverable and pass the pinned visible suite."
    raw["inputs"] = {
        "visible_suite": {
            "path": _input_path(workspace, suite),
            "description": "Evaluator-owned visible acceptance suite; pinned before the agent runs.",
        }
    }
    raw["claims"] = [
        {
            "id": "visible_acceptance",
            "verifier": "python_checks",
            "params": {"suite": "input:visible_suite", "timeout_s": suite_timeout_s},
            "required": True,
            "authority": "requirement",
            "description": "The frozen candidate passes the evaluator-pinned visible suite.",
        }
    ]
    # Infrastructure uncertainty must not become a PASS.
    raw["unknown_policy"] = "hold"
    raw["conflict_policy"] = "escalate"
    raw["attempts"] = {"max": attempts}
    raw["hooks"] = {
        # repair: visible FAIL is fed back into the same native session.
        # gate/conform: the outer evaluator decides after synchronous judge.
        "stop_check": mode == "repair",
        "max_feedback_rounds": feedback_rounds if mode == "repair" else 0,
        # Do not race a background SessionEnd submit against the evaluator.
        "submit_on_end": False,
    }
    raw["notes"] = {
        "native_acceptance_mode": mode,
        "bridge": "ops/eval/native_acceptance_bridge.py",
        "trust_boundary": (
            "The receiver's account and destination must be inaccessible to the agent. "
            "python_checks shares a process with candidate code and is not an adversarial "
            "verifier; use a separate-process verifier or SuiteSpec for hostile code."
        ),
    }
    C.parse(raw, base_dir=workspace)
    return raw


def prepare(*, workspace: pathlib.Path, task_id: str, suite: pathlib.Path | None,
            deliverable: str, mode: str, attempts: int | None, feedback_rounds: int,
            suite_timeout_s: float, destination: str | None,
            receiver_home: pathlib.Path | None = None,
            replace: bool = False, insecure_same_account: bool = False) -> dict[str, Any]:
    workspace = workspace.resolve()
    if receiver_home is None:
        raise ValueError("--receiver-home is required")
    receiver_home = receiver_home.resolve()
    _boundary(workspace, receiver_home, insecure_same_account=insecure_same_account)
    if replace:
        raise ValueError("a run cannot be replaced; use a fresh receiver home")
    contract_path = workspace / ".vacant" / "contract.json"
    trusted_path = receiver_home / "contract.json"
    if contract_path.exists() or trusted_path.exists():
        raise ValueError("contract already exists; use a fresh workspace and receiver home")
    source_suite = (suite or workspace / "tests_visible").resolve()
    if not source_suite.is_dir():
        raise ValueError(f"visible suite does not exist: {source_suite}")
    _suite_files(source_suite)
    receiver_home.mkdir(mode=0o700, parents=True, exist_ok=True)
    receiver_home.chmod(0o700)
    parent = receiver_home.parent.stat()
    if not insecure_same_account and (parent.st_uid != os.geteuid() or parent.st_mode & 0o022):
        raise ValueError("receiver parent must be evaluator-owned and not writable by agent")
    pinned_suite = _snapshot_suite(source_suite, receiver_home)
    if mode == "repair" and not insecure_same_account and not _readable_by_agent(pinned_suite):
        raise ValueError("repair suite must be readable by the agent account")
    raw = build_contract(workspace=workspace, task_id=task_id, suite=pinned_suite,
                         deliverable=deliverable, mode=mode, attempts=attempts,
                         feedback_rounds=feedback_rounds,
                         suite_timeout_s=suite_timeout_s,
                         destination=_destination(destination, workspace, receiver_home))
    raw["notes"]["bridge_run_id"] = uuid.uuid4().hex
    raw["notes"]["bridge_workspace"] = str(workspace)
    raw["notes"]["insecure_same_account"] = insecure_same_account
    raw["notes"]["agent_visible_suite_sha256"] = C.path_sha256(source_suite)
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(raw, ensure_ascii=False, indent=2) + "\n"
    trusted_path.write_text(payload, encoding="utf-8")
    contract_path.write_text(payload, encoding="utf-8")
    root = _receiver_root(receiver_home)
    # Pins the suite and signs the contract lock before the agent gets its first prompt.
    locked = flow.lock(trusted_path, root=root)
    contract_path.write_bytes(trusted_path.read_bytes())
    c = C.load(trusted_path)
    return {
        "prepared": True,
        "mode": mode,
        "contract": str(contract_path),
        "receiver_contract": str(trusted_path),
        "run_id": raw["notes"]["bridge_run_id"],
        "insecure_same_account": insecure_same_account,
        "contract_sha256": c.sha256,
        "task_id": c.task_id,
        "suite": str(c.input_path("visible_suite")),
        "suite_sha256": c.input_pin("visible_suite"),
        "attempts": c.max_attempts,
        "stop_check": c.hooks["stop_check"],
        "submit_on_end": c.hooks["submit_on_end"],
        "receiver_intake_root": str(root) if root is not None else None,
        "lock_signer": locked["lock"].get("signer"),
    }


def _task(workspace: pathlib.Path, receiver_home: pathlib.Path | None):
    if receiver_home is None:
        raise ValueError("--receiver-home is required")
    cp = receiver_home.resolve() / "contract.json"
    if not cp.is_file():
        raise ValueError(f"no receiver contract: {cp}")
    task = flow.open_task(cp, root=_receiver_root(receiver_home))
    if workspace.resolve() != pathlib.Path(task.contract.raw["notes"]["bridge_workspace"]).resolve():
        raise ValueError("workspace differs from prepared run")
    _boundary(workspace.resolve(), receiver_home.resolve(),
              insecure_same_account=bool(task.contract.raw["notes"].get("insecure_same_account")))
    lock = flow._lock_for(task)
    if approval.check_lock(lock, task_id=task.task_id,
                           contract_sha256=task.contract.sha256, trust=task.trust):
        raise ValueError("receiver contract lock invalid")
    return task


def _workspace_contract_drift(workspace: pathlib.Path, task: flow.Task) -> bool:
    try:
        return C.load(workspace / ".vacant" / "contract.json").sha256 != task.contract.sha256
    except (OSError, C.ContractError):
        return True


def judge(*, workspace: pathlib.Path, sandbox: str = "auto",
          attempt: int | None = None, source: str = "native-eval",
          receiver_home: pathlib.Path | None = None) -> dict[str, Any]:
    workspace = workspace.resolve()
    with _serialized(receiver_home):
        return _judge_locked(workspace=workspace, sandbox=sandbox, attempt=attempt,
                             source=source, receiver_home=receiver_home)


def _judge_locked(*, workspace: pathlib.Path, sandbox: str,
                  attempt: int | None, source: str,
                  receiver_home: pathlib.Path | None) -> dict[str, Any]:
    task = _task(workspace, receiver_home)
    mode = str((task.contract.raw.get("notes") or {}).get("native_acceptance_mode") or "")
    if mode == "conform" and attempt is None:
        raise ValueError("conform mode requires --attempt so the outer harness cannot lose retries")
    events = task.ledger.events()
    started = [e for e in events if e["type"] == "attempt_started"
               and e.get("contract_sha256") == task.contract.sha256]
    expected = len(started) + 1
    attempt = expected if attempt is None else attempt
    if attempt != expected or attempt > task.contract.max_attempts:
        raise ValueError(f"attempt must be {expected} within 1..{task.contract.max_attempts}")
    if any(e["type"] == "decision" and e.get("contract_sha256") == task.contract.sha256
           and e.get("outcome") == "accept" for e in events):
        raise ValueError("run already accepted; use a fresh receiver home")
    task.ledger.append("attempt_started", {"contract_sha256": task.contract.sha256,
                                           "attempt": attempt})
    if _workspace_contract_drift(workspace, task):
        task.ledger.append("infra_void", {"contract_sha256": task.contract.sha256,
                                          "stage": "contract_drift", "attempt": attempt})
        return {"outcome": "hold", "artifact_sha256": None, "void": False,
                "reasons": ["workspace contract differs from signed receiver contract"]}
    result = flow.submit(task, workspace, source=source, sandbox=sandbox, attempt=attempt)
    result["run_id"] = task.contract.raw["notes"]["bridge_run_id"]
    result["attempt"] = attempt
    return result


def release(*, workspace: pathlib.Path, artifact_sha256: str,
            destination: str | None = None,
            receiver_home: pathlib.Path | None = None) -> dict[str, Any]:
    with _serialized(receiver_home):
        return _release_locked(workspace=workspace, artifact_sha256=artifact_sha256,
                               destination=destination, receiver_home=receiver_home)


def _release_locked(*, workspace: pathlib.Path, artifact_sha256: str,
                    destination: str | None,
                    receiver_home: pathlib.Path | None) -> dict[str, Any]:
    task = _task(workspace, receiver_home)
    if _workspace_contract_drift(workspace, task):
        return {"released": False, "reasons": ["workspace contract differs from signed receiver contract"]}
    decisions = [e for e in task.ledger.events() if e["type"] == "decision"
                 and e.get("contract_sha256") == task.contract.sha256]
    if not decisions or decisions[-1].get("outcome") != "accept" or \
            decisions[-1].get("artifact_sha256") != artifact_sha256:
        return {"released": False, "reasons": ["artifact is not the latest accepted judge result"]}
    dest = _destination(destination or str(task.contract.release.get("destination")),
                        workspace.resolve(), receiver_home.resolve())
    return flow.release(task, artifact_sha256=artifact_sha256, destination=dest)


def status(*, workspace: pathlib.Path,
           receiver_home: pathlib.Path | None = None) -> dict[str, Any]:
    task = _task(workspace, receiver_home)
    out = flow.status(task)
    out["run_id"] = task.contract.raw["notes"]["bridge_run_id"]
    out["workspace_contract_matches_receiver"] = not _workspace_contract_drift(workspace, task)
    return out


def _emit(obj: dict[str, Any]) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def _add_receiver_home(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--receiver-home", type=pathlib.Path,
        help=("receiver-owned VACANT_HOME root. Recommended: a directory the agent account "
              "cannot write. The bridge stores intake keys/ledger under <root>/intake."),
    )


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("prepare")
    p.add_argument("--workspace", type=pathlib.Path, default=pathlib.Path.cwd())
    p.add_argument("--task-id", required=True)
    p.add_argument("--suite", type=pathlib.Path)
    p.add_argument("--deliverable", default="solution.py")
    p.add_argument("--mode", choices=MODES, default="repair")
    p.add_argument("--attempts", type=int)
    p.add_argument("--feedback-rounds", type=int, default=3)
    p.add_argument("--suite-timeout-s", type=float, default=60.0)
    p.add_argument("--destination", help="evaluator-owned dir: path outside workspace")
    p.add_argument("--replace", action="store_true")
    p.add_argument("--insecure-same-account", action="store_true",
                   help="non-adversarial evaluation only; recorded in signed contract")
    _add_receiver_home(p)

    p = sp.add_parser("judge")
    p.add_argument("--workspace", type=pathlib.Path, default=pathlib.Path.cwd())
    p.add_argument("--sandbox", default="auto")
    p.add_argument("--attempt", type=int)
    p.add_argument("--source", default="native-eval")
    _add_receiver_home(p)

    p = sp.add_parser("release")
    p.add_argument("--workspace", type=pathlib.Path, default=pathlib.Path.cwd())
    p.add_argument("--artifact", required=True, help="artifact_sha256 from accepting judge")
    p.add_argument("--destination")
    _add_receiver_home(p)

    p = sp.add_parser("status")
    p.add_argument("--workspace", type=pathlib.Path, default=pathlib.Path.cwd())
    _add_receiver_home(p)
    return ap


def main(argv: list[str] | None = None) -> int:
    a = _parser().parse_args(argv)
    try:
        if a.cmd == "prepare":
            out = prepare(workspace=a.workspace, task_id=a.task_id, suite=a.suite,
                          deliverable=a.deliverable, mode=a.mode, attempts=a.attempts,
                          feedback_rounds=a.feedback_rounds,
                          suite_timeout_s=a.suite_timeout_s,
                          destination=a.destination, receiver_home=a.receiver_home,
                          replace=a.replace,
                          insecure_same_account=a.insecure_same_account)
            _emit(out)
            return 0
        if a.cmd == "judge":
            out = judge(workspace=a.workspace, sandbox=a.sandbox,
                        attempt=a.attempt, source=a.source,
                        receiver_home=a.receiver_home)
            _emit(out)
            if out.get("void"):
                return EXIT["void"]
            return EXIT.get(str(out.get("outcome")), 2)
        if a.cmd == "release":
            out = release(workspace=a.workspace, artifact_sha256=a.artifact,
                          destination=a.destination,
                          receiver_home=a.receiver_home)
            _emit(out)
            return 0 if out.get("released") else EXIT["release_refused"]
        out = status(workspace=a.workspace, receiver_home=a.receiver_home)
        _emit(out)
        return 0
    except (OSError, ValueError, C.ContractError) as e:
        print(f"native_acceptance_bridge: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
