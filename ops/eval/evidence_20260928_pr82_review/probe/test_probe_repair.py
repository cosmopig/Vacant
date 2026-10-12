from __future__ import annotations

import importlib.util
import json
import os
import pathlib

from vacant_network.adapters import hook

ROOT = pathlib.Path(os.environ["WT"])
SPEC = importlib.util.spec_from_file_location("nab", ROOT / "ops/eval/native_acceptance_bridge.py")
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)

CHECK = "def check_add():\n    from solution import add\n    assert add(2, 3) == 5\n"


def _setup(tmp_path, monkeypatch, mode="repair", suite_text=CHECK):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "agent-home"))
    ws = tmp_path / "app"
    ws.mkdir()
    ext = tmp_path / "receiver-suite"
    ext.mkdir()
    (ext / "test_visible.py").write_text(suite_text)
    bridge.prepare(workspace=ws, task_id="t", suite=ext, deliverable="solution.py", mode=mode,
                   attempts=None, feedback_rounds=3, suite_timeout_s=20,
                   destination="dir:.vacant/native-release", receiver_home=tmp_path / "rcv")
    return ws


def test_repair_stop_hook_feeds_back(tmp_path, monkeypatch):
    ws = _setup(tmp_path, monkeypatch)
    (ws / "solution.py").write_text("def add(a, b): return 0\n")
    out, err, rc = hook.handle("pi", "stop", {"cwd": str(ws), "session_id": "s1"})
    print("REPAIR BAD:", rc, out[:600], err[:300])
    (ws / "solution.py").write_text("def add(a, b): return a + b\n")
    out, err, rc = hook.handle("pi", "stop", {"cwd": str(ws), "session_id": "s1"})
    print("REPAIR GOOD:", rc, out[:300], err[:300])


def test_repair_stop_hook_pytest_style(tmp_path, monkeypatch):
    ws = _setup(tmp_path, monkeypatch, suite_text="def test_add():\n    from solution import add\n    assert add(2,3)==5\n")
    (ws / "solution.py").write_text("def add(a, b): return a + b\n")
    for i in range(5):
        out, err, rc = hook.handle("pi", "stop", {"cwd": str(ws), "session_id": "s1"})
        print("PYTEST-STYLE round", i, rc, out[:300].replace("\n", " | "))


def test_gate_stop_hook(tmp_path, monkeypatch):
    ws = _setup(tmp_path, monkeypatch, mode="gate")
    (ws / "solution.py").write_text("def add(a, b): return 0\n")
    out, err, rc = hook.handle("pi", "stop", {"cwd": str(ws), "session_id": "s1"})
    print("GATE BAD:", rc, out[:300], err[:300])
    out, err, rc = hook.handle("pi", "session_end", {"cwd": str(ws), "session_id": "s1", "reason": "other"})
    print("GATE END:", rc, out[:300], err[:300])
