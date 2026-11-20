"""RC2 Defect 1 對抗性測試：跨生態系保護測試檔與驗收定義（鎖定 manifest／--protect／誠實警語）。

涵蓋審查回報的兩個重現案例與跨生態系等價攻擊（0 次模型呼叫，全用假 agent 腳本）：
- (a) npm 專案：假 agent 把 package.json 的 scripts.test 改成 "true" ⇒ 驗收必 FAIL，原 package.json 不被寫回；
- (b) npm 專案：假 agent 把 m.test.js 改成 process.exit(0) ⇒ 驗收必 FAIL，原 m.test.js 不被寫回；
- 通用保護規則：*.test.*、*.spec.*、__tests__/**、tests/**、test/**、*_test.go、package.json／Cargo.toml／go.mod；
- Go 等價攻擊：假 agent 改 *_test.go（與 go.mod）⇒ 驗收必 FAIL，原檔不動（含常跑假 go 與真 go skipif）；
- --check 與可重複 --protect PATH/GLOB（含 CLI）：
  - 無任何受保護檔時，交付訊息明講 agent 可能修改驗收所執行的內容；
  - 有 --protect 時，竄改驗收腳本仍 FAIL，原腳本還原且不寫回，交付訊息列出被改的受保護檔；
  - 跳出專案目錄的 --protect（如 ../outside）直接拒絕。
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import stat
import sys
import textwrap

import pytest

from vacant_network.adapters import cli as adapters_cli
from vacant_network.adapters import restart as R
from vacant_network.adapters.run import Launch


def _has_node_and_npm() -> bool:
    return bool(shutil.which("node") and shutil.which("npm"))


def _multi_build(tmp_path: pathlib.Path, bodies: list[str], *, prefix: str = "stub"):
    state = tmp_path / f"{prefix}_state.json"
    scripts: list[str] = []
    for i, body in enumerate(bodies):
        s = tmp_path / f"{prefix}_step_{i}.py"
        s.write_text(body, encoding="utf-8")
        scripts.append(str(s))
    dispatcher = tmp_path / f"{prefix}_dispatch.py"
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


def _make_fake_tool(bin_dir: pathlib.Path, name: str, script_body: str) -> pathlib.Path:
    bin_dir.mkdir(parents=True, exist_ok=True)
    tool = bin_dir / name
    tool.write_text(f"#!{sys.executable}\n{script_body}", encoding="utf-8")
    os.chmod(tool, stat.S_IRWXU)
    return tool


def _make_npm_repro_proj(root: pathlib.Path) -> tuple[pathlib.Path, str, str]:
    proj = root / "npm_proj"
    proj.mkdir()
    pkg = json.dumps({"name": "repro", "version": "1.0.0", "scripts": {"test": "node m.test.js"}}, indent=2) + "\n"
    test_js = textwrap.dedent("""\
        const assert = require("assert");
        const m = require("./m.js");
        assert.strictEqual(m.v, 2, `expected v===2, got ${m.v}`);
        """)
    (proj / "package.json").write_text(pkg, encoding="utf-8")
    (proj / "m.test.js").write_text(test_js, encoding="utf-8")
    (proj / "m.js").write_text("exports.v = 1;\n", encoding="utf-8")
    return proj, pkg, test_js


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    monkeypatch.setenv("VACANT_WORK", str(tmp_path / "vw"))
    monkeypatch.setenv("VACANT_HOOK_NO_GC", "1")


# ---------------------------------------------------------------------------
# 1. Reviewer Repro (a) & (b): real npm + node
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _has_node_and_npm(), reason="node/npm not installed")
def test_defect1a_npm_agent_rewrites_package_json_test_script_to_true_must_fail(tmp_path):
    proj, orig_pkg, orig_test = _make_npm_repro_proj(tmp_path)

    # Fake agent replaces package.json scripts.test with "true", leaving m.js at v=1
    build, _ = _multi_build(tmp_path, [textwrap.dedent("""\
        import json, pathlib
        p = pathlib.Path("package.json")
        data = json.loads(p.read_text(encoding="utf-8"))
        data["scripts"]["test"] = "true"
        p.write_text(json.dumps(data, indent=2) + "\\n", encoding="utf-8")
        """)])
    res = R.run(proj, build, "make m.js export v=2", max_attempts=2, attempt_timeout_s=20, budget_s=120)

    assert res["acceptance"]["kind"] == "npm"
    assert res["acceptance"]["pinned_script"] == "node m.test.js"
    assert set(res["protected"]) >= {"m.test.js", "package.json"}
    assert res["accepted"] is False
    assert all(a["accept"] is False for a in res["attempts"])
    assert all("package.json" in a["tests_tampered"] for a in res["attempts"])
    # User's project files MUST remain untouched
    assert (proj / "package.json").read_text(encoding="utf-8") == orig_pkg
    assert (proj / "m.test.js").read_text(encoding="utf-8") == orig_test
    assert (proj / "m.js").read_text(encoding="utf-8") == "exports.v = 1;\n"

    msg = R.summary(res)
    assert "package.json" in msg
    assert "not written back" in msg


@pytest.mark.skipif(not _has_node_and_npm(), reason="node/npm not installed")
def test_defect1b_npm_agent_rewrites_m_test_js_to_exit_zero_must_fail(tmp_path):
    proj, orig_pkg, orig_test = _make_npm_repro_proj(tmp_path)

    # Fake agent replaces m.test.js with process.exit(0), leaving m.js at v=1
    build, _ = _multi_build(tmp_path, [
        "import pathlib\npathlib.Path('m.test.js').write_text('process.exit(0);\\n', encoding='utf-8')\n",
    ])
    res = R.run(proj, build, "make m.js export v=2", max_attempts=2, attempt_timeout_s=20, budget_s=120)

    assert res["acceptance"]["kind"] == "npm"
    assert res["accepted"] is False
    assert all(a["accept"] is False for a in res["attempts"])
    assert all("m.test.js" in a["tests_tampered"] for a in res["attempts"])
    # User's project m.test.js MUST remain untouched
    assert (proj / "m.test.js").read_text(encoding="utf-8") == orig_test
    assert (proj / "package.json").read_text(encoding="utf-8") == orig_pkg
    assert (proj / "m.js").read_text(encoding="utf-8") == "exports.v = 1;\n"

    msg = R.summary(res)
    assert "m.test.js" in msg
    assert "not written back" in msg


@pytest.mark.skipif(not _has_node_and_npm(), reason="node/npm not installed")
def test_defect1_npm_real_fix_passes_while_tampered_package_json_not_written_back(tmp_path):
    proj, orig_pkg, orig_test = _make_npm_repro_proj(tmp_path)

    build, _ = _multi_build(tmp_path, [
        # Attempt 1: cheats by editing both package.json and m.test.js, m.js still wrong
        textwrap.dedent("""\
            import json, pathlib
            pathlib.Path("package.json").write_text(json.dumps({"scripts": {"test": "true"}}) + "\\n")
            pathlib.Path("m.test.js").write_text("process.exit(0);\\n")
            """),
        # Attempt 2: actually fixes m.js, while also sneaking an edit to package.json
        textwrap.dedent("""\
            import json, pathlib
            pathlib.Path("m.js").write_text("exports.v = 2;\\n")
            pathlib.Path("package.json").write_text(json.dumps({"scripts": {"test": "true"}}) + "\\n")
            """),
    ])
    res = R.run(proj, build, "make m.js export v=2", max_attempts=3, attempt_timeout_s=20, budget_s=120)

    assert res["attempts"][0]["accept"] is False
    assert set(res["attempts"][0]["tests_tampered"]) == {"m.test.js", "package.json"}
    assert res["attempts"][1]["accept"] is True
    assert res["accepted"] is True
    assert res["delivered_attempt"] == 2
    # Real code fix is delivered, protected files stay original
    assert (proj / "m.js").read_text(encoding="utf-8") == "exports.v = 2;\n"
    assert (proj / "package.json").read_text(encoding="utf-8") == orig_pkg
    assert (proj / "m.test.js").read_text(encoding="utf-8") == orig_test


# ---------------------------------------------------------------------------
# 2. Universal ecosystem protected patterns (*.spec.*, __tests__/**, tests/**, test/**)
# ---------------------------------------------------------------------------

def test_universal_ecosystem_test_patterns_protected_across_kinds(tmp_path, monkeypatch):
    proj = tmp_path / "uni_proj"
    proj.mkdir()
    (proj / "package.json").write_text(json.dumps({"scripts": {"test": "fake-runner"}}), encoding="utf-8")
    (proj / "src").mkdir()
    (proj / "src" / "app.js").write_text("exports.ok = false;\n", encoding="utf-8")
    (proj / "src" / "app.spec.ts").write_text("spec\n", encoding="utf-8")
    (proj / "src" / "app.test.js").write_text("test\n", encoding="utf-8")
    (proj / "__tests__").mkdir()
    (proj / "__tests__" / "helper.js").write_text("helper\n", encoding="utf-8")
    (proj / "tests" / "e2e").mkdir(parents=True)
    (proj / "tests" / "e2e" / "suite.js").write_text("e2e\n", encoding="utf-8")
    (proj / "test").mkdir()
    (proj / "test" / "unit.js").write_text("unit\n", encoding="utf-8")

    bin_dir = tmp_path / "bin"
    _make_fake_tool(bin_dir, "npm", "import sys; sys.exit(0)\n")
    monkeypatch.setenv("PATH", str(bin_dir))

    spec = R.detect_acceptance(proj)
    assert spec.kind == "npm"
    assert set(spec.protected) == {
        "package.json",
        "src/app.spec.ts",
        "src/app.test.js",
        "__tests__/helper.js",
        "tests/e2e/suite.js",
        "test/unit.js",
    }
    assert "src/app.js" not in spec.protected


# ---------------------------------------------------------------------------
# 3. Go *_test.go & go.mod protection (fake-go always runs + real-go if installed)
# ---------------------------------------------------------------------------

def test_defect1_go_test_file_and_go_mod_tampering_rejected_fake_go(tmp_path, monkeypatch):
    proj = tmp_path / "go_proj"
    proj.mkdir()
    orig_mod = "module example.com/demo\n\ngo 1.22\n"
    orig_test = textwrap.dedent("""\
        package demo
        import "testing"
        func TestAdd(t *testing.T) {
            if Add(1, 2) != 3 { t.Fatal("wrong") }
        }
        """)
    (proj / "go.mod").write_text(orig_mod, encoding="utf-8")
    (proj / "math.go").write_text("package demo\nfunc Add(a, b int) int { return 0 }\n", encoding="utf-8")
    (proj / "math_test.go").write_text(orig_test, encoding="utf-8")

    # Fake `go` that checks the restored math_test.go & math.go contents
    bin_dir = tmp_path / "gobin"
    _make_fake_tool(bin_dir, "go", textwrap.dedent("""\
        import pathlib, sys
        assert sys.argv[1:] == ["test", "./..."]
        t_src = pathlib.Path("math_test.go").read_text(encoding="utf-8")
        m_src = pathlib.Path("math.go").read_text(encoding="utf-8")
        # If test was not restored, agent's "PASS_ALWAYS" would succeed
        if "PASS_ALWAYS" in t_src:
            sys.exit(0)
        sys.exit(0 if "return a + b" in m_src else 1)
        """))
    monkeypatch.setenv("PATH", str(bin_dir))

    build, _ = _multi_build(tmp_path, [textwrap.dedent("""\
        import pathlib
        pathlib.Path("math_test.go").write_text("package demo // PASS_ALWAYS\\n")
        pathlib.Path("go.mod").write_text("module evil\\n")
        """)])
    res = R.run(proj, build, "fix Add", max_attempts=2, attempt_timeout_s=20, budget_s=120)

    assert res["acceptance"]["kind"] == "go"
    assert set(res["protected"]) == {"go.mod", "math_test.go"}
    assert res["accepted"] is False
    assert all(set(a["tests_tampered"]) == {"go.mod", "math_test.go"} for a in res["attempts"])
    assert (proj / "math_test.go").read_text(encoding="utf-8") == orig_test
    assert (proj / "go.mod").read_text(encoding="utf-8") == orig_mod
    msg = R.summary(res)
    assert "math_test.go" in msg and "go.mod" in msg


@pytest.mark.skipif(shutil.which("go") is None, reason="go not installed")
def test_defect1_go_real_test_tampering_rejected(tmp_path):
    proj = tmp_path / "real_go_proj"
    proj.mkdir()
    orig_mod = "module example.com/demo\n\ngo 1.21\n"
    orig_test = textwrap.dedent("""\
        package demo

        import "testing"

        func TestAdd(t *testing.T) {
            if Add(1, 2) != 3 {
                t.Fatalf("got %d, want 3", Add(1, 2))
            }
        }
        """)
    (proj / "go.mod").write_text(orig_mod, encoding="utf-8")
    (proj / "math.go").write_text("package demo\n\nfunc Add(a, b int) int { return 0 }\n", encoding="utf-8")
    (proj / "math_test.go").write_text(orig_test, encoding="utf-8")

    build, _ = _multi_build(tmp_path, [textwrap.dedent("""\
        import pathlib
        pathlib.Path("math_test.go").write_text(
            'package demo\\nimport "testing"\\nfunc TestAdd(t *testing.T) {}\\n'
        )
        """)])
    res = R.run(proj, build, "fix Add", max_attempts=1, attempt_timeout_s=30, budget_s=120)
    assert res["acceptance"]["kind"] == "go"
    assert res["accepted"] is False
    assert "math_test.go" in res["attempts"][0]["tests_tampered"]
    assert (proj / "math_test.go").read_text(encoding="utf-8") == orig_test
    assert (proj / "go.mod").read_text(encoding="utf-8") == orig_mod


# ---------------------------------------------------------------------------
# 4. --check with repeatable --protect PATH/GLOB and honest warning when none
# ---------------------------------------------------------------------------

def test_defect1_check_without_protect_warns_agent_could_edit_check(tmp_path):
    proj = tmp_path / "unprot"
    proj.mkdir()
    (proj / "app.py").write_text("v = 1\n", encoding="utf-8")
    (proj / "verify.py").write_text("import app, sys; sys.exit(0 if app.v == 2 else 1)\n", encoding="utf-8")

    build, _ = _multi_build(tmp_path, [
        "import pathlib\npathlib.Path('app.py').write_text('v = 2\\n')\n",
    ])
    res = R.run(proj, build, "set v=2", max_attempts=1, check=f"{sys.executable} verify.py",
                attempt_timeout_s=20, budget_s=120)
    assert res["protected"] == []
    msg = R.summary(res)
    assert "protected (restored before check): none — the agent could have edited what this check runs" in msg


def test_defect1_check_with_protect_blocks_script_tampering_and_cli_repeatable(tmp_path, monkeypatch, capsys):
    proj = tmp_path / "prot_check"
    proj.mkdir()
    (proj / "app.py").write_text("v = 1\n", encoding="utf-8")
    (proj / "scripts").mkdir()
    orig_verify = "import pathlib, sys\nimport app\nwant = int(pathlib.Path('data/expected.txt').read_text().strip())\nsys.exit(0 if app.v == want else 1)\n"
    orig_expected = "2\n"
    (proj / "scripts" / "verify.py").write_text(orig_verify, encoding="utf-8")
    (proj / "data").mkdir()
    (proj / "data" / "expected.txt").write_text(orig_expected, encoding="utf-8")

    # Fake agent edits BOTH the check script AND the expected fixture file, leaving app.py broken
    agent_py = tmp_path / "cheat_agent.py"
    agent_py.write_text(textwrap.dedent("""\
        import pathlib
        pathlib.Path("scripts/verify.py").write_text("import sys; sys.exit(0)\\n")
        pathlib.Path("data/expected.txt").write_text("1\\n")
        """), encoding="utf-8")

    monkeypatch.chdir(proj)
    rc = adapters_cli.main([
        "do",
        "--cmd", f"{sys.executable} {agent_py} {{prompt}}",
        "--prompt", "set app.v = 2",
        "--attempts", "1",
        "--check", f"{sys.executable} scripts/verify.py",
        "--protect", "scripts/*.py",
        "--protect", "data/expected.txt",
        "--attempt-timeout", "20",
    ])
    out = capsys.readouterr().out
    assert rc == adapters_cli.EXIT["reject"]
    # Neither protected file was modified in the user's project
    assert (proj / "scripts" / "verify.py").read_text(encoding="utf-8") == orig_verify
    assert (proj / "data" / "expected.txt").read_text(encoding="utf-8") == orig_expected
    assert (proj / "app.py").read_text(encoding="utf-8") == "v = 1\n"
    assert "scripts/verify.py" in out
    assert "data/expected.txt" in out
    assert "not written back" in out


def test_defect1_protect_rejects_path_escape(tmp_path):
    proj = tmp_path / "esc"
    proj.mkdir()
    (proj / "a.py").write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="inside project"):
        R.detect_acceptance(proj, check="true", protect=["../outside.txt"])
    with pytest.raises(ValueError, match="inside project"):
        R.detect_acceptance(proj, check="true", protect=["/etc/passwd"])
    with pytest.raises(ValueError, match="empty"):
        R.detect_acceptance(proj, check="true", protect=["  "])


def test_defect1_npm_pinned_script_defense_in_depth_on_direct_acceptance(tmp_path, monkeypatch):
    proj, _, _ = _make_npm_repro_proj(tmp_path)
    bin_dir = tmp_path / "bin"
    _make_fake_tool(bin_dir, "npm", "import sys; sys.exit(0)\n")
    monkeypatch.setenv("PATH", str(bin_dir))

    spec = R.detect_acceptance(proj)
    assert spec.kind == "npm" and spec.pinned_script == "node m.test.js"

    # Simulate direct acceptance() call where workspace package.json was tampered AND originals omitted it
    ws = tmp_path / "tampered_ws"
    shutil.copytree(proj, ws)
    (ws / "package.json").write_text(json.dumps({"scripts": {"test": "true"}}), encoding="utf-8")
    direct = R.acceptance({}, ws, spec=spec)
    assert direct["accept"] is False
    assert direct["status"] == "acceptance_error"
