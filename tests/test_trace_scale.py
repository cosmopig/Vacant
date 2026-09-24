"""大專案（`trace/recorder.py` 的掃描時限與背景的第一次觀察）：掛鉤有 30 秒上限，被 agent 砍掉＝
靜默略過＝更大的缺口。這裡釘住的是**看不到的時候不假裝看到了**：

- 掛鉤裡第一次看就超過時限 ⇒ 改在背景看；在它完成之前的步驟「寫了什麼不知道」，不是「沒寫」
- 背景還在看的期間，掛鉤不再各自重掃（否則每一步多花一整個時限）
- 背景看完時已經在的值，追緝不能說「本來就在」（可能是沒被看到的那幾步寫的）⇒ 缺口，不怪任何人
- 背景看不完（檔案數上限）或等太久 ⇒ 這個專案不再逐步掃描，照實記下
- 掃描關掉之後，每一次掛鉤連舊索引都不讀
"""
from __future__ import annotations

import json
import subprocess
import time

import pytest

from vacant_network.intake import contract as C
from vacant_network.intake import keys
from vacant_network.trace import blame as B
from vacant_network.trace import capture
from vacant_network.trace import recorder as R
from vacant_network.trace import rerun
from vacant_network.trace import workspace as W

MAIN = R.Actor("claude", "s1")
SALES = "id,amount\n1,10\n2,20\n3,30\n"
TOTAL = [{"id": "total", "verifier": "csv_total", "authority": "fact",
          "params": {"csv": "input:sales", "column": "amount", "report": "report.md"}}]


@pytest.fixture
def proj(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    monkeypatch.delenv("VACANT_TRACE", raising=False)
    keys.init_local()
    p = tmp_path / "proj"
    (p / "data").mkdir(parents=True)
    (p / ".vacant").mkdir()
    (p / "data" / "sales.csv").write_text(SALES)
    raw = C.scaffold("scale", deliverable=["report.md"])
    raw["inputs"] = {"sales": {"path": "data/sales.csv"}}
    raw["claims"] = TOTAL
    cp = p / ".vacant" / "contract.json"
    cp.write_text(json.dumps(raw))
    C.lock(cp)
    spawned: list[list[str]] = []
    monkeypatch.setattr(subprocess, "Popen", lambda argv, **kw: spawned.append(list(argv)))
    return p, C.load(cp), spawned


def _hook_recorder(p):
    """掛鉤裡的紀錄器，時限小到第一次看一定超過。"""
    rec = R.Recorder(p)
    rec.scan_deadline_s = 1e-9
    return rec


def _step(rec, sid, tool, inp, write=None):
    rec.pre(sid, MAIN, tool, inp)
    if write:
        write[0].write_text(write[1])
    return rec.post(sid, MAIN, tool, inp, "")


def _events(rec, kind):
    return [e for e in rec.events() if e["type"] == kind]


def test_scan_deadline_raises_even_inside_one_huge_directory(tmp_path):
    for i in range(600):
        (tmp_path / f"f{i:04d}").write_text(str(i))
    with pytest.raises(W.ScanTimeout):
        W.scan(tmp_path, deadline=time.monotonic() - 1)
    assert len(W.scan(tmp_path, deadline=time.monotonic() + 60)) == 600


def test_a_too_slow_first_look_moves_to_the_background_once(proj, monkeypatch):
    p, _c, spawned = proj
    rec = _hook_recorder(p)
    e = _step(rec, "t1", "Write", {"file_path": "report.md"}, write=(p / "report.md", "x\n"))
    assert e["writes"] == [] and e["writes_unknown"]          # 不知道 ≠ 沒寫
    assert e["pre_index"] is None and e["post_index"] is None
    assert len(spawned) == 1 and spawned[0][-2:] == ["baseline", str(p.resolve())]
    assert [x["baseline_deferred"] for x in _events(rec, "coverage")
            if "baseline_deferred" in x]                       # 記下「這段時間沒看」
    # 背景還在看：之後的掛鉤不重掃、不再開背景行程
    calls = []
    real = W.scan
    monkeypatch.setattr(W, "scan", lambda *a, **k: calls.append(1) or real(*a, **k))
    _step(rec, "t2", "Bash", {"command": "echo"})
    assert calls == [] and len(spawned) == 1
    ok, why = rec.verify()
    assert ok, why


def test_the_background_look_resumes_step_by_step_observation(proj):
    p, _c, _spawned = proj
    rec = _hook_recorder(p)
    _step(rec, "t1", "Write", {"file_path": "report.md"}, write=(p / "report.md", "a\n"))
    info = R.Recorder(p).baseline()                            # 背景行程做的事
    assert info["after_unobserved"] is True and info["files"] >= 2
    assert R.Recorder(p).baseline() == {"skipped": "already observed"}   # 冪等
    rec = R.Recorder(p)
    rec.scan_deadline_s = R.HOOK_SCAN_S
    e = _step(rec, "t2", "Write", {"file_path": "report.md"}, write=(p / "report.md", "b\n"))
    assert [w["path"] for w in e["writes"]] == ["report.md"] and "writes_unknown" not in e


def test_a_value_already_there_at_the_background_look_is_a_gap_not_a_blame(proj):
    p, c, _spawned = proj
    rec = _hook_recorder(p)
    # 沒被看到的那一步寫了錯的總數
    _step(rec, "t1", "Write", {"file_path": "report.md"},
          write=(p / "report.md", "# Q3\nTotal: 999\n"))
    R.Recorder(p).baseline()
    rec = R.Recorder(p)
    _step(rec, "t2", "Read", {"file_path": "data/sales.csv"})
    [b] = B.blame_results(rec, c, rerun.run(c, p, sandbox="none"), p, sandbox="none")
    assert (b["state"], b["fault_class"], b["confidence"]) == \
        ("UNOBSERVED", "unattributable", "gap")
    assert not b.get("step")                                   # 不指任何一步、不怪任何人


def test_control_after_the_background_look_an_observed_write_is_still_provable(proj):
    p, c, _spawned = proj
    rec = _hook_recorder(p)
    _step(rec, "t1", "Bash", {"command": "ls"})
    R.Recorder(p).baseline()
    rec = R.Recorder(p)
    _step(rec, "t2", "Write", {"file_path": "report.md"},
          write=(p / "report.md", "# Q3\nTotal: 999\n"))
    [b] = B.blame_results(rec, c, rerun.run(c, p, sandbox="none"), p, sandbox="none")
    assert (b["state"], b["fault_class"], b["confidence"]) == ("located", "agent", "provable")
    assert b["step"]["step"] == "t2"


def test_a_background_look_that_never_lands_turns_scanning_off(proj, monkeypatch):
    p, _c, _spawned = proj
    rec = _hook_recorder(p)
    _step(rec, "t1", "Bash", {"command": "ls"})
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + R.BASELINE_WAIT_S + 1)
    e = _step(rec, "t2", "Bash", {"command": "ls"})
    assert "did not finish" in e["writes_unknown"]
    st = json.loads(rec.state_path.read_text())
    assert "did not finish" in st["scan_disabled"]


