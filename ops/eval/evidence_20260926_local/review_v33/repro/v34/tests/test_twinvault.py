"""原文鏈外、commitment 上鏈、撤回可驗 —— 2026-09-21 裁決的判準。

裁決：`decisions/DECISION_20260921_TWIN_CONSENT_AND_ERASURE.md` §三-1／§三-2
＋ `decisions/DECISION_20260921_TWIN_PLAINTEXT_OFFCHAIN.md`。

守的是 `vacant_network/consent.py` 檔頭那一句：

  > **原文一旦上鏈就刪不掉——那會讓「刪除證明」變成一句謊。**

紀律，這一份逐條遵守：

* **每一個綠燈配一個負控制。** 只證明「乾淨的輸入會綠」等於沒測。
* **「測試綠」不等於「接上去了」。** 2026-09-21 才抓到 `resolve_endpoint()`
  六條測試全綠而產品路徑零呼叫點。所以這裡有一條
  `test_ingest_really_calls_the_shared_guard`：它監視的是**產品路徑有沒有
  真的呼叫到 `consent.assert_no_plaintext`**，不是「那個函式存在」。
* **「沒量到」寫 `None` 不寫 `False`。**
"""
from __future__ import annotations

import json
import pathlib
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import twinlink, twinvault  # noqa: E402
from ops.exhibit.twin.twinstore import (  # noqa: E402
    KIND_ERASED, KIND_ERROR, KIND_GENERATED, KIND_SUBMITTED, KIND_WITHDRAWN,
    SEAL_TAG, TwinStore, canonical_json,
)
from vacant_network import consent  # noqa: E402

NEED = "整理我的桌面"          # 中文 ⇒ 一定進得了 secrets（非 ASCII）
TEXT = "我想要有人幫我把桌面整理乾淨，順便丟掉沒用的東西"
DEAD_ENDPOINT = "http://127.0.0.1:1/v1"


@pytest.fixture()
def store(tmp_path: pathlib.Path):
    s = TwinStore(tmp_path / "t.sqlite3")
    yield s
    s.close()


def _cloud(monkeypatch, items):
    def fake(url, payload=None, timeout=30.0, method=None):  # noqa: ANN001
        return 200, {"items": items}
    monkeypatch.setattr(twinlink, "_http_json", fake)


def _chain_blob(store: TwinStore) -> str:
    """整條鏈的 payload 串起來。要驗「原文一個字都沒上鏈」就看這一坨。"""
    return "\n".join(canonical_json(e["payload"]) for e in store.events())


# ---------------------------------------------------------------------------
# 0. 負控制：先證明「把原文寫上鏈」這件事真的量得出來
# ---------------------------------------------------------------------------

def test_the_old_way_really_did_put_plaintext_on_chain(store: TwinStore) -> None:
    """🔴 **先證明量具量得動。** 這是 2026-09-21 之前的寫法，逐字。

    沒有這一條，下面那些「鏈上找不到原文」的綠燈可能只是因為我找錯地方。
    """
    store.append(KIND_SUBMITTED, "old", {"card": {"need": NEED},
                                         "card_text": TEXT}, source="t")
    assert NEED in _chain_blob(store)
    assert TEXT in _chain_blob(store)


# ---------------------------------------------------------------------------
# 1. 產品路徑：ingest 之後鏈上沒有原文
# ---------------------------------------------------------------------------

def test_ingest_puts_commitment_on_chain_not_plaintext(
        store: TwinStore, monkeypatch) -> None:
    _cloud(monkeypatch, [{"id": "v1", "card": {"need": NEED}, "card_text": TEXT,
                          "ts": 123, "status": "queued"}])
    r = twinlink.ingest(store, "http://cloud.invalid", "t")
    assert r["pulled"] == 1

    blob = _chain_blob(store)
    assert NEED not in blob, "原文上鏈了——append-only ⇒ 刪不掉 ⇒ 刪除證明是謊"
    assert TEXT not in blob

    ev = next(store.events(kind=KIND_SUBMITTED))
    assert ev["payload"]["sealed"] == SEAL_TAG
    assert len(ev["payload"]["commitment"]) == 64
    assert "card" not in ev["payload"] and "card_text" not in ev["payload"]

    # 正控制：原文確實存在，只是住在鏈外——讀得到，而且驗得回那個 commitment。
    cur = store.current("v1")
    assert cur["card"] == {"need": NEED}
    assert cur["card_text"] == TEXT
    assert cur["card_available"] is True
    assert store.vault.commitment_ok("v1", ev["payload"]["commitment"]) is True


