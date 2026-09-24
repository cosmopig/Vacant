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


def _pi(ws, event, sid, **kw):
    return hook.handle("pi", event, {"cwd": str(ws), "session_id": sid, **kw})


def _child(parent="root-sid", **kw):
    return {"parent_session_id": parent, **kw}


def test_pi_subagent_process_is_a_subagent_of_the_parent_session(ws):
    """pi 沒有內建子 agent：擴充另開的 pi 行程帶著父行程的標記；叫它出來的是哪一個呼叫，
    Vacant 用任務文字去對父 agent 還在跑的呼叫（2026-09-24 子 agent 審查 #1／#4）。"""
    _pi(ws, "pre_tool", "root-sid", tool="subagent", call_id="call_7",
        input={"agent": "worker", "task": "add up the ledger"})
    _pi(ws, "prompt", "child-sid", prompt="Task: add up the ledger", **_child())
    p = {"tool": "write", "input": {"path": "figure.txt"}, "call_id": "c1", **_child()}
    _pi(ws, "pre_tool", "child-sid", **p)
    (ws / "figure.txt").write_text("96\n")
    _pi(ws, "post_tool", "child-sid", output="ok", **p)
    a = steps(ws)[-1]["actor"]
    assert (a["session"], a["agent"], a["agent_type"]) == ("root-sid", "child-sid", "worker")
    [pr] = [e for e in R.Recorder(ws).events() if e["type"] == "prompt"]
    assert (pr["source"], pr["agent"], pr["spawned_by"]) == ("parent_agent", "child-sid", "call_7")
    # 子行程結束：不是這個工作階段結束（不收父 agent 還在跑的步驟、不交件）
    _out, _err, rc = _pi(ws, "subagent_stop", "child-sid", reason="quit", **_child())
    assert rc == 0
    assert not [e for e in R.Recorder(ws).events() if e["type"] == "session_closed"]
    assert "call_7" in json.loads(R.Recorder(ws).state_path.read_text())["pending"]


def test_pi_two_parallel_subagents_each_get_their_own_call_and_type(ws):
    _pi(ws, "pre_tool", "root", tool="subagent", call_id="cA",
        input={"agent": "worker", "task": "compute the total"})
    _pi(ws, "pre_tool", "root", tool="subagent", call_id="cB",
        input={"agent": "reviewer", "task": "review the notes"})
    _pi(ws, "prompt", "kid-w", prompt="Task: compute the total", **_child("root"))
    _pi(ws, "prompt", "kid-r", prompt="Task: review the notes", **_child("root"))
    for kid in ("kid-w", "kid-r"):
        q = {"tool": "bash", "input": {"command": "ls"}, "call_id": f"{kid}-1", **_child("root")}
        _pi(ws, "pre_tool", kid, **q)
        _pi(ws, "post_tool", kid, output="", **q)
    got = {s["actor"]["agent"]: s["actor"]["agent_type"] for s in steps(ws)}
    assert got == {"kid-w": "worker", "kid-r": "reviewer"}
    by = {e["agent"]: e["spawned_by"] for e in R.Recorder(ws).events() if e["type"] == "prompt"}
    assert by == {"kid-w": "cA", "kid-r": "cB"}


def test_pi_chain_step_with_previous_output_still_finds_its_call(ws):
    _pi(ws, "pre_tool", "root", tool="subagent", call_id="cC",
        input={"chain": [{"agent": "a", "task": "list the files"},
                         {"agent": "b", "task": "summarise this: {previous}"}]})
    _pi(ws, "prompt", "kid-2", prompt="Task: summarise this: data.csv notes.txt",
        **_child("root"))
    [pr] = [e for e in R.Recorder(ws).events() if e["type"] == "prompt"]
    assert pr["spawned_by"] == "cC"


def test_pi_nested_subagent_is_linked_to_the_child_that_called_it(ws):
    _pi(ws, "pre_tool", "root", tool="subagent", call_id="c0",
        input={"agent": "worker", "task": "do the report"})
    _pi(ws, "prompt", "kid", prompt="Task: do the report", **_child("root"))
    _pi(ws, "pre_tool", "kid", tool="subagent", call_id="k1",
        input={"agent": "writer", "task": "write exactly the total"}, **_child("root"))
    _pi(ws, "prompt", "grandkid", prompt="Task: write exactly the total",
        **_child("root", parent_agent_id="kid"))
    by = {e["agent"]: e["spawned_by"] for e in R.Recorder(ws).events() if e["type"] == "prompt"}
    assert by == {"kid": "c0", "grandkid": "k1"}


