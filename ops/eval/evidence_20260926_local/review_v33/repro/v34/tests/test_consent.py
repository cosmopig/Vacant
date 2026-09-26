"""`vacant_network/consent.py` 的驗收——同意／撤回／刪除證明。

這組測試存在的理由：刪除證明是**展覽對觀眾的承諾的機制面**。一把會 PASS 的
瞎尺在這裡的代價不是實驗作廢，是對著一個真人說了一句做不到的話。所以每一條
乾淨斷言旁邊都有一條反向斷言（防呆真的會咬人），而不是只證明 happy path。

四條誠實邊界各有一條對應的可執行測試：
  1. 鏈只記「我們刪了」            → `test_erasure_records_hashes_not_content`
  2. 撤回上鏈 ≠ 撤回被執行         → `test_withdrawn_without_erase_is_visible`
  3. commitment 的 hiding 全靠 nonce → `test_commitment_without_nonce_is_refused`
  4. 刪除必須連 nonce 一起刪        → `test_erase_without_the_nonce_is_refused`
"""
import hashlib
import pathlib
import secrets
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from vacant_network import consent  # noqa: E402
from vacant_network.canonical import canonical_bytes  # noqa: E402
from vacant_network.identity import Identity, PublicIdentity  # noqa: E402
from vacant_network.logbook import Logbook  # noqa: E402

PERSONA = {
    "domains": ["寫程式", "翻譯"],
    "topics": ["咖啡"],
    "style": ["話很短"],
    "needs": ["要找出哪裡錯了"],
}


@pytest.fixture()
def ident():
    return Identity.generate()


@pytest.fixture()
def who(ident):
    return PublicIdentity(vacant_id=ident.vacant_id, pub=ident.pub)


def _full_cycle(book, ident, *, nonce=None, erase=True):
    nonce = nonce or secrets.token_hex(32)
    commit = consent.persona_commitment(PERSONA, nonce)
    g = consent.grant(book, ident, subject_ref="SYN-A", commitment=commit,
                      fields=list(PERSONA), scope="展覽期間生成一位居民",
                      ts_ms=1000, nonce_ref="nonce_A.bin")
    w = consent.withdraw(book, ident, subject_ref="SYN-A", grant_hash=g.hash(),
                         ts_ms=2000)
    e = None
    if erase:
        blob = canonical_bytes(PERSONA)
        e = consent.erase(
            book, ident, subject_ref="SYN-A", withdraw_hash=w.hash(),
            nonce_ref="nonce_A.bin", ts_ms=3000,
            erased=[
                {"ref": "nonce_A.bin",
                 "sha256": hashlib.sha256(nonce.encode("ascii")).hexdigest(),
                 "bytes_n": len(nonce)},
                {"ref": "persona_A.json",
                 "sha256": hashlib.sha256(blob).hexdigest(), "bytes_n": len(blob)},
            ])
    return g, w, e, nonce


# --- 乾淨路徑 ---------------------------------------------------------------

def test_full_cycle_verifies_and_audits(ident, who):
    book = Logbook()
    _full_cycle(book, ident)
    assert book.verify_chain(who)
    a = consent.audit(book, who)
    assert a["chain_ok"] and a["problems"] == []
    st = a["subjects"]["SYN-A"]
    assert st.state == "erased" and not st.unfulfilled
    assert set(st.erased_refs) == {"nonce_A.bin", "persona_A.json"}


def test_erasure_records_hashes_not_content(ident, who):
    """誠實邊界 1：鏈上只有被刪物的 sha256 與長度，沒有內容。"""
    book = Logbook()
    _g, _w, e, nonce = _full_cycle(book, ident)
    blob = canonical_bytes(e.payload).decode("utf-8")
    for v in PERSONA["domains"] + PERSONA["topics"]:
        assert v not in blob
    assert nonce not in blob
    for item in e.payload["erased"]:
        assert set(item) == {"ref", "sha256", "bytes_n"}


def test_withdrawn_without_erase_is_visible(ident, who):
    """誠實邊界 2：撤回了但沒刪，稽核看得見——這是鏈存在的唯一理由。"""
    book = Logbook()
    _full_cycle(book, ident, erase=False)
    st = consent.audit(book, who)["subjects"]["SYN-A"]
    assert st.state == "withdrawn"
    assert st.unfulfilled is True