def test_ingest_really_calls_the_shared_guard(store: TwinStore, monkeypatch) -> None:
    """🔴 **「測試綠」不等於「接上去了」。**

    這一條不驗防呆本身好不好，它驗的是**產品路徑真的呼叫得到
    `consent.assert_no_plaintext`**——2026-09-21 抓到的病就是
    「擋門存在、產品路徑零呼叫點」。
    """
    seen: list[list[str]] = []
    real = consent.assert_no_plaintext

    def spy(book, secrets):  # noqa: ANN001
        seen.append(list(secrets))
        return real(book, secrets)

    monkeypatch.setattr(consent, "assert_no_plaintext", spy)
    _cloud(monkeypatch, [{"id": "v1", "card": {"need": NEED}, "card_text": TEXT}])
    twinlink.ingest(store, "http://cloud.invalid", "t")

    assert seen, "ingest 一次都沒呼叫 assert_no_plaintext ＝ 防呆沒接上去"
    flat = [s for call in seen for s in call]
    assert NEED in flat, "卡上的中文沒進 secrets ⇒ 防呆看不到它"
    assert any(len(s) == 64 and all(c in "0123456789abcdef" for c in s)
               for s in flat), "nonce 沒進 secrets（誠實邊界 3／4）"


def test_ingest_refuses_to_write_when_the_guard_trips(
        store: TwinStore, monkeypatch) -> None:
    """🔴 負控制：有人把原文放回 payload ⇒ **那一列不准進鏈**。

    模擬的是「未來某次改動又把 card 塞回去」。fail-closed：
    這張卡記一列 error、沒有分身，但鏈上乾淨。
    """
    real_seal = twinvault.TwinVault.seal_card

    def leaky(self, sub_id, card, card_text, **kw):  # noqa: ANN001
        payload, secs = real_seal(self, sub_id, card, card_text, **kw)
        payload["card"] = card          # ← 就是被抓到的那個繞過
        return payload, secs

    monkeypatch.setattr(twinvault.TwinVault, "seal_card", leaky)
    _cloud(monkeypatch, [{"id": "v1", "card": {"need": NEED}, "card_text": TEXT}])
    r = twinlink.ingest(store, "http://cloud.invalid", "t")

    assert r["rejected"] == 1 and r["pulled"] == 0
    assert store.count(KIND_SUBMITTED) == 0
    assert NEED not in _chain_blob(store)
    err = next(store.events(kind=KIND_ERROR))
    assert err["payload"]["guard"] == "VaultError"
    # 錯誤事件本身也上鏈 ⇒ 它不可以回貼例外訊息（訊息可能含原文）
    assert NEED not in canonical_json(err["payload"])


def test_error_events_cannot_leak_plaintext_either(
        store: TwinStore, monkeypatch) -> None:
    """🔴 **錯誤路徑也是上鏈的路徑。**

    例外訊息會逐字夾帶內容（`canonical_bytes` 炸在某個字元上就把它印出來）。
    把那種訊息寫進 append-only 鏈，等於從錯誤路徑把原文漏上鏈——一樣刪不掉。
    """
    def boom(self, sub_id, card, card_text, **kw):  # noqa: ANN001
        raise ValueError("壞在這裡：" + TEXT)       # ← 訊息裡有原文

    monkeypatch.setattr(twinvault.TwinVault, "seal_card", boom)
    _cloud(monkeypatch, [{"id": "v1", "card": {"need": NEED}, "card_text": TEXT}])
    r = twinlink.ingest(store, "http://cloud.invalid", "t")

    assert r["rejected"] == 1
    err = next(store.events(kind=KIND_ERROR))
    assert err["payload"]["reason_redacted"] is True
    assert TEXT not in _chain_blob(store)
    # 正控制：一般的（不含原文的）錯誤訊息照樣留得下來，不是一律遮掉
    assert "ValueError" in err["payload"]["reason"]


def test_ordinary_error_messages_are_not_redacted(
        store: TwinStore, monkeypatch) -> None:
    """負控制的另一邊：沒夾帶原文就不准遮——遮太多等於把除錯資訊丟光。"""
    def boom(self, sub_id, card, card_text, **kw):  # noqa: ANN001
        raise ValueError("disk full")

    monkeypatch.setattr(twinvault.TwinVault, "seal_card", boom)
    _cloud(monkeypatch, [{"id": "v1", "card": {"need": NEED}, "card_text": TEXT}])
    twinlink.ingest(store, "http://cloud.invalid", "t")
    err = next(store.events(kind=KIND_ERROR))
    assert "disk full" in err["payload"]["reason"]
    assert "reason_redacted" not in err["payload"]


