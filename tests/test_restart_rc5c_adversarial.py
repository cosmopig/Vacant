"""Adversarial regression tests for rc5 round 3 (F1+F2, F3, F4).

Covers:
- F1+F2: Binary acceptance integrity analyzer ("verified" | "unverified"),
  recursive npm/make/sh/python/node tracing, local-import check, unverified
  WARNING + changed-files listing (suppressing misleading "protected (restored
  before check):"), receipt & result.json fields, audit list/show display,
  all Devin round-3 repros (r1, r2, r3, r3b, r9, r7b), 8+ unresolvable
  constructs, and common verified cases.
- F3: `.git/objects/info/**`, `.git/objects/pack/**` full lstat + loose object
  set-of-names diff under `.git/objects/??/`, prominent warning, outside_changes,
  receipt, and timing.
- F4: Repairing `$VACANT_HOME` permissions + retry once before writing receipt,
  prominent leading WARNING + `receipt_error` on unrecoverable failure without
  changing exit code, and `vacant audit list --strict` exiting non-zero on
  unsigned restart runs.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import textwrap

import pytest

from vacant_network import audit_export as AE
from vacant_network.adapters import cli as adapters_cli
from vacant_network.adapters import restart as R

needs_node = pytest.mark.skipif(
    shutil.which("node") is None or shutil.which("npm") is None,
    reason="node/npm not on PATH",
)
needs_make = pytest.mark.skipif(shutil.which("make") is None, reason="make not on PATH")
needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH")
needs_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="bash not on PATH")

UNTRACED_TAG = "— inputs not fully traced"
KEPT_FIXED_PREFIX = "kept fixed (restored to their start content before each check):"
OLD_UNVERIFIED_WARNING = (
    "WARNING: this check runs files in the project that the agent could change "
    "(Vacant could not fully trace what it executes); passing does not prove the "
    "check was not tampered with"
)


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
# F1 + F2 (i): Devin round-3 repros (r1, r2, r3, r3b, r9, r7b)
# ============================================================================

@needs_node
def test_f1_r1_npm_script_target_protected_and_unverified_due_to_local_import(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """r1: auto npm kind with scripts.test='node verify.js' where verify.js imports ./dep.js.
    verify.js must be protected (agent rewrite rejected), AND marked unverified because
    verify.js imports project-local dep.js."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "package.json").write_text('{"name":"x","scripts":{"test":"node verify.js"}}\n', encoding="utf-8")
    orig_verify = "const dep = require('./dep.js');\nprocess.exit(dep.answer() === 42 ? 0 : 1);\n"
    (proj / "verify.js").write_text(orig_verify, encoding="utf-8")
    (proj / "dep.js").write_text("exports.answer = () => 41;\n", encoding="utf-8")

    agent = _write_agent(tmp_path, "import pathlib\npathlib.Path('verify.js').write_text('process.exit(0);\\n')\n")
    rc = _run_cli_do(monkeypatch, proj, agent, prompt="make test pass", attempts=1)
    out = capsys.readouterr().out

    # verify.js was protected & restored -> agent tampering rejected!
    assert rc == adapters_cli.EXIT["reject"], out
    assert (proj / "verify.js").read_text(encoding="utf-8") == orig_verify
    assert UNTRACED_TAG in out
    assert OLD_UNVERIFIED_WARNING not in out
    assert KEPT_FIXED_PREFIX in out

    rj = _latest_result_json(tmp_path / "vwork")
    assert "verify.js" in rj["protected"]
    assert rj["acceptance_integrity"] == "untraced"
    assert any("script imports project modules" in r for r in rj["acceptance_integrity_reasons"])

    ok, why, receipts = R.verify_receipts(proj, state_root=tmp_path / "vhome")
    assert ok, why
    assert receipts[-1]["acceptance_integrity"] == "untraced"
    assert any("script imports project modules" in r for r in receipts[-1]["acceptance_integrity_reasons"])


