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


# ---------------------------------------------------------------------------
# summary_metrics_consistency：數值必須綁到「合計淨銷售總額」條目（P000-01b）
# ---------------------------------------------------------------------------


def _make_orders_task(tmp_path: pathlib.Path) -> pathlib.Path:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "orders.csv").write_text(
        "order_id,order_date,status,product_name,net_amount\n"
        "ORD01,2026-09-05,COMPLETED,Keyboard,3000.0\n"
        "ORD02,2026-09-12,CANCELLED,Keyboard,3000.0\n"
        "ORD03,2026-09-15,COMPLETED,Mouse,1500.0\n"
        "ORD03,2026-09-15,COMPLETED,Mouse,1500.0\n"
        "ORD04,2026-10-02,COMPLETED,Monitor,8000.0\n"
        "ORD05,2026-10-18,COMPLETED,Sticker,50.0\n"
        "ORD06,2026-10-20,COMPLETED,Sticker,50.0\n",
        encoding="utf-8",
    )
    return task_dir


def _summary_req_set() -> RequirementSet:
    return RequirementSet(
        task_id="t",
        items=[
            RequirementItem(
                id="req_summary",
                quote="內文中需明確載明「兩月合計淨銷售總額」（精確數值）",
                deliverable="summary.md",
                verifier="summary_metrics_consistency",
                params={"input_csv": "orders.csv"},
            ),
        ],
    )


def _summary_status(tmp_path: pathlib.Path, task_dir: pathlib.Path, text: str) -> str:
    d = tmp_path / "d"
    d.mkdir(exist_ok=True)
    (d / "summary.md").write_text(text, encoding="utf-8")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, _summary_req_set(), d)}
    return res["req_summary"].status


def test_summary_wrong_total_not_rescued_by_correct_number_elsewhere(tmp_path: pathlib.Path):
    """P000-01b 反例：合計條目寫錯值時，不得因全文其他地方出現正確金額（參考代碼）而 PASS。"""
    task_dir = _make_orders_task(tmp_path)
    status = _summary_status(
        tmp_path, task_dir,
        "兩月合計淨銷售總額：99,999.00 元。\n參考代碼：12,600.00。\n",
    )
    assert status == "FAIL"


def test_summary_contradictory_totals_cannot_pass(tmp_path: pathlib.Path):
    """同一指標的多個陳述互相矛盾（一個對一個錯）不得 PASS。"""
    task_dir = _make_orders_task(tmp_path)
    status = _summary_status(
        tmp_path, task_dir,
        "兩月合計淨銷售總額為 12,600.00 元。\n兩月合計金額：88,000.00 元。\n",
    )
    assert status == "FAIL"


def test_summary_no_bound_total_is_unknown(tmp_path: pathlib.Path):
    """數字沒有綁到「合計淨銷售總額」條目（看不到可對應欄位）＝UNKNOWN，不是 PASS。"""
    task_dir = _make_orders_task(tmp_path)
    status = _summary_status(tmp_path, task_dir, "本期淨銷售額 12,600.00 元。\n")
    assert status == "UNKNOWN"


def test_summary_number_formats_still_pass(tmp_path: pathlib.Path):
    """數字格式回歸：$、千分位、無小數、總計+元 等寫法仍應 PASS。"""
    task_dir = _make_orders_task(tmp_path)
    for i, text in enumerate([
        "兩月合計淨銷售總額為 $12,600.00 元。",
        "兩月合計淨銷售總額為 12600.00。",
        "兩月合計淨銷售總額：12,600 元",
        "兩月總計 12,600.00 元。",
    ]):
        assert _summary_status(tmp_path, task_dir, text) == "PASS", text


# ---------------------------------------------------------------------------
# 通用重算檢查器：rowset_filter / group_aggregate / summary_numbers
# ---------------------------------------------------------------------------

def _req_set(verifier: str, params: dict, deliverable: str = "out.csv"):
    return RequirementSet(
        task_id="t",
        items=[
            RequirementItem(
                id="req_main",
                quote="測試需求",
                deliverable=deliverable,
                verifier=verifier,
                params=params,
            )
        ],
    )


