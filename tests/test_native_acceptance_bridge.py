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
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vacant-home"))
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
    return ws


def test_repair_contract_uses_pinned_executable_acceptance(workspace):
    out = bridge.prepare(workspace=workspace, task_id="c5-test", suite=None,
                         deliverable="solution.py", mode="repair", attempts=None,
                         feedback_rounds=3, suite_timeout_s=20,
                         destination="dir:.vacant/native-release")
    c = C.load(workspace / ".vacant" / "contract.json")
    assert out["prepared"] is True
    assert out["suite_sha256"] == c.input_pin("visible_suite")
    assert c.claims[0].verifier == "python_checks"
    assert c.claims[0].params["suite"] == "input:visible_suite"
    assert c.hooks["stop_check"] is True
    assert c.hooks["submit_on_end"] is False
    assert c.max_attempts == 1


def test_pinned_suite_is_protected_from_normal_native_write_tools(workspace):
    bridge.prepare(workspace=workspace, task_id="c5-protect", suite=None,
                   deliverable="solution.py", mode="repair", attempts=None,
                   feedback_rounds=3, suite_timeout_s=20,
                   destination="dir:.vacant/native-release")
    c = C.load(workspace / ".vacant" / "contract.json")
    ev = HookEvent(agent="pi", kind="pre_tool", tool="write",
                   paths=["tests_visible/test_visible.py"], cwd=str(workspace))
    d = decide_pre_tool(ev, c)
    assert d.action == "deny"
    assert d.record["rule"] == "protect_write"


def test_bridge_rejects_bad_candidate_accepts_good_and_releases_same_flow(workspace):
    bridge.prepare(workspace=workspace, task_id="c5-flow", suite=None,
                   deliverable="solution.py", mode="repair", attempts=None,
                   feedback_rounds=3, suite_timeout_s=20,
                   destination="dir:.vacant/native-release")
    (workspace / "solution.py").write_text("def add(a, b): return 0\n", encoding="utf-8")
    bad = bridge.judge(workspace=workspace, sandbox="none", attempt=1)
    assert bad["outcome"] == "reject"

    (workspace / "solution.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
    good = bridge.judge(workspace=workspace, sandbox="none", attempt=1)
    assert good["outcome"] == "accept"
    accepted_sha = good["artifact_sha256"]

    rel = bridge.release(workspace=workspace)
    assert rel["released"] is True
    published = workspace / ".vacant" / "native-release" / "c5-flow" / "solution.py"
    assert published.read_text(encoding="utf-8") == "def add(a, b): return a + b\n"

    st = bridge.status(workspace=workspace)
    assert st["state"] == "released"
    assert st["latest_artifact_sha256"] == accepted_sha


def test_suite_drift_after_prepare_becomes_hold_not_pass(workspace):
    bridge.prepare(workspace=workspace, task_id="c5-drift", suite=None,
                   deliverable="solution.py", mode="repair", attempts=None,
                   feedback_rounds=3, suite_timeout_s=20,
                   destination="dir:.vacant/native-release")
    (workspace / "solution.py").write_text("def add(a, b): return 0\n", encoding="utf-8")
    (workspace / "tests_visible" / "test_visible.py").write_text(
        "def check_add():\n    pass\n", encoding="utf-8")
    res = bridge.judge(workspace=workspace, sandbox="none", attempt=1)
    assert res["outcome"] == "hold"
    assert res["results"][0]["status"] == "UNKNOWN"
    assert "changed since it was pinned" in res["results"][0]["detail"]


def test_conform_mode_defers_feedback_to_outer_fresh_session_harness(workspace):
    out = bridge.prepare(workspace=workspace, task_id="c5-conform", suite=None,
                         deliverable="solution.py", mode="conform", attempts=None,
                         feedback_rounds=3, suite_timeout_s=20,
                         destination="dir:.vacant/native-release")
    c = C.load(workspace / ".vacant" / "contract.json")
    assert out["attempts"] == 5
    assert c.hooks["stop_check"] is False
    assert c.hooks["submit_on_end"] is False
    assert c.max_attempts == 5


def test_prepare_refuses_to_silently_replace_contract(workspace):
    kwargs = dict(workspace=workspace, task_id="c5-replace", suite=None,
                  deliverable="solution.py", mode="gate", attempts=None,
                  feedback_rounds=0, suite_timeout_s=20,
                  destination="dir:.vacant/native-release")
    bridge.prepare(**kwargs)
    with pytest.raises(ValueError, match="already exists"):
        bridge.prepare(**kwargs)
