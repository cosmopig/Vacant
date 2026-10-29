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

import hashlib
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
from test_gc_rescan_cycle import _store_bytes as _store_total  # noqa: E402


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


def test_compact_trace_write_side_restraint_honest_unknown_and_chain_intact(env):
    """round 142 store-on-change 取代了「先全量複製、再回收」的舊設計（round 145 更新本測試）。

    新語義（`workspace.scan` docstring，被明確定義）：
    1. **寫端約束**：未變動檔案的內容不落盤（只記 sha/size/mtime）——磁碟約束在寫入端
       完成，gc 對這類專案沒有東西可回收（files_removed==0），而不是「回收了才省到」。
    2. **改動那一刻存 after 版本**（copy-on-change）；第一次改動之前的 before 版本是
       **被明確定義的 UNKNOWN**——誠實回 None／missing，不崩、不假 PASS。
    3. blob 回收（舊設計存量資料或 after 版本超標時）不傷 Ed25519 簽章鏈；讀端經
       工作區 SHA-256 驗證回退仍可讀取未變動檔案。

    場景：30 個大型背景檔案 + app.py（v1→v2）。未變動檔案零 blob、可經工作區回退讀取；
    app.py 的 after 版本在庫、before 版本誠實 UNKNOWN；gc 前後簽章鏈 100% 完整；
    gc 後再改一個 bg 檔：after 版本照存（copy-on-change），其 before 誠實 UNKNOWN。
    """
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

    # 1. 寫端約束：30 個未變動背景檔案的內容**不落盤**（零 blob）
    bg_shas = {hashlib.sha256(f"background content {i}\n".encode() * 200).hexdigest()
               for i in range(30)}
    stored = {f.name for f in rec.blobs.root.rglob("*") if f.is_file()}
    assert bg_shas.isdisjoint(stored), "未變動檔案不該被複製進版本庫（round 142 寫端約束）"

    # 2. gc 沒有東西可回收（寫端約束本身就是約束）；dry-run 與實際一致
    dry = retention.compact_trace(active_window_s=0.0, dry_run=True)
    assert dry["files_removed"] == 0
    res = retention.compact_trace(active_window_s=0.0, dry_run=False)
    assert res["files_removed"] == 0

    # 3. 簽章鏈與增量驗證 100% 完好
    ok_after, msg_after = rec.verify()
    assert ok_after, msg_after
    ok_since, _, _ = rec.verify_since(0)
    assert ok_since

    # 4. 讀端語義：app.py after 版本在庫；before 版本（第一次改動前）是被明確定義的
    #    UNKNOWN（誠實 None，不假 PASS）；未變動 bg 檔經工作區 SHA-256 回退取回原文
    tr = Trace(rec)
    s1_idx = tr.steps[0].post_index
    s2_idx = tr.steps[1].post_index
    assert tr.file_text(s1_idx, "app.py") is None, "第一次改動前的 before 版本＝定義的 UNKNOWN"
    assert tr.file_text(s2_idx, "app.py") == "def calc():\n    return 2\n"
    assert tr.file_text(s2_idx, "bg_00.txt") == "background content 0\n" * 200
    dest = env / "materialized"
    missing = tr.materialize(s2_idx, dest)
    assert (dest / "app.py").read_text() == "def calc():\n    return 2\n"
    assert (dest / "bg_15.txt").read_text() == "background content 15\n" * 200
    assert "app.py" not in missing and "bg_15.txt" not in missing
    # s1 快照：app.py 的 before 版本誠實列進 missing（不崩、不假還原）
    dest2 = env / "materialized_s1"
    missing2 = tr.materialize(s1_idx, dest2)
    assert "app.py" in missing2

    # 5. gc 後繼續執行新步驟並修改原本未變動的 bg_00.txt：after 版本照存
    #    （copy-on-change）；其 before（原始 bg 內容）不追溯存＝誠實 UNKNOWN
    _step(proj, 3, "Write", {"file_path": str(proj / "bg_00.txt"), "content": "modified bg 0\n"},
          write={"bg_00.txt": "modified bg 0\n"})
    tr2 = Trace(Recorder(ws))
    assert tr2.file_text(tr2.steps[2].post_index, "bg_00.txt") == "modified bg 0\n"
    assert tr2.file_text(tr2.steps[1].post_index, "bg_00.txt") is None, "改動前版本＝定義的 UNKNOWN"
    ok3, msg3 = rec.verify()
    assert ok3, msg3


