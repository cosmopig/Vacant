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
