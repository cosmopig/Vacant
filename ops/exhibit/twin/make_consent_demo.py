"""twin/make_consent_demo — 產出展件的同意／撤回／刪除鏈（一次，產物進版控）。

## 這支在架構裡承重什麼

`SPEC_v3 §七` 的第 5 項（退場與撤回上鏈）依賴第 4 項（persona 萃取，**待倫理
定案**）。但第 5 項的**機制**不依賴真人資料——它只需要「有一份東西、它有
commitment、它被刪了」。本支就用**合成捐贈者**把那個機制真的跑一遍，
讓展件現在就有一條可驗的同意鏈，而不必等倫理定案。

流程逐字照 `vacant/consent.py`：

    persona（鏈外）＋ nonce（鏈外）
        → commitment  ──簽──→  CONSENT_GRANT
        → 捐贈者撤回   ──簽──→  CONSENT_WITHDRAW
        → **真的刪掉檔案**（persona 與 nonce 兩個都刪）
        → 刪掉的位元組 sha256 ──簽──→ PERSONA_ERASED

「真的刪掉」不是修辭：本支會把那兩個檔寫到磁碟、算 sha256、`unlink()`，
再把 hash 簽上鏈。所以 `erased[].sha256` 是**刪除前那份位元組的雜湊**，
不是憑空造的字串。

## 誠實邊界

1. **捐贈者是合成的。** 這一條鏈證明機制接得起來，不證明任何關於真人的事。
   頁面上必須寫「這是示範，不是資料」。
2. 刪除證明的射程見 `vacant/consent.py` 的四條誠實邊界，尤其第 1 條：
   鏈記的是「我們刪了」，不是「世上沒有副本」。
3. `ts_ms` 寫死，所以重跑只會換金鑰與簽章；產物進版控，
   `build_viewer.py --check` 比的是頁面與**磁碟上這一份**，不是重新產生的一份。

用法：
    python3 ops/exhibit/twin/make_consent_demo.py            # 寫出 consent_demo/
    python3 ops/exhibit/twin/make_consent_demo.py --check    # 只驗磁碟上那一份
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import secrets
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from ops.exhibit.twin import roster as rosterlib  # noqa: E402
from vacant import consent, crypto  # noqa: E402
from vacant.canonical import canonical_bytes  # noqa: E402
from vacant.identity import Identity, PublicIdentity  # noqa: E402
from vacant.logbook import Logbook  # noqa: E402

OUT = HERE.parent / "consent_demo"
CHAIN = OUT / "chain.ndjson"
PUB = OUT / "chain.pub.json"
MANIFEST = OUT / "manifest.json"

#: 寫死的時間戳（毫秒）。展件不需要真實時間，而浮動的時間戳會讓每次重跑都
#: 產生一份不一樣的產物，`--check` 就永遠對不上。
T0 = 1_789_000_000_000
SCOPE = "展覽期間用這四類欄位生成一位居民，並在會場公開展示它的工作紀錄"


def build() -> tuple[Logbook, Identity, dict]:
    ident = Identity.generate()
    book = Logbook()
    residents = rosterlib.default_roster()
    secrets_seen: list[str] = []
    records: list[dict] = []

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        ts = T0
        grants: dict[str, tuple] = {}

        # --- 每一位都先同意 -------------------------------------------------
        for r in residents:
            nonce = secrets.token_hex(32)
            persona_bytes = canonical_bytes(r.persona)
            nonce_bytes = nonce.encode("ascii")
            p_path = tmp / f"persona_{r.subject_ref}.json"
            n_path = tmp / f"nonce_{r.subject_ref}.bin"
            p_path.write_bytes(persona_bytes)
            n_path.write_bytes(nonce_bytes)

            commit = consent.persona_commitment(r.persona, nonce)
            g = consent.grant(
                book, ident, subject_ref=r.subject_ref, commitment=commit,
                fields=list(r.persona), scope=SCOPE, ts_ms=ts,
                nonce_ref=n_path.name)
            ts += 1000
            grants[r.subject_ref] = (g, p_path, n_path, nonce)
            secrets_seen.extend(list(r.persona["domains"]) + [nonce])
            records.append({"subject_ref": r.subject_ref, "event": "grant",
                            "entry_hash": g.hash(), "commitment": commit})

        # --- 最後一位撤回，而且真的被刪掉 ------------------------------------
        target = residents[-1]
        g, p_path, n_path, _nonce = grants[target.subject_ref]
        w = consent.withdraw(book, ident, subject_ref=target.subject_ref,
                             grant_hash=g.hash(), ts_ms=ts)
        ts += 1000
        records.append({"subject_ref": target.subject_ref, "event": "withdraw",
                        "entry_hash": w.hash()})

        erased = []
        for path in (n_path, p_path):          # nonce 先刪：它是 hiding 的全部
            data = path.read_bytes()
            erased.append({"ref": path.name,
                           "sha256": hashlib.sha256(data).hexdigest(),
                           "bytes_n": len(data)})
            path.unlink()
            assert not path.exists(), f"{path} 沒有真的被刪掉"

        e = consent.erase(book, ident, subject_ref=target.subject_ref,
                          withdraw_hash=w.hash(), erased=erased,
                          nonce_ref=n_path.name, ts_ms=ts)
        records.append({"subject_ref": target.subject_ref, "event": "erase",
                        "entry_hash": e.hash(),
                        "erased": [i["ref"] for i in erased]})

    # 鏈上不准出現原文或 nonce。這一條在寫檔**之前**跑——鏈是 append-only，
    # 事後掃到就已經來不及了。
    consent.assert_no_plaintext(book, secrets_seen)

    who = PublicIdentity(vacant_id=ident.vacant_id, pub=ident.pub)
    if not book.verify_chain(who):
        raise SystemExit("剛簽出來的鏈自己驗不過——不要寫出去")

    manifest = {
        "v": 1,
        "what": "合成捐贈者的同意／撤回／刪除示範鏈",
        "synthetic": True,
        "honesty": [
            "這是示範，不是資料：捐贈者是程序生成的，沒有任何真人參與。",
            "鏈記的是「我們記下我們刪了，而且刪掉的位元組 sha256 是 X」，"
            "不是「世上沒有副本」。",
            # ⚠ 措辭刻意避開展場紅線的那幾個詞（CLAUDE.md §硬約束 5）：
            # 這幾句會**原樣顯示在展件上**，所以界線要用觀眾讀得懂、
            # 又不會被讀成承諾的話講。意思一個字沒少。
            "撤回上鏈 ≠ 撤回被執行。鏈讓「撤回了但沒刪」看得見，"
            "它提高被發現的機率；刪除有沒有真的發生，鏈說不了。",
            "刪除連 nonce 一起刪：只刪原文而留著 nonce，"
            "鏈上的 commitment 可以被窮舉回原文。",
        ],
        "scope": SCOPE,
        "subjects": [r.subject_ref for r in rosterlib.default_roster()],
        "records": records,
        "stream_id": book.stream_id(),
        "head": book.head(),
        "n_entries": len(book),
    }
    return book, ident, manifest


def write() -> None:
    book, ident, manifest = build()
    OUT.mkdir(parents=True, exist_ok=True)
    book.save(CHAIN)
    PUB.write_text(json.dumps(
        {"vacant_id": ident.vacant_id,
         "pub_hex": crypto.pub_to_hex(ident.pub)},
        ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                                   indent=2) + "\n", encoding="utf-8")
    print(f"寫出 {CHAIN.relative_to(REPO)}：{len(book)} 筆")
    print(f"  stream_id {manifest['stream_id'][:16]}…  head {manifest['head'][:16]}…")


def check() -> int:
    if not CHAIN.exists():
        print("[BROKEN] consent_demo/chain.ndjson 不存在")
        return 1
    book = Logbook.load(CHAIN)
    meta = json.loads(PUB.read_text(encoding="utf-8"))
    who = PublicIdentity.from_hex(meta["vacant_id"], meta["pub_hex"])
    bad = []
    if not book.verify_chain(who):
        bad.append("鏈驗不過")
    audit = consent.audit(book, who)
    if audit["problems"]:
        bad.append("稽核有問題：%s" % audit["problems"])
    states = {k: v.state for k, v in audit["subjects"].items()}
    if "erased" not in states.values():
        bad.append("示範鏈裡沒有任何一位被刪除")
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if man["head"] != book.head() or man["stream_id"] != book.stream_id():
        bad.append("manifest 的 head／stream_id 與鏈對不上")
    for b in bad:
        print("[BROKEN] " + b)
    print("總判定：%s（%d 筆，狀態 %s）"
          % ("OK" if not bad else "BROKEN", len(book), states))
    return 0 if not bad else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="產出／檢查展件的同意示範鏈")
    ap.add_argument("--check", action="store_true", help="只檢查磁碟上那一份")
    a = ap.parse_args(argv)
    if a.check:
        return check()
    write()
    return check()


if __name__ == "__main__":
    sys.exit(main())
