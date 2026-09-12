"""round666：收據鏈落盤之後，第三方**真的**驗得起來嗎。

這組測試存在的理由：`arm_conform` 從第一天就在簽鏈，但 `gain_run.py` 從來沒把
entries 或公鑰寫出去，所以 R440R 的 P-C4（「該臂的鏈 verify_chain 為真」）在
`runs/g_r444_conform_mbpp` 上是**不可結算**而不是「為假」。
（判準與量測：`CRITERION_20260903_R666_RECEIPT_CHAIN_UNVERIFIABLE.md`）

乾淨路徑通過**不算數**——會 PASS 的瞎尺真的存在。所以每一條乾淨斷言旁邊都有一條
竄改斷言：改了 payload／改了 sig／換了公鑰，`verify_chain` 都必須回 False。
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ops.gain.gain_run import save_receipts  # noqa: E402
from vacant.identity import Identity, PublicIdentity  # noqa: E402
from vacant.logbook import Logbook  # noqa: E402


def _st_with_chain(n=3):
    ident = Identity.generate()
    book = Logbook()
    for i in range(n):
        book.append("conform_attempt", {"task_id": f"t{i}", "attempt": 1}, ident,
                    ts_ms=1_700_000_000_000 + i)
    return {"CONFORM": {"book": book, "ident": ident},
            "OFF": {"book": Logbook(), "ident": Identity.generate()}}, ident


def _reload(tmp: pathlib.Path):
    meta = json.loads((tmp / "receipts_CONFORM.pub.json").read_text())
    who = PublicIdentity.from_hex(meta["vacant_id"], meta["pub_hex"])
    return Logbook.load(tmp / "receipts_CONFORM.ndjson"), who


def test_saves_chain_and_pubkey_and_verifies(tmp_path):
    st, _ = _st_with_chain()
    written = save_receipts(tmp_path, st)
    assert set(written) == {"receipts_CONFORM.ndjson", "receipts_CONFORM.pub.json"}
    # 空鏈的臂不寫檔（OFF 沒有收據這回事）
    assert not (tmp_path / "receipts_OFF.ndjson").exists()
    book, who = _reload(tmp_path)
    assert len(book) == 3
    assert book.verify_chain(who) is True


def test_tampered_payload_fails_verification(tmp_path):
    st, _ = _st_with_chain()
    save_receipts(tmp_path, st)
    p = tmp_path / "receipts_CONFORM.ndjson"
    lines = [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
    lines[1]["payload"]["task_id"] = "TAMPERED"
    p.write_text("".join(json.dumps(x, sort_keys=True) + "\n" for x in lines))
    book, who = _reload(tmp_path)
    assert book.verify_chain(who) is False


def test_dropped_entry_fails_verification(tmp_path):
    """刪掉中間一筆——seq 斷掉、prev_hash 串不上。"""
    st, _ = _st_with_chain()
    save_receipts(tmp_path, st)
    p = tmp_path / "receipts_CONFORM.ndjson"
    lines = [x for x in p.read_text().splitlines() if x.strip()]
    p.write_text(lines[0] + "\n" + lines[2] + "\n")
    book, who = _reload(tmp_path)
    assert book.verify_chain(who) is False


def test_wrong_pubkey_fails_verification(tmp_path):
    """公鑰換成別人的 ⇒ 簽章驗不過。落盤的公鑰若被掉包，這裡要叫。"""
    st, _ = _st_with_chain()
    save_receipts(tmp_path, st)
    book = Logbook.load(tmp_path / "receipts_CONFORM.ndjson")
    other = Identity.generate()
    from vacant.crypto import pub_to_hex
    assert book.verify_chain(
        PublicIdentity.from_hex(other.vacant_id, pub_to_hex(other.pub))) is False


# ── round460r-3／round529-2：稽核端的逐筆驗證器（`verify_run_receipts.py`）──
# 上面那幾條測的是 `Logbook.verify_chain` 這個 bool；稽核要的是**壞在哪一筆**。
# 驗證器自己帶 5 條牙齒（--selftest），這裡把它跑起來並釘住它的介面。


def test_verify_run_receipts_selftest_passes():
    import subprocess
    import sys
    r = subprocess.run(
        [sys.executable, "ops/gain/replay/verify_run_receipts.py", "--selftest"],
        cwd=pathlib.Path(__file__).resolve().parents[1],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS" in r.stdout


def test_verify_run_receipts_names_the_failing_entry(tmp_path):
    """壞鏈不准只回 False——要指得出 seq、type 與原因。"""
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    from ops.gain.replay.verify_run_receipts import verify_arm
    from vacant.crypto import pub_to_hex

    ident = Identity.generate()
    book = Logbook()
    for i in range(2):
        book.append("harness_attempt", {"task_id": f"t{i}"}, ident,
                    ts_ms=1_700_000_000_000 + i)
    for i in range(2):
        book.append("harness_verdict", {"task_id": f"t{i}"}, ident,
                    ts_ms=1_700_000_000_100 + i)
    book.save(tmp_path / "receipts_HMIX.ndjson")
    (tmp_path / "receipts_HMIX.pub.json").write_text(json.dumps(
        {"vacant_id": ident.vacant_id, "pub_hex": pub_to_hex(ident.pub)}))
    rows = [{"arm": "HMIX", "task_id": "t0"}, {"arm": "HMIX", "task_id": "t1"}]
    ok = verify_arm(tmp_path, "HMIX", rows)
    assert ok["verdict"] == "OK" and ok["failures"] == []
    assert ok["verdict_n"] == ok["rows_n"] == 2
    assert ok["chain_ok"] is ok["logbook_verify_chain"] is True

    lines = (tmp_path / "receipts_HMIX.ndjson").read_text().splitlines()
    e = json.loads(lines[2])
    e["payload"]["task_id"] = "TAMPERED"
    lines[2] = json.dumps(e, sort_keys=True, separators=(",", ":"))
    (tmp_path / "receipts_HMIX.ndjson").write_text("\n".join(lines) + "\n")
    bad = verify_arm(tmp_path, "HMIX", rows)
    assert bad["verdict"] == "BROKEN"
    sig = [f for f in bad["failures"] if f["reason"] == "bad_signature"]
    assert sig and sig[0]["seq"] == 3, bad["failures"]
    # 竄改之後 verdict 的 task_id 集合也對不上 rows ⇒ 第二條紅線也要亮
    assert any(f["reason"] == "verdict_task_ids_ne_rows" for f in bad["failures"])
