"""磁碟空間與資料留存治理（`vacant_network/retention.py`）測試。

驗證：
1. 壓縮病歷物件庫（`compact_trace`）能刪除未曾變動的背景工作區檔案 blob，
   同時 100% 保持 Ed25519 簽章鏈（`Recorder.verify` / `verify_since`）完整，
   且 `Trace.file_text` 與 `Trace.materialize` 能透過即時工作區 SHA-256 驗證無縫還原。
2. 壓縮後的專案若繼續執行後續步驟，修改原本未變動的檔案時，`Recorder._scan`
   會自動補回修改前的 `before` blob，不會遺失歷史快照。
3. 隔離區壓縮（`compact_quarantine`）能清理被拒絕/舊候選與孤兒 blob，同時保留已放行候選且不破壞 `Ledger.verify_all()`。
4. 工作區重試目錄清理（`compact_work`）、vrun 暫存清理（`compact_vrun_dir`）、日誌截斷（`compact_logs`）與 CLI `vacant gc` 正常運作。
"""
from __future__ import annotations

import json
import os
import pathlib

import pytest

from vacant_network import cli, retention
from vacant_network.adapters import hook, install as INS
from vacant_network.intake import contract as C, flow, ledger
from vacant_network.trace import capture
from vacant_network.trace.blame import Trace
from vacant_network.trace.recorder import Recorder


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    for k in ("VACANT_TRACE", "VACANT_MODE"):
        monkeypatch.delenv(k, raising=False)
    p = INS.state_root() / "install.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"agents": {}, "mode": "evidence"}))
    return tmp_path


def _step(proj: pathlib.Path, n: int, tool: str, inp: dict, write: dict | None = None):
    pre = {
        "session_id": "S1",
        "cwd": str(proj),
        "tool_name": tool,
        "tool_use_id": f"t{n}",
        "tool_input": inp,
    }
    hook.handle("claude", "PreToolUse", pre)
    for rel, content in (write or {}).items():
        f = proj / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)
    post = {**pre, "tool_response": {"stdout": "ok", "stderr": ""}}
    hook.handle("claude", "PostToolUse", post)


def test_compact_trace_reclaims_untouched_blobs_and_preserves_chain_and_blame(env):
    proj = env / "work" / "big_proj"
    proj.mkdir(parents=True)
    # 建立 30 個大型背景檔案（模擬大型 repo 未動到的檔案）與 1 個會被修改的檔案
    for i in range(30):
        (proj / f"bg_{i:02d}.txt").write_text(f"background content {i}\n" * 200)
    (proj / "app.py").write_text("def calc():\n    return 1\n")

    hook.handle("claude", "UserPromptSubmit", {
        "session_id": "S1",
        "cwd": str(proj),
        "prompt": "Update app.py to return 2.",
    })
    _step(proj, 1, "Read", {"file_path": str(proj / "app.py")})
    _step(proj, 2, "Write", {"file_path": str(proj / "app.py"), "content": "def calc():\n    return 2\n"},
          write={"app.py": "def calc():\n    return 2\n"})

    ws = capture.workspace_for(str(proj))
    rec = Recorder(ws)
    ok_before, msg_before = rec.verify()
    assert ok_before, msg_before

    # Dry-run 先檢查可回收的未變動背景 blob 數量（30 個背景檔）
    dry = retention.compact_trace(dry_run=True)
    assert dry["files_removed"] == 30
    assert dry["bytes_freed"] > 50_000

    # 實際執行壓縮
    res = retention.compact_trace(dry_run=False)
    assert res["files_removed"] == 30
    assert res["bytes_freed"] == dry["bytes_freed"]

    # 1. 簽章鏈與增量驗證必須 100% 完好
    ok_after, msg_after = rec.verify()
    assert ok_after, msg_after
    ok_since, _, _ = rec.verify_since(0)
    assert ok_since

    # 2. 已修改檔案的歷史前後版本都還在 objects 內
    tr = Trace(rec)
    s1_idx = tr.steps[0].post_index
    s2_idx = tr.steps[1].post_index
    assert tr.file_text(s1_idx, "app.py") == "def calc():\n    return 1\n"
    assert tr.file_text(s2_idx, "app.py") == "def calc():\n    return 2\n"

    # 3. 未變動背景檔案雖從 objects 移除，但透過即時工作區 SHA-256 比對仍可讀取與還原
    assert tr.file_text(s2_idx, "bg_00.txt") == "background content 0\n" * 200
    dest = env / "materialized"
    tr.materialize(s1_idx, dest)
    assert (dest / "app.py").read_text() == "def calc():\n    return 1\n"
    assert (dest / "bg_15.txt").read_text() == "background content 15\n" * 200

    # 4. 壓縮後若繼續執行新步驟並修改原本未變動的 bg_00.txt，Recorder._scan 會自動補存 before blob
    _step(proj, 3, "Write", {"file_path": str(proj / "bg_00.txt"), "content": "modified bg 0\n"},
          write={"bg_00.txt": "modified bg 0\n"})
    tr2 = Trace(Recorder(ws))
    assert tr2.file_text(tr2.steps[1].post_index, "bg_00.txt") == "background content 0\n" * 200
    assert tr2.file_text(tr2.steps[2].post_index, "bg_00.txt") == "modified bg 0\n"


