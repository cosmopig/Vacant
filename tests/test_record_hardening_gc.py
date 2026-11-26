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


def test_referenced_objects_survive_budget_pressure_across_all_default_paths(env, monkeypatch, capsys):
    """預設 GC（compact_trace / gc_all / auto_gc / vacant gc --target-bytes / --keep-steps / --aggressive）：
    無論預算多緊或指定步數視窗，絕不刪除任何鏈引用物件（含 input/output/prompt/transcript/索引/索引內檔案），
    只回收未引用孤立物件；預算未達標時回報 budget_unmet=True、referenced_bytes_held 並印出明確說明。"""
    _tmp, vh, ws = env
    (ws / "app.py").write_text("v0 = 0\n", encoding="utf-8")
    (ws / "bg.txt").write_text("B" * 20_000, encoding="utf-8")
    rec = R.Recorder(ws)
    rec.baseline()
    # 把未改動的 bg.txt（被 baseline 索引引用）也放進物件庫，模擬索引引用檔案 blob
    bg_sha = rec.blobs.put_bytes((ws / "bg.txt").read_bytes())

    actor = R.Actor("claude", "s1")
    prompt_text = "keep this prompt " + ("P" * 20_000)
    prompt_sha = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
    rec.prompt(prompt_text, session="s1", source="user")

    step_refs: list[str] = []
    for i in range(6):
        body = f"val = {i}\npad = '{chr(65 + i) * 25_000}'\n"
        rec.pre(f"t{i}", actor, "Write", {"file_path": "app.py", "pad": "I" * 10_000, "i": i})
        (ws / "app.py").write_text(body, encoding="utf-8")
        ev = rec.post(f"t{i}", actor, "Write", {"file_path": "app.py", "pad": "I" * 10_000, "i": i},
                      "O" * 15_000)
        step_refs.extend([ev["input_blob"], ev["output_blob"], ev["post_index"]])
        step_refs.append(hashlib.sha256(body.encode("utf-8")).hexdigest())

    tr_sha = rec.blobs.put_bytes(b"T" * 15_000)
    rec.append("transcript", {"actor": actor.to_json(), "role": "session", "sha256": tr_sha})

    must_survive = {bg_sha, prompt_sha, tr_sha, *step_refs}
    for sha in must_survive:
        assert rec.blobs.has(sha)

    # 放入 2 個未引用孤立物件（推回舊 mtime）
    orphan_a = rec.blobs.put_bytes(b"X" * 30_000)
    orphan_b = rec.blobs.put_bytes(b"Y" * 30_000)
    for o in (orphan_a, orphan_b):
        os.utime(rec.blobs.path(o), (1700000000.0, 1700000000.0))

    # 1) compact_trace 極緊預算：只刪未引用孤兒，全部鏈引用物件存活，回報 budget_unmet=True
    rep1 = retention.compact_trace(vh, dry_run=False, target_bytes=1024, orphan_grace_s=0.0,
                                   active_window_s=0.0)
    assert not rec.blobs.has(orphan_a) and not rec.blobs.has(orphan_b)
    assert rep1["files_removed"] == 2
    assert rep1["budget_unmet"] is True
    assert rep1["target"]["budget_unmet"] is True
    assert rep1["target"]["target_reached"] is False
    assert rep1["referenced_bytes_held"] > 100_000
    assert "budget_unmet" in rep1.get("note", "")
    for sha in must_survive:
        assert rec.blobs.has(sha), f"referenced object {sha} must survive compact_trace budget pressure"

    # 2) VACANT_TRACE_BUDGET_BYTES + gc_all + auto_gc：同樣不刪任何引用物件並回報 budget_unmet=True
    monkeypatch.setenv("VACANT_TRACE_BUDGET_BYTES", "1024")
    rep_all = retention.gc_all(root=vh, work_root=_tmp / "work", dry_run=False, verify=True, verify_objects=True)
    assert rep_all["budget_unmet"] is True
    assert rep_all["referenced_bytes_held"] > 100_000
    assert rep_all["verify_ok"] is True
    assert rep_all["objects_ok"] is True
    assert rep_all["objects_verify"]["all_present"] is True

    rep_auto = retention.auto_gc(root=vh, work_root=_tmp / "work", force=True, target_bytes=1024)
    assert rep_auto["ok"] is True
    assert rep_auto["budget_unmet"] is True
    assert rep_auto["referenced_bytes_held"] > 100_000
    for sha in must_survive:
        assert rec.blobs.has(sha), f"referenced object {sha} must survive auto_gc budget pressure"

    # 3) CLI `vacant gc --target-bytes 1024 --keep-steps 1 --aggressive`（未帶 opt-in）：
    #    不刪任何鏈引用物件、印出 budget_unmet 與 --keep-steps 說明
    rc = retention.main(["gc", "--state-dir", str(vh), "--work-dir", str(_tmp / "work"),
                         "--target-bytes", "1024", "--keep-steps", "1", "--aggressive"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "budget_unmet" in out
    assert "--allow-breaking-chain-references" in out
    assert "--keep-steps" in out
    for sha in must_survive:
        assert rec.blobs.has(sha), f"referenced object {sha} must survive CLI gc without opt-in"

    # 4) CLI `--auto --allow-breaking-chain-references` 必須被拒（rc == 2）
    rc_bad = retention.main(["gc", "--auto", "--allow-breaking-chain-references", "--state-dir", str(vh)])
    assert rc_bad == 2
    assert "--auto" in capsys.readouterr().err


def test_explicit_opt_in_records_signed_eviction_event_and_verify_distinguishes_evicted_vs_missing(
    env, monkeypatch, capsys
):
    """明確 opt-in（--allow-breaking-chain-references）才可驅逐鏈引用物件，並於鏈上簽寫 objects_evicted；
    `vacant trace verify --objects` 精準區分「evicted by explicit GC」與未經說明的「missing」。"""
    from vacant_network.identity import PublicIdentity
    from vacant_network.logbook import Logbook, _signed_bytes

    _tmp, vh, ws = env
    (ws / "app.py").write_text("v0 = 0\n", encoding="utf-8")
    rec = R.Recorder(ws)
    rec.baseline()
    actor = R.Actor("claude", "s1")

    output_shas: list[str] = []
    file_shas: list[str] = []
    for i in range(5):
        body = f"step = {i}\npad = '{chr(65 + i) * 35_000}'\n"
        rec.pre(f"t{i}", actor, "Write", {"file_path": "app.py", "i": i})
        (ws / "app.py").write_text(body, encoding="utf-8")
        ev = rec.post(f"t{i}", actor, "Write", {"file_path": "app.py", "i": i}, "R" * 15_000)
        output_shas.append(ev["output_blob"])
        file_shas.append(hashlib.sha256(body.encode("utf-8")).hexdigest())

    snap_sha = rec.blobs.put_bytes(b"S" * 1024)
    rec.append("source_snapshot", {"path": "app.py", "pages": {"http://example.test/p": snap_sha}, "errors": {}})

    # 1) --dry-run 不刪檔、不寫 objects_evicted 事件
    events_before = len(rec.events())
    rc_dry = retention.main([
        "gc", "--state-dir", str(vh), "--work-dir", str(_tmp / "work"),
        "--target-bytes", "60000", "--allow-breaking-chain-references", "--dry-run", "--json",
    ])
    assert rc_dry == 0
    dry_rep = json.loads(capsys.readouterr().out)
    assert dry_rep["trace"]["evicted_referenced_count"] == 0
    assert len(dry_rep["trace"].get("would_evict_referenced") or []) >= 3
    assert len(rec.events()) == events_before

    # 2) 真跑 --allow-breaking-chain-references：驅逐舊物件、寫入已簽章 objects_evicted 事件、鏈驗章通過
    rc_real = retention.main([
        "gc", "--state-dir", str(vh), "--work-dir", str(_tmp / "work"),
        "--target-bytes", "60000", "--allow-breaking-chain-references",
        "--verify", "--verify-objects", "--json",
    ])
    assert rc_real == 0
    real_rep = json.loads(capsys.readouterr().out)
    assert real_rep["verify_ok"] is True
    assert real_rep["objects_ok"] is True
    evicted_list = real_rep["trace"]["evicted_referenced"]
    assert len(evicted_list) >= 3
    assert rec.blobs.has(snap_sha)  # 結構硬底仍保留

    # 確認鏈上有簽章的 objects_evicted 事件，且列出每一個被驅逐的 sha256，簽章可離線重驗
    ok_chain, why_chain = rec.verify()
    assert ok_chain, why_chain
    book = Logbook.load(rec.chain_path)
    ev_entries = [e for e in book.entries if e.type == "objects_evicted"]
    assert len(ev_entries) >= 1
    recorded_shas: set[str] = set()
    me = keys.load_or_create("verifier")
    who = PublicIdentity(vacant_id=me.vacant_id, pub=me.pub)
    for e in ev_entries:
        assert who.verify(
            _signed_bytes(e.stream_id, e.branch_id, e.seq, e.prev_hash, e.ts_ms, e.type, e.payload),
            bytes.fromhex(e.sig),
        )
        assert e.payload.get("allow_breaking_chain_references") is True
        recorded_shas.update(e.payload.get("evicted_shas") or [])
    assert set(evicted_list) <= recorded_shas

    # `vacant trace show` 顯示 objects_evicted
    monkeypatch.chdir(ws)
    assert trace_cli.main(["trace", "show"]) == 0
    show_out = capsys.readouterr().out
    assert "objects_evicted" in show_out

    # 3) `vacant trace verify --objects`：全數缺失都可歸因至明確 GC ⇒ rc==0，報「evicted by explicit GC」、0 missing
    rc_v1 = trace_cli.main(["trace", "verify", "--objects"])
    assert rc_v1 == 0
    v1_out = capsys.readouterr().out
    assert "OBJECTS PARTIAL" in v1_out
    assert "evicted by explicit GC" in v1_out
    assert "0 missing" in v1_out

    rc_v1j = trace_cli.main(["trace", "verify", "--objects", "--json"])
    assert rc_v1j == 0
    v1j = json.loads(capsys.readouterr().out)
    assert v1j["ok"] is True
    assert v1j["objects"]["all_present"] is False
    assert v1j["objects"]["missing_count"] == 0
    assert v1j["objects"]["evicted_count"] >= 3
    assert all(item["status"] == "evicted by explicit GC" for item in v1j["objects"]["evicted"])

    # 4) 再手動靜默刪除 1 個未被記錄驅逐的引用物件（snap_sha）⇒ verify 區分 missing vs evicted by explicit GC 且 rc==1
    rec.blobs.path(snap_sha).unlink()
    rc_v2 = trace_cli.main(["trace", "verify", "--objects"])
    assert rc_v2 == 1
    v2_out = capsys.readouterr().out
    assert "OBJECTS MISSING" in v2_out
    assert f"missing {snap_sha}" in v2_out
    assert "evicted by explicit GC" in v2_out

    rc_v2j = trace_cli.main(["trace", "verify", "--objects", "--json"])
    assert rc_v2j == 1
    v2j = json.loads(capsys.readouterr().out)
    assert v2j["ok"] is False
    assert v2j["objects"]["missing_count"] == 1
    assert v2j["objects"]["missing"][0]["sha256"] == snap_sha
    assert v2j["objects"]["evicted_count"] >= 3
    assert snap_sha not in {e["sha256"] for e in v2j["objects"]["evicted"]}

    # `vacant gc --verify-objects` 也回傳 rc==1 並同時顯示 missing 與 evicted by explicit GC
    rc_gcv = retention.main(["gc", "--state-dir", str(vh), "--work-dir", str(_tmp / "work"),
                             "--verify-objects", "--dry-run"])
    assert rc_gcv == 1
    gcv_out = capsys.readouterr().out
    assert "缺失 1" in gcv_out
    assert "evicted by explicit GC" in gcv_out


def test_explicit_opt_in_fail_closed_when_signing_eviction_fails(env, monkeypatch):
    """fail-closed：即使傳了 allow_breaking_chain_references=True，若無法在鏈上簽寫 objects_evicted
    （例如 MixedSignerRefused），絕不刪除任何該鏈引用的物件。"""
    _tmp, vh, ws = env
    (ws / "app.py").write_text("v0 = 0\n", encoding="utf-8")
    rec = R.Recorder(ws)
    rec.baseline()
    actor = R.Actor("claude", "s1")
    shas: list[str] = []
    for i in range(4):
        body = f"step = {i}\npad = '{chr(65 + i) * 35_000}'\n"
        rec.pre(f"t{i}", actor, "Write", {"file_path": "app.py", "i": i})
        (ws / "app.py").write_text(body, encoding="utf-8")
        ev = rec.post(f"t{i}", actor, "Write", {"file_path": "app.py", "i": i}, "ok")
        shas.append(hashlib.sha256(body.encode("utf-8")).hexdigest())

    def refuse_append(self, etype, payload):
        raise R.MixedSignerRefused("simulated key mismatch")

    monkeypatch.setattr(R.Recorder, "_append", refuse_append)
    rep = retention.compact_trace(vh, dry_run=False, target_bytes=20_000,
                                  allow_breaking_chain_references=True)
    assert rep["evicted_referenced_count"] == 0
    assert rep["budget_unmet"] is True
    assert rep.get("skipped_referenced")
    for sha in shas:
        assert rec.blobs.has(sha), "referenced blob must NOT be deleted when signing objects_evicted fails"
