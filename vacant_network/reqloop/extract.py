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

client 協定（vq-el4.2 實作為 `GlmClient`：subprocess 呼叫 `glm` 指令——
擷取模型的唯一入口；測試用假 client，不呼叫模型）：

    class ExtractClient(Protocol):
        def complete(self, prompt: str) -> str: ...
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
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
    "GlmClient",
    "VERIFIER_HINTS",
    "build_requirement_set",
    "build_task_prompt",
    "csv_preview",
    "default_prompt",
    "json_preview",
    "extract_requirements",
    "main",
    "parse_model_output",
    "quote_is_verbatim",
    "run_task",
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
    "rowset_filter": ("identity",),  # values 選填（只比 identity 行集）
    "group_aggregate": ("group_by", "aggregates"),
    "summary_numbers": ("numbers",),
}

# 這些檢查器用 checks.py 的 _load_source 讀原始資料，必須有 input_csv 或
# input_json（至少其一）；缺了檢查時只回 UNKNOWN——這裡提前 surfaced 成 unverified。
_INPUT_SOURCE_VERIFIERS = frozenset({"rowset_filter", "group_aggregate", "summary_numbers"})

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
    if verifier in _INPUT_SOURCE_VERIFIERS and not (
        isinstance(params.get("input_csv"), str) and params["input_csv"].strip()
        or isinstance(params.get("input_json"), str) and params["input_json"].strip()
    ):
        return "missing_param:input_csv_or_input_json"
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
        "description, required, kind（kind 只能取 explicit／assumption／preference，預設 explicit）。\n"
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


# ------------------------------------------------- vq-el4.2：glm 後端＋任務 CLI

# 每個 verifier 的一行用途提示（只寫在 prompt 裡，幫助模型選對；
# 白名單與參數檢查仍以 checks.py 與本檔 _REQUIRED_PARAMS 為準）。
VERIFIER_HINTS: dict[str, str] = {
    "answer_kv": "答案檔 @key[value] 的鍵值與型別",
    "csv_structure": "交付表格必須存在且含指定欄位",
    "table_structure": "交付表格必須存在且含指定欄位",
    "kv_recomputed": "從原始資料檔重算某鍵值並與交付比對（key/data_file/recompute）",
    "plain_recomputed": "從原始資料檔重算單一數值並與交付比對（data_file/recompute）",
    "tag_format": "文字交付物中 @tag[value] 格式",
    "monthly_sales_metrics": "各月訂單數與淨銷售額與原始資料重算一致",
    "monthly_top_products": "各月淨銷售額前 N 名商品排行與重算一致",
    "summary_metrics_consistency": "摘要文字中合計指標數字與重算一致",
    "summary_numbers": "摘要文字中指定數字與重算一致",
    "rowset_filter": "排除→去重→納入後行集與逐欄值與重算一致（params 必帶 identity、"
                      "input_csv 或 input_json 其一指原始資料檔；values 選填逐欄值）",
    "group_aggregate": "分組聚合值與重算一致（params 必帶 group_by、aggregates、"
                       "input_csv 或 input_json 其一，指原始資料檔）",
    "summary_numbers": "摘要文字中指定數字與重算一致（params 必帶 numbers、"
                       "input_csv 或 input_json 其一，指原始資料檔）",
}


