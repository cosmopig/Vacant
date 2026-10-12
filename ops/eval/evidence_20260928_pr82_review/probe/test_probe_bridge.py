from __future__ import annotations

import importlib.util
import json
import os
import pathlib

import pytest

from vacant_network.intake import contract as C
from vacant_network.intake import flow

ROOT = pathlib.Path(os.environ["WT"])
PATH = ROOT / "ops" / "eval" / "native_acceptance_bridge.py"
SPEC = importlib.util.spec_from_file_location("native_acceptance_bridge", PATH)
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)

GOOD = "def add(a, b): return a + b\n"
BAD = "def add(a, b): return 0\n"
CHECK = "def check_add():\n    from solution import add\n    assert add(2, 3) == 5\n"


def mk_ws(base: pathlib.Path, name="app", suite_text=CHECK, suite_name="test_visible.py"):
    ws = base / name
    (ws / "tests_visible").mkdir(parents=True)
    (ws / "tests_visible" / suite_name).write_text(suite_text, encoding="utf-8")
    return ws


def prep(ws, receiver, *, task="t", mode="gate", suite=None, attempts=None):
    return bridge.prepare(workspace=ws, task_id=task, suite=suite, deliverable="solution.py",
                          mode=mode, attempts=attempts, feedback_rounds=3, suite_timeout_s=20,
                          destination="dir:.vacant/native-release", receiver_home=receiver)


# 1. pytest-style suite passes prepare validation, but a CORRECT candidate is rejected (FAIL)
def test_pytest_style_suite_rejects_correct_candidate(tmp_path):
    ws = mk_ws(tmp_path, suite_text="def test_add():\n    from solution import add\n    assert add(2, 3) == 5\n")
    rcv = tmp_path / "rcv"
    prep(ws, rcv)                       # accepted by build_contract
    (ws / "solution.py").write_text(GOOD)
    out = bridge.judge(workspace=ws, sandbox="none", attempt=1, receiver_home=rcv)
    print(json.dumps(out["results"], indent=1)[:800])
    assert out["outcome"] == "reject"   # a correct solution is REJECTED, not held
    assert out["results"][0]["status"] == "FAIL"


# 2. nested-only suite passes prepare validation but every judge is HOLD
def test_nested_suite_prepares_but_never_runs(tmp_path):
    ws = tmp_path / "app"
    (ws / "tests_visible" / "unit").mkdir(parents=True)
    (ws / "tests_visible" / "unit" / "test_visible.py").write_text(CHECK)
    rcv = tmp_path / "rcv"
    prep(ws, rcv)
    (ws / "solution.py").write_text(GOOD)
    out = bridge.judge(workspace=ws, sandbox="none", attempt=1, receiver_home=rcv)
    print(out["results"][0]["detail"])
    assert out["outcome"] == "hold"


# 3. a receiver-home reused across runs releases an earlier run's accepted artifact
def test_stale_accept_from_previous_run_is_released(tmp_path):
    rcv = tmp_path / "rcv"
    suite = tmp_path / "receiver-suite"
    suite.mkdir()
    (suite / "test_visible.py").write_text(CHECK)
    # run 1 (seed 1): good candidate, accepted and released
    ws1 = mk_ws(tmp_path / "run1")
    prep(ws1, rcv, suite=suite)
    (ws1 / "solution.py").write_text(GOOD)
    r1 = bridge.judge(workspace=ws1, sandbox="none", attempt=1, receiver_home=rcv)
    assert r1["outcome"] == "accept"
    assert bridge.release(workspace=ws1, receiver_home=rcv)["released"]
    # run 2 (seed 2): fresh /app, same task id + same receiver home; the candidate is BAD
    ws2 = mk_ws(tmp_path / "run2")
    p2 = prep(ws2, rcv, suite=suite)
    (ws2 / "solution.py").write_text(BAD)
    r2 = bridge.judge(workspace=ws2, sandbox="none", attempt=1, receiver_home=rcv)
    assert r2["outcome"] == "reject"
    rel = bridge.release(workspace=ws2, receiver_home=rcv)
    print(json.dumps(rel, indent=1, default=str)[:600])
    assert rel["released"] is True          # released although this run's judge rejected
    assert rel["artifact_sha256"] == r1["artifact_sha256"]
    pub = ws2 / ".vacant" / "native-release" / "t" / "solution.py"
    assert pub.read_text() == GOOD          # run 1's code shows up as run 2's delivery
    assert (ws2 / "solution.py").read_text() == BAD


