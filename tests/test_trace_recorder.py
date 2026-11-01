"""追緝的病歷（`vacant_network/trace/recorder.py`）：每一步寫了什麼、沒有紀錄的改動、鏈可驗。"""
from __future__ import annotations

import json

import pytest

from vacant_network.intake import keys
from vacant_network.trace import recorder as R
from vacant_network.trace import workspace as W


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    keys.init_local()
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "data.csv").write_text("a,1\nb,2\n")
    return ws, R.Recorder(ws)


MAIN = R.Actor("claude", "s1")
SUB = R.Actor("claude", "s1", agent="a7f3", agent_type="Explore")


def _types(rec):
    return [e["type"] for e in rec.events()]


def test_each_step_owns_exactly_what_it_wrote(env):
    ws, rec = env
    rec.pre("t1", MAIN, "Write", {"file_path": "report.md"})
    (ws / "report.md").write_text("Total: 3\n")
    e1 = rec.post("t1", MAIN, "Write", {"file_path": "report.md"}, "ok")
    rec.pre("t2", SUB, "Bash", {"command": "sed -i s/3/999/ report.md"})
    (ws / "report.md").write_text("Total: 999\n")                  # 殼層指令改的，平台不會回報
    e2 = rec.post("t2", SUB, "Bash", {"command": "sed ..."}, "")
    assert [w["path"] for w in e1["writes"]] == ["report.md"] and e1["writes"][0]["kind"] == "added"
    assert [w["kind"] for w in e2["writes"]] == ["modified"]
    assert e2["actor"]["agent_type"] == "Explore"
    assert "unrecorded_change" not in _types(rec)
    ok, why = rec.verify()
    assert ok, why
    # 任何一步之前／之後的工作區都能重建
    before = rec.load_index(e2["pre_index"])
    assert rec.blobs.get(before["report.md"].sha256) == b"Total: 3\n"


def test_change_between_steps_is_an_accountability_gap_not_blamed(env):
    ws, rec = env
    rec.pre("t1", MAIN, "Read", {"file_path": "data.csv"})
    rec.post("t1", MAIN, "Read", {"file_path": "data.csv"}, "a,1")
    (ws / "data.csv").write_text("a,1\nb,9999\n")                  # 掛鉤外面改的
    rec.pre("t2", MAIN, "Read", {"file_path": "data.csv"})
    gaps = [e for e in rec.events() if e["type"] == "unrecorded_change"]
    assert len(gaps) == 1 and gaps[0]["changes"][0]["path"] == "data.csv"
    assert "actor" not in gaps[0]                                   # 不歸給任何人
    e2 = rec.post("t2", MAIN, "Read", {"file_path": "data.csv"}, "...")
    assert e2["writes"] == []                                       # 也不算到下一步頭上


def test_gap_at_session_end_and_concurrent_steps(env):
    ws, rec = env
    rec.pre("a", MAIN, "Bash", {"command": "x"})
    rec.pre("b", SUB, "Bash", {"command": "y"})
    (ws / "out.txt").write_text("?")
    ea = rec.post("a", MAIN, "Bash", {}, "")
    eb = rec.post("b", SUB, "Bash", {}, "")
    assert ea["concurrent_with"] == ["b"] and eb["concurrent_with"] == ["a"]
    (ws / "late.txt").write_text("after the last step")
    rec.close(MAIN, "end_turn")
    last_gap = [e for e in rec.events() if e["type"] == "unrecorded_change"][-1]
    assert last_gap["observed_at"] == "session_end"
    assert [c["path"] for c in last_gap["changes"]] == ["late.txt"]


def test_post_without_pre_is_recorded_and_marked(env):
    ws, rec = env
    (ws / "x.txt").write_text("1")
    e0 = rec.post("first", MAIN, "Edit", {"file_path": "x.txt"}, "ok")
    assert e0["baseline_missing"] is True and e0["writes"] == []    # 不知道 ≠ 沒寫，也不全算給它
    (ws / "x.txt").write_text("2")
    e = rec.post("orphan", MAIN, "Edit", {"file_path": "x.txt"}, "ok")
    assert e["pre_missing"] is True and [w["path"] for w in e["writes"]] == ["x.txt"]


