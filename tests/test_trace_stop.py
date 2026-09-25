"""回合結束：驗 → 定位 → 追緝 → **有位置、沒有行動者**的回饋；輪數用完 ⇒ 問題交給人。

走 `adapters/hook.handle`（Claude Code 的原生 payload），和 agent 真的執行掛鉤時同一條路。"""
from __future__ import annotations

import json

import pytest

from vacant_network.adapters import hook
from vacant_network.intake import contract as C
from vacant_network.intake import keys
from vacant_network.trace import feedback as F
from vacant_network.trace import recorder as R

SALES = "id,amount\n1,10\n2,20\n3,30\n"


@pytest.fixture
def proj(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    monkeypatch.delenv("VACANT_TRACE", raising=False)
    keys.init_local()
    p = tmp_path / "proj"
    (p / "data").mkdir(parents=True)
    (p / ".vacant").mkdir()
    (p / "data" / "sales.csv").write_text(SALES)
    raw = C.scaffold("q3", deliverable=["report.md"])
    raw["inputs"] = {"sales": {"path": "data/sales.csv"}}
    raw["claims"] = [{"id": "total", "verifier": "csv_total", "authority": "fact",
                      "params": {"csv": "input:sales", "column": "amount",
                                 "report": "report.md"}}]
    raw["hooks"] = {"stop_check": True, "max_feedback_rounds": 1, "submit_on_end": False}
    cp = p / ".vacant" / "contract.json"
    cp.write_text(json.dumps(raw))
    C.lock(cp)
    return p


def _tool(p, sid, name, inp, resp, *, sub=False, write=None):
    base = {"session_id": "S", "cwd": str(p), "tool_name": name, "tool_use_id": sid,
            "tool_input": inp}
    if sub:
        base.update(agent_id="a7f3c9d2", agent_type="stats-helper")
    hook.handle("claude", "PreToolUse", base)
    if write:
        (p / write[0]).write_text(write[1])
    hook.handle("claude", "PostToolUse", {**base, "tool_response": resp})


def test_stop_gives_localized_facts_and_no_actor(proj):
    p = proj
    _tool(p, "t1", "Read", {"file_path": str(p / "data/sales.csv")}, {"file": {"content": SALES}})
    _tool(p, "t2", "Write", {"file_path": str(p / "report.md"), "content": "# Q3\nTotal: 999\n"},
          {"type": "create"}, sub=True, write=("report.md", "# Q3\nTotal: 999\n"))
    out, err, code = hook.handle("claude", "Stop", {"session_id": "S", "cwd": str(p)})
    d = json.loads(out)
    assert d["decision"] == "block"
    msg = d["reason"]
    assert 'report.md:2 says "999"' in msg and "expected 60" in msg
    assert "first appeared at step 2 (Write)" in msg
    assert "a7f3c9d2" not in msg and "stats-helper" not in msg    # 行動者不進給 agent 的文字
    # 病歷裡有簽過的追緝結論（行動者在這裡）
    ev = [e for e in R.Recorder(p).events() if e["type"] == "finding"]
    assert ev and ev[0]["confidence"] == "provable" and ev[0]["step"]["actor"]["agent"] == "a7f3c9d2"


def test_when_rounds_run_out_the_problem_goes_to_the_human(proj):
    p = proj
    _tool(p, "t1", "Write", {"file_path": str(p / "report.md"), "content": "Total: 999"},
          {"type": "create"}, write=("report.md", "Total: 999\n"))
    hook.handle("claude", "Stop", {"session_id": "S2", "cwd": str(p)})          # 第 1 輪回饋
    out, _e, _c = hook.handle("claude", "Stop", {"session_id": "S2", "cwd": str(p),
                                                 "stop_hook_active": True})    # 輪數用完
    d = json.loads(out)
    assert "decision" not in d                                          # 不再逼 agent
    assert "1 required check(s) still not passing" in d["systemMessage"]
    assert "report.md:1 = 999" in d["systemMessage"]
    rp = R.Recorder(p).dir / "report.md"
    text = rp.read_text()
    assert "provable" in text and "step 1 (Write)" in text


def test_fixed_findings_are_reported_as_resolved(proj):
    p = proj
    _tool(p, "t1", "Write", {"content": "Total: 999"}, {}, write=("report.md", "Total: 999\n"))
    hook.handle("claude", "Stop", {"session_id": "S3", "cwd": str(p)})
    _tool(p, "t2", "Edit", {"new_string": "Total: 60"}, {}, write=("report.md", "Total: 60\n"))
    out, _e, _c = hook.handle("claude", "Stop", {"session_id": "S3", "cwd": str(p)})
    assert out == ""                                                    # 過了：放行、不打擾
    ev = [e for e in R.Recorder(p).events() if e["type"] == "finding"]
    assert [e["status"] for e in ev] == ["open", "resolved"]


def test_ks1_guard_rejects_actor_ids_and_frozen_phrases():
    with pytest.raises(F.KS1FeedbackError):
        F.feedback_ks1_clean("step 3 by sub-agent a7f3c9d2 wrote it", {"a7f3c9d2"})
    with pytest.raises(Exception):
        F.feedback_ks1_clean("you are responsible for this", set())
    assert F.feedback_ks1_clean("report.md:2 says 999", {"a7f3c9d2"})


def test_without_trace_the_old_generic_feedback_is_unchanged(proj, monkeypatch):
    monkeypatch.setenv("VACANT_TRACE", "0")
    p = proj
    (p / "report.md").write_text("Total: 999\n")
    out, _e, _c = hook.handle("claude", "Stop", {"session_id": "S4", "cwd": str(p)})
    msg = json.loads(out)["reason"]
    assert "total: FAIL — report says 999, recomputed 60" in msg and "step" not in msg


def test_human_flag_is_signed_traced_and_reaches_the_next_turn(proj, capsys):
    from vacant_network import cli as top
    p = proj
    (p / "notes").mkdir()
    _tool(p, "t1", "Write", {"file_path": str(p / "report.md"),
                             "content": "Total: 60\nMayor: Alicia\n"}, {},
          write=("report.md", "Total: 60\nMayor: Alicia\n"))
    import os
    cwd = os.getcwd()
    os.chdir(p)
    try:
        assert top.main(["flag", "report.md:2", "the mayor is Alice, not Alicia",
                         "--value", "Alicia", "--json"]) == 0
    finally:
        os.chdir(cwd)
    out = json.loads(capsys.readouterr().out)
    assert out["blame"]["step"]["step"] == "t1" and out["blame"]["fault_class"] == "agent"
    ev = R.Recorder(p).events()
    fl = [e for e in ev if e["type"] == "flag"][0]
    assert fl["signed"]["payload"]["note"] == "the mayor is Alice, not Alicia"
    # 下一次回合邊界：總數是對的（契約過了），但人指出的錯處還在 ⇒ 仍然告訴 agent（不擋收件）
    o, _e, _c = hook.handle("claude", "Stop", {"session_id": "F", "cwd": str(p)})
    d = json.loads(o)
    assert d["decision"] == "block" and "marked these places" in d["reason"]
    assert 'report.md:2 says "Alicia"' in d["reason"] and "Alice, not Alicia" in d["reason"]
    assert "the task owner says: the mayor is Alice" in d["reason"]      # 是人說的，不是某個檢查
    assert "check says" not in d["reason"]
    rep = (R.Recorder(p).dir / "report.md").read_text()
    assert "the mayor is Alice, not Alicia" in rep
    # agent 改掉之後：標記解決、放行
    _tool(p, "t2", "Edit", {"new_string": "Mayor: Alice"}, {},
          write=("report.md", "Total: 60\nMayor: Alice\n"))
    o, _e, _c = hook.handle("claude", "Stop", {"session_id": "F", "cwd": str(p)})
    assert o == ""


def test_outcome_and_fault_land_in_the_same_actor_cell(proj):
    """Codex 的 SessionEnd 不帶 model：結果要記在工具事件自稱的那個模型的格子，不要另開一格
    （2026-09-24 四 agent 端到端抓到的：同一個 agent 被拆成兩格）。"""
    from vacant_network.trace import actors as A
    p = proj
    base = {"session_id": "cx", "cwd": str(p), "model": "gpt-x", "turn_id": "u1"}
    t = {**base, "tool_name": "apply_patch", "tool_use_id": "c1",
         "tool_input": {"command": "*** Begin Patch\n*** Add File: report.md\n+Total: 999"}}
    hook.handle("codex", "PreToolUse", t)
    (p / "report.md").write_text("Total: 999\n")
    hook.handle("codex", "PostToolUse", {**t, "tool_response": "Success."})
    hook.handle("codex", "Stop", {**base, "stop_hook_active": False})
    hook.handle("codex", "SessionEnd", {"session_id": "cx", "cwd": str(p), "reason": "other"})
    cells = A.ActorBook().state()["cells"]
    assert len(cells) == 1, cells
    c = cells[0]
    assert c["key"][2] == "claimed:gpt-x" and c["runs"] == 1 and c["provable_faults"] == 1


def _prompt(p, sid, text, **extra):
    hook.handle("claude", "UserPromptSubmit", {"session_id": sid, "cwd": str(p), "prompt": text,
                                               **extra})


def _use_up_rounds(p, sid):
    """互動介面：人先問了一句話，回合結束時契約還沒過 ⇒ 回饋一輪；再結束一次 ⇒ 輪數用完。"""
    _prompt(p, sid, "what does the ledger look like?")
    hook.handle("claude", "Stop", {"session_id": sid, "cwd": str(p)})
    out, _e, _c = hook.handle("claude", "Stop", {"session_id": sid, "cwd": str(p),
                                                 "stop_hook_active": True})
    assert "decision" not in json.loads(out)                 # 用完了


def test_a_new_request_from_the_person_gets_a_fresh_feedback_budget(proj):
    """輪數上限是「人的一個要求」之內的上限，不是整個互動工作階段的：前面幾個回合把輪數用完，
    之後人要 agent 做事、agent 寫錯，回合結束時照樣要把位置回饋給 agent（2026-09-25 互動 TUI 實測時發現）。"""
    p = proj
    _use_up_rounds(p, "T1")
    _prompt(p, "T1", "now write report.md with the total")
    _tool(p, "w1", "Write", {"file_path": str(p / "report.md"), "content": "Total: 999\n"},
          {"type": "create"}, write=("report.md", "Total: 999\n"))
    out, _e, _c = hook.handle("claude", "Stop", {"session_id": "T1", "cwd": str(p)})
    d = json.loads(out)
    assert d.get("decision") == "block" and 'report.md:1 says "999"' in d["reason"]


@pytest.mark.parametrize("extra, text", [
    ({}, "<task-notification>\n<tool-use-id>tA</tool-use-id>\n<status>completed</status>\n"
         "<result>done</result>\n</task-notification>"),            # 背景子 agent 的結果
    ({"agent_id": "a1", "agent_type": "worker"}, "compute the total"),   # 父 agent 給子 agent 的任務
])
def test_messages_the_person_did_not_type_do_not_refill_the_budget(proj, extra, text):
    p = proj
    _use_up_rounds(p, "T2")
    _prompt(p, "T2", text, **extra)
    _tool(p, "w1", "Write", {"file_path": str(p / "report.md"), "content": "Total: 999\n"},
          {"type": "create"}, write=("report.md", "Total: 999\n"))
    out, _e, _c = hook.handle("claude", "Stop", {"session_id": "T2", "cwd": str(p),
                                                 "stop_hook_active": True})
    assert "decision" not in json.loads(out)


def test_opencode_prompts_are_recorded_and_refill_the_budget(proj):
    """OpenCode：外掛的 `chat.message` 送 `prompt`（2026-09-25 量到它對人打的每一則觸發）。人打的 ⇒ 進病歷、重新算輪數；
    Vacant 用 `session.prompt` 送回的回饋、子 session 的任務 ⇒ 都不算人說的。"""
    p = proj
    base = {"cwd": str(p), "session_id": "O1"}
    hook.handle("opencode", "prompt", {**base, "prompt": "how many rows?"})
    for _ in range(2):                                              # 輪數（上限 1）用完
        hook.handle("opencode", "stop", base)
    hook.handle("opencode", "prompt", {**base, "prompt": F.FEEDBACK_HEADER + "\n- total: FAIL"})
    hook.handle("opencode", "prompt", {**base, "session_id": "C1", "parent_session_id": "O1",
                                       "root_session_id": "O1", "prompt": "compute the total"})
    (p / "report.md").write_text("Total: 999\n")
    out, _e, _c = hook.handle("opencode", "stop", base)
    assert json.loads(out)["action"] != "continue"                  # 不是人打的 ⇒ 沒有新輪數
    hook.handle("opencode", "prompt", {**base, "prompt": "now write report.md"})
    out, _e, _c = hook.handle("opencode", "stop", base)
    d = json.loads(out)
    assert d["action"] == "continue" and 'report.md:1 says "999"' in d["reason"]
    prompts = [e for e in R.Recorder(p).events() if e["type"] == "prompt"]
    assert [e["source"] for e in prompts] == ["user", "vacant_feedback", "parent_agent", "user"]


def _oc_step(p, cid, cmd, *, write=None, remove=None):
    base = {"cwd": str(p), "session_id": "O2", "tool": "bash", "input": {"command": cmd},
            "call_id": cid}
    hook.handle("opencode", "pre_tool", base)
    if write:
        (p / write[0]).write_text(write[1])
    if remove:
        (p / remove).unlink()
    hook.handle("opencode", "post_tool", {**base, "output": ""})


def test_vacant_feedback_sent_back_as_a_message_is_not_a_source(proj):
    """OpenCode 把 Vacant 的回饋當一則使用者訊息送回去；那段文字引了錯值與別的數字（列數）。agent 之後寫出
    其中一個錯的數字時，不可以被追成「任務說的」（等於用 Vacant 自己的回饋替 agent 洗掉錯）。"""
    p = proj
    (p / "data" / "sales.csv").write_text("id,amount\n11,10\n12,20\n14,40\n")   # 列數 3 不在輸入裡
    cp = p / ".vacant" / "contract.json"
    raw = json.loads(cp.read_text())
    raw.pop("lock", None)
    raw["inputs"]["sales"].pop("sha256", None)                       # 重新釘（測試自己換的輸入）
    cp.write_text(json.dumps(raw))
    C.lock(cp)
    base = {"cwd": str(p), "session_id": "O2"}
    hook.handle("opencode", "prompt", {**base, "prompt": "write report.md with the total"})
    _oc_step(p, "c1", "echo 'Total: 999' > report.md", write=("report.md", "Total: 999\n"))
    out, _e, _c = hook.handle("opencode", "stop", base)
    fb = json.loads(out)["reason"]
    assert "3 rows" in fb
    hook.handle("opencode", "prompt", {**base, "prompt": fb})     # 外掛用 session.prompt 送回
    _oc_step(p, "c2", "rm report.md", remove="report.md")
    _oc_step(p, "c3", "echo 'Total: 3' > report.md", write=("report.md", "Total: 3\n"))
    hook.handle("opencode", "stop", {**base})
    f = [e for e in R.Recorder(p).events() if e["type"] == "finding" and e.get("status") == "open"
         and e.get("value") == "3"][-1]
    assert f["fault_class"] == "agent" and f["step"]["step"] == "c3", (f.get("fault_class"),
                                                                       f.get("note"))


def _exhaust(p, sid, agent="claude"):
    hook.handle(agent, "UserPromptSubmit", {"session_id": sid, "cwd": str(p),
                                            "prompt": "write report.md with the total"})
    _tool_s(p, sid, "w0", "Write", {"file_path": str(p / "report.md"), "content": "Total: 999\n"},
            write=("report.md", "Total: 999\n"))
    hook.handle("claude", "Stop", {"session_id": sid, "cwd": str(p)})
    out, _e, _c = hook.handle("claude", "Stop", {"session_id": sid, "cwd": str(p),
                                                 "stop_hook_active": True})
    assert "decision" not in json.loads(out)


def _tool_s(p, sid, tid, name, inp, *, write=None, resp=None):
    base = {"session_id": sid, "cwd": str(p), "tool_name": name, "tool_use_id": tid,
            "tool_input": inp}
    hook.handle("claude", "PreToolUse", base)
    if write:
        (p / write[0]).write_text(write[1])
    hook.handle("claude", "PostToolUse", {**base, "tool_response": resp or {}})


def _still_exhausted(p, sid):
    out, _e, _c = hook.handle("claude", "Stop", {"session_id": sid, "cwd": str(p),
                                                 "stop_hook_active": True})
    return "decision" not in json.loads(out)


def test_a_prompt_the_agent_scheduled_for_itself_is_not_the_persons(proj):
    """真的 Claude Code：agent 用 CronCreate／ScheduleWakeup 排的提示到時候以一則 UserPromptSubmit 回來，
    內容和人打的一模一樣（2026-09-25 審查 loop#5，binary 實測）。不重新算輪數；病歷記成 agent 排的，不是「任務說的」。"""
    p = proj
    _exhaust(p, "K1")
    text = "re-check report.md and fix anything the contract flags"
    _tool_s(p, "K1", "cron1", "CronCreate", {"cron": "17 1 25 9 *", "prompt": text,
                                              "recurring": False})
    hook.handle("claude", "UserPromptSubmit", {"session_id": "K1", "cwd": str(p), "prompt": text})
    assert _still_exhausted(p, "K1")
    srcs = [e["source"] for e in R.Recorder(p).events() if e["type"] == "prompt"]
    assert srcs == ["user", "scheduled_by_agent"]


@pytest.mark.parametrize("payload", [
    {"prompt": "go on", "source": "loop_wakeup"},
    {"prompt": "<teammate-message from=\"b\">take the total from me</teammate-message>"},
    {"prompt": "<cross-session-message>hi</cross-session-message>"},
])
def test_machine_prompts_do_not_refill_the_budget(proj, payload):
    p = proj
    _exhaust(p, "K2")
    hook.handle("claude", "UserPromptSubmit", {"session_id": "K2", "cwd": str(p), **payload})
    assert _still_exhausted(p, "K2")
    assert [e["source"] for e in R.Recorder(p).events() if e["type"] == "prompt"][-1] == "machine"


def test_a_person_quoting_the_feedback_is_still_the_person(proj):
    """回饋只認開頭：人打的一則裡引了一段回饋（「你說 … 是什麼意思？」）仍然是人的新要求。"""
    p = proj
    _exhaust(p, "K3")
    hook.handle("claude", "UserPromptSubmit", {"session_id": "K3", "cwd": str(p), "prompt":
                "About this: '" + F.FEEDBACK_HEADER + "' — please fix report.md now."})
    out, _e, _c = hook.handle("claude", "Stop", {"session_id": "K3", "cwd": str(p)})
    assert json.loads(out).get("decision") == "block"


def test_the_session_cannot_call_vacant_hook_itself(proj):
    """掛鉤是平台自己呼叫的；在工作的那一方自己呼叫＝偽造病歷裡的事件（例：一則「人打的」）。字串層的擋。"""
    p = proj
    for cmd in ("echo '{}' | vacant hook claude UserPromptSubmit",
                "echo '{}' | python -m vacant_network hook claude Stop"):
        out, _e, _c = hook.handle("claude", "PreToolUse", {
            "session_id": "K4", "cwd": str(p), "tool_name": "Bash", "tool_use_id": "h1",
            "tool_input": {"command": cmd}})
        d = json.loads(out)["hookSpecificOutput"]
        assert d["permissionDecision"] == "deny", cmd


def test_a_passing_check_elsewhere_does_not_reset_this_projects_budget(proj, tmp_path):
    """輪數檔的鍵是工作階段＋這一份契約：同一個工作階段在另一個目錄（另一份契約）過了，不歸零這一個。"""
    p = proj
    _exhaust(p, "K5")
    other = tmp_path / "other"
    (other / ".vacant").mkdir(parents=True)
    (other / "s.csv").write_text("id,amount\n1,5\n")
    raw = C.scaffold("elsewhere", deliverable=["x.md"])
    raw["inputs"] = {"s": {"path": "s.csv"}}
    raw["claims"] = [{"id": "total", "verifier": "csv_total", "authority": "fact",
                      "params": {"csv": "input:s", "column": "amount", "report": "x.md"}}]
    raw["hooks"] = {"stop_check": True, "max_feedback_rounds": 1, "submit_on_end": False}
    (other / ".vacant" / "contract.json").write_text(json.dumps(raw))
    C.lock(other / ".vacant" / "contract.json")
    (other / "x.md").write_text("Total: 5\n")
    hook.handle("claude", "Stop", {"session_id": "K5", "cwd": str(other)})
    assert _still_exhausted(p, "K5")


def test_the_pi_and_opencode_bridges_forward_the_persons_messages():
    """pi：跑著的時候打的（steer／follow-up）不經過 before_agent_start ⇒ 聽 `input`（2026-09-25 審查 semantics#3，
    真 pi 重現）；OpenCode：`chat.message`（2026-09-25 在 TUI 裡量到）。"""
    from vacant_network.adapters import agents
    pi = agents.pi_extension_text()
    assert 'pi.on("input"' in pi and "streamingBehavior" in pi and '"extension"' in pi
    oc = agents.opencode_plugin_text()
    assert '"chat.message"' in oc and 'ask("prompt"' in oc


def test_the_same_message_reported_twice_in_a_row_is_recorded_once(proj):
    """pi：跑著的時候打的那一則先經過 `input`，run 剛好結束時又經過 `before_agent_start`（真 pi 實測的競態）。"""
    p = proj
    base = {"cwd": str(p), "session_id": "P1"}
    for _ in range(2):
        hook.handle("pi", "prompt", {**base, "prompt": "now write report.md"})
    assert len([e for e in R.Recorder(p).events() if e["type"] == "prompt"]) == 1
    hook.handle("pi", "prompt", {**base, "prompt": "and a second, different request"})
    hook.handle("pi", "prompt", {**base, "prompt": "now write report.md"})     # 之後又打一次：照記
    assert len([e for e in R.Recorder(p).events() if e["type"] == "prompt"]) == 3
