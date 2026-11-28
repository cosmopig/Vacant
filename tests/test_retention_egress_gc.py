"""vq-7f1 缺陷 2 回歸測試：工作階段結束掛鉤觸發自動 GC 時，不可刪除 `egress.jsonl` 引用但尚未上鏈的頁面內容。

重現事故場景（2026-11-28, vq-7f1）：
- 網路出口代理把抓到的頁面寫進 `$VACANT_HOME/trace/objects/` 並記在 `<project>/egress.jsonl`，
  直到工作階段結束後才由 runner 呼叫 `sources.ingest_egress` 簽進 `chain.ndjson`。
- 工作階段結束時 `adapters/hook.py` 觸發背景 `vacant gc --auto --json`（寬限期 `AUTO_GC_ORPHAN_GRACE_S=60s`）。
- 本檔驗證三件事：
  1. 超過寬限期、尚未進鏈、但列在 `egress.jsonl` 裡的 body 物件，經掛鉤實際觸發的自動 GC 後必須完好存活
     （無論專案已有簽章鏈或僅有 `egress.jsonl`，且即使有緊預算壓力）；
  2. 超過寬限期、未出現在鏈也未出現在任何 `egress.jsonl` 的孤立物件，經同路徑 GC 後確實被刪除；
  3. 設 `VACANT_HOOK_NO_GC=1` 時，掛鉤完全不啟動 GC、孤立物件原封不動。
"""
from __future__ import annotations

import json
import os
import subprocess
import time

import pytest

from vacant_network import retention
from vacant_network.adapters import hook
from vacant_network.intake import keys
from vacant_network.trace import recorder as R
from vacant_network.trace import sources as S


@pytest.fixture
def isolated_vacant(tmp_path, monkeypatch):
    vh = tmp_path / "vacant_home"
    wk = tmp_path / "vacant_work"
    monkeypatch.setenv("VACANT_HOME", str(vh))
    monkeypatch.setenv("VACANT_WORK", str(wk))
    monkeypatch.delenv("VACANT_HOOK_NO_GC", raising=False)
    monkeypatch.setenv("VACANT_HOOK_NO_STOP", "1")
    keys.init_local()
    ws = tmp_path / "proj_alpha"
    ws.mkdir()
    return tmp_path, vh, wk, ws


def _age_past_grace(path, extra_s: float = 3600.0) -> None:
    """將檔案 mtime 推回超過 `AUTO_GC_ORPHAN_GRACE_S` 寬限期之前。"""
    old_ts = time.time() - (retention.AUTO_GC_ORPHAN_GRACE_S + extra_s)
    os.utime(path, (old_ts, old_ts))


def _trigger_session_end_and_wait_gc(monkeypatch, ws, *, agent: str = "claude", event: str = "SessionEnd"):
    """依掛鉤於工作階段結束時的真實路徑觸發背景 auto-gc，並等待該子行程實際結束。"""
    real_popen = subprocess.Popen
    spawned: list[tuple[list[str], subprocess.Popen]] = []

    def tracking_popen(cmd, *args, **kwargs):
        proc = real_popen(cmd, *args, **kwargs)
        spawned.append((list(cmd), proc))
        return proc

    monkeypatch.setattr(subprocess, "Popen", tracking_popen)
    out, err, rc = hook.handle(agent, event, {
        "session_id": "sess-vq7f1-1",
        "cwd": str(ws),
    })
    assert rc == 0, f"hook.handle returned {rc}, err={err!r}"
    gc_procs = [(cmd, p) for cmd, p in spawned if "gc" in cmd and "--auto" in cmd]
    assert len(gc_procs) == 1, f"expected hook to spawn exactly 1 auto-gc subprocess, got {spawned}"
    cmd, proc = gc_procs[0]
    assert "vacant_network" in cmd and "--auto" in cmd
    gc_rc = proc.wait(timeout=30)
    assert gc_rc == 0, f"auto-gc subprocess exited {gc_rc}"
    return cmd, out