def test_guard_catches_smuggling_into_a_whitelisted_field() -> None:
    """🔴 結構閘門擋不到的那一類，要靠 `assert_no_plaintext` 擋。

    兩層各擋各的：形狀合法（白名單內的欄位）但內容是原文 ⇒ 第 1 層放行、
    第 2 層必須攔下來。沒有這一條，第 2 層就只是裝飾。
    """
    payload = {"v": 2, "sealed": SEAL_TAG, "commitment": "a" * 64,
               "card_ref": "plain/" + "0" * 32 + "/card.json",
               "nonce_ref": "plain/" + "0" * 32 + "/nonce.hex",
               "cloud_status": NEED}
    twinvault.assert_sealed_shape(payload, "card")     # 形狀是合法的（正控制）
    with pytest.raises(consent.ConsentError):
        twinvault.assert_payload_clean(payload, [NEED])
    # 負控制的另一邊：同一個 payload 換掉那個值就要過
    twinvault.assert_payload_clean({**payload, "cloud_status": "queued"}, [NEED])


def test_short_ascii_values_do_not_false_positive() -> None:
    """誠實邊界：短的純 ASCII 原文不進 secrets，否則每張卡都被自己的防呆擋掉。

    這一條同時是那個殘餘的**可執行紀錄**——它擋不到，是設計上知道的。
    """
    secs = twinvault.secrets_for({"card": {"need": "e"}, "card_text": "ab"})
    assert secs == []
    zh = twinvault.secrets_for({"card": {"need": NEED}})
    assert NEED in zh, "中文（非 ASCII）必須進得了 secrets"


def test_seal_tag_has_one_source() -> None:
    """兩邊各寫一份 wire 常數＝早晚會漂。"""
    from ops.exhibit.twin import twinstore
    assert twinvault.SEAL_TAG is twinstore.SEAL_TAG


# ---------------------------------------------------------------------------
# 2. 生成的三句話也在鏈外（撤回之後螢幕不該還留著那個人的句子）
# ---------------------------------------------------------------------------

def test_generated_lines_are_off_chain(store: TwinStore, monkeypatch) -> None:
    _cloud(monkeypatch, [{"id": "v1", "card": {"need": NEED}}])
    twinlink.ingest(store, "http://cloud.invalid", "t")
    monkeypatch.setattr(twinlink, "generate_one", lambda *a, **k: {
        "arrival": "我到了" + NEED, "working": "在做", "handover": "交出去",
        "engine": "fallback_deterministic", "latency_ms": 3})
    twinlink.generate(store, DEAD_ENDPOINT, "m", timeout=1.0)

    ev = next(store.events(kind=KIND_GENERATED))
    assert ev["payload"]["sealed"] == SEAL_TAG
    assert "arrival" not in ev["payload"]
    # engine 仍然在鏈上（誠實邊界 2：真模型跟退化查表不可以長得一樣）
    assert ev["payload"]["engine"] == "fallback_deterministic"
    assert NEED not in _chain_blob(store)
    # 正控制：畫面照樣拿得到三句話
    assert store.current("v1")["twin"]["arrival"] == "我到了" + NEED
    assert twinlink.build_view(store)["people"][0]["arrival"] == "我到了" + NEED


# ---------------------------------------------------------------------------
# 3. 撤回 → 上鏈 → 真的 unlink → PERSONA_ERASED
# ---------------------------------------------------------------------------

def _ingest_and_generate(store: TwinStore, monkeypatch, sid: str = "v1") -> None:
    _cloud(monkeypatch, [{"id": sid, "card": {"need": NEED}, "card_text": TEXT}])
    twinlink.ingest(store, "http://cloud.invalid", "t")
    monkeypatch.setattr(twinlink, "generate_one", lambda *a, **k: {
        "arrival": "到了", "working": "做", "handover": "交",
        "engine": "fallback_deterministic"})
    twinlink.generate(store, DEAD_ENDPOINT, "m", timeout=1.0)