class GlmClient:
    """Vibe CLI 後端（vq-el4.2）：只准透過 `glm` 指令呼叫擷取模型。

    `glm` 是唯一入口（11/07）：空暫存目錄、不給工具、單回合、每天 ≤200 萬
    token 的限制都在指令內；每次呼叫寫 state/vibe_calls.jsonl，輸入輸出全文
    存 logs/vibe/。呼叫端不得繞過 glm 直連 vibe，也不得持有金鑰。
    退出碼：0 成功、3 今日預算用完、4 呼叫失敗——非 0 一律 fail-closed
    （丟 ExtractError，不重試；撞額度就停）。
    """

    def __init__(
        self,
        model: str = "glm53",
        purpose: str = "擷取需求",
        glm_bin: str = "glm",
        timeout: float = 900.0,
    ) -> None:
        self.model = model
        self.purpose = purpose
        self.glm_bin = glm_bin
        self.timeout = timeout

    def complete(self, prompt: str) -> str:
        """寫 prompt 暫存檔 → subprocess 呼叫 glm → 回傳 stdout。"""
        fd, prompt_path = tempfile.mkstemp(prefix="vacant_extract_", suffix=".md")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(prompt)
            proc = subprocess.run(
                [
                    self.glm_bin, "--model", self.model,
                    "--purpose", self.purpose, "--prompt-file", prompt_path,
                ],
                capture_output=True, text=True, timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as e:
            raise ExtractError(f"glm timed out after {self.timeout:.0f}s") from e
        finally:
            try:
                os.unlink(prompt_path)
            except OSError:
                pass
        if proc.returncode != 0:
            lines = [ln for ln in (proc.stderr or proc.stdout or "").strip().splitlines() if ln.strip()]
            raise ExtractError(f"glm rc={proc.returncode}: {lines[-1][:200] if lines else 'no output'}")
        return proc.stdout


def csv_preview(csv_text: str, max_rows: int = 5) -> str:
    """CSV 欄位名稱（header）＋前 max_rows 列資料——准進 prompt 的資料內容上限。"""
    lines = [ln for ln in csv_text.splitlines() if ln.strip()]
    return "\n".join(lines[: max_rows + 1])


def json_preview(json_text: str, max_items: int = 5) -> str:
    """JSON 資料檔預覽：陣列只取前 max_items 項、物件取整體結構——准進 prompt 的資料內容上限。

    解析失敗時退回前 max_items+1 行原文（與 csv_preview 同形）。
    """
    try:
        obj = json.loads(json_text)
    except (json.JSONDecodeError, ValueError):
        lines = [ln for ln in json_text.splitlines() if ln.strip()]
        return "\n".join(lines[: max_items + 1])
    if isinstance(obj, list):
        obj = obj[:max_items]
    return json.dumps(obj, ensure_ascii=False, indent=1)


def build_task_prompt(user_text: str, *, data_file: str = "", data_preview: str = "") -> str:
    """正式 prompt（vq-el4.2）：request 全文＋資料檔欄位與前 5 列＋verifier 清單與輸出格式。

    只含使用者原文與資料預覽；不含 hidden、scorer、手寫 requirements.json。
    """
    hints = "\n".join(
        f"- {name}：{VERIFIER_HINTS.get(name, '見 checks.py')}" for name in sorted(SUPPORTED_VERIFIERS)
    )
    parts = [
        "你是需求擷取助手。只依下方使用者原文，抽出可用程式驗證的需求條目。",
        "輸出：一個 JSON 陣列（陣列外不要說明文字），每項欄位：",
        "id, quote, deliverable, verifier, params, description, required, kind；"
        "kind 只能取 explicit／assumption／preference（預設 explicit，不准自造其他值）。",
        "規則：",
        "1. quote 必須是使用者原文的逐字片段（不准改字、換序、改寫、自造）；拿不準寧可不收該條。",
        "2. verifier 只能選：",
        hints,
        "3. params 須符合該 verifier 的要求（如 answer_kv 需 keys；kv_recomputed 需 key/data_file/recompute；csv_structure 需 required_columns）。",
        "4. 無法用程式驗證的需求設 unverified=true，並在 description 說明原因。",
        "5. 不准發明使用者沒說的需求。",
    ]
    if data_file:
        parts += ["", f"附帶資料檔：{data_file}（欄位與前幾列／項，僅供判斷欄位名稱）：", data_preview]
    parts += ["", "使用者原文：", user_text]
    return "\n".join(parts)


def run_task(
    request_md: str | pathlib.Path,
    *,
    model: str,
    client: ExtractClient,
    out_path: str | pathlib.Path,
) -> tuple[RequirementSet, ExtractReport]:
    """對真實任務目錄做一輪擷取：request.md 全文＋第一個 .csv 預覽 → client → 逐字/白名單檢查 → 寫結果。

    只讀 request.md 與任務目錄頂層第一個 .csv；同目錄的 requirements.json、
    bad_*／good 等手寫需求與參考產物一律不讀、不進 prompt。
    """
    req_md = pathlib.Path(request_md)
    t_dir = req_md.parent
    user_text = req_md.read_text(encoding="utf-8")
    data_file = ""
    data_preview = ""
    csvs = sorted(t_dir.glob("*.csv"))
    if csvs:
        data_file = csvs[0].name
        data_preview = csv_preview(csvs[0].read_text(encoding="utf-8"))
    else:
        # 無 CSV 時看頂層 JSON 資料檔（如 nested_events/events.json）；
        # 手寫 requirements.json 是參考需求，一律不准進 prompt。
        jsons = sorted(p for p in t_dir.glob("*.json") if p.name != "requirements.json")
        if jsons:
            data_file = jsons[0].name
            data_preview = json_preview(jsons[0].read_text(encoding="utf-8"))
    prompt = build_task_prompt(user_text, data_file=data_file, data_preview=data_preview)
    req, report = extract_requirements(
        user_text=user_text, client=client, task_id=t_dir.name,
        build_prompt=lambda _text: prompt,
    )
    out = pathlib.Path(out_path)
    doc = req.to_dict()
    doc["model"] = model
    doc["report"] = report.to_dict()
    doc["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return req, report


def main(argv: list[str] | None = None) -> int:
    """CLI：python3 -m vacant_network.reqloop.extract --task <dir> --model glm53"""
    ap = argparse.ArgumentParser(
        prog="python3 -m vacant_network.reqloop.extract",
        description="G2.5 自動擷取需求（glm 後端；prompt 只含原文與資料欄位前 5 列，不含 hidden/scorer/手寫需求）",
    )
    ap.add_argument("--task", required=True, help="任務目錄（含 request.md 與資料 csv）")
    ap.add_argument("--model", default="glm53", choices=("glm53", "glm53flash", "deepseek41"))
    ap.add_argument("--out", default=None, help="輸出 json（預設 ops/reqloop/extract/out/<task>.<model>.json）")
    ap.add_argument("--glm", default="glm", help="glm 指令路徑（測試可注入假指令）")
    a = ap.parse_args(argv)

    req_md = pathlib.Path(a.task) / "request.md"
    if not req_md.is_file():
        print(f"error: 找不到 {req_md}", file=sys.stderr)
        return 2
    task_id = pathlib.Path(a.task).name
    client = GlmClient(model=a.model, purpose=f"{task_id} 擷取需求", glm_bin=a.glm)
    out_path = (
        pathlib.Path(a.out)
        if a.out
        else pathlib.Path("ops/reqloop/extract/out") / f"{task_id}.{a.model}.json"
    )
    req, report = run_task(req_md, model=a.model, client=client, out_path=out_path)
    print(f"條目 {len(req.items)}、丟棄 {len(report.discarded)}、unverified {len(report.unverified)}")
    print(f"寫入：{out_path}")
    if report.extract_error or report.parse_error:
        print(f"擷取失敗（fail-closed）：{report.extract_error or report.parse_error}", file=sys.stderr)
        return 20
    return 0


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


if __name__ == "__main__":
    raise SystemExit(main())
