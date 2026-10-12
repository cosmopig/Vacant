#!/usr/bin/env python3
"""Bridge an existing native coding agent to Vacant's executable acceptance path.

This is an evaluator/receiver-side helper. It never calls a model and it does
not replace Pi, Claude Code, Codex, OpenCode, or another agent platform.

The bridge registers a machine-readable contract whose visible suite is pinned
*before* the agent runs. The normal native-agent hook can then call
`flow.check` at settle time (repair mode), while the outer evaluator performs
the authoritative synchronous `submit` / `release`. The receiver's copy of the
contract (<receiver_home>/contract.json, lock-checked) is the only one that
decides; the copy under <workspace>/.vacant/ is for the agent's hook and is
only *compared* (`workspace_contract_matches_receiver`, informational).

Recommended C5 layout:

- /app/tests_visible: agent-readable copy used by run_tests.sh;
- --receiver-home: a fresh evaluator-owned home per run, outside /app, held by
  a separate OS account. The bridge pins a readable suite beside this home.
  Its path must have no symlink component.
- Non-root evaluator + agent-owned workspace (what `_boundary` checks for): prepare writes
  <workspace>/.vacant/contract.json, so the evaluator must be able to write the workspace
  directory, e.g. `chgrp <evaluator-gid> <workspace>; chmod 775 <workspace>`. Otherwise
  prepare stops with one EACCES line on <workspace>/.vacant and rolls everything back.
- --destination: `dir:<path>` inside the receiver home (default <receiver-home>/released);
  anything else is refused. A run cannot be replaced: use a fresh receiver home.

Repair arm:

    python ops/eval/native_acceptance_bridge.py prepare \
      --workspace /app --task-id "$RUN" --mode repair \
      --receiver-home "/srv/eval/receiver/$RUN/vacant"
    # run the normal native agent in /app
    python ops/eval/native_acceptance_bridge.py judge \
      --workspace /app --attempt 1 \
      --receiver-home "/srv/eval/receiver/$RUN/vacant"
    python ops/eval/native_acceptance_bridge.py release \
      --workspace /app --artifact "<sha from accepting judge>" \
      --receiver-home "/srv/eval/receiver/$RUN/vacant"

For CONFORM, prepare with --mode conform. The *outer harness* must start a
fresh full native-agent session after every non-accepting judge result, passing
--attempt 1..N. This helper deliberately has no model API or router.

Attempts: an attempt is used only by a *decision* (accept/reject/hold/escalate).
`--attempt` must be (decisions so far)+1. Evaluator-side failures never use
one: a failed sandbox preflight is recorded as `infra_void` (stage "preflight")
before `attempt_started` is written, and an exception or a killed judge leaves
no decision, so the same attempt number can be judged again. After 3 failed
tries at one attempt number judge refuses (exit 43): rerun the cell with a
fresh receiver home.

Exit codes (the table of `vacant submit` / `vacant release`, intake/cli.py):
  judge    0 accept, 40 reject, 41 hold, 42 escalate, 43 void (infra, no attempt used)
  release  0 released and read back, 43 void, 44 refused, 45 release unconfirmed
           (effect unknown or readback not ok); grade only exit 0 + readback_ok
  any      2 usage error / refusal / unexpected error (one stderr line, no traceback)

Trust boundary (non-adversarial benchmark helper; read before quoting it as a boundary):
- `python_checks` shares an interpreter with candidate code: it guards against
  accidents, not against a hostile candidate.
- Unless --insecure-same-account, the bridge requires the bwrap backend (none/unshare
  do not hide files from the candidate) and records `evaluator_euid`. bwrap does not
  drop a root evaluator's capabilities: an adversarial boundary needs a NON-ROOT
  evaluator account plus a separate agent uid.
- The contract's `effects.protect_paths` lists the receiver home and the pinned suite.
  Native *write* tools are denied there, and the hook's string-level shell guard denies
  *direct* shell writes (`>` redirects, `tee`/`cp`/`mv`/`rm`/`sed -i`, an inline
  `python -c "open(...)"`). Indirect forms (a path built in a variable, a script file that
  does the write) and every read are allowed. A soft guard, not a boundary.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import fcntl
import hashlib
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile
import uuid
from typing import Any, Iterator

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if sys.path[:1] != [str(_ROOT)]:       # never import another checkout's vacant_network
    sys.path.insert(0, str(_ROOT))

from vacant_network.intake import approval  # noqa: E402
from vacant_network.intake import contract as C  # noqa: E402
from vacant_network.intake import flow  # noqa: E402
from vacant_network.vrun.acceptance import declared_cases, test_files  # noqa: E402
from vacant_network.vrun import sandbox as _sandbox  # noqa: E402

EXIT = {"accept": 0, "reject": 40, "hold": 41, "escalate": 42, "void": 43,
        "release_refused": 44, "release_unconfirmed": 45}
MODES = ("gate", "repair", "conform")
SANDBOXES = ("auto", "bwrap", "unshare", "none")
VOID_CAP = 3
_SHIPS = "the executor ships only top-level .py files to the checks"


def make_sandbox(*args: Any, **kwargs: Any) -> Any:
    """vrun's make_sandbox, looked up at call time (tests can patch either place)."""
    return _sandbox.make_sandbox(*args, **kwargs)