def _write(path: pathlib.Path, text: str, **_kwargs) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_rowset_filter_pass_and_catches(tmp_path: pathlib.Path):
    task_dir = tmp_path / "task"
    _write(
        task_dir / "inventory.csv",
        "item_id,item_name,current_stock,safety_stock,unit_cost,supplier_status\n"
        "A1,電阻,8,40,0.05,ACTIVE\n"
        "A2,MCU,5,20,10.0,ACTIVE\n"
        "A2,MCU,5,20,10.0,ACTIVE\n"      # 重複列
        "A3,電容,50,20,1.0,ACTIVE\n"      # 未低於安全量
        "A4,晶片,3,30,2.0,DISCONTINUED\n"  # 停產，須排除
        "A5,晶振,10,10,0.01,ACTIVE\n",    # 10 < 10 為假
    )
    params = {
        "input_csv": "inventory.csv",
        "exclude": [{"col": "supplier_status", "op": "eq", "value": "DISCONTINUED"}],
        "dedup_by": "item_id",
        "include": [{"col": "current_stock", "op": "lt", "value": "safety_stock"}],
        "identity": ["item_id"],
        "values": {
            "item_name": "item_name",
            "current_stock": "current_stock",
            "safety_stock": "safety_stock",
            "restock_needed": {"expr": "safety_stock - current_stock"},
            "estimated_cost": {"expr": "(safety_stock - current_stock) * unit_cost", "round": 2},
        },
        "atol": 0.01,
    }
    req_set = _req_set("rowset_filter", params, "restock.csv")

    # good：正確兩列（A1：32、1.60；A2：15、150.00）
    good = tmp_path / "good"
    _write(
        good / "restock.csv",
        "item_id,item_name,current_stock,safety_stock,restock_needed,estimated_cost\n"
        "A1,電阻,8,40,32,1.60\n"
        "A2,MCU,5,20,15,150.00\n",
    )
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, good)}
    assert res["req_main"].status == "PASS"

    # bad：多帶了停產品項 A4（行集不符）
    bad_extra = tmp_path / "bad_extra"
    _write(
        bad_extra / "restock.csv",
        "item_id,item_name,current_stock,safety_stock,restock_needed,estimated_cost\n"
        "A1,電阻,8,40,32,1.60\n"
        "A2,MCU,5,20,15,150.00\n"
        "A4,晶片,3,30,27,54.00\n",
    )
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, bad_extra)}
    assert res["req_main"].status == "FAIL"
    assert res["req_main"].evidence.get("counterexamples")

    # bad：金額算錯（150.00 → 140.00）
    bad_val = tmp_path / "bad_val"
    _write(
        bad_val / "restock.csv",
        "item_id,item_name,current_stock,safety_stock,restock_needed,estimated_cost\n"
        "A1,電阻,8,40,32,1.60\n"
        "A2,MCU,5,20,15,140.00\n",
    )
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, bad_val)}
    assert res["req_main"].status == "FAIL"
    ce = res["req_main"].evidence["counterexamples"]
    assert any(c.get("field") == "estimated_cost" for c in ce)


def test_rowset_filter_unsafe_expr_is_unknown(tmp_path: pathlib.Path):
    task_dir = tmp_path / "task"
    _write(
        task_dir / "inventory.csv",
        "item_id,current_stock\nA1,8\n",
    )
    params = {
        "input_csv": "inventory.csv",
        "identity": ["item_id"],
        "values": {"hacked": {"expr": "__import__('os').getcwd()"}},
    }
    req_set = _req_set("rowset_filter", params, "restock.csv")
    good = tmp_path / "good"
    _write(good / "restock.csv", "item_id,hacked\nA1,x\n")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, good)}
    # 不安全運算式＝無可靠重算能力 ⇒ UNKNOWN，不得 PASS 也不得 FAIL
    assert res["req_main"].status == "UNKNOWN"


def test_group_aggregate_counts_ratio_mean(tmp_path: pathlib.Path):
    task_dir = tmp_path / "task"
    _write(
        task_dir / "grades.csv",
        "student_id,class_name,midterm_score,final_score,status\n"
        "S1,Class_A,78,82,ENROLLED\n"
        "S2,Class_A,55,60,ENROLLED\n"
        "S2,Class_A,55,60,ENROLLED\n"   # 重複
        "S3,Class_B,90,70,ENROLLED\n"
        "S4,Class_B,40,50,WITHDRAWN\n",  # 退學，須排除
    )
    params = {
        "input_csv": "grades.csv",
        "exclude": [{"col": "status", "op": "eq", "value": "WITHDRAWN"}],
        "dedup_by": "student_id",
        "group_by": ["class_name"],
        "compute": [{"name": "total_score", "expr": "midterm_score * 0.4 + final_score * 0.6"}],
        "aggregates": [
            {"name": "student_count", "type": "count"},
            {"name": "passing_count", "type": "count_if", "expr": "total_score >= 60.0"},
            {"name": "pass_rate", "type": "ratio", "num": "passing_count", "den": "student_count", "round": 2},
            {"name": "average_score", "type": "mean", "expr": "total_score", "round": 2},
        ],
        "atol": 0.01,
    }
    req_set = _req_set("group_aggregate", params, "class_summary.csv")

    # Class_A: S1 total 80.4 (pass), S2 total 58 (fail) → 2,1,0.50,69.20
    # Class_B: S3 total 90*0.4+70*0.6 = 78.0 (pass) → 1,1,1.00,78.00
    good = tmp_path / "good"
    _write(
        good / "class_summary.csv",
        "class_name,student_count,passing_count,pass_rate,average_score\n"
        "Class_A,2,1,0.50,69.20\n"
        "Class_B,1,1,1.00,78.00\n",
    )
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, good)}
    assert res["req_main"].status == "PASS"

    # bad：平均算錯
    bad_mean = tmp_path / "bad_mean"
    _write(
        bad_mean / "class_summary.csv",
        "class_name,student_count,passing_count,pass_rate,average_score\n"
        "Class_A,2,1,0.50,60.20\n"
        "Class_B,1,1,1.00,78.00\n",
    )
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, bad_mean)}
    assert res["req_main"].status == "FAIL"

    # bad：Class_A 被大小寫拆成兩行（normalize 後同組重複）
    bad_case = tmp_path / "bad_case"
    _write(
        bad_case / "class_summary.csv",
        "class_name,student_count,passing_count,pass_rate,average_score\n"
        "Class_A,1,1,1.00,80.40\n"
        "class_a,1,0,0.00,58.00\n"
        "Class_B,1,1,1.00,78.00\n",
    )
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, bad_case)}
    assert res["req_main"].status == "FAIL"


