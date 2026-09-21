"""twin/twinstore — 觀展者分身卡的**真相來源**：本機、append-only、雜湊鏈。

## 這支在架構裡承重什麼

`CLAUDE.md` 展場硬約束 2：「實體場地 ⇒ 離線可跑、可無人值守循環。不能假設網路。」
於是**真相來源必須在本機**。雲端那台（`vacant-world-cloud`，Zeabur）只是**郵箱**：
它是觀眾手機唯一投得進來的口，但它

1. 沒掛 volume 時**重佈署就歸零**（那個 repo 的 README 自己寫明），
2. `persist(sub)` 是**原地覆寫**——`queued → claimed → done` 每一步都把同一個
   JSON 檔蓋掉，中間狀態不留痕跡。

這兩件事都違反「資料不要刪除」（2026-09-20 人類指示）。所以這一支存在：
把郵箱裡的每一件事**抄進本機、只追加、永不覆寫**，並且鏈起來讓竄改看得出來。

```
   雲端郵箱（會歸零、會覆寫）          這一支（真相來源）
   ┌────────────────────┐            ┌──────────────────────────┐
   │ data/subs/<id>.json│ ──ingest──▶│ twin_event（只 INSERT）   │
   │ 原地覆寫、可能消失  │            │ seq 單調、雜湊鏈、UPDATE  │
   └────────────────────┘            │ 與 DELETE 被 trigger 擋   │
                                     └──────────────────────────┘
```

## 🔴 原文**不在這條鏈上**（2026-09-21 裁決）

鏈是 append-only ⇒ **原文一旦上鏈就刪不掉，那會讓「刪除證明」變成一句謊**
（`vacant_network/consent.py` 檔頭逐字）。所以 2026-09-21 起：

* `submitted`／`generated` 的 payload 只放 **commitment**（`sealed="twinvault.v1"`），
* 原文與 nonce 住在鏈外的檔案庫 `ops/exhibit/twin/twinvault.py`（**刪得掉**），
* `current()` 讀得到原文，是因為它去檔案庫開封，不是因為鏈上有；
  撤回之後檔案庫那一份 `unlink()` 掉，同一支 `current()` 就再也拿不到。

⚠ **2026-09-21 之前寫進來的列帶著原文，而且拿不掉。** 那些主體的 `current()`
會帶 `plaintext_on_chain: True`——**不是瑕疵標記，是事實標記**，不要靜靜隱藏。

## Append-only 是可執行的，不是慣例

`UPDATE` 與 `DELETE` 由 **SQLite trigger `RAISE(ABORT)`** 擋下（見 `SCHEMA`）。
不是「我們約定不要這樣寫」，是寫了就炸。負控制在
`tests/test_twinstore.py::test_update_and_delete_are_blocked`。

狀態不是欄位、是**摺疊**：`current()` 走一遍事件流算出「現在」，
要改狀態就**追加一列新事件**（`fold` 取最後一筆），從不回頭改舊列。

## 誠實邊界（改碼時保留）

1. **雜湊鏈證明的是「竄改看得出來」，不是「竄改不可能」。**
   拿得到這個檔案的人可以把整條鏈從某一列開始**全部重算**，`verify()` 就會通過。
   它擋得住的是「改一列就走」（最常見的意外與偷懶），擋不住有決心的重寫。
   要擋後者需要把鏈頭**外部錨定**（例如 `vacant_network/logbook.py` 的簽章鏈
   ＋定期把 head 抄到別處）——這一支**沒有做**，不要讀成做了。
2. **trigger 擋的是 SQL 路徑。** `rm twinstore.sqlite3`、直接用 hex editor 改 page、
   或 `.dump` 後重建，trigger 一概管不到。防那些要靠備份與離機副本。
3. **`seq` 連續 ≠ 沒漏收。** 它只保證「寫進來的沒被抽掉」，
   不保證「雲端發生過的都寫進來了」——漏收發生在 ingest 那一端（網路斷、
   郵箱已歸零），會記成 `ingest_gap` 事件，不會靜靜當成 0。

用法：
    python3 ops/exhibit/twin/twinstore.py init
    python3 ops/exhibit/twin/twinstore.py verify        # 退出碼 0 綠 / 1 紅
    python3 ops/exhibit/twin/twinstore.py stats
    python3 ops/exhibit/twin/twinstore.py roster
    python3 ops/exhibit/twin/twinstore.py dump --limit 20
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sqlite3
import sys
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Iterator

HERE = pathlib.Path(__file__).resolve()
TWIN = HERE.parent
# 讓這一支當腳本跑的時候也 import 得到 `ops.…` 與 `vacant_network.…`
# （`current()` 要去檔案庫開封）。放在這裡而不是各呼叫端各補一次。
if str(TWIN.parents[2]) not in sys.path:
    sys.path.insert(0, str(TWIN.parents[2]))

#: 預設資料庫位置。展場那台、1003、Mac 都跑得起來，路徑用環境變數換。
#: 放在 `store/` 底下而不是 `live/`，是因為 `live/` 那批是**可重建的輸出**
#: （截檔重播是設計的一部分），而這裡的東西**永遠不截**。
DEFAULT_DB = pathlib.Path(
    os.environ.get("VACANT_TWIN_DB") or (TWIN / "store" / "twinstore.sqlite3")
)


def default_vault_root(db_path: pathlib.Path | str) -> pathlib.Path:
    """檔案庫預設住哪裡：`<庫名>.vault/` 就在庫旁邊。

    跟著庫走而不是跟著目錄走，是因為同一個資料夾可能有兩個庫（演練、正式），
    共用一個檔案庫會讓 A 庫的撤回把 B 庫的原文刪掉。
    """
    p = pathlib.Path(db_path)
    env = os.environ.get("VACANT_TWIN_VAULT")
    return pathlib.Path(env) if env else p.parent / (p.stem + ".vault")


#: 創世串：鏈的第一列的 `prev_sha256`。含 store_id，讓兩個不同的庫
#: 不可能長出同一條鏈（否則「把別台的鏈接過來」會驗得過）。
GENESIS_PREFIX = "vacant.twinstore.v1"

#: 封印標記。payload 帶著它 ⇒ 裡面只有 commitment，原文在 `twinvault` 的檔案庫。
#: **wire 常數**，改它就讀不懂既有的鏈。定義在這裡是因為它是**鏈格式**的一部分；
#: `twinvault.SEAL_TAG` 直接 import 這一個（兩邊各寫一份＝早晚會漂）。
SEAL_TAG = "twinvault.v1"


#: 事件種類。**不是狀態機的狀態**，是「發生過什麼」。
#: 狀態由 `current()` 摺疊算出來。
KIND_SUBMITTED = "submitted"   # 觀眾投了一張卡（從雲端郵箱抄進來）
KIND_GENERATED = "generated"   # 分身生成完成（1003 的模型回話了）
KIND_PUBLISHED = "published"   # 結果回寫雲端成功（觀眾手機看得到了）
KIND_ERROR = "error"           # 某一步失敗。**失敗也是資料**，不准靜靜丟掉
KIND_INGEST_GAP = "ingest_gap" # 明知道漏收了（雲端連不上／郵箱歸零）
KIND_NOTE = "note"             # 人工註記／端到端演練標記
KIND_WITHDRAWN = "withdrawn"   # 觀眾撤回同意（**宣告**，刪除是下一列）
KIND_ERASED = "erased"         # 鏈外原文真的被 unlink 了，帶被刪位元組的 sha256

KINDS = (
    KIND_SUBMITTED, KIND_GENERATED, KIND_PUBLISHED,
    KIND_ERROR, KIND_INGEST_GAP, KIND_NOTE,
    KIND_WITHDRAWN, KIND_ERASED,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS twin_meta (
    k TEXT PRIMARY KEY,
    v TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS twin_event (
    seq            INTEGER PRIMARY KEY,
    ts_unix_ms     INTEGER NOT NULL,
    ts_utc         TEXT    NOT NULL,
    sub_id         TEXT    NOT NULL,
    kind           TEXT    NOT NULL,
    source         TEXT    NOT NULL,
    payload_json   TEXT    NOT NULL,
    payload_sha256 TEXT    NOT NULL,
    prev_sha256    TEXT    NOT NULL,
    row_sha256     TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_twin_event_sub  ON twin_event(sub_id);
CREATE INDEX IF NOT EXISTS ix_twin_event_kind ON twin_event(kind);

-- 🔴 append-only 的牙齒。寫了 UPDATE/DELETE 不是「不建議」，是 ABORT。
CREATE TRIGGER IF NOT EXISTS twin_event_no_update
BEFORE UPDATE ON twin_event BEGIN
    SELECT RAISE(ABORT, 'twin_event 是 append-only：禁止 UPDATE，要改就追加一列');
END;

CREATE TRIGGER IF NOT EXISTS twin_event_no_delete
BEFORE DELETE ON twin_event BEGIN
    SELECT RAISE(ABORT, 'twin_event 是 append-only：禁止 DELETE');
END;
"""


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(obj: Any) -> str:
    """確定性序列化。鏈上算的是這個字串的 sha256，所以它必須逐 byte 可重現。"""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def row_digest(seq: int, ts_unix_ms: int, sub_id: str, kind: str,
               source: str, payload_sha256: str, prev_sha256: str) -> str:
    """一列的雜湊。欄位用 `\\n` 串接——換行不可能出現在 sha256／seq／kind 裡，
    而 `sub_id` 與 `source` 在 `append()` 進來時就擋掉換行，所以串接無歧義。"""
    return _sha("\n".join([
        str(seq), str(ts_unix_ms), sub_id, kind, source, payload_sha256, prev_sha256,
    ]))