def _task_id(raw: str) -> str:
    out = re.sub(r"[^A-Za-z0-9._-]+", "-", raw.strip()).strip("-._")
    if not out:
        raise ValueError("task id is empty after normalization")
    if len(out) > 128:
        out = out[:128].rstrip("-._")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", out):
        raise ValueError(f"invalid task id {out!r}")
    return out


def _oneline(e: BaseException) -> str:
    return " ".join(str(e).split())[:500]


def _rhome(receiver_home: pathlib.Path | None) -> pathlib.Path:
    """The receiver's signing home: mandatory, absolute, and no symlink component (F08)."""
    if receiver_home is None:
        raise ValueError("--receiver-home is required for every bridge operation")
    p = pathlib.Path(os.path.abspath(os.path.expanduser(str(receiver_home))))
    cur = pathlib.Path(p.anchor)
    for part in p.parts[1:]:
        cur = cur / part
        if os.path.islink(cur):
            raise ValueError(f"receiver home path has a symlink component: {cur}; "
                             "use the real path")
    return p


def _receiver_root(receiver_home: pathlib.Path | None) -> pathlib.Path:
    return _rhome(receiver_home) / "intake"


@contextlib.contextmanager
def _serialized(receiver_home: pathlib.Path | None) -> Iterator[None]:
    with (_rhome(receiver_home) / "bridge.lock").open("a+b") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


@contextlib.contextmanager
def _stdin_devnull() -> Iterator[None]:
    """Candidate code must not eat the evaluator's stdin (W2); restored afterwards."""
    try:
        saved: int | None = os.dup(0)
    except OSError:
        saved = None
    null = os.open(os.devnull, os.O_RDONLY)
    try:
        os.dup2(null, 0)
        yield
    finally:
        os.close(null)
        if saved is not None:
            os.dup2(saved, 0)
            os.close(saved)


def _force_rmtree(path: pathlib.Path) -> None:
    """Remove a tree this bridge made, including the read-only suite snapshot."""
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
        return
    if not path.is_dir():
        return
    for q in (path, *path.rglob("*")):
        if not q.is_symlink():
            with contextlib.suppress(OSError):
                q.chmod(0o700)
    shutil.rmtree(path, ignore_errors=True)


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


def _check_parent(parent: pathlib.Path, insecure_same_account: bool) -> None:
    st = parent.stat()
    if not insecure_same_account and (st.st_uid != os.geteuid() or st.st_mode & 0o022):
        raise ValueError("receiver parent must be evaluator-owned and not writable by agent")


