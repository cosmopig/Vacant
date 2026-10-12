from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import types

import pytest

from vacant_network.adapters.hookpolicy import HookEvent, decide_pre_tool
from vacant_network.intake import contract as C
from vacant_network.intake.cli import EXIT as CLI_EXIT

ROOT = pathlib.Path(__file__).resolve().parents[1]
PATH = ROOT / "ops" / "eval" / "native_acceptance_bridge.py"
SPEC = importlib.util.spec_from_file_location("native_acceptance_bridge", PATH)
assert SPEC is not None and SPEC.loader is not None
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)

GOOD = "def add(a, b): return a + b\n"
BAD = "def add(a, b): return 0\n"
CHECK = "def check_add():\n    from solution import add\n    assert add(2, 3) == 5\n"
REAL_PREFLIGHT = bridge._preflight
_PF_CACHE: dict = {}


@pytest.fixture(autouse=True)
def _cached_preflight(monkeypatch):
    """The real preflight costs ~1 s per call with the `none` backend; cache it per backend.
    Tests about the preflight itself put REAL_PREFLIGHT back."""
    def cached(name, *, insecure_same_account):
        key = (name, insecure_same_account)
        if key not in _PF_CACHE:
            _PF_CACHE[key] = REAL_PREFLIGHT(name, insecure_same_account=insecure_same_account)
        return json.loads(json.dumps(_PF_CACHE[key]))
    monkeypatch.setattr(bridge, "_preflight", cached)


@pytest.fixture()
def env(tmp_path):
    ws = tmp_path / "app"
    suite = ws / "tests_visible"
    suite.mkdir(parents=True)
    (suite / "test_visible.py").write_text(CHECK, encoding="utf-8")
    (ws / "goal.md").write_text("Implement add(a, b).\n", encoding="utf-8")
    return ws, tmp_path / "receiver-home"


@pytest.fixture()
def public_tmp():
    # resolve(): on macOS /tmp is a symlink to /private/tmp, and the bridge refuses
    # a receiver home with a symlink component.
    d = pathlib.Path(tempfile.mkdtemp(prefix="bridge-test-", dir="/tmp")).resolve()
    d.chmod(0o755)
    yield d
    bridge._force_rmtree(d)


def _prepare(ws, receiver, *, task="c5-test", mode="repair", attempts=None, suite=None,
             sandbox="none", **kw):
    return bridge.prepare(
        workspace=ws, task_id=task, suite=suite, deliverable="solution.py",
        mode=mode, attempts=attempts, feedback_rounds=3, suite_timeout_s=20,
        destination=None, receiver_home=receiver, insecure_same_account=True,
        sandbox=sandbox, **kw,
    )


def _judge(ws, receiver, **kw):
    kw.setdefault("sandbox", "none")
    return bridge.judge(workspace=ws, receiver_home=receiver, **kw)


def _claim(res, claim_id):
    return next(r for r in res["results"] if r["claim_id"] == claim_id)


def _events(ws, receiver, kind=None):
    evs = bridge._task(ws, receiver).ledger.events()
    return [e for e in evs if kind is None or e["type"] == kind]


def _suite_dir(receiver):
    return receiver.with_name(receiver.name + "-suite")


def _fake_make_sandbox(backend="none", rc=0, out="1\n", exit_msg=None):
    """A stand-in for vrun.sandbox.make_sandbox (preflight failures without a broken host)."""
    def make(name, *, workdir, **kw):
        if exit_msg:
            raise SystemExit(exit_msg)
        sb = types.SimpleNamespace(
            hermetic=False,
            run=lambda cmd, **k: types.SimpleNamespace(rc=rc, stdout=out, stderr="python3: not found",
                                                       timed_out=False))
        return sb, {"backend": backend, "network_isolated": backend == "bwrap",
                    "write_confined": True, "repo_hidden_from_sandbox": backend == "bwrap",
                    "honest_bound": "fake"}
    return make


def _bwrap_usable() -> bool:
    return bool(shutil.which("bwrap")) and REAL_PREFLIGHT("bwrap", insecure_same_account=False)["ok"]


# ── the human's original behaviours ─────────────────────────────────────────────────────

def test_repair_contract_uses_receiver_pinned_executable_acceptance(env):
    ws, receiver = env
    out = _prepare(ws, receiver)
    c = C.load(ws / ".vacant" / "contract.json")
    assert out["prepared"] is True
    assert out["suite_sha256"] == c.input_pin("visible_suite")
    assert out["receiver_intake_root"] == str(receiver / "intake")
    # F12: the two safety floors of the scaffold survive; the visible suite is appended
    claims = {x.id: x for x in c.claims}
    assert list(claims) == ["deliverable_present", "no_secrets_shipped", "visible_acceptance"]
    assert claims["visible_acceptance"].verifier == "python_checks"
    assert claims["visible_acceptance"].params["suite"] == "input:visible_suite"
    assert claims["visible_acceptance"].params["timeout_s"] == 20
    assert c.raw["unknown_policy"] == "hold" and c.raw["conflict_policy"] == "escalate"
    assert c.hooks["stop_check"] is True
    assert c.hooks["submit_on_end"] is False
    assert c.max_attempts == 1
    assert (receiver / "intake" / "keys" / "owner" / "identity.key").is_file()
    assert out["insecure_same_account"] is True
    assert (receiver / "contract.json").is_file()
    assert (receiver / "contract.json").read_bytes() == (ws / ".vacant" / "contract.json").read_bytes()


def test_external_receiver_owned_suite_can_be_pinned(env, tmp_path):
    ws, receiver = env
    external = tmp_path / "receiver-suite"
    external.mkdir()
    (external / "test_visible.py").write_text(
        "def check_add():\n"
        "    from solution import add\n"
        "    assert add(1, 1) == 2\n",
        encoding="utf-8",
    )
    out = _prepare(ws, receiver, task="external-suite", suite=external)
    c = C.load(ws / ".vacant" / "contract.json")
    assert c.input_path("visible_suite") == receiver.with_name(receiver.name + "-suite")
    assert out["suite_sha256"] == C.path_sha256(external)


def test_agent_visible_suite_is_not_the_pinned_receiver_copy(env):
    ws, receiver = env
    _prepare(ws, receiver, task="c5-protect")
    c = C.load(ws / ".vacant" / "contract.json")
    ev = HookEvent(agent="pi", kind="pre_tool", tool="write",
                   paths=["tests_visible/test_visible.py"], cwd=str(ws))
    d = decide_pre_tool(ev, c)
    assert d.action == "allow"
    assert c.input_path("visible_suite") != ws / "tests_visible"


def test_bridge_rejects_bad_candidate_accepts_good_and_releases(env):
    ws, receiver = env
    _prepare(ws, receiver, task="c5-flow", mode="conform", attempts=2)
    (ws / "solution.py").write_text(BAD, encoding="utf-8")
    bad = _judge(ws, receiver, attempt=1)
    assert bad["outcome"] == "reject"

    (ws / "solution.py").write_text(GOOD, encoding="utf-8")
    good = _judge(ws, receiver, attempt=2)
    assert good["outcome"] == "accept"
    accepted_sha = good["artifact_sha256"]

    rel = bridge.release(workspace=ws, artifact_sha256=accepted_sha, receiver_home=receiver)
    assert rel["released"] is True
    published = receiver / "released" / "c5-flow" / "solution.py"
    assert published.read_text(encoding="utf-8") == GOOD

    st = bridge.status(workspace=ws, receiver_home=receiver)
    assert st["state"] == "released"
    assert st["latest_artifact"] == accepted_sha
    assert st["destination_live"]["artifact_sha256"] == accepted_sha
    assert st["attempts_used"] == 2 and st["attempts_max"] == 2