def test_withdraw_erases_plaintext_and_signs_the_proof(
        store: TwinStore, monkeypatch) -> None:
    _ingest_and_generate(store, monkeypatch)
    before = store.count()
    slug = twinvault.slug_for("v1")
    card_file = store.vault.root / "plain" / slug / "card.json"
    nonce_file = store.vault.root / "plain" / slug / "nonce.hex"
    assert card_file.exists() and nonce_file.exists()   # 正控制：刪之前真的在

    out = twinlink.withdraw(store, "v1")

    assert out["ok"] and out["signed"] is True
    assert out["fully_erased"] is True
    # 帳本**變長**不變短：撤回與刪除各留一列
    assert store.count() == before + 2
    assert store.count(KIND_WITHDRAWN) == 1 and store.count(KIND_ERASED) == 1
    assert store.verify()["ok"] is True

    # 原文真的不在了
    assert not card_file.exists() and not nonce_file.exists()
    assert store.current("v1")["card"] is None
    assert store.current("v1")["status"] == "erased"
    assert NEED not in _chain_blob(store)

    # 簽章鏈：狀態 erased、鏈自己驗得過、nonce 有列進被刪清單
    a = store.vault.audit()
    assert a["chain_ok"] is True and not a["problems"]
    assert a["subjects"]["v1"]["state"] == "erased"
    assert any(r.endswith("nonce.hex") for r in a["subjects"]["v1"]["erased_refs"])


def test_nonce_must_be_erased_too(store: TwinStore, monkeypatch) -> None:
    """🔴 誠實邊界 4：只刪原文留著 nonce ＝ 沒刪（commitment 窮舉得回原文）。

    負控制：把 nonce 從被刪清單裡拿掉，`consent.erase` 必須拒簽。
    """
    _ingest_and_generate(store, monkeypatch)
    twinlink.withdraw(store, "v1")
    ev = next(store.events(kind=KIND_ERASED))
    refs = [i["ref"] for i in ev["payload"]["erased"]]
    assert any(r.endswith("nonce.hex") for r in refs)

    with pytest.raises(consent.ConsentError):
        consent.erase(store.vault.book(), store.vault.identity(),
                      subject_ref="v1", withdraw_hash="0" * 64,
                      erased=[i for i in ev["payload"]["erased"]
                              if not i["ref"].endswith("nonce.hex")],
                      nonce_ref=[r for r in refs if r.endswith("nonce.hex")][0],
                      ts_ms=1)


def test_withdraw_is_idempotent(store: TwinStore, monkeypatch) -> None:
    _ingest_and_generate(store, monkeypatch)
    twinlink.withdraw(store, "v1")
    n = store.count()
    again = twinlink.withdraw(store, "v1")
    assert again["already"] is True
    assert store.count() == n, "重複撤回不可以再寫列（帳本刪不掉，會越長越長）"


def test_half_done_withdrawal_can_be_finished(
        store: TwinStore, monkeypatch) -> None:
    """🔴 「撤回了但還沒刪」必須補得完——那個狀態正是這條鏈存在的全部理由。

    造法：讓 `PERSONA_ERASED` 那一步炸掉（斷電／磁碟滿的替身），
    於是簽章鏈停在 `withdrawn`。再撤回一次要把它補成 `erased`，
    而且**不可以**再宣告一次撤回（帳本會多一筆沒有意義的重複）。
    """
    _ingest_and_generate(store, monkeypatch)
    real_erase = consent.erase

    def boom(*a, **k):  # noqa: ANN001
        raise consent.ConsentError("假裝簽不出來")

    monkeypatch.setattr(consent, "erase", boom)
    first = store.vault.withdraw("v1")
    assert first["signed"] is False and first["problems"]
    assert store.vault.state("v1") == "withdrawn"   # unfulfilled：看得見
    assert store.vault.audit()["subjects"]["v1"]["unfulfilled"] is True
    n_withdraw = sum(1 for e in store.vault.book().entries
                     if e.type == consent.WITHDRAW_TYPE)
    assert n_withdraw == 1

    # 檔案已經刪掉了，所以第二次沒有被刪物 ⇒ 要能從**原本那一筆**撤回接上去。
    # 先把 nonce／原文放回去模擬「刪到一半」的另一種版本。
    store.vault.seal_card("v1", {"need": NEED}, None, sign=False)
    monkeypatch.setattr(consent, "erase", real_erase)
    second = store.vault.withdraw("v1")

    assert second["signed"] is True, second["problems"]
    assert store.vault.state("v1") == "erased"
    assert sum(1 for e in store.vault.book().entries
               if e.type == consent.WITHDRAW_TYPE) == 1, "不可以再宣告一次撤回"
    assert store.vault.audit()["chain_ok"] is True
    assert not store.vault.audit()["problems"]