def test_a_workspace_too_big_even_for_the_background_turns_scanning_off(proj, monkeypatch):
    p, _c, _spawned = proj
    rec = _hook_recorder(p)
    _step(rec, "t1", "Bash", {"command": "ls"})
    monkeypatch.setattr(W, "MAX_FILES", 1)
    out = R.Recorder(p).baseline()
    assert "more than 1 files" in out["disabled"]
    st = json.loads(rec.state_path.read_text())
    assert "baseline_pending" not in st and "more than" in st["scan_disabled"]
    assert any("scan_disabled" in x for x in _events(rec, "coverage"))


def test_an_incremental_scan_past_the_deadline_turns_scanning_off(proj):
    p, _c, _spawned = proj
    rec = R.Recorder(p)
    _step(rec, "t1", "Bash", {"command": "ls"})                # 沒有時限：看得到
    rec.scan_deadline_s = 1e-9
    e = _step(rec, "t2", "Write", {"file_path": "report.md"}, write=(p / "report.md", "x\n"))
    assert e["writes"] == [] and "incremental scan passed" in e["writes_unknown"]


def test_once_scanning_is_off_hooks_do_not_even_load_the_old_index(proj, monkeypatch):
    p, _c, _spawned = proj
    rec = R.Recorder(p)
    _step(rec, "t1", "Bash", {"command": "ls"})
    rec.scan_deadline_s = 1e-9
    _step(rec, "t2", "Bash", {"command": "ls"})                # 關掉
    rec = R.Recorder(p)

    def boom(_sha):
        raise AssertionError("loaded an index after scanning was turned off")
    monkeypatch.setattr(rec, "load_index", boom)
    monkeypatch.setattr(W, "scan", lambda *a, **k: (_ for _ in ()).throw(AssertionError("scan")))
    e = _step(rec, "t3", "Bash", {"command": "ls"})
    assert e["writes_unknown"]


def test_the_command_line_has_no_deadline_and_hooks_do(proj, monkeypatch):
    p, _c, _spawned = proj
    assert R.Recorder(p).scan_deadline_s is None               # `vacant trace`／`vacant do`
    seen = []
    real = R.Recorder.pre

    def spy(self, *a, **k):
        seen.append(self.scan_deadline_s)
        return real(self, *a, **k)
    monkeypatch.setattr(R.Recorder, "pre", spy)
    monkeypatch.setenv("VACANT_TRACE", "1")
    capture.observe("claude", "PreToolUse", {"session_id": "s1", "tool_use_id": "u1",
                                             "tool_name": "Bash",
                                             "tool_input": {"command": "ls"}}, cwd=str(p))
    assert seen == [R.HOOK_SCAN_S]