# --- 防呆真的會咬人 ----------------------------------------------------------

def test_commitment_without_nonce_is_refused():
    """誠實邊界 3：nonce 太短就擋。hiding 全靠它，不是靠雜湊。"""
    with pytest.raises(ValueError):
        consent.persona_commitment(PERSONA, "short")


def test_erase_without_the_nonce_is_refused(ident):
    """誠實邊界 4：只刪原文不刪 nonce ＝ 沒刪，因為 commitment 窮舉得回來。"""
    book = Logbook()
    nonce = secrets.token_hex(32)
    g = consent.grant(book, ident, subject_ref="SYN-B",
                      commitment=consent.persona_commitment(PERSONA, nonce),
                      fields=list(PERSONA), scope="s", ts_ms=1, nonce_ref="n.bin")
    w = consent.withdraw(book, ident, subject_ref="SYN-B", grant_hash=g.hash(), ts_ms=2)
    with pytest.raises(consent.ConsentError) as exc:
        consent.erase(book, ident, subject_ref="SYN-B", withdraw_hash=w.hash(),
                      nonce_ref="n.bin", ts_ms=3,
                      erased=[{"ref": "persona.json", "sha256": "a" * 64, "bytes_n": 9}])
    assert "nonce" in str(exc.value)


def test_persona_gate_refuses_fields_outside_the_allowed_four():
    for bad in ({"politics": ["x"]}, {"health": ["x"]}, {"name": ["x"]},
                {"domains": ["ok"], "religion": ["x"]}):
        with pytest.raises(consent.ConsentError):
            consent.check_persona(bad)
    consent.check_persona(PERSONA)          # 正控制：四類都在的就要過


def test_persona_gate_does_not_silently_filter():
    """越界欄位要炸，不要靜靜丟掉——靜靜丟掉會讓上游以為它傳的東西進去了。"""
    p = dict(PERSONA)
    p["politics"] = ["x"]
    with pytest.raises(consent.ConsentError):
        consent.persona_commitment(p, secrets.token_hex(32))


def test_assert_no_plaintext_has_teeth(ident):
    """負控制：真的把原文寫進 payload 時，防呆必須抓到。"""
    book = Logbook()
    book.append("CONSENT_GRANT", {"subject_ref": "X", "leak": PERSONA["domains"][0]},
                ident, ts_ms=1)
    with pytest.raises(consent.ConsentError):
        consent.assert_no_plaintext(book, [PERSONA["domains"][0]])
    # 正控制：乾淨的鏈不准被誤殺
    clean = Logbook()
    _full_cycle(clean, ident)
    consent.assert_no_plaintext(clean, PERSONA["domains"] + PERSONA["topics"])


def test_erase_without_withdraw_is_flagged(ident, who):
    book = Logbook()
    nonce = secrets.token_hex(32)
    consent.grant(book, ident, subject_ref="SYN-C",
                  commitment=consent.persona_commitment(PERSONA, nonce),
                  fields=list(PERSONA), scope="s", ts_ms=1, nonce_ref="n.bin")
    consent.erase(book, ident, subject_ref="SYN-C", withdraw_hash="0" * 64,
                  nonce_ref="n.bin", ts_ms=2,
                  erased=[{"ref": "n.bin", "sha256": "a" * 64, "bytes_n": 1}])
    a = consent.audit(book, who)
    assert any("沒有撤回就宣告刪除" in p for p in a["problems"])
    assert a["subjects"]["SYN-C"].state == "granted"


def test_tampered_chain_is_caught(ident, who):
    book = Logbook()
    _full_cycle(book, ident)
    tampered = book.entries[1].to_json()
    tampered["payload"]["reason"] = "not_the_subject"
    book.entries[1] = type(book.entries[1]).from_json(tampered)
    assert not book.verify_chain(who)
    assert not consent.audit(book, who)["chain_ok"]


def test_commitment_is_the_same_primitive_as_logbook():
    """不另造一套承諾構造：`persona_commitment` 就是 `review_commitment`。"""
    from vacant_network import logbook as lb
    n = secrets.token_hex(32)
    assert consent.persona_commitment(PERSONA, n) == lb.review_commitment(PERSONA, n)
