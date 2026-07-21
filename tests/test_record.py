"""record（P0 紀錄基建）測試：pack 佈局 + check 判準 + SHA256SUMS 竄改偵測 + CLI。

覆蓋 docs/RECORD_SPEC.md：完整包 pack→check PASS；缺必要項/篡改/驗證輸出含 FAIL
時 check 逐條點名；空 run 目錄仍產出合法骨架；CLI exit code。都用 tmp_path，
絕不碰真實 ~/.vacant-mcp。
"""

from __future__ import annotations

import json
from pathlib import Path

from vacant import cli, crypto
from vacant.body import VacantBody
from vacant.canonical import canonical_bytes
from vacant.identity import Identity
from vacant.record import _write_sha256sums, check, pack


# --- 夾具 --------------------------------------------------------------------
def _make_resident(run_dir: Path, name: str = "good_1", *, tamper: bool = False) -> None:
    """在 run_dir/residents/<name>/trust/ 建一條真簽章 logbook。tamper→毀最後一筆簽章。"""
    body = VacantBody.create(name, run_dir / "residents", niches=["code"])
    body.log("DELIVER", {"task_id": "t1", "self_check": True})
    body.log("DELIVER", {"task_id": "t2", "self_check": False})
    body.persist()
    if tamper:
        lb = run_dir / "residents" / name / "trust" / "logbook.ndjson"
        lines = lb.read_text(encoding="utf-8").splitlines()
        d = json.loads(lines[-1])
        sig = d["sig"]
        d["sig"] = ("0" if sig[0] != "0" else "f") + sig[1:]  # 翻一個 hex 位元→驗不過
        lines[-1] = json.dumps(d, ensure_ascii=False)
        lb.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _make_card(task_id: str = "t1", *, valid: bool = True) -> dict:
    """自簽一張最小信任狀；valid=False→簽後改欄位使 host_sig 驗不過。"""
    ident = Identity.generate()
    card: dict = {
        "task_id": task_id, "trust_on": True,
        "deliverer": {"name": "good_1", "credit": {"score": 1.0, "n_obs": 5, "flags": []}},
        "signed_by": "deliverer",
        "signer_pub_hex": crypto.pub_to_hex(ident.pub),
    }
    card["host_sig"] = ident.sign(canonical_bytes(card)).hex()
    if not valid:
        card["task_id"] = "TAMPERED"  # 簽章不覆蓋新值→驗不過
    return card


def _make_full_run(run_dir: Path, *, tamper_chain: bool = False, card_valid: bool = True,
                   with_card: bool = True) -> None:
    """建一個內容齊全的 run（ledger/wire/model_io/居民/信任狀），尚未 pack。"""
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "ledger_events.jsonl").write_text(
        '{"ts_ms":1,"type":"ROUTE","to":"good_1"}\n'
        '{"ts_ms":2,"type":"DELIVERED","passed":true}\n', encoding="utf-8")
    (run_dir / "wire.jsonl").write_text('{"dir":"in","msg":{}}\n', encoding="utf-8")
    (run_dir / "model_io.jsonl").write_text('{"prompt":"p","output":"o"}\n', encoding="utf-8")
    _make_resident(run_dir, tamper=tamper_chain)
    if with_card:
        cdir = run_dir / "trust_cards"
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / "t1.json").write_text(
            json.dumps(_make_card("t1", valid=card_valid), ensure_ascii=False),
            encoding="utf-8")


_EXTRA = {"model_id": "test-model", "endpoint": "in-process", "no_think": True,
          "seeds": [1, 2, 3], "trust_arm": "on"}


# --- 測試 --------------------------------------------------------------------
def test_pack_then_check_pass(tmp_path):
    run = tmp_path / "runs" / "x1" / "r0"
    _make_full_run(run)
    manifest = pack(run, dict(_EXTRA))
    # manifest 必要欄位齊
    for f in ("repo_commit", "pip_freeze", "os", "python", "model_id", "endpoint",
              "no_think", "seeds", "machine", "utc_start", "utc_end", "trust_arm", "scripts"):
        assert f in manifest
    assert manifest["model_id"] == "test-model"
    assert isinstance(manifest["pip_freeze"], list)
    # 佈局：驗證輸出與 SHA256SUMS 都在
    assert (run / "chain_verify.txt").read_text(encoding="utf-8").count("PASS") >= 1
    assert (run / "card_verify.txt").exists()
    assert (run / "SHA256SUMS").exists()
    assert (run / "anomalies.md").exists()
    ok, problems = check(run)
    assert ok, problems
    assert problems == []


def test_missing_manifest_named(tmp_path):
    run = tmp_path / "r"
    _make_full_run(run)
    pack(run, dict(_EXTRA))
    (run / "manifest.json").unlink()
    ok, problems = check(run)
    assert not ok
    assert any("manifest.json" in p for p in problems)


def test_tamper_file_detected_by_sums(tmp_path):
    run = tmp_path / "r"
    _make_full_run(run)
    pack(run, dict(_EXTRA))
    # 篡改一個受 SHA256SUMS 涵蓋的檔
    (run / "ledger_events.jsonl").write_text(
        '{"ts_ms":9,"type":"FORGED"}\n', encoding="utf-8")
    ok, problems = check(run)
    assert not ok
    assert any("SHA256SUMS 不符" in p and "ledger_events.jsonl" in p for p in problems)


