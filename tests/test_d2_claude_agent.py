"""D2′ Claude Code agent 支援：用量解析、環境／旗標隔離，與假模型端到端（L-fake）驗證。

證據等級：L-fake（假模型 `ops/intake/mock_model.py`＋真 `claude` CLI＋真 `vacant install --agents claude --mode observe`
＋真 `source_server.py`）。證明接線、隔離、病歷記錄與用量解析；不代表任何真模型的能力。
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import time

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


RUN_D2 = _load("run_d2", "ops/d2/run_d2.py")
GEN_MAT = _load("gen_materials", "ops/d2/gen_materials.py")
AUDIT_D2 = _load("audit_d2", "ops/d2/audit_d2.py")


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


# ── 單元測試：usage_from_claude_log ─────────────────────────────────────


def test_usage_from_claude_stream_json_dedupes_parallel_blocks(tmp_path):
    """同一通 API 回應有兩個 tool_use block（同 message.id）只算 1 次呼叫，而非 result.num_turns=3。"""
    log = tmp_path / "agent.log"
    lines = [
        {"type": "system", "subtype": "init", "session_id": "s1"},
        {"type": "assistant", "message": {"id": "msg_1", "model": "claude-haiku-4-5",
                                          "usage": {"input_tokens": 10, "output_tokens": 1}}},
        {"type": "assistant", "message": {"id": "msg_1", "model": "claude-haiku-4-5",
                                          "usage": {"input_tokens": 10, "output_tokens": 1}}},
        {"type": "assistant", "message": {"id": "msg_2", "model": "claude-haiku-4-5",
                                          "usage": {"input_tokens": 12, "output_tokens": 1}}},
        {"type": "result", "subtype": "success", "is_error": False, "num_turns": 3,
         "usage": {"input_tokens": 22, "output_tokens": 19,
                   "cache_creation_input_tokens": 120, "cache_read_input_tokens": 450},
         "modelUsage": {"claude-haiku-4-5": {"inputTokens": 22, "outputTokens": 19}}},
    ]
    log.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    u = RUN_D2.usage_from_claude_log(log)
    assert u == {
        "calls": 2,
        "errors": 0,
        "input": 22,
        "output": 19,
        "cache_creation_input_tokens": 120,
        "cache_read_input_tokens": 450,
        "final_error": None,
    }


def test_usage_from_claude_stream_json_api_error_counts_zero_calls(tmp_path):
    """連線失敗時 Claude 印出 <synthetic> 錯誤訊息與 result.is_error=true ⇒ calls=0, errors=1。"""
    log = tmp_path / "agent.log"
    lines = [
        {"type": "system", "subtype": "init"},
        {"type": "assistant", "is_api_error_message": True, "error": "server_error",
         "api_error": "connection_failed",
         "message": {"id": "err_1", "model": "<synthetic>",
                     "content": [{"type": "text", "text": "API Error: Connection refused"}],
                     "usage": {"input_tokens": 0, "output_tokens": 0}}},
        {"type": "result", "subtype": "success", "is_error": True, "num_turns": 1,
         "api_error": "connection_failed", "result": "API Error: Connection refused",
         "usage": {"input_tokens": 0, "output_tokens": 0,
                   "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0},
         "modelUsage": {}},
    ]
    log.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    u = RUN_D2.usage_from_claude_log(log)
    assert u is not None
    assert u["calls"] == 0
    assert u["errors"] == 1
    assert u["input"] is None and u["output"] is None
    assert "Connection refused" in (u["final_error"] or "")


def test_usage_from_claude_timeout_without_result_sums_assistant_messages(tmp_path):
    log = tmp_path / "agent.log"
    lines = [
        {"type": "system", "subtype": "init"},
        {"type": "assistant", "message": {"id": "msg_1", "model": "claude-haiku-4-5",
                                          "usage": {"input_tokens": 15, "output_tokens": 4,
                                                    "cache_creation_input_tokens": 50,
                                                    "cache_read_input_tokens": 100}}},
    ]
    log.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    u = RUN_D2.usage_from_claude_log(log)
    assert u == {
        "calls": 1, "errors": 0, "input": 15, "output": 4,
        "cache_creation_input_tokens": 50, "cache_read_input_tokens": 100, "final_error": None,
    }


def test_usage_from_claude_empty_or_non_json_returns_none(tmp_path):
    log = tmp_path / "agent.log"
    log.write_text("fatal: cli crashed before json\n")
    assert RUN_D2.usage_from_claude_log(log) is None


def test_usage_from_claude_single_json_fallback(tmp_path):
    log = tmp_path / "agent.log"
    log.write_text(json.dumps({
        "type": "result", "subtype": "success", "is_error": False, "num_turns": 2,
        "usage": {"input_tokens": 30, "output_tokens": 12,
                  "cache_creation_input_tokens": 10, "cache_read_input_tokens": 20},
        "modelUsage": {"claude-haiku-4-5": {"inputTokens": 30}},
    }) + "\n")
    u = RUN_D2.usage_from_claude_log(log)
    assert u is not None and u["calls"] == 2 and u["input"] == 30 and u["output"] == 12
    assert u["cache_creation_input_tokens"] == 10 and u["cache_read_input_tokens"] == 20


# ── 單元測試：pi 預設行為不變＋claude 環境／參數隔離 ────────────────────


def _make_minimal_materials(tmp_path: pathlib.Path) -> tuple[pathlib.Path, str]:
    mat = tmp_path / "materials"
    info = GEN_MAT.build(seed=1, n_sets=1, out=mat)
    return mat, info["manifest_sha256"]


def test_pi_default_env_and_argv_unchanged(tmp_path, monkeypatch):
    mat, msha = _make_minimal_materials(tmp_path)
    plan_path = tmp_path / "pi_plan.json"
    plan_path.write_text(json.dumps({
        "schema": "vacant.d2.plan/1", "id": "pi_test", "seed": 1,
        "materials": {"dir": str(mat), "manifest_sha256": msha, "sets": ["s01"]},
        "arms": ["a"], "jobs": 1, "agent_timeout_s": 30,
        "server": {"port": 18991},
        "model": {"provider": "lms", "model": "gemma-4"},
        "vacant_python": sys.executable,
        "agentcfg": {"dir": str(tmp_path), "copy": [], "install_json": str(tmp_path / "i.json")},
    }))
    monkeypatch.setenv("HTTPS_PROXY", "http://should-be-stripped:9999")
    run = RUN_D2.Run(plan_path, tmp_path / "out")
    assert run.agent_kind() == "pi"
    live = tmp_path / "live"
    env = run.agent_env(live)
    assert env["PI_CODING_AGENT_DIR"] == str(live / "cfg")
    assert env["PI_SKIP_VERSION_CHECK"] == "1"
    assert env["NO_PROXY"] == RUN_D2.NO_PROXY
    assert env["http_proxy"] == "http://127.0.0.1:18991"
    assert "https_proxy" not in env and "HTTPS_PROXY" not in env
    out = tmp_path / "r"
    argv = run._agent_argv(live, "hello", out)
    assert argv == ["pi", "-p", "--mode", "json", "--session-dir", str(out / "sessions"),
                    "--provider", "lms", "--model", "gemma-4", "hello"]


def test_claude_env_and_argv_isolation(tmp_path, monkeypatch):
    mat, msha = _make_minimal_materials(tmp_path)
    plan_path = tmp_path / "claude_plan.json"
    plan_path.write_text(json.dumps({
        "schema": "vacant.d2.plan/1", "id": "claude_test", "seed": 1,
        "materials": {"dir": str(mat), "manifest_sha256": msha, "sets": ["s01"]},
        "arms": ["a"], "jobs": 1, "agent_timeout_s": 30,
        "server": {"port": 18992},
        "model": {"agent": "claude", "model": "claude-haiku-4-5", "max_turns": 20},
        "vacant_python": sys.executable,
        "agentcfg": {"dir": str(tmp_path), "copy": [], "install_json": str(tmp_path / "i.json")},
    }))
    monkeypatch.setenv("HTTPS_PROXY", "http://should-be-stripped:9999")
    run = RUN_D2.Run(plan_path, tmp_path / "out")
    assert run.agent_kind() == "claude"
    live = tmp_path / "live"
    (live / "cfg").mkdir(parents=True)
    (live / "cfg" / "settings.json").write_text("{}")
    env = run.agent_env(live)
    assert "PI_CODING_AGENT_DIR" not in env
    assert "https_proxy" not in env and "HTTPS_PROXY" not in env
    assert env["http_proxy"] == "http://127.0.0.1:18992"
    assert "api.anthropic.com" in env["NO_PROXY"]
    assert "claude.ai" in env["NO_PROXY"]
    assert env["HOME"] == os.environ["HOME"]
    argv = run._agent_argv(live, "hello prompt", tmp_path / "r")
    assert argv[:5] == ["claude", "-p", "--model", "claude-haiku-4-5", "--output-format"]
    assert "--setting-sources" in argv and argv[argv.index("--setting-sources") + 1] == ""
    assert "--settings" in argv and argv[argv.index("--settings") + 1] == str(live / "cfg" / "settings.json")
    assert "--strict-mcp-config" in argv
    assert "--disable-slash-commands" in argv
    assert "--no-session-persistence" in argv
    assert "--disallowedTools" in argv and "WebFetch" in argv[argv.index("--disallowedTools") + 1]
    assert "WebSearch" in argv[argv.index("--disallowedTools") + 1]
    assert "--max-turns" in argv and argv[argv.index("--max-turns") + 1] == "20"
    assert argv[-2:] == ["--", "hello prompt"]


# ── 端到端 L-fake 測試：真 claude + 真 vacant install + 真 source_server + 假模型 ──


@pytest.mark.skipif(shutil.which("claude") is None, reason="claude CLI not installed")
def test_d2_claude_end_to_end_with_mock_model(tmp_path, monkeypatch):
    mat, msha = _make_minimal_materials(tmp_path)
    manifest = json.loads((mat / "manifest.json").read_text())
    s01 = manifest["sets"][0]
    first_claim = s01["claims"][0]
    first_val = s01["truth"][0][first_claim["id"]]
    old_line = f"{first_claim['template_line']}____"
    new_line = f"{first_claim['template_line']}{first_val}"

    # 1. 真實執行 `vacant install --agents claude --mode observe`（隔離 HOME 與 VACANT_HOME）
    install_home = tmp_path / "install_home"
    install_home.mkdir()
    install_vhome = install_home / ".vacant"
    install_env = {
        "PATH": os.environ["PATH"],
        "HOME": str(install_home),
        "VACANT_HOME": str(install_vhome),
        "LANG": "C.UTF-8",
    }
    inst = subprocess.run(
        [sys.executable, "-I", "-m", "vacant_network", "install", "--agents", "claude", "--mode", "observe"],
        env=install_env, capture_output=True, text=True, check=True,
    )
    assert "claude:" in inst.stdout
    installed_settings = install_home / ".claude" / "settings.json"
    installed_manifest = install_vhome / "adapters" / "install.json"
    assert installed_settings.is_file()
    assert installed_manifest.is_file()
    assert json.loads(installed_manifest.read_text())["mode"] == "observe"

    # 2. 準備隔離的執行期 HOME／CLAUDE_CONFIG_DIR（埋入誘餌 hook／CLAUDE.md／MCP，驗證隔離不會漏）
    runtime_home = tmp_path / "runtime_home"
    runtime_claude_dir = runtime_home / ".claude"
    runtime_claude_dir.mkdir(parents=True)
    decoy_sentinel = tmp_path / "USER_HOOK_LEAKED"
    (runtime_claude_dir / "settings.json").write_text(json.dumps({
        "disableAllHooks": True,
        "hooks": {
            "SessionStart": [{"hooks": [{"type": "command", "command": f"touch {decoy_sentinel}"}]}],
            "PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": f"touch {decoy_sentinel}"}]}],
        },
    }))
    (runtime_claude_dir / "CLAUDE.md").write_text("DECOY_USER_CLAUDE_MD_SENTINEL\n")
    (runtime_home / ".claude.json").write_text(json.dumps({
        "mcpServers": {"decoy_mcp": {"command": "true", "args": []}},
    }))

    # 3. 啟動假模型 mock_model.py（curl p1.html → Read report.md → Edit report.md）
    mock_port = _free_port()
    src_port = _free_port()
    scn_path = tmp_path / "scenario.json"
    scn_path.write_text(json.dumps({
        "steps": [
            {"run": "curl -s http://s01.d2-sources.example/p1.html"},
            {"read": "report.md"},
            {"edit": ["report.md", old_line, new_line]},
        ],
        "final": "Updated report.md from p1.html.",
        "usage": {
            "input_tokens": 12,
            "output_tokens": 9,
            "cache_creation_input_tokens": 100,
            "cache_read_input_tokens": 200,
        },
    }))
    mock_log = tmp_path / "mock.jsonl"
    mock_bodies = tmp_path / "mock_bodies"
    mock_proc = subprocess.Popen(
        [sys.executable, str(REPO / "ops" / "intake" / "mock_model.py"), str(mock_port)],
        env={**os.environ, "MOCK_SCENARIO": str(scn_path), "MOCK_LOG": str(mock_log),
             "MOCK_BODIES": str(mock_bodies)},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", mock_port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    else:
        mock_proc.terminate()
        pytest.fail("mock_model did not start")

    try:
        # 4. 寫一份 D2 計畫並用 run_d2.Run 跑一組（c0＋a 臂）
        plan_path = tmp_path / "plan.json"
        plan_path.write_text(json.dumps({
            "schema": "vacant.d2.plan/1", "id": "lfake_claude_e2e", "seed": 7,
            "materials": {"dir": str(mat), "manifest_sha256": msha, "sets": ["s01"]},
            "arms": ["a"], "jobs": 1, "agent_timeout_s": 120,
            "server": {"port": src_port},
            "model": {"agent": "claude", "model": "claude-haiku-4-5"},
            "vacant_python": sys.executable,
            "agentcfg": {
                "dir": str(install_home / ".claude"),
                "copy": ["settings.json"],
                "install_json": str(installed_manifest),
            },
        }))

        # 隔離 HOME／CLAUDE_CONFIG_DIR 與假金鑰，絕不碰 /home/user1/.claude 與真實 API
        monkeypatch.setenv("HOME", str(runtime_home))
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(runtime_claude_dir))
        monkeypatch.setenv("ANTHROPIC_BASE_URL", f"http://127.0.0.1:{mock_port}")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-d2-claude-e2e")
        monkeypatch.setenv("CLAUDE_CODE_MAX_RETRIES", "0")
        monkeypatch.setenv("API_TIMEOUT_MS", "20000")
        monkeypatch.setenv("PYTHONPATH", str(REPO))

        root = tmp_path / "run_root"
        run = RUN_D2.Run(plan_path, root)
        rc = run.go()
        assert rc == 0, (root / "runner.log").read_text()

        # 5a. report.md 已被 Edit 改成 p1.html 的真值
        edited_report = (root / "cells" / "s01" / "c0" / "report.md").read_text()
        assert new_line in edited_report
        assert old_line not in edited_report

        # 5b. source_server 收到 p1.html 請求，且沒有任何 Anthropic API 流量走進來源代理
        access = [json.loads(x) for x in (root / "access.jsonl").read_text().splitlines() if x.strip()]
        assert any(a["host"] == "s01.d2-sources.example" and a["path"] == "/p1.html" and a["status"] == 200
                   for a in access)
        assert all(a["host"].endswith(".d2-sources.example") for a in access)

        # 5c. 假模型記錄：沒有 WebFetch／WebSearch、有用到 Bash 與 Edit、沒有外洩使用者設定
        mock_recs = [json.loads(x) for x in mock_log.read_text().splitlines() if x.strip()]
        assert len(mock_recs) == 4
        for rec in mock_recs:
            assert "WebFetch" not in (rec.get("tools") or [])
            assert "WebSearch" not in (rec.get("tools") or [])
        assert [rec.get("tool") for rec in mock_recs] == ["Bash", "Read", "Edit", None]
        assert not decoy_sentinel.exists()
        bodies_text = "\n".join(p.read_text() for p in sorted(mock_bodies.glob("*.json")))
        assert "DECOY_USER_CLAUDE_MD_SENTINEL" not in bodies_text
        assert "decoy_mcp" not in bodies_text

        # 5d. Vacant 病歷鏈完整且含 Bash curl 與 Edit report.md 的 step 事件
        snap_vh = root / "cells" / "s01" / "c0" / "snapshot" / "vh"
        rec = AUDIT_D2.Record(snap_vh)
        assert rec.problems == []
        steps = [e for e in rec.events if e["type"] == "step"]
        bash_steps = [e for e in steps if e["payload"].get("tool") == "Bash"
                      and "http://s01.d2-sources.example/p1.html" in AUDIT_D2.step_cmd(rec, e)]
        edit_steps = [e for e in steps if e["payload"].get("tool") == "Edit"
                      and any(w.get("path") == "report.md" for w in (e["payload"].get("writes") or []))]
        assert len(bash_steps) == 1
        assert len(edit_steps) == 1

        # 5e. run.json 用量解析正確（含快取 token 欄位）
        run_info = json.loads((root / "cells" / "s01" / "c0" / "run" / "run.json").read_text())
        assert run_info["rc"] == 0
        u = run_info["usage"]
        assert u["calls"] == 4
        assert u["errors"] == 0
        assert u["input"] == 48
        assert u["output"] == 36
        assert u["cache_creation_input_tokens"] == 400
        assert u["cache_read_input_tokens"] == 800
        assert u["final_error"] is None

        # 5f. 確認 `vacant trace sources report.md --check --json`（c 臂）也能從 Claude 病歷追到 p1.html
        srv = run.start_server()
        try:
            sc = run.sources_check(root / "live" / "s01", tmp_path / "sc_out")
            assert any((c.get("source") or {}).get("url") == "http://s01.d2-sources.example/p1.html"
                       for c in sc["claims"])
        finally:
            srv.terminate()
            srv.wait()

        # 5g. 基礎設施失敗（0 次成功回應＋連線錯誤 ⇒ InfraError）
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:1")
        err_out = tmp_path / "infra_err_out"
        with pytest.raises(RUN_D2.InfraError):
            run.run_agent(root / "live" / "s01", "hi", err_out)
        err_info = json.loads((err_out / "run.json").read_text())
        assert err_info["usage"]["calls"] == 0
        assert err_info["usage"]["errors"] >= 1
    finally:
        mock_proc.terminate()
        mock_proc.wait()
