"""逐步觀察被永久關掉之後的救回（`trace/recorder.py` 的 `rescan` / `vacant trace rescan`）。

大專案在 `vacant gc` 之後，增量掃描要重新核對／重存大量版本，超過掛鉤的 8 秒上限，
`_disable_scan` 就把這個專案**永久**關掉（自家專案實測）。round 27 只讓人**看得見**
這個狀態；這支釘住的是**救得回**：

- `rescan` 重新完整觀察一次：重存所有版本、刷新 `last_index`、清掉「掃描停用」
- 救回來之後，逐步觀察真的又作用（寫入能被歸因），不是只把旗標翻過去
- 救不回（工作區太大）時不破壞既有狀態——寧可照實說救不回，也不清空已觀測到的
- `baseline()` 預設行為不變（`rescan` 是純增量能力）
- 命令列 `vacant trace rescan` 存在、作用、退出碼誠實
"""
from __future__ import annotations

import json
import subprocess

import pytest

from vacant_network.intake import contract as C
from vacant_network.intake import keys
from vacant_network.trace import recorder as R
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
    raw = C.scaffold("rescan", deliverable=["report.md"])
    raw["inputs"] = {"sales": {"path": "data/sales.csv"}}
    raw["claims"] = TOTAL
    cp = p / ".vacant" / "contract.json"
    cp.write_text(json.dumps(raw))
    C.lock(cp)
    monkeypatch.setattr(subprocess, "Popen", lambda argv, **kw: None)
    return p, C.load(cp)


def _state(p):
    rec = R.Recorder(p)
    return json.loads(rec.state_path.read_text())


def _died_after_gc(p):
    """重現真實故障鏈：先有完整觀察（last_index 在），`gc` 把 store 標成 compaction，
    之後掛鉤的增量掃描（`prev_stored=False`）超時 ⇒ `_disable_scan` 永久關掉。"""
    R.Recorder(p).baseline()                                  # 第一步：看過了，last_index 在
    rec = R.Recorder(p)
    st = json.loads(rec.state_path.read_text())
    st["compacted"] = True                                    # gc 的效果
    rec.state_path.write_text(json.dumps(st))
    rec = R.Recorder(p)
    rec.scan_deadline_s = 1e-9                                # 掛鉤時限極小 ⇒ 增量掃描一定超時
    rec.pre("t", MAIN, "Bash", {"command": "ls"})
    rec.post("t", MAIN, "Bash", {"command": "ls"}, "")
    assert _state(p).get("scan_disabled")                     # 前提：專案已經「死了」


def test_timeout_after_gc_names_gc_in_the_disable_reason(proj):
    """停用原因要寫出真正的起因：gc 之後的第一次重核對，不是「增量 diff 慢」。

    自家專案實測：理由只寫「an incremental scan passed 8s」會讓人以為自己的 repo 掃得慢；
    其實慢在 `vacant gc` 之後的重核對／重存，出路是 `vacant trace rescan`（無時限的重看）。"""
    p, _c = proj
    _died_after_gc(p)
    st = _state(p)
    assert "vacant gc" in st["scan_disabled"]
    # 病歷上的 coverage 事件也寫出真正的起因
    evs = [e for e in R.Recorder(p).events()
           if e["type"] == "coverage" and e.get("scan_disabled")]
    assert evs and "vacant gc" in evs[-1]["scan_disabled"]


def test_timeout_without_gc_keeps_the_incremental_reason(proj):
    """沒跑過 gc 的超時照舊：原因不改，既有訊息不變。"""
    p, _c = proj
    R.Recorder(p).baseline()
    rec = R.Recorder(p)
    rec.scan_deadline_s = 1e-9
    rec.pre("t", MAIN, "Bash", {"command": "ls"})
    rec.post("t", MAIN, "Bash", {"command": "ls"}, "")
    st = _state(p)
    assert "vacant gc" not in st["scan_disabled"]
    assert "an incremental scan passed" in st["scan_disabled"]


