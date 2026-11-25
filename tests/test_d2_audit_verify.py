"""Red tests for D2′ audit chain verification (Task 1) and external anchor (Task 2).

Uses a read-only copy of a real cell from pilot3c_qwen9b into tmp_path (never mutates pilot3c),
plus a small synthetic Ed25519-signed chain to test unrecorded_change before_index/after_index.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import shutil
import subprocess
import sys

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

REPO = pathlib.Path(__file__).resolve().parents[1]
PILOT3C = pathlib.Path("/home/user1/dev/ops/d2_runs/pilot3c_qwen9b")
MANIFEST = pathlib.Path("/home/user1/dev/ops/d2_materials/seed20261126_ffnz/manifest.json")


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


AUDIT_D2 = _load("audit_d2", "ops/d2/audit_d2.py")
ANCHOR_D2 = _load("anchor_d2", "ops/d2/anchor_d2.py")


def _copy_vh(tmp_path: pathlib.Path, set_id: str = "s51", arm: str = "c") -> pathlib.Path:
    src = PILOT3C / "cells" / set_id / arm / "final" / "vh"
    dst = tmp_path / "vh"
    shutil.copytree(src, dst)
    return dst


def _copy_mini_run(tmp_path: pathlib.Path, set_id: str = "s51", arms: tuple[str, ...] = ("c",)) -> pathlib.Path:
    """Copy RUN.json, access.jsonl (if any), c0, and chosen arms of one set into tmp_path/run."""
    dst = tmp_path / "run"
    dst.mkdir()
    for fname in ("RUN.json", "access.jsonl"):
        src_f = PILOT3C / fname
        if src_f.is_file():
            shutil.copy2(src_f, dst / fname)
    shutil.copytree(PILOT3C / "cells" / set_id / "c0", dst / "cells" / set_id / "c0")
    for arm in arms:
        shutil.copytree(PILOT3C / "cells" / set_id / arm, dst / "cells" / set_id / arm)
    return dst


def _chain_file(vh: pathlib.Path) -> pathlib.Path:
    projs = list((vh / "trace" / "projects").iterdir())
    assert len(projs) == 1
    return projs[0] / "chain.ndjson"


def _blob_path(vh: pathlib.Path, sha: str) -> pathlib.Path:
    return vh / "trace" / "objects" / sha[:2] / sha


def _resign_chain(vh: pathlib.Path, events: list[dict]) -> tuple[str, list[dict]]:
    """Generate a brand-new Ed25519 keypair, update intake/trust.json, and re-sign every entry."""
    priv = Ed25519PrivateKey.generate()
    pub_hex = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

    trust_path = vh / "intake" / "trust.json"
    trust = json.loads(trust_path.read_text(encoding="utf-8"))
    trust.setdefault("verifier", {})["local"] = pub_hex
    trust_path.write_text(json.dumps(trust, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    new_events: list[dict] = []
    prev = "0" * 64
    sid = "0" * 64
    for i, e in enumerate(events):
        ne = json.loads(json.dumps(e))
        if i == 0:
            ne["payload"]["signer"] = pub_hex
            ne["stream_id"] = "0" * 64
            ne["prev_hash"] = "0" * 64
        else:
            ne["stream_id"] = sid
            ne["prev_hash"] = prev
        raw = ANCHOR_D2.canon_entry_bytes(ne)
        h = hashlib.sha256(raw).hexdigest()
        ne["sig"] = priv.sign(raw).hex()
        if i == 0:
            sid = h
        prev = h
        new_events.append(ne)

    cf = _chain_file(vh)
    cf.write_text("\n".join(json.dumps(e, ensure_ascii=False, sort_keys=True) for e in new_events) + "\n",
                  encoding="utf-8")
    return pub_hex, new_events


# ── Task 1: Chain & Content-Addressed Object Verification ────────────────


@pytest.mark.skipif(not PILOT3C.is_dir(), reason="pilot3c_qwen9b fixture not present")
def test_untouched_real_chain_all_ok(tmp_path):
    vh = _copy_vh(tmp_path, "s51", "c")
    rec = AUDIT_D2.Record(vh)
    v = rec.verify
    assert v["hash_chain_ok"] is True
    assert v["signatures_ok"] is True
    assert v["signer_trusted"] is True
    assert v["blobs_checked"] > 0
    assert v["blobs_bad"] == 0
    assert v["index_files_checked"] > 0
    assert v["index_files_bad"] == 0
    assert rec.problems == []


@pytest.mark.skipif(not PILOT3C.is_dir(), reason="pilot3c_qwen9b fixture not present")
def test_tampered_prompt_text_blob_detected(tmp_path):
    """Task 1(a): replacing a prompt event's text_blob object increments blobs_bad."""
    vh = _copy_vh(tmp_path, "s51", "c")
    rec0 = AUDIT_D2.Record(vh)
    prompts = [e for e in rec0.events if e["type"] == "prompt" and (e.get("payload") or {}).get("text_blob")]
    assert prompts, "expected at least one prompt event with text_blob"
    sha = prompts[0]["payload"]["text_blob"]
    bp = _blob_path(vh, sha)
    assert bp.is_file()
    bp.write_bytes(b"TAMPERED PROMPT CONTENT - line 999: fake\n")

    rec = AUDIT_D2.Record(vh)
    assert rec.verify["hash_chain_ok"] is True
    assert rec.verify["signatures_ok"] is True
    assert rec.verify["blobs_bad"] > 0
    assert any("referenced blobs" in p for p in rec.problems)