def _sandbox_policy(name: str, insecure_same_account: bool) -> None:
    if name not in SANDBOXES:
        raise ValueError(f"--sandbox must be one of {SANDBOXES}, got {name!r}")
    if not insecure_same_account and name in ("none", "unshare"):
        raise ValueError(f"sandbox {name!r} does not hide files from the candidate; a "
                         "separate-account run needs bwrap (or --insecure-same-account "
                         "for a non-adversarial run)")


def _preflight(name: str, *, insecure_same_account: bool) -> dict[str, Any]:
    """Can the verifier sandbox run python3 at all? Never uses an attempt (F02, F05)."""
    out: dict[str, Any] = {"ok": False, "backend": None, "meta": {}, "reasons": []}
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="vacant-bridge-preflight-"))
    try:
        work = tmp / "work"
        work.mkdir()
        try:
            sb, meta = make_sandbox(name, workdir=str(work))
        except SystemExit as e:
            out["reasons"].append(f"sandbox unavailable: {e}")
            return out
        sb.hermetic = True   # same mode the verifier uses
        out["backend"] = meta.get("backend")
        out["meta"] = {"requested": name, "backend": meta.get("backend"),
                       "network_isolated": meta.get("network_isolated"),
                       "write_confined": meta.get("write_confined"),
                       "repo_hidden_from_sandbox": meta.get("repo_hidden_from_sandbox"),
                       "honest_bound": meta.get("honest_bound")}
        r = sb.run("python3 -c 'print(1)'", workspace=work, timeout_s=30)
        if r.timed_out or r.rc != 0 or r.stdout.strip() != "1":
            out["reasons"].append(
                f"python3 does not run in the {out['backend']} verifier sandbox "
                f"(rc={r.rc}, timed_out={r.timed_out}): {r.stderr.strip()[-200:]}")
        elif not insecure_same_account and out["backend"] != "bwrap":
            out["reasons"].append(f"backend resolved to {out['backend']!r}; a separate-account "
                                  "run requires bwrap")
        else:
            out["ok"] = True
    except Exception as e:  # noqa: BLE001 -- any preflight failure is an infra problem
        out["reasons"].append(f"sandbox preflight failed: {type(e).__name__}: {_oneline(e)}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


def _destination(value: str | None, workspace: pathlib.Path,
                 receiver_home: pathlib.Path) -> str:
    value = value or f"dir:{receiver_home / 'released'}"
    if not value.startswith("dir:"):
        raise ValueError("bridge destination must be an evaluator-owned dir: inside the receiver home")
    path = pathlib.Path(value[4:]).expanduser()
    path = (path if path.is_absolute() else workspace / path).resolve()
    if not _inside(path, receiver_home) or _inside(receiver_home, path):
        raise ValueError("release destination must be inside receiver home")
    return f"dir:{path}"


def _required_params(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    a = fn.args
    pos = [*a.posonlyargs, *a.args]
    req = pos[:len(pos) - len(a.defaults)]
    req += [k for k, d in zip(a.kwonlyargs, a.kw_defaults) if d is None]
    return [x.arg for x in req]


def _suite_files(suite: pathlib.Path) -> list[pathlib.Path]:
    """Refuse a suite the executor cannot run as a whole (F04, M2, M3)."""
    if suite.is_symlink():
        raise ValueError(f"suite directory is a symlink: {suite}")
    for p in sorted(suite.rglob("*")):
        rel = p.relative_to(suite)
        if p.is_symlink():
            raise ValueError(f"suite symlinks are not allowed: {rel}; {_SHIPS}")
        if "__pycache__" in rel.parts:
            continue
        if p.is_dir():
            raise ValueError(f"suite subdirectory {rel}: nested files would not run; {_SHIPS}")
        if not p.is_file() or p.suffix != ".py":
            raise ValueError(f"suite file {rel} is not a .py file; {_SHIPS}")
    files = test_files(suite)
    if not files:
        raise ValueError(f"visible suite has no top-level test_*.py files: {suite}")
    for p in files:
        if not declared_cases(p):
            raise ValueError(f"test file needs top-level check_* or main: {p}")
        try:
            tree = ast.parse(p.read_bytes().decode("utf-8"))
        except (SyntaxError, ValueError):
            continue   # the driver reports it as an import failure
        for fn in tree.body:
            if (isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and fn.name.startswith("check_") and _required_params(fn)):
                raise ValueError(f"{p.name}: {fn.name}() has required parameters "
                                 f"{_required_params(fn)}; checks are called with no "
                                 f"arguments and {_SHIPS}")
    return files


def _suite_target(receiver_home: pathlib.Path) -> pathlib.Path:
    return receiver_home.with_name(receiver_home.name + "-suite")


def _snapshot_suite(suite: pathlib.Path, receiver_home: pathlib.Path) -> pathlib.Path:
    """Copy before pinning; publish a read-only agent-readable suite beside home."""
    source_hash = C.path_sha256(suite)
    target = _suite_target(receiver_home)
    if os.path.lexists(target):
        raise ValueError(f"receiver suite already exists: {target}; use a fresh receiver home")
    temp = target.with_name(target.name + f".tmp-{uuid.uuid4().hex}")
    try:
        shutil.copytree(suite, temp, symlinks=False, ignore=shutil.ignore_patterns("__pycache__"))
        if C.path_sha256(temp) != source_hash or C.path_sha256(suite) != source_hash:
            raise ValueError("suite changed while being snapshotted")
        _suite_files(temp)
        for p in temp.rglob("*"):
            p.chmod(0o555 if p.is_dir() else 0o444)
        temp.chmod(0o555)
        temp.rename(target)
    finally:
        _force_rmtree(temp)
    return target


def _readable_by_agent(suite: pathlib.Path) -> bool:
    """Conservative check for the repair hook running under another UID.
    Works before the snapshot exists: then only the existing parent chain is judged."""
    if suite.is_dir() and any(not p.stat().st_mode & 0o004 for p in suite.rglob("*") if p.is_file()):
        return False
    return all(p.stat().st_mode & 0o001 for p in (suite, *suite.parents) if p.exists())


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
                   destination: str = "dir:.vacant/native-release",
                   protect_paths: list[str] | None = None) -> dict[str, Any]:
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
    # Keep scaffold's two safety floors (deliverable_present, no_secrets_shipped); add ours.
    raw["claims"].append({
        "id": "visible_acceptance",
        "verifier": "python_checks",
        "params": {"suite": "input:visible_suite", "timeout_s": suite_timeout_s},
        "required": True,
        "authority": "requirement",
        "description": "The frozen candidate passes the evaluator-pinned visible suite.",
    })
    # Infrastructure uncertainty must not become a PASS.
    raw["unknown_policy"] = "hold"
    raw["conflict_policy"] = "escalate"
    raw["attempts"] = {"max": attempts}
    raw["effects"]["protect_paths"] = list(protect_paths or [])
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
            "verifier; use a separate-process verifier or SuiteSpec for hostile code. "
            "bwrap does not drop a root evaluator's capabilities (see evaluator_euid): an "
            "adversarial boundary needs a non-root evaluator account. effects.protect_paths "
            "denies native write tools and direct shell writes (string-level guard); indirect "
            "forms and all reads are allowed."
        ),
    }
    C.parse(raw, base_dir=workspace)
    return raw


