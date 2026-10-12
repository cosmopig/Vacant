from __future__ import annotations

import importlib.util
import os
import pathlib

ROOT = pathlib.Path(os.environ["WT"])
SPEC = importlib.util.spec_from_file_location("nab", ROOT / "ops/eval/native_acceptance_bridge.py")
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


def test_nested_pinned_test_file_is_never_run(tmp_path):
    ws = tmp_path / "app"
    suite = ws / "tests_visible"
    (suite / "edge").mkdir(parents=True)
    (suite / "test_basic.py").write_text("def check_basic():\n    from solution import add\n    assert add(2, 3) == 5\n")
    # pinned (covered by the suite sha256) and counted by build_contract's rglob, but never executed
    (suite / "edge" / "test_edge.py").write_text("def check_edge():\n    from solution import add\n    assert add(-1, -1) == -2\n")
    rcv = tmp_path / "rcv"
    bridge.prepare(workspace=ws, task_id="t", suite=None, deliverable="solution.py", mode="gate",
                   attempts=None, feedback_rounds=3, suite_timeout_s=20,
                   destination="dir:.vacant/native-release", receiver_home=rcv)
    (ws / "solution.py").write_text("def add(a, b):\n    return 5 if (a, b) == (2, 3) else 0\n")
    j = bridge.judge(workspace=ws, sandbox="none", attempt=1, receiver_home=rcv)
    print(j["outcome"], j["results"][0]["detail"])
    assert j["outcome"] == "accept"
    assert bridge.release(workspace=ws, receiver_home=rcv)["released"] is True