def test_chain_verify_fail_flagged(tmp_path):
    run = tmp_path / "r"
    _make_full_run(run, tamper_chain=True)
    pack(run, dict(_EXTRA))
    assert "FAIL" in (run / "chain_verify.txt").read_text(encoding="utf-8")
    ok, problems = check(run)
    assert not ok
    assert any("chain_verify.txt" in p and "FAIL" in p for p in problems)


def test_card_verify_fail_flagged(tmp_path):
    run = tmp_path / "r"
    _make_full_run(run, card_valid=False)
    pack(run, dict(_EXTRA))
    assert "FAIL" in (run / "card_verify.txt").read_text(encoding="utf-8")
    ok, problems = check(run)
    assert not ok
    assert any("card_verify.txt" in p and "FAIL" in p for p in problems)


def test_empty_run_dir_pack_skeleton(tmp_path):
    run = tmp_path / "empty"
    manifest = pack(run)  # 完全空目錄
    # 合法骨架：pack 負責的檔都在
    assert (run / "manifest.json").exists()
    assert (run / "SHA256SUMS").exists()
    assert (run / "anomalies.md").exists()
    cv = (run / "chain_verify.txt").read_text(encoding="utf-8")
    assert "SKIPPED" in cv  # 無居民鏈→SKIPPED＋理由
    # 缺項如實記入 manifest["missing"]（含可缺項與未提供的 run 欄位）
    miss = manifest["missing"]
    assert "wire.jsonl" in miss and "model_io.jsonl" in miss
    assert "model_id" in miss and "trust_arm" in miss
    # 但 ledger 這個必要項無法由 pack 生成→check 仍會點名（空骨架非通過）
    ok, problems = check(run)
    assert not ok
    assert any("ledger_events.jsonl" in p for p in problems)


def test_optional_missing_without_reason_flagged(tmp_path):
    run = tmp_path / "r"
    _make_full_run(run)
    pack(run, dict(_EXTRA))
    # 刪掉 wire.jsonl 並抹掉它在 manifest.missing 的理由，再重算 SHA256SUMS
    (run / "wire.jsonl").unlink()
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    manifest["missing"].pop("wire.jsonl", None)
    (run / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_sha256sums(run)  # 使雜湊自洽，隔離出「缺席無理由」這一個問題
    ok, problems = check(run)
    assert not ok
    assert any("wire.jsonl" in p and "理由" in p for p in problems)


def test_card_present_without_card_verify_flagged(tmp_path):
    run = tmp_path / "r"
    _make_full_run(run)
    pack(run, dict(_EXTRA))
    (run / "card_verify.txt").unlink()
    _write_sha256sums(run)  # 保持雜湊自洽，凸顯「有卡缺 card_verify」
    ok, problems = check(run)
    assert not ok
    assert any("card_verify.txt" in p for p in problems)


def test_cli_pack_and_check_exit_codes(tmp_path):
    run = tmp_path / "r"
    _make_full_run(run)
    assert cli.main(["record", "pack", str(run)]) == 0
    # 好包→check exit 0
    assert cli.main(["record", "check", str(run)]) == 0
    # 篡改後→check exit 非 0
    (run / "ledger_events.jsonl").write_text("forged\n", encoding="utf-8")
    assert cli.main(["record", "check", str(run)]) == 1


# --- 私鑰排除（RECORD_SPEC §7；T5）-------------------------------------------
def test_pack_excludes_private_key(tmp_path):
    """pack：identity.key 不進 SHA256SUMS、路徑進 manifest 聲明；check 仍 PASS。"""
    run = tmp_path / "runs" / "x1" / "r_key"
    _make_full_run(run)
    assert (run / "residents" / "good_1" / "trust" / "identity.key").exists()
    manifest = pack(run, dict(_EXTRA))
    sums = (run / "SHA256SUMS").read_text(encoding="utf-8")
    assert "identity.key" not in sums                      # 私鑰不入雜湊清單
    declared = manifest["excluded_private_keys"]
    assert declared == ["residents/good_1/trust/identity.key"]
    ok, problems = check(run)
    assert ok, problems


def test_private_key_in_sums_flagged(tmp_path):
    """SHA256SUMS 被人加入私鑰行 → check 點名私鑰。"""
    run = tmp_path / "runs" / "x1" / "r_key2"
    _make_full_run(run)
    pack(run, dict(_EXTRA))
    with (run / "SHA256SUMS").open("a", encoding="utf-8") as f:
        f.write("deadbeef  residents/good_1/trust/identity.key\n")
    ok, problems = check(run)
    assert not ok
    assert any("私鑰" in p and "identity.key" in p for p in problems)


def test_undeclared_private_key_flagged(tmp_path):
    """私鑰存在但 manifest 未聲明排除（如舊版 pack 產物）→ check 點名。"""
    run = tmp_path / "runs" / "x1" / "r_key3"
    _make_full_run(run)
    pack(run, dict(_EXTRA))
    mpath = run / "manifest.json"
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    manifest["excluded_private_keys"] = []                 # 模擬未聲明
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    ok, problems = check(run)
    assert not ok
    assert any("excluded_private_keys" in p for p in problems)


def test_cli_check_missing_dir_exit_nonzero(tmp_path):
    assert cli.main(["record", "check", str(tmp_path / "nope")]) == 1
