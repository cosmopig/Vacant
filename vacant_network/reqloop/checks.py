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
import calendar
import csv
import datetime
import json
import math
import pathlib
import re
from collections import Counter
from typing import Any, Sequence

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
        v = float(s)
    except ValueError:
        return 0.0
    return v if math.isfinite(v) else 0.0


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


def _strict_table_pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """表格 JSON 物件解析 hook：鍵小寫標準化，且拒絕同名或大小寫重複鍵。"""
    out: dict[str, Any] = {}
    for k, v in pairs:
        norm_k = str(k).strip().lower()
        if norm_k in out:
            raise ValueError(f"duplicate or case-colliding JSON key: {k!r}")
        out[norm_k] = v
    return out


def read_table_deliverable(path: pathlib.Path) -> list[dict[str, Any]]:
    """讀取表格交付物：.json 接受物件陣列或含 records/rows/data 物件陣列之物件；其餘副檔名走 read_csv_rows。

    鍵小寫標準化（與 CSV 同口徑）；值保留 JSON 原生型別（下游統一經 str() 轉換比對）。
    JSON 解析失敗、含重複鍵、空物件、或陣列混入非物件元素時皆回傳空列表（絕不冒稱 PASS）。
    """
    if path.suffix.lower() != ".json":
        return read_csv_rows(path)
    if not path.is_file():
        return []
    try:
        data: Any = json.loads(
            path.read_text(encoding="utf-8-sig"),
            object_pairs_hook=_strict_table_pairs_hook,
        )
    except ValueError:
        return []
    if isinstance(data, dict):
        if not data:
            return []
        for key in ("records", "rows", "data"):
            if key in data:
                if not isinstance(data[key], list):
                    return []
                data = data[key]
                break
        else:
            data = [data]
    if not isinstance(data, list) or not data:
        return []
    rows: list[dict[str, Any]] = []
    for r in data:
        if not isinstance(r, dict) or not r:
            return []
        rows.append(r)
    return rows


def resolve_deliverable_path(deliverable_dir: pathlib.Path, deliverable: str) -> pathlib.Path:
    """安全解析交付物路徑：剝除 /app/、./ 或前導斜線，確保路徑錨定於 deliverable_dir（防 docker 容器路徑穿透）。"""
    d = str(deliverable).strip()
    if d.startswith("/app/"):
        d = d[len("/app/"):]
    elif d.startswith("./"):
        d = d[2:]
    elif d.startswith("/"):
        d = d.lstrip("/")
    return deliverable_dir / d