def test_long_write_lists_move_to_the_store_not_dropped(env):
    ws, rec = env
    rec.pre("big", MAIN, "Bash", {"command": "gen"})
    for i in range(R.INLINE_LIST + 30):
        (ws / f"f{i:03}.txt").write_text(str(i))
    rec.post("big", MAIN, "Bash", {}, "")
    step = [e for e in rec.events() if e["type"] == "step"][-1]
    assert len(step["writes"]) == R.INLINE_LIST and step["n_writes"] == R.INLINE_LIST + 30
    full = json.loads(rec.blobs.get(step["writes_blob"]))
    assert len(full) == R.INLINE_LIST + 30


def test_tampering_with_the_chain_is_detected(env):
    ws, rec = env
    rec.pre("t1", MAIN, "Write", {})
    (ws / "r.md").write_text("x")
    rec.post("t1", MAIN, "Write", {}, "ok")
    lines = rec.chain_path.read_text().splitlines()
    d = json.loads(lines[-1])
    d["payload"]["actor"]["platform"] = "someone-else"
    lines[-1] = json.dumps(d)
    rec.chain_path.write_text("\n".join(lines) + "\n")
    ok, why = rec.verify()
    assert not ok and "does not verify" in why


def test_failed_step_keeps_a_short_error_preview_in_the_signed_entry(env):
    """round 117 dogfood：pi 的失敗步只記 `error: tool reported an error`，真正的錯誤文字
    在輸出 blob 裡；blob 會被 gc 掉（本機 5094 個輸入 blob 已 4930 個被 gc），錯誤原因
    就永久只剩一句話。入口（簽名條目）裡要留一短段預覽，gc 之後還在。"""
    ws, rec = env
    rec.pre("t1", MAIN, "Bash", {"command": "pytest"})
    out = "collected 3 items\nFAILED tests/test_x.py::test_y\nValueError: boom\n"
    e = rec.post("t1", MAIN, "Bash", {"command": "pytest"}, out,
                 error="tool reported an error")
    assert e["error"] == "tool reported an error"
    assert e["error_preview"] == "ValueError: boom"    # 最後一非空行，空白正規化
    # 預覽在簽名條目裡、不在 blob 裡：blob 被 gc 掉之後，重新讀鏈還在
    import os
    blob_path = ws.parent / "vh" / "trace" / "objects" / e["output_blob"][:2] / e["output_blob"]
    os.unlink(blob_path)
    fresh = [x for x in rec.events() if x.get("type") == "step" and x.get("step") == "t1"][0]
    assert fresh["error_preview"] == "ValueError: boom"
    ok, why = rec.verify()
    assert ok, why


def test_error_preview_bounds_and_absent_cases(env):
    ws, rec = env
    rec.pre("t1", MAIN, "Bash", {})
    long_line = "x" * 500
    e1 = rec.post("t1", MAIN, "Bash", {}, long_line, error="tool failed")
    assert e1["error_preview"] == "x" * 160             # 截到 160
    rec.pre("t2", MAIN, "Bash", {})
    e2 = rec.post("t2", MAIN, "Bash", {}, "  tab\t\tline\n\n", error="tool failed")
    assert e2["error_preview"] == "tab line"            # 空白正規化
    rec.pre("t3", MAIN, "Bash", {})
    e3 = rec.post("t3", MAIN, "Bash", {}, "fine output")   # 沒有錯誤 ⇒ 沒有預覽
    assert e3["error"] is None and e3["error_preview"] is None
    rec.pre("t4", MAIN, "Bash", {})
    e4 = rec.post("t4", MAIN, "Bash", {}, None, error="PostToolUseFailure: exit 1")
    assert e4["error"] and e4["error_preview"] is None  # 輸出為 None（claude 形狀）
    rec.pre("t5", MAIN, "Bash", {})
    e5 = rec.post("t5", MAIN, "Bash", {}, {"type": "err"}, error="tool failed")
    assert e5["error_preview"] is None                  # 非文字輸出：不硬造預覽
    ok, why = rec.verify()
    assert ok, why


