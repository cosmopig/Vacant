from __future__ import annotations

import importlib.util
import json
import os
import pathlib

ROOT = pathlib.Path(os.environ["WT"])
SPEC = importlib.util.spec_from_file_location("nab", ROOT / "ops/eval/native_acceptance_bridge.py")
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)

CHECK = "def check_add():\n    from solution import add\n    assert add(2, 3) == 5\n"
GOOD = "def add(a, b): return a + b\n"


def mk(tmp_path, mode="gate"):
    ws = tmp_path / "app"
    (ws / "tests_visible").mkdir(parents=True)
    (ws / "tests_visible" / "test_visible.py").write_text(CHECK)
    rcv = tmp_path / "rcv"
    bridge.prepare(workspace=ws, task_id="t", suite=None, deliverable="solution.py", mode=mode,
                   attempts=None, feedback_rounds=3, suite_timeout_s=20,
                   destination="dir:.vacant/native-release", receiver_home=rcv)
    return ws, rcv


def test_edit_after_judge_does_not_change_release(tmp_path):
    ws, rcv = mk(tmp_path)
    (ws / "solution.py").write_text(GOOD)
    j = bridge.judge(workspace=ws, sandbox="none", attempt=1, receiver_home=rcv)
    (ws / "solution.py").write_text("def add(a, b): return 0\n")
    r = bridge.release(workspace=ws, receiver_home=rcv)
    assert r["released"] and r["artifact_sha256"] == j["artifact_sha256"]
    assert (ws / ".vacant/native-release/t/solution.py").read_text() == GOOD


def test_benign_agent_test_added_to_default_suite_is_hold(tmp_path):
    ws, rcv = mk(tmp_path)
    (ws / "solution.py").write_text(GOOD)
    # the agent writes its own extra test next to the visible ones (shell, not a write tool)
    (ws / "tests_visible" / "test_mine.py").write_text("def check_more():\n    from solution import add\n    assert add(0,0)==0\n")
    j = bridge.judge(workspace=ws, sandbox="none", attempt=1, receiver_home=rcv)
    print(j["outcome"], j["results"][0]["detail"])
    assert j["outcome"] == "hold"
    r = bridge.release(workspace=ws, receiver_home=rcv)
    assert r["released"] is False


def test_post_judge_contract_touch_blocks_release(tmp_path):
    ws, rcv = mk(tmp_path)
    (ws / "solution.py").write_text(GOOD)
    j = bridge.judge(workspace=ws, sandbox="none", attempt=1, receiver_home=rcv)
    assert j["outcome"] == "accept"
    cp = ws / ".vacant" / "contract.json"
    raw = json.loads(cp.read_text()); raw["objective"] += " "
    cp.write_text(json.dumps(raw))
    r = bridge.release(workspace=ws, receiver_home=rcv)
    print(r)
    assert r["released"] is False