@pytest.mark.skipif(not PILOT3C.is_dir(), reason="pilot3c_qwen9b fixture not present")
def test_tampered_indexed_report_md_detected(tmp_path):
    """Task 1(b): replacing a report.md object referenced by an index increments index_files_bad."""
    vh = _copy_vh(tmp_path, "s51", "c")
    rec0 = AUDIT_D2.Record(vh)
    # Find a report.md sha referenced by a step's post_index (not identical to an output_blob if possible)
    output_shas = {e["payload"].get("output_blob") for e in rec0.events if e["type"] == "step"}
    target_sha = None
    for e in reversed(rec0.events):
        if e["type"] != "step" or not e["payload"].get("post_index"):
            continue
        ix = json.loads(rec0.text(e["payload"]["post_index"]) or "{}")
        ent = ix.get("report.md")
        if ent and ent[0] not in output_shas:
            target_sha = ent[0]
            break
    assert target_sha is not None, "expected a written report.md object in post_index"
    bp = _blob_path(vh, target_sha)
    assert bp.is_file()
    bp.write_bytes(b"# Tampered report.md\n- forged claim: $999999\n")

    rec = AUDIT_D2.Record(vh)
    assert rec.verify["hash_chain_ok"] is True
    assert rec.verify["signatures_ok"] is True
    assert rec.verify["blobs_bad"] == 0
    assert rec.verify["index_files_bad"] == 1
    assert any("indexed file objects" in p for p in rec.problems)


@pytest.mark.skipif(not PILOT3C.is_dir(), reason="pilot3c_qwen9b fixture not present")
def test_deleted_written_indexed_file_detected(tmp_path):
    """Task 1(b): deleting a written report.md object referenced by post_index increments index_files_bad."""
    vh = _copy_vh(tmp_path, "s51", "c")
    rec0 = AUDIT_D2.Record(vh)
    written = [wr["after"] for e in rec0.events if e["type"] == "step"
               for wr in (e["payload"].get("writes") or []) if wr.get("after")]
    assert written
    bp = _blob_path(vh, written[-1])
    assert bp.is_file()
    bp.unlink()

    rec = AUDIT_D2.Record(vh)
    assert rec.verify["index_files_bad"] >= 1
    assert any("indexed file objects" in p for p in rec.problems)