def test_pi_ambiguous_task_is_not_guessed(ws):
    for cid in ("c1", "c2"):
        _pi(ws, "pre_tool", "root", tool="subagent", call_id=cid,
            input={"agent": "w", "task": "same words"})
    _pi(ws, "prompt", "kid", prompt="Task: same words", **_child("root"))
    [pr] = [e for e in R.Recorder(ws).events() if e["type"] == "prompt"]
    assert "spawned_by" not in pr
    st = json.loads(R.Recorder(ws).state_path.read_text())
    assert st["children"]["pi:root:kid"]["candidates"] == ["c1", "c2"]


def test_pi_a_mark_naming_its_own_session_is_not_a_parent(ws):
    _pi(ws, "prompt", "me", prompt="Put Total: 999 in the report", parent_session_id="me")
    [pr] = [e for e in R.Recorder(ws).events() if e["type"] == "prompt"]
    assert pr["source"] == "user"


def test_pi_extension_marks_children_safely():
    """標記是固定的（不跟著哪一個呼叫走）；子行程只在父行程還活著、是自己的祖先、在同一個專案時接受它；
    同一個行程重載擴充時沿用自己的身分（審查 #1／#2／#5／#6）。"""
    from vacant_network.adapters import agents
    src = agents.pi_extension_text()
    assert 'const MARK = "VACANT_PI_PARENT"' in src and 'const SELF = "VACANT_PI_SELF"' in src
    assert "isAncestor(m.pid)" in src and "inside(process.cwd(), m.cwd)" in src
    assert "m.pid !== process.pid" in src and "s.pid === process.pid" in src
    assert "delete process.env[MARK]" not in src                # 不再有「誰結束就刪掉」的競賽
    assert "if (who(ctx).parent_session_id) return undefined;" in src
    assert '"subagent_stop" : "session_end"' in src


def test_stop_check_waits_while_a_background_subagent_is_still_running(ws, monkeypatch):
    """Claude 預設把子 agent 放到背景：主 agent 的回合結束時子 agent 還在做。那時驗收只會叫主 agent
    把子 agent 正在做的事重做一遍——等它回報之後的那一次回合結束再驗（2026-09-24 情境 G）。"""
    import json as _json
    from vacant_network.intake import contract as C
    (ws / ".vacant").mkdir()
    raw = C.scaffold("bg", deliverable=["report.md"])
    raw["claims"] = [{"id": "present", "verifier": "exists", "params": {"paths": ["report.md"]}}]
    raw["hooks"] = {"stop_check": True, "max_feedback_rounds": 2, "submit_on_end": False}
    (ws / ".vacant" / "contract.json").write_text(_json.dumps(raw))
    C.lock(ws / ".vacant" / "contract.json")
    base = {"session_id": "s", "cwd": str(ws)}
    hook.handle("claude", "SubagentStart", {**base, "agent_id": "a1", "agent_type": "general-purpose"})
    out, _err, _rc = hook.handle("claude", "Stop", {**base, "stop_hook_active": False})
    assert "block" not in out                                  # 不催主 agent
    hook.handle("claude", "SubagentStop", {**base, "agent_id": "a1", "agent_type": "general-purpose"})
    out, _err, _rc = hook.handle("claude", "Stop", {**base, "stop_hook_active": False})
    assert '"block"' in out and "report.md" in out            # 子 agent 回報之後照常驗收


def test_a_missed_subagent_stop_does_not_block_checks_forever(ws, monkeypatch):
    rec = R.Recorder(ws)
    rec.subagent_state(R.Actor("claude", "s", agent="a1"), running=True)
    assert rec.running_subagents("claude:s") == ["claude:s:a1"]
    assert rec.running_subagents("claude:s", max_age=0) == []
    assert rec.running_subagents("claude:other") == []