def test_compact_trace_keeps_active_project_live_blobs(env):
    """gc↔rescan 設計決定（round 72，2026-10-26；BACKLOG 選項 B＋活躍邊界）：

    對**活躍**專案（鏈活動在 `active_window_s` 內，預設 7 天），「未變動的背景 blob」
    正是那些檔案下一次被修改時所需的 **before 版本**。回收它們會被下一次掃描如數重存
    （`test_gc_rescan_cycle.py` 已量化：一個 gc→scan 週期淨节省≈0；大專案上重存還
    會超時把掃描停用、逐步觀察失守）。因此 gc 對活躍專案保留這些 blob，
    下一次增量掃描不會重存（whack-a-mole 消失）；非活躍專案照舊回收。
    """
    proj = env / "work" / "active_keep"
    proj.mkdir(parents=True)
    for i in range(8):
        (proj / f"bg_{i:02d}.txt").write_text(f"bg {i}\n" * 200)
    (proj / "app.py").write_text("x = 1\n")

    hook.handle("claude", "UserPromptSubmit", {
        "session_id": "S1", "cwd": str(proj), "prompt": "work"})
    _step(proj, 1, "Write", {"file_path": str(proj / "app.py"), "content": "x = 2\n"},
          write={"app.py": "x = 2\n"})

    ws = capture.workspace_for(str(proj))
    rec = Recorder(ws)
    baseline = _store_total(rec)
    assert baseline > 0

    # 活躍專案（預設窗口）：gc 保留 live 背景 blob，store 不縮
    res = retention.compact_trace(dry_run=False)
    assert res["files_removed"] == 0
    assert _store_total(rec) == baseline
    ok, msg = rec.verify()
    assert ok, msg

    # whack-a-mole 消失：gc 沒有回收（files_removed==0），下一次掃描無從重存；
    # 保留的 blob 也必須仍可在下一次掃描後取回。
    # round 95 原寫法用「總位元組不變」斷言——但每一步都記**自己**的 input blob，
    # 這一步的輸入和上一步不同（Write 帶 content，Read 不帶），必然多一個新 blob；
    # 「重存」在內容定址下本就無從以終態位元組區分（重存＝同 sha 同位元組），
    # 真正的釘鎖是上面的 files_removed==0。
    kept = {f.name for f in rec.blobs.root.rglob("*") if f.is_file()}
    _step(proj, 2, "Read", {"file_path": str(proj / "app.py")})
    now = {f.name for f in rec.blobs.root.rglob("*") if f.is_file()}
    assert kept <= now, "gc 保留的 blob 在下一次掃描後遺失：whack-a-mole 仍在"


def test_default_trace_budget_bounded_for_large_workspaces(env):
    """ASSIGNMENT 主軸 2（round 142）：2G repo 不該背 247 MB 的「未變動檔複製」。

    實測背景（2026-10-28）：舊碼初掃把本 repo ≤8 MB 檔案全量複製進 trace/objects
    （542 MB/17,097 blob），而當時 512 MiB 預算恰好高於現況 536 MB ⇒ sweep 空轉。
    未變動檔案的副本零追緝價值（讀端回退工作區＋驗 sha，round 139）；預算應定在
    「工作集之上、垃圾之下」——64 MiB（本專案實測工作集 63.4 MiB，見 dry-run）。
    """
    assert retention.DEFAULT_TRACE_BUDGET_BYTES <= 64 * 1024 * 1024, (
        f"預設預算 {retention.DEFAULT_TRACE_BUDGET_BYTES} B 過高："
        f"舊式全量複製快照會落在預算內而永不回收"
    )