def test_group_aggregate_normalize_and_default(tmp_path: pathlib.Path):
    task_dir = tmp_path / "task"
    _write(
        task_dir / "expenses.csv",
        "expense_id,category,subcategory,amount\n"
        "E1,IT,hardware,100.00\n"
        "E2,it,Hardware,50.25\n"
        "E3,IT,,10.00\n"
        "E4,IT,,10.00\n",
    )
    params = {
        "input_csv": "expenses.csv",
        "group_by": ["category", "subcategory"],
        "group_normalize": {
            "category": "lower",
            "subcategory": {"lower": True, "default": "unspecified"},
        },
        "aggregates": [{"name": "total_amount", "type": "sum", "expr": "amount", "round": 2}],
        "atol": 0.01,
    }
    req_set = _req_set("group_aggregate", params, "expense_summary.csv")

    good = tmp_path / "good"
    _write(
        good / "expense_summary.csv",
        "category,subcategory,total_amount\n"
        "it,hardware,150.25\n"
        "it,unspecified,20.00\n",
    )
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, good)}
    assert res["req_main"].status == "PASS"

    # bad：subcategory 大小寫拆成兩組（同組重複計）
    bad_split = tmp_path / "bad_split"
    _write(
        bad_split / "expense_summary.csv",
        "category,subcategory,total_amount\n"
        "it,hardware,100.00\n"
        "it,Hardware,50.25\n"
        "it,unspecified,20.00\n",
    )
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, bad_split)}
    assert res["req_main"].status == "FAIL"


def test_group_aggregate_distinct_mean_skip_empty(tmp_path: pathlib.Path):
    task_dir = tmp_path / "task"
    _write(
        task_dir / "traffic.csv",
        "visit_id,user_id,day_index,hour,tz_offset_hours,dwell_seconds\n"
        "V1,U1,1,9,8,120\n"
        "V2,U2,1,23,8,85\n"
        "V3,U1,1,23,8,\n"
        "V4,U3,2,0,8,60\n"
        "V5,U3,2,17,8,\n",
    )
    params = {
        "input_csv": "traffic.csv",
        "compute": [{"name": "local_day", "expr": "day_index + ((hour + tz_offset_hours) // 24)"}],
        "group_by": ["local_day"],
        "aggregates": [
            {"name": "visits", "type": "count"},
            {"name": "uv", "type": "distinct", "col": "user_id"},
            {"name": "avg_dwell", "type": "mean_skip_empty", "col": "dwell_seconds", "round": 2},
        ],
        "atol": 0.01,
    }
    req_set = _req_set("group_aggregate", params, "daily_traffic.csv")

    # local_day = day_index + ((hour+tz)//24)：
    #   V1 d1 h9  → 1；V2 d1 h23 → 2；V3 d1 h23 → 2；V4 d2 h0 → 2；V5 d2 h17 → 3
    # day1: {V1(U1,120)}          → visits 1, uv 1, avg 120.00
    # day2: {V2(U2,85),V3(U1,),V4(U3,60)} → visits 3, uv 3, avg (85+60)/2=72.50
    # day3: {V5(U3,)}             → visits 1, uv 1, avg 空
    good = tmp_path / "good"
    _write(
        good / "daily_traffic.csv",
        "local_day,visits,uv,avg_dwell\n"
        "1,1,1,120.00\n"
        "2,3,3,72.50\n"
        "3,1,1,\n",
    )
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, good)}
    assert res["req_main"].status == "PASS"

    # bad：未做時區換算（照 day_index 分組）
    # d1: V1,V2,V3 → 3, uv2, avg (120+85)/2=102.50；d2: V4,V5 → 2, uv1, avg 60.00
    bad_no_tz = tmp_path / "bad_no_tz"
    _write(
        bad_no_tz / "daily_traffic.csv",
        "local_day,visits,uv,avg_dwell\n"
        "1,3,2,102.50\n"
        "2,2,1,60.00\n",
    )
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, bad_no_tz)}
    assert res["req_main"].status == "FAIL"


def test_summary_numbers_csv_and_pct(tmp_path: pathlib.Path):
    task_dir = tmp_path / "task"
    _write(
        task_dir / "grades.csv",
        "student_id,midterm_score,final_score\n"
        "S1,78,82\n"
        "S2,55,60\n"
        "S3,90,70\n",
    )
    params = {
        "input_csv": "grades.csv",
        "compute": [{"name": "total_score", "expr": "midterm_score * 0.4 + final_score * 0.6"}],
        "numbers": [
            {"type": "count", "label": "全年級修課人數"},
            {"type": "pct_if", "expr": "total_score >= 60.0", "label": "全年級及格率", "round": 2},
            {"type": "mean", "expr": "total_score", "label": "全年級平均總評", "round": 2},
        ],
        "atol": 0.01,
    }
    req_set = _req_set("summary_numbers", params, "summary.md")

    # S1 80.4 pass / S2 58 fail / S3 78.0 pass → count 3, pct 66.67, mean 216.4/3=72.13
    good = tmp_path / "good"
    _write(
        good / "summary.md",
        "# 摘要\n全年級修課人數：3 人\n全年級及格率（總評 ≥ 60.0）：66.67%\n全年級平均總評：72.13 分\n",
    )
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, good)}
    assert res["req_main"].status == "PASS"

    # bad：及格率寫錯
    bad_pct = tmp_path / "bad_pct"
    _write(
        bad_pct / "summary.md",
        "# 摘要\n全年級修課人數：3 人\n全年級及格率（總評 ≥ 60.0）：80.00%\n全年級平均總評：72.13 分\n",
    )
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, bad_pct)}
    assert res["req_main"].status == "FAIL"
    ce = res["req_main"].evidence["counterexamples"]
    assert any("及格率" in str(c) for c in ce)


