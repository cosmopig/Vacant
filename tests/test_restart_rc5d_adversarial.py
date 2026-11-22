"""Adversarial regression tests for rc5 round 4 (F1-F8 + traced/untraced rename & factual summary).

Covers:
- F1: `.npmrc`, `.yarnrc`, `.yarnrc.yml`, `.pnpmrc`, `pnpm-workspace.yaml`, `.babelrc`,
  `.babelrc.*`, `babel.config.*`, `.swcrc`, `tsconfig*.json` treated as test-config-class
  (existing kept fixed; agent-created excluded from check copy & write-back via config_ignored).
- F2: `make` up-to-date semantics: non-.PHONY target on traced chain with existing file/dir
  -> untraced with reason `make target 'X' is not .PHONY and a file named X exists`;
  agent-created file/dir matching traced non-.PHONY target -> excluded & not written back.
- F3: `make` `.DEFAULT_GOAL` (`:=`, `=`, `?=`) honored; unresolvable `.DEFAULT_GOAL` -> untraced.
- F4: `python -m unittest discover` with `-s`/`-p`/`-t` or positional start/pattern protects
  existing matching files and excludes agent-created matching files; empty kept-fixed set when
  check runs project code is NEVER `traced`, and contradictory "protected: none — ..." is gone.
- F5: Python FILE scripts get the same AST checks as `python -c` (os.system/popen/exec*/spawn*,
  subprocess, pty, ctypes, importlib, runpy, __import__, eval, exec, compile, non-constant open,
  unprotected relative open, pathlib read_text/read_bytes/open); constant open() to existing
  project file is kept fixed instead.
- F6: Node JS FILE scripts flag fs/fs/promises/child_process/worker_threads/vm, non-literal
  require/import, process.binding, eval, new Function; relative literal requires keep
  "script imports project modules".
- F7: Runner config inside `package.json` (`jest`, `mocha`, `ava`, `vitest`, `nyc`, `c8`,
  `babel`, `eslintConfig`), existing `jest.config.*`/`vitest.config.*`/`.mocharc.*` (JSON,
  YAML, JS), and `jest --config=X` / `--config X`.
- DECIDED CHANGE: `acceptance_integrity` is `traced` / `untraced` everywhere (result.json,
  receipt, audit list/show); factual delivery message with `kept fixed (restored to their
  start content before each check):`, no `protected`/`verified` words, no big WARNING,
  short tag `— inputs not fully traced [...]` (<=3 codes + `+N`), concrete `NOTE:` line ONLY
  when delivered attempt changed an unfixed dependency, changed files list (<=10 + `+N more`),
  and common traced cases stay `traced` with no NOTE and no tag.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import stat
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
# F1: .npmrc and JS/TS/package-manager config files
# ============================================================================

@needs_node
def test_f1_npmrc_created_by_agent_ignored_and_not_written_back(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """f1 repro: agent creates .npmrc with script-shell=/bin/true.
    Must NOT be used by the check, must NOT be written back, and must be listed in config_ignored."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "package.json").write_text('{"scripts": {"test": "node verify.js"}}\n', encoding="utf-8")
    (proj / "verify.js").write_text("process.exit(1);\n", encoding="utf-8")
    (proj / "src.js").write_text("module.exports = {};\n", encoding="utf-8")

    agent = _write_agent(
        tmp_path,
        "import pathlib\npathlib.Path('.npmrc').write_text('script-shell=/bin/true\\n')\n",
    )
    rc = _run_cli_do(monkeypatch, proj, agent, attempts=1)
    out = capsys.readouterr().out

    assert rc == adapters_cli.EXIT["reject"], out
    assert not (proj / ".npmrc").exists(), ".npmrc must not be written back"
    rj = _latest_result_json(tmp_path / "vwork")
    assert rj["accepted"] is False
    assert rj["acceptance_integrity"] == "traced"
    assert ".npmrc" in rj["attempts"][0]["config_ignored"]
    assert ".npmrc" in out
    assert "not used for the check and not written back" in out


def test_f1_existing_and_agent_created_rc_and_ts_babel_configs(tmp_path: pathlib.Path):
    """All F1 config-class files: existing ones are kept fixed; agent-created ones are config_ignored."""
    rc_files = [
        ".npmrc",
        ".yarnrc",
        ".yarnrc.yml",
        ".pnpmrc",
        "pnpm-workspace.yaml",
        ".babelrc",
        ".babelrc.json",
        "babel.config.js",
        ".swcrc",
        "tsconfig.json",
        "tsconfig.test.json",
    ]
    proj = tmp_path / "proj_existing"
    proj.mkdir()
    (proj / "app.js").write_text("module.exports = 1;\n", encoding="utf-8")
    for fn in rc_files:
        (proj / fn).write_text("{}\n", encoding="utf-8")

    prot = set(R.find_protected(proj))
    for fn in rc_files:
        assert fn in prot, f"{fn} must be protected by default"
        assert R._is_test_config(fn), f"_is_test_config({fn!r}) must be True"
    assert "app.js" not in prot