def test_target_sweep_reclaims_active_project_redundant_blobs(env):
    """Axis 2 sweep 對**活躍**專案也生效（既有測試只釘了非活躍專案與「保留」兩端）：

    round 72 說「活躍專案的未變動背景 blob 常規保留」（whack-a-mole）；Axis 2 補充
    「超出 target_bytes 時可安全回收」（讀端回退工作區＋驗 sha，零損失）。兩條同時成立：
    未超標 ⇒ 保留；超標 ⇒ 回收且 blame 誠實（未改檔＝工作區回退；已改檔＝UNKNOWN）。
    """
    proj = env / "work" / "active_sweep"
    proj.mkdir(parents=True)
    for i in range(40):
        (proj / f"bg_{i:02d}.txt").write_text(f"background content {i}\n" * 500)
    (proj / "app.py").write_text("x = 1\n")

    hook.handle("claude", "UserPromptSubmit", {
        "session_id": "S1", "cwd": str(proj), "prompt": "work"})
    _step(proj, 1, "Write", {"file_path": str(proj / "app.py"), "content": "x = 2\n"},
          write={"app.py": "x = 2\n"})

    ws = capture.workspace_for(str(proj))
    rec = Recorder(ws)
    ok, msg = rec.verify()
    assert ok, msg

    # 未超標（預設 64 MiB ≫ 本 store）：活躍專案的背景 blob 照舊保留（round 72）
    keep = retention.compact_trace(dry_run=False)
    assert keep["files_removed"] == 0

    # 超標：sweep 按「工作區冗餘優先」回收，直到 ≤ 目標
    target = 100 * 1024
    res = retention.compact_trace(dry_run=False, target_bytes=target)
    assert res["target"]["target_reached"] is True
    assert res["target"]["bytes_remaining"] <= target

    # 簽章鏈 100% 完好（blob 回收不影響 Ed25519 鏈）
    ok, msg = rec.verify()
    assert ok, msg

    # 讀端誠實：未變動檔經工作區回退仍取回原文；已改檔的舊版本誠實 None
    tr = Trace(rec)
    idx = tr.steps[-1].post_index
    assert tr.file_text(idx, "bg_00.txt") == "background content 0\n" * 500
    (proj / "bg_01.txt").write_text("changed after gc\n")
    assert tr.file_text(idx, "bg_01.txt") is None
    assert tr.file_text(idx, "app.py") == "x = 2\n"  # 被改檔的 must-keep 版本不受影響


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
    # 2026-10-28 Axis 2 最優先新增的兩段也必須在 JSON 報告裡
    assert "wire" in out and "session_hooks" in out


