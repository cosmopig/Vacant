from __future__ import annotations

import importlib.util
import os
import pathlib

from vacant_network.adapters import hook
from vacant_network.intake import verifiers as V

ROOT = pathlib.Path(os.environ["WT"])
SPEC = importlib.util.spec_from_file_location("nab", ROOT / "ops/eval/native_acceptance_bridge.py")
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)
CHECK = "def check_add():\n    from solution import add\n    assert add(2, 3) == 5\n"


def test_repair_feedback_silently_off_when_receiver_suite_unreadable(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "agent-home"))
    ws = tmp_path / "app"; ws.mkdir()
    ext = tmp_path / "srv-receiver-suite"; ext.mkdir()
    (ext / "test_visible.py").write_text(CHECK)
    bridge.prepare(workspace=ws, task_id="t", suite=ext, deliverable="solution.py", mode="repair",
                   attempts=None, feedback_rounds=3, suite_timeout_s=20,
                   destination="dir:.vacant/native-release", receiver_home=tmp_path / "rcv")
    (ws / "solution.py").write_text("def add(a, b): return 0\n")
    real = V.path_sha256
    def as_agent(p):   # the agent account cannot read the receiver-owned copy (README §8 layout)
        if str(p).startswith(str(ext)):
            raise PermissionError(13, "Permission denied", str(p))
        return real(p)
    monkeypatch.setattr(V, "path_sha256", as_agent)
    out, err, rc = hook.handle("pi", "stop", {"cwd": str(ws), "session_id": "s1"})
    print(out)
    assert '"allow"' in out    # wrong candidate, no feedback: repair arm degenerates to gate
