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
