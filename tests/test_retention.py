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


def test_auto_gc_records_growth_point(env, capsys):
    """round 186（ASSIGNMENT 🔴 最優先驗收：「量它從零開始一天長多少」）：
    auto gc 每次真跑自動記一筆用量點進 `$VACANT_HOME/growth.jsonl`（零設定、fail-open），
    schema 含 ts/home/total_bytes/per_dir_bytes/objects_files/gc_last（與 ops 工具同欄位）；
    頻率限制跳過（skipped_rate_limited）不記新筆。"""
    _seed_trace_project(env)
    vh = pathlib.Path(os.environ["VACANT_HOME"])
    gpath = vh / "growth.jsonl"

    rc = cli.main(["gc", "--auto", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["status"] == "ok"
    assert out["growth"]["ok"] is True

    assert gpath.is_file()
    lines = [json.loads(l) for l in gpath.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1
    rec = lines[0]
    assert rec["home"] == str(vh)
    assert rec["total_bytes"] > 0
    assert "trace" in rec["per_dir_bytes"]
    assert rec["objects_files"] >= 0
    assert rec["gc_last"]["status"] == "ok"
    assert rec["source"] == "auto_gc"

    # 頻率限制跳過：不濫記
    rc = cli.main(["gc", "--auto", "--json"])
    out2 = json.loads(capsys.readouterr().out)
    assert rc == 1 and out2["status"] == "skipped_rate_limited"
    lines2 = [l for l in gpath.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines2) == 1, "skipped 不得記新筆"


def test_growth_point_byte_cap_and_dedup(env, capsys, monkeypatch):
    """round 186：growth.jsonl 位元組硬上限（保留最新、淘汰最舊）；同分鐘同 home 的舊筆
    被本筆取代（--force 連跑不濫記）；無效行不背。"""
    _seed_trace_project(env)
    vh = pathlib.Path(os.environ["VACANT_HOME"])
    gpath = vh / "growth.jsonl"
    # 塞 6 筆舊歷史（每筆 ~220 B，總量 1.3 KB 超上限）＋ 1 行垃圾
    old = [{"ts": f"2026-10-0{i}T00:00:00+0000", "home": str(vh),
            "total_bytes": i, "pad": "x" * 100} for i in range(1, 7)]
    gpath.write_text("\n".join(json.dumps(r) for r in old) + "\nnot json\n")
    cap = 800
    monkeypatch.setattr(retention, "DEFAULT_GROWTH_LOG_BYTES", cap)

    rc = cli.main(["gc", "--auto", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["status"] == "ok"

    raw = gpath.read_text(encoding="utf-8")
    assert len(raw.encode("utf-8")) <= cap, "超位元組上限的成長日誌自身會突破封頂"
    lines = [json.loads(l) for l in raw.splitlines() if l.strip()]
    assert lines[-1]["total_bytes"] > 0 and "pad" not in lines[-1], "最新行（本筆）必留"
    assert "not json" not in raw, "無效行不背"
    # 最舊優先淘汰：留下的舊筆必是 6 筆中最新的後綴
    old_kept = [r for r in lines if "pad" in r]
    assert old_kept == old[-len(old_kept):], "淘汰必須最舊優先"


def test_growth_point_fail_open_does_not_break_gc(env, capsys, monkeypatch):
    """round 186：growth 快照出錯只記 body、不得拖垮 gc（fail-open 紅線）。"""
    _seed_trace_project(env)

    def boom(sroot):
        raise OSError("disk gone")
    monkeypatch.setattr(retention, "_growth_snapshot", boom)

    rc = cli.main(["gc", "--auto", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["status"] == "ok", "量具錯誤不得讓 gc 失敗"
    assert out["growth"]["ok"] is False
    assert "disk gone" in out["growth"].get("error", "")


def test_envelope_accounting_accounts_growth_log(env):
    """round 186：growth.jsonl 已註冊進 ENVELOPE_COMPONENTS（位元組硬上限），
    封頂帳目不把它點名為 unaccounted（accounting_complete 保持成立）。"""
    _seed_trace_project(env)
    vh = pathlib.Path(os.environ["VACANT_HOME"])
    (vh / "growth.jsonl").write_text('{"ts": "x", "total_bytes": 1}\n')

    acct = retention.envelope_accounting(vh)
    assert acct["unaccounted"] == []
    assert acct["accounting_complete"] is True
    names = {c["name"] for c in acct["components"]}
    assert "growth.jsonl" in names


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


def test_usage_envelope_gauge(env, capsys):
    """round 168（ASSIGNMENT 🔴 最優先、驗收條件 1 → 常規量具）：
    `vacant usage` 給出「總計對穩態封頂的百分比＋各分組餘量」。

    誠實口徑（ops/packets/disk_top_priority.md §3/§4）：封頂是各分組上限的
    **加總**（trace 64 MiB ＋ wire body 96 ＋ wire index 8 ＋ 固定面 ~10 MiB），
    不是一條程式保證的單一硬上限——人讀輸出必須帶「不是一條單一開關」的註記，
    不得被讀成單一硬上限。wire body／index 分開計量（index.jsonl 是 index，
    其餘是 body）。量具同時進 `--json`（機器可讀）。
    """
    _seed_trace_project(env, name="envl")
    # wire 兩分組：body（.req/.resp.bin）與 index（index.jsonl）分開落盤
    wdir = pathlib.Path(os.environ["VACANT_HOME"]) / "possess" / "proxyd" / "wire"
    wdir.mkdir(parents=True, exist_ok=True)
    (wdir / "a.req.bin").write_bytes(b"x" * 3000)
    (wdir / "a.resp.bin").write_bytes(b"y" * 4000)
    idx_line = '{"n": 1}\n'
    (wdir / "index.jsonl").write_text(idx_line, encoding="utf-8")

    rep = retention.usage_report()
    envl = rep["envelope"]
    # 封頂是明碼常數，加總口徑（不是一條單一開關）
    assert envl["planned_steady_state_bytes"] == retention.STABLE_ENVELOPE_BYTES == 256 * 1024 * 1024
    assert "不是一條單一開關" in envl["note"]
    groups = {g["name"]: g for g in envl["groups"]}
    # trace 物件：現值 vs 64 MiB 上限＋餘量
    tr = groups["trace_objects"]
    assert tr["bytes"] > 0
    assert tr["cap_bytes"] == retention.DEFAULT_TRACE_BUDGET_BYTES
    assert tr["headroom_bytes"] == tr["cap_bytes"] - tr["bytes"]
    # wire body＝7000（body 檔加總、不含 index.jsonl）；index＝該行位元組數
    assert groups["wire_body"]["bytes"] == 7000
    assert groups["wire_body"]["cap_bytes"] == retention.DEFAULT_WIRE_BODY_BYTES
    assert groups["wire_index"]["bytes"] == len(idx_line.encode())
    assert groups["wire_index"]["cap_bytes"] == retention.DEFAULT_WIRE_INDEX_BYTES
    assert groups["wire_index"]["headroom_bytes"] == (
        retention.DEFAULT_WIRE_INDEX_BYTES - len(idx_line.encode()))
    # 總計（state＋work）vs 封頂：百分比與在不在內
    assert envl["total_bytes"] > 0
    assert envl["within_envelope"] is True
    assert 0 < envl["pct_of_envelope"] < 1
    assert abs(envl["pct_of_envelope"]
               - round(100.0 * envl["total_bytes"] / retention.STABLE_ENVELOPE_BYTES, 2)) < 0.01
    # 人讀輸出：封頂行＋各分組餘量＋「不是一條單一開關」註記
    rc = cli.main(["usage"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "穩態封頂" in out and "256 MiB" in out, out
    assert "不是一條單一開關" in out, "封頂口徑必須自報是加總、不是單一硬上限：\n" + out
    assert "餘量" in out, "各分組餘量缺：\n" + out
    # JSON 同欄位（常規量具＝機器可讀）
    rc = cli.main(["usage", "--json"])
    outj = json.loads(capsys.readouterr().out)
    assert outj["envelope"]["total_bytes"] == envl["total_bytes"]
    assert outj["envelope"]["within_envelope"] is True


def test_envelope_byte_caps_sum_within_stable():
    """round 176（packet §4 誠實缺口→程式不變量）：各分組位元組上限的**加總**
    必須 ≤ 穩態封頂——否則「加總」就超出封頂、封頂變成紙面數字。
    純常數斷言，不碰磁碟。"""
    # round 190：加總含**所有**命名位元組上限（bytes ＋ fixed 組件），
    # 不只是三大組——fixed 面也有命名上限後，封頂加總的語義才完整。
    s = sum(b for _, kind, b, _ in retention.ENVELOPE_COMPONENTS
            if kind in ("bytes", "fixed") and b)
    assert s <= retention.STABLE_ENVELOPE_BYTES, (
        f"分組位元組上限加總 {s} B 超出穩態封頂 {retention.STABLE_ENVELOPE_BYTES} B："
        "「加總」已不是封頂，需調大 STABLE_ENVELOPE_BYTES 或調小分組上限")


def test_envelope_accounting_registry_complete(env):
    """round 176（ASSIGNMENT 🔴 最優先、packet §4：「總計封頂本身不是一條程式保證，
    只是一個可驗算的加總」）→ 本輪把它變成程式可驗的不變量：state_dir 的每個
    top-level 組件都必須在 ENVELOPE_COMPONENTS 註冊表裡（有名有姓的上限：位元組硬
    上限／每檔上限／計數制／固定不增長）；已知布局 ⇒ unaccounted == []。"""
    _seed_trace_project(env, name="acc")
    vh = pathlib.Path(os.environ["VACANT_HOME"])
    acct = retention.envelope_accounting(vh)
    assert acct["accounting_complete"] is True
    assert acct["unaccounted"] == []
    names = {c["name"] for c in acct["components"]}
    assert names <= {name for name, *_ in retention.ENVELOPE_COMPONENTS}
    assert acct["byte_caps_sum"] <= retention.STABLE_ENVELOPE_BYTES
    # 量具同報（人讀與 JSON 都看得到）
    rep = retention.usage_report()
    envl = rep["envelope"]
    assert envl["accounting"]["accounting_complete"] is True
    assert envl["within_envelope"] is True


def test_envelope_accounting_flags_unknown_component(env):
    """round 176：註冊表裡沒有負責人的 top-level 組件（某程式路徑無上限寫新資料，
    或外人放檔）必須被量具**点名**，且不得宣稱「在封頂內」——帳目不完整不是
    「在內」。只報告、不刪除（fail-open：Vacant 不刪自己語義不認得的檔）。"""
    _seed_trace_project(env, name="acc2")
    vh = pathlib.Path(os.environ["VACANT_HOME"])
    (vh / "mystery_dir").mkdir()
    (vh / "mystery_dir" / "blob.bin").write_bytes(b"x" * 1000)

    acct = retention.envelope_accounting(vh)
    assert acct["unaccounted"] == ["mystery_dir"]
    assert acct["accounting_complete"] is False

    rep = retention.usage_report()
    envl = rep["envelope"]
    assert envl["accounting"]["unaccounted"] == ["mystery_dir"]
    assert envl["within_envelope"] is False, "帳目不完整時不得宣稱在封頂內"
    # 該檔未被刪除（fail-open）
    assert (vh / "mystery_dir" / "blob.bin").is_file()


def test_envelope_fixed_components_have_named_caps():
    """round 190（ASSIGNMENT 🔴 最優先；packet §4 誠實缺口→程式不變量）：
    `fixed` 類型組件（adapters / gc_report.json / gc_last.json / gc.lock）此前只有
    「不增長」的語義保證、沒有命名上限——某條程式路徑若開始往固定面寫無上限
    資料，量具偵測不到，要等人類注意到才算數。round 190 起每個 fixed 組件都必須
    有命名位元組上限（`DEFAULT_FIXED_COMPONENT_BYTES`），「固定」面真增長時由量具
    點名。純常數斷言，不碰磁碟。"""
    fixed = [(n, b) for n, k, b, _ in retention.ENVELOPE_COMPONENTS if k == "fixed"]
    assert fixed, "ENVELOPE_COMPONENTS 應含 fixed 組件（adapters 等安裝面）"
    for name, cap in fixed:
        msg = (f"{name}：fixed 組件必須有命名位元組上限"
               "（§4 缺口：無上限的「不增長」語義保證量具偵測不到）")
        assert isinstance(cap, int) and cap > 0, msg + f"；實際={cap!r}"


def test_envelope_accounting_flags_fixed_component_overrun(env):
    """round 190（packet §4：「若未來某 fixed 組件實際增長，需在此表升級為計數制或
    位元組上限」→ 收口）：`adapters` 安裝面長過命名上限 ⇒ 量具必須點名
    （`fixed_overrun` 含該組件、`fixed_within_caps` False）、封頂量具不得宣稱
    「在封頂內」；只報告、不刪除（fail-open：fixed 面沒有回收路徑，Vacant 不刪
    自己語義不認得的增長）。"""
    vh = pathlib.Path(os.environ["VACANT_HOME"])
    ad = vh / "adapters"
    ad.mkdir(parents=True, exist_ok=True)
    (ad / "install.json").write_text("{}", encoding="utf-8")
    ok = retention.envelope_accounting(vh)
    assert ok["fixed_within_caps"] is True
    assert ok["fixed_overrun"] == {}

    cap = retention.DEFAULT_FIXED_COMPONENT_BYTES
    big = ad / "leak.bin"
    big.write_bytes(b"x" * (cap + 16 * 1024))
    bad = retention.envelope_accounting(vh)
    assert bad["fixed_within_caps"] is False
    assert "adapters" in bad["fixed_overrun"]
    assert bad["fixed_overrun"]["adapters"]["bytes"] > cap
    assert bad["fixed_overrun"]["adapters"]["cap_bytes"] == cap
    # 只報告、不刪除（fail-open）
    assert big.is_file()

    # 封頂量具同報：fixed 面越限時不得宣稱「在封頂內」
    envl = retention.usage_report()["envelope"]
    assert envl["accounting"]["fixed_within_caps"] is False
    assert envl["within_envelope"] is False


def test_envelope_counted_components_have_named_total_caps():
    """round 192（ASSIGNMENT 🔴 最優先；packet §4 誠實缺口→程式不變量）：
    count-based 組件（trace/projects 步鏈＋索引、intake、quarantine）此前只有
    計數制／每檔機制上限、**沒有總位元組上限**——檔案數／專案數／步數隨時間
    累積時，這些分組可無上限增長，而量具偵測不到。round 192 起每個 count-based
    組件都必須有命名總位元組上限（`COMPONENT_TOTAL_CAPS`），且**所有**命名位元組
    上限（機制上限＋總上限）加總仍 ≤ 穩態封頂——否則「加總」超出封頂、封頂變
    紙面數字。純常數斷言，不碰磁碟。"""
    caps = retention.COMPONENT_TOTAL_CAPS
    # 三個 count-based 分組都必須在冊
    for name in ("trace", "intake", "quarantine"):
        msg = f"{name}：count-based 分組必須有命名總位元組上限（§4 缺口："
        "無總上限的計數制量具偵測不到長期增長）"
        assert name in caps and isinstance(caps[name], int) and caps[name] > 0, msg
    # trace 的總上限 ≥ objects 機制上限（含 projects 子上限）
    assert caps["trace"] > retention.DEFAULT_TRACE_BUDGET_BYTES, (
        "trace 總上限必須大於 objects 機制上限：trace/projects 步鏈不在 objects 預算內")
    # 所有命名位元組上限加總仍 ≤ 穩態封頂（round 176 不變量的 round 192 擴充）
    mech = sum(b for _, kind, b, _ in retention.ENVELOPE_COMPONENTS
               if kind in ("bytes", "fixed") and b)
    extra = caps["trace"] - retention.DEFAULT_TRACE_BUDGET_BYTES  # projects 子上限
    s = mech + extra + caps["intake"] + caps["quarantine"]
    assert s <= retention.STABLE_ENVELOPE_BYTES, (
        f"所有命名位元組上限加總 {s} B 超出穩態封頂 {retention.STABLE_ENVELOPE_BYTES} B")


def test_envelope_accounting_flags_counted_component_overrun(env, capsys):
    """round 192（packet §4「有界但無 byte cap」→ 收口）：count-based 分組
    （intake／quarantine）實際位元組長過命名總上限 ⇒ 量具必須點名（`overrun`
    含該組件、`within_caps` False）、封頂量具不得宣稱「在封頂內」；只報告、
    不刪除（fail-open：這些分組的回收路徑是計數制／每檔截斷，Vacant 不因越限
    就刪自己語義不認得的檔）。"""
    vh = pathlib.Path(os.environ["VACANT_HOME"])
    (vh / "intake").mkdir(parents=True, exist_ok=True)
    (vh / "quarantine").mkdir(parents=True, exist_ok=True)

    ok = retention.envelope_accounting(vh)
    assert ok["within_caps"] is True
    assert ok["overrun"] == {}

    # intake 越限：8 MiB 總上限＋16 KiB 洩漏
    cap_in = retention.DEFAULT_INTAKE_TOTAL_CAP_BYTES
    leak_in = vh / "intake" / "hook_log_leak.txt"
    leak_in.write_bytes(b"x" * (cap_in + 16 * 1024))
    bad_in = retention.envelope_accounting(vh)
    assert bad_in["within_caps"] is False
    assert "intake" in bad_in["overrun"]
    assert bad_in["overrun"]["intake"]["bytes"] > cap_in
    assert bad_in["overrun"]["intake"]["cap_bytes"] == cap_in

    # quarantine 越限：16 MiB 總上限＋16 KiB 洩漏
    cap_q = retention.DEFAULT_QUARANTINE_TOTAL_CAP_BYTES
    leak_q = vh / "quarantine" / "task_x" / "decision_leak.bin"
    leak_q.parent.mkdir(parents=True, exist_ok=True)
    leak_q.write_bytes(b"y" * (cap_q + 16 * 1024))
    bad = retention.envelope_accounting(vh)
    assert bad["within_caps"] is False
    assert "quarantine" in bad["overrun"]
    assert bad["overrun"]["quarantine"]["bytes"] > cap_q
    assert bad["overrun"]["quarantine"]["cap_bytes"] == cap_q
    # 只報告、不刪除（fail-open）
    assert leak_in.is_file() and leak_q.is_file()

    # 封頂量具同報：count-based 面越限時不得宣稱「在封頂內」
    envl = retention.usage_report()["envelope"]
    assert envl["accounting"]["within_caps"] is False
    assert envl["within_envelope"] is False

    # R20261030_0233-2：組件越限的人讀提示必須同時點出兩處上限定義，
    # 避免維護者只查 COMPONENT_TOTAL_CAPS（count-based 總上限）而漏掉
    # fixed 組件（adapters 等）的 ENVELOPE_COMPONENTS（位元組硬上限）。
    rc = cli.main(["usage"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "COMPONENT_TOTAL_CAPS 或 ENVELOPE_COMPONENTS" in out, (
        "組件超命名上限的提示必須同時指向 COMPONENT_TOTAL_CAPS 與 ENVELOPE_COMPONENTS：\n" + out)


def test_envelope_accounting_flags_trace_projects_overrun(env):
    """round 192（packet §4：trace/projects 步鏈＋索引「有界但無 byte cap」→ 收口）：
    `trace/` 整體長過命名總上限（objects 64 MiB ＋ projects 32 MiB）⇒ 量具點名
    （`overrun` 含 `trace`、`within_caps` False）；只報告、不刪除（fail-open：
    projects 步鏈是記責記錄，GC 向來不碰 chain.ndjson——越限是量具的事，不是
    回收路徑的事）。"""
    vh = pathlib.Path(os.environ["VACANT_HOME"])
    _seed_trace_project(env, name="proj_over")
    pd = vh / "trace" / "projects"
    assert pd.is_dir()
    target = sorted(pd.iterdir())[0]

    ok = retention.envelope_accounting(vh)
    assert ok["within_caps"] is True

    cap = retention.COMPONENT_TOTAL_CAPS["trace"]
    # 只把 trace 頂過 96 MiB 總上限（objects 為空，projects 寫 cap+16K 必超）
    big = target / "chain_bloat.ndjson"
    big.write_bytes(b"z" * (cap + 16 * 1024))
    bad = retention.envelope_accounting(vh)
    assert bad["within_caps"] is False
    assert "trace" in bad["overrun"]
    assert bad["overrun"]["trace"]["bytes"] > cap
    assert bad["overrun"]["trace"]["cap_bytes"] == cap
    # 只報告、不刪除（fail-open：步鏈是記責記錄）
    assert big.is_file()

    envl = retention.usage_report()["envelope"]
    assert envl["accounting"]["within_caps"] is False
    assert envl["within_envelope"] is False


def test_usage_envelope_fail_open_missing_home(tmp_path, monkeypatch, capsys):
    """state 目錄不存在時封頂量具仍要給得出（total=0、在內），不崩（fail-open）。"""
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "nope"))
    rep = retention.usage_report()
    envl = rep["envelope"]
    assert envl["total_bytes"] == 0
    assert envl["within_envelope"] is True
    assert envl["pct_of_envelope"] == 0.0


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


def test_usage_envelope_disabled_wire_caps_and_group_overrun(env, monkeypatch, capsys):
    """VACANT_WIRE_BODY_BYTES=0 / VACANT_WIRE_INDEX_BYTES=0 代表「上限已關」（None），
    不可當成 0 B 上限誤報超標；且當任一有上限的分組（如 trace_objects）超標時，
    即使總量 ≤ 256 MiB，within_envelope 也必須為 False。"""
    from vacant_network.intake.statepaths import state_dir
    vh = state_dir()
    wdir = vh / "possess" / "proxyd" / "wire"
    wdir.mkdir(parents=True, exist_ok=True)
    (wdir / "a.req.bin").write_bytes(b"x" * 1000)
    (wdir / "index.jsonl").write_text('{"n": 1}\n', encoding="utf-8")
    odir = vh / "trace" / "objects" / "aa"
    odir.mkdir(parents=True, exist_ok=True)
    (odir / ("a" * 64)).write_bytes(b"z" * 500)

    monkeypatch.setenv("VACANT_WIRE_BODY_BYTES", "0")
    monkeypatch.setenv("VACANT_WIRE_INDEX_BYTES", "0")
    monkeypatch.setenv("VACANT_TRACE_BUDGET_BYTES", "100")

    rep = retention.usage_report(with_estimate=False)
    envl = rep["envelope"]
    groups = {g["name"]: g for g in envl["groups"]}
    assert groups["wire_body"]["cap_bytes"] is None
    assert groups["wire_body"]["headroom_bytes"] is None
    assert groups["wire_index"]["cap_bytes"] is None
    assert groups["wire_index"]["headroom_bytes"] is None
    assert groups["trace_objects"]["cap_bytes"] == 100
    assert groups["trace_objects"]["headroom_bytes"] == -400
    assert envl["within_envelope"] is False

    rc = cli.main(["usage", "--no-estimate"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "wire_body    : 1000 B（上限已關）" in out, out
    assert "wire_index   : 9 B（上限已關）" in out, out
    assert "⚠" in out and "✓ 在封頂內" not in out, out


def test_compact_logs_truncates_project_perf_jsonl_and_prunes_stale_rounds(env):
    """compact_logs 除 intake/hooks 日誌外，也必須截斷 trace/projects/*/perf.jsonl，
    並清理超過保留數量的舊 intake/hooks/rounds_*.json。"""
    from vacant_network.intake.statepaths import state_dir
    vh = state_dir()
    pdir = vh / "trace" / "projects" / "proj1"
    pdir.mkdir(parents=True, exist_ok=True)
    perf = pdir / "perf.jsonl"
    perf.write_text(('{"ts": 1.0, "agent": "pi", "event": "post", "ms": 12.3, "pad": "' + ("p" * 80) + '"}\n') * 300)

    hdir = vh / "intake" / "hooks"
    hdir.mkdir(parents=True, exist_ok=True)
    for i in range(15):
        rf = hdir / f"rounds_sess{i:03d}_tag.json"
        rf.write_text('{"n": 1}\n', encoding="utf-8")
        os.utime(rf, (1000 + i, 1000 + i))

    dry = retention.compact_logs(vh, max_log_bytes=10_000, keep_rounds_files=10, dry_run=True)
    real = retention.compact_logs(vh, max_log_bytes=10_000, keep_rounds_files=10, dry_run=False)
    assert dry["logs_compacted"] == real["logs_compacted"] == 1
    assert dry["bytes_freed"] == real["bytes_freed"] > 15_000
    assert perf.stat().st_size <= 10_000
    remaining_rounds = sorted(p.name for p in hdir.glob("rounds_*.json"))
    assert len(remaining_rounds) == 10
    assert "rounds_sess000_tag.json" not in remaining_rounds
    assert "rounds_sess014_tag.json" in remaining_rounds


def test_compact_trace_protects_recent_orphan_blobs_against_race_condition(env):
    """驗證 compact_trace 在清理未引用孤立物件時，對最近建立的 blob（處於 orphan_grace_s 內）予以保留，
    避免背景 auto_gc 併發執行時誤刪主行程剛寫入的新 blob。"""
    vh = pathlib.Path(os.environ["VACANT_HOME"])
    ws = env / "work" / "recent_orphan"
    ws.mkdir(parents=True)
    rec = Recorder(ws)
    rec.baseline()
    
    # 建立一個孤立 blob（未記在鏈上）
    orphan_bytes = b"RECENT_CONCURRENT_BLOB_CONTENT_12345"
    sha = rec.blobs.put_bytes(orphan_bytes)
    blob_path = rec.blobs.path(sha)
    assert blob_path.is_file()

    # 1) 當 orphan_grace_s=60.0 時，剛建立的新 blob 必須受到保護，不可被刪除
    res_protected = retention.compact_trace(vh, dry_run=False, orphan_grace_s=60.0)
    assert res_protected["files_removed"] == 0
    assert blob_path.is_file()

    # 2) 手動將 blob 的 mtime 推回 120 秒前
    import time
    old_time = time.time() - 120.0
    os.utime(blob_path, (old_time, old_time))

    # 超過 60 秒寬限期後，才能被判定為歷史孤兒清理
    res_pruned = retention.compact_trace(vh, dry_run=False, orphan_grace_s=60.0)
    assert res_pruned["files_removed"] == 1
    assert not blob_path.exists()


def test_usage_overrun_hint_guides_to_both_caps_registries(env, capsys):
    """當組件超過命名上限時，vacant usage 人讀提示文字必須引導至 COMPONENT_TOTAL_CAPS 或 ENVELOPE_COMPONENTS。"""
    from vacant_network import cli
    vh = retention.state_dir()
    adapters = vh / "adapters"
    adapters.mkdir(parents=True, exist_ok=True)
    (adapters / "heavy.bin").write_bytes(b"A" * 1_150_000)
    rc = cli.main(["usage", "--no-estimate"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "⚠ adapters 超命名上限" in out
    assert "retention.COMPONENT_TOTAL_CAPS 或 ENVELOPE_COMPONENTS" in out


def test_usage_report_and_growth_point_resolve_symlinked_vacant_home(tmp_path, monkeypatch, capsys):
    """當 ~/.vacant（或 $VACANT_HOME / $VACANT_WORK）是指向其他分割區或目錄的 symlink 時，
    usage_report、vacant usage CLI 與 record_growth_point 必須先 resolve 根目錄，
    不可讓 _tree_size 將根目錄當成 symlink 回傳 0 B 而導致 totals.state_dir=0、
    envelope.total_bytes=0 與 growth.jsonl total_bytes=0。"""
    real_vh = tmp_path / "real_vacant"
    real_vh.mkdir(parents=True)
    sym_vh = tmp_path / "sym_vacant"
    sym_vh.symlink_to(real_vh)

    real_wk = tmp_path / "real_work"
    real_wk.mkdir(parents=True)
    sym_wk = tmp_path / "sym_work"
    sym_wk.symlink_to(real_wk)

    monkeypatch.setenv("VACANT_HOME", str(sym_vh))
    monkeypatch.setenv("VACANT_WORK", str(sym_wk))

    odir = sym_vh / "trace" / "objects" / "ab"
    odir.mkdir(parents=True)
    (odir / ("b" * 64)).write_bytes(b"x" * 4096)
    (sym_wk / "run1").mkdir(parents=True)
    (sym_wk / "run1" / "artifact.bin").write_bytes(b"y" * 2048)

    rep = retention.usage_report(with_estimate=False)
    assert rep["state_dir"] == str(real_vh.resolve())
    assert rep["work_dir"] == str(real_wk.resolve())
    assert rep["totals"]["state_dir"] >= 4096
    assert rep["totals"]["work_dir"] >= 2048
    assert rep["envelope"]["total_bytes"] == rep["totals"]["state_dir"] + rep["totals"]["work_dir"]

    rc = cli.main(["usage", "--no-estimate", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["state_dir"] == str(real_vh.resolve())
    assert out["totals"]["state_dir"] >= 4096
    assert out["envelope"]["total_bytes"] >= 6144

    gp = retention.record_growth_point()
    assert gp["ok"] is True
    assert gp["record"]["home"] == str(real_vh.resolve())
    assert gp["record"]["total_bytes"] >= 4096


def test_auto_gc_resolves_symlinked_vacant_home(tmp_path, monkeypatch):
    """ASSIGNMENT 🔴最優先驗收(a)＋審查指示 §四-1：$VACANT_HOME 為 symlink 時，
    auto_gc 必須先解析到實體狀態目錄；gc_report.json／gc.lock／growth.jsonl
    都要寫進實體目錄，且成長紀錄 `home` 記實體解析路徑、`total_bytes > 0`
    （symlink 不得被當成根導致 _tree_size 回 0 B、穩態封頂量具失去錨點）。"""
    real_vh = tmp_path / "real_vacant"
    real_vh.mkdir(parents=True)
    sym_vh = tmp_path / "sym_vacant"
    sym_vh.symlink_to(real_vh)
    monkeypatch.setenv("VACANT_HOME", str(sym_vh))

    res = retention.auto_gc(force=True)
    assert res["status"] == "ok"
    assert res["growth"]["record"]["home"] == str(real_vh.resolve())
    assert res["growth"]["record"]["total_bytes"] > 0
    assert (real_vh / retention.AUTO_GC_REPORT_NAME).exists()
    assert (real_vh / "gc.lock").exists()
    assert (real_vh / "growth.jsonl").exists()


def test_verify_trace_chains_resolves_symlinked_vacant_home(tmp_path, monkeypatch):
    """ASSIGNMENT 🔴最優先驗收(a)(c)＋審查指示 §四-1：$VACANT_HOME 為 symlink 時，
    verify_trace_chains 必須透過 _resolve_state_dir 解析到實體狀態目錄；
    trace 專案目錄不存在時回 (0, True, [])——symlink 根不得被當成找不到
    專案目錄或誤判失敗。"""
    real_vh = tmp_path / "real_vacant"
    real_vh.mkdir(parents=True)
    sym_vh = tmp_path / "sym_vacant"
    sym_vh.symlink_to(real_vh)
    monkeypatch.setenv("VACANT_HOME", str(sym_vh))

    count, ok, errs = retention.verify_trace_chains()
    assert count == 0
    assert ok is True
    assert errs == []








def test_verify_trace_chains_detects_corrupted_chain(tmp_path, monkeypatch):
    """ASSIGNMENT 🔴最優先驗收(c)負對照：chain.ndjson 遭損毀時，verify_trace_chains
    必須誠實回 (count=1, ok=False, errors 點名該專案)——不漏放、不崩潰。"""
    real_vh = tmp_path / "real_vacant"
    proj = real_vh / "trace" / "projects" / "corrupted_proj"
    proj.mkdir(parents=True)
    (proj / "chain.ndjson").write_text("not a json chain\n", encoding="utf-8")
    monkeypatch.setenv("VACANT_HOME", str(real_vh))

    count, ok, errs = retention.verify_trace_chains()
    assert count == 1
    assert ok is False
    assert len(errs) == 1
    assert "corrupted_proj" in errs[0]


def test_verify_trace_chains_valid_chain_passes(env):
    """ASSIGNMENT 🔴最優先驗收(c)正對照：具合法 Ed25519 簽章鏈的病歷專案，
    verify_trace_chains 必須回 (count=1, ok=True, errors=[])——與損毀鏈負對照
    (test_verify_trace_chains_detects_corrupted_chain) 形成雙向契約閉環。"""
    _seed_trace_project(env, name="valid_proj", n_files=1)
    count, ok, errs = retention.verify_trace_chains()
    assert count == 1
    assert ok is True
    assert errs == []


def test_verify_trace_chains_mixed_valid_and_corrupted_projects(env):
    """ASSIGNMENT 🔴最優先驗收(c)記責隔離：同時存在合法簽章鏈與損毀鏈時，
    verify_trace_chains 計數 2、整體 ok=False，且 errors 僅點名損毀專案——
    局部損毀不誤傷合法專案（與正/負兩對照合成三向契約閉環）。"""
    _seed_trace_project(env, name="valid_proj", n_files=1)
    cproj = pathlib.Path(os.environ["VACANT_HOME"]) / "trace" / "projects" / "corrupted_proj"
    cproj.mkdir(parents=True, exist_ok=True)
    (cproj / "chain.ndjson").write_text("not a json chain\n", encoding="utf-8")

    count, ok, errs = retention.verify_trace_chains()
    assert count == 2
    assert ok is False
    assert len(errs) == 1
    assert "corrupted_proj" in errs[0]
    assert all("valid_proj" not in e for e in errs)


def test_verify_trace_chains_explicit_root_and_non_project_dirs(tmp_path):
    """ASSIGNMENT 🔴最優先驗收(c)離線判定：verify_trace_chains 支援顯式指定
    狀態目錄（root=Path，不依賴 $VACANT_HOME），且遍歷 projects 時自動忽略
    非目錄雜檔與無 chain.ndjson 之子目錄——不誤傷、不崩潰。"""
    custom_vh = tmp_path / "custom_vacant"
    pdir = custom_vh / "trace" / "projects"
    pdir.mkdir(parents=True)
    (pdir / "empty_proj").mkdir()
    (pdir / "stray_file.txt").write_text("stray\n", encoding="utf-8")
    bad_proj = pdir / "bad_proj"
    bad_proj.mkdir()
    (bad_proj / "chain.ndjson").write_text("not json\n", encoding="utf-8")

    count, ok, errs = retention.verify_trace_chains(root=custom_vh)
    assert count == 1
    assert ok is False
    assert len(errs) == 1
    assert "bad_proj" in errs[0]


def test_record_growth_point_dedup_and_invalid_line_handling(tmp_path):
    """ASSIGNMENT 🔴最優先驗收(a)真機 growth.jsonl 契約：record_growth_point
    同分鐘同 home 連跑以最新筆覆蓋舊筆（--force 連跑不濫記），且損毀行安全
    跳過不崩潰——寫入後檔案恰 1 行、兩次回傳 ok 皆 True。"""
    custom_vh = tmp_path / "custom_vh"
    custom_vh.mkdir()
    (custom_vh / "growth.jsonl").write_text("invalid json line\n", encoding="utf-8")

    r1 = retention.record_growth_point(root=custom_vh)
    r2 = retention.record_growth_point(root=custom_vh)
    assert r1["ok"] is True
    assert r2["ok"] is True

    lines = (custom_vh / "growth.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["home"] == str(custom_vh.resolve())


def test_cli_vacant_gc_verify_corrupted_chain_exit_code(tmp_path, capsys):
    """ASSIGNMENT 🔴最優先驗收(c)：`vacant gc --verify` 遇損毀簽章鏈→回傳 exit code 1，
    `--json` 含 "verify_ok": false 與含損毀專案名之 verify_errors——拒絕假 PASS；
    該專案仍計入 verified_projects（已掃描、驗證失敗）。"""
    vh = tmp_path / "vh"
    pdir = vh / "trace" / "projects" / "broken_proj"
    pdir.mkdir(parents=True)
    (pdir / "chain.ndjson").write_text("bad chain\n", encoding="utf-8")
    saved = os.environ.get("VACANT_WORK")
    os.environ["VACANT_WORK"] = str(tmp_path / "work_empty")  # hermetic：gc 不觸及真實工作目錄
    try:
        rc = retention.main(["gc", "--state-dir", str(vh), "--verify", "--json"])
    finally:
        if saved is None:
            os.environ.pop("VACANT_WORK", None)
        else:
            os.environ["VACANT_WORK"] = saved
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["verify_ok"] is False
    assert out["verified_projects"] == 1
    assert any("broken_proj" in e for e in out["verify_errors"])


def test_verify_trace_chains_missing_or_empty_projects_dir(tmp_path):
    """ASSIGNMENT 驗收 (c)：全新安裝／空狀態目錄——verify_trace_chains 安全回傳 (0, True, [])。

    1) trace/projects 不存在：不崩潰、不拋 FileNotFoundError，回傳 (0, True, [])。
    2) trace/projects 存在但內部無專案：同樣回傳 (0, True, [])。
    """
    empty_vh = tmp_path / "empty_vh"
    empty_vh.mkdir()  # 完全空白目錄（未建立 trace 目錄）
    count, ok, errs = retention.verify_trace_chains(root=empty_vh)
    assert count == 0
    assert ok is True
    assert errs == []
    (empty_vh / "trace" / "projects").mkdir(parents=True)  # 存在但內部無專案
    count, ok, errs = retention.verify_trace_chains(root=empty_vh)
    assert count == 0
    assert ok is True
    assert errs == []


def test_cli_vacant_gc_verify_corrupted_chain_human_output_and_exit_code(tmp_path, capsys):
    """ASSIGNMENT 🔴最優先驗收(c) 人讀版：`vacant gc --verify`（非 --json）遇損毀簽章鏈，
    stdout 印出「驗證失敗 ✗」、列出損毀專案名錯誤項目，並以 exit code 1 退出，不可誤判 0／假 PASS。"""
    vh = tmp_path / "vh"
    pdir = vh / "trace" / "projects" / "bad_proj"
    pdir.mkdir(parents=True)
    (pdir / "chain.ndjson").write_text("corrupted chain\n", encoding="utf-8")
    saved = os.environ.get("VACANT_WORK")
    os.environ["VACANT_WORK"] = str(tmp_path / "work_empty")  # hermetic：gc 不觸及真實工作目錄
    try:
        rc = retention.main(["gc", "--state-dir", str(vh), "--verify"])
    finally:
        if saved is None:
            os.environ.pop("VACANT_WORK", None)
        else:
            os.environ["VACANT_WORK"] = saved
    assert rc == 1
    out = capsys.readouterr().out
    assert "驗證失敗 ✗" in out
    assert "bad_proj" in out
    assert "1 個專案簽章鏈 驗證失敗 ✗" in out


def test_compact_vrun_dir_attempt_workspaces_and_missing_dir(tmp_path):
    # 1) 目標目錄不存在：安全回傳 0 位元組 / 0 檔案，不崩潰
    missing = retention.compact_vrun_dir(tmp_path / "nonexistent")
    assert missing == {"bytes_freed": 0, "files_removed": 0}

    # 2) 含收據之執行目錄：清理 _attempt_*_ws 重試工作區，保留 receipts_*.ndjson
    run_dir = tmp_path / "runs"
    t1 = run_dir / "t1"
    for name in ("_attempt_1_ws", "_attempt_2_ws"):
        ws = t1 / name
        ws.mkdir(parents=True)
        (ws / "tmp.py").write_text("x = 1\n", encoding="utf-8")
    receipts = t1 / "receipts_run.ndjson"
    receipts.write_text("{\"attempt\": 1}\n", encoding="utf-8")

    res = retention.compact_vrun_dir(run_dir, dry_run=False)
    assert res["files_removed"] >= 2
    assert not (t1 / "_attempt_1_ws").exists()
    assert not (t1 / "_attempt_2_ws").exists()
    assert receipts.is_file()
    assert receipts.read_text(encoding="utf-8") == "{\"attempt\": 1}\n"


def test_compact_work_missing_dir_and_strip_workspaces_preserves_logs(tmp_path):
    # 1) 目標目錄不存在：安全回傳 0/0/0，不崩潰
    missing = retention.compact_work(tmp_path / "nonexistent")
    assert missing == {"bytes_freed": 0, "files_removed": 0, "runs_scanned": 0}

    # 2) strip_workspaces_only=True：舊 run 只回收 ws 工作區，保留輕量日誌
    wroot = tmp_path / "work"
    run1_ws = wroot / "t1" / "run1" / "ws"
    run1_ws.mkdir(parents=True)
    (run1_ws / "big.bin").write_text("x" * 20_000, encoding="utf-8")
    log1 = wroot / "t1" / "run1" / "agent_stdout.log"
    log1.write_text("step 1 done\n", encoding="utf-8")
    (wroot / "t1" / "run2" / "ws").mkdir(parents=True)

    res = retention.compact_work(wroot, keep_runs_per_task=1, strip_workspaces_only=True, dry_run=False)
    assert res["files_removed"] >= 1
    assert not (wroot / "t1" / "run1" / "ws").exists()
    assert log1.is_file()
    assert log1.read_text(encoding="utf-8") == "step 1 done\n"


def test_compact_quarantine_missing_dir_and_orphan_objects(tmp_path) -> None:
    """compact_quarantine：無隔離區目錄時安全回傳 0/0/0；quarantine/objects 未被候選引用的孤兒物件被安全回收。"""
    res0 = retention.compact_quarantine(tmp_path / "nonexistent")
    assert res0["bytes_freed"] == 0
    assert res0["files_removed"] == 0
    assert res0["candidates_kept"] == 0

    qroot = tmp_path / "custom_vh" / "quarantine"
    obj_file = qroot / "objects" / "ab" / "orphan_blob"
    obj_file.parent.mkdir(parents=True)
    obj_file.write_bytes(b"orphan data\n")
    past = 1700000000.0  # 固定過去時間戳（2023-11-14），免依賴 time import
    os.utime(obj_file, (past, past))
    (qroot / "candidates").mkdir()

    res = retention.compact_quarantine(tmp_path / "custom_vh", dry_run=False, orphan_grace_s=0.0)
    assert res["files_removed"] >= 1
    assert not obj_file.is_file()


def test_compact_wire_missing_dir_safe(tmp_path: Path) -> None:
    """compact_wire：wire 捕獲目錄不存在時安全回傳零釋放統計字典、不拋異常。"""
    rep = retention.compact_wire(tmp_path / "nonexistent")
    assert rep["body_bytes_freed"] == 0
    assert rep["body_files_removed"] == 0
    assert rep["index_bytes_freed"] == 0
    assert rep["index_lines_dropped"] == 0


def test_compact_logs_missing_dir_safe(tmp_path: Path) -> None:
    """compact_logs：狀態目錄不存在（無 intake/hooks 與 trace/projects）時安全回傳零釋放字典、不拋異常。"""
    rep = retention.compact_logs(tmp_path / "nonexistent")
    assert rep == {"bytes_freed": 0, "logs_compacted": 0}


def test_compact_session_hooks_missing_dir_safe(tmp_path: Path) -> None:
    """compact_session_hooks：possess/hooks 目錄不存在時安全回傳零釋放統計字典、不拋異常。"""
    rep = retention.compact_session_hooks(tmp_path / "nonexistent")
    assert rep["bytes_before"] == 0
    assert rep["files_before"] == 0
    assert rep["bytes_freed"] == 0
    assert rep["files_removed"] == 0
    assert rep["files_truncated"] == 0


def test_compact_trace_missing_dir_safe(tmp_path: Path) -> None:
    """compact_trace：狀態目錄下無 trace 子目錄時安全回傳與完整報告同形的零釋放字典、不拋異常。"""
    rep = retention.compact_trace(tmp_path / "nonexistent")
    assert rep == {"bytes_freed": 0, "files_removed": 0, "projects_scanned": 0,
                   "kept_blobs": 0, "aborted": False}


def test_gc_all_missing_dir_and_verify_safe(tmp_path: Path) -> None:
    """gc_all：狀態目錄與工作區目錄皆不存在時，綜合各模組清理安全回傳零釋放字典、verify 安全回傳，不崩潰。"""
    rep = retention.gc_all(
        root=tmp_path / "nonexistent_vh",
        work_root=tmp_path / "nonexistent_work",
        verify=True,
    )
    assert rep["bytes_freed"] == 0
    assert rep["files_removed"] == 0
    assert rep["aborted"] is False
    assert rep["verify_ok"] is True
    assert rep["verified_projects"] == 0
    assert rep["verify_errors"] == []


def test_usage_report_missing_dir_safe(tmp_path: Path) -> None:
    """usage_report：狀態目錄與工作區目錄皆不存在時，安全回傳零用量統計字典，不拋異常。"""
    rep = retention.usage_report(
        tmp_path / "nonexistent_vh", tmp_path / "nonexistent_work", with_estimate=False
    )
    assert rep["totals"]["state_dir"] == 0
    assert rep["totals"]["work_dir"] == 0
    assert rep["projects"] == []
    assert all(v == 0 for v in rep["areas"].values())
    assert rep["areas"]


def test_envelope_accounting_missing_dir_safe(tmp_path: Path) -> None:
    """envelope_accounting：狀態目錄（$VACANT_HOME）不存在時，安全回傳標準會計字典——
    帳目完整、零越限、封頂加總在封頂內——不拋異常（ASSIGNMENT 🔴最優先 驗收 (c)）。"""
    acct = retention.envelope_accounting(tmp_path / "nonexistent")
    assert acct["components"] == []
    assert acct["unaccounted"] == []
    assert acct["accounting_complete"] is True
    assert acct["within_caps"] is True
    assert acct["fixed_within_caps"] is True
    assert acct["byte_caps_sum_within_envelope"] is True


def test_auto_gc_dry_run_missing_dir_safe(tmp_path: Path) -> None:
    """auto_gc：狀態目錄不存在＋dry_run=True 時，經 gc_all(dry_run=True) 安全回傳——
    status="dry_run"、ok=True、bytes_freed=0、files_removed=0——不建目錄、不拋異常
    （ASSIGNMENT 🔴最優先 驗收 (c)；retention.py 核心零改動）。"""
    p = tmp_path / "nonexistent_vh"
    rep = retention.auto_gc(root=p, dry_run=True)
    assert rep["status"] == "dry_run"
    assert rep["ok"] is True
    assert rep["bytes_freed"] == 0
    assert rep["files_removed"] == 0
    assert not p.exists()


def test_usage_main_missing_dir_safe(tmp_path: Path, capsys) -> None:
    """usage_main（`vacant usage`）：狀態目錄與工作區目錄皆不存在時，
    人讀模式 rc==0 且印出標準「Vacant 磁碟用量」＋「✓ 在封頂內」，
    --json 模式 rc==0 且輸出零用量結構（totals.state_dir==0、
    envelope.within_envelope==True）——不拋異常
    （ASSIGNMENT 🔴最優先 驗收 (a)/(c)；retention.py 核心零改動）。"""
    p_vh = tmp_path / "nonexistent_vh"
    p_work = tmp_path / "nonexistent_work"

    # 人讀模式
    rc = retention.usage_main(["--state-dir", str(p_vh), "--work-dir", str(p_work)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Vacant 磁碟用量" in out
    assert "狀態目錄總計  : 0 B" in out
    assert "穩態封頂" in out
    assert "✓ 在封頂內" in out

    # JSON 模式
    rc = retention.usage_main(["--state-dir", str(p_vh), "--work-dir", str(p_work), "--json"])
    assert rc == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["totals"]["state_dir"] == 0
    assert rep["envelope"]["within_envelope"] is True


def test_retention_main_auto_dry_run_human_output_safe(tmp_path: Path, capsys) -> None:
    """retention.main（`vacant gc` CLI）：--auto --dry-run 且狀態目錄不存在時，
    人讀模式 rc==0、stdout 含「自動 gc 預覽（--dry-run，未刪除）: 可釋放 0 B（0 個檔案）」、
    不建立目錄、不拋異常（ASSIGNMENT 🔴最優先 驗收 (c)；retention.main 零改動）。"""
    p = tmp_path / "nonexistent_vh"
    rc = retention.main(["gc", "--auto", "--dry-run", "--state-dir", str(p)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "自動 gc 預覽（--dry-run，未刪除）: 可釋放 0 B（0 個檔案）" in out
    assert not p.exists()

import argparse  # noqa: E402  (test_retention_parse_size_valid_and_invalid 用)


def test_retention_parse_size_valid_and_invalid():
    """`vacant gc --target-bytes` 的 _parse_size：整數與 K/M/G 後綴 → 精確位元組數；負數/非數字 → ArgumentTypeError。"""
    assert retention._parse_size("1024") == 1024
    assert retention._parse_size("64K") == 64 * 1024
    assert retention._parse_size("256M") == 256 * 1024 * 1024
    assert retention._parse_size("1G") == 1024 * 1024 * 1024
    for bad in ("-1", "invalid"):
        with pytest.raises(argparse.ArgumentTypeError):
            retention._parse_size(bad)


def test_compact_vrun_dir_dry_run_safe(tmp_path: Path) -> None:
    """compact_vrun_dir(dry_run=True)：正確回傳預估 bytes_freed/files_removed，
    但保留 _attempt_*_ws 重試工作區目錄與檔案不刪除（ASSIGNMENT 🔴最優先 驗收 (c)；核心零改動）。"""
    run_dir = tmp_path / "run_x"
    ws = run_dir / "_attempt_1_ws"
    ws.mkdir(parents=True)
    (run_dir / "result.json").write_text('{"ok": true}')
    junk = ws / "junk.txt"
    junk.write_bytes(b"test-bytes-for-dry-run " * 10)
    res = retention.compact_vrun_dir(run_dir, dry_run=True)
    assert res["bytes_freed"] > 0
    assert res["files_removed"] > 0
    assert junk.is_file()
    assert (run_dir / "result.json").is_file()