def test_rescan_revives_a_project_that_died_after_gc(proj):
    p, _c = proj
    _died_after_gc(p)
    out = R.Recorder(p).rescan()
    assert out["rescanned"] is True and out["files"] >= 2
    st = _state(p)
    assert "scan_disabled" not in st and st["last_index"]
    assert st.get("compacted") is None                        # 下一步增量走快路徑，不會再超時
    # 救回不只是翻旗標：逐步觀察真的又作用，寫入能被歸因
    rec = R.Recorder(p)
    rec.scan_deadline_s = R.HOOK_SCAN_S
    rec.pre("t2", MAIN, "Write", {"file_path": "report.md"})
    (p / "report.md").write_text("# Q3\nTotal: 60\n")
    e = rec.post("t2", MAIN, "Write", {"file_path": "report.md"}, "ok")
    assert [w["path"] for w in e["writes"]] == ["report.md"] and "writes_unknown" not in e
    # 病歷上有一筆「重看」的 coverage 事件，簽進鏈
    cov = [e for e in R.Recorder(p).events() if e["type"] == "coverage" and e.get("rescanned")]
    assert cov and cov[-1]["rescanned"]["was_disabled"] is True
    ok, why = R.Recorder(p).verify()
    assert ok, why


def test_rescan_re_stores_the_blob_store_so_incremental_scans_are_safe(proj):
    p, _c = proj
    R.Recorder(p).baseline()
    # 模擬 `gc` 把一部分版本從 store 剪掉：之後的增量掃描若走快路徑（假設版本都在）
    # 會讀到空；rescan 必須重存，讓快路徑的假設重新成立
    rec = R.Recorder(p)
    before = rec.load_index(_state(p)["last_index"])
    some_sha = next(iter(before.values())).sha256
    victim = rec.blobs.path(some_sha)
    if victim.is_file():
        victim.unlink()
    _died_after_gc(p)                                         # 現在專案死了
    R.Recorder(p).rescan()
    fresh = rec.load_index(_state(p)["last_index"])
    # 新版本可讀（重存過的），不是一堆空
    assert all(rec.blobs.get(v.sha256) for v in fresh.values())


def test_rescan_too_big_keeps_existing_state(proj, monkeypatch):
    p, _c = proj
    R.Recorder(p).baseline()
    last = _state(p)["last_index"]
    assert last
    monkeypatch.setattr(W, "MAX_FILES", 1)                    # 工作區太大，救不回
    out = R.Recorder(p).rescan()
    assert out["rescanned"] is False and "more than" in out["error"]
    st = _state(p)
    assert st["last_index"] == last                           # 不破壞既有狀態
    # 救不回時不新增 coverage 事件（沒有東西可記，寧可照實說）
    assert not [e for e in R.Recorder(p).events()
                if e["type"] == "coverage" and e.get("rescanned")]


def test_rescan_works_on_a_never_observed_project(proj):
    p, _c = proj
    # 從來沒看過的專案：rescan 也能當「強制第一次完整觀察」用
    out = R.Recorder(p).rescan()
    assert out["rescanned"] is True and _state(p)["last_index"]


def test_baseline_default_behavior_unchanged(proj):
    p, _c = proj
    R.Recorder(p).baseline()
    # 預設 `baseline()` 還是冪等、不重看（rescan 是獨立能力，不改舊語意）
    assert R.Recorder(p).baseline() == {"skipped": "already observed"}


