"""
vacant_network.reqloop.extract
G2.5 自動擷取需求——驗證與組裝層（vq-el4.1）。

輸入只有：使用者原文（＋資料檔欄位與前幾列，由 prompt 端提供）。
**不准**給 hidden、scorer、答案。
輸出：RequirementSet（沿用現有 schema 與 checks.py 的 verifier，不准另造）。

防「模型自己發明好過的條件」——全部寫成程式檢查，不是提示詞：
1. `quote` 必須是原文的逐字片段：先嚴格子字串；不中則以空白正規化
   （連續空白視同）再比對。模型只准正規化換行/多空格，改字、換序、
   改寫都算不逐字 → **丟棄該條目**（recorded in report.discarded）。
2. `verifier` 必須在 `checks.SUPPORTED_VERIFIERS`（單一事實來源）；
   不在 → 條目保留但 `unverified=True`，檢查時一律 UNKNOWN，**不當通過**。
3. 參數不合（該 verifier 的必要參數缺失/空，或 kv/plain_recomputed 的
   recompute.type 不在支援清單）→ 同樣 `unverified=True`。
4. 模型輸出無法解析、client 例外 → 空 RequirementSet＋報告記錄
   （fail-closed）；絕不假裝「沒有需求＝通過」。

client 協定（vq-el4.2 注入 OpenAI 相容實作；測試用假 client，不呼叫模型）：

    class ExtractClient(Protocol):
        def complete(self, prompt: str) -> str: ...
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from vacant_network.reqloop.checks import (
    KV_RECOMPUTE_TYPES,
    PLAIN_RECOMPUTE_TYPES,
    SUPPORTED_VERIFIERS,
)
from vacant_network.reqloop.requirements import (
    RequirementItem,
    RequirementSet,
    VALID_KINDS,
)

__all__ = [
    "ExtractClient",
    "ExtractError",
    "ExtractParseError",
    "ExtractReport",
    "build_requirement_set",
    "default_prompt",
    "extract_requirements",
    "parse_model_output",
    "quote_is_verbatim",
]


class ExtractClient(Protocol):
    """擷取模型 client 的最小協定。實作見 vq-el4.2；測試用假 client。"""

    def complete(self, prompt: str) -> str: ...


class ExtractError(Exception):
    """擷取層錯誤基類。"""


class ExtractParseError(ExtractError):
    """模型輸出無法解析成需求條目 JSON。"""


@dataclass(frozen=True)
class DiscardedItem:
    index: int
    id: str
    reason: str


@dataclass(frozen=True)
class UnverifiedItem:
    id: str
    reason: str


@dataclass(frozen=True)
class ExtractReport:
    """一輪擷取的審計報告（可進 STATE／票據；不進證據）。"""

    parse_error: str | None = None
    extract_error: str | None = None
    kept: tuple[str, ...] = ()
    discarded: tuple[DiscardedItem, ...] = ()
    unverified: tuple[UnverifiedItem, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "parse_error": self.parse_error,
            "extract_error": self.extract_error,
            "kept": list(self.kept),
            "discarded": [
                {"index": d.index, "id": d.id, "reason": d.reason} for d in self.discarded
            ],
            "unverified": [{"id": u.id, "reason": u.reason} for u in self.unverified],
        }


_WS_RE = re.compile(r"\s+")
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _norm_ws(s: str) -> str:
    return _WS_RE.sub(" ", s).strip()


def quote_is_verbatim(quote: str, user_text: str) -> bool:
    """quote 是否原文的逐字片段。

    嚴格子字串優先；不中則空白正規化（連續空白視同）再比對。
    改字、換序、改寫（paraphrase）必為 False——這是防發明的核心。
    """
    q = (quote or "").strip()
    if not q:
        return False
    if q in user_text:
        return True
    return _norm_ws(q) in _norm_ws(user_text)


# 每個 verifier 必要頂層參數（缺失即檢查器無法可靠裁決——checks.py 自己也回
# UNKNOWN；這裡提前 surfaced 成 unverified，口徑一致）。
# 未列出的 verifier 無靜態必要參數（檢查器自帶預設或自 UNKNOWN 守衛）。
_REQUIRED_PARAMS: dict[str, tuple[str, ...]] = {
    "csv_structure": ("required_columns",),
    "table_structure": ("required_columns",),
    "answer_kv": ("keys",),
    "kv_recomputed": ("key", "data_file", "recompute"),
    "plain_recomputed": ("data_file", "recompute"),
    "tag_format": ("tag",),
}

_RECOMPUTE_TYPES: dict[str, frozenset[str]] = {
    "kv_recomputed": KV_RECOMPUTE_TYPES,
    "plain_recomputed": PLAIN_RECOMPUTE_TYPES,
}


def _param_problem(verifier: str, params: dict[str, Any]) -> str | None:
    """回傳第一個參數缺陷（機器可讀原因）；無缺陷回 None。不丟例外。"""
    if not isinstance(params, dict):
        return "params_not_object"
    for key in _REQUIRED_PARAMS.get(verifier, ()):
        val = params.get(key)
        if val is None:
            return f"missing_param:{key}"
        if isinstance(val, (str, list, dict)) and not val:
            return f"empty_param:{key}"
    if verifier in ("csv_structure", "table_structure"):
        if not isinstance(params.get("required_columns"), list):
            return "required_columns_not_list"
    if verifier == "answer_kv" and not isinstance(params.get("keys"), list):
        return "keys_not_list"
    allowed = _RECOMPUTE_TYPES.get(verifier)
    if allowed is not None:
        rc = params.get("recompute")
        if not isinstance(rc, dict):
            return "recompute_not_dict"
        rtype = str(rc.get("type", "")).strip().lower()
        if rtype not in allowed:
            return f"unsupported_recompute_type:{rtype or 'missing'}"
    return None


def build_requirement_set(
    task_id: str,
    raw_items: Any,
    user_text: str,
) -> tuple[RequirementSet, ExtractReport]:
    """純函數核心：驗證模型輸出並組裝 RequirementSet（不呼叫模型、不讀檔）。

    丟棄（進 report.discarded，不出現在集合裡）：
    - 非 JSON 物件；quote 缺失/非原文逐字片段；deliverable 缺失；kind 非法。
    標 unverified=True（保留條目，進 report.unverified；檢查時 UNKNOWN）：
    - verifier 不在白名單；必要參數缺失/空；recompute.type 不支援。
    模型自帶 unverified=true 一律尊重（fail-closed）。
    """
    if not isinstance(raw_items, list):
        return (
            RequirementSet(task_id=task_id, items=[]),
            ExtractReport(parse_error="model output is not a JSON array of items"),
        )

    discarded: list[DiscardedItem] = []
    unverified: list[UnverifiedItem] = []
    items: list[RequirementItem] = []

    for index, raw in enumerate(raw_items):
        fallback_id = f"req_{index:03d}"
        if not isinstance(raw, dict):
            discarded.append(DiscardedItem(index, fallback_id, "not_an_object"))
            continue

        rid = raw.get("id")
        fid = rid.strip() if isinstance(rid, str) and rid.strip() else fallback_id

        quote = raw.get("quote")
        if not isinstance(quote, str) or not quote.strip():
            discarded.append(DiscardedItem(index, fid, "quote_missing"))
            continue
        if not quote_is_verbatim(quote, user_text):
            discarded.append(DiscardedItem(index, fid, "quote_not_verbatim"))
            continue

        deliverable = raw.get("deliverable")
        if not isinstance(deliverable, str) or not deliverable.strip():
            discarded.append(DiscardedItem(index, fid, "deliverable_missing"))
            continue

        kind = raw.get("kind", "explicit")
        if not isinstance(kind, str) or kind not in VALID_KINDS:
            # 防呆：kind 不在合法集合 → 丟棄（provenance 元資料不可信）
            discarded.append(DiscardedItem(index, fid, f"invalid_kind:{kind!r}"))
            continue

        params = raw.get("params", {})
        if not isinstance(params, dict):
            params = {}

        verifier = raw.get("verifier")
        if not isinstance(verifier, str) or not verifier.strip():
            verifier = ""
        else:
            verifier = verifier.strip()

        unverified_flag = bool(raw.get("unverified", False))
        reason: str | None = None
        if verifier not in SUPPORTED_VERIFIERS:
            reason = f"unknown_verifier:{verifier or 'missing'}"
            unverified_flag = True
        else:
            problem = _param_problem(verifier, params)
            if problem is not None:
                reason = problem
                unverified_flag = True
        if unverified_flag and reason is None:
            reason = "model_declared_unverified"

        items.append(
            RequirementItem(
                id=fid,
                quote=quote.strip(),
                deliverable=deliverable.strip(),
                verifier=verifier,
                kind=kind,  # type: ignore[arg-type]
                params=params,
                description=str(raw.get("description", "") or ""),
                required=bool(raw.get("required", True)),
                authority=str(raw.get("authority", "client") or "client"),
                hidden=False,  # 擷取輸入只有使用者原文；hidden 條目不許由擷取產生
                unverified=unverified_flag,
            )
        )
        if reason is not None:
            unverified.append(UnverifiedItem(fid, reason))

    report = ExtractReport(
        kept=tuple(i.id for i in items),
        discarded=tuple(discarded),
        unverified=tuple(unverified),
    )
    return RequirementSet(task_id=task_id, items=items), report


def parse_model_output(raw: str) -> list[Any]:
    """從模型輸出抽出需求條目 JSON 陣列；抽不出丟 ExtractParseError。

    依次嘗試：整段 → ``` fence 內 JSON → 首個 {...} / [...] 片段。
    物件形式接受 {"items": [...]} / {"requirements": [...]} / 單條物件。
    """
    if not isinstance(raw, str):
        raise ExtractParseError(f"model output is not text: {type(raw).__name__}")
    text = raw.strip()
    if not text:
        raise ExtractParseError("model output is empty")

    candidates: list[str] = [text]
    m = _FENCE_RE.search(text)
    if m:
        candidates.append(m.group(1).strip())
    for pat in (r"\{.*\}", r"\[.*\]"):
        m = re.search(pat, text, re.DOTALL)
        if m:
            candidates.append(m.group(0))

    last_err = ""
    for cand in candidates:
        try:
            data = json.loads(cand)
        except json.JSONDecodeError as e:
            last_err = str(e)
            continue
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("items", "requirements", "requirements_items"):
                if isinstance(data.get(key), list):
                    return data[key]
            if any(k in data for k in ("quote", "verifier", "deliverable")):
                return [data]
    raise ExtractParseError(
        f"cannot parse a JSON array of requirement items: {last_err or 'no JSON fragment found'}"
    )


def default_prompt(user_text: str) -> str:
    """最小預設 prompt（vq-el4.2 會換上正式 prompt；介面不變）。

    輸入只含使用者原文；不含 hidden／scorer／答案。
    verifier 白名單由 checks.SUPPORTED_VERIFIERS 派生（單一事實來源）。
    """
    verifiers = ", ".join(sorted(SUPPORTED_VERIFIERS))
    return (
        "你是需求擷取助手。只依下方使用者原文，抽出可用程式驗證的需求條目。\n"
        "輸出 JSON 陣列，每項欄位：id, quote, deliverable, verifier, params, "
        "description, required, kind。\n"
        "規則：\n"
        "1. quote 必須是使用者原文的逐字片段（不准改寫、不准自造）。\n"
        f"2. verifier 只能選：{verifiers}。\n"
        "3. params 須符合該 verifier 的要求（如 kv_recomputed 需 key/data_file/"
        "recompute.type；answer_kv 需 keys；tag_format 需 tag）。\n"
        "4. 無法用程式檢查的需求設 unverified=true 並在 description 說明。\n"
        "5. 不准發明使用者沒說的需求。\n\n"
        "使用者原文：\n"
        f"{user_text}"
    )


def extract_requirements(
    *,
    user_text: str,
    client: ExtractClient,
    task_id: str = "unnamed_task",
    build_prompt: Any = None,
) -> tuple[RequirementSet, ExtractReport]:
    """一輪擷取：組 prompt → client → 解析 → 驗證 → RequirementSet。

    fail-closed：client 例外或輸出無法解析 → 空 RequirementSet＋報告記錄，
    不丟例外、不當通過。build_prompt（vq-el4.2）可覆蓋預設 prompt。
    """
    try:
        prompt = (build_prompt or default_prompt)(user_text)
        raw = client.complete(prompt)
    except Exception as e:  # 擷取失敗＝沒有需求，絕不假裝有
        return (
            RequirementSet(task_id=task_id, items=[]),
            ExtractReport(extract_error=f"{type(e).__name__}: {e}"),
        )
    try:
        raw_items = parse_model_output(raw)
    except ExtractParseError as e:
        return (
            RequirementSet(task_id=task_id, items=[]),
            ExtractReport(parse_error=str(e)),
        )
    return build_requirement_set(task_id, raw_items, user_text)