def test_summary_numbers_json_flatten(tmp_path: pathlib.Path):
    task_dir = tmp_path / "task"
    _write(
        task_dir / "events.json",
        json.dumps(
            [
                {"event_id": "e1", "event_type": "CLICK", "payload": {"duration_ms": 120}},
                {"event_id": "e2", "event_type": "Click", "payload": {}},
                {"event_id": "e3", "event_type": "VIEW", "payload": {"duration_ms": 80}},
            ]
        ),
        encoding="utf-8",
    )
    flatten = [{"path": "payload.duration_ms", "as": "duration_ms", "impute": 0}]
    params_group = {
        "input_json": "events.json",
        "flatten": flatten,
        "group_by": ["event_type"],
        "group_normalize": {"event_type": "lower"},
        "aggregates": [
            {"name": "event_count", "type": "count"},
            {"name": "total_duration_ms", "type": "sum", "expr": "duration_ms"},
        ],
        "atol": 0.5,
    }
    params_summary = {
        "input_json": "events.json",
        "flatten": flatten,
        "numbers": [
            {"type": "count", "label": "事件總數"},
            {"type": "sum", "expr": "duration_ms", "label": "總時長"},
        ],
        "atol": 0.5,
    }

    req_set = RequirementSet(
        task_id="t",
        items=[
            RequirementItem(id="req_g", quote="g", deliverable="event_stats.csv", verifier="group_aggregate", params=params_group),
            RequirementItem(id="req_s", quote="s", deliverable="summary.md", verifier="summary_numbers", params=params_summary),
        ],
    )

    good = tmp_path / "good"
    _write(
        good / "event_stats.csv",
        "event_type,event_count,total_duration_ms\n"
        "click,2,120\n"
        "view,1,80\n",
    )
    _write(good / "summary.md", "# 摘要\n事件總數：3 筆（event_type 不分大小寫）\n總時長：200 ms\n")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, good)}
    assert res["req_g"].status == "PASS"
    assert res["req_s"].status == "PASS"

    # bad：總時長抄錯（漏掉 impute 0 的那筆仍影響不了總和，但這裡直接寫錯數字）
    bad_sum = tmp_path / "bad_sum"
    _write(
        bad_sum / "event_stats.csv",
        "event_type,event_count,total_duration_ms\n"
        "click,2,120\n"
        "view,1,80\n",
    )
    _write(bad_sum / "summary.md", "# 摘要\n事件總數：3 筆\n總時長：210 ms\n")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, bad_sum)}
    assert res["req_g"].status == "PASS"
    assert res["req_s"].status == "FAIL"


def test_new_verifiers_missing_input_is_unknown(tmp_path: pathlib.Path):
    # 原始輸入不存在＝看不到 ⇒ UNKNOWN，不得 FAIL（更不得 PASS）
    task_dir = tmp_path / "task"
    task_dir.mkdir(parents=True, exist_ok=True)
    params = {"input_csv": "missing.csv", "group_by": ["a"], "aggregates": [{"name": "n", "type": "count"}]}
    req_set = _req_set("group_aggregate", params, "out.csv")
    d = tmp_path / "d"
    _write(d / "out.csv", "a,n\nx,1\n")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, d)}
    assert res["req_main"].status == "UNKNOWN"


def test_group_aggregate_max_min(tmp_path: pathlib.Path):
    """max/min 聚合：組內極值必須逐組核對；空白值不允許被吞掉（⇒UNKNOWN）。"""
    task_dir = tmp_path / "task"
    _write(
        task_dir / "tickets.csv",
        "ticket_id,channel,sla_target_hours,resolved_hours\n"
        "T1,web,4,2.5\n"
        "T2,web,4,6\n"
        "T3,mail,8,1.5\n"
        "T4,mail,8,8\n"
        "T5,chat,2,\n"
    )
    params = {
        "input_csv": "tickets.csv",
        "include": [{"col": "resolved_hours", "op": "ne", "value": ""}],  # 只核對有數值的列
        "group_by": ["channel"],
        "aggregates": [
            {"name": "n", "type": "count"},
            {"name": "worst_hours", "type": "max", "col": "resolved_hours"},
            {"name": "best_hours", "type": "min", "col": "resolved_hours"},
        ],
        "atol": 0.01,
    }
    req_set = _req_set("group_aggregate", params, "sla_report.csv")

    # web: T1 2.5, T2 6 → n2 worst6 best2.5；mail: T3 1.5, T4 8 → n2 worst8 best1.5
    good = tmp_path / "good"
    _write(
        good / "sla_report.csv",
        "channel,n,worst_hours,best_hours\n"
        "web,2,6,2.5\n"
        "mail,2,8,1.5\n"
    )
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, good)}
    assert res["req_main"].status == "PASS"

    # bad：worst_hours 抄成平均值（6→4.25、8→4.75）
    bad_max = tmp_path / "bad_max"
    _write(
        bad_max / "sla_report.csv",
        "channel,n,worst_hours,best_hours\n"
        "web,2,4.25,2.5\n"
        "mail,2,4.75,1.5\n"
    )
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, bad_max)}
    assert res["req_main"].status == "FAIL"
    assert any("worst_hours" in str(c) for c in res["req_main"].evidence["counterexamples"])

    # bad：min/max 互換（best 抄成 worst）
    bad_swap = tmp_path / "bad_swap"
    _write(
        bad_swap / "sla_report.csv",
        "channel,n,worst_hours,best_hours\n"
        "web,2,6,6\n"
        "mail,2,8,8\n"
    )
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, bad_swap)}
    assert res["req_main"].status == "FAIL"


