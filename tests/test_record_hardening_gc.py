"""紀錄強化 2：保留 GC 絕不誤刪鏈引用的物件 ＋ 引用缺失檢查（`verify_trace_objects`／`--objects`）。

對應獨立稽核發現（s43/c_verify 有 16 個被鏈引用的物件被舊版 GC 刪掉）：
- 驗證 `compact_trace` 預設保留整條鏈全部事件（含超過 50 步、`source_snapshot` `pages`、
  `source_fetch` `sha256`、`prompt`、`transcript`、`input_blob`/`output_blob`、索引與索引內檔案版本、
  `coverage.rescanned.index`、未進鏈 `egress.jsonl`），只刪除未被引用的孤立物件。
- 驗證 `verify_trace_objects`／`Recorder.verify_objects`／`vacant trace verify --objects`／
  `vacant gc --verify-objects` 精準回報被刪除或損毀的引用物件。
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib

import pytest

from vacant_network import retention
from vacant_network.intake import keys
from vacant_network.trace import cli as trace_cli
from vacant_network.trace import recorder as R
from vacant_network.trace import sources as SRC


@pytest.fixture
def env(tmp_path, monkeypatch):
    vh = tmp_path / "vh"
    monkeypatch.setenv("VACANT_HOME", str(vh))
    monkeypatch.setenv("VACANT_WORK", str(tmp_path / "work"))
    monkeypatch.setenv("VACANT_TRACE", "1")
    monkeypatch.setenv("VACANT_HOOK_NO_GC", "1")
    keys.init_local()
    ws = tmp_path / "proj"
    ws.mkdir()
    return tmp_path, vh, ws


def test_gc_preserves_all_chain_referenced_objects_and_deletes_only_orphans(env):
    """超過 50 步的鏈＋source_snapshot＋source_fetch＋prompt＋transcript＋egress.jsonl＋孤立物件：
    預設 compact_trace 只刪孤立物件，全部鏈引用物件一個不漏。"""
    tmp_path, vh, ws = env
    (ws / "report.md").write_text("Revenue: 4200\n", encoding="utf-8")
    rec = R.Recorder(ws)
    rec.baseline()
    actor = R.Actor("claude", "s1")

    prompt_sha = hashlib.sha256(b"initial user prompt text").hexdigest()
    rec.prompt("initial user prompt text", session="s1", source="user")

    # 寫超過 55 步（舊版 DEFAULT_KEEP_STEPS=50 會刪掉前 5 步的 blob）
    early_output_shas: list[str] = []
    for i in range(55):
        out_text = f"step-output-{i}-" + ("Z" * 200)
        rec.pre(f"t{i}", actor, "Write", {"file_path": "report.md", "i": i})
        (ws / "report.md").write_text(f"Revenue: {4200 + i}\n", encoding="utf-8")
        ev = rec.post(f"t{i}", actor, "Write", {"file_path": "report.md", "i": i}, out_text)
        if i < 5:
            early_output_shas.append(ev["output_blob"])

    # transcript blob
    tr_bytes = json.dumps({"type": "assistant", "message": {"id": "m1", "model": "claude-haiku"}}).encode()
    tr_sha = rec.blobs.put_bytes(tr_bytes)
    rec.append("transcript", {"actor": actor.to_json(), "role": "session", "sha256": tr_sha})

    # source_snapshot pages blob
    snap_page_sha = rec.blobs.put_bytes(b"<html>Revenue: 4254</html>")
    rec.append("source_snapshot", {
        "schema": "vacant-source-snapshot/1",
        "path": "report.md",
        "pages": {"http://example.test/rev": snap_page_sha},
        "errors": {},
    })

    # source_fetch sha256 blob
    fetch_sha = rec.blobs.put_bytes(b"fetched page body from egress proxy")
    rec.append("source_fetch", {
        "schema": "vacant-source-fetch/1",
        "url": "http://example.test/api",
        "status": 200,
        "sha256": fetch_sha,
    })

    # 未進鏈的 egress.jsonl
    pending_eg_sha = rec.blobs.put_bytes(b"un-ingested egress body")
    (rec.dir / "egress.jsonl").write_text(
        json.dumps({"url": "http://example.test/pending", "sha256": pending_eg_sha}) + "\n",
        encoding="utf-8",
    )

    # rescan（產生 coverage.rescanned.index）
    r_info = rec.rescan()
    rescan_idx = r_info["index"]

    # 放入 3 個未被引用的孤立物件（推回舊 mtime）
    orphan_shas = [rec.blobs.put_bytes(f"orphan-{k}-".encode() * 100) for k in range(3)]
    for osha in orphan_shas:
        os.utime(rec.blobs.path(osha), (1700000000.0, 1700000000.0))

    # 執行預設 compact_trace
    rep = retention.compact_trace(vh, dry_run=False, orphan_grace_s=0.0)
    assert rep["files_removed"] == 3, rep

    # 孤立物件全刪
    for osha in orphan_shas:
        assert not rec.blobs.has(osha), f"unreferenced orphan {osha} should be deleted"

    # 全部鏈引用物件都必須還在
    for must_keep in [prompt_sha, tr_sha, snap_page_sha, fetch_sha, pending_eg_sha, rescan_idx, *early_output_shas]:
        assert rec.blobs.has(must_keep), f"referenced object {must_keep} was wrongly deleted by GC!"

    # 驗證工具必須 100% 通過
    obj_rep = retention.verify_trace_objects(vh, verify_hashes=True)
    assert obj_rep["ok"] is True
    assert obj_rep["missing_count"] == 0
    assert obj_rep["corrupt_count"] == 0
    assert obj_rep["referenced_count"] >= len(early_output_shas) + 6


def test_source_snapshot_and_fetch_survive_tight_target_bytes(env):
    """即使在極緊的 target_bytes 下，source_snapshot pages 與 source_fetch sha256 仍屬硬底不刪除。"""
    _tmp, vh, ws = env
    rec = R.Recorder(ws)
    rec.baseline()
    snap_sha = rec.blobs.put_bytes(b"S" * 20_000)
    fetch_sha = rec.blobs.put_bytes(b"F" * 20_000)
    rec.append("source_snapshot", {"path": "r.md", "pages": {"http://a.test/1": snap_sha}, "errors": {}})
    rec.append("source_fetch", {"url": "http://a.test/2", "sha256": fetch_sha})
    orphan_sha = rec.blobs.put_bytes(b"O" * 20_000)
    os.utime(rec.blobs.path(orphan_sha), (1700000000.0, 1700000000.0))

    retention.compact_trace(vh, dry_run=False, target_bytes=1024, orphan_grace_s=0.0)
    assert not rec.blobs.has(orphan_sha)
    assert rec.blobs.has(snap_sha)
    assert rec.blobs.has(fetch_sha)


def test_verify_objects_reports_missing_and_corrupt_via_api_and_cli(env, monkeypatch, capsys):
    """刪除 2 個被鏈引用的物件、竄改 1 個物件 ⇒ verify_trace_objects 與 CLI 誠實報錯並回退出碼 1。"""
    _tmp, vh, ws = env
    rec = R.Recorder(ws)
    rec.baseline()
    actor = R.Actor("claude", "s1")
    rec.pre("t1", actor, "Write", {"file_path": "a.txt"})
    (ws / "a.txt").write_text("hello\n", encoding="utf-8")
    ev = rec.post("t1", actor, "Write", {"file_path": "a.txt"}, "tool-output-body")
    snap_sha = rec.blobs.put_bytes(b"snapshot content")
    rec.append("source_snapshot", {"path": "a.txt", "pages": {"http://x.test/p": snap_sha}, "errors": {}})
    fetch_sha = rec.blobs.put_bytes(b"fetch content")
    rec.append("source_fetch", {"url": "http://x.test/f", "sha256": fetch_sha})

    # 刪除 2 個引用物件（模擬舊版 GC 誤刪）
    rec.blobs.path(snap_sha).unlink()
    rec.blobs.path(ev["output_blob"]).unlink()

    # API 檢查
    rep = rec.verify_objects()
    assert rep["ok"] is False
    assert rep["missing_count"] == 2
    missing_shas = {m["sha256"] for m in rep["missing"]}
    assert missing_shas == {snap_sha, ev["output_blob"]}

    # CLI: `vacant trace verify --objects --json` 退出碼 1 並列出缺件
    monkeypatch.chdir(ws)
    rc = trace_cli.main(["trace", "verify", "--objects", "--json"])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert out["chain_ok"] is True
    assert out["objects"]["missing_count"] == 2

    # CLI: `vacant gc --verify-objects` 退出碼 1
    rc_gc = retention.main(["gc", "--state-dir", str(vh), "--verify-objects", "--dry-run"])
    assert rc_gc == 1
    gc_out = capsys.readouterr().out
    assert "缺失 2" in gc_out

    # 竄改一個還存在的物件位元組 ⇒ `--verify-hashes` 抓出 corrupt
    rec.blobs.path(fetch_sha).write_bytes(b"TAMPERED")
    rep_h = rec.verify_objects(verify_hashes=True)
    assert rep_h["ok"] is False
    assert rep_h["corrupt_count"] == 1
    assert rep_h["corrupt"][0]["sha256"] == fetch_sha
