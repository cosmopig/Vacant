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


def test_rc6_4_baseline_already_passing_no_changes(tmp_path):
    """rc6(4): When baseline already passes and agent makes no changes, headline states
    tests were already passing before the agent ran, and that agent made no changes."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "calc.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
    (proj / "test_calc.py").write_text(
        "import unittest, calc\nclass T(unittest.TestCase):\n"
        "    def test_add(self): self.assertEqual(calc.add(2, 3), 5)\n",
        encoding="utf-8",
    )
    cp, rj, _, _ = _run_cli(proj, "pass\n", tmp_path)
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert rj["accepted"] is True
    assert len(rj["attempts"]) == 1
    headline = next(ln for ln in cp.stdout.splitlines() if ln.startswith("[vacant] "))
    assert "tests were already passing before the agent ran" in headline
    assert "made no changes" in headline
    assert "acceptance passed on attempt" not in headline


def test_rc6_4_baseline_already_passing_with_changes(tmp_path):
    """rc6(4): When baseline already passes and agent modifies a file (still passing),
    headline leads with baseline already passing, then states what the agent changed."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "calc.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
    (proj / "test_calc.py").write_text(
        "import unittest, calc\nclass T(unittest.TestCase):\n"
        "    def test_add(self): self.assertEqual(calc.add(2, 3), 5)\n",
        encoding="utf-8",
    )
    agent_code = "import pathlib\npathlib.Path('calc.py').write_text('def add(a, b):\\n    return a + b\\n')\n"
    cp, rj, _, _ = _run_cli(proj, agent_code, tmp_path)
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert rj["accepted"] is True
    headline = next(ln for ln in cp.stdout.splitlines() if ln.startswith("[vacant] "))
    assert "tests were already passing before the agent ran" in headline
    assert "changed files" in headline
    assert "1 modified" in headline
    assert "return a + b\n" in (proj / "calc.py").read_text(encoding="utf-8")