def prepare(*, workspace: pathlib.Path, task_id: str, suite: pathlib.Path | None,
            deliverable: str, mode: str, attempts: int | None, feedback_rounds: int,
            suite_timeout_s: float, destination: str | None,
            receiver_home: pathlib.Path | None = None,
            insecure_same_account: bool = False, sandbox: str = "auto",
            agent_suite: pathlib.Path | None = None) -> dict[str, Any]:
    """Validate everything first; create nothing until every check passed (F10).
    A later failure removes what this call created and re-raises."""
    workspace = workspace.resolve()
    rh = _rhome(receiver_home)
    contract_path = workspace / ".vacant" / "contract.json"
    trusted_path = rh / "contract.json"
    target = _suite_target(rh)
    # ---- validation: reads only -------------------------------------------------------
    _boundary(workspace, rh, insecure_same_account=insecure_same_account)
    _sandbox_policy(sandbox, insecure_same_account)
    if contract_path.exists() or trusted_path.exists():
        raise ValueError("contract already exists; use a fresh workspace and receiver home")
    if os.path.lexists(target):
        raise ValueError(f"receiver suite already exists: {target}; use a fresh receiver home")
    source_suite = (suite or workspace / "tests_visible").resolve()
    if not source_suite.is_dir():
        raise ValueError(f"visible suite does not exist: {source_suite}")
    dest = _destination(destination, workspace, rh)
    build_contract(workspace=workspace, task_id=task_id, suite=source_suite,
                   deliverable=deliverable, mode=mode, attempts=attempts,
                   feedback_rounds=feedback_rounds, suite_timeout_s=suite_timeout_s,
                   destination=dest, protect_paths=[str(rh), str(target)])
    visible = agent_suite if agent_suite is not None else workspace / "tests_visible"
    if agent_suite is not None and not visible.is_dir():
        raise ValueError(f"agent visible suite does not exist: {visible}")
    visible_dir = visible.resolve() if visible.is_dir() else None
    if rh.parent.exists():
        _check_parent(rh.parent, insecure_same_account)
    if mode == "repair" and not insecure_same_account and not _readable_by_agent(target):
        raise ValueError("repair suite must be readable by the agent account")
    pf = _preflight(sandbox, insecure_same_account=insecure_same_account)
    if not pf["ok"]:
        raise ValueError("sandbox preflight failed: " + "; ".join(pf["reasons"]))
    # ---- creation: roll back on any failure -------------------------------------------
    made: list[pathlib.Path] = []
    for d in reversed([rh.parent, *rh.parent.parents]):
        if not d.exists():
            d.mkdir(mode=0o755)
            made.append(d)
    rh_before = set(os.listdir(rh)) if rh.exists() else None
    vacant_made = not contract_path.parent.exists()
    pinned: pathlib.Path | None = None
    try:
        rh.mkdir(mode=0o700, exist_ok=True)
        rh.chmod(0o700)
        _check_parent(rh.parent, insecure_same_account)
        pinned = _snapshot_suite(source_suite, rh)
        if mode == "repair" and not insecure_same_account and not _readable_by_agent(pinned):
            raise ValueError("repair suite must be readable by the agent account")
        raw = build_contract(workspace=workspace, task_id=task_id, suite=pinned,
                             deliverable=deliverable, mode=mode, attempts=attempts,
                             feedback_rounds=feedback_rounds,
                             suite_timeout_s=suite_timeout_s, destination=dest,
                             protect_paths=[str(rh), str(pinned)])
        pinned_sha = C.path_sha256(pinned)
        visible_sha = C.path_sha256(visible_dir) if visible_dir is not None else None
        raw["notes"].update({
            "bridge_run_id": uuid.uuid4().hex,
            "bridge_workspace": str(workspace),
            "insecure_same_account": insecure_same_account,
            "evaluator_euid": os.geteuid(),
            "sandbox_backend": pf["backend"],
            "verifier_sandbox": pf["meta"],
            "agent_visible_suite_path": str(visible_dir) if visible_dir is not None else None,
            "agent_visible_suite_sha256": visible_sha,
            "pinned_suite_sha256": pinned_sha,
            "agent_visible_suite_matches_pinned":
                None if visible_sha is None else visible_sha == pinned_sha,
        })
        contract_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(raw, ensure_ascii=False, indent=2) + "\n"
        trusted_path.write_text(payload, encoding="utf-8")
        contract_path.write_text(payload, encoding="utf-8")
        root = _receiver_root(rh)
        # Pins the suite and signs the contract lock before the agent gets its first prompt.
        locked = flow.lock(trusted_path, root=root)
        contract_path.write_bytes(trusted_path.read_bytes())
        c = C.load(trusted_path)
    except BaseException:
        if pinned is not None:
            _force_rmtree(pinned)
        if rh_before is None:
            _force_rmtree(rh)
        elif rh.exists():
            for name in set(os.listdir(rh)) - rh_before:
                _force_rmtree(rh / name)
        contract_path.unlink(missing_ok=True)
        if vacant_made:
            shutil.rmtree(contract_path.parent, ignore_errors=True)
        for d in reversed(made):
            with contextlib.suppress(OSError):
                d.rmdir()
        raise
    notes = raw["notes"]
    return {
        "prepared": True,
        "mode": mode,
        "contract": str(contract_path),
        "receiver_contract": str(trusted_path),
        "run_id": notes["bridge_run_id"],
        "insecure_same_account": insecure_same_account,
        "evaluator_euid": notes["evaluator_euid"],
        "sandbox_backend": notes["sandbox_backend"],
        "contract_sha256": c.sha256,
        "task_id": c.task_id,
        "suite": str(c.input_path("visible_suite")),
        "suite_sha256": c.input_pin("visible_suite"),
        "agent_visible_suite_sha256": notes["agent_visible_suite_sha256"],
        "pinned_suite_sha256": notes["pinned_suite_sha256"],
        "agent_visible_suite_matches_pinned": notes["agent_visible_suite_matches_pinned"],
        "attempts": c.max_attempts,
        "stop_check": c.hooks["stop_check"],
        "submit_on_end": c.hooks["submit_on_end"],
        "receiver_intake_root": str(root),
        "lock_signer": locked["lock"].get("signer"),
    }


