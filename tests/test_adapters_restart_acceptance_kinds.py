"""零設定重開模式（`vacant_network/adapters/restart.py`）多驗收種類測試（W1，0 次模型呼叫）。

涵蓋：
- pytest 風格（裸 `def test_*` 與非 `TestCase` 類別），含 pytest 存在與缺席（標準庫退回）兩條路徑；
- 混合 `unittest.TestCase`＋裸函式；
- 明確 `--check "<shell command>"`（含 CLI、重試、受保護測試檔還原、逾時與行程群組清理）；
- `package.json`／`Cargo.toml`／`go.mod` 自動偵測（以 PATH 模擬工具有／無）與優先順序；
- 收到 0 個測試（`no_tests_collected`）與執行器不可用（`runner_unavailable`）不重試、照實交回並明講原因；
- pytest 路徑維持 C2／C3 隔離性質；既有 unittest 路徑行為不變。
"""
from __future__ import annotations

import json
import os
import pathlib
import signal
import stat
import sys
import textwrap

import pytest

from vacant_network.adapters import cli
from vacant_network.adapters import restart as R
from vacant_network.adapters.run import Launch


def _multi_build(tmp_path: pathlib.Path, bodies: list[str]):
    """每次嘗試依序跑 bodies[0], bodies[1], ...（超過長度就重複最後一段），0 次模型呼叫。"""
    state = tmp_path / "stub_state.json"
    scripts: list[str] = []
    for i, body in enumerate(bodies):
        s = tmp_path / f"stub_step_{i}.py"
        s.write_text(body, encoding="utf-8")
        scripts.append(str(s))
    dispatcher = tmp_path / "stub_dispatch.py"
    dispatcher.write_text(textwrap.dedent(f"""\
        import json, pathlib, runpy
        st = pathlib.Path({str(state)!r})
        n = json.loads(st.read_text())["n"] + 1 if st.exists() else 1
        st.write_text(json.dumps({{"n": n}}))
        scripts = {scripts!r}
        runpy.run_path(scripts[min(n, len(scripts)) - 1], run_name="__main__")
        """), encoding="utf-8")

    def build(prompt: str, ws: pathlib.Path) -> Launch:
        return Launch(argv=[sys.executable, str(dispatcher)], env={})

    return build, state


def _calls(state: pathlib.Path) -> int:
    return json.loads(state.read_text(encoding="utf-8"))["n"] if state.exists() else 0


def _make_fake_tool(bin_dir: pathlib.Path, name: str, script_body: str) -> pathlib.Path:
    bin_dir.mkdir(parents=True, exist_ok=True)
    tool = bin_dir / name
    tool.write_text(f"#!{sys.executable}\n{script_body}", encoding="utf-8")
    os.chmod(tool, stat.S_IRWXU)
    return tool


