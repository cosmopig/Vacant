"""Regression tests for rc5f narrow-unfreeze fixes:
- P1: project modules named like stdlib modules resolve to the project in all Python runners
  (python_unittest, python_pytest, python_bare) while keeping rc5e new-shadow exclusion.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
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


def _make_project_venv_with_pytest(proj: pathlib.Path) -> pathlib.Path:
    """Create a real `.venv` inside `proj` with pytest importable (reusing current pytest site-packages)."""
    spec = importlib.util.find_spec("pytest")
    if spec is None or not spec.origin:
        pytest.skip("pytest not available")
    venv_dir = proj / ".venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    vpy = venv_dir / "bin" / "python"
    vsp = subprocess.check_output(
        [str(vpy), "-c", "import site; print(site.getsitepackages()[0])"],
        text=True,
    ).strip()
    pytest_root = str(pathlib.Path(spec.origin).resolve().parent.parent)
    (pathlib.Path(vsp) / "vacant_test_pytest.pth").write_text(pytest_root + "\n", encoding="utf-8")
    return vpy


# ============================================================================
# P1: Project modules named like stdlib modules resolve to project first
# ============================================================================

def test_p1_ud_existing_queue_py_unittest(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """(u_d) Project has queue.py with FIFO bug; test does `from queue import Q`; agent fixes it."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "queue.py").write_text(
        "class Q:\n"
        "    def __init__(self): self.items=[]\n"
        "    def push(self,x): self.items.append(x)\n"
        "    def pop(self): return self.items.pop()   # bug: should be FIFO\n",
        encoding="utf-8",
    )
    (proj / "test_queue.py").write_text(
        "import unittest\n"
        "from queue import Q\n"
        "class T(unittest.TestCase):\n"
        "    def test_fifo(self):\n"
        "        q=Q(); q.push(1); q.push(2); self.assertEqual(q.pop(),1)\n",
        encoding="utf-8",
    )
    agent = _write_agent(
        tmp_path,
        "import pathlib\n"
        "p = pathlib.Path('queue.py')\n"
        "p.write_text(p.read_text().replace('self.items.pop()', 'self.items.pop(0)'))\n",
    )
    rc = _run_cli_do(monkeypatch, proj, agent, attempts=3)
    out = capsys.readouterr().out
    rj = _latest_result_json(tmp_path / "vwork")

    assert rc == 0, out
    assert rj["acceptance"]["kind"] == "python_unittest"
    assert rj["baseline"]["accept"] is False
    assert rj["baseline"]["status"] == "ok"
    assert rj["baseline"]["run"] == 1
    assert rj["accepted"] is True
    assert rj["delivered_attempt"] == 1
    assert rj["acceptance_integrity"] == "traced"
    assert "NOTE:" not in out
    assert "self.items.pop(0)" in (proj / "queue.py").read_text(encoding="utf-8")


