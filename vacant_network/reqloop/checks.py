"""
vacant_network.reqloop.checks
內容重算檢查器（Recompute Checkers）。

責任：
- 對能執行的條件，用程式從原始資料重算，再跟交付物比。
- 嚴格重算：篩選、去重、排序依據、月份邊界、摘要數字與結果表一致。
- 失敗時提供具體反例（counterexamples），作為只修缺口之證據。
- 沒有可靠重算檢查的條目回傳 UNKNOWN，不准以自評代替。
"""

from __future__ import annotations

import ast
import csv
import datetime
import json
import math
import pathlib
import re
from collections import Counter
from typing import Any

from vacant_network.intake.verifiers import ClaimResult
from vacant_network.reqloop.requirements import RequirementItem, RequirementSet

VERIFIER_VERSION = "0.1.0"


def _clean_str(val: Any) -> str:
    return str(val).strip() if val is not None else ""


def _parse_float(val: Any) -> float:
    if val is None:
        return 0.0
    s = str(val).strip().replace("$", "").replace(",", "").replace("¥", "").replace("元", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _parse_date(val: Any) -> datetime.date | None:
    s = _clean_str(val)
    if not s:
        return None
    # 支援 YYYY-MM-DD 或 YYYY/MM/DD 或含有時間的 ISO 格式
    s = s.split("T")[0].split(" ")[0]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def read_csv_rows(path: pathlib.Path) -> list[dict[str, str]]:
    """讀取 CSV 檔案成字典列表，保留欄位名稱小寫標準化。"""
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return []
        cleaned_fieldnames = [c.strip().lower() for c in reader.fieldnames]
        rows = []
        for r in reader:
            row_dict = {}
            for orig_k, v in r.items():
                if orig_k is not None:
                    row_dict[orig_k.strip().lower()] = v.strip() if v is not None else ""
            rows.append(row_dict)
        return rows


def check_csv_structure(
    deliverable_dir: pathlib.Path,
    item: RequirementItem,
) -> ClaimResult:
    """檢查交付物 CSV 是否存在且包含指定欄位。"""
    csv_file = deliverable_dir / item.deliverable
    if not csv_file.is_file():
        return ClaimResult(
            claim_id=item.id,
            status="FAIL",
            detail=f"交付物檔案不存在: {item.deliverable}",
            evidence={"missing_file": item.deliverable},
            verifier=item.verifier,
            verifier_version=VERIFIER_VERSION,
            required=item.required,
            authority=item.authority,
        )

    rows = read_csv_rows(csv_file)
    if not rows:
        return ClaimResult(
            claim_id=item.id,
            status="FAIL",
            detail=f"交付物 CSV 為空或無標題列: {item.deliverable}",
            evidence={"empty_csv": item.deliverable},
            verifier=item.verifier,
            verifier_version=VERIFIER_VERSION,
            required=item.required,
            authority=item.authority,
        )

    required_cols = [c.lower() for c in item.params.get("required_columns", [])]
    existing_cols = list(rows[0].keys())
    missing_cols = [c for c in required_cols if c not in existing_cols]

    if missing_cols:
        return ClaimResult(
            claim_id=item.id,
            status="FAIL",
            detail=f"交付物 CSV 缺少必要欄位: {missing_cols}",
            evidence={"missing_columns": missing_cols, "existing_columns": existing_cols},
            verifier=item.verifier,
            verifier_version=VERIFIER_VERSION,
            required=item.required,
            authority=item.authority,
        )

    return ClaimResult(
        claim_id=item.id,
        status="PASS",
        detail=f"交付物 CSV 結構驗證通過，包含所有必要欄位: {required_cols}",
        evidence={"row_count": len(rows), "columns": existing_cols},
        verifier=item.verifier,
        verifier_version=VERIFIER_VERSION,
        required=item.required,
        authority=item.authority,
    )


def recompute_orders_monthly(
    task_dir: pathlib.Path,
    params: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[tuple[str, float, int]]], list[dict[str, Any]]]:
    """
    從原始訂單資料嚴格重算月度指標與商品銷售排行。
    回傳：
    - monthly_metrics: { "2026-09": {"orders_count": N, "net_sales": float}, ... }
    - monthly_top_products: { "2026-09": [ (product, net_sales, count), ... ], ... }
    - raw_filtered_rows: 過濾去重後的列
    """
    input_file = task_dir / params.get("input_csv", "orders.csv")
    rows = read_csv_rows(input_file)

    exclude_status = set(s.upper() for s in params.get("exclude_status", ["CANCELLED"]))
    dedup_by = params.get("dedup_by", "order_id").lower()
    date_col = params.get("date_col", "order_date").lower()
    amount_col = params.get("amount_col", "net_amount").lower()
    product_col = params.get("product_col", "product_name").lower()
    status_col = params.get("status_col", "status").lower()

    seen_ids = set()
    filtered_rows = []

    for r in rows:
        # 1. 排除指定狀態
        status_val = r.get(status_col, "").upper()
        if status_val in exclude_status:
            continue
        # 2. 去重（依 order_id）
        order_id = r.get(dedup_by, "")
        if order_id:
            if order_id in seen_ids:
                continue
            seen_ids.add(order_id)
        filtered_rows.append(r)

    # 3. 按月份聚合指標
    monthly_metrics: dict[str, dict[str, Any]] = {}
    monthly_products: dict[str, dict[str, dict[str, Any]]] = {}

    for r in filtered_rows:
        dt = _parse_date(r.get(date_col))
        if dt is None:
            continue
        month_key = dt.strftime("%Y-%m")
        amt = _parse_float(r.get(amount_col))
        prod = r.get(product_col, "unknown")

        if month_key not in monthly_metrics:
            monthly_metrics[month_key] = {"orders_count": 0, "net_sales": 0.0}
            monthly_products[month_key] = {}

        monthly_metrics[month_key]["orders_count"] += 1
        monthly_metrics[month_key]["net_sales"] += amt

        if prod not in monthly_products[month_key]:
            monthly_products[month_key][prod] = {"net_sales": 0.0, "count": 0}
        monthly_products[month_key][prod]["net_sales"] += amt
        monthly_products[month_key][prod]["count"] += 1

    # 4. 排序商品（按淨銷售額 net_sales 由大到小排序）
    monthly_top: dict[str, list[tuple[str, float, int]]] = {}
    for m, prods in monthly_products.items():
        sorted_prods = sorted(
            [(p, d["net_sales"], d["count"]) for p, d in prods.items()],
            key=lambda x: x[1],
            reverse=True,
        )
        monthly_top[m] = sorted_prods

    return monthly_metrics, monthly_top, filtered_rows