def check_csv_structure(
    deliverable_dir: pathlib.Path,
    item: RequirementItem,
) -> ClaimResult:
    """檢查交付物表格（CSV 或 JSON 陣列）是否存在且包含指定欄位。"""
    csv_file = resolve_deliverable_path(deliverable_dir, item.deliverable)
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

    rows = read_table_deliverable(csv_file)
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

    required_cols = [str(c).strip().lower() for c in item.params.get("required_columns", [])]
    existing_cols = [k for k in rows[0].keys() if all(k in r for r in rows)]
    missing_cols = [c for c in required_cols if not all(c in r for r in rows)]

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
    dedup_by = _dedup_by_field(params) or "order_id"
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
    deliv_file = resolve_deliverable_path(deliverable_dir, item.deliverable)
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

    input_csv = str(item.params.get("input_csv", "orders.csv")).strip()
    if not input_csv or not (task_dir / input_csv).is_file():
        return _result(
            item,
            "UNKNOWN",
            f"原始輸入不存在: {input_csv or 'orders.csv'}；無法可靠重算，依規則標 UNKNOWN",
            {"reason": f"missing_input_csv:{input_csv or 'orders.csv'}"},
        )
    expected_metrics, _, _ = recompute_orders_monthly(task_dir, item.params)
    expected_months = item.params.get("expected_months", sorted(expected_metrics.keys()))
    if not expected_metrics or not isinstance(expected_months, list) or not expected_months:
        return _result(
            item,
            "UNKNOWN",
            "原始資料重算無有效月份指標；無法可靠重算，依規則標 UNKNOWN",
            {"reason": "empty_expected_months"},
        )
    atol = float(item.params.get("atol", 0.01))
    include_expected = bool(item.params.get("expected_in_evidence", True))

    # 尋找交付物中的月份欄位
    deliv_by_month = {}
    for r in deliv_rows:
        m = r.get("month") or r.get("order_month") or r.get("date_month")
        if m:
            deliv_by_month[m.strip()] = r

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
            if include_expected:
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
            else:
                mismatches.append(
                    f"月份 {m} 訂單數與原始資料重算不符: 交付物為 {actual_cnt}"
                )
                counterexamples.append({
                    "month": m,
                    "field": "orders_count",
                    "actual": actual_cnt,
                    "problem": "mismatch_with_recomputation",
                    "expected_in_evidence": False,
                    "reason": "可能包含取消訂單、重複訂單未去重，或跨月邊界歸屬錯誤",
                })

        if actual_sales is None or abs(actual_sales - expected_sales) > atol:
            if include_expected:
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
            else:
                mismatches.append(
                    f"月份 {m} 淨銷售額與原始資料重算不符: 交付物為 {actual_sales}"
                )
                counterexamples.append({
                    "month": m,
                    "field": "net_sales",
                    "actual": actual_sales,
                    "problem": "mismatch_with_recomputation",
                    "expected_in_evidence": False,
                    "reason": "可能未扣除取消單、重複計入重複訂單、或金額加總公式錯誤",
                })

    if mismatches:
        ev_fail: dict[str, Any] = {"counterexamples": counterexamples}
        if include_expected:
            ev_fail["expected_metrics"] = expected_metrics
        else:
            ev_fail["expected_in_evidence"] = False
        return ClaimResult(
            claim_id=item.id,
            status="FAIL",
            detail="; ".join(mismatches),
            evidence=ev_fail,
            verifier=item.verifier,
            verifier_version=VERIFIER_VERSION,
            required=item.required,
            authority=item.authority,
        )

    ev_pass: dict[str, Any] = (
        {"recomputed_metrics": expected_metrics}
        if include_expected
        else {"expected_in_evidence": False}
    )
    return ClaimResult(
        claim_id=item.id,
        status="PASS",
        detail="月度訂單數與淨銷售額重算核對完全一致",
        evidence=ev_pass,
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
    deliv_file = resolve_deliverable_path(deliverable_dir, item.deliverable)
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

    input_csv = str(item.params.get("input_csv", "orders.csv")).strip()
    if not input_csv or not (task_dir / input_csv).is_file():
        return _result(
            item,
            "UNKNOWN",
            f"原始輸入不存在: {input_csv or 'orders.csv'}；無法可靠重算，依規則標 UNKNOWN",
            {"reason": f"missing_input_csv:{input_csv or 'orders.csv'}"},
        )
    _, expected_top, _ = recompute_orders_monthly(task_dir, item.params)
    expected_months = item.params.get("expected_months", sorted(expected_top.keys()))
    if not expected_top or not isinstance(expected_months, list) or not expected_months:
        return _result(
            item,
            "UNKNOWN",
            "原始資料重算無有效月份排行；無法可靠重算，依規則標 UNKNOWN",
            {"reason": "empty_expected_months"},
        )
    top_n = int(item.params.get("top_n", 3))
    include_expected = bool(item.params.get("expected_in_evidence", True))

    deliv_by_month = {}
    for r in deliv_rows:
        m = r.get("month") or r.get("order_month")
        if m:
            deliv_by_month[m.strip()] = r

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
            if include_expected:
                counterexamples.append({
                    "month": m,
                    "expected": expected_list,
                    "actual": actual_list,
                    "reason": "缺少排名欄位或未填滿前三名",
                })
            else:
                counterexamples.append({
                    "month": m,
                    "actual": actual_list,
                    "problem": "incomplete_top_products",
                    "expected_in_evidence": False,
                    "reason": "缺少排名欄位或未填滿前三名",
                })
            continue

        if actual_list != expected_list:
            if include_expected:
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
            else:
                mismatches.append(
                    f"月份 {m} 商品排行與原始資料重算不符: 交付物為 {actual_list}"
                )
                counterexamples.append({
                    "month": m,
                    "actual_top": actual_list,
                    "problem": "mismatch_with_recomputation",
                    "expected_in_evidence": False,
                    "reason": "排序依據錯誤（例如誤用訂單筆數/數量排序，而非使用者要求的淨銷售額排序）",
                })

    if mismatches:
        ev_fail: dict[str, Any] = {"counterexamples": counterexamples}
        if not include_expected:
            ev_fail["expected_in_evidence"] = False
        return ClaimResult(
            claim_id=item.id,
            status="FAIL",
            detail="; ".join(mismatches),
            evidence=ev_fail,
            verifier=item.verifier,
            verifier_version=VERIFIER_VERSION,
            required=item.required,
            authority=item.authority,
        )

    ev_pass: dict[str, Any] = (
        {"expected_top": {m: [p[0] for p in prods[:top_n]] for m, prods in expected_top.items()}}
        if include_expected
        else {"expected_in_evidence": False}
    )
    return ClaimResult(
        claim_id=item.id,
        status="PASS",
        detail=f"各月份前 {top_n} 名商品排行（依淨銷售額）重算核對完全一致",
        evidence=ev_pass,
        verifier=item.verifier,
        verifier_version=VERIFIER_VERSION,
        required=item.required,
        authority=item.authority,
    )


_SUMMARY_TOTAL_KEYWORDS = [
    "合計淨銷售總額", "合計淨銷售額", "合計銷售總額", "合計銷售額",
    "合計淨額", "合計金額", "總計淨銷售額", "總計銷售額", "總計淨額", "總計金額", "總計",
]

# 關鍵詞與數字之間允許的分隔（含 markdown 粗體符號）；不含子句標點，
# 避免把「合計…如下：9 月 42,400 元」裡的月份數字抓成總額陳述。
_SUMMARY_CLAIM_GAP = r"[\s:：、,，為是約共即達=*（）()\-\u2014\u2013/／]*"
# 千位分組必須「至少一個 ,ddd」，否則 12600.00 會被拆成 126 + 00。
_SUMMARY_CLAIM_NUM = r"([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)"
_SUMMARY_UNIT_RE = re.compile(r"^\s*(?:元|圓|美元|人民幣|新臺幣|TWD|USD|HKD|JPY|EUR|SGD)")


def _extract_summary_total_claims(content: str, keywords: list[str]) -> list[dict[str, Any]]:
    """找出「合計/總計 + 金額詞 + 數字」的總額陳述，回傳 [{phrase, value}]。

    只認綁定在合計關鍵詞上的數字；無金額詞時要求數字帶 $/¥ 前綴或
    貨幣單位後綴，避免把「訂單總計 25 筆」這類計數誤當成金額。
    """
    kw_alt = "|".join(re.escape(k) for k in sorted(keywords, key=len, reverse=True))
    rx = re.compile(
        rf"({kw_alt}){_SUMMARY_CLAIM_GAP}([\$¥])?\s*{_SUMMARY_CLAIM_NUM}"
    )
    claims: list[dict[str, Any]] = []
    for m in rx.finditer(content):
        phrase, currency, num = m.group(1), m.group(2), m.group(3)
        amount_word = any(w in phrase for w in ("銷售", "淨額", "金額"))
        unit_after = bool(_SUMMARY_UNIT_RE.match(content[m.end():m.end() + 8]))
        if not (amount_word or currency is not None or unit_after):
            continue
        claims.append({"phrase": m.group(0), "value": _parse_float(num)})
    return claims


def check_summary_metrics_consistency(
    task_dir: pathlib.Path,
    deliverable_dir: pathlib.Path,
    item: RequirementItem,
) -> ClaimResult:
    """檢查文字報告中「合計淨銷售總額」條目上的數字是否與重算一致。

    數值必須綁定在合計關鍵詞的陳述上：條目寫錯值＝FAIL；多個陳述互相
    矛盾（任一與重算不符）＝FAIL；全文找不到可對應的合計陳述＝UNKNOWN
    （看不到可可靠對應的欄位，不准自評，也不准因其他地方出現正確數字而 PASS）。
    """
    deliv_file = resolve_deliverable_path(deliverable_dir, item.deliverable)
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

    input_csv = str(item.params.get("input_csv", "orders.csv")).strip()
    if not input_csv or not (task_dir / input_csv).is_file():
        return _result(
            item,
            "UNKNOWN",
            f"原始輸入不存在: {input_csv or 'orders.csv'}；無法可靠重算，依規則標 UNKNOWN",
            {"reason": f"missing_input_csv:{input_csv or 'orders.csv'}"},
        )
    content = deliv_file.read_text(encoding="utf-8")
    expected_metrics, _, _ = recompute_orders_monthly(task_dir, item.params)
    if not expected_metrics:
        return _result(
            item,
            "UNKNOWN",
            "原始資料重算無有效月份指標；無法可靠重算，依規則標 UNKNOWN",
            {"reason": "empty_expected_metrics"},
        )
    total_expected_sales = sum(m["net_sales"] for m in expected_metrics.values())

    atol = float(item.params.get("atol", 0.05))
    include_expected = bool(item.params.get("expected_in_evidence", True))
    keywords = list(item.params.get("metric_keywords") or _SUMMARY_TOTAL_KEYWORDS)
    claims = _extract_summary_total_claims(content, keywords)

    if not claims:
        if include_expected:
            return ClaimResult(
                claim_id=item.id,
                status="UNKNOWN",
                detail=(
                    f"摘要中找不到綁定在合計條目上的總額陳述（重算值 {total_expected_sales:.2f}）；"
                    "看不到可可靠對應的欄位，依規則標 UNKNOWN，不准以全文數字搜索代替"
                ),
                evidence={
                    "expected_total_sales": total_expected_sales,
                    "reason": "no metric-bound total claim found",
                },
                verifier=item.verifier,
                verifier_version=VERIFIER_VERSION,
                required=item.required,
                authority=item.authority,
            )
        return ClaimResult(
            claim_id=item.id,
            status="UNKNOWN",
            detail=(
                "摘要中找不到綁定在合計條目上的總額陳述；"
                "看不到可可靠對應的欄位，依規則標 UNKNOWN，不准以全文數字搜索代替"
            ),
            evidence={
                "expected_in_evidence": False,
                "reason": "no metric-bound total claim found",
            },
            verifier=item.verifier,
            verifier_version=VERIFIER_VERSION,
            required=item.required,
            authority=item.authority,
        )

    wrong = [c for c in claims if abs(c["value"] - total_expected_sales) > atol]
    if wrong:
        values = [c["value"] for c in claims]
        if include_expected:
            detail = f"合計淨銷售總額條目與重算值 {total_expected_sales:.2f} 不符"
            ev_fail: dict[str, Any] = {
                "expected_total_sales": total_expected_sales,
                "counterexamples": [
                    {"phrase": c["phrase"], "value": c["value"],
                     "expected": total_expected_sales}
                    for c in wrong
                ],
            }
        else:
            detail = "合計淨銷售總額條目與原始資料重算不符"
            ev_fail = {
                "expected_in_evidence": False,
                "counterexamples": [
                    {"phrase": c["phrase"], "value": c["value"],
                     "problem": "mismatch_with_recomputation"}
                    for c in wrong
                ],
            }
        if len({round(v, 6) for v in values}) > 1:
            detail += "；且多個合計陳述互相矛盾"
        return ClaimResult(
            claim_id=item.id,
            status="FAIL",
            detail=detail,
            evidence=ev_fail,
            verifier=item.verifier,
            verifier_version=VERIFIER_VERSION,
            required=item.required,
            authority=item.authority,
        )

    if include_expected:
        return ClaimResult(
            claim_id=item.id,
            status="PASS",
            detail=f"文字摘要中的合計淨銷售總額核對正確 ({total_expected_sales:.2f})",
            evidence={
                "expected_total_sales": total_expected_sales,
                "matched_claims": [c["phrase"] for c in claims],
            },
            verifier=item.verifier,
            verifier_version=VERIFIER_VERSION,
            required=item.required,
            authority=item.authority,
        )
    return ClaimResult(
        claim_id=item.id,
        status="PASS",
        detail="文字摘要中的合計淨銷售總額核對正確",
        evidence={
            "expected_in_evidence": False,
            "matched_claims": [c["phrase"] for c in claims],
        },
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
        v = float(value)
        if not math.isfinite(v):
            raise UnsafeExpressionError(f"非有限數字: {value!r}")
        return v
    s = str(value).strip().replace("$", "").replace(",", "").replace("¥", "").replace("元", "")
    if s == "":
        raise UnsafeExpressionError("空白值不可作為數字")
    try:
        v = float(s)
    except ValueError as e:
        raise UnsafeExpressionError(f"不可解析為數字: {value!r}") from e
    if not math.isfinite(v):
        raise UnsafeExpressionError(f"非有限數字: {value!r}")
    return v


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
    if not isinstance(specs, list):
        raise UnknownSource("flatten 須為列表")
    for spec in specs:
        if not isinstance(spec, dict):
            raise UnknownSource("flatten 元素須為物件")
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
    if not isinstance(cond, dict):
        raise UnknownSource("篩選條件須為物件")
    col = str(cond.get("col", "")).strip().lower()
    if not col:
        raise UnknownSource("篩選條件缺少 col")
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


def _dedup_by_field(params: dict[str, Any]) -> str:
    """dedup_by 正規化：單一欄位名字串；模型常誤寫成一元素列表——容錯取首項。

    空列表／多元素／非字串 → UnknownSource（fail-closed，不准猜）。
    vq-el4.3 第 3 輪：glm53 把 dedup_by 寫成 ["order_id"]，原式 `.lower()` 直接
    AttributeError crash（檢查器崩潰不是 FAIL，也不准靜默跳過）。
    """
    d = params.get("dedup_by")
    if d is None:
        return ""
    if isinstance(d, (list, tuple)):
        if len(d) == 1 and isinstance(d[0], str):
            d = d[0]
        else:
            raise UnknownSource(f"dedup_by 須為單一欄位名字串：{d!r}")
    if not isinstance(d, str):
        raise UnknownSource(f"dedup_by 須為欄位名字串：{d!r}")
    return d.strip().lower()


def apply_pipeline(rows: list[dict[str, Any]], params: dict[str, Any]) -> list[dict[str, Any]]:
    """exclude → dedup_by（保留第一筆）→ include。"""
    exclude_specs = params.get("exclude", []) or []
    if not isinstance(exclude_specs, list):
        raise UnknownSource("exclude 須為條件列表")
    for cond in exclude_specs:
        rows = [r for r in rows if not _cond_holds(r, cond)]
    dedup_by = _dedup_by_field(params)
    if dedup_by:
        key = dedup_by
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
    include_specs = params.get("include", []) or []
    if not isinstance(include_specs, list):
        raise UnknownSource("include 須為條件列表")
    for cond in include_specs:
        rows = [r for r in rows if _cond_holds(r, cond)]
    return rows


def apply_compute(rows: list[dict[str, Any]], params: dict[str, Any]) -> list[dict[str, Any]]:
    """逐列計算派生欄位（compute: name + 安全運算式）。"""
    compute_specs = params.get("compute", []) or []
    if not isinstance(compute_specs, list):
        raise UnknownSource("compute 須為列表")
    for spec in compute_specs:
        if not isinstance(spec, dict):
            raise UnknownSource("compute 元素須為物件")
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


def _same_scalar_or_num(exp_str: str, act_str: str, atol: float) -> bool:
    """字串相等，或雙邊皆為非前導零代碼之有效有限數值且差距不超過 atol。"""
    if exp_str == act_str:
        return True
    for s in (exp_str, act_str):
        if len(s) > 1 and s[0] == "0" and s[1].isdigit():
            return False
    try:
        return abs(_to_num(act_str) - _to_num(exp_str)) <= atol
    except UnsafeExpressionError:
        return False


def check_rowset_filter(
    task_dir: pathlib.Path,
    deliverable_dir: pathlib.Path,
    item: RequirementItem,
) -> ClaimResult:
    """逐列重算：exclude→dedup→include 後，行集（identity）與逐欄值必須與交付物一致。"""
    params = dict(item.params)
    try:
        rows = apply_compute(apply_pipeline(load_table(task_dir, params), params), params)
        raw_identity = params.get("identity", []) or []
        if not isinstance(raw_identity, list):
            raise UnknownSource("rowset_filter.params.identity 須為列表")
        identity = [str(c).strip().lower() for c in raw_identity if isinstance(c, str) and c.strip()]
        if not identity:
            raise UnknownSource("rowset_filter.params.identity 缺失")
        raw_values = params.get("values")
        if raw_values is not None and not isinstance(raw_values, dict):
            raise UnknownSource("rowset_filter.params.values 須為物件")
        values_spec: dict[str, Any] = raw_values or {}
        if not values_spec and not (params.get("exclude") or params.get("include") or params.get("dedup_by")):
            raise UnknownSource("rowset_filter.params 缺少 values 與篩選條件；無法構成有效重算")
        expected: list[dict[str, Any]] = []
        for r in rows:
            er = {c: r.get(c, "") for c in identity}
            for out_col, spec in values_spec.items():
                if isinstance(spec, str):
                    col_key = spec.strip().lower()
                    if col_key not in r:
                        raise UnknownSource(f"values[{out_col}] 來源欄位不存在: {spec!r}")
                    er[out_col] = r.get(col_key, "")
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

    deliv_file = resolve_deliverable_path(deliverable_dir, item.deliverable)
    if not deliv_file.is_file():
        return _result(item, "FAIL", f"交付物不存在: {item.deliverable}", {"missing_file": item.deliverable})
    deliv_rows = read_table_deliverable(deliv_file)

    exp_keys = Counter(tuple(_fmt_key(r[c]) for c in identity) for r in expected)
    act_keys = Counter(tuple(_fmt_key(r.get(c, "")) for c in identity) for r in deliv_rows)
    include_expected = bool(params.get("expected_in_evidence", True))
    if exp_keys != act_keys:
        only_exp = sorted(set(exp_keys) - set(act_keys))
        only_act = sorted(set(act_keys) - set(exp_keys))
        if include_expected:
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
        detail = f"行集與原始資料篩選去重結果不符（交付物 {sum(act_keys.values())} 列）"
        return _result(
            item, "FAIL", detail,
            {"expected_in_evidence": False,
             "counterexamples": [{"kind": "rowset_mismatch",
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
            out_key = str(out_col).strip().lower()
            if out_key not in dr:
                mismatches.append(f"列 {list(key)} 缺欄 {out_col}")
                if include_expected:
                    counterexamples.append({
                        "row": list(key),
                        "field": out_col,
                        "expected": exp_v if isinstance(exp_v, str) else _fmt_val(exp_v),
                        "actual": None,
                    })
                else:
                    counterexamples.append({
                        "row": list(key),
                        "field": out_col,
                        "actual": None,
                        "problem": "missing_column",
                    })
                continue
            act_raw = dr.get(out_key)
            act_raw = "" if act_raw is None else str(act_raw).strip()
            if isinstance(exp_v, str):
                if not _same_scalar_or_num(exp_v.strip(), act_raw, atol):
                    if include_expected:
                        mismatches.append(f"列 {list(key)} 欄 {out_col} 不符: 預期 {exp_v!r}，交付物為 {act_raw!r}")
                        counterexamples.append({"row": list(key), "field": out_col, "expected": exp_v, "actual": act_raw})
                    else:
                        mismatches.append(f"列 {list(key)} 欄 {out_col} 與重算不符: 交付物為 {act_raw!r}")
                        counterexamples.append({"row": list(key), "field": out_col, "actual": act_raw, "problem": "mismatch_with_recomputation"})
                continue
            try:
                act_v = _to_num(act_raw)
            except UnsafeExpressionError:
                mismatches.append(f"列 {list(key)} 欄 {out_col} 無法解析: 交付物為 {act_raw!r}")
                if include_expected:
                    counterexamples.append({"row": list(key), "field": out_col, "expected": _fmt_val(exp_v), "actual": act_raw})
                else:
                    counterexamples.append({"row": list(key), "field": out_col, "actual": act_raw, "problem": "not_a_number"})
                continue
            if abs(act_v - float(exp_v)) > atol:
                if include_expected:
                    mismatches.append(f"列 {list(key)} 欄 {out_col} 不符: 預期 {_fmt_val(exp_v)}，交付物為 {act_raw}")
                    counterexamples.append({"row": list(key), "field": out_col,
                                           "expected": _fmt_val(exp_v), "actual": act_raw,
                                           "diff": act_v - float(exp_v)})
                else:
                    mismatches.append(f"列 {list(key)} 欄 {out_col} 與重算不符: 交付物為 {act_raw}")
                    counterexamples.append({"row": list(key), "field": out_col,
                                           "actual": act_raw,
                                           "problem": "mismatch_with_recomputation"})
    if mismatches:
        ev_fail: dict[str, Any] = {"counterexamples": counterexamples}
        if not include_expected:
            ev_fail["expected_in_evidence"] = False
        return _result(item, "FAIL", "; ".join(mismatches), ev_fail)
    return _result(item, "PASS", f"{len(expected)} 列重算核對完全一致",
                   {"recomputed_rows": len(expected)} if include_expected else {"expected_in_evidence": False})


def check_group_aggregate(
    task_dir: pathlib.Path,
    deliverable_dir: pathlib.Path,
    item: RequirementItem,
) -> ClaimResult:
    """分組聚合重算：分組鍵（含 normalize）與各聚合值必須與交付物一致。"""
    params = dict(item.params)
    try:
        rows = apply_compute(apply_pipeline(load_table(task_dir, params), params), params)
        raw_group_by = params.get("group_by", []) or []
        if not isinstance(raw_group_by, list):
            raise UnknownSource("group_aggregate.params.group_by 須為列表")
        group_by = [str(g).strip().lower() for g in raw_group_by if isinstance(g, str) and g.strip()]
        if not group_by:
            raise UnknownSource("group_aggregate.params.group_by 缺失")
        agg_specs = params.get("aggregates", []) or []
        if not isinstance(agg_specs, list) or not agg_specs or not all(isinstance(s, dict) for s in agg_specs):
            raise UnknownSource("group_aggregate.params.aggregates 缺失或非物件列表")
        norm = params.get("group_normalize", {}) or {}
        if not isinstance(norm, dict):
            raise UnknownSource("group_aggregate.params.group_normalize 須為物件")

        groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
        for r in rows:
            key = tuple(_norm_group_key(r.get(g), norm.get(g)) for g in group_by)
            groups.setdefault(key, []).append(r)

        expected: dict[tuple[str, ...], dict[str, Any]] = {}
        for key, grows in groups.items():
            vals: dict[str, Any] = {}
            for spec in agg_specs:
                if not isinstance(spec, dict):
                    raise UnknownSource(f"group_aggregate.params.aggregates 條目非物件: {spec!r}")
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
            vals_lower = {k.lower(): v for k, v in vals.items()}
            for spec in agg_specs:  # ratio 第二趟（依已算出的聚合名）
                if str(spec.get("type", "")).strip().lower() != "ratio":
                    continue
                name = str(spec.get("name", "")).strip()
                num_k = str(spec.get("num", "")).strip()
                den_k = str(spec.get("den", "")).strip()
                num = vals.get(num_k, vals_lower.get(num_k.lower()))
                den = vals.get(den_k, vals_lower.get(den_k.lower()))
                if num is None or den is None or float(den) == 0:
                    raise UnknownSource(f"ratio {name}: 分母為 0 或缺失")
                vals[name] = float(num) / float(den)
                vals_lower[name.lower()] = vals[name]
            for spec in agg_specs:
                name = str(spec.get("name", "")).strip()
                if "round" in spec and vals.get(name) is not None:
                    vals[name] = round(float(vals[name]), int(spec["round"]))
            expected[key] = vals
    except (UnknownSource, UnsafeExpressionError) as e:
        return _result(item, "UNKNOWN", f"無法可靠重算（{e}）；依規則不自評", {"reason": str(e)})

    deliv_file = resolve_deliverable_path(deliverable_dir, item.deliverable)
    if not deliv_file.is_file():
        return _result(item, "FAIL", f"交付物不存在: {item.deliverable}", {"missing_file": item.deliverable})
    deliv_rows = read_table_deliverable(deliv_file)
    if not deliv_rows:
        return _result(item, "FAIL", f"交付物為空: {item.deliverable}", {"empty_csv": item.deliverable})
    missing_cols = [g for g in group_by if not all(g in dr for dr in deliv_rows)]
    if missing_cols:
        return _result(item, "FAIL", f"交付物缺少分組欄位: {missing_cols}", {"missing_columns": missing_cols})

    deliv_groups: dict[tuple[str, ...], list[dict[str, str]]] = {}
    for dr in deliv_rows:
        key = tuple(_norm_group_key(dr.get(g), norm.get(g)) for g in group_by)
        deliv_groups.setdefault(key, []).append(dr)

    exp_keys, act_keys = set(expected), set(deliv_groups)
    dup = [k for k in exp_keys & act_keys if len(deliv_groups[k]) != 1]
    include_expected = bool(params.get("expected_in_evidence", True))
    if exp_keys != act_keys or dup:
        if include_expected:
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
        detail = "分組集與原始資料重算不符"
        if dup:
            detail += f"；重複組 {sorted(dup)}"
        return _result(
            item, "FAIL", detail,
            {"expected_in_evidence": False,
             "counterexamples": [{"kind": "group_mismatch",
                                  "actual_groups": [list(k) for k in sorted(act_keys)]}]},
        )

    atol = float(params.get("atol", 0.01))
    mismatches: list[str] = []
    counterexamples: list[dict[str, Any]] = []
    for key, vals in expected.items():
        dr = deliv_groups[key][0]
        for name, exp_v in vals.items():
            name_key = name.lower()
            if name_key not in dr:
                mismatches.append(f"組 {list(key)} 缺欄 {name}")
                if include_expected:
                    counterexamples.append({"group": list(key), "field": name, "expected": _fmt_val(exp_v), "actual": None})
                else:
                    counterexamples.append({"group": list(key), "field": name, "actual": None, "problem": "missing_column"})
                continue
            act_raw = "" if dr[name_key] is None else str(dr[name_key]).strip()
            if exp_v is None:
                if act_raw != "":
                    mismatches.append(f"組 {list(key)} 欄 {name} 預期空白，交付物為 {act_raw!r}")
                    counterexamples.append({"group": list(key), "field": name, "expected": None, "actual": act_raw})
                continue
            try:
                act_v = _to_num(act_raw)
            except UnsafeExpressionError:
                mismatches.append(f"組 {list(key)} 欄 {name} 無法解析: 交付物為 {act_raw!r}")
                if include_expected:
                    counterexamples.append({"group": list(key), "field": name, "expected": _fmt_val(exp_v), "actual": act_raw})
                else:
                    counterexamples.append({"group": list(key), "field": name, "actual": act_raw, "problem": "not_a_number"})
                continue
            if abs(act_v - float(exp_v)) > atol:
                if include_expected:
                    mismatches.append(f"組 {list(key)} 欄 {name} 不符: 預期 {_fmt_val(exp_v)}，交付物為 {act_raw}")
                    counterexamples.append({"group": list(key), "field": name,
                                           "expected": _fmt_val(exp_v), "actual": act_raw,
                                           "diff": act_v - float(exp_v)})
                else:
                    mismatches.append(f"組 {list(key)} 欄 {name} 與原始資料重算不符: 交付物為 {act_raw}")
                    counterexamples.append({"group": list(key), "field": name,
                                           "actual": act_raw,
                                           "problem": "mismatch_with_recomputation"})
    if mismatches:
        ev_fail: dict[str, Any] = {"counterexamples": counterexamples}
        if not include_expected:
            ev_fail["expected_in_evidence"] = False
        return _result(item, "FAIL", "; ".join(mismatches), ev_fail)
    return _result(item, "PASS", f"{len(expected)} 組聚合重算核對完全一致",
                   {"recomputed_groups": len(expected)} if include_expected else {"expected_in_evidence": False})


_ANSWER_KV_RE = re.compile(r"^\s*@([A-Za-z_][A-Za-z0-9_]*)\s*\[\s*([^\]]*?)\s*\]\s*$",
                           re.MULTILINE)


def _kv_type_ok(key: str, raw: str, cons: str) -> tuple[bool, str]:
    """單一 @key[value] 的約束判定。回 (ok, problem_code)。"""
    try:
        v = float(raw.replace(",", "").strip())
    except ValueError:
        return False, "not_a_number"
    if not math.isfinite(v):
        return False, "not_a_number"
    if cons in ("integer", "nonneg_int") and abs(v - round(v)) > 1e-9:
        return False, "not_an_integer"
    if cons == "nonneg_int" and v < 0:
        return False, "not_nonneg_int"
    if cons == "number_in_01" and not (0.0 <= v <= 1.0):
        return False, "out_of_01"
    return True, ""


class _JsonPairs(list):
    """標記頂層 JSON 物件的 (key, value) 序列，供偵測完全同名或大小寫重複鍵。"""


def _parse_json_kv_found(content: str) -> dict[str, list[str]]:
    """解析 JSON 交付物頂層物件鍵值：大小寫標準化並保留同名或大小寫重複鍵之所有值（供判定 ambiguous）。"""
    data = json.loads(content, object_pairs_hook=_JsonPairs)
    found: dict[str, list[str]] = {}
    if isinstance(data, _JsonPairs):
        for k, v in data:
            found.setdefault(str(k).strip().lower(), []).append(str(v).strip())
    return found


def check_answer_kv(task_dir: pathlib.Path, deliverable_dir: pathlib.Path,
                    item: RequirementItem) -> ClaimResult:
    """G2 新增（工單 P000-20261104-02）：答案檔格式檢查（@key[value] 行，DABench 答案格式）。

    只查**可見格式**：每個要求 key 恰出現一次、值可解析且滿足約束。
    值的**正確性**屬於 hidden 領域——本驗證器不碰，也不得把 hidden 參考值
    帶進修復（紅線：檢查沒看見時不得宣告修好）。
    - 檔案不存在 → FAIL（evidence.missing_file）
    - key 缺失 → FAIL（counterexamples[].problem=missing）
    - key 重複 → FAIL（ambiguous）；值不合約束 → FAIL（not_a_number / not_an_integer /
      not_nonneg_int / out_of_01）
    約束型別：number（預設）/ integer / nonneg_int / number_in_01。
    """
    specs = item.params.get("keys", []) or []
    if not isinstance(specs, list) or not specs:
        return _result(item, "UNKNOWN",
                       "answer_kv.params.keys 缺失；無法可靠檢查答案檔格式",
                       {"reason": "no keys spec"})
    for spec in specs:
        if not isinstance(spec, dict):
            return _result(item, "UNKNOWN",
                           "answer_kv.params.keys 元素須為物件；無法可靠檢查答案檔格式",
                           {"reason": "key_spec_not_dict"})
        key = str(spec.get("key", "")).strip().lower()
        if not key:
            return _result(item, "UNKNOWN",
                           "answer_kv.params.keys[].key 缺失；無法可靠檢查答案檔格式",
                           {"reason": "missing_key_name"})
        cons = str(spec.get("type", "number")).strip().lower()
        if cons not in ("number", "integer", "nonneg_int", "number_in_01"):
            return _result(item, "UNKNOWN",
                           f"未知約束型別：{cons}（不猜）", {"bad_constraint": cons})
    deliv_file = resolve_deliverable_path(deliverable_dir, item.deliverable)
    if not deliv_file.is_file():
        return _result(item, "FAIL", f"答案檔不存在：{item.deliverable}",
                       {"missing_file": item.deliverable})
    content = deliv_file.read_text(encoding="utf-8")
    found: dict[str, list[str]] = {}
    if deliv_file.suffix.lower() == ".json":
        # 工單 P20261106_0632-2：結構化 JSON 交付物（如 result.json）直接讀字典鍵值，
        # 不再硬性限制 @key[value] 純文字正則；值轉字串後走同一 _kv_type_ok 約束檢查。
        try:
            found = _parse_json_kv_found(content)
        except (json.JSONDecodeError, ValueError) as e:
            return _result(item, "FAIL", "答案檔不是合法 JSON（invalid_json）",
                           {"counterexamples": [{"key": "<file>", "problem": "invalid_json"}],
                            "reason": str(e)})
    else:
        for m in _ANSWER_KV_RE.finditer(content):
            found.setdefault(m.group(1).strip().lower(), []).append(m.group(2).strip())
    counterexamples: list[dict[str, Any]] = []
    checked: list[str] = []
    for spec in specs:
        key = str(spec.get("key", "")).strip().lower()
        if not key:
            raise UnknownSource("answer_kv.params.keys[].key 缺失")
        cons = str(spec.get("type", "number")).strip().lower()
        if cons not in ("number", "integer", "nonneg_int", "number_in_01"):
            return _result(item, "UNKNOWN",
                           f"未知約束型別：{cons}（不猜）", {"bad_constraint": cons})
        checked.append(key)
        vals = found.get(key)
        if not vals:
            counterexamples.append({"key": key, "problem": "missing"})
            continue
        if len(vals) > 1:
            counterexamples.append({"key": key, "problem": "ambiguous", "values": vals})
            continue
        ok, problem = _kv_type_ok(key, vals[0], cons)
        if not ok:
            counterexamples.append({"key": key, "problem": problem, "value": vals[0]})
    if counterexamples:
        return _result(item, "FAIL", "答案檔格式未達要求（見 counterexamples）",
                       {"counterexamples": counterexamples, "checked_keys": checked})
    return _result(item, "PASS",
                   f"答案檔 {item.deliverable} 含全部 {len(checked)} 個 key 且格式合法",
                   {"checked_keys": checked})


def _kv_answer_value(deliverable_dir: pathlib.Path, item: RequirementItem,
                     key: str) -> tuple[str | None, list[str]]:
    """讀交付檔中 @key[value]；回傳 (value|None, 問題清單)——與 answer_kv 同一解析規則。"""
    deliv_file = resolve_deliverable_path(deliverable_dir, item.deliverable)
    if not deliv_file.is_file():
        return None, [f"missing_file:{item.deliverable}"]
    content = deliv_file.read_text(encoding="utf-8")
    if deliv_file.suffix.lower() == ".json":
        # 工單 P20261106_0632-2：JSON 交付物直接讀字典鍵值（大小寫不拘，與原正則路徑
        # 同口徑）；非 dict 視為 key 缺失；解析失敗回傳 invalid_json（下游標 FAIL）。
        try:
            found = _parse_json_kv_found(content)
        except (json.JSONDecodeError, ValueError):
            return None, ["invalid_json"]
        vals = found.get(key.strip().lower(), [])
    else:
        vals = [m.group(2).strip() for m in _ANSWER_KV_RE.finditer(content)
                if m.group(1).strip().lower() == key.lower()]
    if not vals:
        return None, ["missing"]
    if len(vals) > 1:
        return None, ["ambiguous"]
    return vals[0], []


def _strict_json_equal(a: Any, b: Any) -> bool:
    """JSON 鍵值保留審計用嚴格相等：型別必須完全一致（排除 Python `True == 1`、`2 == 2.0`），
    且巢狀物件（`_JsonPairs`）不得含重複鍵。"""
    if type(a) is not type(b):
        return False
    if isinstance(a, _JsonPairs):
        if len(a) != len(b):
            return False
        da = dict(a)
        db = dict(b)
        if len(da) != len(a) or len(db) != len(b) or da.keys() != db.keys():
            return False
        return all(_strict_json_equal(da[k], db[k]) for k in da)
    # 工單 P20261107_0243-1：原生 Python dict 遞迴嚴格比對——避免降級至裸 `==`
    # 使巢狀 `bool vs int`（True==1）、`int vs float`（2==2.0）被誤判相等。
    if isinstance(a, dict):
        if a.keys() != b.keys():
            return False
        return all(_strict_json_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(_strict_json_equal(x, y) for x, y in zip(a, b))
    return bool(a == b)


def _kv_preservation_values(path: pathlib.Path) -> tuple[dict[str, list[Any]] | None, str | None]:
    """鍵級保留審計讀鍵→值清單：.txt → 各 @key[value] 行之 raw 字串（與 check_answer_kv 同一正則）；
    .json → 頂層 dict 值（透過 _JsonPairs 保留同名或大小寫重複鍵並保留原始型別供嚴格型別一致比較）。
    回 (found, problem|None)。"""
    if not path.is_file():
        return None, "missing_file"
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None, "unreadable"
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(content, object_pairs_hook=_JsonPairs)
        except (json.JSONDecodeError, ValueError):
            return None, "invalid_json"
        if not isinstance(data, _JsonPairs):
            return None, "not_a_dict"
        found: dict[str, list[Any]] = {}
        for k, v in data:
            found.setdefault(str(k).strip().lower(), []).append(v)
        return found, None
    found = {}
    for m in _ANSWER_KV_RE.finditer(content):
        found.setdefault(m.group(1).strip().lower(), []).append(m.group(2).strip())
    return found, None


def audit_kv_preservation(draft_path: pathlib.Path | str, final_path: pathlib.Path | str,
                          satisfied_keys: Sequence[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """鍵值交付物（@key[value] 文字檔或頂層 JSON 字典）的行級／鍵級保留審計。

    audit 側計算、免模型自評、免正則猜測：對每個 satisfied key 比對原草稿與修復後產物，
    兩側均恰好出現一次且值相等（.json 另需遞迴嚴格型別一致且無重複鍵）→ preserved；值被覆寫、鍵被刪除
    或重複、交付物檔案缺失/不可解析、或草稿中無此鍵（不可判定，保守歸類）→ mutated。
    回 (preserved, mutated)，鍵順序跟隨輸入 satisfied_keys。
    """
    d_vals, _ = _kv_preservation_values(pathlib.Path(draft_path))
    f_vals, _ = _kv_preservation_values(pathlib.Path(final_path))
    preserved: list[str] = []
    mutated: list[str] = []
    for key in satisfied_keys:
        k = str(key).strip().lower()
        if (d_vals is None or f_vals is None
                or len(d_vals.get(k, [])) != 1 or len(f_vals.get(k, [])) != 1):
            mutated.append(str(key))
            continue
        dv, fv = d_vals[k][0], f_vals[k][0]
        if _strict_json_equal(dv, fv):
            preserved.append(str(key))
        else:
            mutated.append(str(key))
    return tuple(preserved), tuple(mutated)


# kv_recomputed 支援的重算型別（與下方 rtype 分派鏈保持同步；
# 守衛測試 tests/test_reqloop_extract.py::test_recompute_type_sets_match_dispatch 以源碼核對）。
KV_RECOMPUTE_TYPES: frozenset[str] = frozenset(
    {"count_if", "zcount3", "mean_int_col", "max_row_first", "pearson2", "col_stats", "null_count",
     "mean_col", "median_col", "std_col"}
)


def check_kv_recomputed(
    task_dir: pathlib.Path,
    deliverable_dir: pathlib.Path,
    item: RequirementItem,
) -> ClaimResult:
    """G2 真草稿冒煙（工單 P000-20261104-02）：@key[value] 值必須與對凍結資料的重算一致。

    所有輸入皆可見：規則（quote/params）＋資料（任務目錄、凍結進 repo 並帶 sha）。
    **防洩漏**：重算值絕不進 detail/evidence——修復模型只看到「你的值與按公開規則
    對公開資料重算不符」，不會被直接給答案（紅線：不向修復模型提供隱藏答案）。
    - 資料檔缺失 / recompute 規則不支援 → UNKNOWN（不猜）
    - 資料檔：.csv 走 csv.DictReader；.json 走 json.load（必須為 row 物件列表，否則 UNKNOWN；
      vq-5nz.13 與 vq-5nz.12（check_plain_recomputed）同型——禁止 .json 走 csv.DictReader
      產生垃圾字典：count_if 類規則會誤算 expected=0，交付 0 即假 PASS）
    - 交付值缺失/重複 → FAIL（missing/ambiguous）
    - 值不符重算 → FAIL（mismatch_with_recomputation；不顯示期望值）
    - 一致 → PASS

    vq-5nz.16 新增重算規則：col_stats（mean/median/樣本sd/bias-corrected 偏度與超额峰度，
    pandas 口徑；dab_378）、null_count（null 細胞計數；dab_427）。
    """
    p = item.params
    key = str(p.get("key", "")).strip()
    if not key:
        return _result(item, "UNKNOWN", "kv_recomputed.params.key 缺失；不自評", {"reason": "no key"})
    data_rel = str(p.get("data_file", "")).strip()
    if not data_rel:
        return _result(item, "UNKNOWN", "kv_recomputed.params.data_file 缺失；不自評", {"reason": "no data_file"})
    data_file = (task_dir / data_rel)
    if not data_file.is_file():
        return _result(item, "UNKNOWN",
                       f"資料檔 {data_rel} 缺失；無法重算，標 UNKNOWN", {"data_file": data_rel})
    rc = p.get("recompute")
    if not isinstance(rc, dict):
        return _result(item, "UNKNOWN", "kv_recomputed.params.recompute 缺失；不自評", {"reason": "no recompute"})
    try:
        if data_file.suffix.lower() == ".json":
            # vq-5nz.13：.json data_file 用 json.load 解析；走 csv.DictReader 會把首行當
            # 「表頭」、剩餘行全成垃圾字典（count_if 誤算 expected=0 → 交付 0 假 PASS）。
            # 必須是 row 物件列表，否則 UNKNOWN（不自評）。
            with data_file.open(encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
                raise UnknownSource(
                    f"JSON 資料檔 {data_rel} 非 row 物件列表；無法可靠重算")
            rows = data
        else:
            with data_file.open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
    except (UnknownSource, OSError, json.JSONDecodeError) as e:
        return _result(item, "UNKNOWN", f"無法可靠重算（{e}）；依規則不自評", {"reason": str(e)})

    unrounded_int_expected: float | None = None
    try:
        rtype = str(rc.get("type", "")).strip().lower()
        if rtype == "count_if":
            col = str(rc.get("col", "")).strip()
            eq = rc.get("eq")
            if not col or eq is None:
                raise UnknownSource("count_if 需要 col 與 eq")
            if not rows or col not in rows[0]:
                raise UnknownSource(f"資料檔找不到欄 {col!r}")
            try:
                eq_num = float(eq)
            except (TypeError, ValueError):
                raise UnknownSource("count_if.eq 不可解析為數字")
            if not math.isfinite(eq_num):
                raise UnknownSource("count_if.eq 非有限數值")
            expected = 0.0
            for r in rows:
                cell = r.get(col)
                try:
                    v = float(str(cell).strip())
                except (TypeError, ValueError):
                    continue
                if not math.isfinite(v):
                    continue
                if v == eq_num:
                    expected += 1.0
        elif rtype == "zcount3":
            col = str(rc.get("col", "")).strip()
            if not col:
                raise UnknownSource("zcount3 需要 col")
            if not rows or col not in rows[0]:
                raise UnknownSource(f"資料檔找不到欄 {col!r}")
            vals: list[float] = []
            for r in rows:
                try:
                    v = float(str(r.get(col, "")).strip())
                except (TypeError, ValueError):
                    continue
                if not math.isfinite(v):
                    continue
                vals.append(v)
            if len(vals) < 2:
                raise UnknownSource("zcount3: 可解析數值不足 2 個")
            mean = sum(vals) / len(vals)
            sd = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5  # 母體慣例；見 params.note
            if sd == 0.0 or not math.isfinite(sd):
                raise UnknownSource("zcount3: 標準差為 0")
            expected = float(sum(1 for v in vals if abs((v - mean) / sd) > 3.0))
        elif rtype == "mean_int_col":
            expected, unrounded_int_expected = _mean_int_col(rows, rc)
        elif rtype == "max_row_first":
            expected = _max_row_first(rows, rc)
        elif rtype == "pearson2":
            # G2 小批（e013 dab_105）：兩欄成對可解析行（缺值行忽略）、Pearson r。
            # vq-el4.10（r1222，dab_057 冤枉缺陷）：點估計＋信賴區間字串
            # （'630308[495000-801000]' → 630308）取前導點估計參與計算，口徑同 _mean_int_col；
            # 修前這類行被靜默丟棄，只在純數字子集合上算 r（dab_057 實測 297/856 對
            # r=0.52 → 把全量 r=0.97 的正確答案自信地 FAIL）。
            col_a = str(rc.get("col_a", "")).strip()
            col_b = str(rc.get("col_b", "")).strip()
            if not col_a or not col_b:
                raise UnknownSource("pearson2 需要 col_a 與 col_b")
            if not rows or col_a not in rows[0] or col_b not in rows[0]:
                raise UnknownSource(f"資料檔找不到欄 {col_a!r} 或 {col_b!r}")
            xs: list[float] = []
            ys: list[float] = []
            for r in rows:
                x = _point_estimate(r.get(col_a, ""))
                y = _point_estimate(r.get(col_b, ""))
                if x is None or y is None:
                    continue
                xs.append(x)
                ys.append(y)
            if len(xs) < 2:
                raise UnknownSource("pearson2: 可用成對數值不足 2")
            ma = sum(xs) / len(xs)
            mb = sum(ys) / len(ys)
            cov = sum((x - ma) * (y - mb) for x, y in zip(xs, ys))
            va = sum((x - ma) ** 2 for x in xs)
            vb = sum((y - mb) ** 2 for y in ys)
            if va == 0.0 or vb == 0.0:
                raise UnknownSource("pearson2: 常數欄，相關係數未定義")
            expected = cov / ((va ** 0.5) * (vb ** 0.5))
        elif rtype == "col_stats":
            expected = _col_stats(rows, rc)
        elif rtype == "null_count":
            expected = _null_count(rows, rc)
        elif rtype == "mean_col":
            expected = _mean_col(rows, rc)
        elif rtype == "median_col":
            expected = _median_col(rows, rc)
        elif rtype == "std_col":
            expected = _std_col(rows, rc)
        else:
            raise UnknownSource(f"不支援的重算規則: {rtype!r}")
        if not isinstance(expected, (int, float)) or isinstance(expected, bool) or not math.isfinite(float(expected)):
            raise UnknownSource("重算結果非有限數值")
        rnd = rc.get("round") if rc.get("round") is not None else p.get("round")
        if isinstance(rnd, int) and not isinstance(rnd, bool):
            expected = round(expected, rnd)
    except (UnknownSource, OSError) as e:
        return _result(item, "UNKNOWN", f"無法可靠重算（{e}）；依規則不自評", {"reason": str(e)})

    val_str, problems = _kv_answer_value(deliverable_dir, item, key)
    if val_str is None:
        return _result(item, "FAIL", f"答案值不可用（{problems[0]}）；值正確性無法成立",
                       {"key": key, "problem": problems[0], "data_file": data_rel,
                        "expected_in_evidence": False})
    try:
        got = float(val_str.replace(",", "").strip())
    except ValueError:
        return _result(item, "FAIL", "答案值不可解析為數字",
                       {"key": key, "problem": "not_a_number", "value": val_str,
                        "expected_in_evidence": False})
    if not math.isfinite(got):
        return _result(item, "FAIL", "答案值不可解析為數字",
                       {"key": key, "problem": "not_a_number", "value": val_str,
                        "expected_in_evidence": False})

    atol = float(p.get("atol", 1e-6))
    rule_desc = f"{str(rc.get('type'))}: {data_rel} {json.dumps({k: v for k, v in rc.items() if k not in ('type', 'note')}, ensure_ascii=False)}"
    if not (abs(got - expected) <= atol):
        if (unrounded_int_expected is not None
                and not re.match(r"^[+-]?\d+$", val_str)
                and round(got) == int(expected)
                and abs(got - unrounded_int_expected) <= max(atol, 0.05)):
            return _result(item, "FAIL",
                           "答案值未取整數（與按公開規則重算的未取整均值一致，但依原始需求須四捨五入為整數；期望值不在證據中）",
                           {"key": key, "deliverable_value": val_str,
                            "problem": "not_an_integer",
                            "rule": rule_desc,
                            "expected_in_evidence": False})
        return _result(item, "FAIL",
                       f"答案值與按公開規則對公開資料的重算不符；請依原始需求與工作區資料自行重算（期望值不在證據中）",
                       {"key": key, "deliverable_value": val_str,
                        "problem": "mismatch_with_recomputation",
                        "rule": rule_desc,
                        "expected_in_evidence": False})
    return _result(item, "PASS",
                   f"答案值與按公開規則（{rule_desc}）的重算一致",
                   {"key": key, "rule": rule_desc, "expected_in_evidence": False})


def _col_values(rows: list[dict[str, Any]], col: str) -> list[float]:
    """取欄（可解析為有限 float 的值，保留檔案序）；欄不存在或全不可解析 → UnknownSource。"""
    if not rows or col not in rows[0]:
        raise UnknownSource(f"資料檔找不到欄 {col!r}")
    vals: list[float] = []
    for r in rows:
        raw = r.get(col)
        if raw is None:
            continue
        try:
            v = float(str(raw).strip())
        except ValueError:
            continue
        if not math.isfinite(v):
            continue
        vals.append(v)
    if not vals:
        raise UnknownSource(f"欄 {col!r} 沒有可解析為數值的值")
    return vals


def _col_stats(rows: list[dict[str, Any]], rc: dict[str, Any]) -> float:
    """col_stats（vq-5nz.16，dab_378）：mean/median/樣本標準差/bias-corrected 偏度/超额峰度。

    口徑 TDD 前凍結（與 pandas 預設一致，2026-11-04 以 pandas 3.1 對照驗證）：
    - sd        = sqrt(Σ(x−m)²/(n−1))                          （n≥2）
    - skewness  G1 = (m3/m2^1.5)·√(n(n−1))/(n−2)               （n≥3，m2>0）
    - kurtosis  G2 = ((n+1)(m4/m2²−3)+6)·(n−1)/((n−2)(n−3))    （n≥4，m2>0，超额峰度）
    m2=0（常數欄）或 n 不足 → UnknownSource（不自評）。round 由呼叫端統一處理。
    """
    col = str(rc.get("col", "")).strip()
    if not col:
        raise UnknownSource("col_stats.col 缺失")
    stat = str(rc.get("stat", "")).strip().lower()
    if stat not in ("mean", "median", "sd", "skewness", "kurtosis"):
        raise UnknownSource(
            "col_stats.stat 須為 mean/median/sd/skewness/kurtosis 之一（不猜）")
    x = _col_values(rows, col)
    n = len(x)
    m = sum(x) / n
    d = [v - m for v in x]
    if stat == "mean":
        val: float = m
    elif stat == "median":
        s = sorted(x)
        mid = n // 2
        val = s[mid] if n % 2 == 1 else (s[mid - 1] + s[mid]) / 2
    else:
        m2 = sum(v * v for v in d) / n
        if m2 <= 0:
            raise UnknownSource(f"欄為常數（m2=0）；無法計算 {stat}（不自評）")
        if stat == "sd":
            if n < 2:
                raise UnknownSource("sd 需要 n≥2")
            val = math.sqrt(sum(v * v for v in d) / (n - 1))
        elif stat == "skewness":
            if n < 3:
                raise UnknownSource("skewness 需要 n≥3")
            m3 = sum(v ** 3 for v in d) / n
            val = (m3 / m2 ** 1.5) * math.sqrt(n * (n - 1)) / (n - 2)
        else:  # kurtosis
            if n < 4:
                raise UnknownSource("kurtosis 需要 n≥4")
            m4 = sum(v ** 4 for v in d) / n
            val = ((n + 1) * (m4 / m2 ** 2 - 3) + 6) * (n - 1) / ((n - 2) * (n - 3))
    return val


def _stat_col_values(rows: list[dict[str, Any]], col: str) -> list[float]:
    """D3（P20261113_0300-3，2026-11-13 受控解凍）：單欄統計（mean_col/median_col/std_col）
    取值口徑，同 pearson2（vq-el4.10，r1222）：純數值原樣解析；附信賴區間的點估計字串
    取前導點估計（'630308[495000-801000]' → 630308）；null/空/不可解析 → 跳過該列
    （修前這類行被靜默丟棄、只在錯誤子集上計算是已知缺陷，不得重蹈）。
    欄不存在或全不可解析 → UnknownSource（不自評）。"""
    if not rows or col not in rows[0]:
        raise UnknownSource(f"資料檔找不到欄 {col!r}")
    vals: list[float] = []
    for r in rows:
        v = _point_estimate(r.get(col, ""))
        if v is not None:
            vals.append(v)
    if not vals:
        raise UnknownSource(f"欄 {col!r} 沒有可解析為數值的值")
    return vals


def _mean_col(rows: list[dict[str, Any]], rc: dict[str, Any]) -> float:
    """mean_col（D3，2026-11-13 受控解凍）：單欄均值，pandas 口徑（mean(df[col])；
    缺失/不可解析值忽略；round 由呼叫端統一處理）。"""
    col = str(rc.get("col", "")).strip()
    if not col:
        raise UnknownSource("mean_col 需要 col")
    x = _stat_col_values(rows, col)
    return sum(x) / len(x)


def _median_col(rows: list[dict[str, Any]], rc: dict[str, Any]) -> float:
    """median_col（D3，2026-11-13 受控解凍）：單欄中位數（pandas median 口徑；
    偶數個值取中位兩值平均）。"""
    col = str(rc.get("col", "")).strip()
    if not col:
        raise UnknownSource("median_col 需要 col")
    x = sorted(_stat_col_values(rows, col))
    n = len(x)
    return x[n // 2] if n % 2 == 1 else (x[n // 2 - 1] + x[n // 2]) / 2


def _std_col(rows: list[dict[str, Any]], rc: dict[str, Any]) -> float:
    """std_col（D3，2026-11-13 受控解凍）：單欄標準差，pandas 口徑＝樣本標準差
    （df[col].std() 預設 ddof=1）；n<2 → UnknownSource（未定義，不自評）。"""
    col = str(rc.get("col", "")).strip()
    if not col:
        raise UnknownSource("std_col 需要 col")
    x = _stat_col_values(rows, col)
    n = len(x)
    if n < 2:
        raise UnknownSource("std_col 需要 n≥2")
    m = sum(x) / n
    return math.sqrt(sum((v - m) ** 2 for v in x) / (n - 1))


_DEFAULT_NULL_VALUES = ("", "none", "null", "nan", "na", "n/a")


def _null_count(rows: list[dict[str, Any]], rc: dict[str, Any]) -> int:
    """null_count（vq-5nz.16，dab_427 min_p）：欄位 null 細胞計數。

    預設 null 集合：''/'none'/'null'/'nan'/'na'/'n-a'（大小寫不敏感、去首尾空白）；
    可用 rc["null_values"]（字串列表）覆蓋。只數 null，不數其他「錯誤資料」。
    """
    col = str(rc.get("col", "")).strip()
    if not col:
        raise UnknownSource("null_count.col 缺失")
    if not rows or col not in rows[0]:
        raise UnknownSource(f"資料檔找不到欄 {col!r}")
    raw_set = rc.get("null_values")
    if raw_set is None:
        nulls = set(_DEFAULT_NULL_VALUES)
    else:
        if not isinstance(raw_set, list):
            raise UnknownSource("null_count.null_values 須為字串列表")
        nulls = {str(v).strip().lower() for v in raw_set}
    n = 0
    for r in rows:
        v = r.get(col)
        if v is None or str(v).strip().lower() in nulls:
            n += 1
    return n


def _unique_count(rows: list[dict[str, Any]], rc: dict[str, Any]) -> int:
    """unique_count（vq-5nz.16，dabstep-10 merchant）：欄位去重計數（字串層級；空值不算一個值）。"""
    col = str(rc.get("col", "")).strip()
    if not col:
        raise UnknownSource("unique_count.col 缺失")
    if not rows or col not in rows[0]:
        raise UnknownSource(f"資料檔找不到欄 {col!r}")
    vals = {str(r.get(col, "")).strip() for r in rows}
    vals.discard("")
    if not vals:
        raise UnknownSource("欄沒有非空值")
    return len(vals)


def _col_max(rows: list[dict[str, Any]], rc: dict[str, Any]) -> float:
    """col_max（vq-5nz.16，dabstep-11 eur_amount）：欄位最大值（不可解析值忽略）。"""
    col = str(rc.get("col", "")).strip()
    if not col:
        raise UnknownSource("col_max.col 缺失")
    return max(_col_values(rows, col))


def _max_row_first(rows: list[dict[str, Any]], rc: dict[str, Any]) -> float:
    """max_row_first（G2 dab_426）：sel_col 最大值、平手取檔案序第一列、輸出該列 out_col。

    「neglecting ties…choose the one that appears first」的文字直譯（e013 dab_426）。
    """
    sel_col = str(rc.get("sel_col", "")).strip()
    out_col = str(rc.get("out_col", "")).strip()
    if not sel_col or not out_col:
        raise UnknownSource("max_row_first 需要 sel_col 與 out_col")
    best: tuple[float, dict[str, Any]] | None = None
    for r in rows:
        try:
            v = float(str(r.get(sel_col, "")).strip())
        except (TypeError, ValueError):
            continue
        if not math.isfinite(v):
            continue
        if best is None or v > best[0]:
            best = (v, r)
    if best is None:
        raise UnknownSource("max_row_first: 無可解析選取欄")
    try:
        out_v = float(str(best[1].get(out_col, "")).strip())
    except (TypeError, ValueError):
        raise UnknownSource(f"max_row_first: {out_col} 不可解析")
    if not math.isfinite(out_v):
        raise UnknownSource(f"max_row_first: {out_col} 不可解析")
    return out_v


def _point_estimate(cell: Any) -> float | None:
    """數值欄位解析口徑（vq-el4.10，r1222；與 _mean_int_col 的 '200[10-30]' 處理同口徑）：
    純數值原樣解析；附信賴區間的點估計字串取前導點估計
    （'630308[495000-801000]' → 630308）；NaN/inf、空、不可解析 → None（呼叫方忽略該行；
    成對不足仍由下游「可解析數值不足」門關住，不會靜默空集合）。"""
    s = str(cell).strip()
    if not s:
        return None
    try:
        f = float(s)
    except ValueError:
        m = re.match(r"^([+-]?\d+(?:\.\d+)?)(?:\s*\[\s*\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?\s*\])?$", s)
        if not m:
            return None
        f = float(m.group(1))
    return f if math.isfinite(f) else None


def _mean_int_col(
    rows: list[dict[str, Any]], rc: dict[str, Any]
) -> tuple[float, float | None]:
    """mean_int_col（G2 小批 e013 dab_055）：「轉 Int64；Null/空忽略」——支援純整數（如 '100'）
    與附信賴區間的點估計字串（如 '630308[495000-801000]'，取前導整數點估計，與
    No. of cases_median 同值，同 dab_057 口徑）；Null/空與非數值字串（如 'xx[1-2]'）忽略。
    未顯式指定 round 時取整（round），避免與 answer_kv type=integer 構成無解矛盾。
    回傳 (expected, unrounded_int_expected)。
    """
    col = str(rc.get("col", "")).strip()
    if not col:
        raise UnknownSource("mean_int_col 需要 col")
    ints: list[int] = []
    for r in rows:
        raw_cell = r.get(col)
        if raw_cell is None:
            continue
        cell = str(raw_cell).strip()
        if not cell:
            continue
        m_int = re.match(r"^([+-]?\d+)(?:\s*\[\s*\d+\s*-\s*\d+\s*\])?$", cell)
        if m_int:
            ints.append(int(m_int.group(1)))
    if not ints:
        raise UnknownSource("mean_int_col: 無可解析整數")
    raw_mean = sum(ints) / len(ints)
    if rc.get("round") is None:
        return float(round(raw_mean)), float(raw_mean)
    return float(raw_mean), None


def _scheme_fee_avg(rows: list[dict[str, Any]], rc: dict[str, Any]) -> float:
    """scheme_fee_avg（vq-5nz.16，dabstep-1273）：card_scheme×is_credit 匹配規則上的平均費率。

    公式依公開 manual.md：fee = fixed_amount + rate · amount / 10000。
    rows 須為 fee 規則物件列表（json data_file）；無匹配規則 → UnknownSource。
    manual.md："If a field is set to null it means that it applies to all possible values"
    ——is_credit=null 為 wildcard（r1029 合併 d96a8dba 採 argon 語意；舊
    bool(None)=False 靜默排除曾造成 dabstep-1273 假 PASS 0.117667）。
    """
    scheme = str(rc.get("scheme", "")).strip()
    if not scheme:
        raise UnknownSource("scheme_fee_avg.scheme 缺失")
    if "is_credit" not in rc:
        raise UnknownSource("scheme_fee_avg.is_credit 缺失（bool）")
    want_credit = bool(rc["is_credit"])
    try:
        amount = float(rc.get("amount"))
    except (TypeError, ValueError):
        raise UnknownSource("scheme_fee_avg.amount 缺失或非數值")
    if not math.isfinite(amount):
        raise UnknownSource("scheme_fee_avg.amount 缺失或非數值")
    fees: list[float] = []
    for r in rows:
        if str(r.get("card_scheme", "")).strip() != scheme:
            continue
        # manual.md："If a field is set to null it means that it applies to all possible values"
        ic = r.get("is_credit")
        if ic is not None and bool(ic) is not want_credit:
            continue
        try:
            fixed = float(r.get("fixed_amount"))
            rate = float(r.get("rate"))
        except (TypeError, ValueError):
            raise UnknownSource("匹配 fee 規則缺 fixed_amount/rate")
        if not (math.isfinite(fixed) and math.isfinite(rate)):
            raise UnknownSource("匹配 fee 規則缺 fixed_amount/rate")
        fees.append(fixed + rate * amount / 10000)
    if not fees:
        raise UnknownSource(f"無匹配 fee 規則 scheme={scheme!r} is_credit={want_credit}")
    return sum(fees) / len(fees)


def _mode_col(rows: list[dict[str, Any]], rc: dict[str, Any]) -> str:
    """mode_col（G2 小批 e014/dabstep-13）：欄位值計數最大者。
    平手→數值最小（可解析為數時），否則字典序最小（TDD 前凍結，見 smoke_e014 manifest）。"""
    col = str(rc.get("col", "")).strip()
    if not col:
        raise UnknownSource("mode_col 需要 col")
    counts: dict[str, int] = {}
    for r in rows:
        cell = str(r.get(col, "")).strip()
        if not cell:
            continue
        counts[cell] = counts.get(cell, 0) + 1
    if not counts:
        raise UnknownSource("mode_col: 無非空值")
    top = max(counts.values())
    winners = [v for v, n in counts.items() if n == top]

    def _key(v: str) -> tuple:
        try:
            fv = float(v)
        except ValueError:
            return (1, 0.0, v)
        if not math.isfinite(fv):
            return (1, 0.0, v)
        return (0, fv, "")

    winners.sort(key=_key)
    return winners[0]


def _cond_rate(rows: list[dict[str, Any]], rc: dict[str, Any]) -> float:
    """cond_rate（G2 小批 e014/dabstep-23）：rate＝|where∩num_where| / |where|。
    where＝分母族群條件、num_where＝分子附加條件（均為 {col,op,value}，複用 _cond_holds）。
    fraud_rate_2023_inperson 語義（TDD 前凍結）：where＝year==2023 ∧ shopper_interaction==POS
    （POS=in-person，payments-readme.md 明言）；num_where＝has_fraudulent_dispute==True；
    分母 0 行→UNKNOWN（不自評）；比率唯一，無平手規則。"""
    where = rc.get("where")
    num_where = rc.get("num_where")
    if not isinstance(where, list) or not where:
        raise UnknownSource("cond_rate 需要 where（分母族群條件）")
    if not isinstance(num_where, list) or not num_where:
        raise UnknownSource("cond_rate 需要 num_where（分子附加條件）")
    for c in list(where) + list(num_where):
        if not isinstance(c, dict) or not str(c.get("col", "")).strip():
            raise UnknownSource("cond_rate 條件缺少 col")
    pop = [r for r in rows if all(_cond_holds(r, c) for c in where)]
    if not pop:
        raise UnknownSource("cond_rate: 分母為 0 行；無法算比率")
    numer = [r for r in pop if all(_cond_holds(r, c) for c in num_where)]
    return len(numer) / len(pop)


def _group_ratio_stat(rows: list[dict[str, Any]], rc: dict[str, Any]) -> float | str:
    """group_ratio_stat（G2.5 dabstep-16/17，manual.md 公開 fraud volume ratio 定義）：
    按 group_col 分組加總金額比率極值——rate_g = sum(分子金額) / sum(分母金額)，
    跨組取 min/max（平手→檔案序首見分組），回傳極值數值（out="val"）或分組名稱（out="group"）。

    語義 TDD 前凍結（對照 dabstep-17 草稿 7.683437＝誤用 count ratio 2132/27748 的實敗形）：
    - sum_col＝加總金額欄；num_sum_col / denom_sum_col 可各自覆蓋分子/分母欄；
    - where（可選）＝分母族群條件、num_where（必填）＝分子條件（皆 {col,op,value}，複用 _cond_holds）；
    - 非數值/NaN/inf 儲存格忽略；分母和為 0 的分組不進候選；無任何有效分母→UnknownSource（不自評）；
    - 重算值不進證據（check_plain_recomputed 防洩漏語義不變）。
    """
    group_col = str(rc.get("group_col", "")).strip()
    if not group_col:
        raise UnknownSource("group_ratio_stat 需要 group_col")
    base_col = str(rc.get("sum_col", "")).strip()
    denom_col = str(rc.get("denom_sum_col", "")).strip() or base_col
    num_col = str(rc.get("num_sum_col", "")).strip() or base_col
    if not denom_col:
        raise UnknownSource("group_ratio_stat 需要 sum_col（或 denom_sum_col）")
    if not num_col:
        raise UnknownSource("group_ratio_stat 需要 sum_col（或 num_sum_col）")
    where = rc.get("where", [])
    if not isinstance(where, list):
        raise UnknownSource("group_ratio_stat.where 須為條件清單")
    num_where = rc.get("num_where")
    if not isinstance(num_where, list) or not num_where:
        raise UnknownSource("group_ratio_stat 需要 num_where（分子條件清單）")
    for c in list(where) + list(num_where):
        if not isinstance(c, dict) or not str(c.get("col", "")).strip():
            raise UnknownSource("group_ratio_stat 條件缺少 col")
    stat = str(rc.get("stat", "min")).strip().lower()
    if stat not in ("min", "max"):
        raise UnknownSource(f"group_ratio_stat.stat 須為 min 或 max，收到 {stat!r}")
    out = str(rc.get("out", "val")).strip().lower()
    if out not in ("val", "group"):
        raise UnknownSource(f"group_ratio_stat.out 須為 val 或 group，收到 {out!r}")
    percent = bool(rc.get("percent", False))

    def _cell_num(v: Any) -> float | None:
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        return f if math.isfinite(f) else None

    order: list[str] = []          # 各分組首次出現序（平手取首見）
    denom: dict[str, float] = {}   # 分組分母和（僅有限數值）
    numer: dict[str, float] = {}   # 分組分子和
    for r in rows:
        g = str(r.get(group_col, "")).strip()
        if not g:
            continue
        if all(_cond_holds(r, c) for c in where):
            v = _cell_num(r.get(denom_col))
            if v is not None:
                if g not in denom:
                    order.append(g)
                denom[g] = denom.get(g, 0.0) + v
        if all(_cond_holds(r, c) for c in num_where):
            v = _cell_num(r.get(num_col))
            if v is not None:
                if g not in numer:
                    order.append(g)
                numer[g] = numer.get(g, 0.0) + v
    cands = [((numer.get(g, 0.0) / denom[g]) * (100.0 if percent else 1.0),
              order.index(g), g)
             for g in order if g in denom and denom[g] != 0.0]
    if not cands:
        raise UnknownSource("group_ratio_stat: 無分組有有效分母；無法算比率")
    best = (min(cands, key=lambda t: (t[0], t[1])) if stat == "min"
            else max(cands, key=lambda t: (t[0], -t[1])))
    return best[2] if out == "group" else best[0]


def _volume_band(total: float) -> str:
    """monthly_volume 檔位（manual.md：'100k-1m' is between 100.000 and 1.000.000；邊界含兩端，TDD 前凍結）。"""
    if total < 100_000:
        return "<100k"
    if total <= 1_000_000:
        return "100k-1m"
    if total <= 5_000_000:
        return "1m-5m"
    return ">5m"


def _fraud_band(rate_pct: float) -> str:
    """monthly_fraud_level 檔位（manual.md：'7.7%-8.3%' means between 7.7 and 8.3 percent；邊界含兩端，TDD 前凍結）。"""
    if rate_pct < 7.2:
        return "<7.2%"
    if rate_pct <= 7.7:
        return "7.2%-7.7%"
    if rate_pct <= 8.3:
        return "7.7%-8.3%"
    return ">8.3%"


def _capture_delay_fits(merchant_cd: Any, fee_cd: Any) -> bool:
    """capture_delay 類別匹配（TDD 前凍結）：immediate⟺0 天、'<3'⟺0<d<3、'3-5'⟺3≤d≤5、'>5'⟺d>5、'manual'⟺商戶值即 'manual'；
    商戶值為字串（immediate/manual）時與類別同字串才算數；fee_cd 為 null＝無限制（manual.md：null applies to all）。"""
    if fee_cd is None:
        return True
    fee_cd = str(fee_cd).strip()
    m = str(merchant_cd).strip()
    try:
        d = float(m)
    except ValueError:
        return fee_cd == m
    if not math.isfinite(d):
        return fee_cd == m
    if fee_cd == "immediate":
        return d == 0
    if fee_cd == "<3":
        return 0 < d < 3
    if fee_cd == "3-5":
        return 3 <= d <= 5
    if fee_cd == ">5":
        return d > 5
    return False  # 'manual' 或其他未定義類別


def _fee_ids_lookup(
    rows: list[dict[str, Any]],
    rc: dict[str, Any],
    task_dir: pathlib.Path,
) -> tuple[int, ...]:
    """fee_ids_lookup（G2 小批 e014/dabstep-1753）：某商戶某自然月之適用 fee ID 集合。

    語義 TDD 前凍結（依 manual.md 公開規則；詳見 ops/reqloop/g2/smoke_e014/manifest.json）：
    - 列表欄位（merchant_category_code/account_type/aci）：null 或空列表＝無限制
      （manual.md："If a field is set to null it means that it applies to all possible values"；
      本 JSON 以 [] 表示無限制）；否則商戶值須在列表內。
    - 標量欄位（capture_delay/monthly_volume/monthly_fraud_level）：null＝無限制；否則須匹配。
    - 商戶 MCC/account_type/capture_delay 取 merchant_data.json；數值 delay（天）對類別映射見 _capture_delay_fits。
    - monthly_volume/monthly_fraud_level 依 payments.csv 該自然月重算（manual.md：
      "Monthly volumes and rates are computed always in natural months"）：
      總量→檔位；fraud 量（has_fraudulent_dispute==True）/總量→比率→檔位。
    - is_credit/aci 為交易層條件；商戶層查詢同時容許 credit/debit 與任一 ACI→不限制適用
      （凍結解讀；較嚴讀法會把答案縮到 1 或 0 筆，差異已記錄於 manifest）。
    - 商戶不存在／該月無行／總量 0→UNKNOWN（看不到＝UNKNOWN，不自評）。
    - 期望 ID 集永不進 detail/evidence（紅線：不向修復模型提供隱藏答案）。
    """
    fees_file = str(rc.get("fees_file", "")).strip()
    merchants_file = str(rc.get("merchants_file", "")).strip()
    merchant_name = str(rc.get("merchant", "")).strip()
    year = rc.get("year")
    month = rc.get("month")
    if not fees_file or not merchants_file or not merchant_name:
        raise UnknownSource("fee_ids_lookup 需要 fees_file/merchants_file/merchant")
    if not isinstance(year, int) or not isinstance(month, int) or not 1 <= month <= 12:
        raise UnknownSource("fee_ids_lookup 需要 year/month（整數）")
    fees_path = task_dir / fees_file
    merchants_path = task_dir / merchants_file
    if not fees_path.is_file():
        raise UnknownSource(f"fees 檔 {fees_file} 缺失")
    if not merchants_path.is_file():
        raise UnknownSource(f"商戶檔 {merchants_file} 缺失")
    with fees_path.open(encoding="utf-8") as f:
        fees = json.load(f)
    with merchants_path.open(encoding="utf-8") as f:
        merchants = json.load(f)
    if not isinstance(fees, list) or not isinstance(merchants, list):
        raise UnknownSource("fee_ids_lookup: fees/商戶檔非 JSON 列表")
    m = next(
        (x for x in merchants
         if isinstance(x, dict) and str(x.get("merchant", "")).strip() == merchant_name),
        None,
    )
    if m is None:
        raise UnknownSource(f"商戶 {merchant_name} 未找到")

    start_doy = sum(calendar.monthrange(year, k)[1] for k in range(1, month)) + 1
    end_doy = start_doy + calendar.monthrange(year, month)[1] - 1
    mrows: list[dict[str, Any]] = []
    for r in rows:
        if str(r.get("merchant", "")).strip() != merchant_name:
            continue
        if str(r.get("year", "")).strip() != str(year):
            continue
        try:
            doy = int(str(r.get("day_of_year", "")).strip())
        except ValueError:
            continue
        if start_doy <= doy <= end_doy:
            mrows.append(r)
    if not mrows:
        raise UnknownSource("該商戶該自然月無付款行；無法重算 volume/fraud")

    total = 0.0
    fraud = 0.0
    have_amount = False
    for r in mrows:
        try:
            amount = float(str(r.get("eur_amount", "")).strip())
        except ValueError:
            continue
        if not math.isfinite(amount):
            continue
        have_amount = True
        total += amount
        if str(r.get("has_fraudulent_dispute", "")).strip().lower() == "true":
            fraud += amount
    if not have_amount or total <= 0:
        raise UnknownSource("總量為 0 或不可解析；fraud 率未定義")
    vol_band = _volume_band(total)
    fraud_band = _fraud_band(fraud / total * 100.0)

    mcc_raw = m.get("merchant_category_code")
    try:
        mcc: int | None = int(mcc_raw)
    except (TypeError, ValueError):
        mcc = None
    acct = m.get("account_type")
    merchant_cd = m.get("capture_delay")

    def _fits(f: dict[str, Any]) -> bool:
        ml = f.get("merchant_category_code")
        if ml and (mcc is None or mcc not in ml):
            return False
        al = f.get("account_type")
        if al and (acct is None or acct not in al):
            return False
        if not _capture_delay_fits(merchant_cd, f.get("capture_delay")):
            return False
        mv = f.get("monthly_volume")
        if mv is not None and mv != vol_band:
            return False
        mf = f.get("monthly_fraud_level")
        if mf is not None and mf != fraud_band:
            return False
        # is_credit/aci：交易層條件，不限制商戶層適用（凍結解讀）
        return True

    return tuple(sorted(int(f["ID"]) for f in fees if isinstance(f, dict) and "ID" in f and _fits(f)))


# plain_recomputed 支援的重算型別（與下方 rtype 分派鏈保持同步；
# 守衛測試 tests/test_reqloop_extract.py::test_recompute_type_sets_match_dispatch 以源碼核對）。
PLAIN_RECOMPUTE_TYPES: frozenset[str] = frozenset(
    {"fee_ids_lookup", "mode_col", "cond_rate", "unique_count", "col_max", "scheme_fee_avg",
     "group_ratio_stat", "mean_col", "median_col", "std_col"}
)


def check_plain_recomputed(
    task_dir: pathlib.Path,
    deliverable_dir: pathlib.Path,
    item: RequirementItem,
) -> ClaimResult:
    """G2 小批（e014/dabstep）：交付物為 plain value（非 @kv 標籤），值須與對凍結資料的重算一致。

    防洩漏語意同 kv_recomputed：重算值絕不進 detail/evidence——修復模型只看到
    「你的值與按公開規則對公開資料重算不符」，不會被直接給答案。
    - 資料檔缺失 / recompute 規則不支援 → UNKNOWN（不猜）
    - 資料檔：.csv 走 csv.DictReader；.json 走 json.load（必須為 row 物件列表，否則 UNKNOWN；
      審查#2 強化——禁止 .json 走 csv.DictReader 產生垃圾字典）
    - 交付值缺失/空 → FAIL
    - 值不符重算 → FAIL（mismatch_with_recomputation；不顯示期望值）
    - 一致 → PASS

    vq-5nz.16 新增重算規則：unique_count（dabstep-10 merchant 去重計數）、
    col_max（dabstep-11 eur_amount 最大值）、
    scheme_fee_avg（dabstep-1273，manual.md 公式 fee=fixed+rate·amount/10000 在
    card_scheme×is_credit 匹配規則上的平均）。
    """
    p = item.params
    data_rel = str(p.get("data_file", "")).strip()
    if not data_rel:
        return _result(item, "UNKNOWN", "plain_recomputed.params.data_file 缺失；不自評", {"reason": "no data_file"})
    data_file = (task_dir / data_rel)
    if not data_file.is_file():
        return _result(item, "UNKNOWN",
                       f"資料檔 {data_rel} 缺失；無法重算，標 UNKNOWN", {"data_file": data_rel})
    rc = p.get("recompute")
    if not isinstance(rc, dict):
        return _result(item, "UNKNOWN", "plain_recomputed.params.recompute 缺失；不自評", {"reason": "no recompute"})
    try:
        if data_file.suffix.lower() == ".json":
            # 審查#2 強化：.json data_file 用 json.load 解析；走 csv.DictReader 會把首行
            # 當表頭、剩餘行全成垃圾字典。必須是 row 物件列表，否則 UNKNOWN（不自評）。
            with data_file.open(encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
                raise UnknownSource(
                    f"JSON 資料檔 {data_rel} 非 row 物件列表；無法可靠重算")
            rows = data
        else:
            with data_file.open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
    except (UnknownSource, OSError, json.JSONDecodeError) as e:
        return _result(item, "UNKNOWN", f"無法可靠重算（{e}）；依規則不自評", {"reason": str(e)})

    rtype = str(rc.get("type", "")).strip().lower()
    try:
        if rtype == "mode_col":
            expected: Any = _mode_col(rows, rc)
        elif rtype == "cond_rate":
            expected = _cond_rate(rows, rc)
        elif rtype == "fee_ids_lookup":
            expected = _fee_ids_lookup(rows, rc, task_dir)
        elif rtype == "unique_count":
            expected = _unique_count(rows, rc)
        elif rtype == "col_max":
            expected = _col_max(rows, rc)
        elif rtype == "group_ratio_stat":
            expected = _group_ratio_stat(rows, rc)
        elif rtype == "scheme_fee_avg":
            expected = _scheme_fee_avg(rows, rc)
        elif rtype == "mean_col":
            expected = _mean_col(rows, rc)
        elif rtype == "median_col":
            expected = _median_col(rows, rc)
        elif rtype == "std_col":
            expected = _std_col(rows, rc)
        else:
            raise UnknownSource(f"不支援的重算規則: {rtype!r}")
        if isinstance(expected, (int, float)) and not isinstance(expected, bool):
            if not math.isfinite(float(expected)):
                raise UnknownSource("重算結果非有限數值")
        rnd = rc.get("round") if rc.get("round") is not None else item.params.get("round")
        if (isinstance(rnd, int) and not isinstance(rnd, bool)
                and isinstance(expected, (int, float)) and not isinstance(expected, bool)):
            expected = round(expected, rnd)
    except (UnknownSource, OSError) as e:
        return _result(item, "UNKNOWN", f"無法可靠重算（{e}）；依規則不自評", {"reason": str(e)})

    deliv_file = resolve_deliverable_path(deliverable_dir, item.deliverable)
    if not deliv_file.is_file():
        return _result(item, "FAIL", f"答案檔缺失（{item.deliverable}）",
                       {"problem": "missing_file", "expected_in_evidence": False})
    val_str = deliv_file.read_text(encoding="utf-8").strip()
    rule_desc = (f"{str(rc.get('type'))}: {data_rel} "
                 f"{json.dumps({k: v for k, v in rc.items() if k not in ('type', 'note')}, ensure_ascii=False)}")
    got_ids: set[int] | None = None
    if rtype == "fee_ids_lookup":
        # 列表答案（fee ID 集合）：順序無關比較；空集合＝空字串（題目自帶口徑 empty list→empty string）；
        # 期望 ID 集永不進 detail/evidence（紅線）。
        if not val_str:
            got_ids = set()
        else:
            got_ids = set()
            for tok in (t.strip() for t in val_str.split(",")):
                if not tok:
                    continue
                try:
                    got_ids.add(int(tok))
                except ValueError:
                    return _result(item, "FAIL", "答案含非數字 fee ID 記號；按題目口徑應為逗號分隔的數字列表（或空字串）",
                                   {"problem": "not_a_fee_id", "value": val_str,
                                    "rule": rule_desc, "expected_in_evidence": False})
    elif not val_str:
        return _result(item, "FAIL", "答案值缺失（空檔）",
                       {"problem": "empty_value", "expected_in_evidence": False})
    # mode_col：答案可能是字串眾數（非數值）；group_ratio_stat out="group"：
    # 答案是分組名稱（dabstep-16 形）——兩者皆不做數值預檢；其餘型別行為不變。
    elif not (
        rtype == "mode_col"
        or (rtype == "group_ratio_stat" and str(rc.get("out", "val")).strip().lower() == "group")
    ):
        try:
            got_pre = float(val_str)
        except ValueError:
            return _result(item, "FAIL", "答案值不可解析為數字",
                           {"problem": "not_a_number", "value": val_str,
                            "expected_in_evidence": False})
        if not math.isfinite(got_pre):
            return _result(item, "FAIL", "答案值不可解析為數字",
                           {"problem": "not_a_number", "value": val_str,
                            "expected_in_evidence": False})


    if got_ids is not None:
        if got_ids == set(expected):
            return _result(item, "PASS",
                           f"答案與按公開規則（{rule_desc}）重算的適用 fee ID 集一致",
                           {"rule": rule_desc, "expected_in_evidence": False})
        return _result(item, "FAIL",
                       f"答案與按公開規則對公開資料重算的適用 fee ID 集不符；請依原始需求與工作區資料自行重算（期望 ID 不在證據中）",
                       {"deliverable_value": val_str,
                        "problem": "mismatch_with_recomputation",
                        "rule": rule_desc, "expected_in_evidence": False})
    exp_num: float | None = None
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        exp_num = float(expected) if math.isfinite(float(expected)) else None
    elif isinstance(expected, str):
        try:
            parsed_exp = float(expected)
        except ValueError:
            exp_num = None
        else:
            exp_num = parsed_exp if math.isfinite(parsed_exp) else None

    if exp_num is not None:
        try:
            got = float(val_str)
        except ValueError:
            return _result(item, "FAIL", "答案值不可解析為數字",
                           {"problem": "not_a_number", "value": val_str,
                            "expected_in_evidence": False})
        if not math.isfinite(got):
            return _result(item, "FAIL", "答案值不可解析為數字",
                           {"problem": "not_a_number", "value": val_str,
                            "expected_in_evidence": False})
        atol = float(p.get("atol", 1e-6))
        ok = abs(got - exp_num) <= atol
    else:
        ok = str(expected).strip() == val_str
    if not ok:
        return _result(item, "FAIL",
                       f"答案值與按公開規則對公開資料的重算不符；請依原始需求與工作區資料自行重算（期望值不在證據中）",
                       {"deliverable_value": val_str,
                        "problem": "mismatch_with_recomputation",
                        "rule": rule_desc,
                        "expected_in_evidence": False})
    return _result(item, "PASS",
                   f"答案值與按公開規則（{rule_desc}）的重算一致",
                   {"rule": rule_desc, "expected_in_evidence": False})


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
        if not isinstance(numbers, list) or not numbers or not all(isinstance(n, dict) for n in numbers):
            raise UnknownSource("summary_numbers.params.numbers 缺失或非物件列表")
        expected: list[tuple[str, Any]] = []
        for n in numbers:
            if not isinstance(n, dict):
                raise UnknownSource(f"summary_numbers.params.numbers 條目非物件: {n!r}")
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

    deliv_file = resolve_deliverable_path(deliverable_dir, item.deliverable)
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
    include_expected = bool(params.get("expected_in_evidence", True))
    for label, exp_v in expected:
        if exp_v is None:
            mismatches.append(f"{label} 重算結果為空，無法核對")
            counterexamples.append({"label": label, "expected": None})
            continue
        if not any(abs(x - float(exp_v)) <= atol for x in found):
            if include_expected:
                mismatches.append(f"摘要未包含正確的{label} {_fmt_val(exp_v)}")
                counterexamples.append({"label": label, "expected": _fmt_val(exp_v),
                                        "found_numbers_in_summary": found[:10]})
            else:
                mismatches.append(f"摘要未包含與原始資料重算一致的{label}")
                counterexamples.append({"label": label, "problem": "mismatch_with_recomputation",
                                        "found_numbers_in_summary": found[:10]})
    if mismatches:
        ev_fail: dict[str, Any] = {"counterexamples": counterexamples}
        if not include_expected:
            ev_fail["expected_in_evidence"] = False
        return _result(item, "FAIL", "; ".join(mismatches), ev_fail)
    return _result(item, "PASS", "摘要各數字均與重算一致",
                   {"recomputed": {l: _fmt_val(v) for l, v in expected}} if include_expected else {"expected_in_evidence": False})


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
    target_file = resolve_deliverable_path(deliverable_dir, file_name)
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
    elif val_type in ("float", "number"):
        try:
            flt_val = float(raw_val)
            if not math.isfinite(flt_val):
                raise ValueError("non-finite float")
        except ValueError:
            return _result(
                item,
                "FAIL",
                f"標籤 @{tag} 的值 '{raw_val}' 無法解析為浮點數",
                {"actual": raw_val, "expected_type": val_type},
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



def _no_task_dir(fn):
    """把 (deliverable_dir, item) 簽名包成統一 (task_dir, deliverable_dir, item)。"""
    def _wrapped(task_dir: pathlib.Path, deliverable_dir: pathlib.Path, item: RequirementItem) -> ClaimResult:
        return fn(deliverable_dir, item)
    return _wrapped


# verifier 白名單——單一事實來源（G2.5 vq-el4.1）。
# run_requirement_checks 依本表分派；vacant_network.reqloop.extract 的白名單由此派生。
# 不准在其他地方另造第二份清單。
_VERIFIER_DISPATCH: dict[str, Any] = {
    "csv_structure": _no_task_dir(check_csv_structure),
    "table_structure": _no_task_dir(check_csv_structure),
    "monthly_sales_metrics": check_monthly_sales_metrics,
    "monthly_top_products": check_monthly_top_products,
    "summary_metrics_consistency": check_summary_metrics_consistency,
    "rowset_filter": check_rowset_filter,
    "group_aggregate": check_group_aggregate,
    "summary_numbers": check_summary_numbers,
    "answer_kv": check_answer_kv,
    "kv_recomputed": check_kv_recomputed,
    "plain_recomputed": check_plain_recomputed,
    "tag_format": _no_task_dir(check_tag_format),
}

SUPPORTED_VERIFIERS: frozenset[str] = frozenset(_VERIFIER_DISPATCH)


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
        fn = _VERIFIER_DISPATCH.get(vname)
        if fn is None:
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

        results.append(fn(t_dir, d_dir, item))

    return results