@pytest.fixture(autouse=True)
def _isolated_work(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_WORK", str(tmp_path / "work"))


# ---------------------------------------------------------------------------
# 1. 重現案例：pytest 風格 calc.py / test_calc.py（有 pytest 與無 pytest 退回）
# ---------------------------------------------------------------------------

def test_reproduced_calc_pytest_direct_and_attempt1(tmp_path):
    proj = tmp_path / "calc_proj"
    proj.mkdir()
    (proj / "calc.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
    (proj / "test_calc.py").write_text(
        "from calc import add\ndef test_add(): assert add(1, 2) == 3\n",
        encoding="utf-8",
    )

    originals = {rel: (proj / rel).read_bytes() for rel in R.find_tests(proj)}
    direct = R.acceptance(originals, proj)
    assert direct["accept"] is True
    assert direct["run"] == 1
    assert direct["passed"] == 1
    assert direct["status"] == "ok"
    assert direct["kind"] == "python_pytest"

    build, state = _multi_build(tmp_path, ["pass\n"])
    res = R.run(proj, build, "verify calc", attempt_timeout_s=20, budget_s=120)
    assert _calls(state) == 1
    assert res["accepted"] is True
    assert res["delivered_attempt"] == 1
    assert res["acceptance"]["kind"] == "python_pytest"
    assert res["acceptance"]["command"]
    assert res["protected"] == ["test_calc.py"]
    assert res["acceptance"]["protected"] == ["test_calc.py"]

    saved = json.loads((pathlib.Path(res["run_dir"]) / "result.json").read_text(encoding="utf-8"))
    assert saved["acceptance"]["kind"] == "python_pytest"
    assert saved["protected"] == ["test_calc.py"]

    msg = R.summary(res)
    assert "python_pytest" in msg
    assert res["acceptance"]["command"] in msg
    assert "test_calc.py" in msg


def test_calc_pytest_stdlib_fallback_when_pytest_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "_pytest_available", lambda *a, **kw: False)

    proj = tmp_path / "calc_proj"
    proj.mkdir()
    (proj / "calc.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
    (proj / "test_calc.py").write_text(
        "from calc import add\ndef test_add(): assert add(1, 2) == 3\n",
        encoding="utf-8",
    )

    originals = {rel: (proj / rel).read_bytes() for rel in R.find_tests(proj)}
    direct = R.acceptance(originals, proj)
    assert direct["accept"] is True
    assert direct["run"] == 1
    assert direct["passed"] == 1
    assert direct["status"] == "ok"
    assert direct["kind"] == "python_bare"

    build, state = _multi_build(tmp_path, ["pass\n"])
    res = R.run(proj, build, "verify calc", attempt_timeout_s=20, budget_s=120)
    assert _calls(state) == 1
    assert res["accepted"] is True
    assert res["delivered_attempt"] == 1
    assert res["acceptance"]["kind"] == "python_bare"
    assert res["protected"] == ["test_calc.py"]
    msg = R.summary(res)
    assert "python_bare" in msg
    assert "test_calc.py" in msg


# ---------------------------------------------------------------------------
# 2. pytest 風格專案有真 bug ⇒ 驗收不通過並重試（有 pytest 與無 pytest 皆同）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("pytest_present,expected_kind", [
    (True, "python_pytest"),
    (False, "python_bare"),
])
def test_pytest_style_bug_fails_and_retries(tmp_path, monkeypatch, pytest_present, expected_kind):
    if not pytest_present:
        monkeypatch.setattr(R, "_pytest_available", lambda *a, **kw: False)

    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "calc.py").write_text("def add(a, b): return 0\n", encoding="utf-8")
    (proj / "test_calc.py").write_text(
        "from calc import add\n"
        "def test_one(): assert add(1, 2) == 3\n"
        "def test_two(): assert add(10, 5) == 15\n",
        encoding="utf-8",
    )

    build, state = _multi_build(tmp_path, [
        "import pathlib\npathlib.Path('calc.py').write_text('def add(a, b): return a - b\\n')\n",
        "import pathlib\npathlib.Path('calc.py').write_text('def add(a, b): return a + b\\n')\n",
    ])
    res = R.run(proj, build, "fix add", attempt_timeout_s=20, budget_s=120)
    assert _calls(state) == 2
    assert res["acceptance"]["kind"] == expected_kind
    assert [a["accept"] for a in res["attempts"]] == [False, True]
    assert res["attempts"][0]["passed"] == 0 and res["attempts"][0]["run"] == 2
    assert res["attempts"][1]["passed"] == 2 and res["attempts"][1]["run"] == 2
    assert res["accepted"] is True
    assert res["delivered_attempt"] == 2
    assert (proj / "calc.py").read_text(encoding="utf-8") == "def add(a, b): return a + b\n"


@pytest.mark.parametrize("pytest_present", [True, False])
def test_pytest_candidate_syntax_error_retries_and_picks_best(tmp_path, monkeypatch, pytest_present):
    if not pytest_present:
        monkeypatch.setattr(R, "_pytest_available", lambda *a, **kw: False)

    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "calc.py").write_text("def add(a, b): return 0\n", encoding="utf-8")
    (proj / "test_calc.py").write_text(
        "from calc import add\n"
        "def test_one(): assert add(1, 2) == 3\n"
        "def test_two(): assert add(10, 5) == 15\n",
        encoding="utf-8",
    )

    build, state = _multi_build(tmp_path, [
        # Attempt 1: 候選碼語法錯誤（由 agent 導致，必須算失敗並重試）
        "import pathlib\npathlib.Path('calc.py').write_text('def add(:\\n')\n",
        # Attempt 2: 過 1/2
        "import pathlib\npathlib.Path('calc.py').write_text('def add(a, b): return 3 if a == 1 else 0\\n')\n",
        # Attempt 3: 過 0/2
        "import pathlib\npathlib.Path('calc.py').write_text('def add(a, b): return -1\\n')\n",
    ])
    res = R.run(proj, build, "fix add", max_attempts=3, attempt_timeout_s=20, budget_s=120)
    assert _calls(state) == 3
    assert res["accepted"] is False
    assert res["attempts"][0]["status"] == "load_error"
    assert res["attempts"][0]["accept"] is False
    assert res["attempts"][1]["passed"] == 1
    assert res["attempts"][2]["passed"] == 0
    assert res["delivered_attempt"] == 2
    assert "return 3 if a == 1 else 0" in (proj / "calc.py").read_text(encoding="utf-8")