def check_monthly_sales_metrics(
    task_dir: pathlib.Path,
    deliverable_dir: pathlib.Path,
    item: RequirementItem,
) -> ClaimResult:
    """檢查交付物 CSV 中的各月訂單數與淨銷售額是否與原始資料重算一致。"""
    deliv_file = deliverable_dir / item.deliverable
    deliv_rows = read_csv_rows(deliv_file)
    if not deliv_rows:
        return ClaimResult(
            claim_id=item.id,
            status="FAIL",
            detail=f"交付物不存在或為空: {item.deliverable}",
            evidence={"missing_file": item.deliverable},
            verifier=item.verifier,
            verifier_version=VERIFIER_VERSION,
            required=item.required,
            authority=item.authority,
        )

    expected_metrics, _, _ = recompute_orders_monthly(task_dir, item.params)
    atol = float(item.params.get("atol", 0.01))

    # 尋找交付物中的月份欄位
    deliv_by_month = {}
    for r in deliv_rows:
        m = r.get("month") or r.get("order_month") or r.get("date_month")
        if m:
            deliv_by_month[m.strip()] = r

    expected_months = item.params.get("expected_months", sorted(expected_metrics.keys()))
    mismatches = []
    counterexamples = []

    for m in expected_months:
        if m not in deliv_by_month:
            mismatches.append(f"缺少月份 {m} 的數據")
            continue
        actual_row = deliv_by_month[m]
        expected_cnt = expected_metrics.get(m, {}).get("orders_count", 0)
        expected_sales = expected_metrics.get(m, {}).get("net_sales", 0.0)

        # 找訂單數字段
        actual_cnt_str = actual_row.get("orders_count") or actual_row.get("order_count") or actual_row.get("count")
        actual_cnt = int(_parse_float(actual_cnt_str)) if actual_cnt_str else None

        # 找淨額字段
        actual_sales_str = actual_row.get("net_sales") or actual_row.get("sales") or actual_row.get("total_sales")
        actual_sales = _parse_float(actual_sales_str) if actual_sales_str else None

        if actual_cnt is None or actual_cnt != expected_cnt:
            mismatches.append(
                f"月份 {m} 訂單數不符: 預期 {expected_cnt}，交付物為 {actual_cnt}"
            )
            counterexamples.append({
                "month": m,
                "field": "orders_count",
                "expected": expected_cnt,
                "actual": actual_cnt,
                "reason": "可能包含取消訂單、重複訂單未去重，或跨月邊界歸屬錯誤",
            })

        if actual_sales is None or abs(actual_sales - expected_sales) > atol:
            mismatches.append(
                f"月份 {m} 淨銷售額不符: 預期 {expected_sales:.2f}，交付物為 {actual_sales}"
            )
            counterexamples.append({
                "month": m,
                "field": "net_sales",
                "expected": expected_sales,
                "actual": actual_sales,
                "diff": (actual_sales - expected_sales) if actual_sales is not None else None,
                "reason": "可能未扣除取消單、重複計入重複訂單、或金額加總公式錯誤",
            })

    if mismatches:
        return ClaimResult(
            claim_id=item.id,
            status="FAIL",
            detail="; ".join(mismatches),
            evidence={"counterexamples": counterexamples, "expected_metrics": expected_metrics},
            verifier=item.verifier,
            verifier_version=VERIFIER_VERSION,
            required=item.required,
            authority=item.authority,
        )

    return ClaimResult(
        claim_id=item.id,
        status="PASS",
        detail="月度訂單數與淨銷售額重算核對完全一致",
        evidence={"recomputed_metrics": expected_metrics},
        verifier=item.verifier,
        verifier_version=VERIFIER_VERSION,
        required=item.required,
        authority=item.authority,
    )


