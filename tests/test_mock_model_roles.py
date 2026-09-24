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
