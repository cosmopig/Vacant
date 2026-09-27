"""gateshim 替 pi 寫的 per-run 設定（2026-09-24 接 Gemini 實測抓到的兩件事）。

1. pi 預設送 `"store": false`，Gemini 的 OpenAI 相容端點回 400 ⇒ per-run compat 要 `supportsStore: False`。
2. 使用者在自己的 `settings.json` 調長 `retry`（免費層 429 要等 47 秒），shim 那一跑換成暫存設定目錄
   ⇒ 那份設定不見 ⇒ agent 放棄 ⇒ 閘門判拒交。失敗被算成 agent 的，其實是設定被丟掉。
   ⇒ `retry` 要帶進來，而且**只帶這一塊**。
"""
from __future__ import annotations

import json
import pathlib

import pytest

from vacant_network.vrun import gateshim


class _Execd(Exception):
    pass


def _exec_pi(tmp_path: pathlib.Path, monkeypatch, user_settings: dict | None) -> dict:
    home = tmp_path / "home"
    agent_dir = home / ".pi" / "agent"
    agent_dir.mkdir(parents=True)
    if user_settings is not None:
        (agent_dir / "settings.json").write_text(json.dumps(user_settings), "utf-8")
    cfg = tmp_path / "cfg"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("PI_CODING_AGENT_DIR", raising=False)
    monkeypatch.setenv("VACANT_RUN_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("VACANT_POSSESS_REAL_BIN", "/bin/true")
    monkeypatch.setenv("VACANT_POSSESS_CFG", str(cfg))
    monkeypatch.setenv("VACANT_AGENT_MODEL", "some-model")

    def fake_execve(path, args, env):
        raise _Execd(env)
    monkeypatch.setattr(gateshim.os, "execve", fake_execve)
    with pytest.raises(_Execd):
        gateshim.exec_inner("pi", ["-p", "x"])
    return {"settings": json.loads((cfg / "settings.json").read_text("utf-8")),
            "models": json.loads((cfg / "models.json").read_text("utf-8"))}


def test_per_run_pi_compat_does_not_send_store(tmp_path, monkeypatch):
    out = _exec_pi(tmp_path, monkeypatch, None)
    compat = out["models"]["providers"]["vacant"]["compat"]
    assert compat["supportsStore"] is False
    assert compat["supportsDeveloperRole"] is False and compat["supportsReasoningEffort"] is False


def test_per_run_pi_settings_carry_users_retry_and_nothing_else(tmp_path, monkeypatch):
    retry = {"maxRetries": 8, "baseDelayMs": 15000, "maxAgentDelayMs": 90000,
             "provider": {"maxRetryDelayMs": 0}}
    out = _exec_pi(tmp_path, monkeypatch, {
        "retry": retry, "defaultProvider": "gemini", "defaultModel": "x",
        "packages": ["npm:something"], "theme": "dark"})
    s = out["settings"]
    assert s["retry"] == retry
    # 這一跑的形狀不准被使用者其他設定改掉：預設 provider 仍是 vacant，其他鍵不帶
    assert s["defaultProvider"] == "vacant" and s["defaultModel"] == "some-model"
    assert set(s) == {"defaultProvider", "defaultModel", "retry"}


@pytest.mark.parametrize("user_settings", [None, {}, {"retry": "nope"}, {"theme": "dark"}])
def test_per_run_pi_settings_without_usable_retry_stay_as_before(tmp_path, monkeypatch,
                                                                 user_settings):
    s = _exec_pi(tmp_path, monkeypatch, user_settings)["settings"]
    assert s == {"defaultProvider": "vacant", "defaultModel": "some-model"}