# ============================================================================
# F2: make up-to-date semantics
# ============================================================================

@needs_make
def test_f2_make_non_phony_agent_created_target_excluded_and_not_written_back(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """f2 repro: Makefile without .PHONY, agent creates file named `test` (or dir `test/x`).
    Agent-created target file is excluded from check copy & write-back, so check fails."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "Makefile").write_text(f"test:\n\t{sys.executable} check.py\n", encoding="utf-8")
    (proj / "check.py").write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
    (proj / "app.py").write_text("X = 1\n", encoding="utf-8")

    agent = _write_agent(tmp_path, "import pathlib\npathlib.Path('test').write_text('')\n")
    rc = _run_cli_do(monkeypatch, proj, agent, extra_args=["--check", "make test"])
    out = capsys.readouterr().out

    assert rc == adapters_cli.EXIT["reject"], out
    assert not (proj / "test").exists(), "'test' file must not be written back"
    rj = _latest_result_json(tmp_path / "vwork")
    assert rj["accepted"] is False
    assert "test" in rj["attempts"][0]["config_ignored"]
    assert "test" in out
    assert "not used for the check and not written back" in out


@needs_make
def test_f2_make_non_phony_existing_file_or_dir_marks_untraced(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """If a non-.PHONY traced target (goal or prereq) already exists as a file or dir, verdict is untraced."""
    # Case 1: existing file named `test`
    proj1 = tmp_path / "p_file"
    proj1.mkdir()
    (proj1 / "Makefile").write_text(f"test:\n\t{sys.executable} check.py\n", encoding="utf-8")
    (proj1 / "check.py").write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
    (proj1 / "test").write_text("existing\n", encoding="utf-8")

    spec1 = R.detect_acceptance(proj1, check="make test")
    assert spec1.integrity == "untraced"
    assert any(
        "make target 'test' is not .PHONY and a file named test exists" in r
        for r in spec1.integrity_reasons
    ), spec1.integrity_reasons

    # Case 2: existing directory matching a prerequisite `prep` on the traced chain
    proj2 = tmp_path / "p_dir"
    (proj2 / "prep").mkdir(parents=True)
    (proj2 / "prep" / "note.txt").write_text("hi\n", encoding="utf-8")
    (proj2 / "Makefile").write_text(
        f".PHONY: test\ntest: prep\n\t{sys.executable} check.py\nprep:\n\ttrue\n",
        encoding="utf-8",
    )
    (proj2 / "check.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")

    spec2 = R.detect_acceptance(proj2, check="make test")
    assert spec2.integrity == "untraced"
    assert any(
        "make target 'prep' is not .PHONY and a file named prep exists" in r
        for r in spec2.integrity_reasons
    ), spec2.integrity_reasons

    # Case 3: `.PHONY: test` stays traced even if a file named `test` exists
    proj3 = tmp_path / "p_phony"
    proj3.mkdir()
    (proj3 / "Makefile").write_text(f".PHONY: test\ntest:\n\t{sys.executable} check.py\n", encoding="utf-8")
    (proj3 / "check.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    (proj3 / "test").write_text("existing\n", encoding="utf-8")
    spec3 = R.detect_acceptance(proj3, check="make test")
    assert spec3.integrity == "traced", spec3.integrity_reasons


# ============================================================================
# F3: make .DEFAULT_GOAL
# ============================================================================

@needs_make
def test_f3_make_default_goal_honored_and_protects_recipe(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """f3 repro: `.DEFAULT_GOAL := help` makes `make` run `help` -> `./h.sh`.
    h.sh must be kept fixed so editing h.sh is rejected."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "Makefile").write_text(
        ".DEFAULT_GOAL := help\ncheck:\n\t@python3 check.py\nhelp:\n\t@./h.sh\n",
        encoding="utf-8",
    )
    (proj / "check.py").write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
    orig_h = "#!/bin/sh\nexit 1\n"
    h_sh = proj / "h.sh"
    h_sh.write_text(orig_h, encoding="utf-8")
    os.chmod(h_sh, 0o755)

    agent = _write_agent(
        tmp_path,
        "import os, pathlib\np = pathlib.Path('h.sh')\np.write_text('#!/bin/sh\\nexit 0\\n')\nos.chmod(p, 0o755)\n",
    )
    rc = _run_cli_do(monkeypatch, proj, agent, extra_args=["--check", "make"])
    out = capsys.readouterr().out

    assert rc == adapters_cli.EXIT["reject"], out
    assert h_sh.read_text(encoding="utf-8") == orig_h
    rj = _latest_result_json(tmp_path / "vwork")
    assert "h.sh" in rj["protected"]
    assert rj["acceptance_integrity"] == "traced"


