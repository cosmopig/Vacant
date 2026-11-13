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
import ast
import copy
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import dataclasses
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
    "VERIFIER_PARAM_EXAMPLES",
    "build_requirement_set",
    "build_task_prompt",
    "trusted_deliverable_from_contract",
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

_RECOMPUTE_TYPES: dict[str, frozenset[str]] = {
    "kv_recomputed": KV_RECOMPUTE_TYPES,
    "plain_recomputed": PLAIN_RECOMPUTE_TYPES,
}

_VALID_KEY_TYPES = frozenset({"number", "integer", "nonneg_int", "number_in_01"})
_VALID_TAG_VALUE_TYPES = frozenset({"integer", "int", "float", "number", "str"})
_VALID_AGG_TYPES = frozenset(
    {"count", "distinct", "sum", "mean", "mean_skip_empty", "max", "min", "count_if", "ratio"}
)
_VALID_SUMMARY_NUM_TYPES = frozenset(
    {"count", "distinct", "sum", "mean", "max", "min", "pct_if"}
)
# 與 checks.py:_col_stats 對齊（僅支援 mean / median / sd / skewness / kurtosis）
_VALID_COL_STATS = frozenset({"mean", "median", "sd", "skewness", "kurtosis"})
_COL_STAT_ALIASES: dict[str, str] = {
    "std": "sd",
    "stddev": "sd",
    "skew": "skewness",
    "kurt": "kurtosis",
    "p50": "median",
}
_AGG_TYPE_ALIASES: dict[str, str] = {
    "distinct_count": "distinct",
    "count_distinct": "distinct",
    "nunique": "distinct",
    "avg": "mean",
    "average": "mean",
}
_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod)
_ALLOWED_CMPS = (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)
_ALLOWED_UNARY = (ast.UAdd, ast.USub)
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def _non_empty_str(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _strip_workspace_prefix(p: Any) -> Any:
    if not isinstance(p, str):
        return p
    s = p.strip()
    if s.startswith("/app/"):
        s = s[len("/app/"):]
    elif s.startswith("./"):
        s = s[2:]
    return s


_FILE_PATH_RE = re.compile(r"^[\w.\-/]+\.\w{1,8}$")


def _deliverable_problem(deliverable: str, user_text: str) -> str | None:
    """交付物檔名必須是原文（含公開 contract）點名的檔案；模型猜的名字 → 回傳原因。

    猜名（如 "answer"、"@total_hotels[count]"、"removed_outliers_count"）檢查時只會因
    「檔案不存在」判 FAIL：對錯草稿是假抓錯、對對草稿是冤枉——那是擷取錯，不是交付錯。
    判準：形如檔案路徑（有副檔名），且路徑或檔名在原文中以完整 token 出現
    （"answer" 不會因原文有 "answer.txt" 而算點名）。
    """
    d = deliverable.strip()
    if not _FILE_PATH_RE.match(d):
        return f"deliverable_not_in_request:{d[:60]}"
    for name in dict.fromkeys((d, pathlib.PurePosixPath(d).name)):
        if re.search(r"(?<![\w\-])" + re.escape(name) + r"(?![\w\-]|\.\w)", user_text):
            return None
    return f"deliverable_not_in_request:{d[:60]}"


# D2（P20261113_0300-2、11-13 裁決第 2 條）：trusted 交付物抽取用的檔案 token 判定。
# 與 _FILE_PATH_RE 的差異：副檔名必須以字母開頭——純數值（如容差 0.000001）
# 絕不得誤認為檔名。漏判只落到 None（維持 UNKNOWN），不會製造交付物。
_TOKEN_FILE_RE = re.compile(
    r"(?<![\w\-/.])([\w.\-/]+\.[A-Za-z][A-Za-z0-9]{0,7})(?![\w\-]|\.\w)"
)


def trusted_deliverable_from_contract(
    user_text: str, input_files: Any = ()
) -> str | None:
    """交付物是任務的事實，不是模型自報（11-13 裁決第 2 條）：從原文（含公開
    contract）抽出被點名的輸出檔。

    規則（全部 fail-closed）：
    - 候選＝完整 token、形如檔案路徑（副檔名以字母開頭）、且不是輸入檔
      （全名或 basename 都不在 input_files）；
    - 恰一個候選 → 回傳它；零個或多個 → None（呼叫方照舊 UNKNOWN，不猜）。
    輸入檔永遠不是交付物（裁決明定的界線）。
    """
    names = {str(x).strip() for x in (input_files or ()) if str(x).strip()}
    names |= {n.rsplit("/", 1)[-1] for n in names}
    cands: list[str] = []
    for tok in dict.fromkeys(_TOKEN_FILE_RE.findall(str(user_text or ""))):
        if tok in names or tok.rsplit("/", 1)[-1] in names:
            continue
        cands.append(tok)
    return cands[0] if len(cands) == 1 else None


def _apply_trusted_deliverable(
    req_set: RequirementSet,
    report: ExtractReport,
    trusted: str,
    user_text: str,
) -> tuple[RequirementSet, ExtractReport]:
    """D2：每條目的 deliverable 一律設為 trusted；模型原字串只留紀錄在
    deliverable_claimed、不參與判定。

    - trusted 本身必須通過 _deliverable_problem（原文點名的檔案）；不通過
      就什麼都不改（fail-closed，不改寫 _deliverable_problem 本身）；
    - 因 deliverable_not_in_request:* 而 unverified 的條目重新判定後解除；
      其他原因（未知 verifier、參數不合、模型自報 unverified）不解除。
    """
    t = str(trusted).strip()
    if not t or _deliverable_problem(t, user_text) is not None:
        return req_set, report
    reasons = {u.id: u.reason for u in report.unverified}
    cleared: set[str] = set()
    items: list[RequirementItem] = []
    for it in req_set.items:
        ni = dataclasses.replace(it, deliverable=t, deliverable_claimed=it.deliverable)
        r = reasons.get(it.id)
        if ni.unverified and isinstance(r, str) and r.startswith(
            "deliverable_not_in_request:"
        ):
            ni = dataclasses.replace(ni, unverified=False)
            cleared.add(it.id)
        items.append(ni)
    if cleared:
        report = dataclasses.replace(
            report,
            unverified=tuple(u for u in report.unverified if u.id not in cleared),
        )
    return dataclasses.replace(req_set, items=items), report


def _unwrap_round_call(expr: str) -> tuple[str, int | None]:
    """若運算式最外層為 round(inner[, n])，拆解為 (inner_src, n) 供 checks.py safe_eval_expr 求值。"""
    if not isinstance(expr, str) or not expr.strip():
        return expr, None
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError:
        return expr, None
    body = tree.body
    if (
        isinstance(body, ast.Call)
        and isinstance(body.func, ast.Name)
        and body.func.id == "round"
        and not body.keywords
        and 1 <= len(body.args) <= 2
    ):
        ndigits = 0
        if len(body.args) == 2:
            arg1 = body.args[1]
            if (
                isinstance(arg1, ast.Constant)
                and isinstance(arg1.value, int)
                and not isinstance(arg1.value, bool)
            ):
                ndigits = int(arg1.value)
            else:
                return expr, None
        return ast.unparse(body.args[0]), ndigits
    return expr, None


def _expr_syntax_ok(expr: str) -> bool:
    """靜態檢查 expr 是否符合 checks.py:safe_eval_expr 允許的 AST 節點。"""
    if not isinstance(expr, str) or not expr.strip():
        return False
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError:
        return False

    def _ok(node: ast.AST) -> bool:
        if isinstance(node, ast.Expression):
            return _ok(node.body)
        if isinstance(node, ast.Constant):
            return (
                isinstance(node.value, (int, float, str))
                and not isinstance(node.value, bool)
            )
        if isinstance(node, ast.Name):
            return True
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
            return _ok(node.left) and _ok(node.right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY:
            return _ok(node.operand)
        if (
            isinstance(node, ast.Compare)
            and len(node.ops) == 1
            and type(node.ops[0]) in _ALLOWED_CMPS
            and len(node.comparators) == 1
        ):
            return _ok(node.left) and _ok(node.comparators[0])
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            return all(_ok(v) for v in node.values)
        return False

    return _ok(tree)


def _recompute_subparam_problem(rtype: str, rc: dict[str, Any]) -> str | None:
    """檢查 kv_recomputed / plain_recomputed 各 rtype 的必要子參數。"""
    if rtype in (
        "mean_int_col",
        "zcount3",
        "null_count",
        "unique_count",
        "col_max",
        "mode_col",
    ):
        if not _non_empty_str(rc.get("col")):
            return "missing_recompute_param:col"
    elif rtype == "count_if":
        if not _non_empty_str(rc.get("col")):
            return "missing_recompute_param:col"
        if rc.get("eq") is None:
            return "missing_recompute_param:eq"
    elif rtype == "max_row_first":
        if not _non_empty_str(rc.get("sel_col")):
            return "missing_recompute_param:sel_col"
        if not _non_empty_str(rc.get("out_col")):
            return "missing_recompute_param:out_col"
    elif rtype == "pearson2":
        if not _non_empty_str(rc.get("col_a")):
            return "missing_recompute_param:col_a"
        if not _non_empty_str(rc.get("col_b")):
            return "missing_recompute_param:col_b"
    elif rtype == "col_stats":
        if not _non_empty_str(rc.get("col")):
            return "missing_recompute_param:col"
        stat = str(rc.get("stat", "")).strip().lower()
        if stat not in _VALID_COL_STATS:
            return f"unsupported_recompute_stat:{stat or 'missing'}"
    elif rtype == "cond_rate":
        where = rc.get("where")
        num_where = rc.get("num_where")
        if (
            not isinstance(where, list)
            or not where
            or any(not isinstance(c, dict) or not _non_empty_str(c.get("col")) for c in where)
        ):
            return "missing_recompute_param:where"
        if (
            not isinstance(num_where, list)
            or not num_where
            or any(
                not isinstance(c, dict) or not _non_empty_str(c.get("col")) for c in num_where
            )
        ):
            return "missing_recompute_param:num_where"
    elif rtype == "group_ratio_stat":
        if not _non_empty_str(rc.get("group_col")):
            return "missing_recompute_param:group_col"
        has_sum = _non_empty_str(rc.get("sum_col")) or (
            _non_empty_str(rc.get("num_sum_col")) and _non_empty_str(rc.get("denom_sum_col"))
        )
        if not has_sum:
            return "missing_recompute_param:sum_col"
        num_where = rc.get("num_where")
        if (
            not isinstance(num_where, list)
            or not num_where
            or any(
                not isinstance(c, dict) or not _non_empty_str(c.get("col")) for c in num_where
            )
        ):
            return "missing_recompute_param:num_where"
        stat = str(rc.get("stat", "max")).strip().lower()
        if stat not in ("min", "max"):
            return f"unsupported_recompute_stat:{stat}"
        out = str(rc.get("out", "val")).strip().lower()
        if out not in ("val", "group"):
            return f"unsupported_recompute_out:{out}"
    elif rtype == "scheme_fee_avg":
        if not _non_empty_str(rc.get("scheme")):
            return "missing_recompute_param:scheme"
        if not isinstance(rc.get("is_credit"), bool):
            return "missing_recompute_param:is_credit"
        amt = rc.get("amount")
        if amt is None or isinstance(amt, bool) or not isinstance(amt, (int, float, str)):
            return "missing_recompute_param:amount"
    elif rtype == "fee_ids_lookup":
        for subk in ("fees_file", "merchants_file", "merchant"):
            if not _non_empty_str(rc.get(subk)):
                return f"missing_recompute_param:{subk}"
        yr = rc.get("year")
        mo = rc.get("month")
        if isinstance(yr, bool) or not isinstance(yr, int):
            return "missing_recompute_param:year"
        if isinstance(mo, bool) or not isinstance(mo, int) or not (1 <= mo <= 12):
            return "missing_recompute_param:month"
    return None


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
        cols = params.get("required_columns")
        if not isinstance(cols, list):
            return "required_columns_not_list"
        if any(not _non_empty_str(c) for c in cols):
            return "invalid_required_column"
    if verifier == "answer_kv":
        keys = params.get("keys")
        if not isinstance(keys, list):
            return "keys_not_list"
        for s in keys:
            if not isinstance(s, dict) or not _non_empty_str(s.get("key")):
                return "invalid_key_spec"
            vtype = str(s.get("type", "number")).strip().lower()
            if vtype not in _VALID_KEY_TYPES:
                return f"unsupported_key_type:{vtype or 'missing'}"
    if verifier == "tag_format":
        if not _non_empty_str(params.get("tag")):
            return "invalid_param:tag"
        vt = params.get("value_type")
        if vt is not None and str(vt).strip().lower() not in _VALID_TAG_VALUE_TYPES:
            return f"unsupported_tag_value_type:{vt}"
    if verifier in (
        "monthly_sales_metrics",
        "monthly_top_products",
        "summary_metrics_consistency",
    ):
        if "input_csv" in params and not _non_empty_str(params.get("input_csv")):
            return "empty_param:input_csv"
        if verifier == "summary_metrics_consistency" and _non_empty_str(params.get("input_csv")):
            csv_name = pathlib.Path(str(params["input_csv"]).strip()).name.lower()
            if csv_name != "orders.csv":
                return "invalid_param:summary_metrics_consistency_requires_orders_csv"
    if verifier in ("rowset_filter", "group_aggregate", "summary_numbers"):
        if not (
            _non_empty_str(params.get("input_csv"))
            or _non_empty_str(params.get("input_json"))
        ):
            return "missing_param:input_csv_or_json"
        # r1183 + argon 20261107_1149：exclude 條件 op:ne 是逆向過濾（「排除非 X」會排空行集），
        # rowset_filter / group_aggregate / summary_numbers 共用 apply_pipeline，一律攔截。
        excl = params.get("exclude")
        if isinstance(excl, list):
            for cond in excl:
                if isinstance(cond, dict) and cond.get("op") == "ne":
                    return "invalid_param:exclude_op_ne"
        comp = params.get("compute")
        if comp is not None:
            if not isinstance(comp, list):
                return "invalid_param:compute"
            for cspec in comp:
                if not isinstance(cspec, dict) or not _non_empty_str(cspec.get("name")):
                    return "invalid_param:compute"
                if not _expr_syntax_ok(str(cspec.get("expr", ""))):
                    return "invalid_param:expr"
        if verifier == "rowset_filter":
            ident = params.get("identity")
            if not isinstance(ident, list) or any(not _non_empty_str(c) for c in ident):
                return "invalid_param:identity"
            vals = params.get("values")
            if vals is not None and not isinstance(vals, dict):
                return "invalid_param:values"
            has_vals = isinstance(vals, dict) and bool(vals)
            has_filter = bool(
                params.get("exclude") or params.get("include") or params.get("dedup_by")
            )
            if not has_vals and not has_filter:
                return "missing_param:values"
            if isinstance(vals, dict):
                for out_col, spec in vals.items():
                    if not _non_empty_str(out_col):
                        return "invalid_param:values"
                    if isinstance(spec, str):
                        if not spec.strip() or not _IDENT_RE.match(spec.strip()):
                            return "invalid_param:values"
                    elif isinstance(spec, dict):
                        if not _non_empty_str(spec.get("expr")):
                            return "invalid_param:values"
                        if not _expr_syntax_ok(str(spec.get("expr", ""))):
                            return "invalid_param:expr"
                    else:
                        return "invalid_param:values"
        elif verifier == "group_aggregate":
            gb = params.get("group_by")
            if not isinstance(gb, list) or any(not _non_empty_str(c) for c in gb):
                return "invalid_param:group_by"
            aggs = params.get("aggregates")
            if not isinstance(aggs, list):
                return "invalid_param:aggregates"
            for a in aggs:
                if not isinstance(a, dict) or not _non_empty_str(a.get("name")):
                    return "invalid_param:aggregates"
                atype = str(a.get("type", "")).strip()
                if atype not in _VALID_AGG_TYPES:
                    return f"unsupported_aggregate_type:{atype or 'missing'}"
                if a.get("expr") is not None and not _expr_syntax_ok(str(a.get("expr", ""))):
                    return "invalid_param:expr"
        elif verifier == "summary_numbers":
            nums = params.get("numbers")
            if not isinstance(nums, list):
                return "invalid_param:numbers"
            for n in nums:
                if not isinstance(n, dict):
                    return "invalid_param:numbers"
                ntype = str(n.get("type", "")).strip()
                if ntype not in _VALID_SUMMARY_NUM_TYPES:
                    return f"unsupported_summary_number_type:{ntype or 'missing'}"
                if n.get("expr") is not None and not _expr_syntax_ok(str(n.get("expr", ""))):
                    return "invalid_param:expr"
    allowed = _RECOMPUTE_TYPES.get(verifier)
    if allowed is not None:
        if verifier == "kv_recomputed" and not _non_empty_str(params.get("key")):
            return "invalid_param:key"
        if not _non_empty_str(params.get("data_file")):
            return "invalid_param:data_file"
        rc = params.get("recompute")
        if not isinstance(rc, dict):
            return "recompute_not_dict"
        rtype = str(rc.get("type", "")).strip().lower()
        if rtype not in allowed:
            return f"unsupported_recompute_type:{rtype or 'missing'}"
        sub_prob = _recompute_subparam_problem(rtype, rc)
        if sub_prob is not None:
            return sub_prob
    return None


def _normalize_raw_items(raw_items: list[Any], user_text: str) -> list[Any]:
    """只做不改語義的純語法正規化（路徑前綴、型別別名、round(expr, n) 拆解、巢狀欄位攤平）。

    argon 20261107_1242：不得替模型補條件。舊版第二趟會從兄弟條目複製
    exclude/dedup_by/include/compute/flatten、對 orders.csv 硬塞 CANCELLED/order_id/
    net_sales 公式、把非 orders.csv 的 summary_metrics_consistency 改成 summary_numbers
    並自訂 round——這些不在模型輸出也不在該條 quote 內，等於把手寫需求藏進擷取器，
    已移除（模型漏寫的條件照原樣檢查；檢查不了的由 _param_problem 標 unverified）。
    """
    cloned = [copy.deepcopy(it) if isinstance(it, dict) else it for it in raw_items]

    # 第一趟：單條目路徑、別名、round(expr, n) 拆解與 input_json 巢狀欄位 flatten
    for raw in cloned:
        if not isinstance(raw, dict):
            continue
        if isinstance(raw.get("deliverable"), str):
            raw["deliverable"] = _strip_workspace_prefix(raw["deliverable"])
        params = raw.get("params")
        if not isinstance(params, dict):
            continue
        for pk in ("data_file", "input_csv", "input_json", "file"):
            if isinstance(params.get(pk), str):
                params[pk] = _strip_workspace_prefix(params[pk])
        rc = params.get("recompute")
        if isinstance(rc, dict):
            for rk in ("fees_file", "merchants_file"):
                if isinstance(rc.get(rk), str):
                    rc[rk] = _strip_workspace_prefix(rc[rk])
            if str(rc.get("type", "")).strip().lower() == "col_stats" and isinstance(rc.get("stat"), str):
                st = rc["stat"].strip().lower()
                rc["stat"] = _COL_STAT_ALIASES.get(st, st)
            if "round" not in rc and isinstance(params.get("round"), int) and not isinstance(params.get("round"), bool):
                rc["round"] = params["round"]

        computed_rounds: dict[str, int] = {}
        comp = params.get("compute")
        if isinstance(comp, list):
            for cspec in comp:
                if isinstance(cspec, dict) and isinstance(cspec.get("expr"), str):
                    inner, r_digits = _unwrap_round_call(cspec["expr"])
                    cspec["expr"] = inner
                    if r_digits is not None and _non_empty_str(cspec.get("name")):
                        computed_rounds[str(cspec["name"]).strip()] = r_digits

        vals = params.get("values")
        if isinstance(vals, dict):
            for out_col, spec in list(vals.items()):
                if isinstance(spec, str):
                    s = spec.strip()
                    if not _IDENT_RE.match(s):
                        inner, r_digits = _unwrap_round_call(s)
                        if _expr_syntax_ok(inner):
                            vdict: dict[str, Any] = {"expr": inner}
                            if r_digits is not None:
                                vdict["round"] = r_digits
                            vals[out_col] = vdict
                    elif s in computed_rounds:
                        vals[out_col] = {"expr": s, "round": computed_rounds[s]}
                elif isinstance(spec, dict) and isinstance(spec.get("expr"), str):
                    inner, r_digits = _unwrap_round_call(spec["expr"])
                    spec["expr"] = inner
                    if r_digits is not None and "round" not in spec:
                        spec["round"] = r_digits

        aggs = params.get("aggregates")
        if isinstance(aggs, list):
            for a in aggs:
                if not isinstance(a, dict):
                    continue
                if isinstance(a.get("type"), str):
                    at = a["type"].strip().lower()
                    a["type"] = _AGG_TYPE_ALIASES.get(at, at)
                if isinstance(a.get("expr"), str):
                    inner, r_digits = _unwrap_round_call(a["expr"])
                    a["expr"] = inner
                    if r_digits is not None and "round" not in a:
                        a["round"] = r_digits
                if isinstance(a.get("col"), str) and "round" not in a:
                    col_name = a["col"].strip()
                    if col_name in computed_rounds:
                        a["round"] = computed_rounds[col_name]

        nums = params.get("numbers")
        if isinstance(nums, list):
            for n in nums:
                if not isinstance(n, dict):
                    continue
                if isinstance(n.get("type"), str):
                    nt = n["type"].strip().lower()
                    n["type"] = _AGG_TYPE_ALIASES.get(nt, nt)
                if isinstance(n.get("expr"), str):
                    inner, r_digits = _unwrap_round_call(n["expr"])
                    n["expr"] = inner
                    if r_digits is not None and "round" not in n:
                        n["round"] = r_digits

        if _non_empty_str(params.get("input_json")):
            ref_cols: list[str] = []
            for key_list in ("group_by", "identity"):
                kl = params.get(key_list)
                if isinstance(kl, list):
                    ref_cols.extend(str(c).strip() for c in kl if _non_empty_str(c))
            if _non_empty_str(params.get("dedup_by")):
                ref_cols.append(str(params["dedup_by"]).strip())
            for cond_key in ("exclude", "include"):
                cl = params.get(cond_key)
                if isinstance(cl, list):
                    for c in cl:
                        if isinstance(c, dict) and _non_empty_str(c.get("col")):
                            ref_cols.append(str(c["col"]).strip())
            for spec_key in ("aggregates", "numbers"):
                sl = params.get(spec_key)
                if isinstance(sl, list):
                    for s in sl:
                        if isinstance(s, dict) and _non_empty_str(s.get("col")):
                            ref_cols.append(str(s["col"]).strip())
            dotted = [c for c in dict.fromkeys(ref_cols) if "." in c]
            if dotted:
                flat = params.get("flatten")
                if not isinstance(flat, list):
                    flat = []
                existing = {
                    str(f.get("as") or f.get("path") or "").strip()
                    for f in flat
                    if isinstance(f, dict)
                }
                for dc in dotted:
                    if dc not in existing:
                        # 只做路徑攤平；缺值怎麼補（impute）是需求語義，由模型依原文寫，程式不代決定
                        flat.append({"path": dc, "as": dc})
                        existing.add(dc)
                params["flatten"] = flat

    return cloned


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

    normalized_items = _normalize_raw_items(raw_items, user_text)
    discarded: list[DiscardedItem] = []
    unverified: list[UnverifiedItem] = []
    items: list[RequirementItem] = []
    seen_ids: set[str] = set()

    for index, raw in enumerate(normalized_items):
        fallback_id = f"req_{index:03d}"
        if not isinstance(raw, dict):
            discarded.append(DiscardedItem(index, fallback_id, "not_an_object"))
            continue

        rid = raw.get("id")
        base_id = rid.strip() if isinstance(rid, str) and rid.strip() else fallback_id
        fid = base_id
        if fid in seen_ids:
            fid = f"{base_id}_{index}"
            suffix = 2
            while fid in seen_ids:
                fid = f"{base_id}_{index}_{suffix}"
                suffix += 1

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

        raw_params = raw.get("params", {})
        params = raw_params if isinstance(raw_params, dict) else {}

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
            problem = _param_problem(verifier, raw_params)
            if problem is not None:
                reason = problem
                unverified_flag = True
        if reason is None:
            d_problem = _deliverable_problem(deliverable, user_text)
            if d_problem is not None:
                reason = d_problem
                unverified_flag = True
        if reason is None and verifier == "tag_format":
            tag_name = str(raw_params.get("tag", "")).strip()
            if tag_name and not re.search(r"@\s*" + re.escape(tag_name) + r"\b", user_text):
                reason = f"tag_not_in_request:{tag_name[:40]}"
                unverified_flag = True
        if unverified_flag and reason is None:
            reason = "model_declared_unverified"

        seen_ids.add(fid)
        items.append(
            RequirementItem(
                id=fid,
                quote=quote.strip(),
                deliverable=deliverable.strip(),
                verifier=verifier,
                kind=kind,  # type: ignore[arg-type]
                params=params,
                description=str(raw.get("description", "") or ""),
                required=True,  # 擷取條目一律 required=True，防模型設 false 繞過門禁
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


def _coerce_parsed_items(data: Any) -> list[Any] | None:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("items", "requirements", "requirements_items"):
            if isinstance(data.get(key), list):
                return data[key]
        if any(k in data for k in ("quote", "verifier", "deliverable")):
            return [data]
    return None


def parse_model_output(raw: str) -> list[Any]:
    """從模型輸出抽出需求條目 JSON 陣列；抽不出丟 ExtractParseError。

    依次嘗試：整段 → 所有 ``` fence 內 JSON → 首個 {...} / [...] 片段 → raw_decode 掃描。
    物件形式接受 {"items": [...]} / {"requirements": [...]} / 單條物件。
    """
    if not isinstance(raw, str):
        raise ExtractParseError(f"model output is not text: {type(raw).__name__}")
    text = raw.strip()
    if not text:
        raise ExtractParseError("model output is empty")

    candidates: list[str] = [text]
    for m in _FENCE_RE.finditer(text):
        fenced = m.group(1).strip()
        if fenced:
            candidates.append(fenced)
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
        coerced = _coerce_parsed_items(data)
        if coerced is not None:
            return coerced

    decoder = json.JSONDecoder()
    for pos, ch in enumerate(text):
        if ch not in "[{":
            continue
        try:
            data, _ = decoder.raw_decode(text, pos)
        except json.JSONDecodeError as e:
            last_err = str(e)
            continue
        coerced = _coerce_parsed_items(data)
        if coerced is not None:
            return coerced

    raise ExtractParseError(
        f"cannot parse a JSON array of requirement items: {last_err or 'no JSON fragment found'}"
    )


def default_prompt(user_text: str) -> str:
    """最小預設 prompt（vq-el4.2 會換上正式 prompt；介面不變）。

    輸入只含使用者原文；不含 hidden／scorer／答案。
    verifier 白名單由 checks.SUPPORTED_VERIFIERS 派生（單一事實來源）。
    """
    verifiers = ", ".join(sorted(SUPPORTED_VERIFIERS))
    examples = "\n".join(
        f"- {name}: {VERIFIER_PARAM_EXAMPLES[name]}" for name in sorted(VERIFIER_PARAM_EXAMPLES)
    )
    return (
        "你是需求擷取助手。只依下方使用者原文，抽出可用程式驗證的需求條目。\n"
        "輸出 JSON 陣列，每項欄位：id, quote, deliverable, verifier, params, "
        "description, required, kind（kind 只能取 explicit／assumption／preference，預設 explicit）。\n"
        "規則：\n"
        "1. quote 必須是使用者原文的逐字片段（不准改寫、不准自造）。\n"
        f"2. verifier 只能選：{verifiers}。\n"
        "3. params 必須符合下方該 verifier 的範例形狀（欄位名、型別、巢狀結構逐字照範例，"
        "不准自創欄位名）：\n"
        f"{examples}\n"
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
    "summary_metrics_consistency": "月度訂單銷售摘要文字中「合計淨銷售總額」與 orders.csv 重算一致（非 orders.csv 任務一律改用 summary_numbers）",
    "rowset_filter": "排除→去重→納入後行集與逐欄值與重算一致（params 必帶 identity、"
                      "input_csv 或 input_json 其一指原始資料檔；values 選填逐欄值）",
    "group_aggregate": "分組聚合值與重算一致（params 必帶 group_by、aggregates、"
                       "input_csv 或 input_json 其一，指原始資料檔）",
    "summary_numbers": "摘要文字中指定數字與重算一致（params 必帶 numbers、"
                       "input_csv 或 input_json 其一，指原始資料檔）",
}


# 每個 verifier 的 params 範例（vq-el4.3 第 2 輪：r1180 門禁 FAIL 的主因是模型自創欄位名——
# identity/group_by 寫成字串、aggregates 用 {column,func}、numbers 用 {value,label}、
# recompute 寫成字串。範例的欄位名、型別、巢狀結構必須逐字照抄；
# 資料檔名必須是任務目錄裡真實存在的檔名（prompt 附帶資料檔那一節會列出）。)
VERIFIER_PARAM_EXAMPLES: dict[str, str] = {
    "answer_kv": '{"keys": [{"key": "grand_total", "type": "number"}]}',
    "csv_structure": '{"required_columns": ["category", "subcategory", "total_amount"]}',
    "table_structure": '{"required_columns": ["month", "orders_count", "net_sales"]}',
    "kv_recomputed": '{"key": "mean_cases", "data_file": "events.csv",'
                     ' "recompute": {"type": "count_if", "col": "cases", "eq": 3}}',
    "plain_recomputed": '{"data_file": "orders.csv",'
                        ' "recompute": {"type": "mode_col", "col": "status"}}',
    "tag_format": '{"tag": "total", "value_type": "number"}',
    "monthly_sales_metrics": '{"input_csv": "orders.csv", "expected_in_evidence": true}',
    "monthly_top_products": '{"input_csv": "orders.csv", "top_n": 3}',
    "summary_metrics_consistency": '{"input_csv": "orders.csv",'
                                   ' "metric_keywords": ["合計淨銷售總額"]}',
    "summary_numbers": '{"input_csv": "orders.csv",'
                       ' "numbers": [{"type": "sum", "col": "amount", "label": "合計淨銷售總額"}]}',
    "rowset_filter": '{"input_csv": "orders.csv", "identity": ["order_id"],'
                     ' "exclude": [{"col": "status", "op": "eq", "value": "CANCELLED"}]}',
    "group_aggregate": '{"input_csv": "orders.csv", "group_by": ["category"],'
                       ' "group_normalize": {"category": {"lower": true}},'
                       ' "aggregates": [{"name": "total_count", "type": "count"},'
                       ' {"name": "high_count", "type": "count_if", "expr": "amount >= 100"},'
                       ' {"name": "high_rate", "type": "ratio", "num": "high_count",'
                       ' "den": "total_count", "round": 4}]}',
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
    """JSON 資料檔預覽：頂層陣列只取前 max_items 項（每列內容完整）；
    頂層物件保留全部鍵（欄位名）、陣列值只取前 max_items 項（每列完整）——不深層遞迴。

    解析失敗時退回前 max_items+1 行原文（與 csv_preview 同形）。
    """
    try:
        obj = json.loads(json_text)
    except (json.JSONDecodeError, ValueError):
        lines = [ln for ln in json_text.splitlines() if ln.strip()]
        return "\n".join(lines[: max_items + 1])
    if isinstance(obj, list):
        obj = obj[:max_items]
    elif isinstance(obj, dict):
        obj = {k: (v[:max_items] if isinstance(v, list) else v) for k, v in obj.items()}
    return json.dumps(obj, ensure_ascii=False, indent=1)


def build_task_prompt(user_text: str, *, data_file: str = "", data_preview: str = "") -> str:
    """正式 prompt（vq-el4.2）：request 全文＋資料檔欄位與前 5 列＋verifier 清單與輸出格式。

    只含使用者原文與資料預覽；不含 hidden、scorer、手寫 requirements.json。
    """
    hints = "\n".join(
        f"- {name}：{VERIFIER_HINTS.get(name, '見 checks.py')}" for name in sorted(SUPPORTED_VERIFIERS)
    )
    examples = "\n".join(
        f"  {name}: {VERIFIER_PARAM_EXAMPLES[name]}" for name in sorted(VERIFIER_PARAM_EXAMPLES)
    )
    parts = [
        "你是需求擷取助手。只依下方使用者原文，抽出可用程式驗證的需求條目。",
        "輸出：一個 JSON 陣列（陣列外不要說明文字），每項欄位：",
        "id, quote, deliverable, verifier, params, description, required, kind；"
        "kind 只能取 explicit／assumption／preference（預設 explicit，不准自造其他值）。",
        "規則：",
        "1. quote 必須是使用者原文的逐字片段（逐字複製，不准改字、換序、改寫、自造）；拿不準寧可不收該條。",
        "2. verifier 只能選：",
        hints,
        "3. params 必須符合下方該 verifier 的範例形狀（欄位名、型別、巢狀結構逐字照範例，不准自創欄位名）：",
        examples,
        "   常見錯誤（任一觸及該條目即被判 unverified 或錯誤 FAIL）：",
        "   - identity、group_by、required_columns、numbers、aggregates、exclude、include 必須是 JSON 陣列，不准寫成單一字串；",
        "   - aggregates 每項必須是 {name, type, col?/expr?}，type 只能取 count / distinct / sum / mean / mean_skip_empty / max / min / count_if / ratio（去重計數一律寫 distinct，不寫 distinct_count）；numbers 每項必須是 {type, col?, label?}，type 只能取 count / distinct / sum / mean / max / min / pct_if；",
        "   - values 必須是 {欄位名: 值} 的物件，不是陣列；若欄位值由算式計算，必須寫成 {\"欄位名\": {\"expr\": \"a - b\", \"round\": 2}}（expr 內只准寫四則/比較算式，不准在 expr 字串內呼叫 round(...) 等函式，四捨五入一律寫在同物件的 \"round\": 2 欄位）；exclude/include 每項必須是 {col, op, value}，op 只能取 eq/ne/lt/le/gt/ge；",
        "   - input_json 若需讀取巢狀欄位（如 payload.duration_ms），必須在 params 附 flatten: [{\"path\": \"payload.duration_ms\", \"as\": \"duration_ms\", \"impute\": 0}] 並以 as 後的欄位名引用；",
        "   - recompute 必須是含 type 的物件，不准寫成字串：kv_recomputed 的 recompute.type 只能選 count_if（必帶 col, eq）、zcount3（必帶 col）、mean_int_col（必帶 col）、max_row_first（必帶 sel_col, out_col）、pearson2（必帶 col_a, col_b）、col_stats（必帶 col, stat；stat 只能取 mean/median/sd/skewness/kurtosis）、null_count（必帶 col）；plain_recomputed 的 recompute.type 只能選 mode_col（必帶 col，選填 where）、cond_rate（必帶 where, num_where）、unique_count（必帶 col，選填 where）、col_max（必帶 col，選填 where）、scheme_fee_avg（必帶 scheme, is_credit, amount）、group_ratio_stat（必帶 group_col, sum_col, num_where，選填 where/stat/out）、fee_ids_lookup（必帶 fees_file, merchants_file, merchant, year, month）；",
        "   - input_csv／input_json／data_file 必須是下方「附帶資料檔」列出的真實檔名（工作區相對路徑，不加 /app/ 前綴），不准猜檔名；",
        "   - deliverable 必須是原文出現的交付物檔案名（如 monthly_sales.csv 或 answer.txt，不加 /app/ 前綴），不准寫描述性短句（如「資料清洗後的行集」）；",
        "   - 原文含過濾/去重規則（如「排除 CANCELLED」、「重複只留第一筆」）時，每個重算條目的 params 都要自帶 exclude/dedup_by——params 逐條獨立、不繼承；dedup_by 是單一字串欄位名（如 \"order_id\"，不是陣列）；",
        "   - 重算需要派生欄位時（如 total_score = midterm_score * 0.4 + final_score * 0.6），先用 compute: [{\"name\": \"total_score\", \"expr\": \"midterm_score * 0.4 + final_score * 0.6\"}] 定義，再在 aggregates/numbers 裡引用；",
        "   - 分組鍵要轉換時（不分大小寫、空白歸類）用 group_normalize: {\"col\": {\"lower\": true, \"default\": \"unspecified\"}}；",
        "   - 原文說「空白剔除不計入平均」時用平均類型 mean_skip_empty（不是 mean）；",
        "   - 條件計數（如及格人數）用 aggregates 的 {\"name\": ..., \"type\": \"count_if\", \"expr\": \"total_score >= 60\"}；",
        "   - exclude/include 語義：exclude 的每個條件＝要排除的列，排除 X 就寫 {\"col\": ..., \"op\": \"eq\", \"value\": X}，不准把算子反寫成 ne；include 的每個條件＝要保留的列，value 可以是欄位名（欄位對欄位比較，如 {\"col\": \"current_stock\", \"op\": \"lt\", \"value\": \"safety_stock\"}）；",
        "   - 條件合併：rowset_filter／group_aggregate／summary_numbers 的 params 要描述該交付物套用「全部」條件（排除、去重、納入）後的最終行集——即使該條 quote 只提到其中一個條件，也要附上完整條件集（例如原文既有「排除 X」又有「選出 current_stock < safety_stock」，rowset_filter 就要 exclude 與 include 都寫）；同一交付物的多步過濾/去重/篩選要整合在同一個 rowset_filter 條目裡，不准每步拆成多個獨立條目造成行集缺漏；「只保留第一筆」類去重用 dedup_by: 欄位名字串；只附部分條件是錯的；",
        "   - 原文把某欄位定義為 X ÷ Y 的比率（如 sla_rate＝sla_met_count ÷ ticket_count）時，該欄位聚合必須是 {\"name\": \"sla_rate\", \"type\": \"ratio\", \"num\": \"sla_met_count\", \"den\": \"ticket_count\"}（num/den 引用同列其他聚合的名字）；用 count_if 表達比率是錯的；",
        "   - 原文說「輸出用 lower」或大小寫不分時，group_normalize 要對該交付物的全部分組欄位套 {\"lower\": true}（不只句中點名的那一個欄位）；",
        "   - rowset_filter 只用於行級交付物（每行＝一筆原始紀錄）；交付物是彙總表時改用對應的聚合 verifier 把過濾規則寫進去，不准對彙總表用 rowset_filter；",
        "   - 需要資料檔的 verifier（rowset_filter、group_aggregate、summary_numbers、monthly_*、summary_metrics_consistency、kv/plain_recomputed）若該任務沒有對應資料檔，該條目設 unverified=true。",
        "4. 無法用程式驗證的需求設 unverified=true，並在 description 說明原因。",
        "5. 不准發明使用者沒說的需求。",
    ]
    if data_file:
        parts += ["", f"附帶資料檔：{data_file}（欄位與前幾列／項，僅供判斷欄位名稱）：", data_preview]
    parts += ["", "使用者原文：", user_text]
    return "\n".join(parts)


def _find_manifest_question(t_dir: pathlib.Path, task_id: str) -> str:
    """當任務目錄無 request.md 時，向父層搜尋 *manifest*.json 內的公開題目 question。"""
    curr = t_dir.resolve()
    for _ in range(4):
        curr = curr.parent
        if not curr.is_dir():
            break
        for mf in sorted(curr.glob("*manifest*.json")):
            try:
                data = json.loads(mf.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(data, dict):
                continue
            for d in data.get("drafts", []):
                if not isinstance(d, dict):
                    continue
                if d.get("id") == task_id or str(d.get("task_dir", "")).endswith(f"/{task_id}/task"):
                    q = str(d.get("question") or "").strip()
                    if q:
                        return q
    return ""


def _resolve_task_context(request_md: str | pathlib.Path) -> tuple[pathlib.Path, str, str]:
    """回傳 (t_dir, task_id, user_text)。支援 request.md、contract.md 與父層 manifest question。"""
    p = pathlib.Path(request_md)
    t_dir = p if p.is_dir() else p.parent
    req_file = t_dir / "request.md" if p.is_dir() else p
    task_id = t_dir.parent.name if t_dir.name == "task" and t_dir.parent.name else t_dir.name

    text_parts: list[str] = []
    if req_file.is_file():
        text_parts.append(req_file.read_text(encoding="utf-8").strip())
    else:
        q = _find_manifest_question(t_dir, task_id)
        if q:
            text_parts.append(q)
    contract_md = t_dir / "contract.md"
    if contract_md.is_file() and contract_md.resolve() != req_file.resolve():
        c_text = contract_md.read_text(encoding="utf-8").strip()
        if c_text and c_text not in text_parts:
            text_parts.append(c_text)
    return t_dir, task_id, "\n\n".join(part for part in text_parts if part)


def _discover_data_preview(t_dir: pathlib.Path) -> tuple[str, str]:
    """探索任務目錄頂層或 data/ 子目錄的資料檔（排除 requirements.json），回傳 (data_file, data_preview)。"""
    csvs = sorted(t_dir.glob("*.csv"))
    if csvs:
        return csvs[0].name, csv_preview(csvs[0].read_text(encoding="utf-8"))
    jsons = sorted(p for p in t_dir.glob("*.json") if p.name != "requirements.json")
    if jsons:
        return jsons[0].name, json_preview(jsons[0].read_text(encoding="utf-8"))
    data_sub = t_dir / "data"
    if data_sub.is_dir():
        sub_files = sorted(
            p
            for p in data_sub.iterdir()
            if p.is_file() and p.suffix.lower() in (".csv", ".json") and p.name != "requirements.json"
        )
        if sub_files:
            rel_names = [f"data/{p.name}" for p in sub_files]
            previews: list[str] = []
            for p in sub_files:
                rel = f"data/{p.name}"
                raw_txt = p.read_text(encoding="utf-8")
                pv = csv_preview(raw_txt) if p.suffix.lower() == ".csv" else json_preview(raw_txt)
                previews.append(f"[{rel}]\n{pv}" if len(sub_files) > 1 else pv)
            return ", ".join(rel_names), "\n\n".join(previews)
    return "", ""


def run_task(
    request_md: str | pathlib.Path,
    *,
    model: str,
    client: ExtractClient,
    out_path: str | pathlib.Path,
) -> tuple[RequirementSet, ExtractReport]:
    """對真實任務目錄做一輪擷取：request.md（或 contract.md + manifest question）全文＋資料預覽 → client → 逐字/白名單檢查 → 寫結果。

    只讀公開題目與資料檔預覽；同目錄的 requirements.json、
    bad_*／good 等手寫需求與參考產物一律不讀、不進 prompt。
    """
    t_dir, task_id, user_text = _resolve_task_context(request_md)
    data_file, data_preview = _discover_data_preview(t_dir)
    prompt = build_task_prompt(user_text, data_file=data_file, data_preview=data_preview)
    req, report = extract_requirements(
        user_text=user_text, client=client, task_id=task_id,
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
    ap.add_argument("--task", required=True, help="任務目錄（含 request.md 或 contract.md 與資料檔）")
    ap.add_argument("--model", default="glm53", choices=("glm53", "glm53flash", "deepseek41"))
    ap.add_argument("--out", default=None, help="輸出 json（預設 ops/reqloop/extract/out/<task>.<model>.json）")
    ap.add_argument("--glm", default="glm", help="glm 指令路徑（測試可注入假指令）")
    a = ap.parse_args(argv)

    t_path = pathlib.Path(a.task)
    req_md = t_path / "request.md"
    contract_md = t_path / "contract.md"
    if not req_md.is_file() and not contract_md.is_file():
        print(f"error: 找不到 {req_md}", file=sys.stderr)
        return 2
    task_id = t_path.parent.name if t_path.name == "task" and t_path.parent.name else t_path.name
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
    trusted_deliverable: str | None = None,
) -> tuple[RequirementSet, ExtractReport]:
    """一輪擷取：組 prompt → client → 解析 → 驗證 → RequirementSet。

    fail-closed：client 例外或輸出無法解析 → 空 RequirementSet＋報告記錄，
    不丟例外、不當通過。build_prompt（vq-el4.2）可覆蓋預設 prompt。
    trusted_deliverable（D2、11-13 裁決第 2 條）：提供時每條目的 deliverable
    一律設為它、模型原字串只留紀錄在 deliverable_claimed；None＝舊行為。
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
    req_set, report = build_requirement_set(task_id, raw_items, user_text)
    if trusted_deliverable is not None:
        # D2：trusted 值由呼叫方以 trusted_deliverable_from_contract 得出（原文
        # 點名的唯一非輸入輸出檔）；套用後 deliverable 不再是模型自報。
        req_set, report = _apply_trusted_deliverable(
            req_set, report, trusted_deliverable, user_text)
    return req_set, report


if __name__ == "__main__":
    raise SystemExit(main())