def test_vacant_state_dir_inside_workspace_is_not_traced(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    monkeypatch.setenv("VACANT_HOME", str(ws / ".vh"))
    keys.init_local()
    ws.mkdir(exist_ok=True)
    rec = R.Recorder(ws)
    rec.pre("t", MAIN, "Write", {})
    (ws / "a").write_text("1")
    e = rec.post("t", MAIN, "Write", {}, "")
    assert [w["path"] for w in e["writes"]] == ["a"]
    assert all(not p.startswith(".vh") for p in W.scan(ws, skip=rec.skip))


def test_refuses_to_append_when_chain_signer_differs(tmp_path, monkeypatch):
    """病歷鏈是另一把金簽的（還原舊狀態目錄、本機金丟了）：現在寫進去＝混簽章鏈、整條不可驗
    ⇒ 拒寫、鏈原封不動（2026-11-01 第 826 輪 mixed-signer 發現；誠實邊界：拒的是寫入，不是使用者）。"""
    import shutil
    vh = tmp_path / "vh"
    monkeypatch.setenv("VACANT_HOME", str(vh))
    keys.init_local()
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "f.txt").write_text("1\n")
    rec = R.Recorder(ws)
    rec.pre("t1", MAIN, "Read", {"file_path": "f.txt"})
    rec.post("t1", MAIN, "Read", {"file_path": "f.txt"}, "1")
    ok, why = rec.verify()
    assert ok, why
    before = rec.chain_path.read_bytes()
    n_before = len(rec.events())

    shutil.rmtree(vh / "intake" / "keys")            # 備份只有病歷、沒有金：load_or_create 會生一把新的
    rec2 = R.Recorder(ws)
    (ws / "f.txt").write_text("1\n2\n")              # 製造未記錄缺口 → 觸發 append
    with pytest.raises(R.MixedSignerRefused):
        rec2.checkpoint("test")
    assert rec2.chain_path.read_bytes() == before    # 鏈原封不動
    assert len(rec2.events()) == n_before
    ok2, why2 = rec2.verify()
    assert ok2, why2                                 # 原鏈照樣可用原簽者驗過


def test_append_allowed_when_genesis_signer_unknown(tmp_path, monkeypatch):
    """舊版病歷（genesis 沒有 signer 欄）：簽者判定不出來＝UNKNOWN，不擋寫入（fail-open，不變量 2）。"""
    import shutil
    vh = tmp_path / "vh"
    monkeypatch.setenv("VACANT_HOME", str(vh))
    keys.init_local()
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "f.txt").write_text("1\n")
    rec = R.Recorder(ws)
    rec.pre("t1", MAIN, "Read", {"file_path": "f.txt"})
    rec.post("t1", MAIN, "Read", {"file_path": "f.txt"}, "1")
    n_before = len(rec.events())
    lines = rec.chain_path.read_text(encoding="utf-8").splitlines(keepends=True)
    g = json.loads(lines[0])
    g["payload"].pop("signer", None)                 # 模擬沒有 signer 欄的舊病歷
    rec.chain_path.write_text(
        json.dumps(g, ensure_ascii=False, sort_keys=True) + "\n" + "".join(lines[1:]),
        encoding="utf-8")
    shutil.rmtree(vh / "intake" / "keys")
    rec2 = R.Recorder(ws)
    (ws / "f.txt").write_text("1\n2\n")
    rec2.checkpoint("test")                          # 不得拋
    assert len(rec2.events()) == n_before + 1


def test_hook_trace_fail_open_on_mixed_signer(tmp_path, monkeypatch):
    """掛鉤路徑遇拒寫：只記錯、不影響裁決、agent 不被擋（掛鉤永遠放行）。"""
    import shutil
    from vacant_network.adapters import hook
    from vacant_network.adapters.hookpolicy import HookEvent
    vh = tmp_path / "vh"
    monkeypatch.setenv("VACANT_HOME", str(vh))
    monkeypatch.setenv("VACANT_TRACE", "1")
    monkeypatch.setenv("VACANT_HOOK_NO_GC", "1")
    keys.init_local()
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "f.txt").write_text("1\n")
    rec = R.Recorder(ws)
    rec.pre("t1", MAIN, "Read", {"file_path": "f.txt"})
    rec.post("t1", MAIN, "Read", {"file_path": "f.txt"}, "1")
    before = rec.chain_path.read_bytes()
    shutil.rmtree(vh / "intake" / "keys")
    ev = HookEvent(agent="claude", kind="pre_tool", cwd=str(ws), session_id="s1")
    payload = {"tool_name": "Read", "tool_input": {"file_path": "f.txt"}, "session_id": "s1"}
    hook._trace("claude", "PreToolUse", payload, ev, None, None)   # 不得拋
    assert rec.chain_path.read_bytes() == before                    # 鏈原封不動