def test_agent_copy_edit_does_not_change_receiver_suite(env):
    """F21: the agent's /app/tests_visible is only a copy; emptying it changes nothing."""
    ws, receiver = env
    _prepare(ws, receiver, task="c5-copy-edit")
    (ws / "solution.py").write_text(BAD, encoding="utf-8")
    (ws / "tests_visible" / "test_visible.py").write_text("def check_add():\n    pass\n",
                                                          encoding="utf-8")
    res = _judge(ws, receiver, attempt=1)
    assert res["outcome"] == "reject"
    assert _claim(res, "visible_acceptance")["status"] == "FAIL"
    assert res["agent_visible_suite_matches_pinned"] is False       # F14: observed, not gating


def test_receiver_suite_drift_after_prepare_holds_and_uses_the_attempt(env):
    """F21: the pinned receiver suite changed after prepare => UNKNOWN => hold, never accept."""
    ws, receiver = env
    _prepare(ws, receiver, task="c5-drift", mode="conform", attempts=2)
    suite = _suite_dir(receiver)
    suite.chmod(0o755)
    (suite / "test_visible.py").chmod(0o644)
    (suite / "test_visible.py").write_text("def check_any():\n    assert True\n", encoding="utf-8")
    (ws / "solution.py").write_text(BAD, encoding="utf-8")
    res = _judge(ws, receiver, attempt=1)
    assert res["outcome"] == "hold"                                  # unknown_policy=hold
    vis = _claim(res, "visible_acceptance")
    assert vis["status"] == "UNKNOWN" and "changed since it was pinned" in vis["detail"]
    # a hold is a decision: it used attempt 1
    with pytest.raises(ValueError, match="attempt must be 2"):
        _judge(ws, receiver, attempt=1)


def test_conform_mode_requires_outer_attempt_accounting(env):
    ws, receiver = env
    out = _prepare(ws, receiver, task="c5-conform", mode="conform")
    c = C.load(ws / ".vacant" / "contract.json")
    assert out["attempts"] == 5
    assert c.hooks["stop_check"] is False
    assert c.hooks["submit_on_end"] is False
    assert c.max_attempts == 5
    (ws / "solution.py").write_text(GOOD, encoding="utf-8")
    with pytest.raises(ValueError, match="requires --attempt"):
        _judge(ws, receiver)
    ok = _judge(ws, receiver, attempt=1)
    assert ok["outcome"] == "accept"


def test_gate_and_repair_defaults(env):
    ws, receiver = env
    _prepare(ws, receiver, task="gate", mode="gate")
    c = C.load(ws / ".vacant" / "contract.json")
    assert c.hooks["stop_check"] is False and c.hooks["max_feedback_rounds"] == 0
    assert c.max_attempts == 1
    ws2 = ws.parent / "app2"
    shutil.copytree(ws, ws2, ignore=shutil.ignore_patterns(".vacant"))
    _prepare(ws2, ws.parent / "rh2", task="repair", mode="repair")
    c2 = C.load(ws2 / ".vacant" / "contract.json")
    assert c2.hooks["stop_check"] is True and c2.hooks["max_feedback_rounds"] == 3


def test_prepare_refuses_to_silently_replace_contract(env):
    ws, receiver = env
    _prepare(ws, receiver, task="c5-replace", mode="gate")
    with pytest.raises(ValueError, match="already exists"):
        _prepare(ws, receiver, task="c5-replace", mode="gate")


def test_workspace_that_already_has_a_contract_is_not_reused_with_a_new_home(env):
    ws, receiver = env
    _prepare(ws, receiver, task="reuse-ws", mode="gate")
    before = (ws / ".vacant" / "contract.json").read_bytes()
    with pytest.raises(ValueError, match="contract already exists"):
        _prepare(ws, receiver.parent / "other-home", task="reuse-ws", mode="gate")
    assert (ws / ".vacant" / "contract.json").read_bytes() == before
    assert not (receiver.parent / "other-home").exists()


