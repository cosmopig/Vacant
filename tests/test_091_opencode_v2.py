"""OpenCode 外掛的雙形狀（1.18.x 的 `server`＋2.x 的 `setup`）與三個缺陷的回歸。

OpenCode 2.x 的載入器只收「default export 是帶 `id` 與 `setup`／`effect` 函式的物件」；
舊的裸函式 default 在那裡被拒、Vacant 安靜地沒有作用。這裡用 node 載入**產生出來的** vacant.js，
餵假的 v1／v2 ctx（掛鉤指令換成一支記錄事件的假腳本）：
- default 是 `{ id, server, setup }`、沒有具名匯出；
- 1.18.35 的預覽 ctx（沒有 tool／session／event／location）⇒ `setup` 什麼都不做；
- 回饋送出前先把 session 移出 busy ⇒ 回饋那一回合結束時會跑第二次檢查（1.x 的 idle、2.x 的
  `session.execution.succeeded`——2.0.24 不把 `session.idle` 交給外掛，實測）；
- stop 帶 `final_text`；每個根 session 各自收到 `session_end`；子 session 的 idle 不檢查。
⚠ 誠實邊界：這裡的 ctx 是假的，驗的是形狀與我們自己的邏輯，**不是** OpenCode 的載入器或真的 agent。
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess

import pytest

from vacant_network.adapters import agents as A

HARNESS = pathlib.Path(__file__).with_name("opencode_plugin_harness.mjs")
NODE = shutil.which("node")

FAKE_HOOK = r"""
import { appendFileSync, readFileSync } from "node:fs";
const event = process.argv[process.argv.length - 1];
const payload = JSON.parse(readFileSync(0, "utf-8") || "{}");
appendFileSync(process.env.VACANT_FAKE_LOG, JSON.stringify({ event, payload }) + "\n");
let out = { action: "allow" };
if (event === "pre_tool" && JSON.stringify(payload.input || {}).includes("DENYME")) out = { action: "deny", reason: "nope" };
if (event === "stop") out = { action: "continue", reason: "Vacant check: report.md is missing." };
process.stdout.write(JSON.stringify(out) + "\n");
"""


def test_default_export_is_one_object_with_id_server_and_setup():
    text = A.opencode_plugin_text()
    assert "export default { id: \"vacant\", server, setup };" in text
    assert "export const" not in text and "export default VacantPlugin" not in text
    assert "if (!ctx?.tool || !ctx?.session || !ctx?.event || !ctx?.location) return;" in text
    # `opencode run` 由 `vacant do` 明講，不靠 argv（2.x 的外掛跑在另一個 serve 行程）
    assert "VACANT_OPENCODE_NONINTERACTIVE" in text


def test_vacant_do_marks_opencode_run_noninteractive(tmp_path):
    la = A.opencode_build("p", tmp_path)
    assert la.env.get("VACANT_OPENCODE_NONINTERACTIVE") == "1"
    if la.cleanup:
        la.cleanup()


def _run(tmp_path, monkeypatch, mode: str) -> dict:
    fake = tmp_path / "fakehook.mjs"
    fake.write_text(FAKE_HOOK, encoding="utf-8")
    monkeypatch.setattr(A, "hook_argv", lambda agent, ev: [NODE, str(fake), agent, ev])
    plugin = tmp_path / "vacant.js"
    plugin.write_text(A.opencode_plugin_text(), encoding="utf-8")
    log = tmp_path / "events.jsonl"
    log.write_text("")
    env = {"PATH": "/usr/bin:/bin", "VACANT_FAKE_LOG": str(log), "VACANT_OPENCODE_NONINTERACTIVE": "0"}
    p = subprocess.run([NODE, str(HARNESS), str(plugin), mode], capture_output=True, text=True,
                       timeout=60, env=env)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(NODE is None, reason="這台機器沒有 node")
def test_shape_and_preview_ctx(tmp_path, monkeypatch):
    r = _run(tmp_path, monkeypatch, "v2")
    assert r["named_exports"] == []
    assert r["default_is_object"] and r["id"] == "vacant"
    assert r["has_setup"] and r["has_server"] and not r["has_effect"]
    assert r.get("preview_setup") is None and r.get("preview_setup_null") is None


@pytest.mark.skipif(NODE is None, reason="這台機器沒有 node")
def test_v2_setup_hooks_feedback_two_rounds_final_text_and_per_session_end(tmp_path, monkeypatch):
    r = _run(tmp_path, monkeypatch, "v2")
    assert r["v2_hooks"] == ["session:prompt", "tool:execute.after", "tool:execute.before"]
    assert r["v2_cleanup_is_function"] and r["subscribe_has_signal"] and r["v2_disposed"] == 3
    assert r["v2_deny_message"] == "nope"
    # 兩輪回饋都送到（第二輪＝回饋那一回合結束的 idle），用 v2 的 session.prompt
    assert [p["sessionID"] for p in r["v2_prompts"]] == ["S1", "S1"]
    assert all(p["text"].startswith("Vacant check") for p in r["v2_prompts"])
    ev = r["v2_events"]
    stops = [e["payload"] for e in ev if e["event"] == "stop"]
    assert [s["session_id"] for s in stops] == ["S1", "S1"]          # 子 session K1 不檢查
    assert stops[0]["final_text"] == "All tests pass." and stops[1]["final_text"] == "Fixed."
    assert stops[0]["cwd"] == "/w/proj"
    ends = sorted(e["payload"]["session_id"] for e in ev if e["event"] == "session_end")
    assert ends == ["S1", "S2"]
    pre = [e["payload"] for e in ev if e["event"] == "pre_tool"]
    assert pre[0]["call_id"] == "c1" and pre[0]["input"] == {"filePath": "r.md"}
    k1 = [x for x in pre if x["session_id"] == "K1"][0]
    assert k1["parent_session_id"] == "S1" and k1["root_session_id"] == "S1"   # 只靠 session.get 認出
    post = [e["payload"] for e in ev if e["event"] == "post_tool"]
    assert post[0]["output"] == "wrote r.md"
    assert [e["payload"]["prompt"] for e in ev if e["event"] == "prompt"] == ["write report.md"]


@pytest.mark.skipif(NODE is None, reason="這台機器沒有 node")
def test_v1_server_uses_prompt_async_and_ends_every_root_session(tmp_path, monkeypatch):
    r = _run(tmp_path, monkeypatch, "v1")
    assert {"tool.execute.before", "tool.execute.after", "chat.message", "event", "dispose"} <= set(r["v1_hooks"])
    assert [p["path"]["id"] for p in r["v1_prompts"]] == ["S1", "S1"]   # 第二輪沒被 busy 吞掉
    ev = r["v1_events"]
    stops = [e["payload"] for e in ev if e["event"] == "stop"]
    assert [s["session_id"] for s in stops] == ["S1", "S1"]
    assert stops[0]["final_text"] == "Done, tests pass."               # 合成的部分不算
    ends = sorted(e["payload"]["session_id"] for e in ev if e["event"] == "session_end")
    assert ends == ["S1", "S2"]                                         # 兩次 dispose 也只各一次
    # server() 之後再來一個完整的 v2 ctx：不重複掛
    assert r["v1_then_setup"] == {"returned": None, "hooked": []}