def test_group_aggregate_max_empty_value_is_unknown(tmp_path: pathlib.Path):
    """max 遇到空白值＝看不到 ⇒ UNKNOWN（不得拿其餘值假裝算出極值）。"""
    task_dir = tmp_path / "task"
    _write(
        task_dir / "tickets.csv",
        "ticket_id,channel,resolved_hours\n"
        "T1,web,2.5\n"
        "T2,web,\n"
    )
    params = {
        "input_csv": "tickets.csv",
        "group_by": ["channel"],
        "aggregates": [{"name": "worst_hours", "type": "max", "col": "resolved_hours"}],
    }
    req_set = _req_set("group_aggregate", params, "sla_report.csv")
    d = tmp_path / "d"
    _write(d / "sla_report.csv", "channel,worst_hours\nweb,2.5\n")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, d)}
    assert res["req_main"].status == "UNKNOWN"


def test_summary_numbers_max_min(tmp_path: pathlib.Path):
    task_dir = tmp_path / "task"
    _write(
        task_dir / "tickets.csv",
        "ticket_id,channel,resolved_hours\n"
        "T1,web,2.5\n"
        "T2,web,6\n"
        "T3,mail,1.5\n"
    )
    params = {
        "input_csv": "tickets.csv",
        "numbers": [
            {"type": "count", "label": "結案工單數"},
            {"type": "max", "col": "resolved_hours", "label": "最長處理時數"},
            {"type": "min", "col": "resolved_hours", "label": "最短處理時數"},
        ],
        "atol": 0.01,
    }
    req_set = _req_set("summary_numbers", params, "summary.md")

    good = tmp_path / "good"
    _write(good / "summary.md", "# 摘要\n結案工單數：3 張\n最長處理時數：6 小時\n最短處理時數：1.5 小時\n")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, good)}
    assert res["req_main"].status == "PASS"

    # bad：最長時數寫成平均（3.5）
    bad_max = tmp_path / "bad_max"
    _write(bad_max / "summary.md", "# 摘要\n結案工單數：3 張\n最長處理時數：3.5 小時\n最短處理時數：1.5 小時\n")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, bad_max)}
    assert res["req_main"].status == "FAIL"
    assert any("最長處理時數" in str(c) for c in res["req_main"].evidence["counterexamples"])


def test_unknown_aggregate_type_stays_unknown(tmp_path: pathlib.Path):
    """未實作的聚合類型一律 UNKNOWN，不得 FAIL 更不得 PASS。"""
    task_dir = tmp_path / "task"
    _write(task_dir / "t.csv", "a,b\nx,1\n")
    params = {
        "input_csv": "t.csv",
        "group_by": ["a"],
        "aggregates": [{"name": "m", "type": "median", "col": "b"}],
    }
    req_set = _req_set("group_aggregate", params, "out.csv")
    d = tmp_path / "d"
    _write(d / "out.csv", "a,m\nx,1\n")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, d)}
    assert res["req_main"].status == "UNKNOWN"


# ── kv_recomputed 新重算規則（G2 小批：e013 真實草稿，2026-11-04）────────

def test_kv_recomputed_mean_int_col_pass_and_fail(tmp_path: pathlib.Path):
    """mean_int_col：Int64 語意——空白/不可解析（如 '100[10-30]'）忽略，其餘取均值。"""
    task_dir = tmp_path / "task"
    _write(
        task_dir / "cases.csv",
        "Country,No. of cases\nA,100\nB,200[10-30]\nC,\nD,300\n",
    )
    params = {
        "key": "mean_cases",
        "data_file": "cases.csv",
        "recompute": {"type": "mean_int_col", "col": "No. of cases",
                      "note": "轉 Int64；Null/空/不可解析忽略"},
    }
    req_set = _req_set("kv_recomputed", params, "answer.txt")
    good = tmp_path / "good"
    _write(good / "answer.txt", "@mean_cases[200]\n")   # (100+300)/2
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, good)}
    assert res["req_main"].status == "PASS"

    bad = tmp_path / "bad"
    _write(bad / "answer.txt", "@mean_cases[250]\n")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, bad)}
    r = res["req_main"]
    assert r.status == "FAIL"
    assert r.evidence.get("expected_in_evidence") is False   # 重算值不進證據


def test_kv_recomputed_mean_int_col_no_parseable_is_unknown(tmp_path: pathlib.Path):
    task_dir = tmp_path / "task"
    _write(task_dir / "cases.csv", "Country,No. of cases\nA,\nB,xx[1-2]\n")
    params = {"key": "k", "data_file": "cases.csv",
              "recompute": {"type": "mean_int_col", "col": "No. of cases"}}
    req_set = _req_set("kv_recomputed", params, "answer.txt")
    d = tmp_path / "d"
    _write(d / "answer.txt", "@k[1]\n")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, d)}
    assert res["req_main"].status == "UNKNOWN"


def test_kv_recomputed_max_row_first_first_tie_wins(tmp_path: pathlib.Path):
    """max_row_first：選取欄最大值、平手取檔案序第一列、輸出該列 out_col。"""
    task_dir = tmp_path / "task"
    _write(
        task_dir / "storms.csv",
        "name,max_storm_cat,max_sust_wind\n"
        "BRET,1,43.45\n"
        "IRMA,6,156.41568\n"
        "OTA,6,165.10544\n",   # OTA 同為最高類別但 IRMA 在前
    )
    params = {
        "key": "max_wind_speed",
        "data_file": "storms.csv",
        "recompute": {"type": "max_row_first", "sel_col": "max_storm_cat",
                      "out_col": "max_sust_wind", "round": 2},
    }
    req_set = _req_set("kv_recomputed", params, "answer.txt")
    good = tmp_path / "good"
    _write(good / "answer.txt", "@max_wind_speed[156.42]\n")   # IRMA（先出現）
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, good)}
    assert res["req_main"].status == "PASS"

    bad = tmp_path / "bad"
    _write(bad / "answer.txt", "@max_wind_speed[165.11]\n")   # 取了組內最大風速（錯）
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, bad)}
    assert res["req_main"].status == "FAIL"


