"""gc↔rescan whack-a-mole 的**設計決定與釘鎖**（round 39 量化 → round 72 決定）。

round 39 把「跑 gc → 掃描重存 → 再跑 gc …」從軼事變成可重跑的測量：
一個 gc→scan 週期的淨节省≈0——gc 省下的磁碟被下一次增量掃描如數還回去；
大專案上重存還會超時把掃描永久停用，逐步觀察（accountability）一起失守。
（原始量化測試見 git 歷史 round 39 版本；本檔現在釘的是決定後的行為。）

**決定（round 72，2026-10-26；BACKLOG「gc↔rescan 設計決定」選項 B＋活躍邊界）**：
- **活躍專案**（鏈上活動在 `active_window_s` 內，預設 7 天）：gc 保留「未變動且
  工作區原檔 bit 相同」的 live 背景 blob。這些 blob 正是那些檔案下一次被修改時
  所需的 **before 版本**；對活躍專案回收它們省不下任何持久磁碟（下一次掃描
  如數重存），只買回 I/O、超時與失觀的風險。⇒ whack-a-mole 消失。
- **非活躍專案**（超出窗口）：照舊回收（省在真正留得住的地方），下一次掃描
  仍會補存、且補存必須逐位元組相同（blame/還原不被悄悄改掉）。

不变式相容：本測試只讀取磁碟用量、不觸模型流量；斷言的是可重算的位元組數。
"""
from __future__ import annotations

import json
import os
import pathlib

import pytest

from vacant_network import retention
from vacant_network.adapters import hook, install as INS
from vacant_network.trace import capture
from vacant_network.trace.recorder import Recorder


def _store_bytes(rec: Recorder) -> int:
    root = rec.blobs.root
    if not root.is_dir():
        return 0
    return sum(f.stat().st_size for f in root.rglob("*") if f.is_file())


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


def _step(proj: pathlib.Path, n: int, tool: str, inp: dict,
          write: dict | None = None) -> None:
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


def _make_project(env, name: str, n_bg: int) -> pathlib.Path:
    proj = env / "work" / name
    proj.mkdir(parents=True)
    for i in range(n_bg):
        # 足夠大、且內容互不相同（避免去重遮蔽）；300 行讓每個 blob 有可測的體積
        (proj / f"bg_{i:02d}.txt").write_text(f"background content {i}\n" * 300)
    (proj / "app.py").write_text("def calc():\n    return 1\n")

    hook.handle("claude", "UserPromptSubmit", {
        "session_id": "S1", "cwd": str(proj), "prompt": "make calc return 2",
    })
    # 一步：修改 app.py（唯一被改的檔）；其餘 `n_bg` 個背景檔全程未動
    _step(proj, 1, "Write",
          {"file_path": str(proj / "app.py")},
          write={"app.py": "def calc():\n    return 2\n"})
    return proj


@pytest.mark.parametrize("n_bg", [12, 40])
def test_active_project_gc_keeps_blobs_no_whack_a_mole(env, n_bg):
    """活躍專案：gc 保留 live 背景 blob；下一次增量掃描**不**重存（淨往返=0）。

    決定前的行為是：gc 回收全部 `n_bg` 個背景 blob、下一次掃描如數重存
    （淨节省≈0 的 whack-a-mole，round 39 量化）。決定後：對活躍專案 gc 直接
    保留這些 blob，store 不縮、也不漲。
    """
    proj = _make_project(env, f"active_{n_bg}", n_bg)
    ws = capture.workspace_for(str(proj))
    rec = Recorder(ws)
    baseline = _store_bytes(rec)
    assert baseline > 0

    # gc（真實機制，預設 active_window_s）：活躍專案的背景 blob 被保留
    res = retention.compact_trace(dry_run=False)
    assert res["files_removed"] == 0, (
        f"active project's live blobs were reclaimed: {res['files_removed']}; "
        "the whack-a-mole rule is back")
    assert _store_bytes(rec) == baseline

    # 下一次增量掃描（真實機制：再走一步，不改任何檔）不重存
    _step(proj, 2, "Read", {"file_path": str(proj / "app.py")})
    assert _store_bytes(rec) == baseline, (
        "the next scan re-stored gc's blobs: gc→scan round-trip is not zero")


def test_inactive_project_gc_reclaims_and_rescan_restores_byte_identical(env):
    """非活躍專案：gc 照舊回收（省在留得住處）；補存必須逐位元組相同。

    這是決定後的**另一面**：省盤不消失，只改落在「非活躍」專案上；而專案
    回來（再次被掃描）時，補存回來的 blob 必須與回收前 bit 相同，否則
    blame/還原會被悄悄改掉。
    """
    proj = _make_project(env, "inactive", 12)
    ws = capture.workspace_for(str(proj))
    rec = Recorder(ws)
    baseline = _store_bytes(rec)

    star_sha = rec.load_index(
        json.loads(rec.state_path.read_text())["last_index"])["bg_00.txt"].sha256
    before = rec.blobs.get(star_sha)

    # 非活躍（active_window_s=0.0）：gc 回收全部背景 blob
    res = retention.compact_trace(active_window_s=0.0, dry_run=False)
    assert res["files_removed"] >= 12
    assert _store_bytes(rec) < baseline
    assert not rec.blobs.path(star_sha).is_file()   # gc 確實回收了它

    # 專案回來（下一次掃描）：如數補存，且逐位元組相同
    _step(proj, 2, "Read", {"file_path": str(proj / "app.py")})
    assert _store_bytes(rec) >= baseline * 0.9
    assert rec.blobs.get(star_sha) == before, (
        "re-materialized blob is not byte-identical to the original")
