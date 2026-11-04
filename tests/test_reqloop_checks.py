"""
測試 vacant_network.reqloop 模組：
- 需求條目（requirements.py）
- 程式重算檢查器（checks.py）
"""

import json
import pathlib
import pytest

from vacant_network.reqloop.requirements import RequirementItem, RequirementSet
from vacant_network.reqloop.checks import (
    recompute_orders_monthly,
    run_requirement_checks,
)


def test_requirement_item_validation():
    # 正常建立
    req = RequirementItem(
        id="req_01",
        quote="排除取消單",
        deliverable="monthly_sales.csv",
        verifier="monthly_sales_metrics",
        kind="explicit",
    )
    assert req.id == "req_01"
    assert req.quote == "排除取消單"
    assert req.kind == "explicit"
    assert not req.unverified

    # 缺少 quote 應報錯
    with pytest.raises(ValueError, match="must include quote"):
        RequirementItem(
            id="req_02",
            quote="   ",
            deliverable="monthly_sales.csv",
            verifier="csv_structure",
        )

    # 非法 kind 應報錯
    with pytest.raises(ValueError, match="Invalid kind"):
        RequirementItem(
            id="req_03",
            quote="測試",
            deliverable="monthly_sales.csv",
            verifier="csv_structure",
            kind="custom_invalid",  # type: ignore
        )

    # 轉換為原生 Claim
    claim = req.to_claim()
    assert claim.id == "req_01"
    assert claim.verifier == "monthly_sales_metrics"
    assert claim.params["quote"] == "排除取消單"


def test_requirement_set_roundtrip(tmp_path: pathlib.Path):
    req_file = tmp_path / "requirements.json"
    req_set = RequirementSet(
        task_id="task_test_orders",
        items=[
            RequirementItem(
                id="req_structure",
                quote="產出 monthly_sales.csv",
                deliverable="monthly_sales.csv",
                verifier="csv_structure",
                params={"required_columns": ["month", "net_sales"]},
            ),
            RequirementItem(
                id="req_unverified",
                quote="視覺排版應美觀",
                deliverable="summary.md",
                verifier="human_look",
                unverified=True,
            ),
        ],
    )
    req_set.save(req_file)

    loaded = RequirementSet.load(req_file)
    assert loaded.task_id == "task_test_orders"
    assert len(loaded.items) == 2
    assert loaded.items[1].unverified is True