def test_withdraw_unknown_id_writes_nothing(store: TwinStore) -> None:
    """公網上任何人掃一遍 id 就能把 append-only 帳本灌到爆，而那些列刪不掉。"""
    n = store.count()
    out = twinlink.withdraw(store, "沒這個人")
    assert out["ok"] is False and out["reason"] == "unknown_id"
    assert store.count() == n


def test_withdrawn_person_is_not_regenerated_or_republished(
        store: TwinStore, monkeypatch) -> None:
    _cloud(monkeypatch, [{"id": "v1", "card": {"need": NEED}}])
    twinlink.ingest(store, "http://cloud.invalid", "t")
    twinlink.withdraw(store, "v1")

    called: list[int] = []

    def boom(*a, **k):  # noqa: ANN001
        called.append(1)
        return {"arrival": "a", "working": "b", "handover": "c", "engine": "x"}

    monkeypatch.setattr(twinlink, "generate_one", boom)
    r = twinlink.generate(store, DEAD_ENDPOINT, "m", timeout=1.0)
    assert called == [], "人家說了刪掉我，還拿他的卡去打模型＝沒在聽"
    assert r["generated"] == 0


def test_view_hides_the_erased_person_but_says_so(
        store: TwinStore, monkeypatch) -> None:
    _ingest_and_generate(store, monkeypatch)
    assert twinlink.build_view(store)["people"][0]["arrival"] == "到了"  # 正控制
    twinlink.withdraw(store, "v1")
    p = twinlink.build_view(store)["people"][0]
    assert p["card"] is None and p["arrival"] is None
    assert p["status"] == "erased"
    assert twinlink.build_view(store)["counts"]["withdrawn"] == 1
    assert "unlink" in twinlink.build_view(store)["erasure_honesty"]


# ---------------------------------------------------------------------------
# 4. 舊鏈：原文拿不掉，只能誠實標記
# ---------------------------------------------------------------------------

def test_legacy_plaintext_is_flagged_never_hidden(store: TwinStore) -> None:
    store.append(KIND_SUBMITTED, "old", {"card": {"need": NEED},
                                         "card_text": TEXT}, source="t")
    cur = store.current("old")
    assert cur["plaintext_on_chain"] is True
    assert cur["card"] == {"need": NEED}, "鏈上就是有，假裝看不到只是自欺"
    assert twinlink.build_view(store)["people"][0]["plaintext_on_chain"] is True


def test_migrate_copies_out_without_deleting_anything(store: TwinStore) -> None:
    store.append(KIND_SUBMITTED, "old", {"card": {"need": NEED},
                                         "card_text": TEXT}, source="t")
    before = store.count()
    rec = twinvault.migrate(store)

    assert rec["moved"] == 1
    assert rec["residual_plaintext_seqs"] == {"old": [1]}
    assert store.count() == before + 1, "migrate 只追加一列 note，不動舊列"
    assert NEED in _chain_blob(store), "🔴 舊列的原文還在——它本來就拿不掉"
    assert store.verify()["ok"] is True
    # 抄出來之後這位主體撤回得了（撤回前是撤不了的：檔案庫裡沒有他的東西）
    out = twinlink.withdraw(store, "old")
    assert out["signed"] is True
    assert out["fully_erased"] is False, "舊鏈那一份還在 ⇒ 不准說完全刪掉了"
    assert out["residual_plaintext_seqs"] == [1]


def test_withdraw_without_migration_is_honest_about_it(store: TwinStore) -> None:
    """沒抄出來的舊主體：撤回照樣上鏈，但**不准假裝簽出了刪除證明**。"""
    store.append(KIND_SUBMITTED, "old", {"card": {"need": NEED}}, source="t")
    out = twinlink.withdraw(store, "old")
    assert out["ok"] is True
    assert out["signed"] is False
    assert out["erased"] == []
    assert out["problems"], "簽不出來要講，不可以靜靜回一個好看的成功"
    assert store.count(KIND_WITHDRAWN) == 1


# ---------------------------------------------------------------------------
# 5. serve：唯讀那一條要維持唯讀，撤回另開一條
# ---------------------------------------------------------------------------