def test_a_symlinked_suite_directory_is_refused(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (real / "test_visible.py").write_text(CHECK)
    link = tmp_path / "link"
    link.symlink_to(real)
    with pytest.raises(ValueError, match="symlink"):
        bridge._suite_files(link)
    assert bridge._suite_files(real)


def test_missing_inside_or_same_account_receiver_is_refused(env):
    ws, receiver = env
    kwargs = dict(workspace=ws, task_id="boundary", suite=None,
                  deliverable="solution.py", mode="gate", attempts=None,
                  feedback_rounds=0, suite_timeout_s=20, destination=None)
    with pytest.raises(ValueError, match="required"):
        bridge.prepare(**kwargs, receiver_home=None)
    with pytest.raises(ValueError, match="separate"):
        bridge.prepare(**kwargs, receiver_home=ws / "receiver",
                       insecure_same_account=True)
    with pytest.raises(ValueError, match="separate"):         # the workspace inside the home
        bridge.prepare(**kwargs, receiver_home=ws.parent, insecure_same_account=True)
    with pytest.raises(ValueError, match="same-account"):
        bridge.prepare(**kwargs, receiver_home=receiver)


def test_previous_run_cannot_be_released_after_rejected_new_run(env):
    ws, receiver = env
    _prepare(ws, receiver, task="reuse", mode="conform", attempts=2)
    (ws / "solution.py").write_text(GOOD)
    good = _judge(ws, receiver, attempt=1)
    assert good["outcome"] == "accept"
    with pytest.raises(ValueError, match="already accepted"):
        _judge(ws, receiver, attempt=2)
    with pytest.raises(ValueError, match="already exists"):
        _prepare(ws, receiver, task="reuse")
    assert not bridge.release(workspace=ws, receiver_home=receiver,
                              artifact_sha256="0" * 64)["released"]
    assert bridge.release(workspace=ws, receiver_home=receiver,
                          artifact_sha256=good["artifact_sha256"])["released"]


def test_attempts_are_monotonic_and_bounded(env):
    ws, receiver = env
    _prepare(ws, receiver, task="attempts", mode="conform", attempts=2)
    (ws / "solution.py").write_text(BAD)
    assert _judge(ws, receiver, attempt=1)["outcome"] == "reject"
    with pytest.raises(ValueError, match="attempt must be 2"):
        _judge(ws, receiver, attempt=1)
    assert _judge(ws, receiver, attempt=2)["outcome"] == "reject"
    with pytest.raises(ValueError, match="outside|attempt must be"):
        _judge(ws, receiver, attempt=3)
    st = bridge.status(workspace=ws, receiver_home=receiver)
    assert st["attempts"] == 2 and st["attempts_used"] == 2


def test_nested_or_nonexecuting_suite_refused_before_agent_starts(env):
    ws, receiver = env
    nested = ws / "tests_visible" / "nested"
    nested.mkdir()
    (nested / "test_hidden.py").write_text("def check_bad(): assert False\n")
    with pytest.raises(ValueError, match="nested"):
        _prepare(ws, receiver)
    (nested / "test_hidden.py").unlink()
    nested.rmdir()
    (ws / "tests_visible" / "test_visible.py").write_text("def test_add(): assert False\n")
    with pytest.raises(ValueError, match=r"check_\* or main"):
        _prepare(ws, receiver)


# ── item 1: attempts, preflight, informational drift (F02 F03 F05 F07 F11) ──────────────

def test_sandbox_argument_is_validated_up_front(env, capsys):
    ws, receiver = env
    _prepare(ws, receiver, task="choices", mode="gate")
    with pytest.raises(SystemExit):                       # argparse choices, exit 2
        bridge.main(["judge", "--workspace", str(ws), "--receiver-home", str(receiver),
                     "--sandbox", "bwrapp"])
    with pytest.raises(ValueError, match="--sandbox must be one of"):
        _judge(ws, receiver, sandbox="bwrapp")
    assert _events(ws, receiver, "attempt_started") == []         # nothing consumed
    for sub in ("prepare", "judge"):
        extra = ["--task-id", "x"] if sub == "prepare" else []
        with pytest.raises(SystemExit):
            bridge._parser().parse_args([sub, *extra, "--sandbox", "docker"])


def test_failed_preflight_is_void_and_does_not_use_the_attempt(env, monkeypatch, capsys):
    ws, receiver = env
    _prepare(ws, receiver, task="pf", mode="gate")
    (ws / "solution.py").write_text(GOOD)
    monkeypatch.setattr(bridge, "_preflight", REAL_PREFLIGHT)
    monkeypatch.setattr(bridge, "make_sandbox", _fake_make_sandbox(exit_msg="no sandbox here"))
    res = _judge(ws, receiver)
    assert res["void"] is True and res["outcome"] is None
    assert "no sandbox here" in " ".join(res["reasons"])
    assert [e["stage"] for e in _events(ws, receiver, "infra_void")] == ["preflight"]
    assert _events(ws, receiver, "infra_void")[0]["attempt"] == 1
    assert _events(ws, receiver, "attempt_started") == []             # never started
    rc = bridge.main(["judge", "--workspace", str(ws), "--receiver-home", str(receiver),
                      "--sandbox", "none"])
    assert rc == bridge.EXIT["void"] == 43
    capsys.readouterr()
    monkeypatch.undo()
    # the host is fine again: the same (only) attempt is still available
    assert _judge(ws, receiver, attempt=1)["outcome"] == "accept"


def test_preflight_looks_up_make_sandbox_at_call_time(monkeypatch):
    monkeypatch.setattr(bridge, "_preflight", REAL_PREFLIGHT)
    monkeypatch.setattr(bridge._sandbox, "make_sandbox", _fake_make_sandbox(exit_msg="patched at the source"))
    pf = bridge._preflight("auto", insecure_same_account=True)
    assert pf["ok"] is False and "patched at the source" in pf["reasons"][0]
    assert pf["backend"] is None


def test_python3_missing_in_sandbox_is_void_not_reject(env, monkeypatch):
    """F05: the driver rc=127 case never reaches the verifier, so a good solution is not rejected."""
    ws, receiver = env
    _prepare(ws, receiver, task="nopy", mode="gate")
    (ws / "solution.py").write_text(GOOD)
    monkeypatch.setattr(bridge, "_preflight", REAL_PREFLIGHT)
    monkeypatch.setattr(bridge, "make_sandbox", _fake_make_sandbox(rc=127, out=""))
    res = _judge(ws, receiver)
    assert res["void"] is True and "python3 does not run" in res["reasons"][0]
    assert _events(ws, receiver, "decision") == []
    monkeypatch.undo()
    assert _judge(ws, receiver)["outcome"] == "accept"


def test_workspace_contract_drift_is_informational_only(env):
    """F03 + H1: the receiver's contract decides; the workspace copy is only compared."""
    ws, receiver = env
    _prepare(ws, receiver, task="tamper", mode="conform", attempts=2)
    (ws / "solution.py").write_text(BAD)
    cp = ws / ".vacant" / "contract.json"
    cp.write_text(cp.read_text().replace('"python_checks"', '"static"'))   # a weaker verifier
    result = _judge(ws, receiver, attempt=1)
    assert result["outcome"] == "reject"                                  # still the receiver's contract
    assert _claim(result, "visible_acceptance")["verifier"] == "python_checks"
    assert result["workspace_contract_matches_receiver"] is False
    assert _events(ws, receiver, "infra_void") == []
    st = bridge.status(workspace=ws, receiver_home=receiver)
    assert st["attempts_used"] == 1 and st["workspace_contract_matches_receiver"] is False
    started = _events(ws, receiver, "attempt_started")[0]
    assert started["workspace_contract_matches_receiver"] is False


def test_deleted_workspace_contract_does_not_block_judge_or_release(env):
    """F03/F07: `git clean -fd` or a fresh /app must not hold, void or burn attempts."""
    ws, receiver = env
    _prepare(ws, receiver, task="gitclean", mode="gate")
    shutil.rmtree(ws / ".vacant")
    (ws / "solution.py").write_text(GOOD)
    res = _judge(ws, receiver)
    assert res["outcome"] == "accept" and res["workspace_contract_matches_receiver"] is False
    rel = bridge.release(workspace=ws, receiver_home=receiver, artifact_sha256=res["artifact_sha256"])
    assert rel["released"] is True and rel["workspace_contract_matches_receiver"] is False


def test_workspace_contract_comparison_is_byte_exact_not_json(env):
    ws, receiver = env
    _prepare(ws, receiver, task="bytes", mode="gate")
    cp, rc = ws / ".vacant" / "contract.json", receiver / "contract.json"
    st = bridge.status(workspace=ws, receiver_home=receiver)
    assert st["workspace_contract_matches_receiver"] is True
    cp.write_text(cp.read_text() + "\n")                  # same JSON, different bytes
    assert bridge.status(workspace=ws, receiver_home=receiver)["workspace_contract_matches_receiver"] is False
    cp.write_bytes(rc.read_bytes())
    assert bridge.status(workspace=ws, receiver_home=receiver)["workspace_contract_matches_receiver"] is True


def test_hostile_workspace_contract_cannot_crash_any_command(env):
    """F11: a 200k-deep JSON is not parsed at all."""
    ws, receiver = env
    _prepare(ws, receiver, task="deep", mode="gate")
    (ws / ".vacant" / "contract.json").write_text("[" * 200000)
    (ws / "solution.py").write_text(GOOD)
    st = bridge.status(workspace=ws, receiver_home=receiver)
    assert st["workspace_contract_matches_receiver"] is False
    res = _judge(ws, receiver)
    assert res["outcome"] == "accept"
    assert bridge.release(workspace=ws, receiver_home=receiver,
                          artifact_sha256=res["artifact_sha256"])["released"] is True


def test_judge_exception_is_void_exit_43_and_the_attempt_stays_available(env, monkeypatch, capsys):
    ws, receiver = env
    _prepare(ws, receiver, task="boom", mode="gate")
    (ws / "solution.py").write_text(GOOD)
    real_submit = bridge.flow.submit

    def boom(*a, **k):
        raise RuntimeError("disk exploded")
    monkeypatch.setattr(bridge.flow, "submit", boom)
    argv = ["judge", "--workspace", str(ws), "--receiver-home", str(receiver), "--sandbox", "none"]
    assert bridge.main(argv) == 43
    out = json.loads(capsys.readouterr().out)
    assert out["void"] is True and "disk exploded" in out["reasons"][0]
    voids = _events(ws, receiver, "infra_void")
    assert [(v["stage"], v["attempt"]) for v in voids] == [("judge", 1)]
    assert "disk exploded" in voids[0]["error"]
    started = _events(ws, receiver, "attempt_started")
    assert len(started) == 1 and started[0]["sandbox_backend"] == "none"
    assert bridge.status(workspace=ws, receiver_home=receiver)["attempts_used"] == 0
    monkeypatch.setattr(bridge.flow, "submit", real_submit)
    assert bridge.main(argv) == 0                                  # same attempt number, accepted


def test_flow_level_void_does_not_use_the_attempt_either(env, monkeypatch):
    ws, receiver = env
    _prepare(ws, receiver, task="flowvoid", mode="gate")
    (ws / "solution.py").write_text(GOOD)
    orig = bridge.flow._verify_manifest
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("transient disk error")
        return orig(*a, **k)
    monkeypatch.setattr(bridge.flow, "_verify_manifest", flaky)
    assert _judge(ws, receiver)["void"] is True
    assert _judge(ws, receiver)["outcome"] == "accept"


def test_killed_judge_does_not_use_an_attempt_and_voids_are_capped(env, capsys):
    """F02: attempts used = decisions. A started-but-never-decided try (kill -9) is free,
    but 3 failed tries at one attempt number stop the cell."""
    ws, receiver = env
    _prepare(ws, receiver, task="killed", mode="gate")
    (ws / "solution.py").write_text(GOOD)
    task = bridge._task(ws, receiver)
    sha = task.contract.sha256
    for _ in range(2):          # two killed judges
        task.ledger.append("attempt_started", {"contract_sha256": sha, "attempt": 1})
    assert bridge.status(workspace=ws, receiver_home=receiver)["attempts_used"] == 0
    task.ledger.append("attempt_started", {"contract_sha256": sha, "attempt": 1})   # the third
    n_before = len(_events(ws, receiver))
    argv = ["judge", "--workspace", str(ws), "--receiver-home", str(receiver), "--sandbox", "none"]
    assert bridge.main(argv) == 43
    out = json.loads(capsys.readouterr().out)
    assert "void cap reached for attempt 1" in out["reasons"][0]
    assert "fresh receiver home" in out["reasons"][0]
    assert len(_events(ws, receiver)) == n_before                  # nothing recorded
    # a fresh home is the way out
    ws2 = ws.parent / "app2"
    shutil.copytree(ws, ws2, ignore=shutil.ignore_patterns(".vacant"))
    _prepare(ws2, ws.parent / "rh2", task="killed")
    assert _judge(ws2, ws.parent / "rh2")["outcome"] == "accept"


def test_preflight_voids_count_toward_the_cap(env):
    ws, receiver = env
    _prepare(ws, receiver, task="pfcap", mode="gate")
    task = bridge._task(ws, receiver)
    for _ in range(3):
        task.ledger.append("infra_void", {"contract_sha256": task.contract.sha256,
                                          "stage": "preflight", "attempt": 1, "error": "x"})
    res = _judge(ws, receiver)
    assert res["void"] is True and "void cap" in res["reasons"][0]


def test_two_voids_below_the_cap_still_judge(env):
    ws, receiver = env
    _prepare(ws, receiver, task="pf2", mode="gate")
    (ws / "solution.py").write_text(GOOD)
    task = bridge._task(ws, receiver)
    for _ in range(2):
        task.ledger.append("infra_void", {"contract_sha256": task.contract.sha256,
                                          "stage": "judge", "attempt": 1, "error": "x"})
    assert _judge(ws, receiver)["outcome"] == "accept"


def test_unexpected_exception_in_a_subcommand_is_one_line_exit_2(env, monkeypatch, capsys):
    ws, receiver = env
    _prepare(ws, receiver, task="oneline", mode="gate")

    def deep(**k):
        raise RecursionError("maximum\nrecursion depth exceeded")
    monkeypatch.setattr(bridge, "status", deep)
    rc = bridge.main(["status", "--workspace", str(ws), "--receiver-home", str(receiver)])
    err = capsys.readouterr().err
    assert rc == 2 and err.count("\n") == 1 and "Traceback" not in err
    assert "RecursionError" in err
    monkeypatch.setattr(bridge, "release", lambda **k: (_ for _ in ()).throw(KeyError("x")))
    assert bridge.main(["release", "--workspace", str(ws), "--receiver-home", str(receiver),
                        "--artifact", "a"]) == 2


def test_judge_records_backend_and_observations(env):
    ws, receiver = env
    out = _prepare(ws, receiver, task="meta", mode="gate")
    c = C.load(receiver / "contract.json")
    assert out["sandbox_backend"] == c.raw["notes"]["sandbox_backend"] == "none"
    assert c.raw["notes"]["evaluator_euid"] == out["evaluator_euid"] == os.geteuid()
    assert c.raw["notes"]["verifier_sandbox"]["backend"] == "none"
    (ws / "solution.py").write_text(GOOD)
    res = _judge(ws, receiver)
    assert res["sandbox_backend"] == "none" and res["attempt"] == 1
    assert res["workspace_contract_matches_receiver"] is True
    assert _claim(res, "visible_acceptance")["evidence"]["sandbox"] == "none"
    started = _events(ws, receiver, "attempt_started")[0]
    assert started["sandbox_backend"] == "none" and started["attempt"] == 1
    assert started["contract_sha256"] == c.sha256


# ── item 3 (F04), item 10 (F10): suite shape, atomic prepare ────────────────────────────

def _suite_case_data_file(s): (s / "cases.json").write_text("[]")
def _suite_case_subdir(s): (s / "data").mkdir()
def _suite_case_symlink(s): (s / "link.py").symlink_to("/etc/hostname")
def _suite_case_pyc_dir_symlink(s): (s / "__pycache__").symlink_to("/tmp")
def _suite_case_required_params(s):
    (s / "test_visible.py").write_text(CHECK + "def check_eq(a, b):\n    assert a == b\n")
def _suite_case_kwonly(s):
    (s / "test_visible.py").write_text(CHECK + "def check_kw(*, a):\n    assert a\n")


@pytest.mark.parametrize("build,needle,why", [
    (_suite_case_data_file, "cases.json", "not a .py file"),
    (_suite_case_subdir, "data", "subdirectory"),
    (_suite_case_symlink, "link.py", "symlinks are not allowed"),
    (_suite_case_pyc_dir_symlink, "__pycache__", "symlinks are not allowed"),
    (_suite_case_required_params, "check_eq", "required parameters"),
    (_suite_case_kwonly, "check_kw", "required parameters"),
])
def test_suite_the_executor_cannot_run_is_refused_and_nothing_is_created(env, build, needle, why):
    ws, receiver = env
    build(ws / "tests_visible")
    deep = receiver.parent / "new-parent" / "rh"
    with pytest.raises(ValueError, match=needle) as ei:
        _prepare(ws, deep)
    assert why in str(ei.value) and "top-level .py files" in str(ei.value)
    assert not deep.parent.exists() and not _suite_dir(deep).exists()
    assert not (ws / ".vacant").exists()


def test_suite_shapes_the_executor_does_run_are_accepted(env):
    ws, receiver = env
    s = ws / "tests_visible"
    (s / "_support.py").write_text("X = 1\n")
    (s / "__pycache__").mkdir()
    (s / "__pycache__" / "test_visible.cpython-311.pyc").write_bytes(b"\0")
    (s / "test_visible.py").write_text(
        CHECK + "def check_default(n=3, *args, **kw):\n    assert n\n")
    _prepare(ws, receiver)
    assert not (_suite_dir(receiver) / "__pycache__").exists()       # never pinned


def test_validation_failures_create_nothing_and_a_retry_works(env):
    ws, receiver = env
    deep = receiver.parent / "a" / "b" / "rh"
    with pytest.raises(ValueError, match="attempts must be in 1..10"):
        _prepare(ws, deep, attempts=11)
    with pytest.raises(ValueError, match="inside receiver home"):
        bridge.prepare(workspace=ws, task_id="t", suite=None, deliverable="solution.py",
                       mode="gate", attempts=None, feedback_rounds=0, suite_timeout_s=20,
                       destination="dir:/tmp/elsewhere-outside", receiver_home=deep,
                       insecure_same_account=True, sandbox="none")
    assert not (receiver.parent / "a").exists() and not _suite_dir(deep).exists()
    assert not (ws / ".vacant").exists()
    assert _prepare(ws, deep)["prepared"] is True                    # same home, same workspace


def test_failure_after_creation_rolls_back_everything(env, monkeypatch):
    ws, receiver = env
    deep = receiver.parent / "a" / "b" / "rh"

    def full(*a, **k):
        raise RuntimeError("disk full")
    monkeypatch.setattr(bridge.flow, "lock", full)
    with pytest.raises(RuntimeError, match="disk full"):
        _prepare(ws, deep)
    assert not (receiver.parent / "a").exists()          # parents this call made
    assert not _suite_dir(deep).exists()                 # the read-only snapshot
    assert not (ws / ".vacant").exists()
    monkeypatch.undo()
    assert _prepare(ws, deep)["prepared"] is True


def test_rollback_keeps_what_the_caller_already_had(env, monkeypatch):
    ws, receiver = env
    receiver.mkdir()
    (receiver / "mine.txt").write_text("keep")
    (ws / ".vacant").mkdir()
    monkeypatch.setattr(bridge.flow, "lock", lambda *a, **k: (_ for _ in ()).throw(OSError("x")))
    with pytest.raises(OSError):
        _prepare(ws, receiver)
    assert os.listdir(receiver) == ["mine.txt"] and (ws / ".vacant").is_dir()
    assert os.listdir(ws / ".vacant") == []


def test_force_rmtree_removes_a_read_only_tree(tmp_path, monkeypatch):
    """The snapshot is 0555/0444: a non-root evaluator must chmod before it can remove it.
    Root would not notice, so rmtree is replaced by a stand-in with non-root semantics."""
    real = shutil.rmtree

    def non_root_rmtree(path, ignore_errors=False, **kw):
        if any(q.is_dir() and not q.stat().st_mode & 0o200 for q in (path, *path.rglob("*"))):
            if ignore_errors:
                return                                  # silently leaves the tree behind
            raise PermissionError(str(path))
        real(path, ignore_errors=ignore_errors, **kw)
    monkeypatch.setattr(bridge.shutil, "rmtree", non_root_rmtree)
    t = tmp_path / "ro"
    (t / "sub").mkdir(parents=True)
    (t / "sub" / "f.py").write_text("x")
    (t / "sub" / "f.py").chmod(0o444)
    (t / "sub").chmod(0o555)
    t.chmod(0o555)
    bridge._force_rmtree(t)
    assert not t.exists()


def test_suite_changed_while_snapshotting_is_refused_and_rolled_back(env, monkeypatch):
    ws, receiver = env
    real = shutil.copytree

    def racing(src, dst, **kw):
        out = real(src, dst, **kw)
        (pathlib.Path(src) / "test_visible.py").write_text("def check_add():\n    pass\n")
        return out                                      # the agent edits the source mid-copy
    monkeypatch.setattr(bridge.shutil, "copytree", racing)
    with pytest.raises(ValueError, match="changed while being snapshotted"):
        _prepare(ws, receiver)
    assert not receiver.exists() and not _suite_dir(receiver).exists()
    assert not (ws / ".vacant").exists()


def test_existing_receiver_suite_is_refused_and_left_alone(env):
    ws, receiver = env
    _suite_dir(receiver).mkdir()
    (_suite_dir(receiver) / "keep.txt").write_text("mine")
    with pytest.raises(ValueError, match="receiver suite already exists"):
        _prepare(ws, receiver)
    assert (_suite_dir(receiver) / "keep.txt").read_text() == "mine"
    assert not receiver.exists() and not (ws / ".vacant").exists()


# ── item 4 (F12), 5 (F13), 6 (F14) ──────────────────────────────────────────────────────

def test_scaffold_safety_floors_still_apply(env):
    """F12: a suite that never touches the deliverable cannot accept a missing file."""
    ws, receiver = env
    (ws / "tests_visible" / "test_visible.py").write_text("def check_nothing():\n    pass\n")
    _prepare(ws, receiver, task="floors", mode="gate")
    res = _judge(ws, receiver)
    assert res["outcome"] == "reject"
    assert _claim(res, "deliverable_present")["status"] == "FAIL"
    assert _claim(res, "visible_acceptance")["status"] == "PASS"


def test_secret_files_in_the_workspace_are_not_published(env):
    ws, receiver = env
    bridge_args = dict(workspace=ws, task_id="keys", suite=None, deliverable="**", mode="gate",
                       attempts=None, feedback_rounds=0, suite_timeout_s=20, destination=None,
                       receiver_home=receiver, insecure_same_account=True, sandbox="none")
    bridge.prepare(**bridge_args)
    (ws / "solution.py").write_text(GOOD)
    (ws / "identity.key").write_text("PRIVATE")
    (ws / "x" / "intake" / "keys" / "owner").mkdir(parents=True)
    (ws / "x" / "intake" / "keys" / "owner" / "note.txt").write_text("PRIVATE")
    res = _judge(ws, receiver)
    assert res["outcome"] == "accept"
    assert _claim(res, "no_secrets_shipped")["status"] == "PASS"
    rel = bridge.release(workspace=ws, receiver_home=receiver, artifact_sha256=res["artifact_sha256"])
    assert rel["released"] is True
    names = {p.name for p in (receiver / "released").rglob("*") if p.is_file()}
    assert "solution.py" in names and "identity.key" not in names and "note.txt" not in names


def test_destination_must_be_a_dir_inside_the_receiver_home(env):
    ws, receiver = env
    for dest, msg in (("dir:/tmp/elsewhere-outside", "inside receiver home"),
                      ("dir:out", "inside receiver home"),          # relative => the workspace
                      ("git:/tmp/x", "dir:"),
                      (f"dir:{receiver}", "inside receiver home")):
        with pytest.raises(ValueError, match=msg):
            bridge.prepare(workspace=ws, task_id="d", suite=None, deliverable="solution.py",
                           mode="gate", attempts=None, feedback_rounds=0, suite_timeout_s=20,
                           destination=dest, receiver_home=receiver,
                           insecure_same_account=True, sandbox="none")
    _prepare_dest = bridge.prepare(workspace=ws, task_id="d", suite=None, deliverable="solution.py",
                                   mode="gate", attempts=None, feedback_rounds=0,
                                   suite_timeout_s=20, destination=f"dir:{receiver}/out",
                                   receiver_home=receiver, insecure_same_account=True,
                                   sandbox="none")
    assert _prepare_dest["prepared"] is True


def test_release_destination_override_cannot_leave_the_receiver_home(env):
    ws, receiver = env
    _prepare(ws, receiver, task="relout", mode="gate")
    (ws / "solution.py").write_text(GOOD)
    res = _judge(ws, receiver)
    for dest in ("dir:" + str(ws / "out"), "dir:out", "git:/tmp/x"):
        with pytest.raises(ValueError):
            bridge.release(workspace=ws, receiver_home=receiver, destination=dest,
                           artifact_sha256=res["artifact_sha256"])
    assert not (ws / "out").exists() and not (ws / "released").exists()


def test_cli_has_no_replace_flag_and_documents_the_destination_rule():
    parser = bridge._parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["prepare", "--task-id", "x", "--replace"])
    prep = next(a for a in parser._subparsers._group_actions[0].choices["prepare"]._actions
                if "--destination" in a.option_strings)
    assert "inside the receiver home" in prep.help and "outside workspace" not in prep.help
    assert "--replace" not in bridge.__doc__


