"""consent — 同意／撤回／刪除證明，**完全長在既有的 logbook 上**。

## 這支在架構裡承重什麼

展覽用真人資料生成分身（CLAUDE.md §硬約束 6；SPEC_v3 §四）。Hollanek 2024 的
要求是「捐贈者同意不夠，互動者也必須能同意」，而 SPEC_v3 §四把第 5 項施工
（退場與撤回上鏈）寫成：

  > 撤回本身上鏈、可驗證——那比「場後即刪」更能展示 Vacant，
  > 因為它展示的是帳本處理一個持續中的義務。

本模組就是那一項的機制面。**它沒有發明任何新機制**：

  · 簽章、hash 串接、驗鏈 ── `vacant/logbook.py`（一個字沒動）
  · 承諾值 ──────────────── `logbook.review_commitment`（同一個原語）
  · 存檔點與回溯稽核 ────── `vacant/checkpoint.py`（同一套）

本模組只加三件事：三個 entry `type` 字串、一個只准四類欄位的閘門、
一個「原文不准上鏈」的可執行防呆。

## 為什麼原文絕對不能上鏈

鏈是 append-only。**原文一旦上鏈就刪不掉**——那會讓「刪除證明」變成一句謊。
所以設計前提是：鏈上只有 commitment，原文與 nonce 住在鏈外，刪除＝把那兩樣
刪掉，再把「刪了什麼（by hash）」簽上鏈。`assert_no_plaintext` 是這條前提的
可執行防呆（形狀比照 `memory.assert_ks1_clean`），不要繞過。

## 誠實邊界（改碼請保留，逐條都是規格的一部分）

1. **鏈證明的是「我們記下我們刪了，而且刪掉的位元組 hash 是 X」，不是
   「世上沒有副本」。** 備份、作業系統快取、觀眾自己手機上的截圖都不在射程內。
   本模組提高的是「悄悄不刪」被發現的機率，不是刪除本身的確定性
   （raises-cost，不是 prevents）。
2. **撤回上鏈 ≠ 撤回被執行。** 鏈讓「撤回了但沒刪」變成看得見的狀態
   （`audit()` 的 `unfulfilled`），這是它的全部價值。
3. **commitment 的 hiding 全靠 nonce，不是靠雜湊。** persona 只有四類欄位、
   每類從一張小清單裡挑 1–3 個，可能取值大約 2×10⁸ 量級——**沒有 nonce 的
   承諾等於明文**，窮舉幾分鐘就還原。由此推出第 4 條。
4. **刪除必須連 nonce 一起刪。** 留著 nonce 而只刪原文，任何人都可以拿鏈上的
   commitment 去窮舉那 2×10⁸ 個 persona，一個一個比對——原文等於沒刪。
   `erase()` 因此要求把 nonce 當成被刪物之一列進 `erased`，少列就報錯。
5. 本模組只處理**捐贈者**那一半。互動者（在旁邊看的人）的同意是場地與流程
   問題，程式碼給不出來，不要讀成「同意問題已解」。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from . import logbook as _logbook
from .identity import Identity, PublicIdentity
from .logbook import LogEntry, Logbook

#: 三個 entry type。它們是 wire 常數，改動＝破壞既有鏈的可讀性。
GRANT_TYPE = "CONSENT_GRANT"
WITHDRAW_TYPE = "CONSENT_WITHDRAW"
ERASED_TYPE = "PERSONA_ERASED"

CONSENT_VERSION = 1

#: SPEC_v3 §四-1 允許萃取的四類，不多不少。名稱就是 `world/js/persona.js` 那四個。
ALLOWED_FIELDS: tuple[str, ...] = ("domains", "topics", "style", "needs")

#: SPEC_v3 §四-3 明文禁止的敏感推論。出現在 persona 的 key 上就擋。
FORBIDDEN_FIELDS: tuple[str, ...] = (
    "politics", "political", "health", "medical", "sexuality", "orientation",
    "religion", "religious", "finance", "financial", "income",
    "name", "address", "employer", "family", "phone", "email",
)

#: nonce 最低長度。承諾的 hiding 全靠它（誠實邊界 3），沿用 logbook 的門檻。
MIN_NONCE_BYTES = _logbook.MIN_NONCE_BYTES


class ConsentError(ValueError):
    """同意紀錄不合格（欄位越界、原文外洩、nonce 沒被刪…）。"""


# --- persona 閘門 -----------------------------------------------------------

def check_persona(persona: dict[str, Any]) -> None:
    """只准四類欄位、每一個值都是字串清單；越界直接擋，不做靜默過濾。

    為什麼不靜默過濾：靜默過濾會讓呼叫端以為自己傳的東西進去了。
    這裡寧可讓上游炸掉，也不要讓「政治傾向被丟掉了」變成一件沒人知道的事。
    """
    if not isinstance(persona, dict):
        raise ConsentError("persona 必須是 dict")
    extra = [k for k in persona if k not in ALLOWED_FIELDS]
    if extra:
        raise ConsentError(
            f"persona 出現允許清單以外的欄位 {extra!r}；"
            f"只准 {list(ALLOWED_FIELDS)}（SPEC_v3 §四-1）"
        )
    low = {k.lower() for k in persona}
    bad = sorted(low & set(FORBIDDEN_FIELDS))
    if bad:
        raise ConsentError(f"persona 出現敏感欄位 {bad!r}（SPEC_v3 §四-3）")
    for k, v in persona.items():
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            raise ConsentError(f"persona[{k!r}] 必須是字串清單")


def persona_commitment(persona: dict[str, Any], nonce: str) -> str:
    """persona 的承諾值 —— 直接呼叫 `logbook.review_commitment`，不另造一套。

    同一個構造：sha256(canonical(persona) ‖ 0x1f ‖ nonce)。用同一支的理由不是
    省事，是**展件上那一頁只想實作一次**：頁內 JS 已經為了收據鏈重寫過一次
    canonical 佈局，再多一種承諾構造就多一個會漂掉的地方。

    ⚠ 誠實邊界 3／4 在這裡生效：nonce 是 hiding 的唯一來源，刪除時必須連它一起刪。
    """
    check_persona(persona)
    return _logbook.review_commitment(persona, nonce)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- 上鏈 -------------------------------------------------------------------

def grant(
    book: Logbook, identity: Identity, *,
    subject_ref: str, commitment: str, fields: list[str], scope: str,
    ts_ms: int, nonce_ref: str,
) -> LogEntry:
    """捐贈者同意：把「同意了什麼」簽上鏈。**原文與 nonce 都不進 payload。**

    `subject_ref`  展場發給捐贈者的代號（不是姓名、不是任何可回推的識別碼）。
    `commitment`   `persona_commitment()` 的輸出。
    `fields`       實際萃取了哪幾類（ALLOWED_FIELDS 的子集）。
    `scope`        同意做什麼用（一句話，會原樣顯示給觀眾）。
    `nonce_ref`    nonce 存放位置的**名字**（例如檔名），不是 nonce 本身。
                   刪除時要用它證明 nonce 也被刪了（誠實邊界 4）。
    """
    unknown = [f for f in fields if f not in ALLOWED_FIELDS]
    if unknown:
        raise ConsentError(f"fields 越界：{unknown!r}")
    if len(commitment) != 64 or any(c not in "0123456789abcdef" for c in commitment):
        raise ConsentError("commitment 必須是 64 字元小寫十六進位")
    return book.append(GRANT_TYPE, {
        "v": CONSENT_VERSION,
        "subject_ref": subject_ref,
        "commitment": commitment,
        "fields": sorted(fields),
        "scope": scope,
        "nonce_ref": nonce_ref,
    }, identity, ts_ms=ts_ms)


def withdraw(
    book: Logbook, identity: Identity, *,
    subject_ref: str, grant_hash: str, ts_ms: int, reason: str = "subject_request",
) -> LogEntry:
    """捐贈者撤回同意。`grant_hash` ＝ 被撤回的那一筆 grant 的 `entry.hash()`。

    撤回**只是宣告**，刪除是下一筆。兩筆分開是刻意的：合成一筆就看不見
    「宣告了但沒做」這個狀態，而那正是唯一值得上鏈的東西（誠實邊界 2）。
    """
    return book.append(WITHDRAW_TYPE, {
        "v": CONSENT_VERSION,
        "subject_ref": subject_ref,
        "grant_hash": grant_hash,
        "reason": reason,
    }, identity, ts_ms=ts_ms)


def erase(
    book: Logbook, identity: Identity, *,
    subject_ref: str, withdraw_hash: str, erased: list[dict[str, Any]],
    nonce_ref: str, ts_ms: int,
) -> LogEntry:
    """刪除證明：把「刪掉了哪些東西、它們的 sha256 是什麼」簽上鏈。

    `erased` 一項一個 dict：`{"ref": str, "sha256": str, "bytes_n": int}`。
    `ref` 是被刪物的名字（檔名／欄位名），**不是內容**。

    ⚠ `nonce_ref` 必須出現在 `erased` 的某一個 `ref` 裡，否則報錯——
    留著 nonce 而只刪原文，鏈上的 commitment 幾分鐘就被窮舉回原文
    （誠實邊界 3／4）。這一條是可執行的，不是註解。
    """
    if not erased:
        raise ConsentError("erased 不能是空的：沒有被刪物的刪除證明證明不了任何事")
    refs = []
    for item in erased:
        for k in ("ref", "sha256", "bytes_n"):
            if k not in item:
                raise ConsentError(f"erased 項目缺欄位 {k}：{item!r}")
        if len(item["sha256"]) != 64:
            raise ConsentError(f"erased[{item['ref']!r}].sha256 不是 64 字元")
        refs.append(item["ref"])
    if nonce_ref not in refs:
        raise ConsentError(
            f"nonce_ref {nonce_ref!r} 不在被刪清單裡。"
            "只刪原文不刪 nonce ＝ 沒刪：鏈上的 commitment 可以被窮舉回原文"
            "（誠實邊界 4）"
        )
    return book.append(ERASED_TYPE, {
        "v": CONSENT_VERSION,
        "subject_ref": subject_ref,
        "withdraw_hash": withdraw_hash,
        "nonce_ref": nonce_ref,
        "erased": sorted(erased, key=lambda d: d["ref"]),
    }, identity, ts_ms=ts_ms)


# --- 驗 ---------------------------------------------------------------------

@dataclass(frozen=True)
class SubjectStatus:
    """一位捐贈者在這條鏈上的狀態。`state` ∈ granted／withdrawn／erased。"""

    subject_ref: str
    state: str
    grant_seq: int | None
    grant_hash: str | None
    commitment: str | None
    fields: tuple[str, ...]
    scope: str
    withdraw_seq: int | None
    erase_seq: int | None
    erased_refs: tuple[str, ...]

    @property
    def unfulfilled(self) -> bool:
        """撤回了但還沒刪——鏈存在的唯一理由就是讓這個狀態看得見。"""
        return self.state == "withdrawn"


def audit(book: Logbook, who: PublicIdentity) -> dict[str, Any]:
    """離線稽核一條同意鏈：先驗鏈，再逐位捐贈者算出狀態。

    回傳 `{"chain_ok": bool, "stream_id": str|None, "head": str,
           "subjects": {subject_ref: SubjectStatus}, "problems": [str]}`。

    `chain_ok` 是 `Logbook.verify_chain` 的結果，不是本函式自己算的——
    驗鏈只有一把尺，不准在這裡再寫一把。
    """
    chain_ok = book.verify_chain(who)
    subjects: dict[str, SubjectStatus] = {}
    problems: list[str] = []
    by_hash: dict[str, LogEntry] = {e.hash(): e for e in book.entries}

    for e in book.entries:
        p = e.payload if isinstance(e.payload, dict) else {}
        ref = p.get("subject_ref")
        if e.type == GRANT_TYPE:
            subjects[ref] = SubjectStatus(
                subject_ref=ref, state="granted", grant_seq=e.seq, grant_hash=e.hash(),
                commitment=p.get("commitment"), fields=tuple(p.get("fields") or ()),
                scope=p.get("scope", ""), withdraw_seq=None, erase_seq=None,
                erased_refs=(),
            )
        elif e.type == WITHDRAW_TYPE:
            cur = subjects.get(ref)
            if cur is None:
                problems.append(f"seq {e.seq}：撤回了一份鏈上沒有的同意（{ref!r}）")
                continue
            if p.get("grant_hash") != cur.grant_hash:
                problems.append(f"seq {e.seq}：grant_hash 指不到本鏈上那一筆 grant")
            elif p.get("grant_hash") not in by_hash:
                problems.append(f"seq {e.seq}：grant_hash 不在本鏈上")
            subjects[ref] = SubjectStatus(
                **{**cur.__dict__, "state": "withdrawn", "withdraw_seq": e.seq})
        elif e.type == ERASED_TYPE:
            cur = subjects.get(ref)
            if cur is None or cur.withdraw_seq is None:
                problems.append(f"seq {e.seq}：沒有撤回就宣告刪除（{ref!r}）")
                continue
            refs = tuple(i["ref"] for i in p.get("erased", []))
            if p.get("nonce_ref") not in refs:
                problems.append(f"seq {e.seq}：刪除清單裡沒有 nonce（誠實邊界 4）")
            subjects[ref] = SubjectStatus(
                **{**cur.__dict__, "state": "erased", "erase_seq": e.seq,
                   "erased_refs": refs})

    return {
        "chain_ok": chain_ok,
        "stream_id": book.stream_id(),
        "head": book.head(),
        "subjects": subjects,
        "problems": problems,
    }


# --- 可執行防呆 --------------------------------------------------------------

def assert_no_plaintext(book: Logbook, secrets: list[str]) -> None:
    """鏈上任何一筆的 payload 都不准出現這些字串（原文、nonce、姓名…）。

    形狀比照 `memory.assert_ks1_clean`：**可執行的紅線，不是註解**。
    鏈是 append-only，所以這條一旦被違反就永遠補不回來——它必須在寫入前跑，
    而不是事後掃。呼叫端要把「persona 原文的每一個值」與「nonce」都傳進來。
    """
    from .canonical import canonical_str
    for e in book.entries:
        blob = canonical_str(e.payload)
        for s in secrets:
            if s and s in blob:
                raise ConsentError(
                    f"seq {e.seq}（{e.type}）的 payload 出現了不該上鏈的字串。"
                    "鏈是 append-only：這一筆進去就刪不掉了"
                )
