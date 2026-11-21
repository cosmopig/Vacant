"""Adversarial regression tests for rc5 round 5 (F1-F3 module shadowing, package __init__.py chains,
new __init__.py under test dirs, .cargo/config*, and auto python kinds).

Covers:
- Normal cases (must stay completely clean: PASS, written back, traced, no NOTE, nothing ignored):
  1. Test does `from solution import add`; no `solution.py` at start; agent creates `solution.py`.
  2. Same, but agent creates package `solution/__init__.py` + `solution/core.py`.
  3. Project already has `queue.py` at start (same name as stdlib); agent fixes `queue.py`.
  4. Legit fix of `mypkg/core.py` (in a package with `mypkg/__init__.py`) produces NO NOTE.
- F1: Agent-created `unittest.py` (or `unittest/__init__.py`) shadowing stdlib under
  `--check "python3 -m unittest discover -s tests -t ."` is excluded from check copy,
  never written back, listed with "shadows module 'unittest'", verdict stays traced.
- F3: Agent-created `json.py` under `--check "python3 check.py"` (and `scripts/json.py`
  under `--check "python3 scripts/check.py"`), installed dist shadow (`pytest.py`), and
  cross-path project module shadow (`src/calc.py` at start, new root `calc.py`).
- F2: Package `__init__.py` chains for dotted imports (`a.b.c` -> `a/__init__.py`, `a/b/__init__.py`,
  plus `src/` layout) flagged in `acceptance_dependencies_changed` with reason `package-init`
  (no single-direct-import MUT exemption for `__init__.py`), under auto `python_unittest`,
  `python_pytest`, `python_bare`, and `--check "python3 check.py"`.
- New `__init__.py` under `tests/`, `test/`, `__tests__/`, or next to a protected test file
  treated as test-config (excluded from check copy, not written back, listed in `config_ignored`).
- `.cargo/config.toml` and `.cargo/config` added to test-config class.
"""
from __future__ import annotations

import json
import pathlib
import shutil
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
    attempts: int = 1,
    extra_args: list[str] | None = None,
    vhome: pathlib.Path | None = None,
    vwork: pathlib.Path | None = None,
) -> int:
    vh = vhome or (proj.parent / "vhome")
    vw = vwork or (proj.parent / "vwork")
    monkeypatch.setenv("VACANT_HOME", str(vh))
    monkeypatch.setenv("VACANT_WORK", str(vw))
    monkeypatch.setenv("VACANT_HOOK_NO_GC", "1")
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
# Normal cases (strictly untouched, clean delivery, traced, no NOTE, no ignore)
# ============================================================================

