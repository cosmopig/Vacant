from __future__ import annotations

import importlib.util
import pathlib

import pytest

from vacant_network.adapters.hookpolicy import HookEvent, decide_pre_tool
from vacant_network.intake import contract as C

ROOT = pathlib.Path(__file__).resolve().parents[1]
PATH = ROOT / "ops" / "eval" / "native_acceptance_bridge.py"
SPEC = importlib.util.spec_from_file_location("native_acceptance_bridge", PATH)
assert SPEC is not None and SPEC.loader is not None
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


@pytest.fixture()
def env(tmp_path):
    ws = tmp_path / "app"
    suite = ws / "tests_visible"
    suite.mkdir(parents=True)
    (suite / "test_visible.py").write_text(
        "def check_add():\n"
        "    from solution import add\n"
        "    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    (ws / "goal.md").write_text("Implement add(a, b).\n", encoding="utf-8")
    return ws, tmp_path / "receiver-home"


def _prepare(ws, receiver, *, task="c5-test", mode="repair", attempts=None, suite=None):
    return bridge.prepare(
        workspace=ws, task_id=task, suite=suite, deliverable="solution.py",
        mode=mode, attempts=attempts, feedback_rounds=3, suite_timeout_s=20,
        destination=None, receiver_home=receiver, insecure_same_account=True,
    )


def test_repair_contract_uses_receiver_pinned_executable_acceptance(env):
    ws, receiver = env
    out = _prepare(ws, receiver)
    c = C.load(ws / ".vacant" / "contract.json")
    assert out["prepared"] is True
    assert out["suite_sha256"] == c.input_pin("visible_suite")
    assert out["receiver_intake_root"] == str(receiver / "intake")
    assert c.claims[0].verifier == "python_checks"
    assert c.claims[0].params["suite"] == "input:visible_suite"
    assert c.hooks["stop_check"] is True
    assert c.hooks["submit_on_end"] is False
    assert c.max_attempts == 1
    assert (receiver / "intake" / "keys" / "owner" / "identity.key").is_file()
    assert out["insecure_same_account"] is True
    assert (receiver / "contract.json").is_file()


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
    (ws / "solution.py").write_text("def add(a, b): return 0\n", encoding="utf-8")
    bad = bridge.judge(workspace=ws, sandbox="none", attempt=1,
                       receiver_home=receiver)
    assert bad["outcome"] == "reject"

    (ws / "solution.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
    good = bridge.judge(workspace=ws, sandbox="none", attempt=2,
                        receiver_home=receiver)
    assert good["outcome"] == "accept"
    accepted_sha = good["artifact_sha256"]

    rel = bridge.release(workspace=ws, artifact_sha256=accepted_sha, receiver_home=receiver)
    assert rel["released"] is True
    published = receiver / "released" / "c5-flow" / "solution.py"
    assert published.read_text(encoding="utf-8") == "def add(a, b): return a + b\n"

    st = bridge.status(workspace=ws, receiver_home=receiver)
    assert st["state"] == "released"
    assert st["latest_artifact"] == accepted_sha
    assert st["destination_live"]["artifact_sha256"] == accepted_sha


def test_suite_drift_after_prepare_becomes_hold_not_pass(env):
    ws, receiver = env
    _prepare(ws, receiver, task="c5-drift")
    (ws / "solution.py").write_text("def add(a, b): return 0\n", encoding="utf-8")
    (ws / "tests_visible" / "test_visible.py").write_text(
        "def check_add():\n    pass\n", encoding="utf-8")
    res = bridge.judge(workspace=ws, sandbox="none", attempt=1,
                       receiver_home=receiver)
    assert res["outcome"] == "reject"
    assert res["results"][0]["status"] == "FAIL"


def test_conform_mode_requires_outer_attempt_accounting(env):
    ws, receiver = env
    out = _prepare(ws, receiver, task="c5-conform", mode="conform")
    c = C.load(ws / ".vacant" / "contract.json")
    assert out["attempts"] == 5
    assert c.hooks["stop_check"] is False
    assert c.hooks["submit_on_end"] is False
    assert c.max_attempts == 5
    (ws / "solution.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
    with pytest.raises(ValueError, match="requires --attempt"):
        bridge.judge(workspace=ws, sandbox="none", receiver_home=receiver)
    ok = bridge.judge(workspace=ws, sandbox="none", attempt=1,
                      receiver_home=receiver)
    assert ok["outcome"] == "accept"


def test_prepare_refuses_to_silently_replace_contract(env):
    ws, receiver = env
    _prepare(ws, receiver, task="c5-replace", mode="gate")
    with pytest.raises(ValueError, match="already exists"):
        _prepare(ws, receiver, task="c5-replace", mode="gate")


def test_tampered_workspace_contract_holds_before_acceptance(env):
    ws, receiver = env
    _prepare(ws, receiver, task="tamper")
    (ws / "solution.py").write_text("def add(a, b): return 0\n")
    cp = ws / ".vacant" / "contract.json"
    cp.write_text(cp.read_text().replace('"python_checks"', '"static"'))
    result = bridge.judge(workspace=ws, receiver_home=receiver, sandbox="none")
    assert result["outcome"] == "hold"
    assert result["artifact_sha256"] is None
    st = bridge.status(workspace=ws, receiver_home=receiver)
    assert st["attempts"] == 1
    assert st["workspace_contract_matches_receiver"] is False


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
    with pytest.raises(ValueError, match="same-account"):
        bridge.prepare(**kwargs, receiver_home=receiver)


def test_previous_run_cannot_be_released_after_rejected_new_run(env):
    ws, receiver = env
    _prepare(ws, receiver, task="reuse", mode="conform", attempts=2)
    (ws / "solution.py").write_text("def add(a, b): return a + b\n")
    good = bridge.judge(workspace=ws, receiver_home=receiver, sandbox="none", attempt=1)
    assert good["outcome"] == "accept"
    with pytest.raises(ValueError, match="already accepted"):
        bridge.judge(workspace=ws, receiver_home=receiver, sandbox="none", attempt=2)
    with pytest.raises(ValueError, match="already exists"):
        _prepare(ws, receiver, task="reuse")
    assert not bridge.release(workspace=ws, receiver_home=receiver,
                              artifact_sha256="0" * 64)["released"]
    assert bridge.release(workspace=ws, receiver_home=receiver,
                          artifact_sha256=good["artifact_sha256"])["released"]


def test_attempts_are_monotonic_and_bounded(env):
    ws, receiver = env
    _prepare(ws, receiver, task="attempts", mode="conform", attempts=2)
    (ws / "solution.py").write_text("def add(a, b): return 0\n")
    assert bridge.judge(workspace=ws, receiver_home=receiver, sandbox="none",
                        attempt=1)["outcome"] == "reject"
    with pytest.raises(ValueError, match="attempt must be 2"):
        bridge.judge(workspace=ws, receiver_home=receiver, sandbox="none", attempt=1)
    assert bridge.judge(workspace=ws, receiver_home=receiver, sandbox="none",
                        attempt=2)["outcome"] == "reject"
    with pytest.raises(ValueError, match="outside|attempt must be"):
        bridge.judge(workspace=ws, receiver_home=receiver, sandbox="none", attempt=3)
    assert bridge.status(workspace=ws, receiver_home=receiver)["attempts"] == 2


def test_nested_or_nonexecuting_suite_refused_before_agent_starts(env):
    ws, receiver = env
    nested = ws / "tests_visible" / "nested"
    nested.mkdir()
    (nested / "test_hidden.py").write_text("def check_bad(): assert False\n")
    with pytest.raises(ValueError, match="nested"):
        _prepare(ws, receiver)
    (nested / "test_hidden.py").unlink()
    (ws / "tests_visible" / "test_visible.py").write_text("def test_add(): assert False\n")
    with pytest.raises(ValueError, match=r"check_\* or main"):
        _prepare(ws, receiver)


def test_agent_editing_visible_copy_does_not_change_receiver_suite(env):
    ws, receiver = env
    _prepare(ws, receiver, task="immutable-suite")
    (ws / "tests_visible" / "test_visible.py").write_text("def check_add(): pass\n")
    (ws / "solution.py").write_text("def add(a, b): return 0\n")
    result = bridge.judge(workspace=ws, receiver_home=receiver, sandbox="none")
    assert result["outcome"] == "reject"
    assert result["results"][0]["status"] == "FAIL"
