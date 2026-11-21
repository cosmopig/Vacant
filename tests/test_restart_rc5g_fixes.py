"""Regression tests for rc5g narrow-unfreeze fixes:
- N1: python_unittest import resolution matches `python3 -m unittest` at project root
  across (a) tests/ package, (b) non-package tests/ dir (no extra paths invented),
  (c) flat root layout (unchanged), (d) src/ layout (fails without PYTHONPATH),
  and verifier scenario v3 (tests/ package + root calendar.py stdlib clash).
- N2: dynamic-import scan applies to depth-1 and depth-2 imported helpers (excluding
  sole direct non-test MUT) including getattr(importlib, ...), marking verdict untraced
  with reason dynamic-import:<file>.
- P5 message: unreadable project paths do not print `acceptance: none`.
"""
from __future__ import annotations

import json
import pathlib
import sys
import textwrap

import pytest

from vacant_network.adapters import cli as adapters_cli
from vacant_network.adapters import restart as R


def _write_agent(tmp_path: pathlib.Path, body: str, name: str = "agent.py") -> pathlib.Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def _run_cli_do(
    monkeypatch: pytest.MonkeyPatch,
    proj: pathlib.Path,
    agent_py: pathlib.Path,
    *,
    prompt: str = "fix",
    attempts: int = 3,
    extra_args: list[str] | None = None,
    vhome: pathlib.Path | None = None,
    vwork: pathlib.Path | None = None,
) -> int:
    vh = vhome or (proj.parent / "vhome")
    vw = vwork or (proj.parent / "vwork")
    monkeypatch.setenv("VACANT_HOME", str(vh))
    monkeypatch.setenv("VACANT_WORK", str(vw))
    monkeypatch.setenv("VACANT_HOOK_NO_GC", "1")
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.chdir(proj)
    argv = [
        "do",
        "--cmd", f"{sys.executable} {agent_py} {{prompt}}",
        "--prompt", prompt,
        "--attempts", str(attempts),
        "--attempt-timeout", "30",
        "--timeout", "120",
        *(extra_args or []),
    ]
    return adapters_cli.main(argv)


def _latest_result_json(vwork: pathlib.Path) -> dict:
    rjs = sorted(vwork.glob("restart-*/result.json"))
    assert rjs, f"no result.json under {vwork}"
    return json.loads(rjs[-1].read_text(encoding="utf-8"))


# ============================================================================
# N1: python_unittest import resolution matches `python3 -m unittest` at root
# ============================================================================