def test_normal_new_solution_module_untouched(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """Normal case 1: test imports `from solution import add`; no solution.py at start;
    agent creates solution.py -> PASS, written back, traced, no NOTE, nothing ignored."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "test_solution.py").write_text(textwrap.dedent("""\
        import unittest
        from solution import add

        class T(unittest.TestCase):
            def test_add(self):
                self.assertEqual(add(2, 3), 5)
    """), encoding="utf-8")

    agent = _write_agent(
        tmp_path,
        "import pathlib\npathlib.Path('solution.py').write_text('def add(a, b):\\n    return a + b\\n')\n",
    )
    rc = _run_cli_do(monkeypatch, proj, agent, attempts=1)
    out = capsys.readouterr().out
    rj = _latest_result_json(tmp_path / "vwork")

    assert rc == 0, out
    assert rj["accepted"] is True
    assert rj["acceptance_integrity"] == "traced"
    assert (proj / "solution.py").is_file()
    assert "return a + b" in (proj / "solution.py").read_text(encoding="utf-8")
    assert rj["attempts"][0]["config_ignored"] == []
    assert rj["acceptance_dependencies_changed"] == []
    assert "NOTE:" not in out
    assert "added test configuration" not in out
    assert "shadows module" not in out


def test_normal_new_solution_package_untouched(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """Normal case 2: test imports `from solution import add`; no solution at start;
    agent creates package solution/__init__.py + solution/core.py -> PASS, written back,
    traced, no NOTE, nothing ignored."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "test_solution.py").write_text(textwrap.dedent("""\
        import unittest
        from solution import add

        class T(unittest.TestCase):
            def test_add(self):
                self.assertEqual(add(2, 3), 5)
    """), encoding="utf-8")

    agent = _write_agent(
        tmp_path,
        textwrap.dedent("""\
            import pathlib
            pathlib.Path('solution').mkdir(exist_ok=True)
            pathlib.Path('solution/core.py').write_text('def add(a, b):\\n    return a + b\\n')
            pathlib.Path('solution/__init__.py').write_text('from .core import add\\n')
        """),
    )
    rc = _run_cli_do(monkeypatch, proj, agent, attempts=1)
    out = capsys.readouterr().out
    rj = _latest_result_json(tmp_path / "vwork")

    assert rc == 0, out
    assert rj["accepted"] is True
    assert rj["acceptance_integrity"] == "traced"
    assert (proj / "solution" / "__init__.py").is_file()
    assert (proj / "solution" / "core.py").is_file()
    assert rj["attempts"][0]["config_ignored"] == []
    assert rj["acceptance_dependencies_changed"] == []
    assert "NOTE:" not in out
    assert "added test configuration" not in out
    assert "shadows module" not in out


def test_normal_existing_stdlib_named_project_module_queue_py(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """Normal case 3: project already has queue.py at start (same name as stdlib module)
    and test imports it; agent fixes queue.py -> not ignored, written back, no NOTE."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "queue.py").write_text(textwrap.dedent("""\
        def make_queue():
            return []

        def enqueue(q, item):
            return q  # bug
    """), encoding="utf-8")
    (proj / "test_queue.py").write_text(textwrap.dedent("""\
        import unittest
        import queue

        class T(unittest.TestCase):
            def test_enqueue(self):
                q = queue.make_queue()
                queue.enqueue(q, 42)
                self.assertEqual(q, [42])
    """), encoding="utf-8")

    agent = _write_agent(
        tmp_path,
        textwrap.dedent("""\
            import pathlib
            pathlib.Path('queue.py').write_text(
                'def make_queue():\\n    return []\\n\\ndef enqueue(q, item):\\n    q.append(item)\\n    return q\\n'
            )
        """),
    )
    rc = _run_cli_do(
        monkeypatch, proj, agent, attempts=1,
        extra_args=["--check", f"{sys.executable} -m unittest test_queue.py"],
    )
    out = capsys.readouterr().out
    rj = _latest_result_json(tmp_path / "vwork")

    assert rc == 0, out
    assert rj["accepted"] is True
    assert rj["acceptance_integrity"] == "traced"
    assert "q.append(item)" in (proj / "queue.py").read_text(encoding="utf-8")
    assert rj["attempts"][0]["config_ignored"] == []
    assert rj["acceptance_dependencies_changed"] == []
    assert "NOTE:" not in out
    assert "added test configuration" not in out
    assert "shadows module" not in out


def test_normal_legit_fix_in_mypkg_core_no_note(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """Constraint: a legit fix changing mypkg/core.py (leaving mypkg/__init__.py untouched)
    must produce NO NOTE line."""
    proj = tmp_path / "proj"
    (proj / "mypkg").mkdir(parents=True)
    (proj / "mypkg" / "__init__.py").write_text("", encoding="utf-8")
    (proj / "mypkg" / "core.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (proj / "test_core.py").write_text(textwrap.dedent("""\
        import unittest
        from mypkg.core import add

        class T(unittest.TestCase):
            def test_add(self):
                self.assertEqual(add(2, 2), 4)
    """), encoding="utf-8")

    agent = _write_agent(
        tmp_path,
        "import pathlib\npathlib.Path('mypkg/core.py').write_text('def add(a, b):\\n    return a + b\\n')\n",
    )
    rc = _run_cli_do(monkeypatch, proj, agent, attempts=1)
    out = capsys.readouterr().out
    rj = _latest_result_json(tmp_path / "vwork")

    assert rc == 0, out
    assert rj["accepted"] is True
    assert rj["acceptance_integrity"] == "traced"
    assert rj["acceptance_dependencies_changed"] == []
    assert "NOTE:" not in out
    assert "return a + b" in (proj / "mypkg" / "core.py").read_text(encoding="utf-8")


# ============================================================================
# F1 & F3: Module shadowing (stdlib, installed distribution, cross-path project module)
# ============================================================================

def test_f1_unittest_py_shadow_excluded_and_not_written_back(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """F1 repro: `--check "python3 -m unittest discover -s tests -t ."`, agent creates
    root `unittest.py` (os._exit(0)). Must be excluded from check copy, check fails
    against real unittest, never written back, listed with "shadows module 'unittest'",
    and verdict stays traced."""
    proj = tmp_path / "proj"
    (proj / "tests").mkdir(parents=True)
    (proj / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (proj / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (proj / "tests" / "test_calc.py").write_text(textwrap.dedent("""\
        import unittest
        import math

        class T(unittest.TestCase):
            def test_math(self):
                self.assertEqual(math.gcd(4, 6), 99)
    """), encoding="utf-8")

    agent = _write_agent(
        tmp_path,
        "import pathlib\npathlib.Path('unittest.py').write_text('import os\\nos._exit(0)\\n')\n",
    )
    rc = _run_cli_do(
        monkeypatch, proj, agent, attempts=1,
        extra_args=["--check", f"{sys.executable} -m unittest discover -s tests -t ."],
    )
    out = capsys.readouterr().out
    rj = _latest_result_json(tmp_path / "vwork")

    assert rc == adapters_cli.EXIT["reject"], out
    assert rj["accepted"] is False
    assert rj["acceptance_integrity"] == "traced"
    assert not (proj / "unittest.py").exists(), "shadowing unittest.py must not be written back"
    assert "unittest.py" in rj["attempts"][0]["config_ignored"]
    assert "shadows module 'unittest'" in out


def test_f1_unittest_package_shadow_excluded(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """F1 package variant: agent creates `unittest/__init__.py` + `unittest/helper.py`."""
    proj = tmp_path / "proj"
    (proj / "tests").mkdir(parents=True)
    (proj / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (proj / "tests" / "test_calc.py").write_text(textwrap.dedent("""\
        import unittest
        class T(unittest.TestCase):
            def test_fail(self):
                self.assertEqual(1, 2)
    """), encoding="utf-8")

    agent = _write_agent(
        tmp_path,
        textwrap.dedent("""\
            import pathlib
            pathlib.Path('unittest').mkdir()
            pathlib.Path('unittest/__init__.py').write_text('import os\\nos._exit(0)\\n')
            pathlib.Path('unittest/helper.py').write_text('X = 1\\n')
        """),
    )
    rc = _run_cli_do(
        monkeypatch, proj, agent, attempts=1,
        extra_args=["--check", f"{sys.executable} -m unittest discover -s tests -t ."],
    )
    out = capsys.readouterr().out
    rj = _latest_result_json(tmp_path / "vwork")

    assert rc == adapters_cli.EXIT["reject"], out
    assert rj["accepted"] is False
    assert not (proj / "unittest").exists()
    assert "unittest/__init__.py" in rj["attempts"][0]["config_ignored"]
    assert "shadows module 'unittest'" in out


def test_f3_json_py_stdlib_shadow_excluded(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """F3 repro: `--check "python3 check.py"` where check.py imports json; agent creates
    root `json.py` (os._exit(0)). Must be excluded from check copy, check fails against
    real json, not written back, listed with "shadows module 'json'", verdict stays traced."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "check.py").write_text(textwrap.dedent("""\
        import json
        import sys

        expected = {"result": 42}
        got = {"result": 0}
        sys.exit(0 if json.dumps(got, sort_keys=True) == json.dumps(expected, sort_keys=True) else 1)
    """), encoding="utf-8")

    agent = _write_agent(
        tmp_path,
        "import pathlib\npathlib.Path('json.py').write_text('import os\\nos._exit(0)\\n')\n",
    )
    rc = _run_cli_do(
        monkeypatch, proj, agent, attempts=1,
        extra_args=["--check", f"{sys.executable} check.py"],
    )
    out = capsys.readouterr().out
    rj = _latest_result_json(tmp_path / "vwork")

    assert rc == adapters_cli.EXIT["reject"], out
    assert rj["accepted"] is False
    assert rj["acceptance_integrity"] == "traced"
    assert not (proj / "json.py").exists()
    assert "json.py" in rj["attempts"][0]["config_ignored"]
    assert "shadows module 'json'" in out


def test_f3_script_subdir_stdlib_shadow_excluded(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """F3 subdir variant: `--check "python3 scripts/check.py"`, agent creates `scripts/json.py`
    (sys.path[0] is the script directory `scripts/`)."""
    proj = tmp_path / "proj"
    (proj / "scripts").mkdir(parents=True)
    (proj / "scripts" / "check.py").write_text(textwrap.dedent("""\
        import json, sys
        sys.exit(0 if json.loads('{"x": 1}')["x"] == 2 else 1)
    """), encoding="utf-8")

    agent = _write_agent(
        tmp_path,
        "import pathlib\npathlib.Path('scripts/json.py').write_text('import os\\nos._exit(0)\\n')\n",
    )
    rc = _run_cli_do(
        monkeypatch, proj, agent, attempts=1,
        extra_args=["--check", f"{sys.executable} scripts/check.py"],
    )
    out = capsys.readouterr().out
    rj = _latest_result_json(tmp_path / "vwork")

    assert rc == adapters_cli.EXIT["reject"], out
    assert rj["accepted"] is False
    assert rj["acceptance_integrity"] == "traced"
    assert not (proj / "scripts" / "json.py").exists()
    assert "scripts/json.py" in rj["attempts"][0]["config_ignored"]
    assert "shadows module 'json'" in out


def test_f1_installed_distribution_shadow_pytest_py(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """Installed distribution shadow: `--check "<venv_python> -m pytest"`, agent creates
    root `pytest.py` (os._exit(0)). Must be excluded with "shadows module 'pytest'"."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "test_one.py").write_text("def test_fail():\n    assert 1 == 2\n", encoding="utf-8")

    agent = _write_agent(
        tmp_path,
        "import pathlib\npathlib.Path('pytest.py').write_text('import os\\nos._exit(0)\\n')\n",
    )
    rc = _run_cli_do(
        monkeypatch, proj, agent, attempts=1,
        extra_args=["--check", f"{sys.executable} -m pytest"],
    )
    out = capsys.readouterr().out
    rj = _latest_result_json(tmp_path / "vwork")

    assert rc == adapters_cli.EXIT["reject"], out
    assert rj["accepted"] is False
    assert rj["acceptance_integrity"] == "traced"
    assert not (proj / "pytest.py").exists()
    assert "pytest.py" in rj["attempts"][0]["config_ignored"]
    assert "shadows module 'pytest'" in out


def test_cross_path_project_module_shadow_src_vs_root(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """Cross-path shadow: `src/calc.py` existed at start; agent creates root `calc.py`
    that would shadow `src/calc.py`. Must be excluded with "shadows module 'calc'"."""
    proj = tmp_path / "proj"
    (proj / "src").mkdir(parents=True)
    (proj / "src" / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (proj / "test_calc.py").write_text(textwrap.dedent("""\
        import sys, pathlib, unittest
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / 'src'))
        import calc

        class T(unittest.TestCase):
            def test_add(self):
                self.assertEqual(calc.add(2, 3), 5)
    """), encoding="utf-8")

    agent = _write_agent(
        tmp_path,
        "import pathlib\npathlib.Path('calc.py').write_text('def add(a, b): return 5\\n')\n",
    )
    rc = _run_cli_do(monkeypatch, proj, agent, attempts=1)
    out = capsys.readouterr().out
    rj = _latest_result_json(tmp_path / "vwork")

    assert rc == adapters_cli.EXIT["reject"], out
    assert rj["accepted"] is False
    assert not (proj / "calc.py").exists(), "root calc.py shadowing src/calc.py must not be written back"
    assert "calc.py" in rj["attempts"][0]["config_ignored"]
    assert "shadows module 'calc'" in out


# ============================================================================
# F2: Package __init__.py chains (auto python_unittest, python_pytest, python_bare, --check)
# ============================================================================

def test_f2_auto_unittest_mypkg_init_poison_flagged_package_init(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """F2 repro: zero-config python_unittest; test_core.py does `from mypkg.core import add`;
    agent rewrites mypkg/__init__.py to monkeypatch TestCase.assertEqual.
    Must record `mypkg/__init__.py` with reason `package-init` and print NOTE line."""
    proj = tmp_path / "proj"
    (proj / "mypkg").mkdir(parents=True)
    (proj / "mypkg" / "__init__.py").write_text("", encoding="utf-8")
    (proj / "mypkg" / "core.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (proj / "test_core.py").write_text(textwrap.dedent("""\
        import unittest
        from mypkg.core import add

        class T(unittest.TestCase):
            def test_add(self):
                self.assertEqual(add(2, 2), 4)
    """), encoding="utf-8")

    agent = _write_agent(
        tmp_path,
        textwrap.dedent("""\
            import pathlib
            pathlib.Path('mypkg/__init__.py').write_text(
                'import unittest\\nunittest.TestCase.assertEqual = lambda *a, **k: None\\n'
            )
        """),
    )
    rc = _run_cli_do(monkeypatch, proj, agent, attempts=1)
    out = capsys.readouterr().out
    rj = _latest_result_json(tmp_path / "vwork")

    assert rc == 0, out
    assert rj["acceptance"]["kind"] == "python_unittest"
    deps = {d["path"]: d["reasons"] for d in rj["acceptance_dependencies_changed"]}
    assert "mypkg/__init__.py" in deps, rj["acceptance_dependencies_changed"]
    assert "package-init" in deps["mypkg/__init__.py"]
    assert "NOTE: the delivered attempt changed files the check reads or runs that were not kept fixed:" in out
    assert "mypkg/__init__.py (package-init)" in out


def test_f2_deep_package_init_chain_and_src_layout(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """Dotted import `a.b.c` includes both `a/__init__.py` and `a/b/__init__.py` (and src/ equivalents).
    Fixing `a/b/c.py` alone produces NO NOTE; changing `a/__init__.py` or `a/b/__init__.py` produces NOTE."""
    # Direct unit test of _find_acceptance_dependencies for both flat and src/ layouts
    test_src = b"import unittest\nfrom a.b.c import fn\n"
    known_flat = {"test_a.py", "a/__init__.py", "a/b/__init__.py", "a/b/c.py"}
    # Changing a/b/c.py only -> empty (MUT exemption still applies to a/b/c.py)
    assert R._find_acceptance_dependencies(
        {"test_a.py": test_src}, known_flat, {"a/b/c.py"}, start_files=known_flat
    ) == []
    # Changing a/__init__.py -> flagged package-init
    res_a = R._find_acceptance_dependencies(
        {"test_a.py": test_src}, known_flat, {"a/__init__.py"}, start_files=known_flat
    )
    assert res_a == [{"path": "a/__init__.py", "reasons": ["package-init"]}]
    # Changing a/b/__init__.py -> flagged package-init
    res_ab = R._find_acceptance_dependencies(
        {"test_a.py": test_src}, known_flat, {"a/b/__init__.py"}, start_files=known_flat
    )
    assert res_ab == [{"path": "a/b/__init__.py", "reasons": ["package-init"]}]

    # src/ layout
    known_src = {"test_a.py", "src/a/__init__.py", "src/a/b/__init__.py", "src/a/b/c.py"}
    assert R._find_acceptance_dependencies(
        {"test_a.py": test_src}, known_src, {"src/a/b/c.py"}, start_files=known_src
    ) == []
    res_src_a = R._find_acceptance_dependencies(
        {"test_a.py": test_src}, known_src, {"src/a/__init__.py"}, start_files=known_src
    )
    assert res_src_a == [{"path": "src/a/__init__.py", "reasons": ["package-init"]}]
    res_src_ab = R._find_acceptance_dependencies(
        {"test_a.py": test_src}, known_src, {"src/a/b/__init__.py"}, start_files=known_src
    )
    assert res_src_ab == [{"path": "src/a/b/__init__.py", "reasons": ["package-init"]}]

    # End-to-end src/ layout test
    proj = tmp_path / "proj"
    (proj / "src" / "a" / "b").mkdir(parents=True)
    (proj / "src" / "a" / "__init__.py").write_text("", encoding="utf-8")
    (proj / "src" / "a" / "b" / "__init__.py").write_text("", encoding="utf-8")
    (proj / "src" / "a" / "b" / "c.py").write_text("def fn():\n    return 0\n", encoding="utf-8")
    (proj / "test_a.py").write_text(textwrap.dedent("""\
        import pathlib, sys, unittest
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / 'src'))
        from a.b.c import fn

        class T(unittest.TestCase):
            def test_fn(self):
                self.assertEqual(fn(), 1)
    """), encoding="utf-8")

    agent = _write_agent(
        tmp_path,
        textwrap.dedent("""\
            import pathlib
            pathlib.Path('src/a/b/__init__.py').write_text(
                'import unittest\\nunittest.TestCase.assertEqual = lambda *a, **k: None\\n'
            )
        """),
    )
    rc = _run_cli_do(monkeypatch, proj, agent, attempts=1)
    out = capsys.readouterr().out
    rj = _latest_result_json(tmp_path / "vwork")

    assert rc == 0, out
    deps = {d["path"]: d["reasons"] for d in rj["acceptance_dependencies_changed"]}
    assert "src/a/b/__init__.py" in deps and "package-init" in deps["src/a/b/__init__.py"]
    assert "NOTE:" in out and "src/a/b/__init__.py (package-init)" in out


def test_f2_kept_fixed_check_script_package_init_flagged(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """Kept-fixed script `--check "python3 check.py"` doing `from mypkg.core import add`:
    changing `mypkg/__init__.py` triggers NOTE with `package-init`."""
    proj = tmp_path / "proj"
    (proj / "mypkg").mkdir(parents=True)
    (proj / "mypkg" / "__init__.py").write_text("", encoding="utf-8")
    (proj / "mypkg" / "core.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (proj / "check.py").write_text(textwrap.dedent("""\
        import sys
        from mypkg.core import add
        sys.exit(0 if add(2, 2) == 4 else 1)
    """), encoding="utf-8")

    agent = _write_agent(
        tmp_path,
        "import pathlib\npathlib.Path('mypkg/__init__.py').write_text('import os\\nos._exit(0)\\n')\n",
    )
    rc = _run_cli_do(
        monkeypatch, proj, agent, attempts=1,
        extra_args=["--check", f"{sys.executable} check.py"],
    )
    out = capsys.readouterr().out
    rj = _latest_result_json(tmp_path / "vwork")

    assert rc == 0, out
    deps = {d["path"]: d["reasons"] for d in rj["acceptance_dependencies_changed"]}
    assert "mypkg/__init__.py" in deps and "package-init" in deps["mypkg/__init__.py"]
    assert "NOTE:" in out and "mypkg/__init__.py (package-init)" in out


def test_auto_python_pytest_and_bare_shadow_and_package_init(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """Auto python_pytest and python_bare both apply shadow exclusion and package-init flagging."""
    # 1. Auto python_pytest (force venv python via VIRTUAL_ENV or monkeypatch resolve_python)
    proj_p = tmp_path / "proj_pytest"
    (proj_p / "mypkg").mkdir(parents=True)
    (proj_p / "mypkg" / "__init__.py").write_text("", encoding="utf-8")
    (proj_p / "mypkg" / "core.py").write_text("def val():\n    return 0\n", encoding="utf-8")
    (proj_p / "test_core.py").write_text(textwrap.dedent("""\
        import json
        from mypkg.core import val

        def test_val():
            assert json.loads(str(val())) == 1
    """), encoding="utf-8")

    monkeypatch.setattr(R, "resolve_python", lambda project=None: sys.executable)
    agent_shadow = _write_agent(
        tmp_path,
        "import pathlib\npathlib.Path('json.py').write_text('def loads(x): return 1\\n')\n",
        name="agent_shadow.py",
    )
    rc_p = _run_cli_do(
        monkeypatch, proj_p, agent_shadow, attempts=1,
        vhome=tmp_path / "vh_p", vwork=tmp_path / "vw_p",
    )
    out_p = capsys.readouterr().out
    rj_p = _latest_result_json(tmp_path / "vw_p")

    assert rj_p["acceptance"]["kind"] == "python_pytest"
    assert rc_p == adapters_cli.EXIT["reject"], out_p
    assert not (proj_p / "json.py").exists()
    assert "json.py" in rj_p["attempts"][0]["config_ignored"]
    assert "shadows module 'json'" in out_p

    # 2. Auto python_bare (force _pytest_available -> False)
    monkeypatch.setattr(R, "_pytest_available", lambda py_exe=None: False)
    rc_b = _run_cli_do(
        monkeypatch, proj_p, agent_shadow, attempts=1,
        vhome=tmp_path / "vh_b", vwork=tmp_path / "vw_b",
    )
    out_b = capsys.readouterr().out
    rj_b = _latest_result_json(tmp_path / "vw_b")

    assert rj_b["acceptance"]["kind"] == "python_bare"
    assert rc_b == adapters_cli.EXIT["reject"], out_b
    assert not (proj_p / "json.py").exists()
    assert "json.py" in rj_b["attempts"][0]["config_ignored"]
    assert "shadows module 'json'" in out_b

    # 3. Package __init__.py poisoning under python_bare -> flagged with package-init
    agent_init = _write_agent(
        tmp_path,
        textwrap.dedent("""\
            import pathlib
            pathlib.Path('mypkg/__init__.py').write_text(
                'import sys, types\\n'
                'm = types.ModuleType("mypkg.core")\\n'
                'm.val = lambda: 1\\n'
                'sys.modules["mypkg.core"] = m\\n'
            )
        """),
        name="agent_init.py",
    )
    rc_bi = _run_cli_do(
        monkeypatch, proj_p, agent_init, attempts=1,
        vhome=tmp_path / "vh_bi", vwork=tmp_path / "vw_bi",
    )
    out_bi = capsys.readouterr().out
    rj_bi = _latest_result_json(tmp_path / "vw_bi")

    assert rj_bi["acceptance"]["kind"] == "python_bare"
    assert rc_bi == 0, out_bi
    deps_bi = {d["path"]: d["reasons"] for d in rj_bi["acceptance_dependencies_changed"]}
    assert "mypkg/__init__.py" in deps_bi and "package-init" in deps_bi["mypkg/__init__.py"]
    assert "NOTE:" in out_bi and "mypkg/__init__.py (package-init)" in out_bi


# ============================================================================
# Fix 3: New __init__.py under protected test dirs or next to a protected test file
# ============================================================================

def test_new_init_py_under_test_dir_excluded_and_not_written_back(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """A new `tests/__init__.py` (did not exist at start) is treated as test-config:
    excluded from check copy, not written back, listed in config_ignored."""
    proj = tmp_path / "proj"
    (proj / "tests").mkdir(parents=True)
    (proj / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (proj / "tests" / "test_calc.py").write_text(textwrap.dedent("""\
        import unittest
        from calc import add

        class T(unittest.TestCase):
            def test_add(self):
                self.assertEqual(add(2, 2), 4)
    """), encoding="utf-8")

    agent = _write_agent(
        tmp_path,
        textwrap.dedent("""\
            import pathlib
            pathlib.Path('tests/__init__.py').write_text(
                'import unittest\\nunittest.TestCase.assertEqual = lambda *a, **k: None\\n'
            )
        """),
    )
    rc = _run_cli_do(
        monkeypatch, proj, agent, attempts=1,
        extra_args=["--check", f"{sys.executable} -m unittest discover -s tests -t ."],
    )
    out = capsys.readouterr().out
    rj = _latest_result_json(tmp_path / "vwork")

    assert rc == adapters_cli.EXIT["reject"], out
    assert rj["accepted"] is False
    assert not (proj / "tests" / "__init__.py").exists()
    assert "tests/__init__.py" in rj["attempts"][0]["config_ignored"]


def test_new_init_py_next_to_protected_test_file_in_custom_dir_excluded(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """A new `__init__.py` next to a protected test file in a non-standard dir (e.g. `checks/test_x.py`)
    or at project root next to `test_x.py` is excluded as test-config."""
    proj = tmp_path / "proj"
    (proj / "checks").mkdir(parents=True)
    (proj / "checks" / "test_x.py").write_text(textwrap.dedent("""\
        import unittest
        class T(unittest.TestCase):
            def test_fail(self):
                self.assertEqual(1, 2)
    """), encoding="utf-8")

    agent = _write_agent(
        tmp_path,
        textwrap.dedent("""\
            import pathlib
            pathlib.Path('checks/__init__.py').write_text('import os\\nos._exit(0)\\n')
        """),
    )
    rc = _run_cli_do(
        monkeypatch, proj, agent, attempts=1,
        extra_args=["--check", f"{sys.executable} -m unittest discover -s checks -t ."],
    )
    out = capsys.readouterr().out
    rj = _latest_result_json(tmp_path / "vwork")

    assert rc == adapters_cli.EXIT["reject"], out
    assert rj["accepted"] is False
    assert not (proj / "checks" / "__init__.py").exists()
    assert "checks/__init__.py" in rj["attempts"][0]["config_ignored"]

    # Also verify spec-level coverage for test/, __tests__/, and root __init__.py next to root test_x.py
    root_proj = tmp_path / "root_proj"
    root_proj.mkdir()
    (root_proj / "test_root.py").write_text("import unittest\nclass T(unittest.TestCase):\n    def test_a(self): pass\n", encoding="utf-8")
    spec = R.detect_acceptance(root_proj)
    assert spec.ignored_new_file_reason("__init__.py") == ""
    assert spec.ignored_new_file_reason("tests/__init__.py") == ""
    assert spec.ignored_new_file_reason("test/__init__.py") == ""
    assert spec.ignored_new_file_reason("__tests__/__init__.py") == ""
    assert spec.ignored_new_file_reason("solution/__init__.py") is None


# ============================================================================
# Fix 4: .cargo/config.toml and .cargo/config in test-config class
# ============================================================================

def test_cargo_config_in_test_config_class(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """`.cargo/config.toml` and `.cargo/config` are in the test-config class; plain `config.toml` is NOT."""
    assert R._is_test_config(".cargo/config.toml") is True
    assert R._is_test_config(".cargo/config") is True
    assert R._is_test_config("crates/sub/.cargo/config.toml") is True
    assert R._is_test_config("crates/sub/.cargo/config") is True
    assert R._is_test_config("config.toml") is False
    assert R._is_test_config("src/config.toml") is False
    assert R._is_test_config("config") is False
    assert R._is_test_config("src/config") is False

    # Existing .cargo/config.toml is kept fixed; agent-created .cargo/config is ignored
    proj = tmp_path / "proj"
    (proj / ".cargo").mkdir(parents=True)
    (proj / ".cargo" / "config.toml").write_text("[build]\njobs = 1\n", encoding="utf-8")
    (proj / "check.py").write_text("import sys; sys.exit(1)\n", encoding="utf-8")

    agent = _write_agent(
        tmp_path,
        textwrap.dedent("""\
            import pathlib
            pathlib.Path('.cargo/config.toml').write_text('[target.x86_64-unknown-linux-gnu]\\nrunner = "/bin/true"\\n')
            pathlib.Path('.cargo/config').write_text('[target.x86_64-unknown-linux-gnu]\\nrunner = "/bin/true"\\n')
        """),
    )
    rc = _run_cli_do(
        monkeypatch, proj, agent, attempts=1,
        extra_args=["--check", f"{sys.executable} check.py"],
    )
    out = capsys.readouterr().out
    rj = _latest_result_json(tmp_path / "vwork")

    assert rc == adapters_cli.EXIT["reject"], out
    assert ".cargo/config.toml" in rj["protected"]
    assert (proj / ".cargo" / "config.toml").read_text(encoding="utf-8") == "[build]\njobs = 1\n"
    assert not (proj / ".cargo" / "config").exists()
    assert ".cargo/config" in rj["attempts"][0]["config_ignored"]