def test_the_background_entry_point(proj, capsys):
    p, _c, _spawned = proj
    assert R.main(["baseline", str(p)]) == 0
    assert json.loads(capsys.readouterr().out)["after_unobserved"] is False
    assert R.main(["nope"]) == 2


def test_big_workspaces_store_each_state_as_a_delta_that_restores_exactly(proj, monkeypatch):
    p, _c, _spawned = proj
    monkeypatch.setattr(R, "DELTA_MIN_FILES", 5)
    for i in range(100):
        (p / "data" / f"f{i:02d}.txt").write_text(str(i))
    rec = R.Recorder(p)
    e1 = _step(rec, "t1", "Bash", {"command": "ls"})
    (p / "data" / "f00.txt").unlink()
    e2 = _step(rec, "t2", "Write", {"file_path": "report.md"}, write=(p / "report.md", "x\n"))
    raw = json.loads(rec.blobs.get(e2["post_index"]))
    assert raw[""]["base"] == e1["post_index"] and raw[""]["del"] == ["data/f00.txt"]
    assert set(raw) == {"", "report.md"}                      # 只存變了的
    fresh = R.Recorder(p)                                     # 另一個行程：沒有快取
    assert fresh.load_index(e2["post_index"]) == W.scan(p, skip=rec.skip)
    assert [w["path"] for w in e2["writes"]] == ["report.md"]
    [gap] = _events(rec, "unrecorded_change")                 # 兩步之間刪的：缺口，照舊
    assert [c["path"] for c in gap["changes"]] == ["data/f00.txt"]
    # 差異大到超過一成（且超過 64 筆）⇒ 存一份新的完整索引，之後對它算
    for i in range(1, 100):
        (p / "data" / f"f{i:02d}.txt").write_text("changed")
    e3 = _step(rec, "t3", "Bash", {"command": "sed"})
    assert "" not in json.loads(rec.blobs.get(e3["post_index"]))
    assert json.loads(rec.state_path.read_text())["index_key"] == e3["post_index"]
    # 關鍵幀被竄改 ⇒ 讀不出來（不是讀出別的狀態）
    kf = rec.blobs.path(e1["post_index"])
    kf.chmod(0o600)
    kf.write_bytes(kf.read_bytes().replace(b"data/f01.txt", b"data/f99.txt"))
    with pytest.raises(ValueError):
        R.Recorder(p).load_index(e2["post_index"])


def test_small_workspaces_keep_full_indexes(proj):
    p, _c, _spawned = proj
    rec = R.Recorder(p)
    e = _step(rec, "t1", "Write", {"file_path": "report.md"}, write=(p / "report.md", "x\n"))
    assert "" not in json.loads(rec.blobs.get(e["post_index"]))


def test_rebuilt_states_hold_only_the_deliverable_like_the_receiving_end(tmp_path, monkeypatch):
    """重跑要和收件口看到同一批檔：收件口只放繳付物進隔離區。整個工作區重建曾經讓 `command`
    主張在追緝時看到收件時看不到的檔（判決不同），大專案每條主張還要寫幾萬個檔。"""
    from vacant_network.intake import flow
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    keys.init_local()
    p = tmp_path / "proj"
    (p / ".vacant").mkdir(parents=True)
    raw = C.scaffold("scope", deliverable=["report.md"])
    raw["claims"] = [{"id": "noscratch", "verifier": "command", "authority": "requirement",
                      "params": {"argv": ["python3", "-c", "import os,sys; "
                                          "sys.exit(1 if os.path.exists('scratch.txt') else 0)"],
                                 "sandbox": "none"}}]
    cp = p / ".vacant" / "contract.json"
    cp.write_text(json.dumps(raw))
    C.lock(cp)
    c = C.load(cp)
    rec = R.Recorder(p)
    rec.pre("t1", MAIN, "Bash", {"command": "work"})
    (p / "report.md").write_text("ok\n")
    (p / "scratch.txt").write_text("notes\n")                  # 不是繳付物
    e = rec.post("t1", MAIN, "Bash", {"command": "work"}, "")
    d = tmp_path / "state"
    assert B.Trace(rec).materialize(e["post_index"], d, c) == []
    assert sorted(x.name for x in d.iterdir()) == ["report.md"]
    intake = flow.check(c, p, sandbox="none")
    [again] = rerun.run(c, d, sandbox="none")
    assert intake["outcome"] == "accept" and again["status"] == "PASS"