def test_p1_ud2_existing_queue_py_pytest(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """(u_d2) Same as u_d with pytest inside project `.venv`."""
    proj = tmp_path / "proj"
    proj.mkdir()
    vpy = _make_project_venv_with_pytest(proj)
    (proj / "queue.py").write_text(
        "class Q:\n"
        "    def __init__(self): self.items=[]\n"
        "    def push(self,x): self.items.append(x)\n"
        "    def pop(self): return self.items.pop()   # bug: should be FIFO\n",
        encoding="utf-8",
    )
    (proj / "test_queue.py").write_text(
        "from queue import Q\n"
        "def test_fifo():\n"
        "    q=Q(); q.push(1); q.push(2); assert q.pop()==1\n",
        encoding="utf-8",
    )
    agent = _write_agent(
        tmp_path,
        "import pathlib\n"
        "p = pathlib.Path('queue.py')\n"
        "p.write_text(p.read_text().replace('self.items.pop()', 'self.items.pop(0)'))\n",
    )
    rc = _run_cli_do(monkeypatch, proj, agent, attempts=3)
    out = capsys.readouterr().out
    rj = _latest_result_json(tmp_path / "vwork")

    assert rc == 0, out
    assert rj["acceptance"]["kind"] == "python_pytest"
    assert rj["interpreter"] == str(vpy)
    assert rj["baseline"]["accept"] is False
    assert rj["baseline"]["run"] == 1
    assert rj["accepted"] is True
    assert rj["delivered_attempt"] == 1
    assert rj["acceptance_integrity"] == "traced"
    assert "NOTE:" not in out
    assert "self.items.pop(0)" in (proj / "queue.py").read_text(encoding="utf-8")


def test_p1_mine_m1_existing_statistics_py_unittest_broken(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """(mine_m1) Project statistics.py is buggy; agent makes it return None -> must FAIL (exit 40)."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "statistics.py").write_text(
        "def median(xs):\n    return sorted(xs)[0]\n",
        encoding="utf-8",
    )
    (proj / "test_stats.py").write_text(
        "import unittest\n"
        "from statistics import median\n"
        "class T(unittest.TestCase):\n"
        "    def test_median(self):\n"
        "        self.assertEqual(median([3, 1, 2]), 2)\n"
        "        self.assertEqual(median([5, 9, 7]), 7)\n",
        encoding="utf-8",
    )
    agent = _write_agent(
        tmp_path,
        "import pathlib\n"
        "pathlib.Path('statistics.py').write_text('def median(xs):\\n    return None\\n')\n",
    )
    rc = _run_cli_do(monkeypatch, proj, agent, attempts=3)
    out = capsys.readouterr().out
    rj = _latest_result_json(tmp_path / "vwork")

    assert rc == adapters_cli.EXIT["reject"], out
    assert rj["acceptance"]["kind"] == "python_unittest"
    assert rj["baseline"]["accept"] is False
    assert rj["accepted"] is False
    assert all(a["accept"] is False for a in rj["attempts"])


def test_p1_m10_existing_statistics_py_bare_broken(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """(m10) Same as mine_m1 on the python_bare runner -> must FAIL (exit 40)."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "statistics.py").write_text(
        "def median(xs):\n    return sorted(xs)[0]\n",
        encoding="utf-8",
    )
    (proj / "test_stats.py").write_text(
        "from statistics import median\n"
        "def test_median():\n"
        "    assert median([3, 1, 2]) == 2\n",
        encoding="utf-8",
    )
    agent = _write_agent(
        tmp_path,
        "import pathlib\n"
        "pathlib.Path('statistics.py').write_text('def median(xs):\\n    return None\\n')\n",
    )
    monkeypatch.setattr(R, "_pytest_available", lambda py_exe=None: False)
    rc = _run_cli_do(monkeypatch, proj, agent, attempts=2)
    out = capsys.readouterr().out
    rj = _latest_result_json(tmp_path / "vwork")

    assert rc == adapters_cli.EXIT["reject"], out
    assert rj["acceptance"]["kind"] == "python_bare"
    assert rj["baseline"]["accept"] is False
    assert rj["accepted"] is False
    assert all(a["accept"] is False for a in rj["attempts"])


def test_p1_new_stdlib_shadow_still_excluded_across_python_runners(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """rc5e compatibility: a NEW statistics.py (absent at start) that would shadow stdlib
    must remain excluded from the check copy and not written back under python_unittest,
    python_pytest, and python_bare."""
    # 1. python_unittest
    proj_u = tmp_path / "proj_u"
    proj_u.mkdir()
    (proj_u / "test_s.py").write_text(
        "import unittest\n"
        "from statistics import median\n"
        "class T(unittest.TestCase):\n"
        "    def test_m(self):\n"
        "        self.assertEqual(median([1, 2, 3]), 99)\n",
        encoding="utf-8",
    )
    agent = _write_agent(
        tmp_path,
        "import pathlib\n"
        "pathlib.Path('statistics.py').write_text('def median(xs): return 99\\n')\n",
    )
    rc_u = _run_cli_do(monkeypatch, proj_u, agent, attempts=1, vhome=tmp_path / "vh_u", vwork=tmp_path / "vw_u")
    capsys.readouterr()
    rj_u = _latest_result_json(tmp_path / "vw_u")
    assert rc_u == adapters_cli.EXIT["reject"]
    assert rj_u["acceptance"]["kind"] == "python_unittest"
    assert not (proj_u / "statistics.py").exists()
    assert "statistics.py" in rj_u["attempts"][0]["config_ignored"]

    # 2. python_bare
    proj_b = tmp_path / "proj_b"
    proj_b.mkdir()
    (proj_b / "test_s.py").write_text(
        "from statistics import median\n"
        "def test_m():\n"
        "    assert median([1, 2, 3]) == 99\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(R, "_pytest_available", lambda py_exe=None: False)
    rc_b = _run_cli_do(monkeypatch, proj_b, agent, attempts=1, vhome=tmp_path / "vh_b", vwork=tmp_path / "vw_b")
    capsys.readouterr()
    rj_b = _latest_result_json(tmp_path / "vw_b")
    assert rc_b == adapters_cli.EXIT["reject"]
    assert rj_b["acceptance"]["kind"] == "python_bare"
    assert not (proj_b / "statistics.py").exists()
    assert "statistics.py" in rj_b["attempts"][0]["config_ignored"]

    # 3. python_pytest (if pytest available)
    if importlib.util.find_spec("pytest") is not None:
        monkeypatch.undo()
        proj_p = tmp_path / "proj_p"
        proj_p.mkdir()
        _make_project_venv_with_pytest(proj_p)
        (proj_p / "test_s.py").write_text(
            "from statistics import median\n"
            "def test_m():\n"
            "    assert median([1, 2, 3]) == 99\n",
            encoding="utf-8",
        )
        rc_p = _run_cli_do(monkeypatch, proj_p, agent, attempts=1, vhome=tmp_path / "vh_p", vwork=tmp_path / "vw_p")
        capsys.readouterr()
        rj_p = _latest_result_json(tmp_path / "vw_p")
        assert rc_p == adapters_cli.EXIT["reject"]
        assert rj_p["acceptance"]["kind"] == "python_pytest"
        assert not (proj_p / "statistics.py").exists()
        assert "statistics.py" in rj_p["attempts"][0]["config_ignored"]


# ============================================================================
# P5: Unreadable files and directories stop upfront with exit 43 + receipt
# ============================================================================

def test_p5_unreadable_file_and_dir_stop_upfront_exit_43_with_receipt(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """Project with an unreadable file (chmod 000) and unreadable dir (chmod 000)
    stops before running the agent: exit 43, 0 attempts, clear message, project unchanged,
    signed receipt written and verifiable."""
    import os
    if os.geteuid() == 0:
        pytest.skip("running as root bypasses chmod 000")

    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "calc.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
    secret = proj / "secret.txt"
    secret.write_text("hidden\n", encoding="utf-8")
    locked = proj / "locked_dir"
    locked.mkdir()
    (locked / "inside.txt").write_text("nope\n", encoding="utf-8")
    marker = tmp_path / "agent_ran.txt"
    agent = _write_agent(
        tmp_path,
        f"import pathlib\npathlib.Path({str(marker)!r}).write_text('ran')\n"
        "pathlib.Path('calc.py').write_text('broken')\n",
    )

    secret.chmod(0o000)
    locked.chmod(0o000)
    try:
        rc = _run_cli_do(monkeypatch, proj, agent, attempts=3)
        out = capsys.readouterr().out
        rj = _latest_result_json(tmp_path / "vwork")

        assert rc == adapters_cli.EXIT["void"], out
        assert not marker.exists(), "agent must not have been run"
        assert rj["attempts"] == []
        assert rj["delivered_attempt"] == 0
        assert rj["unreadable_paths"] == ["locked_dir", "secret.txt"]
        assert "[vacant] cannot read 2 path(s) in the project (permission denied): locked_dir, secret.txt; " \
               "fix the permissions or move them out of the project. Nothing was run." in out
        assert "acceptance: none" not in out
        assert "acceptance: not detected (stopped before detection)" in out
        assert (proj / "calc.py").read_text(encoding="utf-8") == "def add(a, b): return a + b\n"
        assert rj["receipt"]["recorded"] is True
        ok, why, receipts = R.verify_receipts(proj, state_root=tmp_path / "vhome")
        assert ok, why
        assert len(receipts) == 1
        assert receipts[0]["unreadable_paths"] == ["locked_dir", "secret.txt"]
        assert receipts[0]["attempts"] == []
    finally:
        locked.chmod(0o700)
        secret.chmod(0o600)


# ============================================================================
# Smaller item 1: Dynamic imports in protected test files / kept-fixed scripts
# ============================================================================

@pytest.mark.parametrize("label,snippet", [
    ("import_module", "import importlib\nm = importlib.import_module('math')\n"),
    ("dunder_import", "m = __import__('math')\n"),
    ("exec", "exec('x = 1')\n"),
    ("eval", "y = eval('1 + 1')\n"),
    ("runpy", "import runpy\n"),
    ("spec_from_file_location", "import importlib.util\nfn = importlib.util.spec_from_file_location\n"),
])
def test_dynamic_import_in_auto_python_and_check_is_untraced(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
    label: str, snippet: str,
):
    """Any protected test file or kept-fixed script using dynamic import/exec must be
    verdict `untraced` with reason `dynamic-import` across auto python kinds and --check."""
    # 1. Auto python_unittest
    proj_u = tmp_path / f"{label}_u"
    proj_u.mkdir()
    (proj_u / "test_dyn.py").write_text(
        "import unittest\n" + snippet +
        "class T(unittest.TestCase):\n    def test_ok(self): self.assertTrue(True)\n",
        encoding="utf-8",
    )
    spec_u = R.detect_acceptance(proj_u)
    assert spec_u.kind == "python_unittest"
    assert spec_u.integrity == "untraced"
    assert any("dynamic-import" in r for r in spec_u.integrity_reasons), spec_u.integrity_reasons
    assert any(R._short_integrity_code(r) == "dynamic-import" for r in spec_u.integrity_reasons)

    # 2. Auto python_bare
    proj_b = tmp_path / f"{label}_b"
    proj_b.mkdir()
    (proj_b / "test_dyn.py").write_text(snippet + "def test_ok():\n    assert True\n", encoding="utf-8")
    monkeypatch.setattr(R, "_pytest_available", lambda py_exe=None: False)
    spec_b = R.detect_acceptance(proj_b)
    assert spec_b.kind == "python_bare"
    assert spec_b.integrity == "untraced"
    assert any("dynamic-import" in r for r in spec_b.integrity_reasons), spec_b.integrity_reasons

    # 3. Auto python_pytest (when pytest is available)
    if importlib.util.find_spec("pytest") is not None:
        monkeypatch.setattr(R, "_pytest_available", lambda py_exe=None: True)
        spec_p = R.detect_acceptance(proj_b)
        assert spec_p.kind == "python_pytest"
        assert spec_p.integrity == "untraced"
        assert any("dynamic-import" in r for r in spec_p.integrity_reasons), spec_p.integrity_reasons

    # 4. --check kept-fixed script
    proj_c = tmp_path / f"{label}_c"
    proj_c.mkdir()
    (proj_c / "check.py").write_text("import sys\n" + snippet + "sys.exit(0)\n", encoding="utf-8")
    spec_c = R.detect_acceptance(proj_c, check=f"{sys.executable} check.py")
    assert spec_c.integrity == "untraced"
    assert any("dynamic-import" in r for r in spec_c.integrity_reasons), spec_c.integrity_reasons
    assert any(R._short_integrity_code(r) == "dynamic-import" for r in spec_c.integrity_reasons)

    # 5. End-to-end auto python_unittest prints [dynamic-import] in summary
    if label == "import_module":
        monkeypatch.undo()
        agent = _write_agent(tmp_path, "pass\n", name="noop_agent.py")
        rc = _run_cli_do(
            monkeypatch, proj_u, agent, attempts=1,
            vhome=tmp_path / "vh_dyn", vwork=tmp_path / "vw_dyn",
        )
        out = capsys.readouterr().out
        rj = _latest_result_json(tmp_path / "vw_dyn")
        assert rc == 0, out
        assert rj["acceptance_integrity"] == "untraced"
        assert any("dynamic-import" in r for r in rj["acceptance_integrity_reasons"])
        assert "[dynamic-import]" in out


# ============================================================================
# Smaller item 2: Audit display for conflict runs
# ============================================================================

def test_audit_display_for_write_back_conflict_run(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """A run that passed acceptance but wrote nothing back due to write_back_conflicts (exit 43)
    must show `accepted, not written back (conflict)` in `vacant audit list` and `show`,
    while remaining cryptographically verifiable (`--strict` exit 0)."""
    from vacant_network import audit_export as AE

    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (proj / "test_calc.py").write_text(
        "import unittest, calc\n"
        "class T(unittest.TestCase):\n"
        "    def test_add(self): self.assertEqual(calc.add(2, 3), 5)\n",
        encoding="utf-8",
    )
    # Agent fixes calc.py in workspace AND edits the live project's calc.py to simulate concurrent edit
    agent = _write_agent(
        tmp_path,
        "import pathlib\n"
        "pathlib.Path('calc.py').write_text('def add(a, b):\\n    return a + b\\n')\n"
        f"pathlib.Path({str(proj / 'calc.py')!r}).write_text('def add(a, b):\\n    return a * 100\\n')\n",
    )
    vh = tmp_path / "vh_conf"
    vw = tmp_path / "vw_conf"
    rc = _run_cli_do(monkeypatch, proj, agent, attempts=1, vhome=vh, vwork=vw)
    capsys.readouterr()
    rj = _latest_result_json(vw)

    assert rc == adapters_cli.EXIT["void"]
    assert rj["accepted"] is True
    assert rj["write_back_conflicts"] == ["calc.py"]
    assert "return a * 100" in (proj / "calc.py").read_text(encoding="utf-8")

    # audit list --strict: verifiable (exit 0) and shows conflict status, not plain accepted
    rc_list = AE.main(["list", "--vacant-home", str(vh), "--work-root", str(vw), "--strict"])
    out_list = capsys.readouterr().out
    assert rc_list == 0, out_list
    assert "accepted, not written back (conflict)" in out_list
    assert "yes" in out_list

    # audit show: shows conflict status and remains verified=True
    run_id = pathlib.Path(rj["run_dir"]).name
    rc_show = AE.main(["show", f"restart:{run_id}", "--vacant-home", str(vh), "--work-root", str(vw)])
    out_show = capsys.readouterr().out
    assert rc_show == 0, out_show
    assert "result=accepted, not written back (conflict)" in out_show
    assert "verified=True" in out_show
    assert "write_back_conflict" in out_show


# ============================================================================
# Smaller item 3: Wording for shadowed modules vs real test-config files
# ============================================================================

def test_wording_shadow_module_not_called_test_configuration(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """A new file excluded for shadowing a module uses `left out of the check and not written back:`
    (not `added test configuration`); real test-config files keep `added test configuration`."""
    proj = tmp_path / "proj"
    (proj / "tests").mkdir(parents=True)
    (proj / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (proj / "tests" / "test_x.py").write_text(
        "import unittest\nclass T(unittest.TestCase):\n    def test_f(self): self.assertEqual(1, 2)\n",
        encoding="utf-8",
    )
    # 1. Shadowing module only
    agent_s = _write_agent(
        tmp_path,
        "import pathlib\npathlib.Path('unittest.py').write_text('import os\\nos._exit(0)\\n')\n",
        name="ag_shadow.py",
    )
    rc_s = _run_cli_do(
        monkeypatch, proj, agent_s, attempts=1,
        extra_args=["--check", f"{sys.executable} -m unittest discover -s tests -t ."],
        vhome=tmp_path / "vh_w1", vwork=tmp_path / "vw_w1",
    )
    out_s = capsys.readouterr().out
    assert rc_s == adapters_cli.EXIT["reject"]
    assert "left out of the check and not written back: unittest.py (shadows module 'unittest')" in out_s
    assert "added test configuration" not in out_s

    # 2. Both a real test-config (conftest.py) and a shadowed module (unittest.py)
    agent_both = _write_agent(
        tmp_path,
        "import pathlib\n"
        "pathlib.Path('conftest.py').write_text('# hook\\n')\n"
        "pathlib.Path('unittest.py').write_text('import os\\nos._exit(0)\\n')\n",
        name="ag_both.py",
    )
    rc_b = _run_cli_do(
        monkeypatch, proj, agent_both, attempts=1,
        extra_args=["--check", f"{sys.executable} -m unittest discover -s tests -t ."],
        vhome=tmp_path / "vh_w2", vwork=tmp_path / "vw_w2",
    )
    out_b = capsys.readouterr().out
    assert rc_b == adapters_cli.EXIT["reject"]
    assert "the agent added test configuration (conftest.py); not used for the check and not written back" in out_b
    assert "left out of the check and not written back: unittest.py (shadows module 'unittest')" in out_b




