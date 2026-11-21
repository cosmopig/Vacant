"""RC2 Defect 2 測試：專案直譯器解析、acceptance-only node_modules 與基線預檢（0 次模型呼叫）。

涵蓋：
1. 直譯器解析優先順序：$VIRTUAL_ENV/bin/python > <project>/.venv/bin/python > <project>/venv/bin/python > PATH > sys.executable。
2. 專案自有 .venv 裝有本地套件（離線快速建立真 venv＋site-packages 本地模組）：
   - 未啟用 VIRTUAL_ENV 時自動從原專案 .venv 解析（不複製 .venv 進 ws／snap）；
   - 啟用 VIRTUAL_ENV 重現審查案例（原專案已通過、假 agent 不做事 ⇒ 基線 PASS 註記、第 1 次 PASS、不白燒嘗試）；
   - 直譯器路徑記於 result、result.json、簽章收據與交付訊息；保留 -B 不產生 __pycache__。
3. pipx 情境：Vacant 自己的 sys.executable 沒有 pytest，但專案 .venv 有 pytest ⇒ 仍選 python_pytest 並用專案直譯器通過。
4. 基線預檢（BASELINE）：
   - collection load_error（缺依賴 ImportError）⇒ 0 次 agent 嘗試即停、CLI 非零退出碼、訊息明講
     "acceptance cannot run in this environment: <reason>" 並附指令與直譯器；
   - --check 指令不存在（exit 127）⇒ 0 次 agent 嘗試即停、CLI 非零退出碼；
   - 基線 PASS 時仍照政策跑 agent 並在交付訊息明講基線已通過。
5. npm 專案測試依賴 node_modules（若缺 node/npm 則 skip）：
   - node_modules 不複製進 ws／snap，agent 無法透過 symlink 改寫原專案 node_modules；
   - 驗收階段可正常 require('tiny-math') 並通過。
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import stat
import sys
import textwrap
import venv

import pytest

from vacant_network.adapters import cli as adapters_cli
from vacant_network.adapters import restart as R
from vacant_network.adapters.run import Launch


def _has_node_and_npm() -> bool:
    return bool(shutil.which("node") and shutil.which("npm"))


def _make_venv_with_module(venv_dir: pathlib.Path, mod_name: str, mod_src: str, *,
                           extra_site: pathlib.Path | None = None) -> pathlib.Path:
    """快速離線建一個最小真 venv（不裝 pip），並放入本地模組（與選用 .pth 指向額外 site-packages）。"""
    venv.EnvBuilder(with_pip=False, symlinks=True).create(str(venv_dir))
    py = venv_dir / "bin" / "python"
    site_dirs = list(venv_dir.glob("lib/python*/site-packages"))
    assert site_dirs, f"no site-packages in {venv_dir}"
    site = site_dirs[0]
    (site / f"{mod_name}.py").write_text(mod_src, encoding="utf-8")
    if extra_site is not None:
        (site / "_extra_site.pth").write_text(str(extra_site) + "\n", encoding="utf-8")
    return py


def _current_site_packages() -> pathlib.Path:
    import pytest as _pt
    return pathlib.Path(_pt.__file__).resolve().parent.parent


def _counting_build(tmp_path: pathlib.Path, body: str = "pass\n", *, name: str = "agent"):
    state = tmp_path / f"{name}_state.json"
    script = tmp_path / f"{name}.py"
    script.write_text(textwrap.dedent(f"""\
        import json, pathlib
        st = pathlib.Path({str(state)!r})
        n = json.loads(st.read_text())["n"] + 1 if st.exists() else 1
        st.write_text(json.dumps({{"n": n}}))
        """) + body, encoding="utf-8")

    def build(prompt: str, ws: pathlib.Path) -> Launch:
        return Launch(argv=[sys.executable, str(script)], env={})

    return build, state


def _calls(state: pathlib.Path) -> int:
    return json.loads(state.read_text(encoding="utf-8"))["n"] if state.exists() else 0


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    monkeypatch.setenv("VACANT_WORK", str(tmp_path / "vw"))
    monkeypatch.setenv("VACANT_HOOK_NO_GC", "1")


# ---------------------------------------------------------------------------
# 1. Interpreter resolution order
# ---------------------------------------------------------------------------

def test_resolve_python_order(tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    proj.mkdir()

    def _mk_py(p: pathlib.Path) -> pathlib.Path:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"#!/bin/sh\nexec {sys.executable} \"$@\"\n", encoding="utf-8")
        os.chmod(p, stat.S_IRWXU)
        return p

    env_venv = tmp_path / "active_venv"
    py_env = _mk_py(env_venv / "bin" / "python")
    py_dotvenv = _mk_py(proj / ".venv" / "bin" / "python")
    py_venv = _mk_py(proj / "venv" / "bin" / "python")
    path_bin = tmp_path / "path_bin"
    py_path = _mk_py(path_bin / "python3")

    # 1. $VIRTUAL_ENV/bin/python 最高優先
    monkeypatch.setenv("VIRTUAL_ENV", str(env_venv))
    monkeypatch.setenv("PATH", str(path_bin))
    assert R.resolve_python(proj) == str(py_env)

    # 2. 無 VIRTUAL_ENV ⇒ <project>/.venv/bin/python
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    assert R.resolve_python(proj) == str(py_dotvenv)

    # 3. 無 .venv ⇒ <project>/venv/bin/python
    shutil.rmtree(proj / ".venv")
    assert R.resolve_python(proj) == str(py_venv)

    # 4. 無 venv ⇒ PATH 上的 python3
    shutil.rmtree(proj / "venv")
    assert R.resolve_python(proj) == str(py_path)

    # 5. PATH 無 python3／python ⇒ sys.executable
    empty_bin = tmp_path / "empty_bin"
    empty_bin.mkdir()
    monkeypatch.setenv("PATH", str(empty_bin))
    assert R.resolve_python(proj) == sys.executable


# ---------------------------------------------------------------------------
# 2. Project .venv with dependency (unactivated & activated VIRTUAL_ENV repro)
# ---------------------------------------------------------------------------

def test_project_dot_venv_dependency_without_activation_and_not_copied(tmp_path, monkeypatch):
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    proj = tmp_path / "dep_proj"
    proj.mkdir()
    venv_py = _make_venv_with_module(
        proj / ".venv",
        "tinydep_rc2",
        "MAGIC = 42\n",
        extra_site=_current_site_packages(),
    )
    (proj / "app.py").write_text("import tinydep_rc2\ndef val(): return 0\n", encoding="utf-8")
    (proj / "test_app.py").write_text(
        "import tinydep_rc2\nfrom app import val\n"
        "def test_val(): assert val() == tinydep_rc2.MAGIC\n",
        encoding="utf-8",
    )

    build, state = _counting_build(
        tmp_path,
        "import pathlib\npathlib.Path('app.py').write_text('import tinydep_rc2\\ndef val(): return tinydep_rc2.MAGIC\\n')\n",
    )
    res = R.run(proj, build, "return tinydep_rc2.MAGIC", max_attempts=2, attempt_timeout_s=20, budget_s=120)

    assert _calls(state) == 1
    assert res["accepted"] is True
    assert res["acceptance"]["kind"] == "python_pytest"
    assert res["interpreter"] == str(venv_py)
    assert res["acceptance"]["interpreter"] == str(venv_py)
    assert res["baseline"]["status"] == "ok"
    assert res["baseline"]["accept"] is False
    assert res["baseline"]["passed"] == 0 and res["baseline"]["run"] == 1
    # .venv 絕沒有被複製進工作區副本或快照
    att1 = pathlib.Path(res["run_dir"]) / "attempt_1"
    assert not (att1 / "w" / ".venv").exists()
    assert not (next(att1.glob("snap-*")) / ".venv").exists()
    # -B 保留：專案與驗收後不產生 __pycache__
    assert not (proj / "__pycache__").exists()

    # result.json、簽章收據與交付訊息皆記下實際直譯器
    saved = json.loads((pathlib.Path(res["run_dir"]) / "result.json").read_text(encoding="utf-8"))
    assert saved["interpreter"] == str(venv_py)
    assert saved["acceptance"]["interpreter"] == str(venv_py)

    ok, why, receipts = R.verify_receipts(proj, state_root=tmp_path / "vh")
    assert ok, why
    assert receipts[0]["acceptance"]["interpreter"] == str(venv_py)
    assert receipts[0]["baseline"]["status"] == "ok"

    msg = R.summary(res)
    assert str(venv_py) in msg
    assert "interpreter:" in msg


def test_activated_virtual_env_already_passing_repro(tmp_path, monkeypatch):
    """審查重現案例：專案自有 venv 已啟用（VIRTUAL_ENV 設定、bin 在 PATH 最前），專案原本就會過，假 agent 不做事。"""
    proj = tmp_path / "repro_proj"
    proj.mkdir()
    venv_dir = tmp_path / "external_venv"
    venv_py = _make_venv_with_module(
        venv_dir,
        "ext_dep_rc2",
        "ANSWER = 99\n",
        extra_site=_current_site_packages(),
    )
    (proj / "app.py").write_text("import ext_dep_rc2\ndef answer(): return ext_dep_rc2.ANSWER\n", encoding="utf-8")
    (proj / "test_app.py").write_text(
        "import ext_dep_rc2\nfrom app import answer\n"
        "def test_answer(): assert answer() == ext_dep_rc2.ANSWER\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("VIRTUAL_ENV", str(venv_dir))
    monkeypatch.setenv("PATH", f"{venv_dir / 'bin'}{os.pathsep}/usr/bin:/bin")

    build, state = _counting_build(tmp_path, "pass\n")
    res = R.run(proj, build, "no-op", max_attempts=3, attempt_timeout_s=20, budget_s=120)

    # 基線已過、第 1 次嘗試即過（不浪費 3 次），且交付訊息明講基線已通過
    assert _calls(state) == 1
    assert res["accepted"] is True
    assert res["baseline"]["accept"] is True
    assert res["baseline"]["passed"] == 1 and res["baseline"]["run"] == 1
    assert res["interpreter"] == str(venv_py)
    msg = R.summary(res)
    assert "already passing before the agent ran" in msg
    assert str(venv_py) in msg


# ---------------------------------------------------------------------------
# 3. pipx-like case: Vacant's sys.executable lacks pytest, project's .venv has it
# ---------------------------------------------------------------------------

def test_pipx_like_vacant_lacks_pytest_but_project_venv_has_pytest(tmp_path, monkeypatch):
    sys_py = "/usr/bin/python3"
    if not pathlib.Path(sys_py).is_file() or R._pytest_available(sys_py):
        pytest.skip("requires a system python without pytest to simulate pipx interpreter")

    proj = tmp_path / "pipx_proj"
    proj.mkdir()
    # 專案 .venv 內有 pytest（透過 .pth 指向目前測試環境的 site-packages）＋本地套件
    venv_py = _make_venv_with_module(
        proj / ".venv",
        "proj_pkg_rc2",
        "VALUE = 7\n",
        extra_site=_current_site_packages(),
    )
    (proj / "calc.py").write_text("import proj_pkg_rc2\ndef get(): return proj_pkg_rc2.VALUE\n", encoding="utf-8")
    (proj / "test_calc.py").write_text(
        "import pytest\nfrom calc import get\n"
        "@pytest.mark.parametrize('want', [7])\n"
        "def test_get(want): assert get() == want\n",
        encoding="utf-8",
    )

    # 模擬 pipx：Vacant 自己的 sys.executable 沒有 pytest，且無 VIRTUAL_ENV
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setattr(R.sys, "executable", sys_py)

    build, state = _counting_build(tmp_path, "pass\n")
    res = R.run(proj, build, "check", max_attempts=2, attempt_timeout_s=20, budget_s=120)

    assert _calls(state) == 1
    assert res["acceptance"]["kind"] == "python_pytest"
    assert res["interpreter"] == str(venv_py)
    assert res["accepted"] is True
    assert res["attempts"][0]["passed"] == 1 and res["attempts"][0]["run"] == 1


# ---------------------------------------------------------------------------
# 4. BASELINE environment errors stop with 0 agent attempts & nonzero CLI exit
# ---------------------------------------------------------------------------

def test_baseline_load_error_stops_with_zero_attempts_and_nonzero_cli_exit(tmp_path, monkeypatch, capsys):
    proj = tmp_path / "broken_env_proj"
    proj.mkdir()
    (proj / "app.py").write_text("x = 1\n", encoding="utf-8")
    # 宣告過的相依沒裝在直譯器裡＝環境問題（沒宣告的缺模組多半是 agent 要寫的，見下一個測試）
    (proj / "requirements.txt").write_text("definitely-missing-dep-rc2-999>=1.0\n", encoding="utf-8")
    (proj / "test_app.py").write_text(
        "import definitely_missing_dep_rc2_999\n"
        "def test_ok(): assert True\n",
        encoding="utf-8",
    )

    state = tmp_path / "cli_state.json"
    agent = tmp_path / "agent.py"
    agent.write_text(textwrap.dedent(f"""\
        import json, pathlib
        pathlib.Path({str(state)!r}).write_text(json.dumps({{"n": 1}}))
        pathlib.Path("app.py").write_text("x = 999\\n")
        """), encoding="utf-8")

    # 測試直譯器本身能跑（不一定要 pytest，用 unittest 亦可；確保 collection ImportError ⇒ load_error）
    monkeypatch.setenv("VIRTUAL_ENV", sys.prefix) if sys.prefix != sys.base_prefix else None
    monkeypatch.chdir(proj)
    rc = adapters_cli.main([
        "do",
        "--cmd", f"{sys.executable} {agent} {{prompt}}",
        "--prompt", "fix app",
        "--attempts", "3",
        "--attempt-timeout", "20",
    ])
    out = capsys.readouterr().out

    assert rc != 0
    assert not state.exists(), "agent MUST NOT run when baseline has load_error"
    assert (proj / "app.py").read_text(encoding="utf-8") == "x = 1\n"
    assert "acceptance cannot run in this environment:" in out
    assert "definitely_missing_dep_rc2_999" in out
    assert "interpreter:" in out
    assert "acceptance:" in out


@pytest.mark.parametrize("style", ["unittest", "pytest"])
def test_baseline_missing_module_the_agent_must_write_does_not_stop(tmp_path, monkeypatch, capsys, style):
    """回歸（rc2 審查時重現）：測試 import 了還沒寫的 m.py，基線是 load_error，但那是正常起點，agent 必須照常跑。"""
    proj = tmp_path / f"newmod_{style}"
    proj.mkdir()
    if style == "unittest":
        test_src = ("import unittest\nfrom m import f\n"
                    "class T(unittest.TestCase):\n    def test_f(self):\n        self.assertEqual(f(), 2)\n")
    else:
        test_src = "from m import f\ndef test_f():\n    assert f() == 2\n"
    (proj / "test_m.py").write_text(test_src, encoding="utf-8")
    agent = tmp_path / "agent.py"
    agent.write_text('import pathlib\npathlib.Path("m.py").write_text("def f():\\n    return 2\\n")\n',
                     encoding="utf-8")
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.chdir(proj)
    rc = adapters_cli.main([
        "do",
        "--cmd", f"{sys.executable} {agent} {{prompt}}",
        "--prompt", "write m.py",
        "--attempts", "3",
        "--attempt-timeout", "20",
    ])
    out = capsys.readouterr().out
    assert "cannot run in this environment" not in out
    assert rc == 0, out
    assert (proj / "m.py").read_text(encoding="utf-8") == "def f():\n    return 2\n"


def test_declared_dependency_parsing(tmp_path):
    from vacant_network.adapters.restart import _declared_dependency, _missing_module_name
    (tmp_path / "requirements-dev.txt").write_text("# c\n-r base.txt\nPyYAML==6.0  # yaml\nfoo_bar[x]>=1\n")
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["requests>=2", "attrs"]\n')
    assert _declared_dependency(tmp_path, "pyyaml")
    assert _declared_dependency(tmp_path, "foo_bar")
    assert _declared_dependency(tmp_path, "requests")
    assert _declared_dependency(tmp_path, "attrs")
    assert not _declared_dependency(tmp_path, "m")
    assert _missing_module_name("x\nModuleNotFoundError: No module named 'a.b'\n") == "a.b"
    assert _missing_module_name("ImportError: cannot import name 'f' from 'm'") is None


def test_baseline_check_command_not_found_stops_with_zero_attempts(tmp_path, monkeypatch, capsys):
    proj = tmp_path / "missing_cmd_proj"
    proj.mkdir()
    (proj / "app.py").write_text("x = 1\n", encoding="utf-8")

    state = tmp_path / "cmd_state.json"
    agent = tmp_path / "agent.py"
    agent.write_text(f"import pathlib; pathlib.Path({str(state)!r}).write_text('ran')\n", encoding="utf-8")

    monkeypatch.chdir(proj)
    rc = adapters_cli.main([
        "do",
        "--cmd", f"{sys.executable} {agent} {{prompt}}",
        "--prompt", "fix app",
        "--check", "definitely_not_a_real_command_rc2_xyz",
        "--attempts", "3",
        "--attempt-timeout", "20",
    ])
    out = capsys.readouterr().out

    assert rc != 0
    assert not state.exists(), "agent MUST NOT run when --check command is not found (exit 127)"
    assert "acceptance cannot run in this environment:" in out
    assert "definitely_not_a_real_command_rc2_xyz" in out


# ---------------------------------------------------------------------------
# 5. npm project with node_modules dependency (acceptance-only, not copied)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _has_node_and_npm(), reason="node/npm not installed")
def test_npm_project_uses_node_modules_via_symlink_without_copying(tmp_path):
    proj = tmp_path / "nm_proj"
    proj.mkdir()
    pkg = json.dumps({"name": "nm-demo", "version": "1.0.0", "scripts": {"test": "node m.test.js"}}, indent=2) + "\n"
    (proj / "package.json").write_text(pkg, encoding="utf-8")
    (proj / "m.js").write_text("const tm = require('tiny-math'); exports.val = () => tm.add(1, 0);\n", encoding="utf-8")
    (proj / "m.test.js").write_text(textwrap.dedent("""\
        const assert = require("assert");
        const tm = require("tiny-math");
        const m = require("./m.js");
        assert.strictEqual(tm.add(2, 3), 5);
        assert.strictEqual(m.val(), 5);
        """), encoding="utf-8")

    nm_mod = proj / "node_modules" / "tiny-math"
    nm_mod.mkdir(parents=True)
    orig_dep = "exports.add = (a, b) => a + b;\n"
    (nm_mod / "index.js").write_text(orig_dep, encoding="utf-8")

    # 假 agent：確認 ws 裡看得到 node_modules（指向原專案的 symlink，agent 才能自己跑測試），並修好 m.js
    marker = tmp_path / "agent_saw_nm.txt"
    build, state = _counting_build(tmp_path, textwrap.dedent(f"""\
        import pathlib
        nm = pathlib.Path("node_modules")
        pathlib.Path({str(marker)!r}).write_text(f"{{nm.is_symlink()}} {{(nm / 'tiny-math' / 'index.js').exists()}}")
        pathlib.Path("m.js").write_text("const tm = require('tiny-math'); exports.val = () => tm.add(2, 3);\\n")
        """))

    res = R.run(proj, build, "make m.val() return 5", max_attempts=2, attempt_timeout_s=20, budget_s=120)

    assert _calls(state) == 1
    assert marker.read_text(encoding="utf-8") == "True True", "agent ws must reach node_modules via a symlink (not a copy)"
    assert res["baseline"]["status"] == "failed" and res["baseline"]["accept"] is False
    assert res["accepted"] is True
    assert res["delivered_attempt"] == 1
    # 原專案的 node_modules 完好未被寫穿
    assert (nm_mod / "index.js").read_text(encoding="utf-8") == orig_dep
    assert "tm.add(2, 3)" in (proj / "m.js").read_text(encoding="utf-8")
    # 快照中沒有 node_modules
    att1 = pathlib.Path(res["run_dir"]) / "attempt_1"
    assert not (next(att1.glob("snap-*")) / "node_modules").exists()
