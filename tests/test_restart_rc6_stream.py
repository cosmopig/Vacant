"""rc6(2): Attempt output path + tail -f hint, and optional --stream flag."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import textwrap

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _make_proj(proj: pathlib.Path) -> None:
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (proj / "test_calc.py").write_text(
        textwrap.dedent("""\
            import unittest, calc
            class T(unittest.TestCase):
                def test_add(self):
                    self.assertEqual(calc.add(2, 3), 5)
        """),
        encoding="utf-8",
    )


def _write_chatty_agent(tmp_path: pathlib.Path) -> pathlib.Path:
    agent = tmp_path / "chatty_agent.py"
    agent.write_text(
        textwrap.dedent("""\
            import pathlib, sys
            print("AGENT_STDOUT_MARKER_LINE_1", flush=True)
            print("AGENT_STDERR_MARKER_LINE_2", file=sys.stderr, flush=True)
            pathlib.Path("calc.py").write_text("def add(a, b):\\n    return a + b\\n", encoding="utf-8")
        """),
        encoding="utf-8",
    )
    return agent


def _run_vacant_do(tmp_path: pathlib.Path, extra: list[str]) -> tuple[subprocess.CompletedProcess, pathlib.Path]:
    proj = tmp_path / "proj"
    _make_proj(proj)
    vh = tmp_path / "vhome"
    vw = tmp_path / "vwork"
    agent = _write_chatty_agent(tmp_path)
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
        "--prompt", "fix calc",
        "--attempt-timeout", "30",
        "--timeout", "60",
        *extra,
    ]
    cp = subprocess.run(cmd, cwd=proj, env=env, capture_output=True, text=True, timeout=120)
    run_dirs = sorted(vw.glob("restart-*"))
    assert len(run_dirs) == 1
    return cp, run_dirs[0]


def test_rc6_default_prints_tail_hint_and_does_not_stream(tmp_path):
    """Default behavior: prints agent_stdout.log path + tail -f hint; does NOT stream agent output."""
    cp, run_dir = _run_vacant_do(tmp_path, [])
    assert cp.returncode == 0, cp.stdout + cp.stderr
    log_path = run_dir / "attempt_1" / "logs" / "agent_stdout.log"
    err_path = run_dir / "attempt_1" / "logs" / "agent_stderr.log"
    assert str(log_path) in cp.stdout
    assert "tail -f" in cp.stdout
    # Default must NOT stream agent stdout/stderr to terminal
    assert "AGENT_STDOUT_MARKER_LINE_1" not in cp.stdout
    assert "AGENT_STDERR_MARKER_LINE_2" not in cp.stderr
    # Log files still have the full agent output
    assert "AGENT_STDOUT_MARKER_LINE_1" in log_path.read_text(encoding="utf-8")
    assert "AGENT_STDERR_MARKER_LINE_2" in err_path.read_text(encoding="utf-8")


def test_rc6_stream_flag_streams_agent_output_and_keeps_logs(tmp_path):
    """--stream streams agent stdout and stderr directly to terminal AND saves both log files."""
    cp, run_dir = _run_vacant_do(tmp_path, ["--stream"])
    assert cp.returncode == 0, cp.stdout + cp.stderr
    log_path = run_dir / "attempt_1" / "logs" / "agent_stdout.log"
    err_path = run_dir / "attempt_1" / "logs" / "agent_stderr.log"
    assert str(log_path) in cp.stdout
    assert "AGENT_STDOUT_MARKER_LINE_1" in cp.stdout
    assert "AGENT_STDERR_MARKER_LINE_2" in cp.stderr
    assert "AGENT_STDOUT_MARKER_LINE_1" in log_path.read_text(encoding="utf-8")
    assert "AGENT_STDERR_MARKER_LINE_2" in err_path.read_text(encoding="utf-8")
    rj = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    assert rj["accepted"] is True