def test_f3_make_default_goal_variants_and_unresolvable(tmp_path: pathlib.Path):
    """Honour `=`, `?=`, `:=` for `.DEFAULT_GOAL`; dynamic `.DEFAULT_GOAL` -> untraced."""
    # `=` and `?=`
    p1 = tmp_path / "p1"
    p1.mkdir()
    (p1 / "Makefile").write_text(
        ".PHONY: a b\n.DEFAULT_GOAL = b\n.DEFAULT_GOAL ?= a\na:\n\ttrue\nb:\n\tpython3 ok.py\n",
        encoding="utf-8",
    )
    (p1 / "ok.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    spec1 = R.detect_acceptance(p1, check="make")
    assert spec1.integrity == "traced", spec1.integrity_reasons
    assert "ok.py" in spec1.protected

    # Dynamic/unresolvable `.DEFAULT_GOAL`
    p2 = tmp_path / "p2"
    p2.mkdir()
    (p2 / "Makefile").write_text(
        "TARGET := b\n.DEFAULT_GOAL := $(TARGET)\na:\n\ttrue\nb:\n\ttrue\n",
        encoding="utf-8",
    )
    spec2 = R.detect_acceptance(p2, check="make")
    assert spec2.integrity == "untraced"
    assert any(".DEFAULT_GOAL" in r for r in spec2.integrity_reasons)


# ============================================================================
# F4: unittest discover patterns & empty protected list
# ============================================================================

def test_f4_unittest_discover_pattern_protects_and_ignores_agent_created(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """f4 repro: `python3 -m unittest discover -s . -p '*_check.py'` must keep `foo_check.py` fixed
    and exclude agent-created matching files like `bar_check.py`."""
    proj = tmp_path / "proj"
    proj.mkdir()
    orig_check = (
        "import unittest\n"
        "class T(unittest.TestCase):\n"
        "    def test_math(self):\n"
        "        self.assertEqual(1 + 1, 3)\n"
    )
    (proj / "foo_check.py").write_text(orig_check, encoding="utf-8")
    (proj / "app.py").write_text("X = 1\n", encoding="utf-8")

    agent = _write_agent(
        tmp_path,
        textwrap.dedent("""\
            import pathlib
            pathlib.Path('foo_check.py').write_text(
                'import unittest\\nclass T(unittest.TestCase):\\n    def test_math(self): self.assertEqual(1+1, 2)\\n'
            )
            pathlib.Path('bar_check.py').write_text(
                'import unittest\\nclass T2(unittest.TestCase):\\n    def test_ok(self): pass\\n'
            )
            """),
    )
    rc = _run_cli_do(
        monkeypatch, proj, agent,
        extra_args=["--check", f"{sys.executable} -m unittest discover -s . -p '*_check.py'"],
    )
    out = capsys.readouterr().out

    assert rc == adapters_cli.EXIT["reject"], out
    assert (proj / "foo_check.py").read_text(encoding="utf-8") == orig_check
    assert not (proj / "bar_check.py").exists(), "agent-created matching file must not be written back"
    rj = _latest_result_json(tmp_path / "vwork")
    assert "foo_check.py" in rj["protected"]
    assert "bar_check.py" in rj["attempts"][0]["config_ignored"]
    assert rj["acceptance_integrity"] == "traced"


def test_f4_unittest_discover_subdir_and_positional_args(tmp_path: pathlib.Path):
    """discover with `-s sub -p '*_spec.py' -t .` and positional `discover sub '*_spec.py'`."""
    proj = tmp_path / "proj"
    (proj / "checks").mkdir(parents=True)
    (proj / "checks" / "alpha_spec.py").write_text("import unittest\n", encoding="utf-8")
    (proj / "other_spec.py").write_text("import unittest\n", encoding="utf-8")

    spec1 = R.detect_acceptance(proj, check="python3 -m unittest discover -s checks -p '*_spec.py' -t .")
    assert "checks/alpha_spec.py" in spec1.protected
    assert "other_spec.py" not in spec1.protected
    assert spec1.integrity == "traced"

    spec2 = R.detect_acceptance(proj, check="python3 -m unittest discover checks '*_spec.py'")
    assert "checks/alpha_spec.py" in spec2.protected
    assert spec2.integrity == "traced"


def test_f4_empty_protected_is_never_traced_and_no_contradictory_line(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """A check that executes project code with empty kept-fixed set MUST be untraced,
    and the contradictory 'protected: none — the agent could have edited' line must be gone."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "app.py").write_text("X = 1\n", encoding="utf-8")

    # discover with pattern matching 0 files -> empty protected
    spec = R.detect_acceptance(proj, check=f"{sys.executable} -m unittest discover -s . -p '*_missing.py'")
    assert spec.protected == ()
    assert spec.integrity == "untraced"
    assert spec.integrity_reasons

    # Inline python -c with empty protected
    agent = _write_agent(tmp_path, "import pathlib\npathlib.Path('app.py').write_text('X = 2\\n')\n")
    rc = _run_cli_do(
        monkeypatch, proj, agent,
        extra_args=["--check", f"{sys.executable} -c 'import sys; sys.exit(0)'"],
    )
    out = capsys.readouterr().out
    assert rc == 0, out
    rj = _latest_result_json(tmp_path / "vwork")
    assert rj["protected"] == []
    assert rj["acceptance_integrity"] == "untraced"
    assert "the agent could have edited" not in out
    assert "kept fixed (restored to their start content before each check): none" in out
    assert "— inputs not fully traced" in out


# ============================================================================
# F5: Python script escapes (os.system, subprocess, ctypes, open, pathlib, etc.)
# ============================================================================

def test_f5_py_os_system_untraced_and_note_on_helper_change(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """f5 repro: verify.py uses os.system('sh helper.sh'); agent edits helper.sh.
    Must be untraced (naming os.system) AND print NOTE naming helper.sh."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "verify.py").write_text(
        'import os, sys\nsys.exit(0 if os.system("sh helper.sh") == 0 else 1)\n',
        encoding="utf-8",
    )
    (proj / "helper.sh").write_text("exit 1\n", encoding="utf-8")
    (proj / "app.py").write_text("X = 1\n", encoding="utf-8")

    agent = _write_agent(tmp_path, "import pathlib\npathlib.Path('helper.sh').write_text('exit 0\\n')\n")
    rc = _run_cli_do(monkeypatch, proj, agent, extra_args=["--check", f"{sys.executable} verify.py"])
    out = capsys.readouterr().out

    assert rc == 0, out
    rj = _latest_result_json(tmp_path / "vwork")
    assert rj["acceptance_integrity"] == "untraced"
    assert any("os.system" in r or "system" in r for r in rj["acceptance_integrity_reasons"]), rj["acceptance_integrity_reasons"]
    assert any(d["path"] == "helper.sh" for d in rj["acceptance_dependencies_changed"]), rj["acceptance_dependencies_changed"]
    assert "— inputs not fully traced" in out
    assert "NOTE: the delivered attempt changed files the check reads or runs that were not kept fixed:" in out
    assert "helper.sh" in out


@pytest.mark.parametrize("label,code,expected_substr", [
    ("os_popen", "import os\nos.popen('true').read()\n", "popen"),
    ("os_execv", "import os\nos.execv('/bin/true', ['true'])\n", "execv"),
    ("os_spawnl", "import os\nos.spawnl(os.P_WAIT, '/bin/true', 'true')\n", "spawnl"),
    ("from_os_system", "from os import system\nsystem('true')\n", "system"),
    ("subprocess", "import subprocess\nsubprocess.run(['true'])\n", "subprocess"),
    ("pty", "import pty\npty.spawn(['true'])\n", "pty"),
    ("ctypes", "import ctypes\nctypes.CDLL(None)\n", "ctypes"),
    ("importlib", "import importlib\nimportlib.import_module('sys')\n", "importlib"),
    ("runpy", "import runpy\nrunpy.run_module('sys')\n", "runpy"),
    ("dunder_import", "__import__('sys')\n", "__import__"),
    ("eval", "eval('1+1')\n", "eval"),
    ("exec", "exec('x=1')\n", "exec"),
    ("compile", "compile('x=1', '<x>', 'exec')\n", "compile"),
    ("open_nonconst", "p = 'a' + '.txt'\nopen(p).read()\n", "open"),
    ("open_missing", "open('nonexistent.txt').read()\n", "open"),
    ("pathlib_read_text", "from pathlib import Path\nPath('data.txt').read_text()\n", "read_text"),
    ("pathlib_read_bytes", "import pathlib\npathlib.Path('data.txt').read_bytes()\n", "read_bytes"),
    ("pathlib_open", "import pathlib\npathlib.Path('data.txt').open()\n", "open"),
])
def test_f5_py_file_script_escapes_parametrized(
    tmp_path: pathlib.Path, label: str, code: str, expected_substr: str
):
    proj = tmp_path / label
    proj.mkdir()
    (proj / "verify.py").write_text(code, encoding="utf-8")
    (proj / "data.txt").write_text("ok\n", encoding="utf-8")

    spec = R.detect_acceptance(proj, check="python3 verify.py")
    assert spec.integrity == "untraced", f"{label}: unexpectedly {spec.integrity}"
    assert any(expected_substr in r for r in spec.integrity_reasons), (
        f"{label}: expected {expected_substr!r} in {spec.integrity_reasons}"
    )


def test_f5_py_constant_open_existing_file_is_kept_fixed(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """open('expected.txt') where expected.txt exists -> expected.txt is kept fixed & traced."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "verify.py").write_text(
        "import sys\nwant = open('expected.txt').read().strip()\nsys.exit(0 if want == '42' else 1)\n",
        encoding="utf-8",
    )
    (proj / "expected.txt").write_text("41\n", encoding="utf-8")

    agent = _write_agent(tmp_path, "import pathlib\npathlib.Path('expected.txt').write_text('42\\n')\n")
    rc = _run_cli_do(monkeypatch, proj, agent, extra_args=["--check", f"{sys.executable} verify.py"])
    out = capsys.readouterr().out

    assert rc == adapters_cli.EXIT["reject"], out
    assert (proj / "expected.txt").read_text(encoding="utf-8") == "41\n"
    rj = _latest_result_json(tmp_path / "vwork")
    assert {"verify.py", "expected.txt"} <= set(rj["protected"])
    assert rj["acceptance_integrity"] == "traced"


# ============================================================================
# F6: Node script escapes
# ============================================================================

@needs_node
def test_f6_node_fs_read_untraced(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """f6 repro: node verify.js requires 'fs' and reads 'expected'+'.txt' -> untraced naming fs."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "verify.js").write_text(
        'const fs = require("fs");\n'
        'const want = fs.readFileSync("expected" + ".txt", "utf8").trim();\n'
        'process.exit(want === "42" ? 0 : 1);\n',
        encoding="utf-8",
    )
    (proj / "expected.txt").write_text("41\n", encoding="utf-8")

    agent = _write_agent(tmp_path, "import pathlib\npathlib.Path('expected.txt').write_text('42\\n')\n")
    rc = _run_cli_do(monkeypatch, proj, agent, extra_args=["--check", "node verify.js"])
    out = capsys.readouterr().out

    assert rc == 0, out
    rj = _latest_result_json(tmp_path / "vwork")
    assert rj["acceptance_integrity"] == "untraced"
    assert any("fs" in r for r in rj["acceptance_integrity_reasons"]), rj["acceptance_integrity_reasons"]
    assert "— inputs not fully traced" in out


@pytest.mark.parametrize("label,code,expected_substr", [
    ("req_fs", "const fs = require('fs');\n", "fs"),
    ("req_fs_promises", "const fsp = require('fs/promises');\n", "fs/promises"),
    ("imp_node_fs", "import fs from 'node:fs';\n", "fs"),
    ("req_child_process", "const cp = require('child_process');\n", "child_process"),
    ("req_worker_threads", "const wt = require('worker_threads');\n", "worker_threads"),
    ("req_vm", "const vm = require('vm');\n", "vm"),
    ("dyn_req_var", "const m = 'x'; require(m);\n", "require"),
    ("dyn_req_concat", "require('f' + 's');\n", "require"),
    ("dyn_req_template", "const n = 'fs'; require(`${n}`);\n", "require"),
    ("process_binding", "process.binding('fs');\n", "process.binding"),
    ("eval_call", "eval('1+1');\n", "eval"),
    ("new_function", "new Function('return 1')();\n", "new Function"),
    ("dyn_import_var", "const x = './a.js'; import(x);\n", "import"),
    ("dyn_import_concat", "import('./' + 'a.js');\n", "import"),
    ("rel_require", "const d = require('./dep.js');\n", "script imports project modules"),
])
def test_f6_node_script_escapes_parametrized(
    tmp_path: pathlib.Path, label: str, code: str, expected_substr: str
):
    proj = tmp_path / label
    proj.mkdir()
    (proj / "verify.js").write_text(code, encoding="utf-8")
    (proj / "dep.js").write_text("module.exports = 1;\n", encoding="utf-8")

    spec = R.detect_acceptance(proj, check="node verify.js")
    assert spec.integrity == "untraced", f"{label}: unexpectedly {spec.integrity}"
    assert any(expected_substr in r for r in spec.integrity_reasons), (
        f"{label}: expected {expected_substr!r} in {spec.integrity_reasons}"
    )


# ============================================================================
# F7: Runner config inside package.json, jest/vitest/mocha configs, --config
# ============================================================================

@needs_node
def test_f7_package_json_jest_setupfiles_protected(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """f7 repro: package.json has jest.setupFiles: ['./setup.js'].
    setup.js must be kept fixed, so agent neutering global.expect is rejected."""
    proj = tmp_path / "proj"
    (proj / "node_modules" / ".bin").mkdir(parents=True)
    (proj / "package.json").write_text(
        '{"scripts": {"test": "jest"}, "jest": {"setupFiles": ["./setup.js"]}}\n',
        encoding="utf-8",
    )
    orig_setup = "// jest setup (original)\n"
    (proj / "setup.js").write_text(orig_setup, encoding="utf-8")
    (proj / "sum.js").write_text("module.exports = (a, b) => a - b;\n", encoding="utf-8")
    (proj / "sum.test.js").write_text(
        "const sum = require('./sum.js');\ntest('adds', () => expect(sum(1, 2)).toBe(3));\n",
        encoding="utf-8",
    )
    jest_stub = proj / "node_modules" / ".bin" / "jest"
    jest_stub.write_text(
        "#!/usr/bin/env node\n"
        "const fs = require('fs'), path = require('path');\n"
        "const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));\n"
        "for (const s of (pkg.jest && pkg.jest.setupFiles) || []) require(path.resolve(s));\n"
        "global.test = (n, f) => f();\n"
        "if (!global.expect) global.expect = (a) => ({ toBe(b) { if (a !== b) throw new Error(a + '!=' + b); } });\n"
        "try { require(path.resolve('sum.test.js')); } catch (e) { process.exitCode = 1; }\n",
        encoding="utf-8",
    )
    os.chmod(jest_stub, 0o755)

    agent = _write_agent(
        tmp_path,
        "import pathlib\npathlib.Path('setup.js').write_text('global.expect = () => ({ toBe() {} });\\n')\n",
    )
    rc = _run_cli_do(monkeypatch, proj, agent, attempts=1)
    out = capsys.readouterr().out

    assert rc == adapters_cli.EXIT["reject"], out
    assert (proj / "setup.js").read_text(encoding="utf-8") == orig_setup
    rj = _latest_result_json(tmp_path / "vwork")
    assert {"package.json", "setup.js", "sum.test.js"} <= set(rj["protected"])
    assert rj["acceptance_integrity"] == "traced"


def test_f7_package_json_unresolvable_and_rootdir_and_config_files(tmp_path: pathlib.Path):
    """Test package.json runner keys, <rootDir>, jest.config.js/json, .mocharc.yml, --config."""
    # 1. Unresolvable path in package.json jest.setupFiles -> untraced
    p1 = tmp_path / "p1"
    p1.mkdir()
    (p1 / "package.json").write_text(
        '{"scripts": {"test": "jest"}, "jest": {"setupFiles": ["./missing.js"]}}\n',
        encoding="utf-8",
    )
    s1 = R.detect_acceptance(p1, check="npm test")
    assert s1.integrity == "untraced"

    # 2. <rootDir> with unknown expansion ($1) -> untraced; <rootDir>/setup.js existing -> protected & traced
    p2 = tmp_path / "p2"
    p2.mkdir()
    (p2 / "package.json").write_text(
        '{"scripts": {"test": "jest"}, "jest": {"moduleNameMapper": {"^@/(.*)$": "<rootDir>/src/$1"}}}\n',
        encoding="utf-8",
    )
    s2 = R.detect_acceptance(p2, check="npm test")
    assert s2.integrity == "untraced"

    p2b = tmp_path / "p2b"
    p2b.mkdir()
    (p2b / "setup.js").write_text("// ok\n", encoding="utf-8")
    (p2b / "package.json").write_text(
        '{"scripts": {"test": "jest"}, "jest": {"setupFiles": ["<rootDir>/setup.js"]}}\n',
        encoding="utf-8",
    )
    s2b = R.detect_acceptance(p2b, check="npm test")
    assert "setup.js" in s2b.protected
    assert s2b.integrity == "traced", s2b.integrity_reasons

    # 3. jest.config.js literal path -> protects; non-literal path -> untraced
    p3 = tmp_path / "p3"
    p3.mkdir()
    (p3 / "package.json").write_text('{"scripts": {"test": "jest"}}\n', encoding="utf-8")
    (p3 / "setup.js").write_text("// ok\n", encoding="utf-8")
    (p3 / "jest.config.js").write_text("module.exports = { setupFiles: ['./setup.js'] };\n", encoding="utf-8")
    s3 = R.detect_acceptance(p3, check="jest")
    assert {"jest.config.js", "setup.js"} <= set(s3.protected)
    assert s3.integrity == "traced", s3.integrity_reasons

    p3b = tmp_path / "p3b"
    p3b.mkdir()
    (p3b / "package.json").write_text('{"scripts": {"test": "jest"}}\n', encoding="utf-8")
    (p3b / "setup.js").write_text("// ok\n", encoding="utf-8")
    (p3b / "jest.config.js").write_text(
        "const path = require('path');\nmodule.exports = { setupFiles: [path.resolve(__dirname, 'setup.js')] };\n",
        encoding="utf-8",
    )
    s3b = R.detect_acceptance(p3b, check="jest")
    assert s3b.integrity == "untraced"

    # 4. .mocharc.yml -> protects require file
    p4 = tmp_path / "p4"
    p4.mkdir()
    (p4 / "package.json").write_text('{"scripts": {"test": "mocha"}}\n', encoding="utf-8")
    (p4 / "mocha_setup.js").write_text("// ok\n", encoding="utf-8")
    (p4 / ".mocharc.yml").write_text("require:\n  - ./mocha_setup.js\n", encoding="utf-8")
    s4 = R.detect_acceptance(p4, check="mocha")
    assert {".mocharc.yml", "mocha_setup.js"} <= set(s4.protected)
    assert s4.integrity == "traced", s4.integrity_reasons

    # 5. jest --config=custom.json and jest --config custom.json
    p5 = tmp_path / "p5"
    p5.mkdir()
    (p5 / "package.json").write_text('{"scripts": {"test": "jest"}}\n', encoding="utf-8")
    (p5 / "custom_setup.js").write_text("// ok\n", encoding="utf-8")
    (p5 / "my_jest.json").write_text('{"setupFiles": ["./custom_setup.js"]}\n', encoding="utf-8")
    for cmd in ("jest --config=my_jest.json", "jest --config my_jest.json", "npx jest --config=my_jest.json"):
        s5 = R.detect_acceptance(p5, check=cmd)
        assert {"my_jest.json", "custom_setup.js"} <= set(s5.protected), f"{cmd}: {s5.protected}"
        assert s5.integrity == "traced", f"{cmd}: {s5.integrity_reasons}"


# ============================================================================
# DECIDED CHANGE: traced/untraced, factual delivery message, NOTE, short tags, audit
# ============================================================================

def test_decided_change_message_facts_only_and_changed_files_truncation(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """Delivery message uses `kept fixed (...)`, no `protected`/`verified` words,
    no big WARNING, short untraced tag, and changed files list (<=10, else first 10 + '+N more')."""
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "app.py").write_text("X = 1\n", encoding="utf-8")
    (proj / "check.py").write_text("import sys, app\nsys.exit(0 if app.X == 2 else 1)\n", encoding="utf-8")

    # Agent fixes app.py AND creates 11 extra files (total 12 changed files -> 10 shown + '+2 more')
    agent = _write_agent(
        tmp_path,
        textwrap.dedent("""\
            import pathlib
            pathlib.Path('app.py').write_text('X = 2\\n')
            for i in range(11):
                pathlib.Path(f'extra_{i:02d}.txt').write_text('ok\\n')
            """),
    )
    rc = _run_cli_do(monkeypatch, proj, agent, extra_args=["--check", f"{sys.executable} check.py"])
    out = capsys.readouterr().out
    assert rc == 0, out

    # No "protected" or "verified" words in the delivery summary!
    summary_start = out.index("[vacant] ")
    summary_text = out[summary_start:]
    assert not re.search(r"\bprotected\b", summary_text, re.IGNORECASE), summary_text
    assert not re.search(r"\bverified\b", summary_text, re.IGNORECASE), summary_text
    assert "WARNING: this check runs files" not in summary_text
    assert "kept fixed (restored to their start content before each check): check.py" in summary_text
    assert "— inputs not fully traced [script-imports-project-modules]" in summary_text
    assert "NOTE: the delivered attempt changed files the check reads or runs" not in summary_text
    assert "+2 more" in summary_text

    # Audit list & show display "untraced"
    vh = str(tmp_path / "vhome")
    vw = str(tmp_path / "vwork")
    rj = _latest_result_json(tmp_path / "vwork")
    assert rj["acceptance_integrity"] == "untraced"
    assert AE.main(["list", "--vacant-home", vh, "--work-root", vw]) == 0
    list_out = capsys.readouterr().out
    assert "untraced" in list_out
    rec_id = f"restart:{pathlib.Path(rj['run_dir']).name}"
    assert AE.main(["show", rec_id, "--vacant-home", vh, "--work-root", vw]) == 0
    show_out = capsys.readouterr().out
    assert "untraced" in show_out


def test_decided_change_common_traced_cases_no_note_no_tag(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """Common traced cases must stay `traced`, with no NOTE line and no untraced tag:
    1. auto-detected unittest project
    2. npm with scripts.test: 'jest' and no jest config keys
    3. --check 'make test' with .PHONY: test and understood recipe."""
    # 1. Auto-detected unittest
    p_uni = tmp_path / "uni"
    p_uni.mkdir()
    (p_uni / "calc.py").write_text("def add(a, b): return a - b\n", encoding="utf-8")
    (p_uni / "test_calc.py").write_text(
        "import unittest, calc\nclass T(unittest.TestCase):\n"
        "    def test_a(self): self.assertEqual(calc.add(2, 3), 5)\n",
        encoding="utf-8",
    )
    ag_uni = _write_agent(
        tmp_path,
        "import pathlib\npathlib.Path('calc.py').write_text('def add(a, b): return a + b\\n')\n",
        "ag_uni.py",
    )
    rc = _run_cli_do(monkeypatch, p_uni, ag_uni, vhome=tmp_path / "vh_uni", vwork=tmp_path / "vw_uni")
    out = capsys.readouterr().out
    assert rc == 0, out
    rj = _latest_result_json(tmp_path / "vw_uni")
    assert rj["acceptance_integrity"] == "traced"
    assert rj["acceptance_integrity_reasons"] == []
    assert "— inputs not fully traced" not in out
    assert "NOTE:" not in out
    assert "kept fixed (restored to their start content before each check): test_calc.py" in out

    # Audit shows traced
    assert AE.main(["list", "--vacant-home", str(tmp_path / "vh_uni"), "--work-root", str(tmp_path / "vw_uni")]) == 0
    assert "traced" in capsys.readouterr().out

    # 2. npm with scripts.test: "jest" and no jest config keys
    if shutil.which("npm"):
        p_npm = tmp_path / "npm_jest"
        p_npm.mkdir()
        (p_npm / "package.json").write_text('{"name":"x","scripts":{"test":"jest"}}\n', encoding="utf-8")
        (p_npm / "sum.test.js").write_text("test('ok', () => {});\n", encoding="utf-8")
        spec_npm = R.detect_acceptance(p_npm)
        assert spec_npm.integrity == "traced", spec_npm.integrity_reasons
        assert spec_npm.integrity_reasons == ()

    # 3. --check "make test" with .PHONY: test and understood recipe
    if shutil.which("make"):
        p_mk = tmp_path / "mk_ok"
        p_mk.mkdir()
        (p_mk / "calc.py").write_text("def add(a, b): return a - b\n", encoding="utf-8")
        (p_mk / "test_calc.py").write_text(
            "import unittest, calc\nclass T(unittest.TestCase):\n"
            "    def test_a(self): self.assertEqual(calc.add(2, 3), 5)\n",
            encoding="utf-8",
        )
        (p_mk / "Makefile").write_text(f".PHONY: test\ntest:\n\t{sys.executable} -m unittest\n", encoding="utf-8")
        rc = _run_cli_do(
            monkeypatch, p_mk, ag_uni,
            extra_args=["--check", "make test"],
            vhome=tmp_path / "vh_mk", vwork=tmp_path / "vw_mk",
        )
        out = capsys.readouterr().out
        assert rc == 0, out
        rj_mk = _latest_result_json(tmp_path / "vw_mk")
        assert rj_mk["acceptance_integrity"] == "traced"
        assert "— inputs not fully traced" not in out
        assert "NOTE:" not in out
        assert "kept fixed (restored to their start content before each check):" in out