def check_monthly_top_products(
    task_dir: pathlib.Path,
    deliverable_dir: pathlib.Path,
    item: RequirementItem,
) -> ClaimResult:
    """檢查各月份前 N 名商品排行是否嚴格依淨銷售額重算一致。"""
    deliv_file = deliverable_dir / item.deliverable
    deliv_rows = read_csv_rows(deliv_file)
    if not deliv_rows:
        return ClaimResult(
            claim_id=item.id,
            status="FAIL",
            detail=f"交付物不存在或為空: {item.deliverable}",
            evidence={"missing_file": item.deliverable},
            verifier=item.verifier,
            verifier_version=VERIFIER_VERSION,
            required=item.required,
            authority=item.authority,
        )

    _, expected_top, _ = recompute_orders_monthly(task_dir, item.params)
    top_n = int(item.params.get("top_n", 3))

    deliv_by_month = {}
    for r in deliv_rows:
        m = r.get("month") or r.get("order_month")
        if m:
            deliv_by_month[m.strip()] = r

    expected_months = item.params.get("expected_months", sorted(expected_top.keys()))
    mismatches = []
    counterexamples = []

    for m in expected_months:
        if m not in deliv_by_month:
            mismatches.append(f"缺少月份 {m} 的排行數據")
            continue
        actual_row = deliv_by_month[m]
        expected_list = [p[0] for p in expected_top.get(m, [])[:top_n]]

        # 提取交付物中的 top 商品
        actual_list = []
        for i in range(1, top_n + 1):
            val = actual_row.get(f"top_{i}_product") or actual_row.get(f"top_{i}")
            if val:
                actual_list.append(val.strip())

        if len(actual_list) < len(expected_list):
            mismatches.append(f"月份 {m} 前 {top_n} 名商品未完整提供: 預期 {len(expected_list)} 個，實有 {len(actual_list)} 個")
            counterexamples.append({
                "month": m,
                "expected": expected_list,
                "actual": actual_list,
                "reason": "缺少排名欄位或未填滿前三名",
            })
            continue

        if actual_list != expected_list:
            mismatches.append(
                f"月份 {m} 商品排行錯誤: 預期 {expected_list}，交付物為 {actual_list}"
            )
            # 附上各商品的重算金額與筆數反例說明
            prod_info = {p[0]: {"sales": p[1], "count": p[2]} for p in expected_top.get(m, [])}
            counterexamples.append({
                "month": m,
                "expected_top": expected_list,
                "actual_top": actual_list,
                "prod_details": prod_info,
                "reason": "排序依據錯誤（例如誤用訂單筆數/數量排序，而非使用者要求的淨銷售額排序）",
            })

    if mismatches:
        return ClaimResult(
            claim_id=item.id,
            status="FAIL",
            detail="; ".join(mismatches),
            evidence={"counterexamples": counterexamples},
            verifier=item.verifier,
            verifier_version=VERIFIER_VERSION,
            required=item.required,
            authority=item.authority,
        )

    return ClaimResult(
        claim_id=item.id,
        status="PASS",
        detail=f"各月份前 {top_n} 名商品排行（依淨銷售額）重算核對完全一致",
        evidence={"expected_top": {m: [p[0] for p in prods[:top_n]] for m, prods in expected_top.items()}},
        verifier=item.verifier,
        verifier_version=VERIFIER_VERSION,
        required=item.required,
        authority=item.authority,
    )


def check_summary_metrics_consistency(
    task_dir: pathlib.Path,
    deliverable_dir: pathlib.Path,
    item: RequirementItem,
) -> ClaimResult:
    """檢查繁體中文文字報告 summary.md 中的合計淨額等數字是否與重算完全一致。"""
    deliv_file = deliverable_dir / item.deliverable
    if not deliv_file.is_file():
        return ClaimResult(
            claim_id=item.id,
            status="FAIL",
            detail=f"摘要文字報告不存在: {item.deliverable}",
            evidence={"missing_file": item.deliverable},
            verifier=item.verifier,
            verifier_version=VERIFIER_VERSION,
            required=item.required,
            authority=item.authority,
        )

    content = deliv_file.read_text(encoding="utf-8")
    expected_metrics, _, _ = recompute_orders_monthly(task_dir, item.params)
    total_expected_sales = sum(m["net_sales"] for m in expected_metrics.values())

    # 搜尋文字中的金額數字，允許常見格式如 12345.67 或 12,345.67 或 $12345
    # 將整篇內容中出現的數字與 total_expected_sales 比對
    atol = float(item.params.get("atol", 0.05))
    number_pattern = re.compile(r"[\$¥]?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)")
    found_numbers = []
    for match in number_pattern.finditer(content):
        val = _parse_float(match.group(1))
        if val > 0:
            found_numbers.append(val)

    # 檢查是否含有精確總銷售額
    matched = any(abs(num - total_expected_sales) <= atol for num in found_numbers)

    if not matched:
        return ClaimResult(
            claim_id=item.id,
            status="FAIL",
            detail=f"文字摘要未包含正確的兩月合計淨銷售總額 {total_expected_sales:.2f}",
            evidence={
                "expected_total_sales": total_expected_sales,
                "found_numbers_in_summary": found_numbers[:10],
                "reason": "摘要中的數字抄錯、或誤算了包含取消訂單的銷售額",
            },
            verifier=item.verifier,
            verifier_version=VERIFIER_VERSION,
            required=item.required,
            authority=item.authority,
        )

    return ClaimResult(
        claim_id=item.id,
        status="PASS",
        detail=f"文字摘要中的合計淨銷售額核對正確 ({total_expected_sales:.2f})",
        evidence={"expected_total_sales": total_expected_sales},
        verifier=item.verifier,
        verifier_version=VERIFIER_VERSION,
        required=item.required,
        authority=item.authority,
    )


# ---------------------------------------------------------------------------
# 通用重算核心（rowset_filter / group_aggregate / summary_numbers 共用）
# ---------------------------------------------------------------------------

class UnknownSource(ValueError):
    """原始輸入缺失或格式不可解析＝看不到，依規則回 UNKNOWN。"""


class UnsafeExpressionError(ValueError):
    """運算式含不允許語法、未知欄位、或值不可解析＝無可靠重算能力。"""


_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod)
_ALLOWED_CMPS = (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)
_ALLOWED_UNARY = (ast.UAdd, ast.USub)

# 注意：千位分組選項必須「至少一個 ,ddd」，否則 4502.24 會被拆成 450 + 2.24。
_NUMBER_RE = re.compile(
    r"[\$¥]?\s*([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)"
)


def _to_num(value: Any) -> float:
    if isinstance(value, bool):
        raise UnsafeExpressionError("bool 不是數字")
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace("$", "").replace(",", "").replace("¥", "").replace("元", "")
    if s == "":
        raise UnsafeExpressionError("空白值不可作為數字")
    try:
        return float(s)
    except ValueError as e:
        raise UnsafeExpressionError(f"不可解析為數字: {value!r}") from e