def test_n1a_tests_package_fix_and_break(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """N1(a): root mycal.py + tests/__init__.py + tests/test_mycal.py (`import mycal`,
    plus relative import `from . import helper`): fix -> PASS, break -> FAIL."""
    for mode in ("fix", "break"):
        base = tmp_path / mode
        proj = base / "proj"
        (proj / "tests").mkdir(parents=True)
        (proj / "mycal.py").write_text("def days_in_feb(y):\n    return 28\n", encoding="utf-8")
        (proj / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (proj / "tests" / "helper.py").write_text("LEAP_YEAR = 2024\n", encoding="utf-8")
        (proj / "tests" / "test_mycal.py").write_text(
            "import unittest\n"
            "import mycal\n"
            "from . import helper\n"
            "class T(unittest.TestCase):\n"
            "    def test_leap(self):\n"
            "        self.assertEqual(mycal.days_in_feb(helper.LEAP_YEAR), 29)\n"
            "        self.assertEqual(mycal.days_in_feb(2023), 28)\n",
            encoding="utf-8",
        )
        if mode == "fix":
            body = (
                "import pathlib\n"
                "pathlib.Path('mycal.py').write_text("
                "'def days_in_feb(y):\\n"
                "    return 29 if (y % 4 == 0 and y % 100 != 0) or y % 400 == 0 else 28\\n')\n"
            )
        else:
            body = "import pathlib\npathlib.Path('mycal.py').write_text('def days_in_feb(y):\\n    return 30\\n')\n"
        agent = _write_agent(base, body)
        rc = _run_cli_do(monkeypatch, proj, agent, attempts=2)
        out = capsys.readouterr().out
        rj = _latest_result_json(base / "vwork")

        assert rj["acceptance"]["kind"] == "python_unittest"
        assert rj["baseline"]["status"] == "ok"
        assert rj["baseline"]["accept"] is False
        assert rj["baseline"]["run"] == 1
        assert rj["acceptance_integrity"] == "traced"
        if mode == "fix":
            assert rc == 0, out
            assert rj["accepted"] is True
            assert rj["delivered_attempt"] == 1
            assert "NOTE:" not in out
        else:
            assert rc == adapters_cli.EXIT["reject"], out
            assert rj["accepted"] is False
            assert all(a["status"] == "ok" and a["accept"] is False for a in rj["attempts"])


def test_n1a_tests_package_keeps_rc5e_new_shadow_excluded(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """N1 + rc5e: inside a tests/ package layout, a new root file shadowing stdlib
    (e.g. statistics.py absent at start) is still excluded and not written back."""
    proj = tmp_path / "proj"
    (proj / "tests").mkdir(parents=True)
    (proj / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (proj / "tests" / "test_s.py").write_text(
        "import unittest\n"
        "from statistics import median\n"
        "class T(unittest.TestCase):\n"
        "    def test_m(self):\n"
        "        self.assertEqual(median([1, 2, 3]), 99)\n",
        encoding="utf-8",
    )
    agent = _write_agent(
        tmp_path,
        "import pathlib\npathlib.Path('statistics.py').write_text('def median(xs): return 99\\n')\n",
    )
    rc = _run_cli_do(monkeypatch, proj, agent, attempts=1)
    out = capsys.readouterr().out
    rj = _latest_result_json(tmp_path / "vwork")

    assert rc == adapters_cli.EXIT["reject"], out
    assert rj["accepted"] is False
    assert not (proj / "statistics.py").exists()
    assert "statistics.py" in rj["attempts"][0]["config_ignored"]


def test_n1b_non_package_tests_dir_root_import_and_no_extra_paths(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """N1(b): tests/ without __init__.py resolves root modules (sys.path[0] == project root)
    so fix -> PASS and break -> FAIL, and does NOT invent tests/ on sys.path."""
    for mode in ("fix", "break"):
        base = tmp_path / mode
        proj = base / "proj"
        (proj / "tests").mkdir(parents=True)
        (proj / "mycal.py").write_text("def days_in_feb(y):\n    return 28\n", encoding="utf-8")
        (proj / "tests" / "test_mycal.py").write_text(
            "import unittest\n"
            "import mycal\n"
            "class T(unittest.TestCase):\n"
            "    def test_leap(self):\n"
            "        self.assertEqual(mycal.days_in_feb(2024), 29)\n",
            encoding="utf-8",
        )
        if mode == "fix":
            body = "import pathlib\npathlib.Path('mycal.py').write_text('def days_in_feb(y):\\n    return 29\\n')\n"
        else:
            body = "import pathlib\npathlib.Path('mycal.py').write_text('def days_in_feb(y):\\n    return 30\\n')\n"
        agent = _write_agent(base, body)
        rc = _run_cli_do(monkeypatch, proj, agent, attempts=1)
        out = capsys.readouterr().out
        rj = _latest_result_json(base / "vwork")

        assert rj["acceptance"]["kind"] == "python_unittest"
        assert rj["baseline"]["status"] == "ok"
        assert rj["baseline"]["accept"] is False
        if mode == "fix":
            assert rc == 0, out
            assert rj["accepted"] is True
        else:
            assert rc == adapters_cli.EXIT["reject"], out
            assert rj["accepted"] is False

    # No extra paths invented: bare `import sibling` from non-package tests/ must NOT resolve
    base_sib = tmp_path / "no_extra_path"
    proj_sib = base_sib / "proj"
    (proj_sib / "tests").mkdir(parents=True)
    (proj_sib / "tests" / "sibling.py").write_text("VAL = 1\n", encoding="utf-8")
    (proj_sib / "tests" / "test_sib.py").write_text(
        "import unittest\n"
        "import sibling\n"
        "class T(unittest.TestCase):\n"
        "    def test_v(self):\n"
        "        self.assertEqual(sibling.VAL, 1)\n",
        encoding="utf-8",
    )
    agent_noop = _write_agent(base_sib, "pass\n")
    rc_sib = _run_cli_do(monkeypatch, proj_sib, agent_noop, attempts=1)
    capsys.readouterr()
    rj_sib = _latest_result_json(base_sib / "vwork")
    assert rc_sib == adapters_cli.EXIT["reject"]
    assert rj_sib["accepted"] is False
    assert rj_sib["attempts"][0]["status"] == "load_error"
    assert "No module named 'sibling'" in (rj_sib["attempts"][0]["first_problem"] or "")


def test_n1c_flat_project_unchanged_fix_and_break(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """N1(c): flat project (test files at root) remains unchanged: fix -> PASS, break -> FAIL."""
    for mode in ("fix", "break"):
        base = tmp_path / mode
        proj = base / "proj"
        proj.mkdir(parents=True)
        (proj / "mycal.py").write_text("def days_in_feb(y):\n    return 28\n", encoding="utf-8")
        (proj / "test_mycal.py").write_text(
            "import unittest\n"
            "import mycal\n"
            "class T(unittest.TestCase):\n"
            "    def test_leap(self):\n"
            "        self.assertEqual(mycal.days_in_feb(2024), 29)\n",
            encoding="utf-8",
        )
        if mode == "fix":
            body = "import pathlib\npathlib.Path('mycal.py').write_text('def days_in_feb(y):\\n    return 29\\n')\n"
        else:
            body = "import pathlib\npathlib.Path('mycal.py').write_text('def days_in_feb(y):\\n    return 30\\n')\n"
        agent = _write_agent(base, body)
        rc = _run_cli_do(monkeypatch, proj, agent, attempts=1)
        out = capsys.readouterr().out
        rj = _latest_result_json(base / "vwork")

        assert rj["acceptance"]["kind"] == "python_unittest"
        assert rj["baseline"]["status"] == "ok"
        assert rj["baseline"]["accept"] is False
        if mode == "fix":
            assert rc == 0, out
            assert rj["accepted"] is True
        else:
            assert rc == adapters_cli.EXIT["reject"], out
            assert rj["accepted"] is False


def test_n1d_src_layout_fails_without_pythonpath(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """N1(d): src/ layout (`src/pkg` + `tests/`) must fail with ModuleNotFoundError when
    PYTHONPATH is not set, even when the agent writes a correct fix (do NOT add src/ to sys.path)."""
    proj = tmp_path / "proj"
    (proj / "src" / "pkg").mkdir(parents=True)
    (proj / "tests").mkdir(parents=True)
    (proj / "src" / "pkg" / "__init__.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (proj / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (proj / "tests" / "test_pkg.py").write_text(
        "import unittest\n"
        "from pkg import add\n"
        "class T(unittest.TestCase):\n"
        "    def test_add(self):\n"
        "        self.assertEqual(add(2, 3), 5)\n",
        encoding="utf-8",
    )
    agent = _write_agent(
        tmp_path,
        "import pathlib\npathlib.Path('src/pkg/__init__.py').write_text('def add(a, b):\\n    return a + b\\n')\n",
    )
    monkeypatch.delenv("PYTHONPATH", raising=False)
    rc = _run_cli_do(monkeypatch, proj, agent, attempts=1)
    out = capsys.readouterr().out
    rj = _latest_result_json(tmp_path / "vwork")

    assert rc == adapters_cli.EXIT["reject"], out
    assert rj["acceptance"]["kind"] == "python_unittest"
    assert rj["accepted"] is False
    assert rj["attempts"][0]["status"] == "load_error"
    assert "No module named 'pkg'" in (rj["attempts"][0]["first_problem"] or "")


def test_n1_v3_tests_package_with_root_calendar_stdlib_clash(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """Verifier scenario v3: tests/ package + root calendar.py (stdlib name clash).
    Fix -> PASS (exit 0), break -> FAIL (exit 40)."""
    for mode in ("fix", "break"):
        base = tmp_path / mode
        proj = base / "proj"
        (proj / "tests").mkdir(parents=True)
        (proj / "calendar.py").write_text("def days_in_feb(y):\n    return 28\n", encoding="utf-8")
        (proj / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (proj / "tests" / "test_cal.py").write_text(
            "import unittest\n"
            "from calendar import days_in_feb\n"
            "class T(unittest.TestCase):\n"
            "    def test_leap(self):\n"
            "        self.assertEqual(days_in_feb(2024), 29)\n",
            encoding="utf-8",
        )
        if mode == "fix":
            body = (
                "import pathlib\n"
                "pathlib.Path('calendar.py').write_text("
                "'def days_in_feb(y):\\n"
                "    return 29 if (y % 4 == 0 and y % 100 != 0) or y % 400 == 0 else 28\\n')\n"
            )
        else:
            body = "import pathlib\npathlib.Path('calendar.py').write_text('def days_in_feb(y):\\n    return 30\\n')\n"
        agent = _write_agent(base, body)
        rc = _run_cli_do(monkeypatch, proj, agent, attempts=1)
        out = capsys.readouterr().out
        rj = _latest_result_json(base / "vwork")

        assert rj["acceptance"]["kind"] == "python_unittest"
        assert rj["baseline"]["status"] == "ok"
        assert rj["baseline"]["accept"] is False
        assert rj["baseline"]["run"] == 1
        assert rj["acceptance_integrity"] == "traced"
        if mode == "fix":
            assert rc == 0, out
            assert rj["accepted"] is True
            assert rj["delivered_attempt"] == 1
            assert "NOTE:" not in out
        else:
            assert rc == adapters_cli.EXIT["reject"], out
            assert rj["accepted"] is False
            assert rj["attempts"][0]["status"] == "ok"
            assert rj["attempts"][0]["accept"] is False
