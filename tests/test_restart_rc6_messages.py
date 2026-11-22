"""rc6(3)-(6): Improved human-facing messages and output formatting in `vacant do` restart mode."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import textwrap

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _run_cli(proj: pathlib.Path, agent_code: str, tmp_path: pathlib.Path, extra: list[str] | None = None):
    vh = tmp_path / "vhome"
    vw = tmp_path / "vwork"
    agent = tmp_path / "agent.py"
    agent.write_text(agent_code, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env.update(
        PYTHONPATH=str(REPO_ROOT),
        VACANT_HOME=str(vh),
        VACANT_WORK=str(vw),
        VACANT_HOOK_NO_GC="1",
    )
    cmd = [
        sys.executable, "-m", "vacant_network.cli", "do",
        "--cmd", f"{sys.executable} {agent} {{prompt}}",
        "--prompt", "fix tests",
        "--attempt-timeout", "30",
        "--timeout", "120",
        *(extra or []),
    ]
    cp = subprocess.run(cmd, cwd=proj, env=env, capture_output=True, text=True, timeout=180)
    rjs = sorted(vw.glob("restart-*/result.json"))
    rj = json.loads(rjs[-1].read_text(encoding="utf-8")) if rjs else {}
    return cp, rj, vh, vw


def test_rc6_3_failure_message_details(tmp_path):
    """rc6(3): Rejected run message explains passed/total, per-attempt progress,
    first failing test + reason, that delivered attempt was written to project, and exit code 40."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "calc.py").write_text(
        "def add(a, b): return 0\ndef sub(a, b): return 0\ndef mul(a, b): return 0\n",
        encoding="utf-8",
    )
    (proj / "test_calc.py").write_text(
        textwrap.dedent("""\
            import unittest, calc
            class T(unittest.TestCase):
                def test_add(self): self.assertEqual(calc.add(2, 3), 5)
                def test_sub(self): self.assertEqual(calc.sub(5, 3), 2)
                def test_mul(self): self.assertEqual(calc.mul(2, 3), 6)
        """),
        encoding="utf-8",
    )
    state = tmp_path / "state.txt"
    agent_code = textwrap.dedent(f"""\
        import pathlib
        st = pathlib.Path({str(state)!r})
        n = int(st.read_text()) + 1 if st.exists() else 1
        st.write_text(str(n))
        if n == 1:
            pathlib.Path("calc.py").write_text(
                "def add(a, b): return a + b\\ndef sub(a, b): return 0\\ndef mul(a, b): return 0\\n"
            )
        elif n == 2:
            pathlib.Path("calc.py").write_text(
                "def add(a, b): return a + b\\ndef sub(a, b): return a - b\\ndef mul(a, b): return 999\\n"
            )
        else:
            pathlib.Path("calc.py").write_text(
                "def add(a, b): return a + b\\ndef sub(a, b): return 0\\ndef mul(a, b): return 0\\n"
            )
    """)
    cp, rj, _, _ = _run_cli(proj, agent_code, tmp_path)
    out = cp.stdout
    assert cp.returncode == 40, out + cp.stderr
    assert rj["delivered_attempt"] == 2
    assert "passed/total" in out
    assert "written to your project" in out
    assert "attempts (passed/total):" in out
    assert "#1 1/3 FAIL" in out
    assert "#2 2/3 FAIL [delivered]" in out
    assert "#3 1/3 FAIL" in out
    assert "first failing test:" in out
    assert "test_mul" in out
    assert "AssertionError" in out
    assert "exit code 40:" in out