def test_recompute_and_checks(tmp_path: pathlib.Path):
    # 建立測試用 orders.csv
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    orders_csv = task_dir / "orders.csv"
    orders_csv.write_text(
        "order_id,order_date,status,product_name,net_amount\n"
        "ORD01,2026-09-05,COMPLETED,Keyboard,3000.0\n"
        "ORD02,2026-09-12,CANCELLED,Keyboard,3000.0\n"  # 取消單
        "ORD03,2026-09-15,COMPLETED,Mouse,1500.0\n"
        "ORD03,2026-09-15,COMPLETED,Mouse,1500.0\n"   # 重複單
        "ORD04,2026-10-02,COMPLETED,Monitor,8000.0\n"
        "ORD05,2026-10-18,COMPLETED,Sticker,50.0\n"
        "ORD06,2026-10-20,COMPLETED,Sticker,50.0\n",
        encoding="utf-8",
    )

    # 1. 測試原始重算函式
    metrics, top_prods, filtered = recompute_orders_monthly(
        task_dir,
        {
            "input_csv": "orders.csv",
            "exclude_status": ["CANCELLED"],
            "dedup_by": "order_id",
            "date_col": "order_date",
            "amount_col": "net_amount",
            "product_col": "product_name",
        },
    )
    # 9月有效訂單：ORD01, ORD03 => 2 筆，淨額 4500.0
    assert metrics["2026-09"]["orders_count"] == 2
    assert metrics["2026-09"]["net_sales"] == 4500.0
    # 10月有效訂單：ORD04, ORD05, ORD06 => 3 筆，淨額 8100.0
    assert metrics["2026-10"]["orders_count"] == 3
    assert metrics["2026-10"]["net_sales"] == 8100.0
    # 10月商品排行：Monitor (8000.0) 第一，Sticker (100.0，2筆) 第二
    assert top_prods["2026-10"][0][0] == "Monitor"
    assert top_prods["2026-10"][1][0] == "Sticker"

    # 2. 定義測試需求集合
    req_set = RequirementSet(
        task_id="test_orders",
        items=[
            RequirementItem(
                id="req_csv_struct",
                quote="產出 CSV 包含必要欄位",
                deliverable="monthly_sales.csv",
                verifier="csv_structure",
                params={"required_columns": ["month", "orders_count", "net_sales", "top_1_product"]},
            ),
            RequirementItem(
                id="req_metrics",
                quote="排除取消與重複，計算各月淨額與訂單數",
                deliverable="monthly_sales.csv",
                verifier="monthly_sales_metrics",
                params={"input_csv": "orders.csv"},
            ),
            RequirementItem(
                id="req_ranking",
                quote="依淨銷售額計算前三名商品",
                deliverable="monthly_sales.csv",
                verifier="monthly_top_products",
                params={"input_csv": "orders.csv", "top_n": 1},
            ),
            RequirementItem(
                id="req_summary",
                quote="摘要包含兩月合計淨銷售總額",
                deliverable="summary.md",
                verifier="summary_metrics_consistency",
                params={"input_csv": "orders.csv"},
            ),
            RequirementItem(
                id="req_unverified",
                quote="排版風格符合個人審美",
                deliverable="summary.md",
                verifier="aesthetic_eval",
                unverified=True,
            ),
        ],
    )

    # 3. 測試 正確交付物 (Good)
    good_dir = tmp_path / "good"
    good_dir.mkdir()
    (good_dir / "monthly_sales.csv").write_text(
        "month,orders_count,net_sales,top_1_product\n"
        "2026-09,2,4500.0,Keyboard\n"
        "2026-10,3,8100.0,Monitor\n",
        encoding="utf-8",
    )
    (good_dir / "summary.md").write_text(
        "# 月度銷售分析報告\n"
        "本期兩月合計淨銷售總額為 12,600.00 元。\n",
        encoding="utf-8",
    )

    results = run_requirement_checks(task_dir, req_set, good_dir)
    res_map = {r.claim_id: r for r in results}
    assert res_map["req_csv_struct"].status == "PASS"
    assert res_map["req_metrics"].status == "PASS"
    assert res_map["req_ranking"].status == "PASS"
    assert res_map["req_summary"].status == "PASS"
    assert res_map["req_unverified"].status == "UNKNOWN"  # 不得自評，應為 UNKNOWN

    # 4. 測試 錯誤交付物 (Bad: 包含了取消單)
    bad_dir_cancelled = tmp_path / "bad_cancelled"
    bad_dir_cancelled.mkdir()
    (bad_dir_cancelled / "monthly_sales.csv").write_text(
        "month,orders_count,net_sales,top_1_product\n"
        "2026-09,3,7500.0,Keyboard\n"  # 誤將取消單加進去
        "2026-10,3,8100.0,Monitor\n",
        encoding="utf-8",
    )
    (bad_dir_cancelled / "summary.md").write_text("本期兩月合計淨銷售總額為 12,600.00 元。", encoding="utf-8")
    results_bad = run_requirement_checks(task_dir, req_set, bad_dir_cancelled)
    res_bad_map = {r.claim_id: r for r in results_bad}
    assert res_bad_map["req_metrics"].status == "FAIL"
    assert len(res_bad_map["req_metrics"].evidence["counterexamples"]) > 0

    # 5. 測試 錯誤交付物 (Bad: 排名誤依訂單筆數而非金額)
    bad_dir_ranking = tmp_path / "bad_ranking"
    bad_dir_ranking.mkdir()
    (bad_dir_ranking / "monthly_sales.csv").write_text(
        "month,orders_count,net_sales,top_1_product\n"
        "2026-09,2,4500.0,Keyboard\n"
        "2026-10,3,8100.0,Sticker\n",  # Sticker 有 2 筆，Monitor 只有 1 筆，若依筆數排 Sticker 第一
        encoding="utf-8",
    )
    (bad_dir_ranking / "summary.md").write_text("兩月合計淨銷售總額為 12,600.00 元。", encoding="utf-8")
    results_bad_rank = run_requirement_checks(task_dir, req_set, bad_dir_ranking)
    res_bad_rank_map = {r.claim_id: r for r in results_bad_rank}
    assert res_bad_rank_map["req_ranking"].status == "FAIL"
    assert "排序依據錯誤" in res_bad_rank_map["req_ranking"].evidence["counterexamples"][0]["reason"]