def test_rc6_5_cache_noise_collapsed_and_markers_explained(tmp_path):
    """rc6(5): __pycache__ / .pytest_cache files in not_delivered are collapsed into a single count,
    non-cache skipped files stay listed, and +/~/- markers are explained inline and in --help."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "calc.py").write_text("def add(a, b): return a - b\n", encoding="utf-8")
    (proj / "test_calc.py").write_text(
        "import unittest, calc\nclass T(unittest.TestCase):\n"
        "    def test_add(self): self.assertEqual(calc.add(2, 3), 5)\n",
        encoding="utf-8",
    )
    agent_code = textwrap.dedent("""\
        import pathlib
        pathlib.Path("calc.py").write_text("def add(a, b): return a + b\\n")
        for rel in [
            "__pycache__/calc.cpython-312.pyc",
            "__pycache__/test_calc.cpython-312.pyc",
            ".pytest_cache/CACHEDIR.TAG",
            ".pytest_cache/v/cache/nodeids",
        ]:
            p = pathlib.Path(rel)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x\\n")
    """)
    cp, rj, _, _ = _run_cli(proj, agent_code, tmp_path)
    out = cp.stdout
    assert cp.returncode == 0, out + cp.stderr
    # result.json keeps full list
    assert len(rj["not_delivered"]) == 4
    # summary collapses cache files and does NOT list individual .pyc / CACHEDIR.TAG paths
    assert "not delivered: 4 cache files (__pycache__/.pytest_cache)" in out
    assert "calc.cpython-312.pyc" not in out
    assert "CACHEDIR.TAG" not in out
    # + / ~ / - legend explained inline
    assert "changed files (+ added, ~ modified, - deleted): ~calc.py" in out

    # Also verify --help explains + / ~ / -
    help_cp = subprocess.run(
        [sys.executable, "-m", "vacant_network.cli", "do", "--help"],
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
        capture_output=True, text=True, timeout=30,
    )
    assert help_cp.returncode == 0
    assert "+ added" in help_cp.stdout and "~ modified" in help_cp.stdout and "- deleted" in help_cp.stdout


def test_rc6_6_npm_node_test_human_message_and_pass_fail_only(tmp_path):
    """rc6(6): `node --test` shows a plain-language note instead of [unsupported-option:node:--test],
    and npm reports honestly that this check only reports pass/fail (no per-test count)."""
    import shutil
    if not shutil.which("npm") or not shutil.which("node"):
        import pytest
        pytest.skip("npm/node not installed")

    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "package.json").write_text(
        json.dumps({"name": "dur", "version": "1.0.0", "scripts": {"test": "node --test"}}),
        encoding="utf-8",
    )
    (proj / "lib").mkdir()
    (proj / "lib" / "add.js").write_text("module.exports = (a, b) => a - b;\n", encoding="utf-8")
    (proj / "test").mkdir()
    (proj / "test" / "add.test.js").write_text(
        "const test = require('node:test');\n"
        "const assert = require('node:assert/strict');\n"
        "const add = require('../lib/add');\n"
        "test('adds', () => assert.equal(add(2, 3), 5));\n",
        encoding="utf-8",
    )
    agent_code = "import pathlib\npathlib.Path('lib/add.js').write_text('module.exports = (a, b) => a + b;\\n')\n"
    cp, rj, _, _ = _run_cli(proj, agent_code, tmp_path)
    out = cp.stdout
    assert cp.returncode == 0, out + cp.stderr
    assert rj["accepted"] is True
    assert "unsupported-option:node:--test" not in out
    assert "node --test" in out
    assert "pass/fail only" in out


def test_rc6_9_readmes_synced_for_vacant_do_and_selftest():
    """rc6(9): All 3 READMEs cover `vacant do` flags, exit codes, output/receipt locations,
    markers, honest cloud-agent caveat, and updated selftest output."""
    for name in ("README.md", "README.en.md", "README.ja.md"):
        txt = (REPO_ROOT / name).read_text(encoding="utf-8")
        for token in (
            "vacant do claude",
            "--cmd",
            "--prompt-file",
            "--check",
            "--protect",
            "--timeout",
            "--attempt-timeout",
            "--stream",
            "tail -f",
            "VACANT_WORK",
            "VACANT_HOME",
            "vacant audit show",
            "| `0` |",
            "| `40` |",
            "| `43` |",
            "| `130` |",
            "1/6",
        ):
            assert token in txt, f"{name} missing {token!r}"
        assert "4/6" not in txt, f"{name} still has stale 4/6 selftest count"


def test_long_traceback_keeps_test_name_and_assertion_line(tmp_path):
    """第二次查證 P5：traceback 超過 800 字元時，原本只留尾端、把測試名稱截掉（訊息變成 `first failure: -  196,`）。"""
    import sys as _sys
    from vacant_network.adapters import restart as _R
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "calc.py").write_text("def items(): return []\n", encoding="utf-8")
    (proj / "test_calc.py").write_text(
        "import unittest, calc\nclass T(unittest.TestCase):\n    maxDiff=None\n"
        "    def test_items(self): self.assertEqual(calc.items(), list(range(100)))\n"
        "    def test_ok(self): pass\n", encoding="utf-8")
    agent = tmp_path / "ag.py"
    agent.write_text("import pathlib\npathlib.Path('calc.py').write_text('def items(): return list(range(0,200,2))\\n')\n",
                     encoding="utf-8")
    res = _R.run(proj, lambda p, ws: _R.Launch(argv=[_sys.executable, str(agent)], env={}), "x",
                 max_attempts=1, attempt_timeout_s=30, budget_s=60)
    msg = _R.summary(res)
    assert "first failing test: test_items" in msg, msg
    assert "AssertionError: Lists differ" in msg, msg


def test_node_test_tap_failure_shows_not_ok_name_and_error(tmp_path):
    """第二次查證 P5：`node --test` 失敗時原本印 TAP 尾端的 `# todo 0`／`# duration_ms`。"""
    import shutil as _sh
    import sys as _sys
    import pytest as _pt
    from vacant_network.adapters import restart as _R
    if not (_sh.which("node") and _sh.which("npm")):
        _pt.skip("node/npm not installed")
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "package.json").write_text('{"name":"t","version":"1.0.0","scripts":{"test":"node --test"}}\n', encoding="utf-8")
    (proj / "calc.js").write_text("exports.add=(a,b)=>a-b;\n", encoding="utf-8")
    (proj / "calc.test.js").write_text(
        "const test=require('node:test');const assert=require('node:assert');const {add}=require('./calc');\n"
        "test('adds numbers',()=>{assert.strictEqual(add(1,2),3);});\ntest('ok',()=>{});\n", encoding="utf-8")
    res = _R.run(proj, lambda p, ws: _R.Launch(argv=[_sys.executable, "-c", "pass"], env={}), "x",
                 max_attempts=1, attempt_timeout_s=60, budget_s=120)
    msg = _R.summary(res)
    assert "first failing test: adds numbers" in msg, msg
    assert "-1 !== 3" in msg, msg
    assert "# todo" not in msg and "duration_ms" not in msg, msg