def test_f1_r2_check_python_m_module_protected_and_unverified(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """r2: --check 'python3 -m verify' protects verify.py; because verify.py imports impl,
    it is rejected on tamper AND flagged untraced."""
    proj = tmp_path / "proj"
    proj.mkdir()
    orig_verify = "import sys\nimport impl\nsys.exit(0 if impl.answer() == 42 else 1)\n"
    (proj / "verify.py").write_text(orig_verify, encoding="utf-8")
    (proj / "impl.py").write_text("def answer():\n    return 41\n", encoding="utf-8")
    (proj / "test_keep.py").write_text(
        "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self): self.assertTrue(True)\n",
        encoding="utf-8",
    )

    agent = _write_agent(tmp_path, "import pathlib\npathlib.Path('verify.py').write_text('import sys\\nsys.exit(0)\\n')\n")
    rc = _run_cli_do(monkeypatch, proj, agent, extra_args=["--check", f"{sys.executable} -m verify"])
    out = capsys.readouterr().out

    assert rc == adapters_cli.EXIT["reject"], out
    assert (proj / "verify.py").read_text(encoding="utf-8") == orig_verify
    assert UNTRACED_TAG in out
    assert OLD_UNVERIFIED_WARNING not in out
    assert KEPT_FIXED_PREFIX in out

    rj = _latest_result_json(tmp_path / "vwork")
    assert "verify.py" in rj["protected"]
    assert rj["acceptance_integrity"] == "untraced"
    assert any("script imports project modules" in r for r in rj["acceptance_integrity_reasons"])

    ok, why, receipts = R.verify_receipts(proj, state_root=tmp_path / "vhome")
    assert ok, why
    assert receipts[-1]["acceptance_integrity"] == "untraced"


@needs_node
@pytest.mark.parametrize("check_cmd", [
    "if true; then npm test; fi",
    "( npm test )",
    "echo run | xargs -I RUN npm test",
])
def test_f1_r3_shell_constructs_hiding_npm_flagged_unverified(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], check_cmd: str
):
    """r3: if/then, subshell, xargs hiding npm test must yield untraced tag,
    list kept-fixed & changed files, and record in result.json + receipt + audit."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "package.json").write_text('{"name":"x","scripts":{"test":"node verify.test.js"}}\n', encoding="utf-8")
    (proj / "verify.test.js").write_text(
        "const dep = require('./dep.js');\nprocess.exit(dep.answer() === 42 ? 0 : 1);\n",
        encoding="utf-8",
    )
    (proj / "dep.js").write_text("exports.answer = () => 41;\n", encoding="utf-8")

    agent = _write_agent(tmp_path, textwrap.dedent("""\
        import json
        d = json.load(open("package.json"))
        d["scripts"]["test"] = "true"
        open("package.json", "w").write(json.dumps(d))
        """))
    _run_cli_do(monkeypatch, proj, agent, extra_args=["--check", check_cmd])
    out = capsys.readouterr().out

    assert UNTRACED_TAG in out
    assert OLD_UNVERIFIED_WARNING not in out
    assert KEPT_FIXED_PREFIX in out
    assert "package.json" in out  # listed among kept-fixed / tampered files

    rj = _latest_result_json(tmp_path / "vwork")
    assert rj["acceptance_integrity"] == "untraced"
    assert rj["acceptance_integrity_reasons"]

    ok, why, receipts = R.verify_receipts(proj, state_root=tmp_path / "vhome")
    assert ok, why
    assert receipts[-1]["acceptance_integrity"] == "untraced"
    assert receipts[-1]["acceptance_integrity_reasons"]

    # Check audit list and audit show display untraced
    vh, vw = str(tmp_path / "vhome"), str(tmp_path / "vwork")
    assert AE.main(["list", "--vacant-home", vh, "--work-root", vw]) == 0
    list_out = capsys.readouterr().out
    assert "untraced" in list_out
    rec_id = f"restart:{pathlib.Path(rj['run_dir']).name}"
    assert AE.main(["show", rec_id, "--vacant-home", vh, "--work-root", vw]) == 0
    show_out = capsys.readouterr().out
    assert "untraced" in show_out


@needs_node
@needs_make
def test_f1_r3b_make_recipe_calling_npm_protects_package_json_and_verifies(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """r3b: --check 'make test' where recipe calls 'npm test' -> follows Makefile ->
    protects & pins package.json -> follows node verify.test.js (no local imports) ->
    traced, agent tampering package.json is rejected."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "Makefile").write_text("test:\n\tnpm test\n", encoding="utf-8")
    orig_pkg = '{"name":"x","scripts":{"test":"node verify.test.js"}}\n'
    (proj / "package.json").write_text(orig_pkg, encoding="utf-8")
    (proj / "verify.test.js").write_text("process.exit(1);\n", encoding="utf-8")

    agent = _write_agent(tmp_path, textwrap.dedent("""\
        import json
        d = json.load(open("package.json"))
        d["scripts"]["test"] = "true"
        open("package.json", "w").write(json.dumps(d))
        """))
    rc = _run_cli_do(monkeypatch, proj, agent, extra_args=["--check", "make test"])
    out = capsys.readouterr().out

    assert rc == adapters_cli.EXIT["reject"], out
    assert (proj / "package.json").read_text(encoding="utf-8") == orig_pkg
    assert UNTRACED_TAG not in out
    assert OLD_UNVERIFIED_WARNING not in out
    assert KEPT_FIXED_PREFIX in out

    rj = _latest_result_json(tmp_path / "vwork")
    assert rj["acceptance_integrity"] == "traced"
    assert rj["acceptance_integrity_reasons"] == []
    assert {"Makefile", "package.json", "verify.test.js"} <= set(rj["protected"])