def test_cmd_rescan_runs_and_revives(proj, capsys):
    p, _c = proj
    _died_after_gc(p)
    from vacant_network.trace import cli
    cp = p / ".vacant" / "contract.json"
    rc = cli.main(["--contract", str(cp), "rescan"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "re-observed" in out and "on again" in out
    assert "scan_disabled" not in _state(p)


def test_cmd_rescan_too_big_exits_nonzero(proj, monkeypatch, capsys):
    p, _c = proj
    R.Recorder(p).baseline()
    monkeypatch.setattr(W, "MAX_FILES", 1)
    from vacant_network.trace import cli
    cp = p / ".vacant" / "contract.json"
    rc = cli.main(["--contract", str(cp), "rescan"])
    assert rc == 2
    assert "rescan failed" in capsys.readouterr().err


# —— 超時之後自動救回：不再需要人手跑 `vacant trace rescan` ——

def test_timeout_spawns_a_background_rescan_attempt(proj, monkeypatch):
    """超時 ⇒ 照樣停用（誠實，不讓掛鉤多等），但自動在背景試一次 `rescan` 救回。

    背景救不回時（這支測試裡 Popen 被 stub 掉）維持停用——最壞情況＝舊行為。"""
    p, _c = proj
    spawned: list[list[str]] = []
    monkeypatch.setattr(subprocess, "Popen", lambda argv, **kw: spawned.append(list(argv)))
    _died_after_gc(p)                                         # 超時 ⇒ 停用
    st = _state(p)
    assert "scan_disabled" in st
    assert st["auto_rescan"]["n"] == 1                        # 記了次數
    assert len(spawned) == 1
    assert spawned[0][-2:] == ["rescan", str(p.resolve())]    # 背景跑的就是 `rescan`


def test_background_rescan_revives_without_human_action(proj, monkeypatch):
    """背景行程真的跑完（這裡用同一份 `rescan()` 模擬）⇒ 逐步觀察自動恢復，不必等人。

    救回成功 ⇒ 自動救回的預算重置（手動救回也是同一條路徑、同樣重置）。"""
    p, _c = proj
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: None)   # 背景不真跑
    _died_after_gc(p)
    st = _state(p)
    assert "scan_disabled" in st and st["auto_rescan"]["n"] == 1
    out = R.Recorder(p).rescan()                                # 背景行程做的事
    assert out["rescanned"] is True
    st = _state(p)
    assert "scan_disabled" not in st and "auto_rescan" not in st
    # 救回之後，掛鉤照舊能歸因寫入
    rec = R.Recorder(p)
    rec.scan_deadline_s = R.HOOK_SCAN_S
    rec.pre("t2", MAIN, "Write", {"file_path": "report.md"})
    (p / "report.md").write_text("# Q3\nTotal: 60\n")
    e = rec.post("t2", MAIN, "Write", {"file_path": "report.md"}, "ok")
    assert [w["path"] for w in e["writes"]] == ["report.md"] and "writes_unknown" not in e


def test_auto_rescan_budget_caps_the_background_attempts(proj, monkeypatch):
    """每次自動救回＝背景完整讀一次工作區；預算用完 ⇒ 維持停用、不再起背景行程。

    手動 `vacant trace rescan` 照舊可用（並重置預算）。"""
    p, _c = proj
    spawned: list[list[str]] = []
    monkeypatch.setattr(subprocess, "Popen", lambda argv, **kw: spawned.append(list(argv)))
    R.Recorder(p).baseline()
    rec = R.Recorder(p)
    st = json.loads(rec.state_path.read_text())
    st["auto_rescan"] = {"n": R.AUTO_RESCAN_MAX, "ts": 0}
    rec.state_path.write_text(json.dumps(st))
    rec.scan_deadline_s = 1e-9
    rec.pre("t", MAIN, "Bash", {"command": "ls"})
    rec.post("t", MAIN, "Bash", {"command": "ls"}, "")
    st = _state(p)
    assert st["scan_disabled"]                                  # 照樣停用
    assert st["auto_rescan"]["n"] == R.AUTO_RESCAN_MAX          # 不再加
    assert not spawned                                           # 不再起背景行程
    # 手動救回照舊：成功、並重置預算
    out = R.Recorder(p).rescan()
    assert out["rescanned"] is True and "auto_rescan" not in _state(p)


def test_module_main_accepts_rescan(proj, capsys):
    """`python -m vacant_network.trace.recorder rescan <ws>`：背景行程的入口。"""
    p, _c = proj
    _died_after_gc(p)
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = R.main(["rescan", str(p.resolve())])
    assert rc == 0
    info = json.loads(buf.getvalue().strip().splitlines()[-1])
    assert info["rescanned"] is True
    assert "scan_disabled" not in _state(p)