class AppendOnlyViolation(RuntimeError):
    """SQL 層試圖 UPDATE/DELETE 時 SQLite 丟出來的東西，包成我們自己的型別。"""


class TwinStore:
    """append-only 事件庫。所有寫入只有一條路：`append()`。"""

    def __init__(self, path: pathlib.Path | str = DEFAULT_DB,
                 read_only: bool = False,
                 vault: pathlib.Path | str | None = None) -> None:
        """`read_only=True` 由 SQLite 層強制唯讀（`mode=ro`），不是靠自律。

        ⚠ 為什麼需要這個旗標：預設建構子會 `mkdir` ＋ `executescript(SCHEMA)`
        ——**那是寫入**。給現場螢幕用的「唯讀」端點如果走預設路徑，
        每一次 GET 都在對真相來源寫東西，那句「唯讀」就是假的。
        """
        self.path = pathlib.Path(path)
        self.read_only = read_only
        self.vault_root = pathlib.Path(vault) if vault else default_vault_root(self.path)
        self._vault: Any = None
        if read_only:
            uri = "file:" + urllib.request.pathname2url(str(self.path)) + "?mode=ro"
            self.conn = sqlite3.connect(uri, uri=True, timeout=30.0)
            self.conn.row_factory = sqlite3.Row
            self.conn.isolation_level = None
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), timeout=30.0)
        self.conn.row_factory = sqlite3.Row
        # 交易自己管（autocommit）。python 的 sqlite3 預設會替 DML 偷偷開一個交易，
        # 而**被 trigger 擋下的那一句會把那個交易留在開著的狀態**——下一次
        # `BEGIN IMMEDIATE` 就炸 "cannot start a transaction within a transaction"。
        # 換句話說：預設行為會讓「append-only 擋成功」這件事汙染後面每一次寫入。
        self.conn.isolation_level = None
        # WAL：ingest 在寫的同時，現場螢幕那一端還讀得到。展場不能因為
        # 「有人剛投了一張卡」就讓畫面卡住。
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=FULL")  # 展覽現場會直接拔電源
        self.conn.executescript(SCHEMA)
        self._ensure_store_id()

    # -- 鏈外檔案庫 -----------------------------------------------------------

    @property
    def vault(self) -> Any:
        """鏈外檔案庫（原文住的地方）。**惰性建立**。

        ⚠ 惰性不是效能考量，是「唯讀真的唯讀」：`TwinVault` 的建構子不 mkdir，
        讀路徑也不 mkdir，所以 `serve` 的 GET 走過來不會在真相來源旁邊長出目錄。
        import 也放在函式裡——`twinvault` 需要 `cryptography`，而
        `twinstore` 的雜湊鏈本身不需要，不要讓核心多綁一個相依。
        """
        if self._vault is None:
            from ops.exhibit.twin.twinvault import TwinVault
            self._vault = TwinVault(self.vault_root)
        return self._vault

    # -- meta ---------------------------------------------------------------

    def _ensure_store_id(self) -> str:
        cur = self.conn.execute("SELECT v FROM twin_meta WHERE k='store_id'")
        row = cur.fetchone()
        if row:
            return row["v"]
        sid = uuid.uuid4().hex
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self.conn.execute(
                "INSERT INTO twin_meta(k, v) VALUES ('store_id', ?)", (sid,))
            self.conn.execute(
                "INSERT OR REPLACE INTO twin_meta(k, v) VALUES ('created_utc', ?)",
                (datetime.now(timezone.utc).isoformat(),))
            self.conn.execute("COMMIT")
        except sqlite3.IntegrityError:
            # 另一個行程同時建庫。回頭讀它寫的那一個，不要兩個 store_id 打架。
            self.conn.execute("ROLLBACK")
            return self.conn.execute(
                "SELECT v FROM twin_meta WHERE k='store_id'").fetchone()["v"]
        return sid

    @property
    def store_id(self) -> str:
        return self.conn.execute(
            "SELECT v FROM twin_meta WHERE k='store_id'").fetchone()["v"]

    def genesis(self) -> str:
        return _sha(f"{GENESIS_PREFIX}\n{self.store_id}")

    # -- 寫（唯一一條路） -----------------------------------------------------

    def append(self, kind: str, sub_id: str, payload: Any,
               source: str, ts_unix_ms: int | None = None) -> dict[str, Any]:
        """追加一列。回傳那一列。**沒有 update()、沒有 delete()，刻意的。**"""
        if kind not in KINDS:
            raise ValueError(f"未知的 kind：{kind!r}（允許 {KINDS}）")
        for name, val in (("sub_id", sub_id), ("source", source), ("kind", kind)):
            if not isinstance(val, str) or not val:
                raise ValueError(f"{name} 必須是非空字串，拿到 {val!r}")
            if "\n" in val:
                # 串接雜湊的前提。讓它明確地炸，而不是安靜地讓兩列算出同一個 digest。
                raise ValueError(f"{name} 不可含換行（雜湊鏈用換行當分隔）：{val!r}")

        payload_json = canonical_json(payload)
        payload_sha = _sha(payload_json)
        now_ms = int(ts_unix_ms if ts_unix_ms is not None
                     else datetime.now(timezone.utc).timestamp() * 1000)
        ts_utc = datetime.fromtimestamp(now_ms / 1000, timezone.utc).isoformat()

        # BEGIN IMMEDIATE：seq 與 prev 要一起讀一起寫，否則兩個 ingest 同時跑
        # 會算出同一個 prev，鏈就分岔了。
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            last = self.conn.execute(
                "SELECT seq, row_sha256 FROM twin_event ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            seq = (last["seq"] + 1) if last else 1
            prev = last["row_sha256"] if last else self.genesis()
            digest = row_digest(seq, now_ms, sub_id, kind, source, payload_sha, prev)
            self.conn.execute(
                "INSERT INTO twin_event(seq, ts_unix_ms, ts_utc, sub_id, kind, source,"
                " payload_json, payload_sha256, prev_sha256, row_sha256)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (seq, now_ms, ts_utc, sub_id, kind, source,
                 payload_json, payload_sha, prev, digest),
            )
            self.conn.execute("COMMIT")
        except sqlite3.IntegrityError:
            self.conn.execute("ROLLBACK")
            raise
        except Exception:
            self.conn.execute("ROLLBACK")
            raise
        return {
            "seq": seq, "ts_unix_ms": now_ms, "ts_utc": ts_utc, "sub_id": sub_id,
            "kind": kind, "source": source, "payload": payload,
            "payload_sha256": payload_sha, "prev_sha256": prev, "row_sha256": digest,
        }

    # -- 讀 -------------------------------------------------------------------

    def events(self, sub_id: str | None = None,
               kind: str | None = None) -> Iterator[dict[str, Any]]:
        sql = "SELECT * FROM twin_event"
        where, args = [], []
        if sub_id:
            where.append("sub_id = ?"); args.append(sub_id)
        if kind:
            where.append("kind = ?"); args.append(kind)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY seq ASC"
        for r in self.conn.execute(sql, args):
            d = dict(r)
            d["payload"] = json.loads(d["payload_json"])
            yield d

    def head(self) -> dict[str, Any] | None:
        r = self.conn.execute(
            "SELECT * FROM twin_event ORDER BY seq DESC LIMIT 1").fetchone()
        if not r:
            return None
        d = dict(r)
        d["payload"] = json.loads(d["payload_json"])
        return d

    def count(self, kind: str | None = None) -> int:
        if kind:
            return self.conn.execute(
                "SELECT COUNT(*) c FROM twin_event WHERE kind=?", (kind,)
            ).fetchone()["c"]
        return self.conn.execute(
            "SELECT COUNT(*) c FROM twin_event").fetchone()["c"]

    def sub_ids(self) -> list[str]:
        return [r["sub_id"] for r in self.conn.execute(
            "SELECT sub_id, MIN(seq) s FROM twin_event WHERE kind=?"
            " GROUP BY sub_id ORDER BY s ASC", (KIND_SUBMITTED,))]

    # -- 摺疊出「現在」（不是欄位，是算出來的） --------------------------------

    def current(self, sub_id: str) -> dict[str, Any] | None:
        """把一個 sub_id 的事件流摺成現況。**沒有任何一列被改過。**

        原文（`card`／`card_text`／分身的三句話）**不在鏈上**：這裡看到的是
        去鏈外檔案庫開封的結果。撤回之後檔案庫那一份被 `unlink()`，
        同一支函式就回 `None`——「刪了」在讀取面是真的看得到的。

        ⚠ 舊列（2026-09-21 之前）的原文在 payload 裡，拿不掉。那種情況
        `plaintext_on_chain=True`，**照樣回原文**（它本來就在鏈上，
        假裝看不到只是自欺）。
        """
        evs = list(self.events(sub_id=sub_id))
        if not evs:
            return None
        out: dict[str, Any] = {
            "sub_id": sub_id, "card": None, "twin": None,
            "submitted_seq": None, "generated_seq": None, "published_seq": None,
            "withdrawn_seq": None, "erased_seq": None,
            "sealed": False, "plaintext_on_chain": False,
            "errors": [], "status": "unknown",
        }
        card_ref: dict[str, Any] | None = None
        twin_ref: dict[str, Any] | None = None
        for e in evs:  # 依 seq 遞增，後面的蓋掉前面的 ⇒ 「最後一筆贏」
            p = e["payload"] if isinstance(e["payload"], dict) else {}
            sealed = p.get("sealed") == SEAL_TAG
            if e["kind"] == KIND_SUBMITTED:
                out["submitted_seq"] = e["seq"]
                out["cloud_ts"] = p.get("ts")
                if sealed:
                    out["sealed"] = True
                    card_ref = p
                else:
                    out["card"] = p.get("card")
                    out["card_text"] = p.get("card_text")
                    if p.get("card") is not None or p.get("card_text") is not None:
                        out["plaintext_on_chain"] = True
            elif e["kind"] == KIND_GENERATED:
                out["generated_seq"] = e["seq"]
                out["twin"] = dict(p)
                if sealed:
                    twin_ref = p
                elif any(p.get(k) for k in ("arrival", "working", "handover")):
                    out["plaintext_on_chain"] = True
            elif e["kind"] == KIND_PUBLISHED:
                out["published_seq"] = e["seq"]
            elif e["kind"] == KIND_WITHDRAWN:
                out["withdrawn_seq"] = e["seq"]
            elif e["kind"] == KIND_ERASED:
                out["erased_seq"] = e["seq"]
                out["erased_refs"] = [i.get("ref") for i in (p.get("erased") or [])]
            elif e["kind"] == KIND_ERROR:
                out["errors"].append({"seq": e["seq"], **p})

        # 鏈外開封。**檔案不在就是不在**——不要回一個空字串假裝有東西。
        if card_ref is not None:
            plain = self.vault.open_card(sub_id)
            out["card"] = (plain or {}).get("card")
            out["card_text"] = (plain or {}).get("card_text")
            out["card_commitment"] = card_ref.get("commitment")
            out["card_available"] = plain is not None
        if twin_ref is not None:
            plain = self.vault.open_twin(sub_id)
            out["twin"] = {**dict(twin_ref), **(plain or {})}
            out["twin_available"] = plain is not None

        if out["erased_seq"]:
            out["status"] = "erased"
        elif out["withdrawn_seq"]:
            out["status"] = "withdrawn"
        elif out["published_seq"]:
            out["status"] = "published"
        elif out["generated_seq"]:
            out["status"] = "generated"
        elif out["submitted_seq"]:
            out["status"] = "submitted"
        return out

    def roster(self) -> list[dict[str, Any]]:
        return [c for c in (self.current(s) for s in self.sub_ids()) if c]

    def pending(self, kind_done: str, kind_src: str = KIND_SUBMITTED) -> list[str]:
        """有 `kind_src` 但還沒有 `kind_done` 的 sub_id，依最早出現排序。"""
        rows = self.conn.execute(
            "SELECT sub_id, MIN(seq) s FROM twin_event WHERE kind=?"
            " AND sub_id NOT IN (SELECT sub_id FROM twin_event WHERE kind=?)"
            " GROUP BY sub_id ORDER BY s ASC", (kind_src, kind_done))
        return [r["sub_id"] for r in rows]

    # -- 驗鏈 -----------------------------------------------------------------

    def verify(self) -> dict[str, Any]:
        """從創世走到鏈頭。回 `{ok, checked, broken_at, reason}`。

        `broken_at` 是**第一個**對不上的 seq；`ok=True` 時它是 `None`
        （不是 0——0 是一個合法的 seq 位置，寫 0 就是說謊）。
        """
        prev = self.genesis()
        checked = 0
        expect_seq = 1
        for r in self.conn.execute("SELECT * FROM twin_event ORDER BY seq ASC"):
            if r["seq"] != expect_seq:
                return {"ok": False, "checked": checked, "broken_at": r["seq"],
                        "reason": f"seq 不連續：預期 {expect_seq} 拿到 {r['seq']}"}
            if _sha(r["payload_json"]) != r["payload_sha256"]:
                return {"ok": False, "checked": checked, "broken_at": r["seq"],
                        "reason": "payload 與 payload_sha256 對不上（內容被改過）"}
            if r["prev_sha256"] != prev:
                return {"ok": False, "checked": checked, "broken_at": r["seq"],
                        "reason": "prev_sha256 接不上前一列（鏈斷）"}
            want = row_digest(r["seq"], r["ts_unix_ms"], r["sub_id"], r["kind"],
                              r["source"], r["payload_sha256"], r["prev_sha256"])
            if want != r["row_sha256"]:
                return {"ok": False, "checked": checked, "broken_at": r["seq"],
                        "reason": "row_sha256 與欄位算出來的不符（欄位被改過）"}
            prev = r["row_sha256"]
            checked += 1
            expect_seq += 1
        return {"ok": True, "checked": checked, "broken_at": None,
                "reason": "全鏈自洽", "head": prev if checked else None,
                "genesis": self.genesis()}

    def close(self) -> None:
        self.conn.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _p(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="twinstore — append-only 分身卡真相來源")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="建庫（冪等）")
    sub.add_parser("verify", help="驗雜湊鏈；退出碼 0 綠 / 1 紅")
    sub.add_parser("stats", help="筆數統計")
    sub.add_parser("roster", help="摺疊出每一位觀眾的現況")
    d = sub.add_parser("dump", help="倒出事件流")
    d.add_argument("--limit", type=int, default=0)
    d.add_argument("--sub-id", default=None)
    n = sub.add_parser("note", help="追加一列人工註記")
    n.add_argument("text")
    n.add_argument("--sub-id", default="_ops")

    a = ap.parse_args(list(argv) if argv is not None else None)
    st = TwinStore(a.db)

    if a.cmd == "init":
        _p({"db": str(st.path), "store_id": st.store_id,
            "genesis": st.genesis(), "events": st.count()})
        return 0
    if a.cmd == "verify":
        r = st.verify()
        _p({"db": str(st.path), **r})
        return 0 if r["ok"] else 1
    if a.cmd == "stats":
        _p({"db": str(st.path), "store_id": st.store_id,
            "total": st.count(),
            "by_kind": {k: st.count(k) for k in KINDS},
            "visitors": len(st.sub_ids()),
            "head_seq": (st.head() or {}).get("seq")})
        return 0
    if a.cmd == "roster":
        _p(st.roster())
        return 0
    if a.cmd == "dump":
        evs = list(st.events(sub_id=a.sub_id))
        if a.limit:
            evs = evs[-a.limit:]
        for e in evs:
            e.pop("payload_json", None)
        _p(evs)
        return 0
    if a.cmd == "note":
        _p(st.append(KIND_NOTE, a.sub_id, {"text": a.text}, source="cli"))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