@needs_node
def test_f1_r9_npm_workspace_prefix_protects_sub_package_json_and_verifies(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """r9: auto npm kind with scripts.test='npm --prefix sub test' follows sub/package.json,
    protects & pins it, rejects agent rewrite of sub/package.json, and is traced."""
    proj = tmp_path / "proj"
    (proj / "sub").mkdir(parents=True)
    (proj / "package.json").write_text(
        '{"name":"root","workspaces":["sub"],"scripts":{"test":"npm --prefix sub test"}}\n',
        encoding="utf-8",
    )
    orig_sub = '{"name":"sub","scripts":{"test":"node real.test.js"}}\n'
    (proj / "sub" / "package.json").write_text(orig_sub, encoding="utf-8")
    (proj / "sub" / "real.test.js").write_text("process.exit(1);\n", encoding="utf-8")

    agent = _write_agent(tmp_path, textwrap.dedent("""\
        import json
        p = "sub/package.json"
        d = json.load(open(p)); d["scripts"]["test"] = "true"
        open(p, "w").write(json.dumps(d))
        """))
    rc = _run_cli_do(monkeypatch, proj, agent)
    out = capsys.readouterr().out

    assert rc == adapters_cli.EXIT["reject"], out
    assert (proj / "sub" / "package.json").read_text(encoding="utf-8") == orig_sub
    assert UNTRACED_TAG not in out
    assert OLD_UNVERIFIED_WARNING not in out
    assert KEPT_FIXED_PREFIX in out

    rj = _latest_result_json(tmp_path / "vwork")
    assert rj["acceptance_integrity"] == "traced"
    assert "sub/package.json" in rj["protected"]


@needs_bash
def test_f2_r7b_bash_verify_unquoted_file_flagged_unverified_and_lists_changed(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """r7b: --check 'bash verify.sh' where verify.sh runs 'python3 impl.py | diff -q - expected.txt'.
    Analyzer cannot trace diff/expected.txt -> untraced tag + NOTE naming expected.txt,
    lists expected.txt in changed files."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "test_keep.py").write_text(
        "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self): self.assertTrue(True)\n",
        encoding="utf-8",
    )
    (proj / "expected.txt").write_text("42\n", encoding="utf-8")
    (proj / "impl.py").write_text("print(41)\n", encoding="utf-8")
    (proj / "verify.sh").write_text(
        f"#!/bin/sh\n{sys.executable} impl.py | diff -q - expected.txt\n",
        encoding="utf-8",
    )

    agent = _write_agent(tmp_path, "import pathlib\npathlib.Path('expected.txt').write_text('41\\n')\n")
    rc = _run_cli_do(monkeypatch, proj, agent, extra_args=["--check", "bash verify.sh"])
    out = capsys.readouterr().out

    assert rc == 0, out
    assert UNTRACED_TAG in out
    assert OLD_UNVERIFIED_WARNING not in out
    assert "NOTE: the delivered attempt changed files the check reads or runs that were not kept fixed:" in out
    assert "expected.txt" in out

    rj = _latest_result_json(tmp_path / "vwork")
    assert rj["acceptance_integrity"] == "untraced"
    assert rj["acceptance_integrity_reasons"]
    assert "verify.sh" in rj["protected"]  # still protected what was understood

    ok, why, receipts = R.verify_receipts(proj, state_root=tmp_path / "vhome")
    assert ok, why
    assert receipts[-1]["acceptance_integrity"] == "untraced"


# ============================================================================
# F1 + F2 (ii): 8+ unresolvable shell/inline constructs -> untraced tag
# ============================================================================

@pytest.mark.parametrize("label,check_cmd", [
    ("function_def", "f() { true; }; f"),
    ("for_loop", "for x in 1; do true; done"),
    ("cmd_subst", "$(cat cmd.txt)"),
    ("eval_cmd", 'eval "true"'),
    ("heredoc", "sh <<'EOF'\ntrue\nEOF"),
    ("source_unresolvable", "bash -c 'source ./lib.sh'"),
    ("node_e_require", "node -e \"require('./x.js')\""),
    ("glob_tests", "bash tests/*.sh"),
    ("backticks", "`echo true`"),
    ("redirect_in", "cat < expected.txt"),
])
def test_f1_f2_unresolvable_constructs_yield_unverified_and_warning(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
    label: str, check_cmd: str,
):
    if label == "node_e_require" and shutil.which("node") is None:
        pytest.skip("node not on PATH")
    proj = tmp_path / "proj"
    (proj / "tests").mkdir(parents=True)
    (proj / "cmd.txt").write_text("true\n", encoding="utf-8")
    (proj / "expected.txt").write_text("ok\n", encoding="utf-8")
    (proj / "lib.sh").write_text("diff -q expected.txt expected.txt\n", encoding="utf-8")
    (proj / "x.js").write_text("module.exports = 1;\n", encoding="utf-8")
    (proj / "tests" / "a.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (proj / "work.txt").write_text("v1\n", encoding="utf-8")

    agent = _write_agent(tmp_path, "import pathlib\npathlib.Path('work.txt').write_text('v2\\n')\n")
    rc = _run_cli_do(monkeypatch, proj, agent, extra_args=["--check", check_cmd])
    out = capsys.readouterr().out

    assert rc == 0, f"{label}: unexpected rc={rc}\n{out}"
    assert UNTRACED_TAG in out, f"{label}: missing untraced tag\n{out}"
    assert OLD_UNVERIFIED_WARNING not in out, f"{label}: must not print old WARNING\n{out}"
    assert KEPT_FIXED_PREFIX in out, f"{label}: missing kept fixed line\n{out}"
    assert "work.txt" in out, f"{label}: changed file not listed\n{out}"

    rj = _latest_result_json(tmp_path / "vwork")
    assert rj["acceptance_integrity"] == "untraced", f"{label}: {rj}"
    assert rj["acceptance_integrity_reasons"], f"{label}: empty reasons"

    ok, why, receipts = R.verify_receipts(proj, state_root=tmp_path / "vhome")
    assert ok, why
    assert receipts[-1]["acceptance_integrity"] == "untraced"


def test_f1_f2_source_in_shell_script_unresolvable_yields_unverified(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """`source ./lib.sh` inside verify.sh (or directly via --check) yields untraced tag."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "lib.sh").write_text("diff -q a.txt a.txt\n", encoding="utf-8")
    (proj / "a.txt").write_text("hi\n", encoding="utf-8")
    (proj / "verify.sh").write_text("#!/bin/bash\nsource ./lib.sh\n", encoding="utf-8")

    agent = _write_agent(tmp_path, "import pathlib\npathlib.Path('a.txt').write_text('bye\\n')\n")
    rc = _run_cli_do(monkeypatch, proj, agent, extra_args=["--check", "bash verify.sh"])
    out = capsys.readouterr().out

    assert rc == 0, out
    assert UNTRACED_TAG in out
    assert OLD_UNVERIFIED_WARNING not in out
    assert KEPT_FIXED_PREFIX in out
    rj = _latest_result_json(tmp_path / "vwork")
    assert rj["acceptance_integrity"] == "untraced"


# ============================================================================
# F1 + F2 (iii): Common traced cases stay traced, with no tag and no NOTE
# ============================================================================

def test_f1_f2_common_verified_cases_stay_verified_no_warning(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """Plain unittest, pytest, npm+jest, clean bash verify.sh, and simple make test all stay traced."""
    # 1. Plain unittest
    p_uni = tmp_path / "uni"
    p_uni.mkdir()
    (p_uni / "calc.py").write_text("def add(a, b): return a - b\n", encoding="utf-8")
    (p_uni / "test_calc.py").write_text(
        "import unittest, calc\nclass T(unittest.TestCase):\n"
        "    def test_a(self): self.assertEqual(calc.add(2, 3), 5)\n",
        encoding="utf-8",
    )
    ag_uni = _write_agent(tmp_path, "import pathlib\npathlib.Path('calc.py').write_text('def add(a, b): return a + b\\n')\n", "ag_uni.py")
    rc = _run_cli_do(monkeypatch, p_uni, ag_uni, vhome=tmp_path / "vh_uni", vwork=tmp_path / "vw_uni")
    out = capsys.readouterr().out
    assert rc == 0, out
    assert UNTRACED_TAG not in out
    assert OLD_UNVERIFIED_WARNING not in out
    assert KEPT_FIXED_PREFIX in out
    rj = _latest_result_json(tmp_path / "vw_uni")
    assert rj["acceptance_integrity"] == "traced"
    assert rj["acceptance_integrity_reasons"] == []

    # Audit list & show display "traced"
    assert AE.main(["list", "--vacant-home", str(tmp_path / "vh_uni"), "--work-root", str(tmp_path / "vw_uni")]) == 0
    l_out = capsys.readouterr().out
    assert "INTEGRITY" in l_out and "traced" in l_out
    rec_id = f"restart:{pathlib.Path(rj['run_dir']).name}"
    assert AE.main(["show", rec_id, "--vacant-home", str(tmp_path / "vh_uni"), "--work-root", str(tmp_path / "vw_uni")]) == 0
    s_out = capsys.readouterr().out
    assert "traced" in s_out

    # 2. Plain pytest-style
    p_pyt = tmp_path / "pyt"
    p_pyt.mkdir()
    (p_pyt / "calc.py").write_text("def add(a, b): return a - b\n", encoding="utf-8")
    (p_pyt / "test_calc.py").write_text("import calc\ndef test_a(): assert calc.add(2, 3) == 5\n", encoding="utf-8")
    rc = _run_cli_do(monkeypatch, p_pyt, ag_uni, vhome=tmp_path / "vh_pyt", vwork=tmp_path / "vw_pyt")
    out = capsys.readouterr().out
    assert rc == 0, out
    assert UNTRACED_TAG not in out
    assert _latest_result_json(tmp_path / "vw_pyt")["acceptance_integrity"] == "traced"

    # 3. npm kind with scripts.test: "jest"
    p_npm = tmp_path / "npm_jest"
    p_npm.mkdir()
    (p_npm / "package.json").write_text('{"name":"demo","scripts":{"test":"jest"}}\n', encoding="utf-8")
    (p_npm / "app.test.js").write_text("test('ok', () => expect(1).toBe(1));\n", encoding="utf-8")
    if shutil.which("npm"):
        spec_npm = R.detect_acceptance(p_npm)
        assert spec_npm.kind == "npm"
        assert spec_npm.integrity == "traced"
        assert spec_npm.integrity_reasons == ()

    # 4. --check "bash verify.sh" with only understood lines
    p_sh = tmp_path / "sh_ok"
    p_sh.mkdir()
    (p_sh / "calc.py").write_text("def add(a, b): return a - b\n", encoding="utf-8")
    (p_sh / "test_calc.py").write_text(
        "import unittest, calc\nclass T(unittest.TestCase):\n"
        "    def test_a(self): self.assertEqual(calc.add(2, 3), 5)\n",
        encoding="utf-8",
    )
    (p_sh / "verify.sh").write_text(f"#!/bin/sh\nset -e\n{sys.executable} -m unittest\n", encoding="utf-8")
    rc = _run_cli_do(
        monkeypatch, p_sh, ag_uni,
        extra_args=["--check", "bash verify.sh"],
        vhome=tmp_path / "vh_sh", vwork=tmp_path / "vw_sh",
    )
    out = capsys.readouterr().out
    assert rc == 0, out
    assert UNTRACED_TAG not in out
    assert KEPT_FIXED_PREFIX in out
    rj_sh = _latest_result_json(tmp_path / "vw_sh")
    assert rj_sh["acceptance_integrity"] == "traced"
    assert "verify.sh" in rj_sh["protected"]

    # 5. --check "make test" with a simple recipe
    if shutil.which("make"):
        p_mk = tmp_path / "mk_ok"
        p_mk.mkdir()
        (p_mk / "calc.py").write_text("def add(a, b): return a - b\n", encoding="utf-8")
        (p_mk / "test_calc.py").write_text(
            "import unittest, calc\nclass T(unittest.TestCase):\n"
            "    def test_a(self): self.assertEqual(calc.add(2, 3), 5)\n",
            encoding="utf-8",
        )
        (p_mk / "Makefile").write_text(f"test:\n\t{sys.executable} -m unittest\n", encoding="utf-8")
        rc = _run_cli_do(
            monkeypatch, p_mk, ag_uni,
            extra_args=["--check", "make test"],
            vhome=tmp_path / "vh_mk", vwork=tmp_path / "vw_mk",
        )
        out = capsys.readouterr().out
        assert rc == 0, out
        assert UNTRACED_TAG not in out
        assert KEPT_FIXED_PREFIX in out
        rj_mk = _latest_result_json(tmp_path / "vw_mk")
        assert rj_mk["acceptance_integrity"] == "traced"
        assert "Makefile" in rj_mk["protected"]


# ============================================================================
# F3: .git/objects changes (info/**, pack/**, loose object add & delete)
# ============================================================================

@needs_git
def test_f3_r4_git_objects_info_pack_and_loose_add_delete_detected_and_warned(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """r4: writes to .git/objects/info/*, .git/objects/pack/*, and deleting/adding loose
    objects under .git/objects/??/ must appear in outside_changes, receipt, and warning."""
    proj = tmp_path / "proj"
    proj.mkdir()
    subprocess.run(["git", "init", "-q", "."], cwd=proj, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=proj, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=proj, check=True)
    (proj / "impl.py").write_text("def answer():\n    return 41\n", encoding="utf-8")
    (proj / "test_impl.py").write_text(
        "import unittest, impl\nclass T(unittest.TestCase):\n"
        "    def test_a(self): self.assertEqual(impl.answer(), 42)\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=proj, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=proj, check=True)

    loose_before = sorted(
        f.relative_to(proj).as_posix()
        for f in (proj / ".git" / "objects").rglob("*")
        if f.is_file() and "pack" not in f.parts and "info" not in f.parts
    )
    assert loose_before, "expected at least one loose git object"
    victim_loose = loose_before[0]

    agent = _write_agent(tmp_path, textwrap.dedent(f"""\
        import pathlib
        p = pathlib.Path("impl.py")
        p.write_text(p.read_text().replace("41", "42"))
        proj = pathlib.Path({str(proj)!r})
        info = proj / ".git/objects/info"
        info.mkdir(parents=True, exist_ok=True)
        (info / "alternates").write_text("/nonexistent/evil-objects\\n")
        (info / "grafts").write_text("0"*40 + " " + "1"*40 + "\\n")
        (proj / ".git/objects/pack/pack-evil.pack").write_text("PACK")
        (proj / {victim_loose!r}).unlink()
        new_dir = proj / ".git/objects/ff"
        new_dir.mkdir(parents=True, exist_ok=True)
        (new_dir / ("a" * 38)).write_bytes(b"fakeobj")
        """))

    rc = _run_cli_do(monkeypatch, proj, agent, prompt="fix impl")
    out = capsys.readouterr().out

    assert rc == 0, out
    assert "WARNING: .git/objects" in out

    rj = _latest_result_json(tmp_path / "vwork")
    oc = set(rj["outside_changes"])
    expected_paths = {
        ".git/objects/info/alternates",
        ".git/objects/info/grafts",
        ".git/objects/pack/pack-evil.pack",
        victim_loose,
        ".git/objects/ff/" + ("a" * 38),
    }
    assert expected_paths <= oc, f"missing from outside_changes: {expected_paths - oc}; got {oc}"
    assert isinstance(rj["lstat_listing_s"], (int, float)) and rj["lstat_listing_s"] >= 0.0

    ok, why, receipts = R.verify_receipts(proj, state_root=tmp_path / "vhome")
    assert ok, why
    rcpt_oc = set(receipts[-1]["outside_changes"])
    assert expected_paths <= rcpt_oc


def test_f3_loose_objects_scandir_names_only_no_content_read(tmp_path: pathlib.Path):
    """Loose objects under .git/objects/??/ are recorded by name only without reading contents
    or lstat-ing unreadable object bytes."""
    proj = tmp_path / "proj"
    loose_dir = proj / ".git" / "objects" / "ab"
    loose_dir.mkdir(parents=True)
    obj = loose_dir / ("c" * 38)
    obj.write_bytes(b"unreadable-content")
    os.chmod(obj, 0o000)  # cannot be read even if someone tried!
    try:
        listing = R._project_lstat_listing(proj)
        key = ".git/objects/ab/" + ("c" * 38)
        assert key in listing
        assert listing[key] == ("git_loose",)
    finally:
        os.chmod(obj, 0o600)


# ============================================================================
# F4: Receipt suppression repair + retry, failure warning, audit --strict
# ============================================================================

def test_f4_r5_chmod_vacant_home_repaired_and_receipt_written(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """r5: agent chmod -R 0500 $VACANT_HOME -> Vacant repairs state permissions, writes
    signed receipt, and `vacant audit list --strict` exits 0 with verified receipt."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "impl.py").write_text("def answer():\n    return 41\n", encoding="utf-8")
    (proj / "test_impl.py").write_text(
        "import unittest, impl\nclass T(unittest.TestCase):\n"
        "    def test_a(self): self.assertEqual(impl.answer(), 42)\n",
        encoding="utf-8",
    )
    vhome = tmp_path / "vhome"
    vwork = tmp_path / "vwork"

    agent = _write_agent(tmp_path, textwrap.dedent("""\
        import os, pathlib
        p = pathlib.Path("impl.py")
        p.write_text(p.read_text().replace("41", "42"))
        vh = os.environ["VACANT_HOME"]
        os.makedirs(vh, exist_ok=True)
        for dp, dns, fns in os.walk(vh, topdown=False):
            for n in fns + dns:
                try:
                    os.chmod(os.path.join(dp, n), 0o500)
                except OSError:
                    pass
            try:
                os.chmod(dp, 0o500)
            except OSError:
                pass
        """))

    try:
        rc = _run_cli_do(monkeypatch, proj, agent, vhome=vhome, vwork=vwork)
        out = capsys.readouterr().out

        assert rc == 0, out
        assert "could NOT be written" not in out
        rj = _latest_result_json(vwork)
        assert rj["receipt"]["recorded"] is True, rj["receipt"]
        assert not rj.get("receipt_error")

        ok, why, receipts = R.verify_receipts(proj, state_root=vhome)
        assert ok, why
        assert len(receipts) == 1

        audit_rc = AE.main(["list", "--vacant-home", str(vhome), "--work-root", str(vwork), "--strict"])
        assert audit_rc == 0
    finally:
        if vhome.exists():
            for dp, dns, fns in os.walk(vhome, topdown=True):
                try:
                    os.chmod(dp, 0o700)
                except OSError:
                    pass
                for n in dns + fns:
                    try:
                        os.chmod(os.path.join(dp, n), 0o700 if os.path.isdir(os.path.join(dp, n)) else 0o600)
                    except OSError:
                        pass


def test_f4_unrecoverable_receipt_failure_warns_first_line_records_error_and_strict_fails(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """When receipt writing still fails after permission repair + retry:
    - exit code is unchanged (0 for accepted run),
    - summary STARTS with prominent WARNING line,
    - result.json records `receipt_error`,
    - `vacant audit list --strict` exits non-zero (3)."""
    from vacant_network.trace.recorder import Recorder

    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "impl.py").write_text("def answer():\n    return 41\n", encoding="utf-8")
    (proj / "test_impl.py").write_text(
        "import unittest, impl\nclass T(unittest.TestCase):\n"
        "    def test_a(self): self.assertEqual(impl.answer(), 42)\n",
        encoding="utf-8",
    )
    vhome = tmp_path / "vhome"
    vwork = tmp_path / "vwork"
    agent = _write_agent(
        tmp_path,
        "import pathlib\np = pathlib.Path('impl.py'); p.write_text(p.read_text().replace('41', '42'))\n",
    )

    calls = {"n": 0}

    def _boom(self, etype, payload):
        calls["n"] += 1
        raise PermissionError("simulated persistent unwritable chain")

    monkeypatch.setattr(Recorder, "append", _boom)

    rc = _run_cli_do(monkeypatch, proj, agent, vhome=vhome, vwork=vwork)
    out = capsys.readouterr().out

    assert rc == 0, out  # exit code unchanged
    assert calls["n"] == 2  # initial attempt + 1 retry

    rj = _latest_result_json(vwork)
    assert rj["receipt"]["recorded"] is False
    assert rj.get("receipt_error") and "simulated persistent unwritable chain" in rj["receipt_error"]

    # summary() itself must start with the prominent WARNING line, and CLI output prints it before [vacant]
    sum_first = R.summary(rj).splitlines()[0]
    assert sum_first.startswith("WARNING: the signed receipt for this run could NOT be written (")
    assert "this run has no verifiable record" in sum_first
    assert sum_first in out
    assert out.index(sum_first) < out.index("[vacant] acceptance passed")

    # `vacant audit list --strict` must exit non-zero for an unsigned restart run
    audit_rc = AE.main(["list", "--vacant-home", str(vhome), "--work-root", str(vwork), "--strict"])
    assert audit_rc == 3
    export_rc = AE.main(["export", "--vacant-home", str(vhome), "--work-root", str(vwork), "--strict"])
    assert export_rc == 3
