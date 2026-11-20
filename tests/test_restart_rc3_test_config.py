"""rc3：測試設定檔和測試檔同等對待（rc2 查證時重現：agent 新增 conftest.py 讓 pytest 全過＝放行卻錯）。"""
import importlib.util
import pathlib
import sys
import textwrap

import pytest

from vacant_network.adapters import cli as adapters_cli
from vacant_network.adapters import restart as RS

needs_pytest = pytest.mark.skipif(importlib.util.find_spec("pytest") is None, reason="pytest not importable")

WRONG = "def add(a, b):\n    return a - b\n"


def _proj(tmp_path, extra=None):
    p = tmp_path / "proj"
    p.mkdir()
    (p / "calc.py").write_text(WRONG)
    (p / "test_calc.py").write_text("from calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n")
    for rel, txt in (extra or {}).items():
        (p / rel).parent.mkdir(parents=True, exist_ok=True)
        (p / rel).write_text(txt)
    return p


def _run(tmp_path, monkeypatch, p, files):
    agent = tmp_path / "agent.py"
    agent.write_text("import pathlib\n" + "".join(
        f"pathlib.Path({rel!r}).parent.mkdir(parents=True, exist_ok=True)\n"
        f"pathlib.Path({rel!r}).write_text({txt!r})\n" for rel, txt in files.items()))
    monkeypatch.setenv("VIRTUAL_ENV", sys.prefix)
    monkeypatch.setenv("VACANT_WORK", str(tmp_path / "work"))
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "home"))
    monkeypatch.chdir(p)
    return adapters_cli.main(["do", "--cmd", f"{sys.executable} {agent} {{prompt}}", "--prompt", "x",
                              "--attempts", "1", "--timeout", "120"])


HOOK = textwrap.dedent("""\
    import pytest
    @pytest.hookimpl(tryfirst=True)
    def pytest_pyfunc_call(pyfuncitem):
        return True
    """)


@needs_pytest
@pytest.mark.parametrize("rel", ["conftest.py"])
def test_new_conftest_hook_does_not_pass_the_check(tmp_path, monkeypatch, capsys, rel):
    p = _proj(tmp_path)
    rc = _run(tmp_path, monkeypatch, p, {rel: HOOK})
    out = capsys.readouterr().out
    assert "python_pytest" in out
    assert rc == adapters_cli.EXIT["reject"], out
    assert not (p / rel).exists(), "agent-added conftest.py must not be written back"
    assert (p / "calc.py").read_text() == WRONG
    assert "added test configuration (conftest.py)" in out


@needs_pytest
def test_modified_existing_conftest_is_restored(tmp_path, monkeypatch, capsys):
    p = _proj(tmp_path, {"conftest.py": "# original conftest\n"})
    rc = _run(tmp_path, monkeypatch, p, {"conftest.py": HOOK})
    out = capsys.readouterr().out
    assert rc == adapters_cli.EXIT["reject"], out
    assert (p / "conftest.py").read_text() == "# original conftest\n"
    assert "conftest.py" in out and "not written back" in out


@needs_pytest
@pytest.mark.parametrize("rel,txt", [
    ("pyproject.toml", '[tool.pytest.ini_options]\npythonpath = ["hack"]\n'),
    ("pytest.ini", "[pytest]\npythonpath = hack\n"),
    ("setup.cfg", "[tool:pytest]\npythonpath = hack\n"),
    ("tox.ini", "[pytest]\npythonpath = hack\n"),
])
def test_new_ini_that_shadows_the_module_does_not_pass(tmp_path, monkeypatch, capsys, rel, txt):
    """ini 的 pythonpath 把 agent 寫的 hack/calc.py 排到前面：原 calc.py 還是錯的，不能判過。"""
    p = _proj(tmp_path)
    rc = _run(tmp_path, monkeypatch, p, {rel: txt, "hack/calc.py": "def add(a, b):\n    return a + b\n"})
    out = capsys.readouterr().out
    assert rc == adapters_cli.EXIT["reject"], out
    assert not (p / rel).exists()
    assert (p / "calc.py").read_text() == WRONG


@needs_pytest
def test_honest_fix_with_new_conftest_still_passes(tmp_path, monkeypatch, capsys):
    """誠實修好 calc.py，順便加了 conftest.py：照樣通過；conftest.py 不寫回、訊息列出。"""
    p = _proj(tmp_path)
    rc = _run(tmp_path, monkeypatch, p, {"calc.py": "def add(a, b):\n    return a + b\n",
                                         "conftest.py": "# fixtures\n"})
    out = capsys.readouterr().out
    assert rc == 0, out
    assert (p / "calc.py").read_text() == "def add(a, b):\n    return a + b\n"
    assert not (p / "conftest.py").exists()


def test_test_config_classification():
    for rel in ["conftest.py", "a/b/conftest.py", "pytest.ini", "tox.ini", "setup.cfg", "pyproject.toml",
                "jest.config.js", "jest.config.ts", "vitest.config.mts", "vite.config.js", ".mocharc.yml",
                "babel.config.js", ".babelrc", "karma.conf.js", "jest.setup.js"]:
        assert RS._is_test_config(rel), rel
    for rel in ["calc.py", "src/app.js", "package-lock.json", "README.md"]:
        assert not RS._is_test_config(rel), rel


def test_existing_configs_are_protected_by_default(tmp_path):
    for rel in ["conftest.py", "pyproject.toml", "jest.config.js", "src/x.py"]:
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x")
    prot = RS.find_protected(tmp_path)
    assert {"conftest.py", "pyproject.toml", "jest.config.js"} <= set(prot)
    assert "src/x.py" not in prot


def test_audit_task_column_and_strict_exit(tmp_path, monkeypatch, capsys):
    from vacant_network import audit_export as AE
    p = _proj(tmp_path)
    rc = _run(tmp_path, monkeypatch, p, {"calc.py": "def add(a, b):\n    return a + b\n"})
    assert rc == 0
    capsys.readouterr()
    home, work = str(tmp_path / "home"), str(tmp_path / "work")
    recs = AE.collect_all(vacant_home=home, work_root=work)
    assert len(recs) == 1 and str(recs[0]["task"]).startswith("request:")
    assert AE.main(["list", "--vacant-home", home, "--work-root", work, "--strict"]) == 0
    chain = next((tmp_path / "home").rglob("chain.ndjson"))
    import re
    txt = chain.read_text()
    new = re.sub(r'"accepted":\s*true', '"accepted": false', txt)
    assert new != txt
    chain.write_text(new)
    assert AE.main(["list", "--vacant-home", home, "--work-root", work]) == 0
    assert AE.main(["list", "--vacant-home", home, "--work-root", work, "--strict"]) == 3
    assert AE.main(["export", "--vacant-home", home, "--work-root", work, "--strict"]) == 3
