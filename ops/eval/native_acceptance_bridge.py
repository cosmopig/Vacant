#!/usr/bin/env python3
"""Bridge native coding agents to Vacant's executable acceptance path.

This is an evaluation-side helper. Run it *outside* the agent session.

The important distinction is:

- evidence mode: inspect the trace and give consistency/provenance feedback;
- this bridge: register a pinned visible suite as a machine-readable contract,
  let the normal native-agent hook call flow.check at settle time, and make the
  evaluator synchronously submit/release the frozen candidate.

Typical C5 repair arm:

    python ops/eval/native_acceptance_bridge.py prepare \
      --workspace /app --task-id "$TASK" --mode repair
    # run the normal pi session in /app
    python ops/eval/native_acceptance_bridge.py judge --workspace /app
    python ops/eval/native_acceptance_bridge.py release --workspace /app

For CONFORM, prepare with --mode conform. The outer harness starts a fresh full
native-agent session after every non-accepting judge result, up to --attempts.
The bridge never calls a model itself.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Any

from vacant_network.intake import contract as C
from vacant_network.intake import flow

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


def _input_path(workspace: pathlib.Path, suite: pathlib.Path) -> str:
    """Prefer a stable workspace-relative path, but allow receiver-owned absolute suites."""
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
    """Build the benchmark contract. Pinning/signing is deliberately a separate step."""
    workspace = workspace.resolve()
    suite = (suite or (workspace / "tests_visible")).resolve()
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    if not workspace.is_dir():
        raise ValueError(f"workspace does not exist: {workspace}")
    if not suite.is_dir():
        raise ValueError(f"visible suite does not exist: {suite}")
    if not any(p.is_file() and p.name.startswith("test_") and p.suffix == ".py"
               for p in suite.rglob("*.py")):
        raise ValueError(f"visible suite has no test_*.py files: {suite}")
    if not deliverable or pathlib.PurePosixPath(deliverable).is_absolute() or ".." in             pathlib.PurePosixPath(deliverable).parts:
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
    # Verification infrastructure failure must never become acceptance.
    raw["unknown_policy"] = "hold"
    raw["conflict_policy"] = "escalate"
    raw["attempts"] = {"max": attempts}
    raw["hooks"] = {
        # repair = visible failure goes back into the same native session.
        # gate/conform = the outer harness decides what to do after synchronous judge.
        "stop_check": mode == "repair",
        "max_feedback_rounds": feedback_rounds if mode == "repair" else 0,
        # Avoid racing a background SessionEnd submit with the evaluator's synchronous judge.
        "submit_on_end": False,
    }
    raw["notes"] = {
        "native_acceptance_mode": mode,
        "bridge": "ops/eval/native_acceptance_bridge.py",
        "trust_boundary": (
            "The visible suite must be pinned before the agent starts. For a hostile agent, "
            "filesystem/account isolation is still required; hook path protection is not a sandbox."
        ),
    }
    C.parse(raw, base_dir=workspace)
    return raw


def prepare(*, workspace: pathlib.Path, task_id: str, suite: pathlib.Path | None,
            deliverable: str, mode: str, attempts: int | None, feedback_rounds: int,
            suite_timeout_s: float, destination: str, replace: bool = False) -> dict[str, Any]:
    workspace = workspace.resolve()
    contract_path = workspace / ".vacant" / "contract.json"
    if contract_path.exists() and not replace:
        raise ValueError(f"{contract_path} already exists; use --replace intentionally")
    raw = build_contract(workspace=workspace, task_id=task_id, suite=suite,
                         deliverable=deliverable, mode=mode, attempts=attempts,
                         feedback_rounds=feedback_rounds,
                         suite_timeout_s=suite_timeout_s, destination=destination)
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    # flow.lock both pins the suite hash and creates the owner-signed contract lock used
    # by the receiver gate. Do this before the agent sees its first prompt.
    locked = flow.lock(contract_path)
    c = C.load(contract_path)
    return {
        "prepared": True,
        "mode": mode,
        "contract": str(contract_path),
        "contract_sha256": c.sha256,
        "task_id": c.task_id,
        "suite": str(c.input_path("visible_suite")),
        "suite_sha256": c.input_pin("visible_suite"),
        "attempts": c.max_attempts,
        "stop_check": c.hooks["stop_check"],
        "submit_on_end": c.hooks["submit_on_end"],
        "lock_signer": locked["lock"].get("signer"),
    }


def judge(*, workspace: pathlib.Path, sandbox: str = "auto",
          attempt: int | None = None, source: str = "native-eval") -> dict[str, Any]:
    workspace = workspace.resolve()
    cp = C.find(workspace)
    if cp is None:
        raise ValueError(f"no machine contract found under {workspace}")
    task = flow.open_task(cp)
    if attempt is not None and not 1 <= attempt <= task.contract.max_attempts:
        raise ValueError(f"attempt {attempt} outside 1..{task.contract.max_attempts}")
    return flow.submit(task, workspace, source=source, sandbox=sandbox, attempt=attempt)


def release(*, workspace: pathlib.Path, destination: str | None = None) -> dict[str, Any]:
    workspace = workspace.resolve()
    cp = C.find(workspace)
    if cp is None:
        raise ValueError(f"no machine contract found under {workspace}")
    task = flow.open_task(cp)
    return flow.release(task, destination=destination)


def status(*, workspace: pathlib.Path) -> dict[str, Any]:
    cp = C.find(workspace.resolve())
    if cp is None:
        raise ValueError(f"no machine contract found under {workspace}")
    return flow.status(flow.open_task(cp))


def _emit(obj: dict[str, Any]) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


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
    p.add_argument("--destination", default="dir:.vacant/native-release")
    p.add_argument("--replace", action="store_true")

    p = sp.add_parser("judge")
    p.add_argument("--workspace", type=pathlib.Path, default=pathlib.Path.cwd())
    p.add_argument("--sandbox", default="auto")
    p.add_argument("--attempt", type=int)
    p.add_argument("--source", default="native-eval")

    p = sp.add_parser("release")
    p.add_argument("--workspace", type=pathlib.Path, default=pathlib.Path.cwd())
    p.add_argument("--destination")

    p = sp.add_parser("status")
    p.add_argument("--workspace", type=pathlib.Path, default=pathlib.Path.cwd())
    return ap


def main(argv: list[str] | None = None) -> int:
    a = _parser().parse_args(argv)
    try:
        if a.cmd == "prepare":
            out = prepare(workspace=a.workspace, task_id=a.task_id, suite=a.suite,
                          deliverable=a.deliverable, mode=a.mode, attempts=a.attempts,
                          feedback_rounds=a.feedback_rounds,
                          suite_timeout_s=a.suite_timeout_s,
                          destination=a.destination, replace=a.replace)
            _emit(out)
            return 0
        if a.cmd == "judge":
            out = judge(workspace=a.workspace, sandbox=a.sandbox,
                        attempt=a.attempt, source=a.source)
            _emit(out)
            if out.get("void"):
                return EXIT["void"]
            return EXIT.get(str(out.get("outcome")), 2)
        if a.cmd == "release":
            out = release(workspace=a.workspace, destination=a.destination)
            _emit(out)
            return 0 if out.get("released") else EXIT["release_refused"]
        out = status(workspace=a.workspace)
        _emit(out)
        return 0
    except (OSError, ValueError, C.ContractError) as e:
        print(f"native_acceptance_bridge: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
