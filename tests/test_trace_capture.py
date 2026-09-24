"""四個 agent 的原生掛鉤 → 病歷（`trace/capture.py`，經 `adapters/hook.handle`）。

payload 的形狀取自 `ops/accountability/capture/` 的實測（真 binary＋假模型）。"""
from __future__ import annotations

import json

import pytest

from vacant_network.adapters import hook
from vacant_network.intake import keys
from vacant_network.trace import capture
from vacant_network.trace import recorder as R


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    monkeypatch.setenv("VACANT_TRACE", "1")
    keys.init_local()
    w = tmp_path / "proj"
    (w / "data").mkdir(parents=True)
    (w / "data" / "cities.csv").write_text("city,population\nSpringfield,30720\n")
    return w


def steps(w):
    return [e for e in R.Recorder(w).events() if e["type"] == "step"]


def test_claude_main_and_subagent_steps_with_shell_writes(ws, tmp_path):
    base = {"session_id": "s1", "cwd": str(ws), "transcript_path": str(tmp_path / "t.jsonl")}
    hook.handle("claude", "PreToolUse", {**base, "tool_name": "Read", "tool_use_id": "toolu_1",
                                         "tool_input": {"file_path": str(ws / "data/cities.csv")}})
    hook.handle("claude", "PostToolUse", {**base, "tool_name": "Read", "tool_use_id": "toolu_1",
                                          "tool_input": {"file_path": "x"},
                                          "tool_response": {"file": {"content": "30720"}}})
    sub = {**base, "agent_id": "ae25", "agent_type": "general-purpose"}
    cmd = {"command": "cut -c1-4 data/cities.csv > notes.txt"}
    hook.handle("claude", "PreToolUse", {**sub, "tool_name": "Bash", "tool_use_id": "toolu_2",
                                         "tool_input": cmd})
    (ws / "notes.txt").write_text("3072\n")                    # Bash 寫的：平台不回報
    hook.handle("claude", "PostToolUse", {**sub, "tool_name": "Bash", "tool_use_id": "toolu_2",
                                          "tool_input": cmd, "tool_response": {"stdout": ""}})
    hook.handle("claude", "PreToolUse", {**base, "tool_name": "Bash", "tool_use_id": "toolu_3",
                                         "tool_input": {"command": "false"}})
    hook.handle("claude", "PostToolUseFailure", {**base, "tool_name": "Bash",
                                                 "tool_use_id": "toolu_3",
                                                 "tool_input": {"command": "false"},
                                                 "error": "Exit code 1"})
    got = {s["step"]: s for s in steps(ws)}
    assert got["toolu_2"]["writes"][0]["path"] == "notes.txt"
    assert got["toolu_2"]["actor"] == {"platform": "claude", "session": "s1", "agent": "ae25",
                                       "agent_type": "general-purpose"}
    assert got["toolu_1"]["writes"] == [] and "agent" not in got["toolu_1"]["actor"]
    assert got["toolu_3"]["error"] == "Exit code 1"
    rec = R.Recorder(ws)
    assert json.loads(rec.blobs.get(got["toolu_1"]["output_blob"])) == {"file": {"content": "30720"}}
    # 工作階段結束：封存逐字稿，模型 id 是自稱
    (tmp_path / "t.jsonl").write_text(json.dumps({"type": "assistant", "message": {
        "model": "srv:claude-opus-5-5", "content": [{"type": "tool_use", "id": "toolu_1"}]}}) + "\n")
    hook.handle("claude", "SessionEnd", {**base, "reason": "other"})
    tr = [e for e in rec.events() if e["type"] == "transcript"][0]
    assert tr["models_claimed"] == {"toolu_1": "srv:claude-opus-5-5"}
    assert tr["observed_by"] == "agent_claim"
    assert rec.blobs.has(tr["sha256"])
    assert rec.events()[-1]["type"] == "session_closed"
    assert rec.verify()[0]


def test_denied_step_is_recorded_without_running(ws, monkeypatch):
    base = {"session_id": "s1", "cwd": str(ws)}
    vh = str(ws.parent / "vh")
    hook.handle("claude", "PreToolUse", {**base, "tool_name": "Bash", "tool_use_id": "t9",
                                         "tool_input": {"command": f"rm -rf {vh}"}})
    s = steps(ws)[-1]
    assert s["step"] == "t9" and s["denied"] and s["writes"] == []


def test_codex_post_never_comes_for_failed_patch(ws):
    base = {"session_id": "root", "cwd": str(ws), "model": "gpt-x", "turn_id": "u1"}
    hook.handle("codex", "PreToolUse", {**base, "tool_name": "apply_patch", "tool_use_id": "c1",
                                        "tool_input": {"command": "*** Begin Patch"}})
    (ws / "half.md").write_text("partial")
    hook.handle("codex", "Stop", {**base, "stop_hook_active": False})   # 回合結束：收尾
    s = steps(ws)[-1]
    assert s["step"] == "c1" and s["post_missing"] == "turn_end"
    assert s["writes"][0]["path"] == "half.md" and s["actor"]["model"] == "gpt-x"


def test_opencode_child_session_is_a_subagent_of_the_root(ws):
    hook.handle("opencode", "pre_tool", {"tool": "write", "input": {"filePath": "a.md"},
                                         "call_id": "k1", "cwd": str(ws), "session_id": "child",
                                         "parent_session_id": "root", "root_session_id": "root"})
    (ws / "a.md").write_text("x")
    hook.handle("opencode", "post_tool", {"tool": "write", "input": {"filePath": "a.md"},
                                          "call_id": "k1", "cwd": str(ws), "output": "ok",
                                          "session_id": "child", "parent_session_id": "root",
                                          "root_session_id": "root"})
    a = steps(ws)[-1]["actor"]
    assert a["session"] == "root" and a["agent"] == "child"


def test_pi_error_and_claimed_model(ws):
    p = {"tool": "bash", "input": {"command": "exit 3"}, "call_id": "p1", "cwd": str(ws),
         "session_id": "ps", "model": "local/gemma"}
    hook.handle("pi", "pre_tool", p)
    hook.handle("pi", "post_tool", {**p, "output": "", "is_error": True})
    s = steps(ws)[-1]
    assert s["error"] and s["actor"]["model"] == "local/gemma"


def test_off_by_default_without_contract_and_never_in_home(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    monkeypatch.delenv("VACANT_TRACE", raising=False)
    assert capture.workspace_for(str(tmp_path)) is None
    monkeypatch.setenv("VACANT_TRACE", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    assert capture.workspace_for(str(tmp_path)) is None                  # 家目錄＝整台機器
    assert capture.workspace_for("/") is None


def test_broken_trace_never_breaks_the_hook(ws, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("disk on fire")
    monkeypatch.setattr(capture, "observe", boom)
    out = hook.handle("claude", "PreToolUse", {"session_id": "s", "cwd": str(ws),
                                               "tool_name": "Read", "tool_input": {}})
    assert out == ("", "", 0)
