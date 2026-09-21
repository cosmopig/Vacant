"""twin/twinvault — **原文住這裡（鏈外、刪得掉）；鏈上只留 commitment。**

## 這支在架構裡承重什麼

`vacant_network/consent.py` 的檔頭早就把前提寫死了，逐字：

  > **原文一旦上鏈就刪不掉——那會讓「刪除證明」變成一句謊。** 所以設計前提是：
  > 鏈上只有 commitment，原文與 nonce 住在鏈外……`assert_no_plaintext` 是這條
  > 前提的可執行防呆，不要繞過。

而 2026-09-21 批判者查到：`ops/exhibit/twin/twinstore.py` 把觀眾打的 `card` /
`card_text` **原文**寫進 append-only 鏈的 payload，`assert_no_plaintext` 在整個
`ops/exhibit/twin/` **`git grep` 零命中**。**防呆存在、規格存在、被繞過了。**
裁決 `decisions/DECISION_20260921_TWIN_CONSENT_AND_ERASURE.md` 第一條把它接回去，
本模組就是那條線。

```
  觀眾原文 ──┬─ sha256(canonical(原文) ‖ 0x1f ‖ nonce) ──▶ twinstore 鏈（append-only，永不刪）
             │                                       ＋ 簽章鏈 CONSENT_GRANT
             └─ 原文＋nonce ──▶ vault/plain/<slug>/   （鏈外，unlink() 刪得掉）

  撤回 ──▶ twinstore withdrawn 一列 ＋ 簽章鏈 CONSENT_WITHDRAW
       ──▶ **真的 unlink()**（nonce 一起刪，誠實邊界 4）
       ──▶ twinstore erased 一列 ＋ 簽章鏈 PERSONA_ERASED（帶被刪位元組的 sha256）
```

**這是接線不是研發。** 簽章、hash 串接、承諾值、三個 entry type、
`assert_no_plaintext` 全部來自 `vacant_network/consent.py` 與 `logbook.py`，
一個字沒改；`ops/exhibit/twin/make_consent_demo.py` 已經用合成捐贈者跑通同一條路。
本模組只加「檔案庫住哪裡」與「payload 長什麼樣」。

## 兩層防呆，為什麼需要兩層

1. `assert_sealed_shape()` —— **結構閘門**：payload 的 key 必須在白名單內、
   每個值必須符合型別與樣式（commitment ＝ 64 hex、ref ＝ `plain/<32hex>/…`）。
   「有人把 `card` 塞回 payload」這種事**零誤判**地擋在這裡。
2. `assert_payload_clean()` —— 呼叫**既有的** `consent.assert_no_plaintext`：
   原文與 nonce 的字串不准出現在 payload 的任何角落。它擋的是第 1 層擋不到的
   那一類：**有人在白名單裡新增一個欄位，然後把原文放進去。**

   ⚠ **為什麼 secrets 要篩過**（`secrets_for`）：`assert_no_plaintext` 是子字串
   比對，而 payload 骨架本身是 ASCII（`"sealed"`、`"plain/"`、`"needs"`…），
   commitment 是 64 個 hex 字元。如果把觀眾打的 `"e"`、`"ab"` 也當 secret，
   **每一張卡都會被自己的防呆擋掉**（`"ab"` 落在某個 commitment 裡的機率約兩成）。
   所以收錄規則是「長度 ≥ 8」**或**「含非 ASCII 字元」，再扣掉骨架字串。
   中文值（`"整理桌面"`）走第二條，一個字都不會漏。
   **殘餘講明白**：8 個字元以下的純 ASCII 原文值不進 secrets ⇒ 第 2 層看不到它，
   由第 1 層的結構閘門頂住。兩層都不是萬能，寫在這裡不是為了好看。

## 誠實邊界（改碼請保留，逐條都是規格的一部分）

1. **`vacant_network/consent.py` 的四條誠實邊界原封不動適用**，尤其第 1 條：
   鏈記的是「我們記下我們刪了，而且刪掉的位元組 sha256 是 X」，
   **不是「世上沒有副本」**。作業系統快取、備份、雲端郵箱那一份、
   觀眾自己手機上的截圖，都不在射程內。
2. **雲端郵箱（`vacant-world-cloud`）那一份原文，這支刪不到。** 那邊
   `app.delete` 零路由（2026-09-21 盤點）。所以 `withdraw()` 回傳的
   `cloud_copy` 永遠是 `"not_attempted_no_endpoint"`——**不是 `false`、
   更不是省略**。有了端點再改這裡。
3. **舊鏈裡的原文拿不掉。** 2026-09-21 之前寫進 `twinstore` 的
   `submitted`／`generated` payload 帶著原文，而那條鏈是 append-only。
   `migrate()` 能做的只有「把原文**另外**抄一份進檔案庫、讓之後的讀取走檔案庫」，
   **鏈上那一份永遠在**。所以舊主體撤回時，`erased` 事件會帶
   `residual_plaintext_seqs`——**新鏈開始才乾淨，舊的只能誠實標記**。
4. **跨程序互斥靠 `atomic.file_lock`，那在 Windows 上退化成 no-op**
   （`vacant_network/atomic.py` 自己寫明）。展場的 loop 與 serve 都跑在
   1003 上面那台 Linux VM，這條線成立；哪天搬到 Windows 原生跑，
   `serve --allow-withdraw` 與 `loop` 同時寫簽章鏈就沒有互斥了。
5. **模型生成的三句話是衍生物，不是觀眾的原話**，但它也搬進檔案庫了：
   撤回之後螢幕上不該還留著那個人的句子。`degrade_reason` 會夾帶模型原始回應
   （可能逐字複誦卡上的字），所以**它不上鏈**，只有 `degrade_kind` 上鏈。

用法：
    python3 ops/exhibit/twin/twinvault.py selftest              # 離線自檢＋負控制
    python3 ops/exhibit/twin/twinvault.py audit   --db …
    python3 ops/exhibit/twin/twinvault.py migrate --db …        # 舊鏈：抄一份進檔案庫
    python3 ops/exhibit/twin/twinvault.py withdraw --db … --id <sub_id>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import secrets as _secrets
import sys
from typing import Any, Iterable

HERE = pathlib.Path(__file__).resolve()
TWIN = HERE.parent
sys.path.insert(0, str(TWIN.parents[2]))

from ops.exhibit.twin.twinstore import (  # noqa: E402
    KIND_GENERATED, KIND_NOTE, KIND_SUBMITTED, SEAL_TAG,
)
from vacant_network import consent, crypto, logbook as _logbook  # noqa: E402
from vacant_network.atomic import atomic_write_bytes, file_lock  # noqa: E402
from vacant_network.canonical import canonical_bytes, canonical_str  # noqa: E402
from vacant_network.identity import Identity, PublicIdentity  # noqa: E402
from vacant_network.logbook import Logbook  # noqa: E402

#: payload 上的封印標記，**單一真相在 `twinstore.SEAL_TAG`**（它是鏈格式的一部分）。
__all_seal__ = SEAL_TAG
PAYLOAD_VERSION = 2

#: nonce 長度（bytes，`token_hex` 會給 2 倍字元數）。hiding 全靠它。
NONCE_BYTES = 32

#: 這一句會**原樣顯示給觀眾**（簽進 CONSENT_GRANT 的 scope）。
DEFAULT_SCOPE = (
    "展覽期間用你投的這張卡生成一位居民，在會場螢幕上演它的工作紀錄；"
    "你隨時可以撤回，撤回會把原文與 nonce 從檔案庫刪掉並把刪除證明簽上鏈。"
)

#: 卡上的欄位 → `consent.ALLOWED_FIELDS` 的類別。
#: ⚠ 這是**對映不是別名**：卡的欄位名（need/shape/…）不在 `ALLOWED_FIELDS` 裡，
#: 直接拿去餵 `consent.grant` 會被它的 `fields 越界` 擋下（那個擋門是對的）。
#: 對映關係寫在這裡當單一真相，不要在呼叫端各寫一份。
CARD_FIELD_CATEGORY: dict[str, str] = {
    "need": "needs",
    "first_line": "style",
    "shape": "style",
    "texture": "style",
    "color": "style",
    "vibe": "style",
}
#: 卡的原文（`card_text`）整段算「需求」那一類。
CARD_TEXT_CATEGORY = "needs"

#: 模型生成結果裡**准許上鏈**的欄位（全部是機器側的量測值，不是人講的話）。
#: 🔴 `arrival`／`working`／`handover`／`degrade_reason` **刻意不在裡面**。
TWIN_ON_CHAIN_KEYS: tuple[str, ...] = (
    "engine", "model", "endpoint", "latency_ms", "raw_len",
    "reasoning_tokens", "completion_tokens", "reasoning_chars",
    "max_tokens", "budget_escalated", "degraded_from", "degrade_kind",
)
#: 生成結果裡搬進檔案庫的欄位（觀眾看得到的句子＋可能夾帶原文的除錯字串）。
TWIN_OFF_CHAIN_KEYS: tuple[str, ...] = (
    "arrival", "working", "handover", "degrade_reason",
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_REF = re.compile(r"^plain/[0-9a-f]{32}/[a-z0-9_]+\.[a-z]+$")

#: secrets 收錄門檻，見檔頭「兩層防呆」。
MIN_ASCII_SECRET_LEN = 8


class VaultError(RuntimeError):
    """檔案庫／封印不合格。"""


#: 兩層防呆會丟的例外。呼叫端要**單獨**接（而且接在 `CARD_LEVEL_ERRORS` 前面：
#: `consent.ConsentError` 是 `ValueError` 的子類，順序寫反就被當成普通壞卡）。
#: ⚠ 接到之後**不要把例外訊息寫進事件流**——訊息可能含原文，而事件流也是鏈。
GUARD_ERRORS: tuple[type[BaseException], ...] = (VaultError, consent.ConsentError)


# ---------------------------------------------------------------------------
# 防呆層 1：結構閘門（零誤判）
# ---------------------------------------------------------------------------

_CARD_PAYLOAD_SPEC: dict[str, tuple[type, ...] | str] = {
    "v": (int,),
    "sealed": "seal_tag",
    "commitment": "hex64",
    "card_ref": "ref",
    "nonce_ref": "ref",
    "fields": "fields",
    "grant_hash": "hex64_or_none",
    "ts": "scalar",
    "cloud_status": "scalar",
}

_TWIN_PAYLOAD_SPEC: dict[str, tuple[type, ...] | str] = {
    "v": (int,),
    "sealed": "seal_tag",
    "commitment": "hex64",
    "twin_ref": "ref",
    "nonce_ref": "ref",
    **{k: "scalar" for k in TWIN_ON_CHAIN_KEYS},
}

SPECS = {"card": _CARD_PAYLOAD_SPEC, "twin": _TWIN_PAYLOAD_SPEC}

#: 每一種封印**一定要有**的欄位。少了就不是封印，是半成品。
REQUIRED = {
    "card": ("v", "sealed", "commitment", "card_ref", "nonce_ref"),
    "twin": ("v", "sealed", "commitment", "twin_ref", "nonce_ref"),
}

#: `scalar` 允許的字串長度上限。超過就是有人在夾帶。
MAX_SCALAR_CHARS = 200


def _check_scalar(key: str, val: Any) -> None:
    if val is None or isinstance(val, (int, float, bool)):
        return
    if isinstance(val, str):
        if len(val) > MAX_SCALAR_CHARS:
            raise VaultError(
                f"payload[{key!r}] 是 {len(val)} 字的字串（上限 {MAX_SCALAR_CHARS}）"
                "——這個長度只可能是有人把內容塞進中繼欄位")
        return
    raise VaultError(f"payload[{key!r}] 型別不合（{type(val).__name__}）："
                     "封印過的 payload 只准純量")


def assert_sealed_shape(payload: Any, what: str) -> None:
    """**結構閘門**：封印過的 payload 只准長這個樣子。

    `what` ∈ `"card"` / `"twin"`。這一層零誤判——它不看內容，只看形狀，
    所以「有人把 `card` 原文塞回 payload」一定擋得下（key 不在白名單）。
    """
    spec = SPECS.get(what)
    if spec is None:
        raise VaultError(f"未知的封印種類 {what!r}")
    if not isinstance(payload, dict):
        raise VaultError("封印過的 payload 必須是 dict")
    extra = sorted(set(payload) - set(spec))
    if extra:
        raise VaultError(
            f"封印過的 {what} payload 出現白名單外的欄位 {extra}；"
            f"只准 {sorted(spec)}——原文不准上鏈（consent.py 檔頭）")
    for key in REQUIRED[what]:
        if key not in payload:
            raise VaultError(f"封印過的 {what} payload 缺欄位 {key!r}")
    for key, rule in spec.items():
        if key not in payload:
            continue
        val = payload[key]
        if isinstance(rule, tuple):
            if not isinstance(val, rule) or isinstance(val, bool):
                raise VaultError(f"payload[{key!r}] 型別不合")
        elif rule == "seal_tag":
            if val != SEAL_TAG:
                raise VaultError(f"payload['sealed'] 必須是 {SEAL_TAG!r}")
        elif rule == "hex64":
            if not (isinstance(val, str) and _HEX64.match(val)):
                raise VaultError(f"payload[{key!r}] 必須是 64 字元小寫十六進位")
        elif rule == "hex64_or_none":
            if val is not None and not (isinstance(val, str) and _HEX64.match(val)):
                raise VaultError(f"payload[{key!r}] 必須是 64 hex 或 None")
        elif rule == "ref":
            if not (isinstance(val, str) and _REF.match(val)):
                raise VaultError(
                    f"payload[{key!r}] 不是合法的檔案庫參照（plain/<32hex>/<名字>）："
                    f"{val!r}——ref 是**名字**不是內容")
        elif rule == "fields":
            if not isinstance(val, list) or not all(
                    isinstance(x, str) and x in consent.ALLOWED_FIELDS for x in val):
                raise VaultError(
                    f"payload['fields'] 只准 {list(consent.ALLOWED_FIELDS)} 的子集")
        else:
            _check_scalar(key, val)


# ---------------------------------------------------------------------------
# 防呆層 2：呼叫既有的 consent.assert_no_plaintext
# ---------------------------------------------------------------------------

class _Entry:
    """`assert_no_plaintext` 只碰 `e.seq` / `e.type` / `e.payload`，就給它這三個。

    ⚠ 為什麼不複製一份 `assert_no_plaintext` 過來：**複製＝兩把尺**。
    那支是這條紅線的單一真相來源（形狀比照 `memory.assert_ks1_clean`），
    這裡要的是「產品路徑真的呼叫到它」，不是「產品路徑呼叫到一個長得像它的東西」。
    """

    __slots__ = ("seq", "type", "payload")

    def __init__(self, seq: int, etype: str, payload: Any) -> None:
        self.seq, self.type, self.payload = seq, etype, payload


class _Book:
    __slots__ = ("entries",)

    def __init__(self, entries: list[_Entry]) -> None:
        self.entries = entries


def _skeleton_blob() -> str:
    """payload 骨架（把每一個「會隨內容變」的值換成固定假值）的 canonical 字串。

    用途：從 secrets 裡扣掉「本來就會出現在骨架裡」的字串，避免誤判。
    """
    card = {"v": PAYLOAD_VERSION, "sealed": SEAL_TAG, "commitment": "0" * 64,
            "card_ref": "plain/" + "0" * 32 + "/card.json",
            "nonce_ref": "plain/" + "0" * 32 + "/nonce.hex",
            "fields": list(consent.ALLOWED_FIELDS), "grant_hash": "0" * 64,
            "ts": 0, "cloud_status": ""}
    twin = {"v": PAYLOAD_VERSION, "sealed": SEAL_TAG, "commitment": "0" * 64,
            "twin_ref": "plain/" + "0" * 32 + "/twin.json",
            "nonce_ref": "plain/" + "0" * 32 + "/nonce.hex",
            **{k: "" for k in TWIN_ON_CHAIN_KEYS}}
    return canonical_str(card) + canonical_str(twin)


def _strings_in(obj: Any, out: list[str]) -> None:
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _strings_in(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _strings_in(v, out)


def secrets_for(*plain_objects: Any) -> list[str]:
    """哪些字串算「不准上鏈的祕密」。收錄規則與殘餘見檔頭「兩層防呆」。"""
    raw: list[str] = []
    for obj in plain_objects:
        _strings_in(obj, raw)
    skeleton = _skeleton_blob()
    keep: list[str] = []
    for s in raw:
        if not s:
            continue
        if len(s) < MIN_ASCII_SECRET_LEN and s.isascii():
            continue          # 太短的純 ASCII：會誤中骨架／commitment，交給第 1 層
        if s in skeleton:
            continue          # 本來就在骨架裡的字（"needs"、"plain/"…）
        keep.append(s)
    return sorted(set(keep))


def assert_payload_clean(payload: Any, secrets: Iterable[str], *,
                         kind: str = "sealed", seq: int = 0) -> None:
    """**在寫入之前**跑 `consent.assert_no_plaintext`。鏈是 append-only，事後掃來不及。"""
    consent.assert_no_plaintext(_Book([_Entry(seq, kind, payload)]), list(secrets))


def append_sealed(store: Any, kind: str, sub_id: str, payload: dict[str, Any],
                  secrets: Iterable[str], source: str, *,
                  what: str) -> dict[str, Any]:
    """唯一一條把封印過的 payload 寫進 `twinstore` 的路：**先過兩層防呆再 append**。

    ⚠ 不要在別處直接 `store.append(KIND_SUBMITTED, …)` ——那就是 2026-09-21
    被抓到的那個繞過。`tests/test_twinvault.py` 有一條測試守著產品路徑真的
    走這裡（不是「函式存在」，是「ingest 呼叫得到」）。
    """
    assert_sealed_shape(payload, what)
    assert_payload_clean(payload, secrets, kind=kind)
    return store.append(kind, sub_id, payload, source=source)


# ---------------------------------------------------------------------------
# 檔案庫本體
# ---------------------------------------------------------------------------

def slug_for(sub_id: str) -> str:
    """檔案庫目錄名 ＝ `sha256(sub_id)` 前 32 字。

    ⚠ **不是美觀問題，是路徑穿越**：`sub_id` 來自公網（雲端郵箱），
    直接拿去當目錄名，`"../../etc"` 就把檔案庫寫到別的地方去了。
    """
    return hashlib.sha256(sub_id.encode("utf-8")).hexdigest()[:32]


class TwinVault:
    """鏈外檔案庫 ＋ 簽章同意鏈。**只有這裡的東西刪得掉。**"""

    def __init__(self, root: pathlib.Path | str, *, scope: str = DEFAULT_SCOPE) -> None:
        self.root = pathlib.Path(root)
        self.scope = scope
        # 簽章鏈的記憶體快取，見 `_load_book()`。**用 (size, mtime_ns) 當指紋**，
        # 所以別的行程寫過之後這裡一定會重讀——不是「相信自己是唯一的寫者」。
        self._cache: tuple[int, int, Logbook] | None = None
        self._ident: Identity | None = None

    # -- 路徑（讀路徑一律不建目錄：唯讀端點必須真的唯讀） --------------------

    @property
    def plain_dir(self) -> pathlib.Path:
        return self.root / "plain"

    @property
    def consent_dir(self) -> pathlib.Path:
        return self.root / "consent"

    @property
    def chain_path(self) -> pathlib.Path:
        return self.consent_dir / "chain.ndjson"

    @property
    def pub_path(self) -> pathlib.Path:
        return self.consent_dir / "chain.pub.json"

    @property
    def key_dir(self) -> pathlib.Path:
        return self.consent_dir / "key"

    @property
    def lock_path(self) -> pathlib.Path:
        return self.consent_dir / "chain.lock"

    def exists(self) -> bool:
        return self.root.exists()

    def _sub_dir(self, sub_id: str) -> pathlib.Path:
        return self.plain_dir / slug_for(sub_id)

    def ref(self, sub_id: str, name: str) -> str:
        return f"plain/{slug_for(sub_id)}/{name}"

    def path_of(self, ref: str) -> pathlib.Path:
        if not _REF.match(ref):
            raise VaultError(f"不合法的 ref：{ref!r}")
        return self.root / ref

    # -- 身分（簽同意鏈的那把鑰匙） ------------------------------------------

    def identity(self) -> Identity:
        """展場這一台的簽章身分。第一次呼叫時生成並落盤（0600）。

        ⚠ 私鑰在 `consent/key/identity.key`。`RECORD_SPEC §7` 要求 pack 排除
        `identity.key`，歸檔時不要把它打包出去。
        """
        if self._ident is not None:
            return self._ident
        if (self.key_dir / "identity.key").exists():
            ident = Identity.load(self.key_dir)
        else:
            ident = Identity.generate()
            ident.save(self.key_dir)
        if not self.pub_path.exists():
            # 公鑰檔掉了（或是舊版留下的私鑰）⇒ 補回去。
            # 少了它 `public_identity()` 回 None，整條簽章鏈就**驗不了也簽不下去**，
            # 而那會安靜地退化成「撤回沒有簽章證明」。
            atomic_write_bytes(self.pub_path, json.dumps(
                {"vacant_id": ident.vacant_id,
                 "pub_hex": crypto.pub_to_hex(ident.pub)},
                ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n")
        self._ident = ident
        return ident

    def public_identity(self) -> PublicIdentity | None:
        if not self.pub_path.exists():
            return None
        meta = json.loads(self.pub_path.read_text(encoding="utf-8"))
        return PublicIdentity.from_hex(meta["vacant_id"], meta["pub_hex"])

    def book(self) -> Logbook:
        """讀回簽章鏈。**O(1) 的常見情況**：檔案沒被動過就用快取那一份。

        ⚠ 為什麼需要這個：`Logbook.load` ＋ `Logbook.save` 都是整檔 O(N)，
        而 ingest 是一張卡簽一筆 ⇒ 整場下來 O(N²)。實測（Mac，2026-09-21）
        200 張卡時每張要 **395 ms**、撤回一次 **2.0 秒**——展場是秒級互動，
        那個數字直接違反 `CLAUDE.md` 展場硬約束 1。

        ⚠ **快取不可以假設「只有我在寫」**：`serve --allow-withdraw` 與 `loop`
        是兩個行程。指紋用 `(size, mtime_ns)`，別人寫過就重讀。
        """
        try:
            st = self.chain_path.stat()
        except FileNotFoundError:
            self._cache = None
            return Logbook()
        if self._cache is not None:
            size, mtime, book = self._cache
            if size == st.st_size and mtime == st.st_mtime_ns:
                return book
        book = Logbook.load(self.chain_path)
        self._cache = (st.st_size, st.st_mtime_ns, book)
        return book

    def _append_new(self, book: Logbook, n0: int) -> None:
        """把 `book.entries[n0:]` **附加**到 ndjson 尾巴，不整檔重寫。

        ⚠ 這不是 `atomic_write_bytes` 的原子性——它換來的是 O(1)。
        射程講清楚：
        · 一次 `write()` 寫完整的幾行再 `fsync`，同一台機器上不會交錯
          （寫者之間有 `file_lock` 序列化）；
        · **當機當在 write 中間，尾巴可能是半行。** 那時 `Logbook.load`
          會在那一行 `json.loads` 炸掉——**吵，不是安靜壞掉**，這是刻意的。
          真相來源是 `twinstore` 那個 SQLite（`synchronous=FULL`），
          簽章鏈是它的**附加**證明，不是它的替代品。
        """
        new = book.entries[n0:]
        if not new:
            return
        blob = b"".join(canonical_bytes(e.to_json()) + b"\n" for e in new)
        self.chain_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.chain_path, "ab") as f:
            f.write(blob)
            f.flush()
            os.fsync(f.fileno())
        st = self.chain_path.stat()
        self._cache = (st.st_size, st.st_mtime_ns, book)

    # -- 封印（寫） -----------------------------------------------------------

    def _nonce(self, sub_id: str, *, create: bool) -> str | None:
        p = self._sub_dir(sub_id) / "nonce.hex"
        if p.exists():
            return p.read_text(encoding="ascii").strip()
        if not create:
            return None
        n = _secrets.token_hex(NONCE_BYTES)
        p.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(p, n.encode("ascii"))
        return n

    def seal_card(self, sub_id: str, card: Any, card_text: Any, *,
                  ts: Any = None, cloud_status: Any = None,
                  ts_ms: int | None = None,
                  sign: bool = True) -> tuple[dict[str, Any], list[str]]:
        """把原文寫進檔案庫、簽一筆 `CONSENT_GRANT`，回傳**可以上鏈的 payload**。

        回 `(payload, secrets)`：`secrets` 要餵給 `append_sealed`，
        它就是「這一張卡上不准出現在鏈上的字串」。
        """
        plain = {"card": card, "card_text": card_text}
        nonce = self._nonce(sub_id, create=True)
        assert nonce is not None
        commit = _logbook.review_commitment(plain, nonce)
        atomic_write_bytes(self._sub_dir(sub_id) / "card.json", canonical_bytes(plain))

        cats = set()
        if isinstance(card, dict):
            for k in card:
                if card.get(k) and k in CARD_FIELD_CATEGORY:
                    cats.add(CARD_FIELD_CATEGORY[k])
        if card_text:
            cats.add(CARD_TEXT_CATEGORY)

        grant_hash: str | None = None
        if sign:
            with file_lock(self.lock_path):
                book = self.book()
                n0 = len(book)
                ident = self.identity()
                g = consent.grant(
                    book, ident, subject_ref=sub_id, commitment=commit,
                    fields=sorted(cats), scope=self.scope,
                    ts_ms=int(ts_ms if ts_ms is not None else _now_ms()),
                    nonce_ref=self.ref(sub_id, "nonce.hex"))
                self._append_new(book, n0)
                grant_hash = g.hash()

        payload = {
            "v": PAYLOAD_VERSION,
            "sealed": SEAL_TAG,
            "commitment": commit,
            "card_ref": self.ref(sub_id, "card.json"),
            "nonce_ref": self.ref(sub_id, "nonce.hex"),
            "fields": sorted(cats),
            "grant_hash": grant_hash,
            "ts": ts if isinstance(ts, (int, float)) or ts is None else str(ts)[:64],
            "cloud_status": (cloud_status if cloud_status is None
                             else str(cloud_status)[:64]),
        }
        return payload, secrets_for(plain, nonce)

    def seal_twin(self, sub_id: str, twin: dict[str, Any]
                  ) -> tuple[dict[str, Any], list[str]]:
        """把模型生成的三句話搬進檔案庫，鏈上只留量測欄位＋commitment。"""
        plain = {k: twin.get(k) for k in TWIN_OFF_CHAIN_KEYS if twin.get(k) is not None}
        nonce = self._nonce(sub_id, create=True)
        assert nonce is not None
        commit = _logbook.review_commitment(plain, nonce)
        atomic_write_bytes(self._sub_dir(sub_id) / "twin.json", canonical_bytes(plain))
        payload: dict[str, Any] = {
            "v": PAYLOAD_VERSION, "sealed": SEAL_TAG, "commitment": commit,
            "twin_ref": self.ref(sub_id, "twin.json"),
            "nonce_ref": self.ref(sub_id, "nonce.hex"),
        }
        for k in TWIN_ON_CHAIN_KEYS:
            if k in twin:
                v = twin[k]
                payload[k] = v if not isinstance(v, str) else v[:MAX_SCALAR_CHARS]
        return payload, secrets_for(plain, nonce)

    # -- 開封（讀） -----------------------------------------------------------

    def open_card(self, sub_id: str) -> dict[str, Any] | None:
        return self._read(self._sub_dir(sub_id) / "card.json")

    def open_twin(self, sub_id: str) -> dict[str, Any] | None:
        return self._read(self._sub_dir(sub_id) / "twin.json")

    @staticmethod
    def _read(p: pathlib.Path) -> dict[str, Any] | None:
        if not p.exists():
            return None
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return obj if isinstance(obj, dict) else None

    def commitment_ok(self, sub_id: str, commitment: str, *,
                      what: str = "card") -> bool | None:
        """檔案庫那一份真的算得出鏈上那個 commitment 嗎？

        ⚠ **三態**：nonce 或原文已經不在 ⇒ 回 `None`（沒得算），**不是 `False`**。
        「刪掉了所以驗不了」跟「留著但對不上」是兩件事。
        """
        nonce = self._nonce(sub_id, create=False)
        plain = self.open_card(sub_id) if what == "card" else self.open_twin(sub_id)
        if nonce is None or plain is None:
            return None
        return _logbook.review_commitment(plain, nonce) == commitment

    # -- 撤回 → 真的刪 → 簽 PERSONA_ERASED ------------------------------------

    def state(self, sub_id: str) -> str:
        """`none` / `granted` / `withdrawn` / `erased`（讀簽章鏈算出來的）。"""
        who = self.public_identity()
        if who is None or not self.chain_path.exists():
            return "none"
        st = consent.audit(self.book(), who)["subjects"].get(sub_id)
        return st.state if st else "none"

    def withdraw(self, sub_id: str, *, reason: str = "subject_request",
                 ts_ms: int | None = None) -> dict[str, Any]:
        """撤回 → 上鏈 → 原文 `unlink()` → `PERSONA_ERASED`。**冪等。**

        回一份紀錄；`signed` 說明簽章鏈那一半有沒有成立（舊主體沒有 grant 就沒有）。
        """
        t = int(ts_ms if ts_ms is not None else _now_ms())
        out: dict[str, Any] = {
            "sub_id": sub_id, "at_ms": t, "reason": reason,
            "signed": False, "already": False, "erased": [],
            # 誠實邊界 2：雲端那一份刪不到，寫清楚而不是省略。
            "cloud_copy": "not_attempted_no_endpoint",
            "problems": [],
        }
        with file_lock(self.lock_path):
            who = self.public_identity()
            book = self.book()
            n0 = len(book)
            cur = None
            if who is not None and len(book):
                cur = consent.audit(book, who)["subjects"].get(sub_id)
            if cur is not None and cur.state == "erased":
                out["already"] = True
                out["signed"] = True
                out["erased"] = list(cur.erased_refs)
                return out

            # 1) 撤回宣告（有 grant 才簽得出來——沒有就誠實留白，不偽造一筆）
            w_hash: str | None = None
            if cur is not None and cur.grant_hash:
                ident = self.identity()
                if cur.state == "granted":
                    w_hash = consent.withdraw(
                        book, ident, subject_ref=sub_id,
                        grant_hash=cur.grant_hash, ts_ms=t, reason=reason).hash()
                elif cur.withdraw_seq is not None:
                    # 🔴 **「撤回了但還沒刪」是可以重試的。**
                    #    那個狀態（`SubjectStatus.unfulfilled`）正是這條鏈存在的
                    #    全部理由（`consent.py` 誠實邊界 2）。上一次做到一半的話，
                    #    這裡**沿用那一筆撤回**把刪除補完——不要再宣告一次撤回
                    #    （帳本會多一筆沒有意義的重複），也不要因此永遠簽不出
                    #    `PERSONA_ERASED`（那等於「宣告了但沒做」變成死結）。
                    prev = next((x for x in book.entries
                                 if x.seq == cur.withdraw_seq), None)
                    if prev is None:
                        out["problems"].append(
                            f"稽核說 seq {cur.withdraw_seq} 有一筆撤回，"
                            "但鏈上找不到它——不補刪除證明")
                    else:
                        w_hash = prev.hash()
                out["withdraw_hash"] = w_hash
            else:
                out["problems"].append(
                    "簽章鏈上沒有這位主體的 CONSENT_GRANT（舊鏈時代進來的）："
                    "撤回照樣執行、原文照樣刪，但簽不出 PERSONA_ERASED")

            # 2) **真的刪**。nonce 先刪：它是 hiding 的全部（誠實邊界 4）。
            erased: list[dict[str, Any]] = []
            for name in ("nonce.hex", "card.json", "twin.json"):
                p = self._sub_dir(sub_id) / name
                if not p.exists():
                    continue
                data = p.read_bytes()
                erased.append({"ref": self.ref(sub_id, name),
                               "sha256": hashlib.sha256(data).hexdigest(),
                               "bytes_n": len(data)})
                p.unlink()
                if p.exists():                      # 正控制：真的不在了才往下走
                    raise VaultError(f"{p} 沒有真的被刪掉")
            d = self._sub_dir(sub_id)
            if d.exists() and not any(d.iterdir()):
                d.rmdir()
            out["erased"] = erased

            # 3) 刪除證明上鏈（要有撤回那一筆才簽得出來）
            nonce_ref = self.ref(sub_id, "nonce.hex")
            if w_hash is not None and erased:
                try:
                    e = consent.erase(book, self.identity(), subject_ref=sub_id,
                                      withdraw_hash=w_hash, erased=erased,
                                      nonce_ref=nonce_ref, ts_ms=t + 1)
                    out["erase_hash"] = e.hash()
                    out["signed"] = True
                except consent.ConsentError as exc:
                    # 最常見：nonce 早就不在了 ⇒ 簽不出合格的刪除證明。
                    # **不要湊一個假的**，記下來。
                    out["problems"].append(f"PERSONA_ERASED 簽不出來：{exc}")
            elif w_hash is not None:
                out["problems"].append(
                    "檔案庫裡沒有這位主體的原文（可能已經刪過、或從來沒封印過）："
                    "撤回上鏈了，但沒有被刪物可以證明")
            self._append_new(book, n0)
        return out

    # -- 稽核 -----------------------------------------------------------------

    def audit(self) -> dict[str, Any]:
        who = self.public_identity()
        if who is None:
            return {"chain_ok": None, "subjects": {}, "problems": ["還沒有簽章鏈"],
                    "n_entries": 0}
        book = self.book()
        a = consent.audit(book, who)
        return {
            "chain_ok": a["chain_ok"],
            "stream_id": a["stream_id"],
            "head": a["head"],
            "n_entries": len(book),
            "problems": a["problems"],
            "subjects": {k: {"state": v.state, "fields": list(v.fields),
                             "erased_refs": list(v.erased_refs),
                             "unfulfilled": v.unfulfilled}
                         for k, v in a["subjects"].items()},
        }


def _now_ms() -> int:
    from datetime import datetime, timezone
    return int(datetime.now(timezone.utc).timestamp() * 1000)


# ---------------------------------------------------------------------------
# 舊鏈遷移：**原文拿不掉，只能抄一份出來＋誠實標記**
# ---------------------------------------------------------------------------

def legacy_plaintext_seqs(store: Any, sub_id: str) -> list[int]:
    """這位主體有哪幾列 payload 裡帶著原文（＝2026-09-21 之前寫進去的）。"""
    out = []
    for e in store.events(sub_id=sub_id):
        p = e.get("payload")
        if not isinstance(p, dict) or p.get("sealed") == SEAL_TAG:
            continue
        if e["kind"] == KIND_SUBMITTED and (
                p.get("card") is not None or p.get("card_text") is not None):
            out.append(e["seq"])
        elif e["kind"] == KIND_GENERATED and any(
                p.get(k) for k in ("arrival", "working", "handover")):
            out.append(e["seq"])
    return out


def migrate(store: Any, *, sign: bool = True) -> dict[str, Any]:
    """舊鏈 → 檔案庫。**不刪任何東西、不改任何一列。**

    做的只有兩件事：
    1. 把舊列裡的原文**另外抄一份**進檔案庫（於是那位主體從此撤回得了，
       而且之後的讀取走檔案庫）；
    2. 追加一列 `note`，把「這幾個 seq 的鏈上原文永遠拿不掉」記下來。

    ⚠ **這不是「清乾淨」。** 鏈上那一份還在，`withdraw()` 之後
    `residual_plaintext_seqs` 會一路帶著它。新鏈開始才乾淨。
    """
    vault: TwinVault = store.vault
    moved, already, residual = 0, 0, {}
    for sid in store.sub_ids():
        seqs = legacy_plaintext_seqs(store, sid)
        if not seqs:
            continue
        residual[sid] = seqs
        if vault.open_card(sid) is not None:
            already += 1
            continue
        cur = store.current(sid) or {}
        vault.seal_card(sid, cur.get("card"), cur.get("card_text"), sign=sign)
        twin = cur.get("twin")
        if isinstance(twin, dict) and any(twin.get(k) for k in TWIN_OFF_CHAIN_KEYS):
            vault.seal_twin(sid, twin)
        moved += 1
    rec = {
        "v": 1,
        "what": "legacy_plaintext_migration",
        "moved": moved, "already": already,
        "subjects_with_chain_plaintext": len(residual),
        "honesty": "鏈上那幾列的原文拿不掉（append-only）。這次只抄了一份到鏈外，"
                   "讓這些主體撤回得了；撤回後鏈上那一份仍然在。",
    }
    store.append(KIND_NOTE, "_vault", rec, source="twinvault:migrate")
    rec["residual_plaintext_seqs"] = residual
    return rec


# ---------------------------------------------------------------------------
# selftest（含負控制）
# ---------------------------------------------------------------------------

def selftest() -> int:  # noqa: C901
    import tempfile

    fails: list[str] = []

    def chk(name: str, cond: bool, extra: str = "") -> None:
        print(("  [OK] " if cond else "  [紅] ") + name + (f" — {extra}" if extra else ""))
        if not cond:
            fails.append(name)

    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td) / "v"
        vault = TwinVault(root)
        card = {"need": "整理桌面", "shape": "圓潤"}
        text = "我想要有人幫我整理桌面"

        print("1. 封印：原文進檔案庫、payload 只有 commitment")
        payload, secs = vault.seal_card("sub-1", card, text, ts=1, cloud_status="queued")
        blob = canonical_str(payload)
        chk("payload 不含原文", "整理桌面" not in blob)
        chk("payload 有 commitment", bool(_HEX64.match(payload["commitment"])))
        chk("原文真的落在鏈外", (root / "plain" / slug_for("sub-1") / "card.json").exists())
        chk("commitment 算得回來", vault.commitment_ok("sub-1", payload["commitment"]) is True)

        print("2. 負控制：把原文塞回 payload，兩層防呆都要炸")
        try:
            assert_sealed_shape({**payload, "card": card}, "card")
            chk("結構閘門擋下多出來的 card 欄位", False, "竟然沒炸")
        except VaultError:
            chk("結構閘門擋下多出來的 card 欄位", True)
        try:
            assert_payload_clean({**payload, "cloud_status": "整理桌面"}, secs)
            chk("assert_no_plaintext 擋下夾帶在白名單欄位裡的原文", False, "竟然沒炸")
        except consent.ConsentError:
            chk("assert_no_plaintext 擋下夾帶在白名單欄位裡的原文", True)
        nonce_secret = next(x for x in secs if _HEX64.match(x))
        try:
            assert_payload_clean({**payload, "cloud_status": nonce_secret}, secs)
            chk("assert_no_plaintext 擋下夾帶的 nonce", False, "竟然沒炸")
        except consent.ConsentError:
            chk("assert_no_plaintext 擋下夾帶的 nonce", True)

        print("3. 正控制：乾淨的 payload 要過")
        try:
            assert_sealed_shape(payload, "card")
            assert_payload_clean(payload, secs)
            chk("乾淨 payload 兩層都過", True)
        except Exception as exc:  # noqa: BLE001
            chk("乾淨 payload 兩層都過", False, f"{type(exc).__name__}: {exc}")

        print("4. 撤回 → 真的 unlink → PERSONA_ERASED")
        twin = {"arrival": "嗨", "working": "在做", "handover": "好了",
                "engine": "fallback_deterministic"}
        vault.seal_twin("sub-1", twin)
        chk("撤回前狀態 granted", vault.state("sub-1") == "granted", vault.state("sub-1"))
        rec = vault.withdraw("sub-1")
        chk("簽出了 PERSONA_ERASED", rec["signed"] is True, str(rec["problems"]))
        chk("三個檔都列進被刪清單", len(rec["erased"]) == 3, str(len(rec["erased"])))
        chk("nonce 在被刪清單裡",
            any(r["ref"].endswith("nonce.hex") for r in rec["erased"]))
        chk("原文真的不在了", vault.open_card("sub-1") is None)
        chk("狀態變 erased", vault.state("sub-1") == "erased", vault.state("sub-1"))
        chk("驗不了就回 None 不回 False",
            vault.commitment_ok("sub-1", payload["commitment"]) is None)
        chk("雲端那一份講清楚沒動",
            rec["cloud_copy"] == "not_attempted_no_endpoint")
        chk("重複撤回是冪等的", vault.withdraw("sub-1")["already"] is True)

        print("5. 簽章鏈自己驗得過，而且鏈上一個原文都沒有")
        a = vault.audit()
        chk("chain_ok", a["chain_ok"] is True)
        chk("稽核無 problem", not a["problems"], str(a["problems"]))
        try:
            consent.assert_no_plaintext(vault.book(), secs)
            chk("整條簽章鏈也不含原文／nonce", True)
        except consent.ConsentError as exc:
            chk("整條簽章鏈也不含原文／nonce", False, str(exc)[:80])

        print("6. 負控制：路徑穿越的 sub_id 不可以跑出檔案庫")
        evil = "../../../../etc/passwd"
        p, _ = vault.seal_card(evil, {"need": "x"}, None, sign=False)
        chk("ref 仍然是 plain/<32hex>/…", bool(_REF.match(p["card_ref"])), p["card_ref"])
        chk("檔案落在 plain/ 底下",
            (root / "plain") in vault.path_of(p["card_ref"]).parents)

    print()
    if fails:
        print(f"selftest 紅：{len(fails)} 項失敗 → {fails}")
        return 1
    print("selftest 全綠（含 5 個負控制）")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _p(o: Any) -> None:
    print(json.dumps(o, ensure_ascii=False, indent=2, default=str))


def main(argv: Iterable[str] | None = None) -> int:
    from ops.exhibit.twin.twinstore import DEFAULT_DB, TwinStore

    ap = argparse.ArgumentParser(
        description="twinvault — 原文鏈外、commitment 上鏈、撤回可驗")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    s = ap.add_subparsers(dest="cmd", required=True)
    s.add_parser("selftest", help="離線自檢＋負控制")
    s.add_parser("audit", help="簽章同意鏈的狀態")
    m = s.add_parser("migrate", help="舊鏈的原文抄一份進檔案庫（不刪任何東西）")
    m.add_argument("--no-sign", action="store_true")
    w = s.add_parser("withdraw", help="撤回 → 上鏈 → unlink → PERSONA_ERASED")
    w.add_argument("--id", required=True)
    w.add_argument("--reason", default="subject_request")

    a = ap.parse_args(list(argv) if argv is not None else None)
    if a.cmd == "selftest":
        return selftest()

    st = TwinStore(a.db)
    try:
        if a.cmd == "audit":
            _p({"db": str(st.path), "vault": str(st.vault.root), **st.vault.audit()})
            return 0
        if a.cmd == "migrate":
            _p(migrate(st, sign=not a.no_sign))
            return 0
        if a.cmd == "withdraw":
            from ops.exhibit.twin import twinlink
            _p(twinlink.withdraw(st, a.id, reason=a.reason, source="cli"))
            return 0
    finally:
        st.close()
    return 2


if __name__ == "__main__":
    sys.exit(main())