# 4. attempts are never enforced or counted
def test_attempts_not_enforced(tmp_path):
    ws = mk_ws(tmp_path)
    rcv = tmp_path / "rcv"
    prep(ws, rcv, mode="gate")            # gate: max 1 attempt, "FAIL => reject"
    (ws / "solution.py").write_text(BAD)
    assert bridge.judge(workspace=ws, sandbox="none", attempt=1, receiver_home=rcv)["outcome"] == "reject"
    (ws / "solution.py").write_text(GOOD)
    assert bridge.judge(workspace=ws, sandbox="none", attempt=1, receiver_home=rcv)["outcome"] == "accept"
    assert bridge.release(workspace=ws, receiver_home=rcv)["released"] is True
    st = bridge.status(workspace=ws, receiver_home=rcv)
    print({k: st[k] for k in ("attempts", "decisions", "state")})
    assert st["attempts"] == 0 and st["decisions"] == 2


def test_conform_attempts_unbounded(tmp_path):
    ws = mk_ws(tmp_path)
    rcv = tmp_path / "rcv"
    prep(ws, rcv, mode="conform", attempts=2)
    (ws / "solution.py").write_text(BAD)
    for _ in range(4):
        assert bridge.judge(workspace=ws, sandbox="none", attempt=2, receiver_home=rcv)["outcome"] == "reject"
    (ws / "solution.py").write_text(GOOD)
    assert bridge.judge(workspace=ws, sandbox="none", attempt=1, receiver_home=rcv)["outcome"] == "accept"
    st = bridge.status(workspace=ws, receiver_home=rcv)
    print({k: st[k] for k in ("attempts", "decisions", "state")})
    assert st["decisions"] == 5


# 5. judge trusts whatever contract sits in the (agent-writable) workspace
def test_judge_accepts_under_tampered_contract(tmp_path):
    ws = mk_ws(tmp_path)
    rcv = tmp_path / "rcv"
    ext = tmp_path / "receiver-suite"
    ext.mkdir()
    (ext / "test_visible.py").write_text(CHECK)
    prep(ws, rcv, suite=ext)
    # the agent (shell, not a write tool) swaps the suite for its own trivial one
    (ws / "mysuite").mkdir()
    (ws / "mysuite" / "test_x.py").write_text("def check_ok():\n    pass\n")
    cp = ws / ".vacant" / "contract.json"
    raw = json.loads(cp.read_text())
    raw["inputs"]["visible_suite"] = {"path": "mysuite", "sha256": C.path_sha256(ws / "mysuite")}
    cp.write_text(json.dumps(raw))
    (ws / "solution.py").write_text(BAD)
    out = bridge.judge(workspace=ws, sandbox="none", attempt=1, receiver_home=rcv)
    print(out["outcome"], out.get("contract_sha256"))
    assert out["outcome"] == "accept"      # judge exit code 0 for a candidate that fails the pinned suite
    rel = bridge.release(workspace=ws, receiver_home=rcv)
    print(rel["reasons"])
    assert rel["released"] is False


def test_tampered_contract_released_when_receiver_home_omitted(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "shared-home"))
    ws = mk_ws(tmp_path)
    prep(ws, None)
    (ws / "tests_visible" / "test_visible.py").write_text("def check_ok():\n    pass\n")
    cp = ws / ".vacant" / "contract.json"
    raw = json.loads(cp.read_text())
    del raw["inputs"]["visible_suite"]["sha256"]
    cp.write_text(json.dumps(raw))
    flow.lock(cp)          # what `vacant contract lock` from the agent shell does
    (ws / "solution.py").write_text(BAD)
    out = bridge.judge(workspace=ws, sandbox="none", attempt=1, receiver_home=None)
    assert out["outcome"] == "accept"
    rel = bridge.release(workspace=ws, receiver_home=None)
    assert rel["released"] is True