@pytest.mark.parametrize("pytest_present,expected_kind", [
    (True, "python_pytest"),
    (False, "python_bare"),
])
def test_pytest_non_testcase_class(tmp_path, monkeypatch, pytest_present, expected_kind):
    if not pytest_present:
        monkeypatch.setattr(R, "_pytest_available", lambda *a, **kw: False)

    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "calc.py").write_text("def add(a, b): return 0\n", encoding="utf-8")
    (proj / "test_calc.py").write_text(textwrap.dedent("""\
        from calc import add

        class TestCalc:
            def test_add(self):
                assert add(2, 3) == 5
        """), encoding="utf-8")

    build, state = _multi_build(tmp_path, [
        "import pathlib\npathlib.Path('calc.py').write_text('def add(a, b): return 99\\n')\n",
        "import pathlib\npathlib.Path('calc.py').write_text('def add(a, b): return a + b\\n')\n",
    ])
    res = R.run(proj, build, "fix add", attempt_timeout_s=20, budget_s=120)
    assert _calls(state) == 2
    assert res["acceptance"]["kind"] == expected_kind
    assert res["accepted"] is True
    assert res["delivered_attempt"] == 2
    assert res["attempts"][1]["run"] == 1 and res["attempts"][1]["passed"] == 1


# ---------------------------------------------------------------------------
# 3. 混合 unittest.TestCase ＋ 裸 def test_* 函式
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("pytest_present,expected_kind", [
    (True, "python_pytest"),
    (False, "python_bare"),
])
def test_mixed_unittest_and_bare_functions(tmp_path, monkeypatch, pytest_present, expected_kind):
    if not pytest_present:
        monkeypatch.setattr(R, "_pytest_available", lambda *a, **kw: False)

    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "calc.py").write_text("def add(a, b): return 0\ndef mul(a, b): return 0\n", encoding="utf-8")
    (proj / "test_mixed.py").write_text(textwrap.dedent("""\
        import unittest
        from calc import add, mul

        class TestUnit(unittest.TestCase):
            def test_add(self):
                self.assertEqual(add(1, 2), 3)

        def test_mul():
            assert mul(3, 4) == 12
        """), encoding="utf-8")

    build, state = _multi_build(tmp_path, [
        # Attempt 1: 只有 unittest 過、裸函式沒過 ⇒ 1/2，必須重試
        "import pathlib\npathlib.Path('calc.py').write_text('def add(a, b): return a + b\\ndef mul(a, b): return 0\\n')\n",
        # Attempt 2: 兩邊都過 ⇒ 2/2
        "import pathlib\npathlib.Path('calc.py').write_text('def add(a, b): return a + b\\ndef mul(a, b): return a * b\\n')\n",
    ])
    res = R.run(proj, build, "fix calc", attempt_timeout_s=20, budget_s=120)
    assert _calls(state) == 2
    assert res["acceptance"]["kind"] == expected_kind
    assert res["attempts"][0]["accept"] is False
    assert res["attempts"][0]["run"] == 2 and res["attempts"][0]["passed"] == 1
    assert res["attempts"][1]["accept"] is True
    assert res["attempts"][1]["run"] == 2 and res["attempts"][1]["passed"] == 2
    assert res["accepted"] is True
    assert res["delivered_attempt"] == 2


# ---------------------------------------------------------------------------
# 4. --check "<shell command>"（CLI、重試與同分交最後一次、受保護測試檔還原、逾時清理）
# ---------------------------------------------------------------------------

