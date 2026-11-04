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

import csv
import datetime
import math
import pathlib
import re
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