@pytest.mark.skipif(not PILOT3C.is_dir(), reason="pilot3c_qwen9b fixture not present")
def test_tampered_source_check_url_breaks_signature_and_hash(tmp_path):
    """Task 1(c): changing one url inside a source_check payload breaks signature (and chain hash)."""
    vh = _copy_vh(tmp_path, "s51", "c")
    cf = _chain_file(vh)
    events = [json.loads(line) for line in cf.read_text(encoding="utf-8").splitlines() if line.strip()]

    edited = False
    for e in events:
        if e["type"] == "source_check":
            for cl in e["payload"].get("claims") or []:
                src = cl.get("source")
                if src and src.get("url"):
                    src["url"] = src["url"] + "?tampered=1"
                    edited = True
                    break
        if edited:
            break
    assert edited, "expected a source_check event with a source url"

    cf.write_text("\n".join(json.dumps(e, ensure_ascii=False, sort_keys=True) for e in events) + "\n",
                  encoding="utf-8")

    rec = AUDIT_D2.Record(vh)
    assert rec.verify["signatures_ok"] is False
    assert rec.verify["hash_chain_ok"] is False
    assert any("bad signature" in p for p in rec.problems)


def test_unrecorded_change_before_and_after_index_verified(tmp_path):
    """Task 1(b): unrecorded_change before_index/after_index file objects are parsed and verified (deduped)."""
    vh = tmp_path / "vh"
    priv = Ed25519PrivateKey.generate()
    pub_hex = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    (vh / "intake").mkdir(parents=True)
    (vh / "intake" / "trust.json").write_text(json.dumps({"verifier": {"local": pub_hex}}), encoding="utf-8")

    def put_obj(data: bytes) -> str:
        s = hashlib.sha256(data).hexdigest()
        p = _blob_path(vh, s)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return s

    f_before = put_obj(b"before content\n")
    f_after = put_obj(b"after content\n")
    f_shared = put_obj(b"shared content\n")
    idx_before = put_obj(json.dumps({
        "report.md": [f_before, 15, 1, False],
        "notes.txt": [f_shared, 15, 1, False],
    }).encode("utf-8"))
    idx_after = put_obj(json.dumps({
        "report.md": [f_after, 14, 2, False],
        "notes.txt": [f_shared, 15, 1, False],
    }).encode("utf-8"))

    raw_events = [
        {"branch_id": "main", "seq": 1, "ts_ms": 1000, "type": "trace_genesis",
         "payload": {"schema": "vacant-trace/1", "signer": pub_hex, "workspace": "/tmp/ws"}},
        {"branch_id": "main", "seq": 2, "ts_ms": 2000, "type": "unrecorded_change",
         "payload": {
             "before_index": idx_before,
             "after_index": idx_after,
             "changes": [{"path": "report.md", "before": f_before, "after": f_after, "kind": "modified"}],
         }},
    ]
    events: list[dict] = []
    prev, sid = "0" * 64, "0" * 64
    for i, e in enumerate(raw_events):
        e["stream_id"] = "0" * 64 if i == 0 else sid
        e["prev_hash"] = "0" * 64 if i == 0 else prev
        raw = ANCHOR_D2.canon_entry_bytes(e)
        h = hashlib.sha256(raw).hexdigest()
        e["sig"] = priv.sign(raw).hex()
        if i == 0:
            sid = h
        prev = h
        events.append(e)

    pdir = vh / "trace" / "projects" / "proj1"
    pdir.mkdir(parents=True)
    (pdir / "chain.ndjson").write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")

    # Untouched: 3 unique files (f_before, f_after, f_shared) checked once each (deduped), 0 bad
    rec_ok = AUDIT_D2.Record(vh)
    assert rec_ok.verify["hash_chain_ok"] is True
    assert rec_ok.verify["signatures_ok"] is True
    assert rec_ok.verify["index_files_checked"] == 3
    assert rec_ok.verify["index_files_bad"] == 0
    assert rec_ok.problems == []

    # Tamper f_after -> caught
    _blob_path(vh, f_after).write_bytes(b"TAMPERED AFTER\n")
    rec_bad = AUDIT_D2.Record(vh)
    assert rec_bad.verify["index_files_checked"] == 3
    assert rec_bad.verify["index_files_bad"] == 1
    assert rec_bad.verify["blobs_bad"] == 0
    assert any("indexed file objects" in p for p in rec_bad.problems)