def test_compact_quarantine_preserves_released_and_ledger_integrity(env):
    proj = env / "qproj"
    (proj / ".vacant").mkdir(parents=True, exist_ok=True)
    raw = C.scaffold("task-q1", deliverable=["report.md"], destination="dir:published")
    raw["claims"] = [
        {"id": "has_report", "verifier": "exists", "params": {"paths": ["report.md"]}},
        {"id": "has_summary", "verifier": "text", "params": {"path": "report.md", "required_headings": ["Summary"]}},
    ]
    cpath = proj / ".vacant" / "contract.json"
    cpath.write_text(json.dumps(raw, indent=2))
    flow.lock(cpath)
    task = flow.open_task(cpath)

    # 第一次提交：不合格（缺少 # Summary）-> reject
    ws_bad = env / "ws_bad"
    ws_bad.mkdir()
    (ws_bad / "report.md").write_text("bad report content without heading\n" * 100)
    r1 = flow.submit(task, ws_bad, source="test")
    assert r1["outcome"] == "reject"

    # 第二次提交：合格 -> accept & release
    ws_good = env / "ws_good"
    ws_good.mkdir()
    (ws_good / "report.md").write_text("# Summary\ngood report content\n")
    r2 = flow.submit(task, ws_good, source="test")
    assert r2["outcome"] == "accept"
    flow.release(task)

    # 執行 quarantine 壓縮（keep_latest_per_task=1）：刪除舊失敗候選（r1）與其孤兒 blob，保留已放行（r2）
    qres = retention.compact_quarantine(keep_latest_per_task=1, dry_run=False)
    assert qres["files_removed"] >= 2
    assert qres["candidates_kept"] == 1

    # 驗證 Ledger 簽章鏈依然 100% 通過
    ok, probs = task.ledger.verify(task.trust)
    assert ok, probs


def test_compact_work_and_vrun_and_logs(env):
    from vacant_network.intake.statepaths import state_dir, work_dir
    work_root = work_dir()
    # 建立兩個 run：一個舊的、一個新的（含 ws, ws2, ws3）
    old_run = work_root / "task-old" / "20260101T000000Z-aaaa"
    (old_run / "ws").mkdir(parents=True)
    (old_run / "ws" / "big.bin").write_text("x" * 20_000)

    new_run = work_root / "task-old" / "20260102T000000Z-bbbb"
    for d in ("ws", "ws2", "ws3"):
        (new_run / d).mkdir(parents=True)
        (new_run / d / "file.txt").write_text(f"content in {d}\n" * 500)

    wres = retention.compact_work(
        keep_runs_per_task=1, max_age_days=365.0, strip_workspaces_only=False, dry_run=False
    )
    # old_run 整個被刪，new_run 的 ws 與 ws2 被刪、只留最終 ws3
    assert not old_run.exists()
    assert not (new_run / "ws").exists()
    assert not (new_run / "ws2").exists()
    assert (new_run / "ws3").exists()
    assert wres["files_removed"] >= 3

    # 測試掛鉤日誌截斷
    hdir = state_dir() / "intake" / "hooks"
    hdir.mkdir(parents=True, exist_ok=True)
    (hdir / "submit.log").write_text("log line\n" * 60_000)
    lres = retention.compact_logs(max_log_bytes=10_000, dry_run=False)
    assert lres["logs_compacted"] == 1
    assert (hdir / "submit.log").stat().st_size <= 10_000

    # 測試 vrun 暫存清理
    vrun_dir = env / "vrun_results"
    (vrun_dir / "t1" / "_frozen_ws").mkdir(parents=True)
    (vrun_dir / "t1" / "_frozen_ws" / "data.bin").write_text("y" * 10_000)
    (vrun_dir / "t1" / "wire_RUN-ON").mkdir(parents=True)
    (vrun_dir / "t1" / "result.json").write_text("{}")

    vres = retention.compact_vrun_dir(vrun_dir, dry_run=False)
    assert vres["files_removed"] >= 2
    assert not (vrun_dir / "t1" / "_frozen_ws").exists()
    assert not (vrun_dir / "t1" / "wire_RUN-ON").exists()
    assert (vrun_dir / "t1" / "result.json").exists()


def test_cli_vacant_gc_json(env, capsys):
    rc = cli.main(["gc", "--dry-run", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["dry_run"] is True
    assert "bytes_freed" in out
    assert "trace" in out and "quarantine" in out and "work" in out and "logs" in out