def test_session_end_hook_auto_gc_preserves_old_egress_bodies_not_yet_in_chain(isolated_vacant, monkeypatch):
    """超過寬限期、尚未進鏈、但記在 `egress.jsonl` 裡的頁面內容，經工作階段結束掛鉤觸發的真實 auto-gc 後必須存活。"""
    tmp_path, vh, _wk, ws = isolated_vacant
    (ws / "notes.txt").write_text("initial\n", encoding="utf-8")

    # 專案 A：已有簽章鏈（僅一般步驟，尚未跑 ingest_egress ⇒ 鏈上沒有任何 source_fetch 事件）
    rec = R.Recorder(ws)
    rec.baseline()
    actor = R.Actor("claude", "sess-vq7f1-1")
    rec.pre("t1", actor, "Bash", {"command": "echo fetching"})
    rec.post("t1", actor, "Bash", {"command": "echo fetching"}, "fetching")
    assert not any(e.get("type") == "source_fetch" for e in rec.events())

    body1 = b"<html><body><p>Fictional Alpha metric: 42 (3)</p></body></html>\n" * 40
    body2 = b"<html><body><p>Fictional Beta metric: 98.6%</p></body></html>\n" * 40
    sha1 = rec.blobs.put_bytes(body1)
    sha2 = rec.blobs.put_bytes(body2)
    _age_past_grace(rec.blobs.path(sha1))
    _age_past_grace(rec.blobs.path(sha2))

    # 寫出與 egress.py 相同格式的 egress.jsonl（含一般 200 回應與無 sha256 的 TLS CONNECT）
    eg_lines = [
        json.dumps({"ts_ms": 1700000001000, "url": "http://pages.fictional.example/a.html",
                    "method": "GET", "status": 200, "sha256": sha1, "bytes": len(body1), "ua": "curl/8"}),
        json.dumps({"ts_ms": 1700000002000, "url": "https://tls.fictional.example:443",
                    "method": "CONNECT", "tls": True}),
        json.dumps({"ts_ms": 1700000003000, "url": "http://pages.fictional.example/b.html",
                    "method": "GET", "status": 200, "sha256": sha2, "bytes": len(body2), "ua": "curl/8"}),
    ]
    (rec.dir / "egress.jsonl").write_text("\n".join(eg_lines) + "\n", encoding="utf-8")

    # 專案 B：尚無 chain.ndjson（只有 egress.jsonl），同樣超過寬限期
    ws_b = tmp_path / "proj_beta"
    ws_b.mkdir()
    rec_b = R.Recorder(ws_b)
    rec_b.dir.mkdir(parents=True, exist_ok=True)
    body3 = b"<html><body><p>No-chain project page: 777</p></body></html>\n" * 40
    sha3 = rec_b.blobs.put_bytes(body3)
    _age_past_grace(rec_b.blobs.path(sha3))
    (rec_b.dir / "egress.jsonl").write_text(
        json.dumps({"ts_ms": 1700000004000, "url": "http://pages.fictional.example/c.html",
                    "method": "GET", "status": 200, "sha256": sha3, "bytes": len(body3)}) + "\n",
        encoding="utf-8",
    )
    assert not rec_b.chain_path.exists()

    # 加上緊預算壓力（遠小於三個 body 合計）確認自動 GC 在預算壓力下同樣不刪 egress body
    monkeypatch.setenv("VACANT_TRACE_BUDGET_BYTES", "1024")

    _trigger_session_end_and_wait_gc(monkeypatch, ws)

    report = json.loads((vh / "gc_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "ok", report
    assert report["auto"] is True

    # 三個尚未進鏈的 egress 頁面 body 都必須完好存活且內容一致
    assert rec.blobs.has(sha1) and rec.blobs.get(sha1) == body1
    assert rec.blobs.has(sha2) and rec.blobs.get(sha2) == body2
    assert rec_b.blobs.has(sha3) and rec_b.blobs.get(sha3) == body3

    # 之後 runner 呼叫 ingest_egress 上鏈，兩頁內容都讀得回來
    assert S.ingest_egress(rec) == 3
    fetched = S.egress_records(rec)
    assert {r["url"] for r in fetched} == {
        "http://pages.fictional.example/a.html",
        "http://pages.fictional.example/b.html",
    }
    ok, why = rec.verify()
    assert ok, why


def test_session_end_hook_auto_gc_removes_old_unreferenced_orphan_not_in_egress(isolated_vacant, monkeypatch):
    """超過寬限期、且不在鏈也不在任何 `egress.jsonl` 的真正孤立物件，經同路徑自動 GC 必須被刪除。"""
    _tmp, vh, _wk, ws = isolated_vacant
    rec = R.Recorder(ws)
    rec.baseline()

    # 一個有列在 egress.jsonl 的舊物件（必須存活）
    kept_body = b"egress-referenced body content\n" * 20
    kept_sha = rec.blobs.put_bytes(kept_body)
    _age_past_grace(rec.blobs.path(kept_sha))
    (rec.dir / "egress.jsonl").write_text(
        json.dumps({"ts_ms": 1700000010000, "url": "http://pages.fictional.example/keep.html",
                    "method": "GET", "status": 200, "sha256": kept_sha, "bytes": len(kept_body)}) + "\n",
        encoding="utf-8",
    )

    # 一個完全未被任何鏈或 egress.jsonl 引用的舊物件（必須被回收）
    orphan_body = b"completely-unreferenced-orphan-blob\n" * 50
    orphan_sha = rec.blobs.put_bytes(orphan_body)
    _age_past_grace(rec.blobs.path(orphan_sha))

    _trigger_session_end_and_wait_gc(monkeypatch, ws)

    report = json.loads((vh / "gc_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "ok", report
    assert report["trace"]["files_removed"] >= 1
    assert not rec.blobs.has(orphan_sha), "unreferenced orphan older than grace period must be removed by auto-gc"
    assert rec.blobs.has(kept_sha) and rec.blobs.get(kept_sha) == kept_body


def test_hook_no_gc_env_skips_gc_entirely(isolated_vacant, monkeypatch):
    """設 `VACANT_HOOK_NO_GC=1` 時，SessionEnd／Stop 掛鉤必須完全跳過 GC，不生子行程、不刪任何孤立物件。"""
    _tmp, vh, _wk, ws = isolated_vacant
    rec = R.Recorder(ws)
    rec.baseline()

    orphan_body = b"orphan-kept-because-no-gc-env\n" * 50
    orphan_sha = rec.blobs.put_bytes(orphan_body)
    _age_past_grace(rec.blobs.path(orphan_sha))

    monkeypatch.setenv("VACANT_HOOK_NO_GC", "1")

    spawned_cmds: list[list[str]] = []
    real_popen = subprocess.Popen

    def spy_popen(cmd, *args, **kwargs):
        spawned_cmds.append(list(cmd))
        return real_popen(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", spy_popen)

    for event in ("Stop", "SessionEnd"):
        _out, _err, rc = hook.handle("claude", event, {
            "session_id": "sess-vq7f1-nogc",
            "cwd": str(ws),
        })
        assert rc == 0

    gc_spawns = [c for c in spawned_cmds if "gc" in c and "--auto" in c]
    assert gc_spawns == [], f"VACANT_HOOK_NO_GC=1 must skip auto-gc, but saw {gc_spawns}"
    assert not (vh / "gc_report.json").exists()
    assert not (vh / "gc_last.json").exists()
    assert rec.blobs.has(orphan_sha), "orphan must remain untouched when VACANT_HOOK_NO_GC=1"