def test_agent_visible_suite_is_hashed_for_real_and_compared_with_the_pinned_one(env, tmp_path):
    """F14: with --suite the pinned copy differs from what the agent sees: say so."""
    ws, receiver = env
    external = tmp_path / "rsuite"
    external.mkdir()
    (external / "test_visible.py").write_text("def check_add():\n    from solution import add\n"
                                              "    assert add(1, 1) == 2\n")
    out = _prepare(ws, receiver, task="f14", mode="gate", suite=external)
    assert out["agent_visible_suite_sha256"] == C.path_sha256(ws / "tests_visible")
    assert out["pinned_suite_sha256"] == C.path_sha256(external) == out["suite_sha256"]
    assert out["agent_visible_suite_matches_pinned"] is False
    notes = C.load(receiver / "contract.json").raw["notes"]
    assert notes["agent_visible_suite_sha256"] == out["agent_visible_suite_sha256"]
    assert notes["pinned_suite_sha256"] == out["pinned_suite_sha256"]
    assert notes["agent_visible_suite_matches_pinned"] is False
    (ws / "solution.py").write_text(GOOD)
    res = _judge(ws, receiver)
    assert res["outcome"] == "accept"                    # the receiver's suite decides (add(1, 1) == 2)
    assert res["agent_visible_suite_matches_pinned"] is False


