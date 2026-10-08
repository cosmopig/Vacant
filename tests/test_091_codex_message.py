"""0.9.1：Codex 的 Stop 也要把「給人的訊息」送到人眼前（`adapters/hook.render`），
以及延後驗收（子 agent 還在跑）時一串只提示一次。

Codex 的 Stop 在 exit 0 時 stdout 為 JSON，`systemMessage` 是通用輸出欄位（只給人看、不進模型）。
誠實邊界：文件沒寫 exit 0 時 stderr 是否顯示，所以不走 stderr。"""
from __future__ import annotations

import json

import pytest

from vacant_network.adapters import hook
from vacant_network.adapters.hook import HookDecision, HookEvent
from vacant_network.intake import keys


def _ev(agent="codex", kind="stop"):
    return HookEvent(agent=agent, kind=kind, tool=None, command=None, paths=[], cwd=".",
                     session_id="s", stop_hook_active=False, reason=None)


def test_codex_stop_renders_user_message_as_system_message():
    d = HookDecision("allow", "", {"user_message": "Vacant check did not run"})
    out, err, code = hook.render("codex", _ev(), d)
    assert json.loads(out) == {"systemMessage": "Vacant check did not run"}
    assert err == "" and code == 0


def test_codex_stop_without_message_stays_empty_and_block_keeps_only_reason():
    assert hook.render("codex", _ev(), HookDecision("allow")) == ("", "", 0)
    d = HookDecision("continue", "fix X", {"user_message": "人看的"})
    out, _e, _c = hook.render("codex", _ev(), d)
    assert json.loads(out) == {"decision": "block", "reason": "fix X"}   # 模型只收到 reason


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    monkeypatch.setenv("VACANT_TRACE", "1")
    monkeypatch.setattr(hook, "_zero_mode", lambda: "evidence")
    keys.init_local()
    w = tmp_path / "proj"
    w.mkdir()
    return w


def test_deferral_tells_the_person_once_per_streak(ws):
    base = {"session_id": "s", "cwd": str(ws)}
    hook.handle("codex", "SubagentStart", {**base, "agent_id": "a1"})
    msgs = []
    for _ in range(3):
        out, _e, _c = hook.handle("codex", "Stop", {**base, "stop_hook_active": False})
        msgs.append(json.loads(out).get("systemMessage") if out else None)
    assert msgs == [hook.DEFER_NOTICE, None, None]
    assert "subagent is still running" in hook.DEFER_NOTICE
