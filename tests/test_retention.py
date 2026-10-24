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
from vacant_network.trace.recorder import Actor, Recorder
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


def test_cli_vacant_gc_verify_and_older_than_hours(env, capsys):
    # 建立一個合法 session
    proj = env / "ws_verify"
    proj.mkdir()
    (proj / "main.py").write_text("print('hello')\n")
    hook.handle("claude", "UserPromptSubmit", {
        "session_id": "S1",
        "cwd": str(proj),
        "prompt": "Say hello in main.py",
    })
    _step(proj, 1, "Write", {"file_path": str(proj / "main.py"), "content": "print('hello world')\n"},
          write={"main.py": "print('hello world')\n"})

    # 執行 gc --verify
    rc = cli.main(["gc", "--state-dir", str(env / "vh"), "--older-than-hours", "0.001", "--verify", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["verified_projects"] >= 1
    assert out["verify_ok"] is True
    assert out["verify_errors"] == []


# ── 自動回收（零設定 gc）與用量檢視 ─────────────────────────────────────────────

def _seed_trace_project(env, name="ap", n_files=12, size=60_000):
    """建一個有 n_files 個大型檔案的病歷專案（供 gc／預算測試用）。"""
    proj = env / "work" / name
    proj.mkdir(parents=True, exist_ok=True)
    for i in range(n_files):
        (proj / f"f_{i:02d}.txt").write_text(f"content {i}\n" * (size // 9))
    (proj / "main.py").write_text("x = 1\n")
    hook.handle("claude", "UserPromptSubmit", {
        "session_id": "S1", "cwd": str(proj), "prompt": "work",})
    _step(proj, 1, "Write", {"file_path": str(proj / "main.py"), "content": "x = 2\n"},
          write={"main.py": "x = 2\n"})
    return proj


def test_auto_gc_runs_writes_report_and_rate_limits(env, capsys):
    _seed_trace_project(env)
    vh = pathlib.Path(os.environ["VACANT_HOME"])
    # 第一次：跑
    rc = cli.main(["gc", "--auto", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["status"] == "ok"
    assert (vh / "gc_last.json").is_file()
    assert (vh / "gc_report.json").is_file()
    # 第二次（沒 --force）：頻率限制跳過
    rc = cli.main(["gc", "--auto", "--json"])
    out2 = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert out2["status"] == "skipped_rate_limited"
    # --force：跳過頻率限制
    rc = cli.main(["gc", "--auto", "--force", "--json"])
    out3 = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out3["status"] == "ok"


def test_auto_gc_locked_when_another_holder(env, capsys):
    _seed_trace_project(env, name="lp")
    vh = pathlib.Path(os.environ["VACANT_HOME"])
    import fcntl
    lock_path = vh / "gc.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        out = retention.auto_gc(force=True)  # 同程序另一把 fd：flock 仍會擋
        assert out["status"] == "skipped_locked"
        assert out["ok"] is False
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def test_auto_gc_fail_open_on_broken_state(env):
    # 把狀態目錄佔成一個檔案 → auto_gc 必須回 error，不拋例外（fail-open）
    broken = env / "broken_home"
    broken.write_text("not a dir")
    out = retention.auto_gc(root=broken, force=True)
    assert out["ok"] is False
    assert out["status"] == "error"
    assert "error" in out


def test_budget_aborts_compact_trace_at_safe_point(env, monkeypatch):
    proj = _seed_trace_project(env, name="bp", n_files=20, size=100_000)
    calls = {"n": 0}
    orig = retention._remove_path

    def slow_remove(p, *, dry_run=False):
        calls["n"] += 1
        if calls["n"] <= 3:
            import time as _t
            _t.sleep(0.15)  # 前幾個刪除各花 150ms → 0.25s 預算會在中途用掉
        return orig(p, dry_run=dry_run)

    monkeypatch.setattr(retention, "_remove_path", slow_remove)
    import time as _t
    rep = retention.compact_trace(budget=retention._Budget(_t.time() + 0.25))
    assert rep["aborted"] is True
    assert rep["files_removed"] < 20
    # 簽章鏈仍然完整
    ws = capture.workspace_for(str(proj))
    ok, msg = Recorder(ws).verify()
    assert ok, msg


def test_usage_report_fields_and_cli(env, capsys):
    _seed_trace_project(env, name="up")
    rep = retention.usage_report()
    assert rep["totals"]["state_dir"] > 0
    assert "trace_objects" in rep["areas"]
    assert rep["objects"]["count"] > 0
    assert len(rep["projects"]) == 1 and rep["projects"][0]["bytes"] > 0
    assert "bytes" in rep["reclaimable_estimate"]
    rc = cli.main(["usage", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["state_dir"] == str(pathlib.Path(os.environ["VACANT_HOME"]).resolve())
    assert "totals" in out and "projects" in out


def test_hook_spawns_auto_gc_on_stop(env, monkeypatch):
    _seed_trace_project(env, name="hp")
    spawned = {}

    class FakePopen:
        def __init__(self, cmd, **kw):
            spawned["cmd"] = cmd
            spawned["kw"] = kw
            self.pid = 4242

    import subprocess as _sp
    monkeypatch.setattr(_sp, "Popen", FakePopen)
    # 直接呼叫
    hook._spawn_auto_gc("claude", "stop")
    assert spawned.get("cmd") is not None
    cmd = spawned["cmd"]
    assert "vacant_network" in cmd and "gc" in cmd and "--auto" in cmd
    assert spawned["kw"].get("start_new_session") is True
    # 從 handle() 走（Stop 事件；VACANT_HOOK_NO_STOP 只關驗收，不關磁碟治理）
    monkeypatch.setenv("VACANT_HOOK_NO_STOP", "1")
    spawned.clear()
    out, err, rc = hook.handle("claude", "Stop", {
        "session_id": "S1", "cwd": str(env / "work" / "hp"), "stop_hook_active": False})
    assert rc == 0
    assert spawned.get("cmd") is not None, "handle(Stop) 應該觸發背景 gc"
    # VACANT_HOOK_NO_GC=1 時不觸發
    monkeypatch.setenv("VACANT_HOOK_NO_GC", "1")
    spawned.clear()
    hook.handle("claude", "Stop", {"session_id": "S1", "cwd": str(env / "work" / "hp")})
    assert spawned.get("cmd") is None

