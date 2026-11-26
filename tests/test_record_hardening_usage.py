"""紀錄強化 1：模型呼叫數與 token 用量簽進鏈（`model_usage` 事件）。

覆蓋四個 agent 的真實格式夾具：
- Claude Code：`Stop`／`SessionEnd`／`SubagentStop` 逐字稿（含同 `message.id` 串流去重、快取 token、缺欄位標 `complete=False`、畸形行、超上限不阻塞）
- pi：`turn_end`／`stop`／`session_end`（含實際執行 `PI_EXTENSION` JS 驗證 `turn_end` 累加→`stop`/`session_end` 帶 `model_usage`）
- Codex：rollout `token_count`（含重複快照去重）、`turn.completed`、缺 `token_count` 標 `complete=False`
- OpenCode：1.x／2.x 外掛帶 `model_usage`（含 `usageFromMessagesV1` 語法與執行檢查）
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess

import pytest

from vacant_network.adapters import agents as AG
from vacant_network.adapters import hook
from vacant_network.intake import keys
from vacant_network.trace import capture
from vacant_network.trace import cli as trace_cli
from vacant_network.trace import recorder as R


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    monkeypatch.setenv("VACANT_TRACE", "1")
    monkeypatch.setenv("VACANT_HOOK_NO_GC", "1")
    monkeypatch.setenv("VACANT_HOOK_NO_STOP", "1")
    keys.init_local()
    w = tmp_path / "proj"
    w.mkdir()
    return w


def _usage_events(ws: pathlib.Path) -> list[dict]:
    return [e for e in R.Recorder(ws).events() if e["type"] == "model_usage"]


def test_claude_transcript_stop_and_session_end_recorded_and_deduped(ws, tmp_path):
    """Claude Code 逐字稿：同 message.id 串流分片只算一次呼叫，Stop 與 SessionEnd 簽進鏈且 session_closed 仍在尾筆。"""
    tpath = tmp_path / "claude_session.jsonl"
    lines = [
        # 第一通回應拆成兩條串流行（共用 msg_01），應取最後一條的用量、只算 1 次呼叫
        {"type": "assistant", "message": {
            "id": "msg_01", "model": "claude-haiku-4-5-20251001",
            "usage": {"input_tokens": 100, "output_tokens": 10,
                      "cache_read_input_tokens": 500, "cache_creation_input_tokens": 200},
            "content": [{"type": "text", "text": "thinking..."}],
        }},
        {"type": "assistant", "message": {
            "id": "msg_01", "model": "claude-haiku-4-5-20251001",
            "usage": {"input_tokens": 100, "output_tokens": 45,
                      "cache_read_input_tokens": 500, "cache_creation_input_tokens": 200},
            "content": [{"type": "tool_use", "id": "toolu_1", "name": "Read", "input": {}}],
        }},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "toolu_1"}]}},
        # 第二通回應（不同 id）
        {"type": "assistant", "message": {
            "id": "msg_02", "model": "claude-haiku-4-5-20251001",
            "usage": {"input_tokens": 120, "output_tokens": 80,
                      "cache_read_input_tokens": 700, "cache_creation_input_tokens": 0},
            "content": [{"type": "text", "text": "done"}],
        }},
    ]
    tpath.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    base = {"session_id": "s-claude", "cwd": str(ws), "transcript_path": str(tpath)}

    hook.handle("claude", "Stop", {**base, "stop_hook_active": False})
    evs = _usage_events(ws)
    assert len(evs) == 1
    u = evs[0]
    assert u["scope"] == "turn"
    assert u["source"] == "claude_transcript"
    assert u["observed_by"] == "agent_claim"
    assert u["complete"] is True
    assert u["calls"] == 2
    assert u["input_tokens"] == 220
    assert u["output_tokens"] == 125
    assert u["cache_read_tokens"] == 1200
    assert u["cache_write_tokens"] == 200
    assert u["models_claimed"] == ["claude-haiku-4-5-20251001"]

    hook.handle("claude", "SessionEnd", {**base, "reason": "other"})
    rec = R.Recorder(ws)
    all_evs = rec.events()
    assert all_evs[-1]["type"] == "session_closed"
    evs2 = _usage_events(ws)
    assert len(evs2) == 2
    assert evs2[-1]["scope"] == "session"
    assert evs2[-1]["calls"] == 2
    assert evs2[-1]["input_tokens"] == 220
    assert evs2[-1]["output_tokens"] == 125
    assert rec.verify()[0]


def test_claude_incomplete_and_malformed_transcript_marks_partial(ws, tmp_path):
    """缺 usage 欄位或含畸形行 ⇒ complete=False 並附 note，絕不阻塞掛鉤。"""
    tpath = tmp_path / "partial.jsonl"
    tpath.write_text(
        json.dumps({"type": "assistant", "message": {
            "id": "m1", "model": "claude-sonnet-4-6",
            "usage": {"input_tokens": 50, "output_tokens": 20},
        }}) + "\n"
        + "{corrupted json line\n"
        + json.dumps({"type": "assistant", "message": {
            "id": "m2", "model": "claude-sonnet-4-6",
        }}) + "\n",
        encoding="utf-8",
    )
    hook.handle("claude", "SessionEnd", {
        "session_id": "s-part", "cwd": str(ws), "transcript_path": str(tpath), "reason": "other",
    })
    evs = _usage_events(ws)
    assert len(evs) == 1
    u = evs[0]
    assert u["complete"] is False
    assert u["calls"] == 2
    assert u["input_tokens"] == 50
    assert u["output_tokens"] == 20
    assert "malformed" in u["note"] and "lacked token usage" in u["note"]
    assert R.Recorder(ws).verify()[0]


def test_claude_oversized_transcript_on_stop_marks_incomplete_without_reading(ws, tmp_path, monkeypatch):
    """Stop 掛鉤遇到超過 MAX_USAGE_STOP_BYTES 的逐字稿不硬讀，記 complete=False。"""
    monkeypatch.setattr(capture, "MAX_USAGE_STOP_BYTES", 64)
    tpath = tmp_path / "huge.jsonl"
    tpath.write_text("x" * 200, encoding="utf-8")
    hook.handle("claude", "Stop", {
        "session_id": "s-big", "cwd": str(ws), "transcript_path": str(tpath),
    })
    evs = _usage_events(ws)
    assert len(evs) == 1
    assert evs[0]["complete"] is False
    assert evs[0]["calls"] is None
    assert "exceeded" in evs[0]["note"]


def test_codex_rollout_and_exec_json_fixtures(ws, tmp_path):
    """Codex rollout token_count（含重複快照去重）與 codex exec --json turn.completed 都能抽成 model_usage。"""
    rollout = tmp_path / "codex_rollout.jsonl"
    rollout_lines = [
        {"type": "turn_context", "payload": {"model": "gpt-5.4"}},
        {"type": "event_msg", "payload": {"type": "token_count", "info": {
            "total_token_usage": {"input_tokens": 500, "cached_input_tokens": 100,
                                  "output_tokens": 120, "total_tokens": 620},
        }}},
        # 重複的 cumulative 快照：不應重複計為兩通呼叫
        {"type": "event_msg", "payload": {"type": "token_count", "info": {
            "total_token_usage": {"input_tokens": 500, "cached_input_tokens": 100,
                                  "output_tokens": 120, "total_tokens": 620},
        }}},
        {"type": "event_msg", "payload": {"type": "token_count", "info": {
            "total_token_usage": {"input_tokens": 1400, "cached_input_tokens": 400,
                                  "output_tokens": 310, "total_tokens": 1710},
        }}},
    ]
    rollout.write_text("\n".join(json.dumps(x) for x in rollout_lines) + "\n", encoding="utf-8")
    hook.handle("codex", "SessionEnd", {
        "session_id": "cx-1", "cwd": str(ws), "transcript_path": str(rollout), "reason": "other",
    })
    evs = _usage_events(ws)
    assert len(evs) == 1
    u = evs[0]
    assert u["source"] == "codex_transcript"
    assert u["complete"] is True
    assert u["calls"] == 2
    assert u["input_tokens"] == 1400
    assert u["output_tokens"] == 310
    assert u["cache_read_tokens"] == 400
    assert u["total_tokens"] == 1710
    assert u["models_claimed"] == ["gpt-5.4"]

    # codex exec --json (turn.completed)
    exec_log = tmp_path / "codex_exec.jsonl"
    exec_log.write_text("\n".join(json.dumps(x) for x in [
        {"type": "turn.completed", "model": "gpt-5.4-mini",
         "usage": {"input_tokens": 300, "cached_input_tokens": 50, "output_tokens": 90}},
        {"type": "turn.completed", "model": "gpt-5.4-mini",
         "usage": {"input_tokens": 400, "cached_input_tokens": 150, "output_tokens": 110}},
    ]) + "\n", encoding="utf-8")
    parsed = capture.usage_from_transcript("codex", exec_log.read_bytes())
    assert parsed is not None
    assert parsed["complete"] is True
    assert parsed["calls"] == 2
    assert parsed["input_tokens"] == 700
    assert parsed["output_tokens"] == 200
    assert parsed["cache_read_tokens"] == 200
    assert parsed["models_claimed"] == ["gpt-5.4-mini"]
    assert R.Recorder(ws).verify()[0]


def test_pi_turn_end_stop_and_session_end_usage(ws, capsys):
    """pi 掛鉤：turn_end 單回合、stop／session_end 累計 model_usage、與無 token 退化為 complete=False。"""
    # 1) turn_end 帶單回合 message.usage
    hook.handle("pi", "turn_end", {
        "session_id": "pi-1", "cwd": str(ws), "model": "local/gemma-4-12b",
        "message": {"model": "local/gemma-4-12b",
                    "usage": {"input": 1000, "output": 250, "cacheRead": 400, "cacheWrite": 50}},
    })
    # 2) stop 帶 PI_EXTENSION 產出的 model_usage 快照
    hook.handle("pi", "stop", {
        "session_id": "pi-1", "cwd": str(ws), "turn": 3,
        "model_usage": {
            "source": "pi_hook", "calls": 3, "input_tokens": 3200, "output_tokens": 710,
            "cache_read_tokens": 900, "complete": True, "models_claimed": ["local/gemma-4-12b"],
        },
    })
    # 3) 只有 turn 沒有 token 的舊形狀 ⇒ complete=False
    hook.handle("pi", "session_end", {
        "session_id": "pi-2", "cwd": str(ws), "turn": 4, "model": "local/qwen",
    })
    evs = _usage_events(ws)
    assert len(evs) == 3
    assert evs[0]["calls"] == 1 and evs[0]["input_tokens"] == 1000 and evs[0]["output_tokens"] == 250
    assert evs[0]["cache_read_tokens"] == 400 and evs[0]["complete"] is True
    assert evs[1]["calls"] == 3 and evs[1]["input_tokens"] == 3200 and evs[1]["complete"] is True
    assert evs[2]["calls"] == 4 and evs[2]["input_tokens"] is None and evs[2]["complete"] is False
    assert R.Recorder(ws).verify()[0]

    # trace show 人讀輸出與 --session 過濾正常呈現 model_usage
    old = pathlib.Path.cwd()
    try:
        import os
        os.chdir(ws)
        rc = trace_cli.main(["trace", "show", "--session", "pi-1"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "model_usage" in out and "in=3200 out=710" in out
    finally:
        os.chdir(old)


def test_opencode_hook_usage_recorded(ws):
    """OpenCode 外掛送來的 model_usage 在 stop／session_end 簽進鏈。"""
    hook.handle("opencode", "stop", {
        "session_id": "oc-1", "cwd": str(ws),
        "model_usage": {
            "source": "opencode_hook", "calls": 2, "input_tokens": 900, "output_tokens": 180,
            "cache_read_tokens": 300, "complete": True, "models_claimed": ["anthropic/claude-haiku"],
        },
    })
    evs = _usage_events(ws)
    assert len(evs) == 1
    assert evs[0]["source"] == "opencode_hook"
    assert evs[0]["calls"] == 2 and evs[0]["input_tokens"] == 900 and evs[0]["complete"] is True
    assert R.Recorder(ws).verify()[0]


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_pi_extension_js_accumulates_turn_end_usage_into_stop_and_session_end(tmp_path):
    """實際跑 node 載入 PI_EXTENSION：兩次 turn_end 的 usage 累加並隨 stop／session_end 送給掛鉤。"""
    log_path = tmp_path / "hook_calls.jsonl"
    stub = tmp_path / "stub_hook.py"
    stub.write_text(
        "import json, pathlib, sys\n"
        f"p = pathlib.Path({str(log_path)!r})\n"
        "ev = sys.argv[1]\n"
        "body = json.loads(sys.stdin.read() or '{}')\n"
        "with p.open('a') as f: f.write(json.dumps({'event': ev, 'body': body}) + '\\n')\n"
        "print(json.dumps({'action': 'allow'}))\n",
        encoding="utf-8",
    )
    ext = tmp_path / "vacant.mjs"
    import sys as _sys
    ext.write_text(AG.PI_EXTENSION % {
        "argv": json.dumps([_sys.executable, str(stub)]),
        "timeout_ms": 5000,
        "budget_re": "/" + AG.BUDGET_RE_SRC.replace("/", r"\/") + "/i",
    }, encoding="utf-8")
    driver = tmp_path / "run.mjs"
    driver.write_text(
        f"import init from {json.dumps(ext.as_uri())};\n"
        "const handlers = {};\n"
        "init({ on(ev, fn) { handlers[ev] = fn; } });\n"
        "const ctx = { cwd: '/tmp', sessionManager: { getSessionId: () => 'pi-js-1' }, "
        "              model: { provider: 'local', id: 'gemma-4-12b' } };\n"
        "await handlers.turn_end({ message: { stopReason: 'toolUse', model: 'gemma-4-12b', "
        "  usage: { input: 500, output: 120, cacheRead: 200 } }, toolResults: [{}] }, ctx);\n"
        "await handlers.turn_end({ message: { stopReason: 'stop', model: 'gemma-4-12b', "
        "  usage: { input: 650, output: 95, cacheRead: 350 } }, toolResults: [] }, ctx);\n"
        "await handlers.agent_before_settle({ context: { llmMessages: [] } }, ctx);\n"
        "await handlers.session_shutdown({ reason: 'quit' }, ctx);\n",
        encoding="utf-8",
    )
    r = subprocess.run(["node", str(driver)], capture_output=True, text=True, timeout=15)
    assert r.returncode == 0, r.stderr
    calls = [json.loads(ln) for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    stop_call = next(c for c in calls if c["event"] == "stop")
    end_call = next(c for c in calls if c["event"] == "session_end")
    for call in (stop_call, end_call):
        mu = call["body"]["model_usage"]
        assert mu["calls"] == 2
        assert mu["input_tokens"] == 1150
        assert mu["output_tokens"] == 215
        assert mu["cache_read_tokens"] == 550
        assert mu["complete"] is True
        assert mu["models_claimed"] == ["gemma-4-12b"]
