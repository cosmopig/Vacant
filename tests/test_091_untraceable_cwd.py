"""零設定在 cwd 太大（`/`、家目錄、agent 的設定目錄）時不再沉默（2026-10 事件：pi 在 `/` 開，
49 個步驟一步都沒記、放行、人沒被告知）。那個目錄照樣不掃；Stop 告訴人「沒查」，一個工作階段一次；
事件紀錄分得出「沒查」（`zero_ran: false, why: untraceable_cwd`）和「查過」。"""
import json

import pytest

from vacant_network.adapters import hook
from vacant_network.adapters import install as INS
from vacant_network.adapters.hookpolicy import vacant_state_dir
from vacant_network.trace import capture, zerostop


def _install(mode="evidence"):
    p = INS.state_root() / "install.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"agents": {}, "mode": mode}))


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    for k in ("VACANT_TRACE", "VACANT_MODE", "VACANT_HOOK_NO_STOP", "VACANT_FEEDBACK_MODE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(zerostop, "_run_child", zerostop.check)
    return tmp_path


def _events():
    p = vacant_state_dir() / "intake" / "hooks" / "events.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines()] if p.is_file() else []


def _claude_stop(cwd, session="S"):
    out, err, code = hook.handle("claude", "Stop", {
        "session_id": session, "cwd": str(cwd), "hook_event_name": "Stop",
        "stop_hook_active": False, "last_assistant_message": "Done."})
    assert code == 0 and err == ""
    return json.loads(out) if out else {}


def _pi_stop(cwd, session="P"):
    out, _, code = hook.handle("pi", "stop", {"session_id": session, "cwd": str(cwd),
                                              "final_text": "Done."})
    assert code == 0
    return json.loads(out)


@pytest.mark.parametrize("where", ["home", "root"])
def test_claude_is_told_once_per_session_that_nothing_was_checked(env, where):
    _install()
    cwd = env / "home" if where == "home" else "/"
    hook.handle("claude", "PreToolUse", {"session_id": "S", "cwd": str(cwd), "tool_name": "Bash",
                                         "tool_use_id": "t1", "tool_input": {"command": "ls"}})
    d = _claude_stop(cwd)
    msg = d["systemMessage"]
    assert msg.startswith("Vacant did not check this work") and "project folder" in msg
    assert "decision" not in d
    stop = [e for e in _events() if e["kind"] == "stop"][-1]
    assert stop["zero_ran"] is False and stop["why"] == "untraceable_cwd"
    assert stop["zero"] == {"ran": False, "why": "untraceable_cwd"}
    assert "user_message" not in stop                      # 給人的字不進事件紀錄
    # 同一個工作階段的下一次 Stop 不再說；紀錄照樣寫「沒查」
    assert _claude_stop(cwd) == {}
    assert [e for e in _events() if e["kind"] == "stop"][-1]["zero_ran"] is False
    # 別的工作階段再說一次
    assert "systemMessage" in _claude_stop(cwd, session="S2")
    assert not list((env / "vh").rglob("chain*.jsonl"))    # 那個目錄照樣沒有被記


def test_pi_gets_the_note_for_the_person_not_a_continue(env):
    _install()
    d = _pi_stop(env / "home")
    assert d["action"] == "allow" and d["reason"] == ""
    assert d["note"].startswith("Vacant did not check this work")


def test_observe_mode_records_not_ran_without_a_message(env):
    _install("observe")
    assert _claude_stop("/") == {}
    stop = [e for e in _events() if e["kind"] == "stop"][-1]
    assert stop["zero_ran"] is False and stop["why"] == "untraceable_cwd"


def test_not_installed_stays_silent(env):
    assert _claude_stop("/") == {}
    assert zerostop.untraceable("claude", "S", "/", "off") == {}


def test_agent_config_dirs_are_not_workspaces(env):
    _install()
    home = env / "home"
    for cd in (".pi", ".claude", ".codex", ".config/opencode", ".config", ".pi/agent/sessions"):
        (home / cd).mkdir(parents=True, exist_ok=True)
        assert capture.workspace_for(str(home / cd)) is None, cd
        assert capture.untraceable_cwd(str(home / cd)) is not None, cd
    proj = home / "code" / "proj"
    proj.mkdir(parents=True)
    assert capture.workspace_for(str(proj)) == proj.resolve()
    assert capture.untraceable_cwd(str(proj)) is None


def test_a_normal_project_still_gets_sent_back_for_a_missing_output(env):
    _install()
    p = env / "work" / "proj"
    p.mkdir(parents=True)
    (p / ".git").mkdir()
    base = {"session_id": "N", "cwd": str(p)}
    hook.handle("claude", "UserPromptSubmit", {**base, "prompt": "Write the answer to answer.txt."})
    pre = {**base, "tool_name": "Bash", "tool_use_id": "t1", "tool_input": {"command": "echo 42"}}
    hook.handle("claude", "PreToolUse", pre)
    hook.handle("claude", "PostToolUse", {**pre, "tool_response": {"stdout": "42\n", "stderr": ""}})
    d = _claude_stop(p, session="N")
    assert d.get("decision") == "block" and "answer.txt" in d["reason"]
    assert "Vacant did not check" not in d["reason"]
    stop = [e for e in _events() if e["kind"] == "stop"][-1]
    assert stop["zero_ran"] is True and "why" not in stop