def safe_eval_expr(expr: str, row: dict[str, Any]) -> Any:
    """安全運算式求值：只允許常數、欄位名、四則/整除/取餘、單一比較、and/or。

    禁止函式呼叫、屬性、下標、字串運算等一切其他節點；未知欄位或值不可解析
    一律拋 UnsafeExpressionError（呼叫端轉為 UNKNOWN，不得假裝 PASS/FAIL）。
    """
    if not isinstance(expr, str) or not expr.strip():
        raise UnsafeExpressionError("運算式為空")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise UnsafeExpressionError(f"運算式語法錯誤: {e.msg}") from e

    def ev(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                return node.value
            if isinstance(node.value, str):
                return node.value
            raise UnsafeExpressionError(f"不允許的常數: {node.value!r}")
        if isinstance(node, ast.Name):
            if node.id in row:
                return row[node.id]
            raise UnsafeExpressionError(f"未知欄位: {node.id}")
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
            a, b = _to_num(ev(node.left)), _to_num(ev(node.right))
            op = type(node.op)
            if op is ast.Add:
                return a + b
            if op is ast.Sub:
                return a - b
            if op is ast.Mult:
                return a * b
            if b == 0:
                raise UnsafeExpressionError("除以零")
            if op is ast.Div:
                return a / b
            if op is ast.FloorDiv:
                return a // b
            return a % b
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY:
            v = _to_num(ev(node.operand))
            return v if isinstance(node.op, ast.UAdd) else -v
        if isinstance(node, ast.Compare):
            if len(node.ops) != 1 or len(node.comparators) != 1:
                raise UnsafeExpressionError("不支援鏈式比較")
            a_raw, b_raw = ev(node.left), ev(node.comparators[0])
            try:
                a, b = _to_num(a_raw), _to_num(b_raw)
            except UnsafeExpressionError:
                a, b = str(a_raw).strip().lower(), str(b_raw).strip().lower()
                op = type(node.ops[0])
                if op is ast.Eq:
                    return a == b
                if op is ast.NotEq:
                    return a != b
                raise UnsafeExpressionError("非數字不可用順序比較")
            op = type(node.ops[0])
            if op is ast.Eq:
                return a == b
            if op is ast.NotEq:
                return a != b
            if op is ast.Lt:
                return a < b
            if op is ast.LtE:
                return a <= b
            if op is ast.Gt:
                return a > b
            return a >= b
        if isinstance(node, ast.BoolOp):
            vals = [bool(ev(v)) for v in node.values]
            return all(vals) if isinstance(node.op, ast.And) else any(vals)
        raise UnsafeExpressionError(f"不允許的語法: {type(node).__name__}")

    return ev(tree)


def load_table(task_dir: pathlib.Path, params: dict[str, Any]) -> list[dict[str, Any]]:
    """依 params 讀原始資料（input_csv 或 input_json），再套用 flatten。"""
    if "input_csv" in params:
        p = task_dir / str(params["input_csv"])
        if not p.is_file():
            raise UnknownSource(f"原始輸入不存在: {params['input_csv']}")
        rows = read_csv_rows(p)
        if not rows:
            raise UnknownSource(f"原始輸入為空: {params['input_csv']}")
    elif "input_json" in params:
        p = task_dir / str(params["input_json"])
        if not p.is_file():
            raise UnknownSource(f"原始輸入不存在: {params['input_json']}")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise UnknownSource(f"原始輸入 JSON 解析失敗: {e.msg}") from e
        if not isinstance(data, list) or not data or not all(isinstance(e, dict) for e in data):
            raise UnknownSource("input_json 必須是非空的物件列表")
        rows = [dict(e) for e in data]
    else:
        raise UnknownSource("params 缺少 input_csv / input_json")
    return apply_flatten(rows, params.get("flatten", []) or [])


def apply_flatten(rows: list[dict[str, Any]], specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把 JSON 巢狀欄位（path=a.b.c）攤平到 row[as]；缺失依 impute 填補。"""
    for spec in specs:
        path = [p for p in str(spec.get("path", "")).split(".") if p]
        if not path:
            raise UnknownSource("flatten.path 缺失")
        as_name = str(spec.get("as", path[-1]))
        has_impute = "impute" in spec
        for row in rows:
            v: Any = row
            for part in path:
                v = v.get(part) if isinstance(v, dict) else None
            row[as_name] = spec["impute"] if (v is None and has_impute) else v
    return rows


def _cond_holds(row: dict[str, Any], cond: dict[str, Any]) -> bool:
    col = str(cond.get("col", "")).strip().lower()
    op = str(cond.get("op", "eq")).strip().lower()
    value = cond.get("value")
    left_raw = row.get(col, "")
    # value 若同時是該列的欄位名＝欄位對欄位比較（如 current_stock < safety_stock）
    if isinstance(value, str) and value in row:
        right_raw: Any = row[value]
    else:
        right_raw = value
    try:
        a, b = _to_num(left_raw), _to_num(right_raw)
    except UnsafeExpressionError:
        a = str(left_raw).strip().lower()
        b = str(right_raw).strip().lower()
    if op == "eq":
        return a == b
    if op == "ne":
        return a != b
    if op == "lt":
        return a < b
    if op == "le":
        return a <= b
    if op == "gt":
        return a > b
    if op == "ge":
        return a >= b
    raise UnknownSource(f"未知比較算子: {op}")


def apply_pipeline(rows: list[dict[str, Any]], params: dict[str, Any]) -> list[dict[str, Any]]:
    """exclude → dedup_by（保留第一筆）→ include。"""
    for cond in params.get("exclude", []) or []:
        rows = [r for r in rows if not _cond_holds(r, cond)]
    dedup_by = params.get("dedup_by")
    if dedup_by:
        key = str(dedup_by).strip().lower()
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for r in rows:
            k = str(r.get(key, "")).strip()
            if k:
                if k in seen:
                    continue
                seen.add(k)
            out.append(r)
        rows = out
    for cond in params.get("include", []) or []:
        rows = [r for r in rows if _cond_holds(r, cond)]
    return rows


def apply_compute(rows: list[dict[str, Any]], params: dict[str, Any]) -> list[dict[str, Any]]:
    """逐列計算派生欄位（compute: name + 安全運算式）。"""
    for spec in params.get("compute", []) or []:
        name = str(spec.get("name", "")).strip()
        if not name:
            raise UnknownSource("compute.name 缺失")
        expr = str(spec.get("expr", ""))
        for r in rows:
            r[name] = safe_eval_expr(expr, r)
    return rows


def _fmt_key(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _fmt_val(v: Any) -> str:
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else repr(v)
    return str(v)


def _norm_group_key(value: Any, spec: Any) -> str:
    if value is None:
        s = ""
    elif isinstance(value, float) and value.is_integer():
        s = str(int(value))
    else:
        s = str(value).strip()
    if isinstance(spec, dict):
        if spec.get("lower"):
            s = s.lower()
        if spec.get("upper"):
            s = s.upper()
        if not s and spec.get("default") is not None:
            s = str(spec["default"])
    elif isinstance(spec, str):
        m = spec.strip().lower()
        if m == "lower":
            s = s.lower()
        elif m == "upper":
            s = s.upper()
    return s


def _agg_values(rows: list[dict[str, Any]], spec: dict[str, Any], skip_empty: bool) -> list[float]:
    expr = spec.get("expr")
    col = str(spec.get("col", "")).strip().lower()
    out: list[float] = []
    for r in rows:
        raw: Any = safe_eval_expr(str(expr), r) if expr else r.get(col, "")
        if raw is None:
            if skip_empty:
                continue
            raise UnsafeExpressionError(f"聚合遇到 null: {col or expr!r}")
        s = str(raw).strip()
        if s == "":
            if skip_empty:
                continue
            raise UnsafeExpressionError(f"聚合遇到空白值: {col or expr!r}")
        out.append(_to_num(raw))
    return out


def _result(item: RequirementItem, status: str, detail: str, evidence: dict[str, Any]) -> ClaimResult:
    return ClaimResult(
        claim_id=item.id,
        status=status,
        detail=detail,
        evidence=evidence,
        verifier=item.verifier,
        verifier_version=VERIFIER_VERSION,
        required=item.required,
        authority=item.authority,
    )


def check_rowset_filter(
    task_dir: pathlib.Path,
    deliverable_dir: pathlib.Path,
    item: RequirementItem,
) -> ClaimResult:
    """逐列重算：exclude→dedup→include 後，行集（identity）與逐欄值必須與交付物一致。"""
    params = dict(item.params)
    try:
        rows = apply_compute(apply_pipeline(load_table(task_dir, params), params), params)
        identity = [str(c).strip().lower() for c in params.get("identity", []) or []]
        if not identity:
            raise UnknownSource("rowset_filter.params.identity 缺失")
        values_spec: dict[str, Any] = params.get("values", {}) or {}
        expected: list[dict[str, Any]] = []
        for r in rows:
            er = {c: r.get(c, "") for c in identity}
            for out_col, spec in values_spec.items():
                if isinstance(spec, str):
                    er[out_col] = r.get(spec, "")
                elif isinstance(spec, dict) and "expr" in spec:
                    v = safe_eval_expr(str(spec["expr"]), r)
                    if "round" in spec:
                        v = round(float(v), int(spec["round"]))
                    er[out_col] = v
                else:
                    raise UnknownSource(f"values[{out_col}] 形式不明: {spec!r}")
            expected.append(er)
    except (UnknownSource, UnsafeExpressionError) as e:
        return _result(item, "UNKNOWN", f"無法可靠重算（{e}）；依規則不自評", {"reason": str(e)})

    deliv_file = deliverable_dir / item.deliverable
    if not deliv_file.is_file():
        return _result(item, "FAIL", f"交付物不存在: {item.deliverable}", {"missing_file": item.deliverable})
    deliv_rows = read_csv_rows(deliv_file)

    exp_keys = Counter(tuple(_fmt_key(r[c]) for c in identity) for r in expected)
    act_keys = Counter(tuple(_fmt_key(r.get(c, "")) for c in identity) for r in deliv_rows)
    if exp_keys != act_keys:
        only_exp = sorted(set(exp_keys) - set(act_keys))
        only_act = sorted(set(act_keys) - set(exp_keys))
        detail = "行集不符"
        if only_exp:
            detail += f"；缺少列 {[_fmt_key(k) for k in only_exp]}"
        if only_act:
            detail += f"；多出列 {[_fmt_key(k) for k in only_act]}"
        detail += f"（預期 {sum(exp_keys.values())} 列、交付物 {sum(act_keys.values())} 列）"
        return _result(
            item, "FAIL", detail,
            {"counterexamples": [{"kind": "rowset_mismatch",
                                  "expected_keys": [list(k) for k in only_exp],
                                  "actual_keys": [list(k) for k in only_act]}]},
        )

    atol = float(params.get("atol", 0.01))
    mismatches: list[str] = []
    counterexamples: list[dict[str, Any]] = []
    used: set[int] = set()
    for er in expected:
        key = tuple(_fmt_key(er[c]) for c in identity)
        idx = None
        for i, dr in enumerate(deliv_rows):
            if i in used:
                continue
            if tuple(_fmt_key(dr.get(c, "")) for c in identity) == key:
                idx = i
                break
        if idx is None:
            mismatches.append(f"列 {list(key)} 未找到對應交付行")
            continue
        used.add(idx)
        dr = deliv_rows[idx]
        for out_col, spec in values_spec.items():
            exp_v = er[out_col]
            act_raw = dr.get(out_col)
            act_raw = "" if act_raw is None else str(act_raw).strip()
            if isinstance(exp_v, str):
                if exp_v.strip() != act_raw:
                    mismatches.append(f"列 {list(key)} 欄 {out_col} 不符: 預期 {exp_v!r}，交付物為 {act_raw!r}")
                    counterexamples.append({"row": list(key), "field": out_col, "expected": exp_v, "actual": act_raw})
                continue
            try:
                act_v = _to_num(act_raw)
            except UnsafeExpressionError:
                mismatches.append(f"列 {list(key)} 欄 {out_col} 無法解析: 交付物為 {act_raw!r}")
                counterexamples.append({"row": list(key), "field": out_col, "expected": _fmt_val(exp_v), "actual": act_raw})
                continue
            if abs(act_v - float(exp_v)) > atol:
                mismatches.append(f"列 {list(key)} 欄 {out_col} 不符: 預期 {_fmt_val(exp_v)}，交付物為 {act_raw}")
                counterexamples.append({"row": list(key), "field": out_col,
                                       "expected": _fmt_val(exp_v), "actual": act_raw,
                                       "diff": act_v - float(exp_v)})
    if mismatches:
        return _result(item, "FAIL", "; ".join(mismatches), {"counterexamples": counterexamples})
    return _result(item, "PASS", f"{len(expected)} 列重算核對完全一致", {"recomputed_rows": len(expected)})


def check_group_aggregate(
    task_dir: pathlib.Path,
    deliverable_dir: pathlib.Path,
    item: RequirementItem,
) -> ClaimResult:
    """分組聚合重算：分組鍵（含 normalize）與各聚合值必須與交付物一致。"""
    params = dict(item.params)
    try:
        rows = apply_compute(apply_pipeline(load_table(task_dir, params), params), params)
        group_by = [str(g).strip().lower() for g in params.get("group_by", []) or []]
        if not group_by:
            raise UnknownSource("group_aggregate.params.group_by 缺失")
        agg_specs = params.get("aggregates", []) or []
        if not agg_specs:
            raise UnknownSource("group_aggregate.params.aggregates 缺失")
        norm = params.get("group_normalize", {}) or {}

        groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
        for r in rows:
            key = tuple(_norm_group_key(r.get(g), norm.get(g)) for g in group_by)
            groups.setdefault(key, []).append(r)

        expected: dict[tuple[str, ...], dict[str, Any]] = {}
        for key, grows in groups.items():
            vals: dict[str, Any] = {}
            for spec in agg_specs:
                t = str(spec.get("type", "")).strip().lower()
                name = str(spec.get("name", "")).strip()
                if not name:
                    raise UnknownSource("aggregate.name 缺失")
                if t == "count":
                    v: Any = float(len(grows))
                elif t == "distinct":
                    col = str(spec.get("col", "")).strip().lower()
                    v = float(len({str(r.get(col, "")).strip() for r in grows if str(r.get(col, "")).strip()}))
                elif t in ("sum", "mean", "mean_skip_empty"):
                    nums = _agg_values(grows, spec, skip_empty=(t == "mean_skip_empty"))
                    if t == "sum":
                        v = float(sum(nums))
                    else:
                        v = float(sum(nums) / len(nums)) if nums else None
                elif t in ("max", "min"):
                    nums = _agg_values(grows, spec, skip_empty=False)
                    if not nums:
                        raise UnknownSource(f"{t}: 組內無資料")
                    v = float(max(nums)) if t == "max" else float(min(nums))
                elif t == "count_if":
                    v = float(sum(1 for r in grows if bool(safe_eval_expr(str(spec.get("expr", "")), r))))
                elif t == "ratio":
                    continue  # 第二趟算
                else:
                    raise UnknownSource(f"未知聚合類型: {t}")
                vals[name] = v
            for spec in agg_specs:  # ratio 第二趟（依已算出的聚合名）
                if str(spec.get("type", "")).strip().lower() != "ratio":
                    continue
                name = str(spec.get("name", "")).strip()
                num = vals.get(str(spec.get("num", "")))
                den = vals.get(str(spec.get("den", "")))
                if num is None or den is None or float(den) == 0:
                    raise UnknownSource(f"ratio {name}: 分母為 0 或缺失")
                vals[name] = float(num) / float(den)
            for spec in agg_specs:
                name = str(spec.get("name", "")).strip()
                if "round" in spec and vals.get(name) is not None:
                    vals[name] = round(float(vals[name]), int(spec["round"]))
            expected[key] = vals
    except (UnknownSource, UnsafeExpressionError) as e:
        return _result(item, "UNKNOWN", f"無法可靠重算（{e}）；依規則不自評", {"reason": str(e)})

    deliv_file = deliverable_dir / item.deliverable
    if not deliv_file.is_file():
        return _result(item, "FAIL", f"交付物不存在: {item.deliverable}", {"missing_file": item.deliverable})
    deliv_rows = read_csv_rows(deliv_file)
    if not deliv_rows:
        return _result(item, "FAIL", f"交付物為空: {item.deliverable}", {"empty_csv": item.deliverable})
    missing_cols = [g for g in group_by if g not in deliv_rows[0]]
    if missing_cols:
        return _result(item, "FAIL", f"交付物缺少分組欄位: {missing_cols}", {"missing_columns": missing_cols})

    deliv_groups: dict[tuple[str, ...], list[dict[str, str]]] = {}
    for dr in deliv_rows:
        key = tuple(_norm_group_key(dr.get(g), norm.get(g)) for g in group_by)
        deliv_groups.setdefault(key, []).append(dr)

    exp_keys, act_keys = set(expected), set(deliv_groups)
    dup = [k for k in exp_keys & act_keys if len(deliv_groups[k]) != 1]
    if exp_keys != act_keys or dup:
        detail = "分組集不符"
        if exp_keys - act_keys:
            detail += f"；缺少組 {sorted(exp_keys - act_keys)}"
        if act_keys - exp_keys:
            detail += f"；多出組 {sorted(act_keys - exp_keys)}"
        if dup:
            detail += f"；重複組 {sorted(dup)}"
        return _result(
            item, "FAIL", detail,
            {"counterexamples": [{"kind": "group_mismatch",
                                  "expected_groups": [list(k) for k in sorted(exp_keys)],
                                  "actual_groups": [list(k) for k in sorted(act_keys)]}]},
        )

    atol = float(params.get("atol", 0.01))
    mismatches: list[str] = []
    counterexamples: list[dict[str, Any]] = []
    for key, vals in expected.items():
        dr = deliv_groups[key][0]
        for name, exp_v in vals.items():
            if name not in dr:
                mismatches.append(f"組 {list(key)} 缺欄 {name}")
                counterexamples.append({"group": list(key), "field": name, "expected": _fmt_val(exp_v), "actual": None})
                continue
            act_raw = "" if dr[name] is None else str(dr[name]).strip()
            if exp_v is None:
                if act_raw != "":
                    mismatches.append(f"組 {list(key)} 欄 {name} 預期空白，交付物為 {act_raw!r}")
                    counterexamples.append({"group": list(key), "field": name, "expected": None, "actual": act_raw})
                continue
            try:
                act_v = _to_num(act_raw)
            except UnsafeExpressionError:
                mismatches.append(f"組 {list(key)} 欄 {name} 無法解析: 交付物為 {act_raw!r}")
                counterexamples.append({"group": list(key), "field": name, "expected": _fmt_val(exp_v), "actual": act_raw})
                continue
            if abs(act_v - float(exp_v)) > atol:
                mismatches.append(f"組 {list(key)} 欄 {name} 不符: 預期 {_fmt_val(exp_v)}，交付物為 {act_raw}")
                counterexamples.append({"group": list(key), "field": name,
                                       "expected": _fmt_val(exp_v), "actual": act_raw,
                                       "diff": act_v - float(exp_v)})
    if mismatches:
        return _result(item, "FAIL", "; ".join(mismatches), {"counterexamples": counterexamples})
    return _result(item, "PASS", f"{len(expected)} 組聚合重算核對完全一致", {"recomputed_groups": len(expected)})


def check_summary_numbers(
    task_dir: pathlib.Path,
    deliverable_dir: pathlib.Path,
    item: RequirementItem,
) -> ClaimResult:
    """摘要文字中的每個指定數字必須與程式重算一致（文字裡找得到該數值才算數）。"""
    params = dict(item.params)
    try:
        rows = apply_compute(apply_pipeline(load_table(task_dir, params), params), params)
        numbers = params.get("numbers", []) or []
        if not numbers:
            raise UnknownSource("summary_numbers.params.numbers 缺失")
        expected: list[tuple[str, Any]] = []
        for n in numbers:
            t = str(n.get("type", "")).strip().lower()
            label = str(n.get("label", t))
            if t == "count":
                v: Any = float(len(rows))
            elif t == "distinct":
                col = str(n.get("col", "")).strip().lower()
                v = float(len({str(r.get(col, "")).strip() for r in rows if str(r.get(col, "")).strip()}))
            elif t in ("sum", "mean"):
                nums = _agg_values(rows, n, skip_empty=(t == "mean"))
                if t == "sum":
                    v = float(sum(nums))
                else:
                    v = float(sum(nums) / len(nums)) if nums else None
            elif t in ("max", "min"):
                nums = _agg_values(rows, n, skip_empty=False)
                if not nums:
                    raise UnknownSource(f"{t}: 無資料")
                v = float(max(nums)) if t == "max" else float(min(nums))
            elif t == "pct_if":
                total = len(rows)
                if total == 0:
                    raise UnknownSource("pct_if: 無資料")
                hits = sum(1 for r in rows if bool(safe_eval_expr(str(n.get("expr", "")), r)))
                v = 100.0 * hits / total
            else:
                raise UnknownSource(f"未知數字類型: {t}")
            if "round" in n and v is not None:
                v = round(float(v), int(n["round"]))
            expected.append((label, v))
    except (UnknownSource, UnsafeExpressionError) as e:
        return _result(item, "UNKNOWN", f"無法可靠重算（{e}）；依規則不自評", {"reason": str(e)})

    deliv_file = deliverable_dir / item.deliverable
    if not deliv_file.is_file():
        return _result(item, "FAIL", f"摘要文字報告不存在: {item.deliverable}", {"missing_file": item.deliverable})
    content = deliv_file.read_text(encoding="utf-8")
    atol = float(params.get("atol", 0.01))
    found: list[float] = []
    for m in _NUMBER_RE.finditer(content):
        try:
            found.append(float(m.group(1).replace(",", "")))
        except ValueError:
            continue

    mismatches: list[str] = []
    counterexamples: list[dict[str, Any]] = []
    for label, exp_v in expected:
        if exp_v is None:
            mismatches.append(f"{label} 重算結果為空，無法核對")
            counterexamples.append({"label": label, "expected": None})
            continue
        if not any(abs(x - float(exp_v)) <= atol for x in found):
            mismatches.append(f"摘要未包含正確的{label} {_fmt_val(exp_v)}")
            counterexamples.append({"label": label, "expected": _fmt_val(exp_v),
                                    "found_numbers_in_summary": found[:10]})
    if mismatches:
        return _result(item, "FAIL", "; ".join(mismatches), {"counterexamples": counterexamples})
    return _result(item, "PASS", "摘要各數字均與重算一致", {"recomputed": {l: _fmt_val(v) for l, v in expected}})


def check_tag_format(deliverable_dir: pathlib.Path, item: RequirementItem) -> ClaimResult:
    """檢查文字交付物中的格式化標籤（例如 @name[value]）。

    支援參數:
    - file: 檔案名稱（預設 "answer.txt"）
    - tag: 標籤名稱（例如 "mean_cases" 或 "null_entries_count"）
    - value_type: "integer" | "int" | "float" | "str"（預設 "str"）
    - min_value: 最小值限制（數值類型適用，選填）
    - max_value: 最大值限制（數值類型適用，選填）
    """
    file_name = item.params.get("file", "answer.txt")
    target_file = deliverable_dir / file_name
    if not target_file.is_file():
        return _result(
            item,
            "FAIL",
            f"交付物缺少指定檔案: {file_name}",
            {"missing_file": file_name},
        )

    tag = item.params.get("tag", "")
    val_type = item.params.get("value_type", "str").lower()

    try:
        content = target_file.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return _result(
            item,
            "FAIL",
            f"無法讀取交付物檔案 {file_name}: {e}",
            {"read_error": str(e)},
        )

    if not tag:
        return _result(item, "UNKNOWN", "未指定要檢查的 tag 名稱", {"missing_param": "tag"})

    pattern_correct = rf"@{re.escape(tag)}\[([^\]]*)\]"
    pattern_bracketless = rf"@{re.escape(tag)}([^\s\[\]\r\n]+)"

    m_correct = list(re.finditer(pattern_correct, content))
    m_bracketless = list(re.finditer(pattern_bracketless, content))

    if not m_correct:
        if m_bracketless:
            actual = m_bracketless[0].group(0)
            val = m_bracketless[0].group(1)
            return _result(
                item,
                "FAIL",
                f"標籤 @{tag} 格式不符：缺少方括號包裹值，找到 '{actual}'，預期格式為 @{tag}[<value>]",
                {"actual": actual, "extracted_raw": val, "expected_format": f"@{tag}[<value>]", "reason": "missing_brackets"},
            )
        return _result(
            item,
            "FAIL",
            f"交付物檔案 {file_name} 未包含必要標籤 @{tag}[...]",
            {"missing_tag": tag, "expected_format": f"@{tag}[<value>]"},
        )

    raw_val = m_correct[0].group(1).strip()

    if val_type in ("int", "integer"):
        if "." in raw_val:
            return _result(
                item,
                "FAIL",
                f"標籤 @{tag} 的值 '{raw_val}' 包含小數點，不符整數要求",
                {"actual": raw_val, "expected_type": "integer", "reason": "contains_decimal"},
            )
        try:
            int_val = int(raw_val)
        except ValueError:
            return _result(
                item,
                "FAIL",
                f"標籤 @{tag} 的值 '{raw_val}' 無法解析為整數",
                {"actual": raw_val, "expected_type": "integer"},
            )
        if "min_value" in item.params and int_val < item.params["min_value"]:
            return _result(
                item,
                "FAIL",
                f"標籤 @{tag} 的值 {int_val} 小於下限 {item.params['min_value']}",
                {"actual": int_val, "min_value": item.params["min_value"]},
            )
        if "max_value" in item.params and int_val > item.params["max_value"]:
            return _result(
                item,
                "FAIL",
                f"標籤 @{tag} 的值 {int_val} 大於上限 {item.params['max_value']}",
                {"actual": int_val, "max_value": item.params["max_value"]},
            )
    elif val_type == "float":
        try:
            flt_val = float(raw_val)
        except ValueError:
            return _result(
                item,
                "FAIL",
                f"標籤 @{tag} 的值 '{raw_val}' 無法解析為浮點數",
                {"actual": raw_val, "expected_type": "float"},
            )
        if "min_value" in item.params and flt_val < item.params["min_value"]:
            return _result(
                item,
                "FAIL",
                f"標籤 @{tag} 的值 {flt_val} 小於下限 {item.params['min_value']}",
                {"actual": flt_val, "min_value": item.params["min_value"]},
            )
        if "max_value" in item.params and flt_val > item.params["max_value"]:
            return _result(
                item,
                "FAIL",
                f"標籤 @{tag} 的值 {flt_val} 大於上限 {item.params['max_value']}",
                {"actual": flt_val, "max_value": item.params["max_value"]},
            )

    return _result(
        item,
        "PASS",
        f"標籤 @{tag}[{raw_val}] 符合指定格式及型別要求",
        {"tag": tag, "value": raw_val, "value_type": val_type},
    )


def run_requirement_checks(
    task_dir: str | pathlib.Path,
    req_set: RequirementSet,
    deliverable_dir: str | pathlib.Path,
) -> list[ClaimResult]:
    """執行 RequirementSet 中的所有重算檢查，回傳 ClaimResult 清單。"""
    t_dir = pathlib.Path(task_dir)
    d_dir = pathlib.Path(deliverable_dir)
    results: list[ClaimResult] = []

    for item in req_set.items:
        if item.unverified:
            results.append(
                ClaimResult(
                    claim_id=item.id,
                    status="UNKNOWN",
                    detail="此條目無可靠程式重算檢查器，依規則標為 UNKNOWN，不准以自評代替",
                    evidence={"unverified": True},
                    verifier=item.verifier,
                    verifier_version=VERIFIER_VERSION,
                    required=item.required,
                    authority=item.authority,
                )
            )
            continue

        vname = item.verifier
        if vname == "csv_structure":
            res = check_csv_structure(d_dir, item)
        elif vname == "monthly_sales_metrics":
            res = check_monthly_sales_metrics(t_dir, d_dir, item)
        elif vname == "monthly_top_products":
            res = check_monthly_top_products(t_dir, d_dir, item)
        elif vname == "summary_metrics_consistency":
            res = check_summary_metrics_consistency(t_dir, d_dir, item)
        elif vname == "rowset_filter":
            res = check_rowset_filter(t_dir, d_dir, item)
        elif vname == "group_aggregate":
            res = check_group_aggregate(t_dir, d_dir, item)
        elif vname == "summary_numbers":
            res = check_summary_numbers(t_dir, d_dir, item)
        elif vname == "tag_format":
            res = check_tag_format(d_dir, item)
        else:
            # 未知檢查器：依規則一律標記為 UNKNOWN，不得假裝 PASS
            results.append(
                ClaimResult(
                    claim_id=item.id,
                    status="UNKNOWN",
                    detail=f"未知檢查器 {vname!r}，依規則不准自評，標記為 UNKNOWN",
                    evidence={"unknown_verifier": vname},
                    verifier=vname,
                    verifier_version=VERIFIER_VERSION,
                    required=item.required,
                    authority=item.authority,
                )
            )
            continue

        results.append(res)

    return results