def _task(workspace: pathlib.Path, receiver_home: pathlib.Path | None):
    rh = _rhome(receiver_home)
    cp = rh / "contract.json"
    if not cp.is_file():
        raise ValueError(f"no receiver contract: {cp}")
    task = flow.open_task(cp, root=_receiver_root(rh))
    notes = task.contract.raw.get("notes") or {}
    if not notes.get("bridge_workspace"):
        raise ValueError(f"receiver contract was not prepared by this bridge: {cp}")
    if workspace.resolve() != pathlib.Path(notes["bridge_workspace"]).resolve():
        raise ValueError("workspace differs from prepared run")
    _boundary(workspace.resolve(), rh,
              insecure_same_account=bool(notes.get("insecure_same_account")))
    lock = flow._lock_for(task)
    if approval.check_lock(lock, task_id=task.task_id,
                           contract_sha256=task.contract.sha256, trust=task.trust):
        raise ValueError("receiver contract lock invalid")
    return task


def _observe(workspace: pathlib.Path, rh: pathlib.Path, task: flow.Task) -> dict[str, Any]:
    """Informational only: never HOLD, void or refuse because of what is seen here."""
    try:
        same = (hashlib.sha256((workspace / ".vacant" / "contract.json").read_bytes()).digest()
                == hashlib.sha256((rh / "contract.json").read_bytes()).digest())
    except OSError:
        same = False
    path = (task.contract.raw.get("notes") or {}).get("agent_visible_suite_path")
    try:
        suite_same: bool | None = (C.path_sha256(pathlib.Path(path))
                                   == task.contract.input_pin("visible_suite")) if path else None
    except (OSError, KeyError, ValueError):
        suite_same = None
    return {"workspace_contract_matches_receiver": same,
            "agent_visible_suite_matches_pinned": suite_same}


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
    rh = _rhome(receiver_home)
    notes = task.contract.raw.get("notes") or {}
    sha = task.contract.sha256
    if str(notes.get("native_acceptance_mode") or "") == "conform" and attempt is None:
        raise ValueError("conform mode requires --attempt so the outer harness cannot lose retries")
    events = task.ledger.events()
    decisions = [e for e in events if e["type"] == "decision" and e.get("contract_sha256") == sha]
    if any(e.get("outcome") == "accept" for e in decisions):
        raise ValueError("run already accepted; use a fresh receiver home")
    expected = len(decisions) + 1     # only a decision uses an attempt
    attempt = expected if attempt is None else attempt
    if attempt != expected or attempt > task.contract.max_attempts:
        raise ValueError(f"attempt must be {expected} within 1..{task.contract.max_attempts}")
    insecure = bool(notes.get("insecure_same_account"))
    _sandbox_policy(sandbox, insecure)
    base = {"run_id": notes["bridge_run_id"], "attempt": attempt, "contract_sha256": sha}
    failed_tries = max(
        sum(1 for e in events if e["type"] == "infra_void" and e.get("attempt") == attempt),
        sum(1 for e in events if e["type"] == "attempt_started" and e.get("attempt") == attempt
            and e.get("contract_sha256") == sha))
    if failed_tries >= VOID_CAP:
        return {**base, "outcome": None, "void": True, "artifact_sha256": None,
                "reasons": [f"void cap reached for attempt {attempt}; "
                            "rerun the cell with a fresh receiver home"]}
    obs = _observe(workspace, rh, task)
    pf = _preflight(sandbox, insecure_same_account=insecure)
    if not pf["ok"]:
        task.ledger.append("infra_void", {"contract_sha256": sha, "stage": "preflight",
                                          "attempt": attempt, "error": "; ".join(pf["reasons"])[:500]})
        return {**base, **obs, "outcome": None, "void": True, "artifact_sha256": None,
                "sandbox_backend": pf["backend"], "reasons": pf["reasons"]}
    backend = pf["backend"]
    task.ledger.append("attempt_started", {
        "contract_sha256": sha, "attempt": attempt, "sandbox_backend": backend,
        "workspace_contract_matches_receiver": obs["workspace_contract_matches_receiver"]})
    try:
        result = flow.submit(task, workspace, source=source, sandbox=backend, attempt=attempt)
    except Exception as e:  # noqa: BLE001 -- evaluator-side failure: void, not a decision
        err = f"{type(e).__name__}: {_oneline(e)}"
        task.ledger.append("infra_void", {"contract_sha256": sha, "stage": "judge",
                                          "attempt": attempt, "error": err[:500]})
        result = {"outcome": None, "void": True, "artifact_sha256": None,
                  "reasons": [f"judge failed: {err}"]}
    result.update({**base, **obs, "sandbox_backend": backend})
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
    rh = _rhome(receiver_home)
    obs = _observe(workspace.resolve(), rh, task)
    decisions = [e for e in task.ledger.events() if e["type"] == "decision"
                 and e.get("contract_sha256") == task.contract.sha256]
    if not decisions or decisions[-1].get("outcome") != "accept" or \
            decisions[-1].get("artifact_sha256") != artifact_sha256:
        return {"released": False, "reasons": ["artifact is not the latest accepted judge result"],
                **obs}
    dest = _destination(destination or str(task.contract.release.get("destination")),
                        workspace.resolve(), rh)
    return {**flow.release(task, artifact_sha256=artifact_sha256, destination=dest), **obs}