def test_kv_recomputed_pearson2_pass_and_fail(tmp_path: pathlib.Path):
    """pearson2：成對可解析行、Pearson r、可依 round。"""
    task_dir = tmp_path / "task"
    _write(
        task_dir / "loans.csv",
        "ApplicantIncome,LoanAmount\n1,2\n2,4\n3,5\n,99\n4,8\n",   # 缺值行忽略
    )
    params = {
        "key": "corr",
        "data_file": "loans.csv",
        "recompute": {"type": "pearson2", "col_a": "ApplicantIncome",
                      "col_b": "LoanAmount", "round": 2},
    }
    req_set = _req_set("kv_recomputed", params, "answer.txt")
    # r = sqrt(27/28) ≈ 0.98198 → round 2 = 0.98
    good = tmp_path / "good"
    _write(good / "answer.txt", "@corr[0.98]\n")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, good)}
    assert res["req_main"].status == "PASS"

    bad = tmp_path / "bad"
    _write(bad / "answer.txt", "@corr[0.97]\n")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, bad)}
    assert res["req_main"].status == "FAIL"


def test_kv_recomputed_pearson2_constant_column_is_unknown(tmp_path: pathlib.Path):
    task_dir = tmp_path / "task"
    _write(task_dir / "x.csv", "a,b\n1,5\n2,5\n3,5\n")
    params = {"key": "k", "data_file": "x.csv",
              "recompute": {"type": "pearson2", "col_a": "a", "col_b": "b"}}
    req_set = _req_set("kv_recomputed", params, "answer.txt")
    d = tmp_path / "d"
    _write(d / "answer.txt", "@k[0]\n")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, d)}
    assert res["req_main"].status == "UNKNOWN"


# ── plain_recomputed＋mode_col（G2 小批：e014/dabstep 真實草稿，2026-11-04）──────

def test_plain_recomputed_mode_col_pass_and_fail(tmp_path: pathlib.Path):
    """mode_col：欄位值計數最大（dabstep-13 hour_of_day 語義）；交付物為 plain value（非 @kv）。
    重算值不進證據（紅線：不向修復模型提供隱藏答案）。"""
    task_dir = tmp_path / "task"
    _write(
        task_dir / "payments.csv",
        "hour_of_day\n14\n14\n14\n13\n13\n16\n",   # mode = 14
    )
    params = {
        "data_file": "payments.csv",
        "recompute": {"type": "mode_col", "col": "hour_of_day",
                      "note": "值計數最大者；平手→數值最小（可解析為數時），否則字典序最小（TDD 前凍結）"},
    }
    req_set = _req_set("plain_recomputed", params, "answer.txt")
    good = tmp_path / "good"
    _write(good / "answer.txt", "14\n")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, good)}
    assert res["req_main"].status == "PASS"

    bad = tmp_path / "bad"
    _write(bad / "answer.txt", "13\n")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, bad)}
    r = res["req_main"]
    assert r.status == "FAIL"
    assert r.evidence.get("expected_in_evidence") is False   # 重算值不進證據


def test_plain_recomputed_mode_col_tie_and_unknown(tmp_path: pathlib.Path):
    """mode_col 平手→數值最小（2 勝 10，非字典序 '10'）；無非空值→UNKNOWN（不自評）。"""
    task_dir = tmp_path / "task"
    _write(task_dir / "t.csv", "v\n2\n10\n2\n10\n")   # 2:2 與 10:2 平手 → 數值最小 2
    params = {"data_file": "t.csv", "recompute": {"type": "mode_col", "col": "v"}}
    req_set = _req_set("plain_recomputed", params, "answer.txt")
    d = tmp_path / "d"
    _write(d / "answer.txt", "2\n")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, d)}
    assert res["req_main"].status == "PASS"

    lexicographic_trap = tmp_path / "lex"
    _write(lexicographic_trap / "answer.txt", "10\n")   # 字典序 '10' 最小≠規則
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, lexicographic_trap)}
    assert res["req_main"].status == "FAIL"

    task_dir2 = tmp_path / "task2"
    _write(task_dir2 / "e.csv", "v\n\n\n")             # 無非空值 → UNKNOWN
    req_set2 = _req_set("plain_recomputed", dict(params), "answer.txt")
    d2 = tmp_path / "d2"
    _write(d2 / "answer.txt", "1\n")
    res2 = {r.claim_id: r for r in run_requirement_checks(task_dir2, req_set2, d2)}
    assert res2["req_main"].status == "UNKNOWN"


# ── plain_recomputed＋cond_rate（G2 小批：e014/dabstep-23，2026-11-04）────────

def _cond_rate_params() -> dict:
    """fraud_rate_2023_inperson（TDD 前凍結語義）：
    分母＝year==2023 ∧ shopper_interaction==POS（POS=in-person，payments-readme.md 明言）；
    分子＝分母中 has_fraudulent_dispute==True；rate＝分子/分母；分母 0→UNKNOWN；比率唯一無平手。"""
    return {
        "data_file": "payments.csv",
        "recompute": {
            "type": "cond_rate",
            "where": [{"col": "year", "op": "eq", "value": "2023"},
                      {"col": "shopper_interaction", "op": "eq", "value": "POS"}],
            "num_where": [{"col": "has_fraudulent_dispute", "op": "eq", "value": "True"}],
            "note": "fraud_rate_2023_inperson；POS=in-person（payments-readme.md）；語義 TDD 前凍結",
        },
    }


