"""假模型（`ops/intake/mock_model.py`）演子 agent：角色從對話開頭的使用者訊息來、委派用各家自己的工具。

這支測的是**劇本機制**（L-fake 的一部分），不是任何模型的行為。"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "mock_model", pathlib.Path(__file__).resolve().parents[1] / "ops" / "intake" / "mock_model.py")
M = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(M)

SCN = {"steps": [{"agent": {"prompt": "ROLE:sub do it", "description": "d", "pi_agent": "w"}},
                 {"run": "cat figure.txt"}],
       "final": "main done",
       "roles": {"sub": {"steps": [{"run": "echo 96 > figure.txt"}], "final": "sub done"}}}
BASH = {"name": "Bash", "input_schema": {"properties": {"command": {"type": "string"}}}}


@pytest.fixture(autouse=True)
def scenario(tmp_path, monkeypatch):
    f = tmp_path / "s.json"
    f.write_text(json.dumps(SCN))
    monkeypatch.setenv("MOCK_SCENARIO", str(f))


def test_role_comes_from_the_opening_user_messages_only():
    msgs = [{"role": "system", "content": "x"},
            {"role": "user", "content": [{"type": "text", "text": "<env/>"}]},
            {"role": "user", "content": "ROLE:sub go"},
            {"role": "assistant", "content": "ROLE:main"}]
    assert M.role_of(M.opening_user_text(msgs)) == "sub"
    later = [{"role": "user", "content": "task"}, {"role": "assistant", "content": "ok"},
             {"role": "user", "content": "ROLE:sub result echoed back"}]
    assert M.role_of(M.opening_user_text(later)) is None       # 主 agent 不會因為回報變成子 agent


@pytest.mark.parametrize("tools,name,key", [
    ([{"name": "Agent", "input_schema": {"properties": {"prompt": {}, "run_in_background": {}}}},
      BASH], "Agent", "prompt"),
    ([{"type": "function", "function": {"name": "task", "parameters": {}}}], "task", "prompt"),
    ([{"type": "function", "function": {"name": "subagent", "parameters": {}}}], "subagent",
     "task"),
    ([{"type": "namespace", "name": "multi_agent_v1",
       "tools": [{"type": "function", "name": "spawn_agent"}]}],
     "multi_agent_v1/spawn_agent", "message"),
])
def test_each_agent_delegates_with_its_own_tool(tools, name, key):
    kind, tool, args = M.plan(0, tools, None)
    assert (kind, tool) == ("tool", name) and "ROLE:sub" in args[key]
    if name == "Agent":
        assert args["run_in_background"] is False               # 前景：做完才往下


def test_codex_waits_for_the_spawned_agent_then_continues():
    ns = [{"type": "namespace", "name": "multi_agent_v1",
           "tools": [{"type": "function", "name": "spawn_agent"}]},
          {"type": "function", "name": "exec_command",
           "parameters": {"properties": {"cmd": {"type": "string"}}}}]
    assert M.plan(1, ns, None, last_agent_id="a-1")[1:] == (
        "multi_agent_v1/wait_agent", {"targets": ["a-1"], "timeout_ms": 120000})
    assert M.plan(2, ns, None)[1] == "exec_command"


def test_the_sub_agent_plays_its_own_script():
    assert M.plan(0, [BASH], None, role="sub")[2] == {"command": "echo 96 > figure.txt"}
    assert M.plan(1, [BASH], None, role="sub") == ("text", "sub done", None)


TURNS = {"turns": [
    {"when": "How many rows", "steps": [{"run": "cat a.csv"}], "final": "3 rows.",
     "fix": {"steps": [], "final": "I'll wait."}},
    {"when": "Now write", "steps": [{"run": "echo 999 > r.md"}], "final": "Done.",
     "fix": {"steps": [{"run": "echo 69 > r.md"}], "final": "Fixed."}}]}


def _chat_plan(msgs):
    sec, pos = M.pick_turn([(i, M._text_of(m.get("content"))) for i, m in enumerate(msgs)
                            if m.get("role") == "user"])
    fed, k = M.split_on_feedback(msgs[pos + 1:], lambda m: m.get("role") == "tool",
                                 lambda m: json.dumps(m.get("content")))
    return M.plan(k, [BASH], None, fed, None, section=sec)


def test_turns_follow_the_latest_message_the_person_typed(tmp_path, monkeypatch):
    """互動介面的多回合：人最近打的那一則決定演哪一段；回饋被送回來的那幾則不算人打的；
    工具結果與回饋只數那一則之後的（前一回合的回饋不會讓這一回合一開始就演 `fix`）。"""
    f = tmp_path / "t.json"
    f.write_text(json.dumps(TURNS))
    monkeypatch.setenv("MOCK_SCENARIO", str(f))
    fb = M.FEEDBACK_MARK + " (…)"
    t1 = [{"role": "user", "content": "How many rows are there?"}]
    assert _chat_plan(t1)[:2] == ("tool", "Bash")
    t1 += [{"role": "assistant", "content": None}, {"role": "tool", "content": "id\n1\n2\n3"},
           {"role": "assistant", "content": "3 rows."}, {"role": "user", "content": fb}]
    assert _chat_plan(t1) == ("text", "I'll wait.", None)            # 第一回合的 fix 段
    t2 = t1 + [{"role": "assistant", "content": "I'll wait."},
               {"role": "user", "content": "Now write the report"}]
    kind, name, args = _chat_plan(t2)
    assert kind == "tool" and "999" in json.dumps(args)             # 第二回合從頭演，不是 fix
    t2 += [{"role": "assistant", "content": None}, {"role": "tool", "content": ""},
           {"role": "assistant", "content": "Done."}, {"role": "user", "content": fb}]
    kind, name, args = _chat_plan(t2)
    assert kind == "tool" and "69" in json.dumps(args)              # 第二回合的回饋 ⇒ 它的 fix 段


def test_without_turns_the_whole_conversation_counts_as_before():
    assert M.pick_turn([(0, "anything")]) == (None, -1)


@pytest.mark.parametrize("headers, ok", [
    ({"x-api-key": "sk-fake-offline-000"}, True),
    ({"authorization": "Bearer sk-fake"}, True),
    ({}, True),                                                     # 沒帶：不是它能驗的
    ({"authorization": "Bearer something-else-123"}, False),
    ({"x-api-key": "sk-fake-offline-000", "authorization": "Bearer other-456"}, False),
])
def test_the_mock_only_takes_the_experiments_fake_key(tmp_path, monkeypatch, headers, ok):
    """一跑成功本身就證明 agent 用的是假金鑰；別的憑證被拒，而且值不進紀錄。"""
    import http.server
    import threading
    import urllib.error
    import urllib.request
    log = tmp_path / "mock.jsonl"
    monkeypatch.setattr(M, "LOG", str(log))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), M.H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{srv.server_address[1]}/v1/chat/completions",
            data=json.dumps({"messages": [{"role": "user", "content": "hi"}]}).encode(),
            headers={"content-type": "application/json", **headers}, method="POST")
        try:
            code = urllib.request.urlopen(req, timeout=10).status
        except urllib.error.HTTPError as e:
            code = e.code
    finally:
        srv.shutdown()
    assert (code == 200) is ok and (code == 401) is (not ok)
    text = log.read_text()
    assert ('"auth": "rejected"' in text) is (not ok)
    assert "something-else-123" not in text and "other-456" not in text
