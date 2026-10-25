"""gc↔rescan whack-a-mole：一個**已被量化**的設計張力（characterization，非 bug 報告）。

本輪（free-diverge）把自家專案反覆出現的「跑 gc → 掃描超時被永久停用 → `vacant
trace rescan` 救回 → 再跑 gc …」從軼事變成一個可重跑、可引用的測量。它釘住的是
**機制**，不是某次的時序：

- `vacant gc`（`retention.compact_trace`）依其**文件化意圖**回收「從未變動且工作區原檔
  內容相同」的背景 blob（`retention.py:416` 註解：工作區本身就是這份內容，重複副本可
  安全回收）。
- 但 `Recorder._scan` 的快路徑假設「`prev` 的所有版本都在庫裡」
  （`recorder.py:349` 註解＋`test_rescan_re_stores_the_blob_store_so_incremental_scans_are_safe`
  已把「gc 之後必須重存」釘成設計意圖）。`gc` 標記 `compacted=True` 後，下一次增量掃描
  走 `prev_stored=False`，把剛被回收的 blob **全部重存**。

兩者相加 ⇒ **gc 省下的磁碟，被下一次掃描如數還回去；一個 gc→scan 週期的淨节省≈0。**
本測試把這個週期用真實機制（真實 `compact_trace`＋真實增量掃描）量化並釘住，讓
「要不要修、往哪個方向修」變成一個**有數字**的設計決定，而不是反覆救火的感覺。

這是**已知且有意**的張力（round 36 已把「增量超時→永久停用」的政策本身留待設計決定），
所以本測試斷言的是**目前行為**（whack-a-mole 確實發生、且被完整還原），不是「它不該發生」。
要改變它，需先做 BACKLOG「gc↔rescan 設計決定」項，並連帶處理
`test_rescan_re_stores_the_blob_store_so_incremental_scans_are_safe` 所釘的意圖。

不变式相容：本測試只讀取磁碟用量、不觸模型流量；斷言的是可重算的位元組數，
「看不到的＝UNKNOWN」不在此適用（這裡看到的是真實 store 大小）。
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


@pytest.mark.parametrize("n_bg", [12, 40])
def test_gc_savings_are_fully_rematerialized_by_the_next_scan(env, n_bg):
    """一個完整的 gc→scan 週期：gc 省下的 blob 被下一次增量掃描如數還回去（淨节省≈0）。

    這是 whack-a-mole 的**機制**，不是某次超時。用小而確定可斷言的檔案數（`n_bg`）
    跑真實 `compact_trace`＋真實增量掃描，量化「回收→重存」的往返。
    """
    proj = env / "work" / f"big_{n_bg}"
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

    ws = capture.workspace_for(str(proj))
    rec = Recorder(ws)
    baseline = _store_bytes(rec)
    assert baseline > 0

    # gc（真實機制）：回收全部未變動背景 blob
    res = retention.compact_trace(dry_run=False)
    assert res["files_removed"] == n_bg              # 只回收未變動的背景檔
    freed = res["bytes_freed"]
    assert freed > 0
    compact = _store_bytes(rec)
    assert compact < baseline                        # gc 確實省了磁碟

    # 下一次增量掃描（真實機制：再走一步，不改任何檔）
    _step(proj, 2, "Read", {"file_path": str(proj / "app.py")})
    after = _store_bytes(rec)

    # whack-a-mole 的量化核心：掃描把 gc 回收的 blob 如數重存 ⇒ 淨节省≈0
    rematerialized = after - compact
    assert rematerialized >= freed * 0.9, (
        f"gc freed {freed}B but the next scan only re-stored {rematerialized}B; "
        f"the whack-a-mole (full re-materialization) is not reproduced")
    assert after >= baseline * 0.9, (
        f"store did not return to baseline: {after}B vs {baseline}B "
        f"(gc's savings stuck, which would mean the cycle is NOT whack-a-mole)")
    # 淨节省：一個 gc→scan 週期下來，磁碟回到原狀
    assert (baseline - after) < freed * 0.2, (
        f"net saving {baseline - after}B after a full gc->scan cycle is too large; "
        f"the cycle should give back ~everything gc freed")


def test_gc_savings_only_stick_when_the_scan_is_disabled(env):
    """whack-a-mole 的另一面：gc 的節省「留得住」的唯一情況是掃描已停用。

    這正是大專案的實際結局——重存超時 → `_disable_scan` 永久關掉 → gc 的節省不再被
    還回去，但代價是逐步觀察（accountability）也一起關掉。本測試量化這層取捨：
    掃描停用時，gc 的節省穩定；掃描啟用時（上一支測試），節省被如數還回。
    """
    proj = env / "work" / "disabled"
    proj.mkdir(parents=True)
    for i in range(12):
        (proj / f"bg_{i:02d}.txt").write_text(f"background content {i}\n" * 300)
    (proj / "app.py").write_text("def calc():\n    return 1\n")

    hook.handle("claude", "UserPromptSubmit", {
        "session_id": "S1", "cwd": str(proj), "prompt": "make calc return 2",
    })
    _step(proj, 1, "Write",
          {"file_path": str(proj / "app.py")},
          write={"app.py": "def calc():\n    return 2\n"})

    ws = capture.workspace_for(str(proj))
    rec = Recorder(ws)
    baseline = _store_bytes(rec)

    res = retention.compact_trace(dry_run=False)
    freed = res["bytes_freed"]
    compact = _store_bytes(rec)
    assert compact < baseline and freed > 0

    # 把掃描永久停用（大專案超時後 `_disable_scan` 的真實結果）
    st = json.loads(rec.state_path.read_text())
    st["scan_disabled"] = "an incremental scan passed 8s"
    rec.state_path.write_text(json.dumps(st))

    # 掃描已停：再走一步不會重存 ⇒ gc 的節省留得住
    _step(proj, 2, "Read", {"file_path": str(proj / "app.py")})
    after = _store_bytes(rec)
    assert after < baseline, (
        f"with the scan disabled, gc's savings should stick, but the store grew back "
        f"to {after}B from {compact}B (baseline {baseline}B)")
    assert (after - compact) < freed * 0.2, "scan was disabled; nothing should be re-stored"


def test_rematerialized_blobs_are_byte_identical(env):
    """重存回去的 blob 必須與 gc 回收前逐位元組相同（否則 blame/還原會被悄悄改掉）。

    這是 whack-a-mole 的**正確性**面：往返（gc 回收→scan 重存）不能改動內容。
    """
    proj = env / "work" / "ident"
    proj.mkdir(parents=True)
    content = "background content X\n" * 300
    for i in range(12):
        (proj / f"bg_{i:02d}.txt").write_text(f"background content {i}\n" * 300)
    (proj / "bg_star.txt").write_text(content)
    (proj / "app.py").write_text("def calc():\n    return 1\n")

    hook.handle("claude", "UserPromptSubmit", {
        "session_id": "S1", "cwd": str(proj), "prompt": "make calc return 2",
    })
    _step(proj, 1, "Write",
          {"file_path": str(proj / "app.py")},
          write={"app.py": "def calc():\n    return 2\n"})

    ws = capture.workspace_for(str(proj))
    rec = Recorder(ws)
    star_sha = rec.load_index(
        json.loads(rec.state_path.read_text())["last_index"])["bg_star.txt"].sha256
    before = rec.blobs.get(star_sha)

    assert retention.compact_trace(dry_run=False)["files_removed"] >= 12
    assert not rec.blobs.path(star_sha).is_file()          # gc 確實回收了它

    _step(proj, 2, "Read", {"file_path": str(proj / "app.py")})  # 觸發重存
    after = rec.blobs.get(star_sha)
    assert after == before, "re-materialized blob is not byte-identical to the original"