class _Srv:
    def __init__(self, db: pathlib.Path, **kw):
        from http.server import ThreadingHTTPServer  # noqa: F401
        self.kw = kw
        self.db = db
        self.thread: threading.Thread | None = None
        self.port = 0

    def __enter__(self):
        import socket
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        self.port = s.getsockname()[1]
        s.close()
        self.thread = threading.Thread(
            target=twinlink.serve,
            args=(self.db, self.port, "127.0.0.1"),
            kwargs=self.kw, daemon=True)
        self.thread.start()
        for _ in range(200):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{self.port}/stats",
                                       timeout=0.5).read()
                break
            except Exception:  # noqa: BLE001
                import time
                time.sleep(0.02)
        return self

    def __exit__(self, *a):
        return False

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"


def _get(url: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _post(url: str) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=b"", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_readonly_serve_neither_writes_nor_withdraws(
        tmp_path: pathlib.Path, monkeypatch) -> None:
    db = tmp_path / "t.sqlite3"
    st = TwinStore(db)
    _cloud(monkeypatch, [{"id": "v1", "card": {"need": NEED}}])
    twinlink.ingest(st, "http://cloud.invalid", "t")
    st.close()

    with _Srv(db) as srv:                       # 預設：撤回**關著**
        code, body = _get(srv.url("/withdraw/v1"))
        assert code == 200
        assert b'<meta charset="utf-8">' in body    # 本機 HTML 一定要有 charset
        assert "確定撤回".encode() in body
        code, body = _post(srv.url("/withdraw/v1"))
        assert code == 405, "唯讀那一台不可以撤得動"

    st = TwinStore(db)
    try:
        assert st.count(KIND_WITHDRAWN) == 0
        assert st.current("v1")["card"] == {"need": NEED}, "GET 不准動到任何東西"
    finally:
        st.close()


def test_readonly_reading_does_not_create_the_vault(tmp_path: pathlib.Path) -> None:
    """🔴 「唯讀」要是真的。`current()` 會去檔案庫開封——那不可以順手 mkdir。

    負控制在下面那一行：同一個路徑，**寫**的那一次就長出來了 ⇒
    這個量具分得出「有建」與「沒建」。
    """
    db = tmp_path / "t.sqlite3"
    st = TwinStore(db)
    st.append(KIND_SUBMITTED, "old", {"card": {"need": NEED}}, source="t")
    vault_root = st.vault.root
    st.close()
    assert not vault_root.exists()

    ro = TwinStore(db, read_only=True)
    try:
        twinlink.build_view(ro)
        ro.current("old")
        assert not vault_root.exists(), "唯讀讀一遍就在真相來源旁邊長出目錄"
    finally:
        ro.close()

    w = TwinStore(db)
    try:
        w.vault.seal_card("old", {"need": NEED}, None, sign=False)
        assert vault_root.exists()      # 負控制：寫的時候真的會建
    finally:
        w.close()


def test_serve_withdraw_endpoint_actually_erases(
        tmp_path: pathlib.Path, monkeypatch) -> None:
    db = tmp_path / "t.sqlite3"
    st = TwinStore(db)
    _cloud(monkeypatch, [{"id": "v1", "card": {"need": NEED}}])
    twinlink.ingest(st, "http://cloud.invalid", "t")
    slug = twinvault.slug_for("v1")
    card_file = st.vault.root / "plain" / slug / "card.json"
    assert card_file.exists()
    st.close()

    with _Srv(db, allow_withdraw=True) as srv:
        code, body = _post(srv.url("/withdraw/v1"))
        assert code == 200, body
        out = json.loads(body)
        assert out["ok"] and out["signed"] is True
        code, body = _post(srv.url(
            "/withdraw/" + urllib.parse.quote("沒這個人")))
        assert code == 404

    assert not card_file.exists(), "端點回 200 但原文還在＝那個 200 是謊"
    st = TwinStore(db)
    try:
        assert st.current("v1")["status"] == "erased"
        assert st.verify()["ok"] is True
    finally:
        st.close()


def test_withdraw_token_is_enforced_when_asked(
        tmp_path: pathlib.Path, monkeypatch) -> None:
    db = tmp_path / "t.sqlite3"
    st = TwinStore(db)
    _cloud(monkeypatch, [{"id": "v1", "card": {"need": NEED}}])
    twinlink.ingest(st, "http://cloud.invalid", "t")
    st.close()

    with _Srv(db, allow_withdraw=True, withdraw_token="s3cret") as srv:
        assert _post(srv.url("/withdraw/v1"))[0] == 403          # 負控制
        assert _post(srv.url("/withdraw/v1?token=s3cret"))[0] == 200
