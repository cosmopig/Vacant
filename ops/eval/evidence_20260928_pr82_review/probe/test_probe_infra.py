from __future__ import annotations

import importlib.util
import os
import pathlib

from vacant_network.vrun import sandbox as S

ROOT = pathlib.Path(os.environ["WT"])
SPEC = importlib.util.spec_from_file_location("nab", ROOT / "ops/eval/native_acceptance_bridge.py")
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)

CHECK = "def check_add():\n    from solution import add\n    assert add(2, 3) == 5\n"


def test_python3_missing_in_verifier_env_is_reject_not_hold(tmp_path, monkeypatch):
    ws = tmp_path / "app"
    (ws / "tests_visible").mkdir(parents=True)
    (ws / "tests_visible" / "test_visible.py").write_text(CHECK)
    rcv = tmp_path / "rcv"
    bridge.prepare(workspace=ws, task_id="t", suite=None, deliverable="solution.py", mode="gate",
                   attempts=None, feedback_rounds=3, suite_timeout_s=20,
                   destination="dir:.vacant/native-release", receiver_home=rcv)
    (ws / "solution.py").write_text("def add(a, b): return a + b\n")
    orig = S._clean_env
    empty = tmp_path / "emptybin"; empty.mkdir()
    # simulate an interpreter that is missing inside the verifier environment:
    # bash starts (so no OSError / SandboxInfraError) but `python3` is not found (rc=127)
    monkeypatch.setattr(S, "_clean_env", lambda *a, **k: {**orig(*a, **k), "PATH": f"{empty}:/bin:/usr/bin".replace("/usr/bin", str(empty)).replace(":/bin", ":" + str(empty))})
    import shutil
    (empty / "bash").symlink_to(shutil.which("bash"))
    (empty / "mktemp").symlink_to(shutil.which("mktemp"))
    (empty / "rm").symlink_to(shutil.which("rm"))
    out = bridge.judge(workspace=ws, sandbox="none", attempt=1, receiver_home=rcv)
    print(out["outcome"], out["results"][0]["status"], out["results"][0]["detail"][:300])
    assert out["outcome"] == "reject"