# ── Task 2: External Anchor (Truncation, Re-sign, audit_d2 --anchor) ─────


@pytest.mark.skipif(not PILOT3C.is_dir(), reason="pilot3c_qwen9b fixture not present")
def test_truncation_invisible_to_chain_but_caught_by_anchor(tmp_path):
    """Truncating the last N lines passes Record verification alone, but is caught by anchor_d2 and audit_d2 --anchor."""
    run_root = _copy_mini_run(tmp_path, "s51", ("c",))
    anchor_path = tmp_path / "anchor.json"

    # 1. Write anchor via CLI
    r_write = subprocess.run(
        [sys.executable, str(REPO / "ops" / "d2" / "anchor_d2.py"),
         "write", "--root", str(run_root), "--out", str(anchor_path)],
        capture_output=True, text=True, check=True,
    )
    w_info = json.loads(r_write.stdout)
    assert w_info["ok"] is True
    assert w_info["chains"] == 2  # s51/c0 and s51/c

    anchor_doc = json.loads(anchor_path.read_text(encoding="utf-8"))
    assert anchor_doc["run_json_sha256"] == hashlib.sha256((run_root / "RUN.json").read_bytes()).hexdigest()
    assert anchor_doc["timestamp"]
    assert set(anchor_doc["chains"]) == {"s51/c0", "s51/c"}

    # 2. Untouched check passes (both anchor_d2 check and audit_d2 --anchor)
    r_ok = subprocess.run(
        [sys.executable, str(REPO / "ops" / "d2" / "anchor_d2.py"),
         "check", "--root", str(run_root), "--anchor", str(anchor_path)],
        capture_output=True, text=True,
    )
    assert r_ok.returncode == 0
    assert json.loads(r_ok.stdout)["ok"] is True

    r_audit_ok = subprocess.run(
        [sys.executable, str(REPO / "ops" / "d2" / "audit_d2.py"),
         "--root", str(run_root), "--manifest", str(MANIFEST), "--anchor", str(anchor_path)],
        capture_output=True, text=True,
    )
    assert r_audit_ok.returncode == 0
    audit_ok_out = json.loads(r_audit_ok.stdout)
    assert audit_ok_out["anchor_check"]["ok"] is True
    assert audit_ok_out["record_problems"] == []

    # 3. Truncate the last 3 lines of s51/c chain.ndjson
    vh_c = run_root / "cells" / "s51" / "c" / "final" / "vh"
    cf = _chain_file(vh_c)
    lines = [l for l in cf.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) > 5
    cf.write_text("\n".join(lines[:-3]) + "\n", encoding="utf-8")

    # Chain verification alone CANNOT detect tail truncation!
    rec_trunc = AUDIT_D2.Record(vh_c)
    assert rec_trunc.verify["hash_chain_ok"] is True
    assert rec_trunc.verify["signatures_ok"] is True
    assert rec_trunc.verify["signer_trusted"] is True
    assert rec_trunc.verify["blobs_bad"] == 0
    assert rec_trunc.verify["index_files_bad"] == 0
    assert rec_trunc.problems == []

    # External anchor DOES catch it!
    r_bad = subprocess.run(
        [sys.executable, str(REPO / "ops" / "d2" / "anchor_d2.py"),
         "check", "--root", str(run_root), "--anchor", str(anchor_path)],
        capture_output=True, text=True,
    )
    assert r_bad.returncode != 0
    chk = json.loads(r_bad.stdout)
    assert chk["ok"] is False
    assert chk["chains_bad"] == 1
    assert any(m["chain"] == "s51/c" and any("head_moved_backwards" in r for r in m["reasons"])
               for m in chk["mismatches"])

    # audit_d2.py --anchor surfaces anchor_check failure
    out_full = tmp_path / "audit_trunc.json"
    r_audit_bad = subprocess.run(
        [sys.executable, str(REPO / "ops" / "d2" / "audit_d2.py"),
         "--root", str(run_root), "--manifest", str(MANIFEST),
         "--anchor", str(anchor_path), "--out", str(out_full)],
        capture_output=True, text=True,
    )
    assert r_audit_bad.returncode != 0
    audit_bad_out = json.loads(r_audit_bad.stdout)
    assert audit_bad_out["anchor_check"]["ok"] is False
    assert audit_bad_out["anchor_check"]["chains_bad"] == 1
    assert any("anchor:" in p and "s51/c" in p for p in audit_bad_out["record_problems"])
    full_doc = json.loads(out_full.read_text(encoding="utf-8"))
    assert full_doc["anchor_check"]["ok"] is False