def test_agent_visible_suite_matches_by_default_and_judge_recomputes_it(env):
    ws, receiver = env
    out = _prepare(ws, receiver, task="f14b", mode="conform", attempts=2)
    assert out["agent_visible_suite_matches_pinned"] is True
    (ws / "solution.py").write_text(BAD)
    assert _judge(ws, receiver, attempt=1)["agent_visible_suite_matches_pinned"] is True
    (ws / "tests_visible" / "test_visible.py").write_text("def check_add():\n    pass\n")
    assert _judge(ws, receiver, attempt=2)["agent_visible_suite_matches_pinned"] is False
    assert bridge.status(workspace=ws, receiver_home=receiver)["agent_visible_suite_matches_pinned"] is False


def test_no_agent_suite_means_null_and_explicit_agent_suite_is_honoured(env, tmp_path):
    ws, receiver = env
    shutil.move(str(ws / "tests_visible"), str(tmp_path / "elsewhere"))
    external = tmp_path / "elsewhere"
    out = _prepare(ws, receiver, task="f14c", mode="gate", suite=external)
    assert out["agent_visible_suite_sha256"] is None
    assert out["agent_visible_suite_matches_pinned"] is None
    ws2 = tmp_path / "app2"
    ws2.mkdir()
    out2 = _prepare(ws2, tmp_path / "rh2", task="f14d", mode="gate", suite=external,
                    agent_suite=external)
    assert out2["agent_visible_suite_matches_pinned"] is True
    ws3 = tmp_path / "app3"
    ws3.mkdir()
    with pytest.raises(ValueError, match="agent visible suite does not exist"):
        _prepare(ws3, tmp_path / "rh3", task="f14e", mode="gate", suite=external,
                 agent_suite=tmp_path / "missing")