def status(*, workspace: pathlib.Path,
           receiver_home: pathlib.Path | None = None) -> dict[str, Any]:
    task = _task(workspace, receiver_home)
    out = flow.status(task)
    out["run_id"] = task.contract.raw["notes"]["bridge_run_id"]
    out["attempts_used"] = out.get("decisions", 0)     # attempts = tries; used = decisions
    out["attempts_max"] = task.contract.max_attempts
    out.update(_observe(workspace.resolve(), _rhome(receiver_home), task))
    return out


def _release_exit(res: dict[str, Any]) -> int:
    """The mapping of `vacant release` (intake/cli.py cmd_release)."""
    if res.get("void"):
        return EXIT["void"]
    if res.get("released") and res.get("readback_ok") is not False:
        return 0
    if res.get("released") or res.get("effect"):
        return EXIT["release_unconfirmed"]
    return EXIT["release_refused"]


def _emit(obj: dict[str, Any]) -> None:
    # ASCII-only: an agent-chosen file name that is not valid UTF-8 (a lone surrogate)
    # must not crash the printout after the verdict is already signed.
    print(json.dumps(obj, ensure_ascii=True, indent=2, default=str))


def _add_receiver_home(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--receiver-home", type=pathlib.Path,
        help=("receiver-owned VACANT_HOME root, a fresh one per run; its path must have no "
              "symlink component. Recommended: a directory the agent account cannot write. "
              "The bridge stores intake keys/ledger under <root>/intake."),
    )


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("prepare")
    p.add_argument("--workspace", type=pathlib.Path, default=pathlib.Path.cwd())
    p.add_argument("--task-id", required=True)
    p.add_argument("--suite", type=pathlib.Path,
                   help="suite to pin (default <workspace>/tests_visible); copied beside the "
                        "receiver home")
    p.add_argument("--agent-suite", type=pathlib.Path,
                   help="the suite directory the agent sees (default <workspace>/tests_visible "
                        "if it exists, else none); only compared with the pinned suite")
    p.add_argument("--deliverable", default="solution.py")
    p.add_argument("--mode", choices=MODES, default="repair")
    p.add_argument("--attempts", type=int)
    p.add_argument("--feedback-rounds", type=int, default=3)
    p.add_argument("--suite-timeout-s", type=float, default=60.0)
    p.add_argument("--destination",
                   help="release destination: `dir:<path>` inside the receiver home "
                        "(default dir:<receiver-home>/released); anything else is refused")
    p.add_argument("--sandbox", choices=SANDBOXES, default="auto",
                   help="verifier sandbox to preflight; without --insecure-same-account "
                        "only bwrap is accepted")
    p.add_argument("--insecure-same-account", action="store_true",
                   help="non-adversarial evaluation only; recorded in signed contract")
    _add_receiver_home(p)

    p = sp.add_parser("judge")
    p.add_argument("--workspace", type=pathlib.Path, default=pathlib.Path.cwd())
    p.add_argument("--sandbox", choices=SANDBOXES, default="auto")
    p.add_argument("--attempt", type=int,
                   help="(decisions so far)+1; required in conform mode")
    p.add_argument("--source", default="native-eval")
    _add_receiver_home(p)

    p = sp.add_parser("release")
    p.add_argument("--workspace", type=pathlib.Path, default=pathlib.Path.cwd())
    p.add_argument("--artifact", required=True, help="artifact_sha256 from accepting judge")
    p.add_argument("--destination", help="dir:<path> inside the receiver home")
    _add_receiver_home(p)

    p = sp.add_parser("status")
    p.add_argument("--workspace", type=pathlib.Path, default=pathlib.Path.cwd())
    _add_receiver_home(p)
    return ap


def main(argv: list[str] | None = None) -> int:
    a = _parser().parse_args(argv)
    try:
        if a.cmd == "prepare":
            _emit(prepare(workspace=a.workspace, task_id=a.task_id, suite=a.suite,
                          deliverable=a.deliverable, mode=a.mode, attempts=a.attempts,
                          feedback_rounds=a.feedback_rounds,
                          suite_timeout_s=a.suite_timeout_s,
                          destination=a.destination, receiver_home=a.receiver_home,
                          insecure_same_account=a.insecure_same_account,
                          sandbox=a.sandbox, agent_suite=a.agent_suite))
            return 0
        if a.cmd == "judge":
            with _stdin_devnull():
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
            return _release_exit(out)
        _emit(status(workspace=a.workspace, receiver_home=a.receiver_home))
        return 0
    except (OSError, ValueError, C.ContractError) as e:
        print(f"native_acceptance_bridge: {_oneline(e)}", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001 -- never a traceback
        print(f"native_acceptance_bridge: unexpected {type(e).__name__}: {_oneline(e)}",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