def test_check_cli_accepts_on_attempt1(tmp_path, monkeypatch, capsys):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "app.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.chdir(proj)

    state = tmp_path / "cli_state.json"
    agent = tmp_path / "agent.py"
    agent.write_text(textwrap.dedent(f"""\
        import json, pathlib
        st = pathlib.Path({str(state)!r})
        n = json.loads(st.read_text())["n"] + 1 if st.exists() else 1
        st.write_text(json.dumps({{"n": n}}))
        pathlib.Path("app.py").write_text("x = 2\\n")
        """), encoding="utf-8")

    check_cmd = f"{sys.executable} -c 'import sys; sys.exit(0)'"
    rc = cli.main([
        "do",
        "--cmd", f"{sys.executable} {agent} {{prompt}}",
        "--prompt", "update app",
        "--check", check_cmd,
        "--attempt-timeout", "20",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert _calls(state) == 1
    assert (proj / "app.py").read_text(encoding="utf-8") == "x = 2\n"
    assert "acceptance: check" in out
    assert check_cmd in out
    assert "protected (restored before check): none" in out


def test_check_failing_retries_and_delivers_latest_on_all_fail(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "out.txt").write_text("init\n", encoding="utf-8")

    build, state = _multi_build(tmp_path, [
        "import pathlib\npathlib.Path('out.txt').write_text('v1\\n')\n",
        "import pathlib\npathlib.Path('out.txt').write_text('v2\\n')\n",
        "import pathlib\npathlib.Path('out.txt').write_text('v3\\n')\n",
    ])
    check_cmd = f"{sys.executable} -c 'import sys; sys.exit(1)'"
    res = R.run(proj, build, "try it", max_attempts=3, check=check_cmd,
                attempt_timeout_s=20, budget_s=120)
    assert _calls(state) == 3
    assert res["accepted"] is False
    assert res["acceptance"]["kind"] == "check"
    assert res["acceptance"]["command"] == check_cmd
    assert all(a["passed"] is None and a["run"] is None for a in res["attempts"])
    # 僅看退出碼時 passed 為 None，同分規則交最後一次
    assert res["delivered_attempt"] == 3
    assert (proj / "out.txt").read_text(encoding="utf-8") == "v3\n"

    # 若第 2 次讓 --check 退出 0，應在第 2 次就停
    (tmp_path / "run2_stubs").mkdir(exist_ok=True)
    build2, state2 = _multi_build(tmp_path / "run2_stubs", [
        "import pathlib\npathlib.Path('out.txt').write_text('bad\\n')\n",
        "import pathlib\npathlib.Path('out.txt').write_text('good\\n')\n",
        "import pathlib\npathlib.Path('out.txt').write_text('never\\n')\n",
    ])
    check_good = f"{sys.executable} -c \"import pathlib, sys; sys.exit(0 if pathlib.Path('out.txt').read_text().strip() == 'good' else 1)\""
    res2 = R.run(proj, build2, "make good", max_attempts=3, check=check_good,
                 attempt_timeout_s=20, budget_s=120)
    assert _calls(state2) == 2
    assert res2["accepted"] is True
    assert res2["delivered_attempt"] == 2
    assert (proj / "out.txt").read_text(encoding="utf-8") == "good\n"


def test_check_restores_protected_test_files_before_running(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    orig_test = "from calc import add\nassert add(1, 2) == 3\n"
    (proj / "calc.py").write_text("def add(a, b): return 0\n", encoding="utf-8")
    (proj / "test_calc.py").write_text(orig_test, encoding="utf-8")

    build, state = _multi_build(tmp_path, [
        # Attempt 1: 竄改測試檔讓它永遠通過，但 calc.py 還是錯的
        "import pathlib\npathlib.Path('test_calc.py').write_text('assert True\\n')\n"
        "pathlib.Path('calc.py').write_text('def add(a, b): return 0\\n')\n",
        # Attempt 2: 真的修好 calc.py
        "import pathlib\npathlib.Path('calc.py').write_text('def add(a, b): return a + b\\n')\n",
    ])
    check_cmd = f"{sys.executable} test_calc.py"
    res = R.run(proj, build, "fix add", max_attempts=3, check=check_cmd,
                attempt_timeout_s=20, budget_s=120)
    assert _calls(state) == 2
    assert res["attempts"][0]["accept"] is False
    assert res["attempts"][0]["tests_tampered"] == ["test_calc.py"]
    assert res["attempts"][1]["accept"] is True
    assert res["accepted"] is True
    assert res["delivered_attempt"] == 2
    assert res["protected"] == ["test_calc.py"]
    assert (proj / "test_calc.py").read_text(encoding="utf-8") == orig_test
    assert (proj / "calc.py").read_text(encoding="utf-8") == "def add(a, b): return a + b\n"
    msg = R.summary(res)
    assert "acceptance: check" in msg
    assert check_cmd in msg
    assert "test_calc.py" in msg
    assert "edited test files" in msg


def test_check_timeout_kills_process_group_and_respects_budget(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "a.txt").write_text("hi\n", encoding="utf-8")
    pid_file = tmp_path / "ext_grandchild.pid"
    helper = tmp_path / "spawn_sleep.py"
    helper.write_text(textwrap.dedent(f"""\
        import pathlib, subprocess, sys, time
        p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        pathlib.Path({str(pid_file)!r}).write_text(str(p.pid))
        time.sleep(60)
        """), encoding="utf-8")

    build, _ = _multi_build(tmp_path, ["pass\n"])
    try:
        res = R.run(proj, build, "check timeout", max_attempts=1,
                    check=f"{sys.executable} {helper}",
                    attempt_timeout_s=2.0, budget_s=2.0, min_attempt_s=0.5)
        assert res["accepted"] is False
        assert res["attempts"][0]["status"] == "timeout"
        assert res["total_wall_s"] <= 3.5
        assert pid_file.exists()
        pid = int(pid_file.read_text(encoding="utf-8"))
        alive = True
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            alive = False
        assert not alive, f"grandchild pid {pid} leaked alive after --check timeout"
    finally:
        if pid_file.exists():
            try:
                os.kill(int(pid_file.read_text(encoding="utf-8")), signal.SIGKILL)
            except (OSError, ValueError):
                pass


# ---------------------------------------------------------------------------
# 5. package.json / Cargo.toml / go.mod 偵測與 PATH 模擬（有／無工具）
# ---------------------------------------------------------------------------

def test_detect_npm_cargo_go_present_and_absent_via_path(tmp_path, monkeypatch):
    bin_dir = tmp_path / "fakebin"
    _make_fake_tool(bin_dir, "npm", textwrap.dedent("""\
        import pathlib, sys
        assert sys.argv[1:] == ["test"], sys.argv
        sys.exit(0 if pathlib.Path("ok.flag").exists() else 1)
        """))
    _make_fake_tool(bin_dir, "cargo", textwrap.dedent("""\
        import pathlib, sys
        assert sys.argv[1:] == ["test"], sys.argv
        sys.exit(0 if pathlib.Path("ok.flag").exists() else 1)
        """))
    _make_fake_tool(bin_dir, "go", textwrap.dedent("""\
        import pathlib, sys
        assert sys.argv[1:] == ["test", "./..."], sys.argv
        sys.exit(0 if pathlib.Path("ok.flag").exists() else 1)
        """))

    # --- package.json (npm) ---
    js_proj = tmp_path / "js_proj"
    js_proj.mkdir()
    (js_proj / "package.json").write_text(json.dumps({"scripts": {"test": "node t.js"}}), encoding="utf-8")

    monkeypatch.setenv("PATH", str(bin_dir))
    spec = R.detect_acceptance(js_proj)
    assert spec.kind == "npm" and spec.command == "npm test" and spec.argv == ("npm", "test")

    (tmp_path / "js_stubs").mkdir(exist_ok=True)
    build, state = _multi_build(tmp_path / "js_stubs", [
        "pass\n",
        "import pathlib\npathlib.Path('ok.flag').write_text('1')\n",
    ])
    res = R.run(js_proj, build, "fix js", attempt_timeout_s=20, budget_s=120)
    assert _calls(state) == 2
    assert res["accepted"] is True
    assert res["acceptance"]["kind"] == "npm"
    assert res["acceptance"]["command"] == "npm test"
    assert "npm test" in R.summary(res)

    # npm 不在 PATH 上 ⇒ 視為不可用，不重試
    empty_bin = tmp_path / "emptybin"
    empty_bin.mkdir()
    monkeypatch.setenv("PATH", str(empty_bin))
    spec_missing = R.detect_acceptance(js_proj)
    assert spec_missing.kind == "none"
    assert spec_missing.reason and "npm" in spec_missing.reason
    (tmp_path / "js_miss").mkdir()
    build_m, state_m = _multi_build(tmp_path / "js_miss", ["pass\n", "pass\n"])
    res_m = R.run(js_proj, build_m, "fix js", attempt_timeout_s=20, budget_s=120)
    assert _calls(state_m) == 1
    assert res_m["accepted"] is None
    assert res_m["attempts"][0]["status"] == "runner_unavailable"
    assert "npm" in R.summary(res_m)

    # package.json 沒有 test script 或只有 npm init 預設佔位腳本 ⇒ 忽略
    no_test_js = tmp_path / "no_test_js"
    no_test_js.mkdir()
    (no_test_js / "package.json").write_text(
        json.dumps({"scripts": {"test": 'echo "Error: no test specified" && exit 1'}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("PATH", str(bin_dir))
    assert R.detect_acceptance(no_test_js).kind == "none"

    # --- Cargo.toml (cargo) ---
    rs_proj = tmp_path / "rs_proj"
    rs_proj.mkdir()
    (rs_proj / "Cargo.toml").write_text('[package]\nname = "demo"\n', encoding="utf-8")
    monkeypatch.setenv("PATH", str(bin_dir))
    spec_rs = R.detect_acceptance(rs_proj)
    assert spec_rs.kind == "cargo" and spec_rs.command == "cargo test" and spec_rs.argv == ("cargo", "test")

    (tmp_path / "rs_stubs").mkdir()
    build_rs, state_rs = _multi_build(tmp_path / "rs_stubs", [
        "import pathlib\npathlib.Path('ok.flag').write_text('1')\n",
    ])
    res_rs = R.run(rs_proj, build_rs, "fix rs", attempt_timeout_s=20, budget_s=120)
    assert _calls(state_rs) == 1 and res_rs["accepted"] is True
    assert res_rs["acceptance"]["kind"] == "cargo" and res_rs["acceptance"]["command"] == "cargo test"

    monkeypatch.setenv("PATH", str(empty_bin))
    assert R.detect_acceptance(rs_proj).kind == "none"

    # --- go.mod (go) ---
    go_proj = tmp_path / "go_proj"
    go_proj.mkdir()
    (go_proj / "go.mod").write_text("module example.com/demo\n\ngo 1.22\n", encoding="utf-8")
    monkeypatch.setenv("PATH", str(bin_dir))
    spec_go = R.detect_acceptance(go_proj)
    assert spec_go.kind == "go" and spec_go.command == "go test ./..." and spec_go.argv == ("go", "test", "./...")

    (tmp_path / "go_stubs").mkdir()
    build_go, state_go = _multi_build(tmp_path / "go_stubs", [
        "import pathlib\npathlib.Path('ok.flag').write_text('1')\n",
    ])
    res_go = R.run(go_proj, build_go, "fix go", attempt_timeout_s=20, budget_s=120)
    assert _calls(state_go) == 1 and res_go["accepted"] is True
    assert res_go["acceptance"]["kind"] == "go" and res_go["acceptance"]["command"] == "go test ./..."

    monkeypatch.setenv("PATH", str(empty_bin))
    assert R.detect_acceptance(go_proj).kind == "none"

    # --- 優先順序：--check ＞ Python ＞ npm ＞ cargo ＞ go；缺工具時往下順延 ---
    combo = tmp_path / "combo"
    combo.mkdir()
    (combo / "package.json").write_text(json.dumps({"scripts": {"test": "node t.js"}}), encoding="utf-8")
    (combo / "Cargo.toml").write_text('[package]\nname = "c"\n', encoding="utf-8")
    (combo / "go.mod").write_text("module c\n", encoding="utf-8")

    # 只有 go 在 PATH 上 ⇒ 略過缺席的 npm／cargo，選 go
    go_only_bin = tmp_path / "go_only_bin"
    _make_fake_tool(go_only_bin, "go", "import sys; sys.exit(0)\n")
    monkeypatch.setenv("PATH", str(go_only_bin))
    assert R.detect_acceptance(combo).kind == "go"

    # 三個都在 PATH 上 ⇒ 依序選 npm；加上 Python 測試檔 ⇒ 選 Python；給 --check ⇒ 選 check
    monkeypatch.setenv("PATH", str(bin_dir))
    assert R.detect_acceptance(combo).kind == "npm"
    (combo / "test_a.py").write_text("def test_x(): assert True\n", encoding="utf-8")
    assert R.detect_acceptance(combo).kind == "python_pytest"
    assert R.detect_acceptance(combo, check="true").kind == "check"


# ---------------------------------------------------------------------------
# 6. 0 個測試被收集（no_tests_collected）＆ 執行器無法啟動（runner_unavailable）
# ---------------------------------------------------------------------------

def test_zero_tests_collected_runs_once_no_restart_honest_message(tmp_path):
    proj = tmp_path / "empty_tests"
    proj.mkdir()
    (proj / "app.py").write_text("x = 1\n", encoding="utf-8")
    (proj / "test_empty.py").write_text("# no test cases here\ndef helper():\n    return 42\n", encoding="utf-8")

    originals = {rel: (proj / rel).read_bytes() for rel in R.find_tests(proj)}
    direct = R.acceptance(originals, proj)
    assert direct["status"] == "no_tests_collected"
    assert direct["accept"] is None
    assert direct["run"] == 0

    build, state = _multi_build(tmp_path, [
        "import pathlib\npathlib.Path('app.py').write_text('x = 2\\n')\n",
        "import pathlib\npathlib.Path('app.py').write_text('x = 3\\n')\n",
    ])
    res = R.run(proj, build, "edit app", max_attempts=3, attempt_timeout_s=20, budget_s=120)
    assert _calls(state) == 1                         # 絕不重試浪費 3 次
    assert len(res["attempts"]) == 1
    assert res["accepted"] is None
    assert res["attempts"][0]["status"] == "no_tests_collected"
    assert res["delivered_attempt"] == 1
    assert (proj / "app.py").read_text(encoding="utf-8") == "x = 2\n"

    msg = R.summary(res)
    assert "0 tests were collected" in msg
    assert "nothing could be checked" in msg
    assert "test_empty.py" in msg


def test_pytest_zero_tests_collected_returns_no_tests_collected(tmp_path):
    proj = tmp_path / "pytest_zero"
    proj.mkdir()
    (proj / "test_empty.py").write_text("# nothing collected\n", encoding="utf-8")
    originals = {"test_empty.py": (proj / "test_empty.py").read_bytes()}
    spec = R.AcceptanceSpec(kind="python_pytest", command="pytest", protected=("test_empty.py",))
    direct = R.acceptance(originals, proj, spec=spec)
    assert direct["status"] == "no_tests_collected"
    assert direct["accept"] is None
    assert direct["run"] == 0


def test_runner_unavailable_original_test_syntax_error_and_missing_pytest(tmp_path, monkeypatch):
    # Case A: 原受保護測試檔本身有語法錯誤（非 agent 造成）⇒ 跑一次、不重試
    proj_syn = tmp_path / "proj_syn"
    proj_syn.mkdir()
    (proj_syn / "app.py").write_text("x = 1\n", encoding="utf-8")
    (proj_syn / "test_broken.py").write_text("def test_bad(:\n    pass\n", encoding="utf-8")
    (tmp_path / "syn_stubs").mkdir()
    build_s, state_s = _multi_build(tmp_path / "syn_stubs", [
        "import pathlib\npathlib.Path('app.py').write_text('x = 2\\n')\n",
        "pass\n",
    ])
    res_s = R.run(proj_syn, build_s, "edit app", max_attempts=3, attempt_timeout_s=20, budget_s=120)
    assert _calls(state_s) == 1
    assert res_s["accepted"] is None
    assert res_s["attempts"][0]["status"] == "runner_unavailable"
    assert "nothing could be checked" in R.summary(res_s)

    # Case B: 測試函式需要 pytest fixture 且 pytest 缺席 ⇒ 跑一次、不重試
    monkeypatch.setattr(R, "_pytest_available", lambda *a, **kw: False)

    proj_fix = tmp_path / "proj_fix"
    proj_fix.mkdir()
    (proj_fix / "test_fix.py").write_text("def test_with_fixture(tmp_path):\n    assert tmp_path\n", encoding="utf-8")
    (tmp_path / "fix_stubs").mkdir()
    build_f, state_f = _multi_build(tmp_path / "fix_stubs", ["pass\n", "pass\n"])
    res_f = R.run(proj_fix, build_f, "do it", max_attempts=3, attempt_timeout_s=20, budget_s=120)
    assert _calls(state_f) == 1
    assert res_f["accepted"] is None
    assert res_f["attempts"][0]["status"] == "runner_unavailable"
    assert "fixtures" in (res_f["attempts"][0]["first_problem"] or "")

    # Case C: 測試檔 `import pytest` 且測試直譯器確實沒有裝 pytest ⇒ 跑一次、不重試
    sys_py = "/usr/bin/python3"
    if pathlib.Path(sys_py).is_file():
        monkeypatch.undo()
        monkeypatch.setenv("VACANT_WORK", str(tmp_path / "work"))
        if not R._pytest_available(sys_py):
            monkeypatch.setattr(R.sys, "executable", sys_py)
            proj_imp = tmp_path / "proj_imp"
            proj_imp.mkdir()
            (proj_imp / "test_imp.py").write_text("import pytest\ndef test_a():\n    assert True\n", encoding="utf-8")
            (tmp_path / "imp_stubs").mkdir()
            build_i, state_i = _multi_build(tmp_path / "imp_stubs", ["pass\n", "pass\n"])
            res_i = R.run(proj_imp, build_i, "do it", max_attempts=3, attempt_timeout_s=20, budget_s=120)
            assert _calls(state_i) == 1
            assert res_i["accepted"] is None
            assert res_i["attempts"][0]["status"] == "runner_unavailable"
            assert "nothing could be checked" in R.summary(res_i)


# ---------------------------------------------------------------------------
# 7. pytest 路徑安全回歸（C2 套件遮蔽、C3 模組遮蔽）＆ 既有 unittest 路徑不變
# ---------------------------------------------------------------------------

def test_pytest_path_blocks_c2_package_shadow_and_c3_module_shadow(tmp_path):
    proj = tmp_path / "sec_proj"
    proj.mkdir()
    (proj / "calc.py").write_text("def add(a, b): return 0\n", encoding="utf-8")
    (proj / "test_calc.py").write_text(
        "from calc import add\ndef test_add(): assert add(1, 2) == 3\n",
        encoding="utf-8",
    )

    # C2: 嘗試用 test_calc/__init__.py 遮蔽原 test_calc.py，同時寫入假的 pytest.py（C3）
    build, _ = _multi_build(tmp_path, [textwrap.dedent("""\
        import pathlib
        pathlib.Path("calc.py").write_text("def add(a, b): return -1\\n")
        pathlib.Path("test_calc").mkdir()
        pathlib.Path("test_calc/__init__.py").write_text("def test_fake(): assert True\\n")
        pathlib.Path("pytest.py").write_text("def main(*a, **kw): return 0\\n")
        """)])
    res = R.run(proj, build, "fix add", max_attempts=1, attempt_timeout_s=20, budget_s=120)
    assert res["acceptance"]["kind"] == "python_pytest"
    assert res["accepted"] is False


def test_unittest_path_selected_and_exact_counts_preserved(tmp_path):
    proj = tmp_path / "ut_proj"
    proj.mkdir()
    (proj / "sol.py").write_text("def f(x): return x\n", encoding="utf-8")
    (proj / "sol_test.py").write_text(textwrap.dedent("""\
        import unittest
        from sol import f
        class T(unittest.TestCase):
            def test_one(self):
                self.assertEqual(f(1), 2)
            def test_two(self):
                self.assertEqual(f(41), 42)
        """), encoding="utf-8")

    spec = R.detect_acceptance(proj)
    assert spec.kind == "python_unittest"
    assert spec.protected == ("sol_test.py",)

    build, _ = _multi_build(tmp_path, [
        "import pathlib\npathlib.Path('sol.py').write_text('def f(x): return 2 if x == 1 else 0\\n')\n",
        "import pathlib\npathlib.Path('sol.py').write_text('def f(x): return x + 1\\n')\n",
    ])
    res = R.run(proj, build, "fix f", attempt_timeout_s=20, budget_s=120)
    assert res["acceptance"]["kind"] == "python_unittest"
    assert res["attempts"][0]["run"] == 2 and res["attempts"][0]["passed"] == 1
    assert res["attempts"][1]["run"] == 2 and res["attempts"][1]["passed"] == 2
    assert res["accepted"] is True
    assert res["delivered_attempt"] == 2
    msg = R.summary(res)
    assert "python_unittest" in msg
    assert "sol_test.py" in msg
    assert "confirm1" not in msg and "redo1" not in msg