# ── item 7 (F09): release exit codes mirror `vacant release` ────────────────────────────

def test_exit_table_is_the_canonical_one():
    assert bridge.EXIT == CLI_EXIT


@pytest.mark.parametrize("res,code", [
    ({"released": True, "readback_ok": True}, 0),
    ({"released": True, "readback_ok": False}, 45),
    ({"released": False, "void": True}, 43),
    ({"released": False, "effect": "unknown", "readback_ok": False}, 45),
    ({"released": False, "effect": "already_published", "readback_ok": False}, 45),
    ({"released": False, "reasons": ["nope"]}, 44),
])
def test_release_exit_mapping(res, code):
    assert bridge._release_exit(res) == code


def test_release_exit_codes_end_to_end(env, capsys, monkeypatch):
    ws, receiver = env
    _prepare(ws, receiver, task="relexit", mode="gate")
    (ws / "solution.py").write_text(GOOD)
    res = _judge(ws, receiver)
    argv = ["release", "--workspace", str(ws), "--receiver-home", str(receiver)]
    assert bridge.main([*argv, "--artifact", "0" * 64]) == 44                 # refused
    (receiver / "released").write_text("a file where the directory should be")
    assert bridge.main([*argv, "--artifact", res["artifact_sha256"]]) == 43   # infra void
    assert bridge.status(workspace=ws, receiver_home=receiver)["state"] == "void"
    (receiver / "released").unlink()
    real = bridge.flow.release
    monkeypatch.setattr(bridge.flow, "release", lambda t, **k: {
        **real(t, **k), "released": False, "effect": "unknown", "readback_ok": False})
    assert bridge.main([*argv, "--artifact", res["artifact_sha256"]]) == 45   # effect unknown
    monkeypatch.undo()
    capsys.readouterr()
    assert bridge.main([*argv, "--artifact", res["artifact_sha256"]]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["released"] is True and out["readback_ok"] is True


def test_judge_exit_codes(env, capsys):
    ws, receiver = env
    _prepare(ws, receiver, task="judgeexit", mode="conform", attempts=2)
    argv = ["judge", "--workspace", str(ws), "--receiver-home", str(receiver), "--sandbox", "none"]
    (ws / "solution.py").write_text(BAD)
    assert bridge.main([*argv, "--attempt", "1"]) == 40
    (ws / "solution.py").write_text(GOOD)
    assert bridge.main([*argv, "--attempt", "2"]) == 0
    assert bridge.main([*argv, "--attempt", "3"]) == 2                         # refusal: one line
    assert capsys.readouterr().err.count("\n") == 1


# ── item 9 (F08): receiver home path must have no symlink component ─────────────────────

def test_symlinked_receiver_home_is_refused_everywhere(env, tmp_path):
    ws, receiver = env
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    with pytest.raises(ValueError, match="symlink"):
        _prepare(ws, link / "rh")
    assert not (real / "rh").exists()                      # refused before anything was created
    _prepare(ws, real / "rh", task="symlinks", mode="gate")
    (ws / "solution.py").write_text(GOOD)
    via = link / "rh"
    with pytest.raises(ValueError, match="symlink"):
        _judge(ws, via)
    with pytest.raises(ValueError, match="symlink"):
        bridge.release(workspace=ws, receiver_home=via, artifact_sha256="0" * 64)
    with pytest.raises(ValueError, match="symlink"):
        bridge.status(workspace=ws, receiver_home=via)
    home_link = tmp_path / "homelink"
    home_link.symlink_to(real / "rh")
    with pytest.raises(ValueError, match="symlink"):
        bridge.status(workspace=ws, receiver_home=home_link)
    assert bridge.status(workspace=ws, receiver_home=real / "rh")["state"] == "open"


# ── item 10 (F01 F17): sandbox policy ───────────────────────────────────────────────────

@pytest.mark.parametrize("name,insecure,ok", [
    ("none", False, False), ("unshare", False, False), ("bwrap", False, True),
    ("auto", False, True), ("none", True, True), ("unshare", True, True),
])
def test_sandbox_policy(name, insecure, ok):
    if ok:
        bridge._sandbox_policy(name, insecure)
    else:
        with pytest.raises(ValueError, match="does not hide files"):
            bridge._sandbox_policy(name, insecure)


def _non_insecure(monkeypatch, backend="bwrap"):
    """Reach the non-insecure code paths without a second uid (the uid rule has its own test)."""
    monkeypatch.setattr(bridge, "_boundary", lambda *a, **k: None)
    monkeypatch.setattr(bridge, "_preflight", REAL_PREFLIGHT)
    monkeypatch.setattr(bridge, "make_sandbox", _fake_make_sandbox(backend))


def _prepare_secure(ws, receiver, sandbox="auto", mode="gate"):
    return bridge.prepare(workspace=ws, task_id="secure", suite=None, deliverable="solution.py",
                          mode=mode, attempts=None, feedback_rounds=0, suite_timeout_s=20,
                          destination=None, receiver_home=receiver, sandbox=sandbox)


def test_non_insecure_prepare_refuses_files_not_isolated_from_the_candidate(env, monkeypatch):
    ws, receiver = env
    _non_insecure(monkeypatch, backend="none")
    with pytest.raises(ValueError, match="does not hide files"):
        _prepare_secure(ws, receiver, sandbox="none")
    with pytest.raises(ValueError, match="requires bwrap"):            # auto resolved to none
        _prepare_secure(ws, receiver, sandbox="auto")
    assert not receiver.exists() and not (ws / ".vacant").exists()
    monkeypatch.setattr(bridge, "make_sandbox", _fake_make_sandbox("bwrap"))
    out = _prepare_secure(ws, receiver, sandbox="auto")
    assert out["insecure_same_account"] is False and out["sandbox_backend"] == "bwrap"
    assert C.load(receiver / "contract.json").raw["notes"]["insecure_same_account"] is False


def test_non_insecure_judge_refuses_none_and_voids_when_auto_resolves_to_none(env, monkeypatch):
    ws, receiver = env
    _non_insecure(monkeypatch, backend="bwrap")
    _prepare_secure(ws, receiver)
    (ws / "solution.py").write_text(GOOD)
    with pytest.raises(ValueError, match="does not hide files"):
        _judge(ws, receiver, sandbox="none")
    assert _events(ws, receiver, "attempt_started") == []
    monkeypatch.setattr(bridge, "make_sandbox", _fake_make_sandbox("none"))
    res = _judge(ws, receiver, sandbox="auto")                      # host lost bwrap
    assert res["void"] is True and "requires bwrap" in res["reasons"][0]
    assert [e["stage"] for e in _events(ws, receiver, "infra_void")] == ["preflight"]
    assert _events(ws, receiver, "decision") == []


def test_task_rechecks_the_account_boundary_from_the_signed_contract(env, monkeypatch):
    ws, receiver = env
    _non_insecure(monkeypatch)
    _prepare_secure(ws, receiver)
    monkeypatch.undo()                  # the real boundary again: workspace owner == evaluator
    with pytest.raises(ValueError, match="same-account"):
        bridge.status(workspace=ws, receiver_home=receiver)


def test_parent_of_the_receiver_home_must_not_be_agent_writable(env, monkeypatch):
    ws, receiver = env
    _non_insecure(monkeypatch)
    receiver.parent.chmod(0o777)
    with pytest.raises(ValueError, match="receiver parent"):
        _prepare_secure(ws, receiver)
    assert not receiver.exists()
    receiver.parent.chmod(0o755)
    assert _prepare_secure(ws, receiver)["prepared"] is True


def test_repair_suite_must_be_readable_by_the_agent_account(env, monkeypatch):
    ws, receiver = env                                      # pytest's tmp dirs are 0700
    _non_insecure(monkeypatch)
    with pytest.raises(ValueError, match="readable by the agent"):
        _prepare_secure(ws, receiver, mode="repair")
    assert not receiver.exists() and not _suite_dir(receiver).exists()
    assert _prepare_secure(ws, receiver, mode="gate")["prepared"] is True   # only repair needs it


def test_repair_suite_in_a_traversable_tree_is_accepted(public_tmp, monkeypatch):
    ws = public_tmp / "app"
    (ws / "tests_visible").mkdir(parents=True)
    (ws / "tests_visible" / "test_visible.py").write_text(CHECK)
    _non_insecure(monkeypatch)
    out = _prepare_secure(ws, public_tmp / "rcv" / "vacant", mode="repair")
    assert out["stop_check"] is True
    assert (_suite_dir(public_tmp / "rcv" / "vacant").stat().st_mode & 0o777) == 0o555


def test_pinned_suite_is_read_only_and_symlink_free(env):
    ws, receiver = env
    _prepare(ws, receiver)
    suite = _suite_dir(receiver)
    assert suite.stat().st_mode & 0o222 == 0
    assert (suite / "test_visible.py").stat().st_mode & 0o222 == 0
    assert not any(p.is_symlink() for p in suite.rglob("*"))


def test_symlink_in_the_suite_is_refused(env):
    ws, receiver = env
    (ws / "tests_visible" / "link.py").symlink_to("/etc/hostname")
    with pytest.raises(ValueError, match="symlink"):
        _prepare(ws, receiver)


@pytest.mark.skipif(os.geteuid() != 0 or not shutil.which("setpriv") or not _bwrap_usable(),
                    reason="needs root, setpriv and a working bwrap")
def test_separate_account_layout_end_to_end_under_bwrap(public_tmp):
    ws = public_tmp / "app"
    (ws / "tests_visible").mkdir(parents=True)
    (ws / "tests_visible" / "test_visible.py").write_text(CHECK)
    (ws / "solution.py").write_text(GOOD)
    for p in (ws, *ws.rglob("*")):
        os.chown(p, 65534, 65534)
    rh = public_tmp / "receiver" / "vacant"
    out = bridge.prepare(workspace=ws, task_id="sepacct", suite=None, deliverable="solution.py",
                         mode="repair", attempts=None, feedback_rounds=1, suite_timeout_s=20,
                         destination=None, receiver_home=rh, insecure_same_account=False,
                         sandbox="auto")
    assert out["sandbox_backend"] == "bwrap" and out["insecure_same_account"] is False
    assert out["evaluator_euid"] == 0
    as_agent = ["setpriv", "--reuid=65534", "--regid=65534", "--clear-groups", sys.executable, "-c"]
    key = rh / "intake" / "keys" / "owner" / "identity.key"
    r = subprocess.run([*as_agent, f"open({str(key)!r}).read()"], capture_output=True, text=True)
    assert r.returncode != 0 and "Permission" in r.stderr          # the agent cannot read keys
    r = subprocess.run([*as_agent, f"open({str(_suite_dir(rh) / 'test_visible.py')!r}).read()"],
                       capture_output=True, text=True)
    assert r.returncode == 0                                       # ... but can read the pinned suite
    r = subprocess.run([*as_agent, f"open({str(rh / 'x')!r}, 'w')"], capture_output=True, text=True)
    assert r.returncode != 0                                       # ... nor write the receiver home
    with pytest.raises(ValueError, match="does not hide files"):
        bridge.judge(workspace=ws, receiver_home=rh, sandbox="none")
    res = bridge.judge(workspace=ws, receiver_home=rh, sandbox="auto")
    assert res["outcome"] == "accept" and res["sandbox_backend"] == "bwrap"
    assert _claim(res, "visible_acceptance")["evidence"]["sandbox"] == "bwrap"
    assert bridge.release(workspace=ws, receiver_home=rh,
                          artifact_sha256=res["artifact_sha256"])["released"] is True


@pytest.mark.skipif(not _bwrap_usable(), reason="needs bwrap")
def test_candidate_cannot_see_receiver_files_under_bwrap(env):
    ws, receiver = env
    _prepare(ws, receiver, task="bwrap-hidden", mode="gate", sandbox="bwrap")
    key = receiver / "intake" / "keys" / "owner" / "identity.key"
    (ws / "solution.py").write_text(
        f"import os\nLEAK = os.path.exists({str(key)!r})\n"
        "def add(a, b): return a + b if not LEAK else 0\n")
    assert _judge(ws, receiver, sandbox="bwrap")["outcome"] == "accept"


# ── item 11 (F20): effects.protect_paths ────────────────────────────────────────────────

def test_receiver_home_and_suite_are_protected_from_native_write_tools(env):
    ws, receiver = env
    _prepare(ws, receiver, task="protect")
    c = C.load(ws / ".vacant" / "contract.json")
    assert c.effects["protect_paths"] == [str(receiver), str(_suite_dir(receiver))]
    for target in (receiver / "contract.json", receiver / "intake" / "trust.json",
                   _suite_dir(receiver) / "test_visible.py"):
        ev = HookEvent(agent="pi", kind="pre_tool", tool="write", paths=[str(target)], cwd=str(ws))
        assert decide_pre_tool(ev, c).action == "deny", target
    ev = HookEvent(agent="pi", kind="pre_tool", tool="write", paths=[str(ws / "solution.py")],
                   cwd=str(ws))
    assert decide_pre_tool(ev, c).action == "allow"
    # documented limit: reads are not blocked
    ev = HookEvent(agent="pi", kind="pre_tool", tool="read",
                   paths=[str(_suite_dir(receiver) / "test_visible.py")], cwd=str(ws))
    assert decide_pre_tool(ev, c).action == "allow"


def test_shell_guard_denies_direct_writes_but_not_indirect_forms_or_reads(env):
    """The wording in the docstring, the contract note and README 5.2-6/8: direct shell writes
    into protect_paths are denied; indirect forms and every read are allowed (soft guard)."""
    ws, receiver = env
    _prepare(ws, receiver, task="shellguard")
    c = C.load(ws / ".vacant" / "contract.json")
    rh, suite = str(receiver), str(_suite_dir(receiver))

    def verdict(cmd):
        ev = HookEvent(agent="pi", kind="pre_tool", tool="bash", command=cmd, cwd=str(ws))
        return decide_pre_tool(ev, c).action

    for cmd in (f"echo x > {rh}/contract.json", f"echo x >> {rh}/contract.json",
                f"cp /tmp/x {rh}/contract.json", f"rm -rf {suite}", f"touch {rh}/x",
                f"echo x | tee {suite}/test_visible.py", f"sed -i s/5/6/ {suite}/test_visible.py",
                f"dd if=/dev/zero of={rh}/x",
                f"python3 -c \"open('{rh}/contract.json', 'w').write('x')\""):
        assert verdict(cmd) == "deny", cmd
    for cmd in (f"cat {rh}/contract.json", f"cat {rh}/intake/keys/owner/identity.key",
                f"cat {suite}/test_visible.py",
                f"BRIDGE_RH={rh}; echo x > $BRIDGE_RH/contract.json", "python3 attack.py"):
        assert verdict(cmd) == "allow", cmd
    for text in (bridge.__doc__, c.raw["notes"]["trust_boundary"]):
        assert "not blocked" not in text and "shell commands are not" not in text


# ── item 12 (W2, W3) and the lock ───────────────────────────────────────────────────────

def test_judge_does_not_eat_the_evaluators_stdin(env):
    ws, receiver = env
    _prepare(ws, receiver, task="stdin", mode="gate")
    (ws / "solution.py").write_text("import sys\n_ = sys.stdin.read()\n" + GOOD)
    cmd = (f"{sys.executable} {PATH} judge --workspace {ws} --receiver-home {receiver} "
           "--sandbox none >/dev/null; cat")
    r = subprocess.run(["sh", "-c", cmd], input=b"TASK_B\nTASK_C\n", capture_output=True,
                       env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert r.stdout == b"TASK_B\nTASK_C\n"
    assert bridge.status(workspace=ws, receiver_home=receiver)["state"] == "accepted"


def test_stdin_redirect_is_restored_afterwards():
    r, w = os.pipe()                       # pytest points fd 0 at /dev/null: use a real pipe
    saved = os.dup(0)
    try:
        os.dup2(r, 0)
        pipe_ino = os.fstat(0).st_ino
        with bridge._stdin_devnull():
            assert os.fstat(0).st_rdev == os.stat(os.devnull).st_rdev
        assert os.fstat(0).st_ino == pipe_ino              # the pipe is back on fd 0
    finally:
        os.dup2(saved, 0)
        for fd in (saved, r, w):
            os.close(fd)


def test_script_imports_its_own_checkout_first(tmp_path):
    """W3: a decoy vacant_network earlier on PYTHONPATH must not win."""
    assert str(ROOT) in sys.path            # (other test modules may push their own dir in front)
    decoy = tmp_path / "decoy" / "vacant_network"
    decoy.mkdir(parents=True)
    (decoy / "__init__.py").write_text("raise ImportError('decoy checkout imported')\n")
    r = subprocess.run([sys.executable, str(PATH), "--help"], capture_output=True, text=True,
                       cwd=tmp_path, env={"PATH": os.environ["PATH"], "HOME": str(tmp_path),
                                          "PYTHONPATH": str(tmp_path / "decoy"),
                                          "PYTHONDONTWRITEBYTECODE": "1"})
    assert r.returncode == 0, r.stderr
    assert "prepare" in r.stdout and "decoy" not in r.stderr


def test_judge_is_serialized_by_the_receiver_lock(env, monkeypatch):
    ws, receiver = env
    _prepare(ws, receiver, task="flock", mode="gate")
    (ws / "solution.py").write_text(GOOD)
    calls = []
    real = bridge.fcntl.flock
    def spy(fd, op):
        if str(getattr(fd, "name", "")).endswith("bridge.lock"):
            calls.append(op)
        return real(fd, op)
    monkeypatch.setattr(bridge.fcntl, "flock", spy)
    _judge(ws, receiver)
    assert calls == [bridge.fcntl.LOCK_EX, bridge.fcntl.LOCK_UN]


# ── H3: release only what was judged and accepted ───────────────────────────────────────

def test_rejected_artifact_is_never_released_and_release_publishes_the_judged_bytes(env):
    ws, receiver = env
    _prepare(ws, receiver, task="h3", mode="conform", attempts=2)
    (ws / "solution.py").write_text(BAD)
    bad = _judge(ws, receiver, attempt=1)
    assert bad["outcome"] == "reject"
    r = bridge.release(workspace=ws, receiver_home=receiver, artifact_sha256=bad["artifact_sha256"])
    assert r["released"] is False and "latest accepted" in r["reasons"][0]
    assert not (receiver / "released").exists()
    (ws / "solution.py").write_text(GOOD)
    good = _judge(ws, receiver, attempt=2)
    (ws / "solution.py").write_text(BAD)                  # the agent edits after judge
    r = bridge.release(workspace=ws, receiver_home=receiver, artifact_sha256=good["artifact_sha256"])
    assert r["released"] is True
    assert (receiver / "released" / "h3" / "solution.py").read_text() == GOOD
    # the older (rejected) artifact still cannot be released after a later accept
    assert bridge.release(workspace=ws, receiver_home=receiver,
                          artifact_sha256=bad["artifact_sha256"])["released"] is False


def test_receiver_contract_edited_without_relock_is_refused(env):
    ws, receiver = env
    _prepare(ws, receiver, task="relock", mode="gate")
    rc = receiver / "contract.json"
    raw = json.loads(rc.read_text())
    raw["objective"] = "weaker"
    rc.write_text(json.dumps(raw))
    (ws / ".vacant" / "contract.json").write_bytes(rc.read_bytes())   # keep the copy in sync
    (ws / "solution.py").write_text(BAD)
    for call in (lambda: _judge(ws, receiver),
                 lambda: bridge.release(workspace=ws, receiver_home=receiver, artifact_sha256="a"),
                 lambda: bridge.status(workspace=ws, receiver_home=receiver)):
        with pytest.raises(ValueError, match="lock invalid"):
            call()


def test_judging_another_workspace_with_a_prepared_home_is_refused(env, tmp_path):
    ws, receiver = env
    _prepare(ws, receiver, task="ws-mismatch", mode="gate")
    ws2 = tmp_path / "app2"
    shutil.copytree(ws, ws2)
    (ws2 / "solution.py").write_text(GOOD)
    with pytest.raises(ValueError, match="differs"):
        _judge(ws2, receiver)


@pytest.mark.parametrize("raw", ["///", "..", "   "])
def test_empty_task_id_is_refused(env, raw):
    ws, receiver = env
    with pytest.raises(ValueError, match="task id"):
        _prepare(ws, receiver, task=raw)


def test_long_task_id_is_trimmed_to_the_contract_limit(env):
    ws, receiver = env
    out = _prepare(ws, receiver, task="x" * 300)
    assert len(out["task_id"]) == 128


def test_emit_survives_a_non_utf8_file_name(capsys):
    """An agent-chosen file name that is not valid UTF-8 reaches the output as a lone
    surrogate; printing it must not crash after the verdict is already signed."""
    bridge._emit({"skipped": ["bad\udcffname.py"], "reasons": ["驗收"]})
    out = capsys.readouterr().out
    assert json.loads(out) == {"skipped": ["bad\udcffname.py"], "reasons": ["驗收"]}
    out.encode("ascii")