def test_plain_recomputed_cond_rate_pass_and_fail(tmp_path: pathlib.Path):
    """cond_rate：只數「2023∧POS」且 dispute=True（Ecommerce 與 2022 皆不入分母）。
    重算值不進證據（紅線：不向修復模型提供隱藏答案）。"""
    task_dir = tmp_path / "task"
    _write(
        task_dir / "payments.csv",
        "year,shopper_interaction,has_fraudulent_dispute\n"
        "2023,POS,True\n2023,POS,True\n2023,POS,False\n2023,POS,False\n"
        "2023,Ecommerce,True\n2022,POS,True\n",   # 正確 rate=2/4=0.5；全表=4/6、漏 year=3/5，皆不同
    )
    req_set = _req_set("plain_recomputed", _cond_rate_params(), "answer.txt")
    good = tmp_path / "good"
    _write(good / "answer.txt", "0.5\n")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, good)}
    assert res["req_main"].status == "PASS"

    bad = tmp_path / "bad"
    _write(bad / "answer.txt", "0.4\n")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, bad)}
    r = res["req_main"]
    assert r.status == "FAIL"
    assert r.evidence.get("expected_in_evidence") is False   # 重算值不進證據


def test_plain_recomputed_cond_rate_zero_and_unknown(tmp_path: pathlib.Path):
    """cond_rate：分母內 dispute 全 False→rate 0.0（答案「0」PASS，真實 dabstep-23 即此形）；
    分母 0 行→UNKNOWN（不自評）；缺 num_where→UNKNOWN。"""
    task_dir = tmp_path / "task"
    _write(
        task_dir / "payments.csv",
        "year,shopper_interaction,has_fraudulent_dispute\n"
        "2023,POS,False\n2023,POS,False\n2023,Ecommerce,True\n",
    )
    req_set = _req_set("plain_recomputed", _cond_rate_params(), "answer.txt")
    zero = tmp_path / "zero"
    _write(zero / "answer.txt", "0\n")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, zero)}
    assert res["req_main"].status == "PASS"

    wrong = tmp_path / "wrong"
    _write(wrong / "answer.txt", "0.00152745\n")   # dabstep-23 真實草稿值：非 0→FAIL
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, wrong)}
    r = res["req_main"]
    assert r.status == "FAIL"
    assert r.evidence.get("expected_in_evidence") is False

    _write(task_dir / "e.csv", "year,shopper_interaction,has_fraudulent_dispute\n2022,POS,True\n")
    params = {"data_file": "e.csv", "recompute": dict(_cond_rate_params()["recompute"])}
    req_set2 = _req_set("plain_recomputed", params, "answer.txt")
    d2 = tmp_path / "d2"
    _write(d2 / "answer.txt", "0\n")
    res2 = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set2, d2)}
    assert res2["req_main"].status == "UNKNOWN"

    no_num = {"data_file": "payments.csv",
              "recompute": {"type": "cond_rate",
                            "where": [{"col": "year", "op": "eq", "value": "2023"}]}}
    req_set3 = _req_set("plain_recomputed", no_num, "answer.txt")
    res3 = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set3, zero)}
    assert res3["req_main"].status == "UNKNOWN"


# ── plain_recomputed＋fee_ids_lookup（G2 小批：e014/dabstep-1753，2026-11-04）──

def _write_fee_fixture(task_dir: pathlib.Path) -> None:
    """M1（Belles 同形）：MCC 5942、account R、delay '1' 天（→'<3'）；
    2023-03（doy 60..90，平年）總量 250000→'100k-1m'、欺詐 30000→12%→'>8.3%'。
    2 月（doy 30）、2022、其他商戶（M2/M3）行皆不入重算。
    M2：MCC 9999／F／manual；M3：MCC 7777／F（無 fee 列 MCC）→適用集為空。"""
    _write(
        task_dir / "payments.csv",
        "merchant,year,day_of_year,eur_amount,has_fraudulent_dispute\n"
        "M1,2023,60,100000,False\n"
        "M1,2023,90,150000,False\n"
        "M1,2023,70,30000,True\n"
        "M1,2023,30,999999,True\n"
        "M1,2022,60,999999,True\n"
        "M2,2023,60,500000,True\n"
        "M3,2023,60,1000,False\n",
    )
    _write(task_dir / "merchant_data.json", json.dumps([
        {"merchant": "M1", "merchant_category_code": 5942, "account_type": "R",
         "capture_delay": "1", "acquirer": ["x"]},
        {"merchant": "M2", "merchant_category_code": 9999, "account_type": "F",
         "capture_delay": "manual", "acquirer": ["y"]},
        {"merchant": "M3", "merchant_category_code": 7777, "account_type": "F",
         "capture_delay": "2", "acquirer": ["z"]},
    ]))
    _write(task_dir / "fees.json", json.dumps([
        # 命中 M1：MCC∋5942 ∧ acct∋R ∧ cd '<3' ∧ vol 100k-1m ∧ fraud >8.3%
        {"ID": 7, "merchant_category_code": [5942, 5943], "account_type": ["R"],
         "capture_delay": "<3", "monthly_volume": "100k-1m", "monthly_fraud_level": ">8.3%",
         "is_credit": None, "aci": []},
        # 全欄無限制（null/空列表＝applies to all，manual.md 明言）
        {"ID": 8, "merchant_category_code": [], "account_type": ["R"],
         "capture_delay": None, "monthly_volume": None, "monthly_fraud_level": None,
         "is_credit": None, "aci": []},
        # MCC 不含 5942 → 排除
        {"ID": 9, "merchant_category_code": [9999], "account_type": [],
         "capture_delay": None, "monthly_volume": None, "monthly_fraud_level": None,
         "is_credit": None, "aci": []},
        # acct 不含 R → 排除
        {"ID": 10, "merchant_category_code": [5942], "account_type": ["F"],
         "capture_delay": None, "monthly_volume": None, "monthly_fraud_level": None,
         "is_credit": None, "aci": []},
        # capture_delay 類別不符（1 天只落 '<3'；'immediate'⟺0、'3-5'、'>5'、'manual' 皆排除）
        {"ID": 11, "merchant_category_code": [5942], "account_type": [],
         "capture_delay": "3-5", "monthly_volume": None, "monthly_fraud_level": None,
         "is_credit": None, "aci": []},
        {"ID": 12, "merchant_category_code": [5942], "account_type": [],
         "capture_delay": "immediate", "monthly_volume": None, "monthly_fraud_level": None,
         "is_credit": None, "aci": []},
        {"ID": 13, "merchant_category_code": [5942], "account_type": [],
         "capture_delay": ">5", "monthly_volume": None, "monthly_fraud_level": None,
         "is_credit": None, "aci": []},
        # volume 檔位不符（250000 落 '100k-1m'，非 '>5m'）→ 排除
        {"ID": 14, "merchant_category_code": [5942], "account_type": [],
         "capture_delay": None, "monthly_volume": ">5m", "monthly_fraud_level": None,
         "is_credit": None, "aci": []},
        # fraud 檔位不符（12% 落 '>8.3%'，非 '7.7%-8.3%'）→ 排除
        {"ID": 15, "merchant_category_code": [5942], "account_type": [],
         "capture_delay": None, "monthly_volume": None, "monthly_fraud_level": "7.7%-8.3%",
         "is_credit": None, "aci": []},
        # is_credit/aci 為交易層條件（商戶同時有 credit/debit、任一 ACI）→ 不限制商戶層適用（凍結解讀）
        {"ID": 16, "merchant_category_code": [5942], "account_type": [],
         "capture_delay": None, "monthly_volume": None, "monthly_fraud_level": None,
         "is_credit": True, "aci": ["A"]},
    ]))