@pytest.mark.skipif(not PILOT3C.is_dir(), reason="pilot3c_qwen9b fixture not present")
def test_resign_with_new_key_and_trust_caught_by_anchor(tmp_path):
    """Re-signing an entire chain with a new key + updated trust.json fools Record alone, but is caught by anchor."""
    run_root = _copy_mini_run(tmp_path, "s51", ("c",))
    anchor_path = tmp_path / "anchor.json"
    anchor_doc = ANCHOR_D2.build_anchor(run_root)
    anchor_path.write_text(json.dumps(anchor_doc, indent=1), encoding="utf-8")

    # Attacker edits a source_check url AND re-signs the whole chain with a freshly generated key + new trust.json
    vh_c = run_root / "cells" / "s51" / "c" / "final" / "vh"
    cf = _chain_file(vh_c)
    events = [json.loads(l) for l in cf.read_text(encoding="utf-8").splitlines() if l.strip()]
    for e in events:
        if e["type"] == "source_check":
            for cl in e["payload"].get("claims") or []:
                if cl.get("source") and cl["source"].get("url"):
                    cl["source"]["url"] = "http://evil.example/forged.html"
                    break
            break
    _resign_chain(vh_c, events)

    # Record alone sees a self-consistent chain signed by a trusted key in the attacker's trust.json!
    rec = AUDIT_D2.Record(vh_c)
    assert rec.verify["hash_chain_ok"] is True
    assert rec.verify["signatures_ok"] is True
    assert rec.verify["signer_trusted"] is True
    assert rec.verify["blobs_bad"] == 0
    assert rec.verify["index_files_bad"] == 0
    assert rec.problems == []

    # External anchor catches last_hash, chain_sha256, AND trust_sha256 mismatches!
    chk = ANCHOR_D2.check_anchor(run_root, anchor_doc)
    assert chk["ok"] is False
    assert chk["chains_bad"] == 1
    m = next(x for x in chk["mismatches"] if x["chain"] == "s51/c")
    assert "last_hash_mismatch" in m["reasons"]
    assert "chain_sha256_mismatch" in m["reasons"]
    assert "trust_sha256_mismatch" in m["reasons"]

    # audit_d2.py --anchor also reports anchor_check failure
    r_audit = subprocess.run(
        [sys.executable, str(REPO / "ops" / "d2" / "audit_d2.py"),
         "--root", str(run_root), "--manifest", str(MANIFEST), "--anchor", str(anchor_path)],
        capture_output=True, text=True,
    )
    assert r_audit.returncode != 0
    out = json.loads(r_audit.stdout)
    assert out["anchor_check"]["ok"] is False
    assert any("trust_sha256_mismatch" in p for p in out["anchor_check"]["problems"])


@pytest.mark.skipif(not PILOT3C.is_dir(), reason="pilot3c_qwen9b fixture not present")
def test_anchor_catches_run_json_tamper(tmp_path):
    run_root = _copy_mini_run(tmp_path, "s51", ("c",))
    anchor_doc = ANCHOR_D2.build_anchor(run_root)
    assert ANCHOR_D2.check_anchor(run_root, anchor_doc)["ok"] is True

    (run_root / "RUN.json").write_text('{"tampered": true}\n', encoding="utf-8")
    chk = ANCHOR_D2.check_anchor(run_root, anchor_doc)
    assert chk["ok"] is False
    assert chk["run_json_ok"] is False
    assert any(m["chain"] == "RUN.json" for m in chk["mismatches"])
