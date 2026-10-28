"""gc↔rescan whack-a-mole 的**設計決定與釘鎖**（round 39 量化 → round 72 決定 →
round 142+ store-on-change 收斂）。

round 39 把「跑 gc → 掃描重存 → 再跑 gc …」從軼事變成可重跑的測量：
一個 gc→scan 週期的淨节省≈0——gc 省下的磁碟被下一次增量掃描如數還回去；
大專案上重存還會超時把掃描永久停用，逐步觀察（accountability）一起失守。

**round 72 決定**（選項 B＋活躍邊界）：活躍專案的 live 背景 blob 不回收
（它們是下一次修改所需的 before 版本）；非活躍專案照舊回收。

**round 142+ store-on-change（本檔現在釘的行為）**：寫端約束取代了「補存」——
- 掃描只存**改動過**的檔案版本；未變動檔案只記 SHA-256 索引、不落盤。
- **活躍專案**：legacy store（舊時代全量複製下來的存量）中「未變動且工作區原檔
  bit 相同」的 blob 仍被 gc 保留（下一次修改所需的 before 版本）；新時代的掃描
  本身不再產生可回收的 bg blob。⇒ whack-a-mole 消失（雙重：gc 端＋掃描端）。
- **非活躍專案**：legacy blob 照舊回收（省在真正留得住的地方）；回收後讀端走
  「工作區 + sha 驗證」回退——原檔未變動仍取回逐位元組相同內容，原檔已改動
  則那份舊版本確實不存在、誠實回 UNKNOWN。簽章鏈全程完整。

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

    # legacy store（舊時代全量複製下來的 bg blob，store-on-change 不再產生這種東西）：
    # 活躍專案的保留規則對它同樣成立——它是下次修改所需的 before 版本
    star_sha = rec.load_index(
        json.loads(rec.state_path.read_text())["last_index"])["bg_00.txt"].sha256
    legacy = (proj / "bg_00.txt").read_bytes()
    rec.blobs.put_bytes(legacy)   # 內容定址 → 同一個 sha
    assert rec.blobs.path(star_sha).is_file()
    with_legacy = _store_bytes(rec)

    # gc（真實機制，預設 active_window_s）：活躍專案的背景 blob 被保留
    res = retention.compact_trace(dry_run=False)
    assert res["files_removed"] == 0, (
        f"active project's live blobs were reclaimed: {res['files_removed']}; "
        "the whack-a-mole rule is back")
    assert _store_bytes(rec) == with_legacy

    # 下一次增量掃描（真實機制：再走一步，不改任何檔）不重存
    _step(proj, 2, "Read", {"file_path": str(proj / "app.py")})
    assert _store_bytes(rec) == with_legacy, (
        "the next scan re-stored gc's blobs: gc→scan round-trip is not zero")


def test_inactive_project_gc_reclaims_reads_honest_afterward(env):
    """非活躍專案：gc 照舊回收（省在留得住處）——round 142+ store-on-change 後的讀端語義。

    round 72 的決定釘的是「專案回來時補存逐位元組相同」；round 142+ 的寫端約束
    取代了補存：未變動的背景內容**不再落盤**（所以 gc 對新時代的專案無東西可回收），
    legacy store（舊時代全量複製下來的存量，正是 1003 上 872M store 的形態）被回收後，
    讀端走「工作區 + sha 驗證」回退：
    - 工作區原檔未變動 ⇒ 仍取回逐位元組相同的內容（零磁碟成本，不補存）；
    - 原檔其後已被改動 ⇒ 那份舊版本確實不存在——誠實回 UNKNOWN（不崩、不假 PASS）。
    兩種情況下簽章鏈都完整。
    """
    proj = _make_project(env, "inactive", 12)
    ws = capture.workspace_for(str(proj))
    rec = Recorder(ws)

    star_rel = "bg_00.txt"
    star_path = proj / star_rel
    idx_sha = json.loads(rec.state_path.read_text())["last_index"]
    star_sha = rec.load_index(idx_sha)[star_rel].sha256
    original = star_path.read_bytes()

    # legacy store：把這份 bg 內容直接放進 blob 庫（模擬舊時代的存量）
    assert rec.blobs.put_bytes(original) == star_sha

    # 非活躍（active_window_s=0.0）：gc 回收它
    res = retention.compact_trace(active_window_s=0.0, dry_run=False)
    assert res["files_removed"] >= 1
    assert not rec.blobs.path(star_sha).is_file()   # gc 確實回收了它

    # 工作區原檔未變動 ⇒ 讀端回退取回逐位元組相同的內容（零磁碟成本）
    from vacant_network.trace.blame import Trace
    assert Trace(Recorder(ws)).file_text(idx_sha, star_rel) == original.decode("utf-8")

    # 原檔其後已被改動 ⇒ 那份舊版本確實不存在，誠實 UNKNOWN
    star_path.write_text("something entirely different\n")
    assert Trace(Recorder(ws)).file_text(idx_sha, star_rel) is None, (
        "a reclaimed old version is a defined UNKNOWN, not a fabricated PASS")

    # 簽章鏈完整（回收內容不傷鏈）
    ok, msg = rec.verify()
    assert ok, msg
