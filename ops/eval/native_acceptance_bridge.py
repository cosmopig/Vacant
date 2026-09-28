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
- /srv/eval/receiver/<task>/tests_visible: evaluator-owned verifier copy passed
  via --suite and not writable by the agent;
- --receiver-home: evaluator-owned Vacant state/signing home, separate from the
  agent's VACANT_HOME.

Repair arm:

    python ops/eval/native_acceptance_bridge.py prepare \
      --workspace /app --task-id "$TASK" --mode repair \
      --suite "/srv/eval/receiver/$TASK/tests_visible" \
      --receiver-home "/srv/eval/receiver/$TASK/vacant"
    # run the normal native agent in /app
    python ops/eval/native_acceptance_bridge.py judge \
      --workspace /app --attempt 1 \
      --receiver-home "/srv/eval/receiver/$TASK/vacant"
    python ops/eval/native_acceptance_bridge.py release \
      --workspace /app \
      --receiver-home "/srv/eval/receiver/$TASK/vacant"

For CONFORM, prepare with --mode conform. The *outer harness* must start a
fresh full native-agent session after every non-accepting judge result, passing
--attempt 1..N. This helper deliberately has no model API or router.
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


def _receiver_root(receiver_home: pathlib.Path | None) -> pathlib.Path | None:
    """CLI accepts a VACANT_HOME-like root; flow accepts its intake/ child."""
    return None if receiver_home is None else receiver_home.resolve() / "intake"


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
    if not any(p.is_file() and p.name.startswith("test_") and p.suffix == ".py"
               for p in suite.rglob("*.py")):
        raise ValueError(f"visible suite has no test_*.py files: {suite}")
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
            "Pin before the agent starts. For adversarial work, keep the verifier suite and "
            "receiver signing state under a different account/process; hooks are not a sandbox."
        ),
    }
    C.parse(raw, base_dir=workspace)
    return raw


def prepare(*, workspace: pathlib.Path, task_id: str, suite: pathlib.Path | None,
            deliverable: str, mode: str, attempts: int | None, feedback_rounds: int,
            suite_timeout_s: float, destination: str,
            receiver_home: pathlib.Path | None = None,
            replace: bool = False) -> dict[str, Any]:
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
    root = _receiver_root(receiver_home)
    # Pins the suite and signs the contract lock before the agent gets its first prompt.
    locked = flow.lock(contract_path, root=root)
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
        "receiver_intake_root": str(root) if root is not None else None,
        "lock_signer": locked["lock"].get("signer"),
    }


def _task(workspace: pathlib.Path, receiver_home: pathlib.Path | None):
    cp = C.find(workspace.resolve())
    if cp is None:
        raise ValueError(f"no machine contract found under {workspace}")
    return flow.open_task(cp, root=_receiver_root(receiver_home))


def judge(*, workspace: pathlib.Path, sandbox: str = "auto",
          attempt: int | None = None, source: str = "native-eval",
          receiver_home: pathlib.Path | None = None) -> dict[str, Any]:
    workspace = workspace.resolve()
    task = _task(workspace, receiver_home)
    mode = str((task.contract.raw.get("notes") or {}).get("native_acceptance_mode") or "")
    if mode == "conform" and attempt is None:
        raise ValueError("conform mode requires --attempt so the outer harness cannot lose retries")
    if attempt is not None and not 1 <= attempt <= task.contract.max_attempts:
        raise ValueError(f"attempt {attempt} outside 1..{task.contract.max_attempts}")
    return flow.submit(task, workspace, source=source, sandbox=sandbox, attempt=attempt)


def release(*, workspace: pathlib.Path, destination: str | None = None,
            receiver_home: pathlib.Path | None = None) -> dict[str, Any]:
    return flow.release(_task(workspace, receiver_home), destination=destination)


def status(*, workspace: pathlib.Path,
           receiver_home: pathlib.Path | None = None) -> dict[str, Any]:
    return flow.status(_task(workspace, receiver_home))


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
    p.add_argument("--destination", default="dir:.vacant/native-release")
    p.add_argument("--replace", action="store_true")
    _add_receiver_home(p)

    p = sp.add_parser("judge")
    p.add_argument("--workspace", type=pathlib.Path, default=pathlib.Path.cwd())
    p.add_argument("--sandbox", default="auto")
    p.add_argument("--attempt", type=int)
    p.add_argument("--source", default="native-eval")
    _add_receiver_home(p)

    p = sp.add_parser("release")
    p.add_argument("--workspace", type=pathlib.Path, default=pathlib.Path.cwd())
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
                          replace=a.replace)
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
            out = release(workspace=a.workspace, destination=a.destination,
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