def _fee_ids_params(merchant: str = "M1", year: int = 2023, month: int = 3) -> dict:
    return {
        "data_file": "payments.csv",
        "recompute": {
            "type": "fee_ids_lookup",
            "fees_file": "fees.json",
            "merchants_file": "merchant_data.json",
            "merchant": merchant, "year": year, "month": month,
            "note": "語義 TDD 前凍結（manual.md）：null/空列表＝無限制；自然月重算 volume/fraud 檔位；"
                    "is_credit/aci 交易層條件不限制商戶層適用",
        },
    }


def test_plain_recomputed_fee_ids_lookup_pass_and_fail(tmp_path: pathlib.Path):
    """fee_ids_lookup：M1 適用集＝{7,8,16}（順序無關比較；2/2022/M2 行不入重算）。
    真實 dabstep-1753 草稿值 'None'→FAIL；漏一筆（7,8）→FAIL；期望 ID 不進證據（紅線）。"""
    task_dir = tmp_path / "task"
    _write_fee_fixture(task_dir)
    req_set = _req_set("plain_recomputed", _fee_ids_params(), "answer.txt")

    good = tmp_path / "good"
    _write(good / "answer.txt", "8,7,16\n")   # 與期望同集、不同序 → PASS
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, good)}
    assert res["req_main"].status == "PASS"

    bad = tmp_path / "bad"
    _write(bad / "answer.txt", "None\n")      # dabstep-1753 真實草稿值
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, bad)}
    r = res["req_main"]
    assert r.status == "FAIL"
    assert r.evidence.get("expected_in_evidence") is False   # 期望 ID 不進證據
    blob = json.dumps(r.evidence, ensure_ascii=False) + (r.detail or "")
    assert "16" not in blob and "7,8" not in blob             # 期望集合不出現在 detail/evidence

    partial = tmp_path / "partial"
    _write(partial / "answer.txt", "7,8\n")   # 漏 16 → FAIL
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, partial)}
    assert res["req_main"].status == "FAIL"


def test_plain_recomputed_fee_ids_lookup_empty_and_unknown(tmp_path: pathlib.Path):
    """適用集為空→答案＝空字串（題目自帶口徑 empty list→empty string），空檔 PASS、'None' FAIL。
    商戶不存在／該自然月無行→UNKNOWN（看不到＝UNKNOWN，不自評）。"""
    task_dir = tmp_path / "task"
    _write_fee_fixture(task_dir)

    req_set = _req_set("plain_recomputed", _fee_ids_params(merchant="M3"), "answer.txt")
    d = tmp_path / "empty"
    _write(d / "answer.txt", "")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, d)}
    assert res["req_main"].status == "PASS"

    none = tmp_path / "none"
    _write(none / "answer.txt", "None\n")
    res = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set, none)}
    assert res["req_main"].status == "FAIL"

    req_set2 = _req_set("plain_recomputed", _fee_ids_params(merchant="NOPE"), "answer.txt")
    d2 = tmp_path / "d2"
    _write(d2 / "answer.txt", "8\n")
    res2 = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set2, d2)}
    assert res2["req_main"].status == "UNKNOWN"

    req_set3 = _req_set("plain_recomputed", _fee_ids_params(year=2024), "answer.txt")
    d3 = tmp_path / "d3"
    _write(d3 / "answer.txt", "8\n")
    res3 = {r.claim_id: r for r in run_requirement_checks(task_dir, req_set3, d3)}
    assert res3["req_main"].status == "UNKNOWN"