def test_gc_cli_reports_wire_and_session_hooks(env, monkeypatch, capsys):
    """round 164 回歸：`vacant gc` 的人類輸出必須逐段顯示 2026-10-28 Axis 2 最優先
    新增的兩段（模型 wire 捕獲／session 事件），且釋放位元組與 `--json` 報告一致。
    修前：總計 bytes_freed 含這兩段、明細行卻沒有——實際環境裡它們是最大非-trace
    兩段（本機 wire 25 MB、hooks 0.9 MB），使用者看不出回收到哪。
    """
    import time as _time
    from vacant_network.intake.statepaths import state_dir
    sroot = state_dir().resolve()
    # wire：兩通 body（各 4 KiB）= 8 KiB > 4 KiB 上限 → 最舊一通可回收（4096 B）
    monkeypatch.setenv("VACANT_WIRE_BODY_BYTES", "4096")
    wdir = sroot / "possess" / "proxyd" / "wire"
    wdir.mkdir(parents=True, exist_ok=True)
    now = _time.time()
    for i, name in enumerate(("old.req.bin", "new.resp.bin")):
        p = wdir / name
        p.write_bytes(b"0" * 4096)
        t = now - (2 - i) * 60
        os.utime(p, (t, t))
    # session 事件：單檔 ~2.6 MB > 預設單檔上限 2 MiB → 有可截斷位元組
    hdir = sroot / "possess" / "hooks"
    hdir.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"event": "canary", "pad": "x" * 256}) + "\n"
    (hdir / "pi_1.jsonl").write_text(line * 10_000, encoding="utf-8")

    rc = retention.main(["gc", "--dry-run", "--json"])
    assert rc == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["wire"]["body_bytes_freed"] == 4096
    assert rep["wire"]["body_files_removed"] == 1
    assert rep["session_hooks"]["bytes_freed"] > 0

    rc = retention.main(["gc", "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    wire_line = next(l for l in out.splitlines() if "模型 wire" in l)
    hooks_line = next(l for l in out.splitlines() if "session 事件" in l)
    assert retention._human_bytes(rep["wire"]["body_bytes_freed"]) in wire_line
    assert retention._human_bytes(rep["session_hooks"]["bytes_freed"]) in hooks_line


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


def _seed_legacy_blob(rec: Recorder, content: bytes) -> str:
    """把一份內容直接放進物件庫，模擬舊「掃描即全存」時代的 legacy store。

    round 142+ 的 store-on-change 不再因掃描產生未引用 blob（寫端約束），
    所以「大量可回收存量」的現實形態是 legacy store——正是 1003 上 872M store 的
    形態。測試用它建立可回收的存量。"""
    sha = hashlib.sha256(content).hexdigest()
    p = rec.blobs.root / sha[:2] / sha
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return sha


def test_budget_aborts_compact_trace_at_safe_point(env, monkeypatch):
    """預算在「大量刪除中途」到期 ⇒ 安全點中止：鏈完整、已刪的不復存在、
    剩餘可下次繼續刪。慢速 `_remove_path` 模擬每檔 I/O，0.25s 預算只夠刪兩三檔。"""
    proj = _seed_trace_project(env, name="bp", n_files=1)
    rec = Recorder(capture.workspace_for(str(proj)))
    for i in range(20):   # legacy store：20 個未受鏈引用的大 blob
        _seed_legacy_blob(rec, f"legacy blob {i}\n".encode() * 2000)
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
    # `active_window_s=0.0`：模擬非活躍專案（否則 blob 被保留、無東西可刪）
    rep = retention.compact_trace(active_window_s=0.0,
                                  budget=retention._Budget(_t.time() + 0.25))
    assert rep["aborted"] is True
    assert 1 <= rep["files_removed"] < 20
    # 未刪的 blob 還在（下次可繼續刪）
    assert _store_total(rec) > 0
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


def test_usage_human_output_notes_apparent_vs_block_size(env, capsys):
    """`vacant usage` 的數字是 apparent size（st_size 加總，du -sb 同義）；
    `du -sh` 數的是已分配 block，兩者不必然相同（BACKLOG 2026-10-19：
    「對不熟悉 apparent/block 的人仍是摩擦」）。人讀輸出必須有一行註腳，
    否則使用者拿 `du -sh` 對不上會以為 Vacant 數錯了。"""
    _seed_trace_project(env, name="foot")
    rc = cli.main(["usage"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "apparent" in out, "人讀輸出缺 apparent 註腳：\n" + out
    assert "du -sh" in out, "註腳必須點名 du -sh（對不上的那個數字）：\n" + out


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


# ─────────────── 2026-10-28 Axis 2 最優先：wire 捕獲＋session hook 上限 ───────────────

def _wire_env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    return tmp_path


def _mk_wire(tmp_path, n_calls=10, body_bytes=1024 * 1024, line_pad=900):
    """造 n_calls 通 wire 捕獲（body 舊→新）＋index journal 每通一行。"""
    import time as _time
    from vacant_network.intake.statepaths import state_dir
    sroot = state_dir().resolve()
    wdir = sroot / "possess" / "proxyd" / "wire"
    wdir.mkdir(parents=True, exist_ok=True)
    now = _time.time()
    for i in range(n_calls):
        for kind in ("req", "resp"):
            p = wdir / f"r{i:04d}.{kind}.bin"
            p.write_bytes(b"0" * body_bytes)
            _time_t = now - (n_calls - i) * 60
            os.utime(p, (_time_t, _time_t))
    lines = [json.dumps({
        "call_id": i, "ts": now - (n_calls - i) * 60, "mode": "live", "status": 200,
        "request_sha256": "x" * 40, "response_sha256": "y" * 40,
        "request_bytes": body_bytes, "response_bytes": body_bytes,
        "pad": "z" * line_pad,
    }) for i in range(n_calls)]
    (wdir / "index.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return sroot, wdir


def test_compact_wire_caps_bodies_keeps_index_and_journal(tmp_path, monkeypatch):
    _wire_env(tmp_path, monkeypatch)
    sroot, wdir = _mk_wire(tmp_path, n_calls=10, body_bytes=1024 * 1024)
    MB = 1024 * 1024
    rep = retention.compact_wire(sroot, max_body_bytes=4 * MB, max_index_bytes=8 * 1024)
    # body：20 檔 × 1 MiB = 20 MiB → 保留最新 4 檔（4 MiB）、刪最舊 16 檔
    assert rep["body_files_before"] == 20
    assert rep["body_files_removed"] == 16
    assert rep["body_bytes_freed"] == 16 * MB
    kept = sorted(f.name for f in wdir.iterdir() if f.suffix == ".bin")
    # 4 個**檔**（非 4 通）＝4 MiB：最新兩通的 req/resp（round 154 同 commit 的
    # 註解與 `body_files_removed == 16` 皆為按檔口徑；被拆對的 body 內容誠實 UNKNOWN，
    # 證據在 index.jsonl 的 sha256，見 `compact_wire` docstring）
    assert kept == [f"r{i:04d}.{k}.bin" for i in range(8, 10) for k in ("req", "resp")]
    # index：10 行 × ~1.1 KB > 8 KiB → 保留最新完整行（keep=4 KiB）；每行仍是合法 JSON
    text = (wdir / "index.jsonl").read_text(encoding="utf-8")
    kept_lines = [json.loads(l) for l in text.splitlines() if l.strip()]
    assert 1 <= len(kept_lines) < 10
    assert kept_lines[-1]["call_id"] == 9          # 最新一通保留
    assert min(l["call_id"] for l in kept_lines) >= 1   # 最舊的至少被截掉一些
    assert rep["index_lines_dropped"] == 10 - len(kept_lines)
    # attest 仍可讀（追緝/對帳不受影響；被截掉的通＝UNKNOWN，不損毀）。
    # `read_relay_calls` 回 `list[dict] | None`（見 `vrun/attest.py`）；不可解析的
    # 行會帶 `_unparsable`——截斷必須是整行，所以每一行都不該有它。
    from vacant_network.vrun import attest
    calls = attest.read_relay_calls(wdir / "index.jsonl", since=0)
    assert calls is not None and len(calls) == len(kept_lines)
    assert all("_unparsable" not in c for c in calls), "截斷後不得有殘行"


def test_compact_wire_dry_run_changes_nothing(tmp_path, monkeypatch):
    _wire_env(tmp_path, monkeypatch)
    sroot, wdir = _mk_wire(tmp_path, n_calls=10, body_bytes=1024 * 1024)
    before = {p.name: p.stat().st_size for p in wdir.iterdir()}
    rep = retention.compact_wire(sroot, max_body_bytes=4 * 1024 * 1024,
                                 max_index_bytes=8 * 1024, dry_run=True)
    after = {p.name: p.stat().st_size for p in wdir.iterdir()}
    assert before == after, "dry-run 不得改動任何檔案"
    assert rep["body_files_removed"] == 16          # 估算有、刪除無


def test_compact_session_hooks_count_and_file_caps(tmp_path, monkeypatch):
    import time as _time
    _wire_env(tmp_path, monkeypatch)
    from vacant_network.intake.statepaths import state_dir
    sroot = state_dir().resolve()
    hdir = sroot / "possess" / "hooks"
    hdir.mkdir(parents=True, exist_ok=True)
    now = _time.time()
    for i in range(250):
        p = hdir / f"pi_{i:04d}.jsonl"
        p.write_text(json.dumps({"run_id": str(i), "event": "session_start"}) + "\n")
        t = now - (300 - i) * 10
        os.utime(p, (t, t))
    big = hdir / "pi_big.jsonl"
    big.write_text(json.dumps({"event": "x", "pad": "z" * 200}) * 20000)  # ~4.2 MiB
    os.utime(big, (now - 5, now - 5))
    rep = retention.compact_session_hooks(sroot, max_file_bytes=2 * 1024 * 1024,
                                          keep_sessions=200)
    # 251 檔 → 保留最新 200 個（含 big）→ 刪 51 個最舊
    assert rep["files_before"] == 251
    assert rep["files_removed"] == 51
    # big（最新）保留但被截到 ≤ 1 MiB（一半上限）＋一行的餘量
    assert rep["files_truncated"] == 1
    assert big.stat().st_size <= 2 * 1024 * 1024 + 1024
    remaining = sorted(f.name for f in hdir.iterdir())
    assert "pi_big.jsonl" in remaining
    assert len(remaining) == 200


def test_gc_all_dry_run_does_not_touch_wire(tmp_path, monkeypatch):
    _wire_env(tmp_path, monkeypatch)
    sroot, wdir = _mk_wire(tmp_path, n_calls=4, body_bytes=2048)
    monkeypatch.setenv("VACANT_WIRE_BODY_BYTES", "2048")
    monkeypatch.setenv("VACANT_WIRE_INDEX_BYTES", "1024")
    before = {p.name: p.read_bytes() for p in wdir.iterdir()}
    rep = retention.gc_all(root=sroot, work_root=tmp_path / "work", dry_run=True, verify=False)
    after = {p.name: p.read_bytes() for p in wdir.iterdir()}
    assert rep["dry_run"] is True
    assert before == after, "gc_all(dry_run=True) 不得刪除或截斷 wire 檔案"
    assert rep["wire"]["body_files_removed"] > 0


def test_compact_session_hooks_no_double_count_on_oversized_old_session(tmp_path, monkeypatch):
    import time as _time
    _wire_env(tmp_path, monkeypatch)
    from vacant_network.intake.statepaths import state_dir
    sroot = state_dir().resolve()
    hdir = sroot / "possess" / "hooks"
    hdir.mkdir(parents=True, exist_ok=True)
    now = _time.time()
    for i, sz in enumerate([30_000, 1_000, 1_000]):
        p = hdir / f"s{i}.jsonl"
        p.write_text(("a" * 99 + "\n") * (sz // 100))
        t = now - (10 - i) * 60
        os.utime(p, (t, t))
    rep = retention.compact_session_hooks(sroot, max_file_bytes=10_000, keep_sessions=2)
    assert rep["files_removed"] == 1
    assert rep["files_truncated"] == 0
    assert rep["bytes_freed"] == 30_000
    assert rep["bytes_freed"] <= rep["bytes_before"]


def test_compact_trace_dry_run_matches_real_run_with_orphans_and_target(env):
    vh = pathlib.Path(os.environ["VACANT_HOME"])
    ws = env / "work" / "orphan_sweep"
    ws.mkdir(parents=True)
    (ws / "bg.txt").write_bytes(b"B" * 30_000)
    rec = Recorder(ws)
    rec.baseline()
    rec.blobs.put_bytes((ws / "bg.txt").read_bytes())
    rec.blobs.put_bytes(b"O" * 50_000)
    dry = retention.compact_trace(vh, dry_run=True, target_bytes=40_000)
    real = retention.compact_trace(vh, dry_run=False, target_bytes=40_000)
    assert dry["bytes_freed"] == real["bytes_freed"] == 50_000
    assert dry["files_removed"] == real["files_removed"] == 1
    assert dry["target"]["bytes_freed"] == real["target"]["bytes_freed"] == 0


def test_target_sweep_evicts_historical_versions_and_blame_returns_unknown(env):
    from vacant_network.trace.blame import blame_location
    from vacant_network.trace.locate import Location

    vh = pathlib.Path(os.environ["VACANT_HOME"])
    ws = env / "work" / "hist_sweep"
    ws.mkdir(parents=True)
    (ws / "app.py").write_text("line1 = 100\nline2 = 999\n")
    rec = Recorder(ws)
    rec.baseline()
    s1 = Actor("claude", "s1")
    s2 = Actor("claude", "s2")

    # 1) store=False 下，初始已存在於 app.py 的 line2 = 999 未落盤；
    #    s1 只改了 line1 = 200，追緝 line2 = 999 必須誠實回 UNKNOWN，不可誣賴 s1
    rec.pre("t1", s1, "Edit", {"file_path": str(ws / "app.py"), "new_string": "line1 = 200"})
    (ws / "app.py").write_text("line1 = 200\nline2 = 999\n")
    rec.post("t1", s1, "Edit", {"file_path": str(ws / "app.py"), "new_string": "line1 = 200"}, "ok")
    b0 = blame_location(Trace(rec), Location("app.py", line=2, value="999"))
    assert b0["state"] == "UNKNOWN" and b0["fault_class"] == "unattributable"

    # 2) 連續多步修改產生大量歷史版本（~250 KB），超過 target_bytes=60 KB：
    #    GC 必須能回收舊版本壓到預算以下，且回收後追緝被刪版本引入的值時誠實回 UNKNOWN
    rec.pre("t2", s1, "Write", {"file_path": str(ws / "app.py"), "content": "magic = 77777\n"})
    (ws / "app.py").write_text("pad = '" + ("A" * 50_000) + "'\nmagic = 77777\n")
    rec.post("t2", s1, "Write", {"file_path": str(ws / "app.py"), "content": "magic = 77777\n"}, "ok")

    for i in range(3, 7):
        content = f"pad = '{chr(65 + i) * 50_000}'\nmagic = 77777\n"
        rec.pre(f"t{i}", s2, "Edit", {"file_path": str(ws / "app.py"), "new_string": f"step_{i}"})
        (ws / "app.py").write_text(content)
        rec.post(f"t{i}", s2, "Edit", {"file_path": str(ws / "app.py"), "new_string": f"step_{i}"}, "ok")

    res = retention.compact_trace(vh, dry_run=False, target_bytes=60_000)
    assert res["target"]["target_reached"] is True
    assert res["target"]["bytes_remaining"] <= 60_000
    assert res["target"]["files_removed"] >= 3
    ok, msg = rec.verify()
    assert ok, msg

    # 舊版本被 GC 回收後，追緝 magic = 77777 不可誣賴最後修改 pad 的 s2，必須回 UNKNOWN
    b_after = blame_location(Trace(rec), Location("app.py", line=2, value="77777"))
    assert b_after["state"] == "UNKNOWN" and b_after["fault_class"] == "unattributable"


def test_gc_all_and_usage_report_respect_trace_budget_env(env, monkeypatch):
    vh = pathlib.Path(os.environ["VACANT_HOME"])
    ws = env / "work" / "budget_env_proj"
    ws.mkdir(parents=True)
    (ws / "app.py").write_text("x = 1\n")
    rec = Recorder(ws)
    rec.baseline()
    s1 = Actor("claude", "s1")
    for i in range(4):
        body = f"pad = '{chr(65 + i) * 30_000}'\nx = {i}\n"
        rec.pre(f"t{i}", s1, "Write", {"file_path": str(ws / "app.py"), "content": f"x={i}"})
        (ws / "app.py").write_text(body)
        rec.post(f"t{i}", s1, "Write", {"file_path": str(ws / "app.py"), "content": f"x={i}"}, "ok")

    monkeypatch.setenv("VACANT_TRACE_BUDGET_BYTES", "50000")
    urep = retention.usage_report(vh, env / "work")
    assert urep["budget"]["within_budget"] is False
    assert urep["reclaimable_estimate"]["bytes"] > 50_000

    dry = retention.gc_all(root=vh, work_root=env / "work", dry_run=True)
    real = retention.gc_all(root=vh, work_root=env / "work", dry_run=False, verify=True)
    assert dry["bytes_freed"] == real["bytes_freed"] > 50_000
    assert real["verify_ok"] is True
    assert real["trace"]["target"]["target_reached"] is True
    assert real["trace"]["target"]["bytes_remaining"] <= 50_000


def test_target_sweep_evicts_rank2_and_rank3_and_blame_returns_unknown(env):
    from vacant_network.trace.blame import blame_location
    from vacant_network.trace.locate import Location

    vh = pathlib.Path(os.environ["VACANT_HOME"])
    ws = env / "work" / "rank23_sweep"
    ws.mkdir(parents=True)
    (ws / "README.md").write_text("init\n")
    rec = Recorder(ws)
    rec.baseline()
    s1 = Actor("claude", "s1")
    rec.prompt("please set magic = 424242\n" + ("P" * 30_000), session="s1", source="user")
    rec.pre("step0", s1, "Write", {"file_path": str(ws / "app.py"), "content": "write_app"})
    (ws / "app.py").write_text("pad = '" + ("A" * 30_000) + "'\nmagic = 424242\n")
    rec.post("step0", s1, "Write", {"file_path": str(ws / "app.py"), "content": "write_app"},
             "W" * 30_000)

    # 回收前：424242 來自任務提示（input / lineage_exact）
    b_before = blame_location(Trace(rec), Location("app.py", line=2, value="424242"))
    assert b_before["state"] == "located" and b_before["fault_class"] == "input"
    assert b_before["confidence"] == "lineage_exact"

    # 壓到 10 KB：無 rank 0/1 可刪，必須動用 rank 2（最新檔案版本 app.py 30 KB）
    # 與 rank 3（提示 text_blob 30 KB、步驟 output_blob 30 KB）
    res = retention.compact_trace(vh, dry_run=False, target_bytes=10_000)
    assert res["target"]["target_reached"] is True
    assert res["target"]["bytes_remaining"] <= 10_000
    assert res["target"]["files_removed"] >= 3
    ok, msg = rec.verify()
    assert ok, msg

    # app.py 經工作區回退仍可讀到 step0 引入 424242，但提示與步驟 I/O blob 已被 GC 回收，
    # 追緝不可誣賴 agent_fault，必須誠實回 UNKNOWN
    b_after = blame_location(Trace(rec), Location("app.py", line=2, value="424242"))
    assert b_after["state"] == "UNKNOWN" and b_after["fault_class"] == "unattributable"


def test_compact_logs_includes_auto_gc_log_and_dry_run_matches(env):
    from vacant_network.intake.statepaths import state_dir
    hdir = state_dir() / "intake" / "hooks"
    hdir.mkdir(parents=True, exist_ok=True)
    (hdir / "auto_gc.log").write_text(("gc line " + ("x" * 90) + "\n") * 300)
    dry = retention.compact_logs(max_log_bytes=10_000, dry_run=True)
    real = retention.compact_logs(max_log_bytes=10_000, dry_run=False)
    assert dry["logs_compacted"] == real["logs_compacted"] == 1
    assert dry["bytes_freed"] == real["bytes_freed"] > 15_000
    assert (hdir / "auto_gc.log").stat().st_size <= 10_000


