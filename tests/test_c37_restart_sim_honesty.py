"""c37 重抽重放器（`ops/eval/c37_offline_restart_sim.py`）必須**自己在輸出上標註**：
哪一欄是 reachable（可見測試＝評分器，agent 自己拿得到這個訊號）、哪一欄只是
oracle 上界（用了隱藏評分器，不可引用為成效）。

鐵律（ASSIGNMENT 2026-10-24）：
- 「+15.4 pp」（ALL test-restart 77.7%）不得引用為成效——它混用了隱藏評分器。
- 任何成效數字：寫清楚用的是哪一欄、有沒有用到評分器、n 是多少。
- 未驗證「可見測試＝評分器」的 suite，fail-closed 當上界。

本測試用 fixture 資料（不碰 520KB 的 c37_final.json），零機時。
"""
from __future__ import annotations

import json

from ops.eval.c37_offline_restart_sim import (
    VISIBLE_TESTS_ARE_GRADER,
    render,
    simulate,
)


def _fixture() -> list[dict]:
    """兩個 suite、各一個（batch, task）群組、各 ≥2 個獨立 run。

    polyglot_py（可見測試＝評分器）：r1 掛、r2 掛（有 flag）、r3 過。
    dabstep（隱藏評分）：r1 掛、r2 過。
    """
    base = {
        "cell": "", "task_dir": "", "pass": False,
        "findings_final": [], "num_reviews": 1,
    }
    rows = []
    for i, (p, f) in enumerate([
        (False, []), (False, ["hint"]), (True, []),
    ], start=1):
        rows.append({**base,
                     "cell": f"b1-polyglot_py-t1-r{i}",
                     "task_dir": "/srv/eval/staged/polyglot_py/t1",
                     "pass": p, "findings_final": f})
    for i, (p, f) in enumerate([(False, []), (True, [])], start=1):
        rows.append({**base,
                     "cell": f"b2-dabstep-t9-r{i}",
                     "task_dir": "/srv/eval/staged/dabstep/t9",
                     "pass": p, "findings_final": f})
    return rows


def test_table_numbers_unchanged_and_per_suite_signal_labeled():
    res = simulate(_fixture(), cap=3)
    pg = res["rows"]["polyglot_py"]
    ds = res["rows"]["dabstep"]
    allr = res["rows"]["ALL"]

    # 數字語意與舊版一致（fixture 上手工算過的值）
    assert pg["pass1_pct"] == 0.0 and pg["flag_pct"] == 0.0
    assert pg["test_pct"] == 100.0 and pg["test_runs"] == 3.0
    assert pg["oracle_pct"] == 100.0 and pg["units"] == 1 and pg["cells"] == 3
    assert ds["test_pct"] == 100.0 and ds["test_runs"] == 2.0
    assert allr["units"] == 2 and allr["test_pct"] == 100.0 and allr["flag_pct"] == 0.0

    # 每行的 test-restart 欄訊號標註
    assert pg["test_signal"] == "visible==grader"
    assert ds["test_signal"] == "hidden-grader(UB)"
    assert allr["test_signal"] == "mixed(UB)"


def test_citable_section_names_the_reachable_columns_with_n_and_cap():
    res = simulate(_fixture(), cap=3)
    cit = res["citable"]

    # flag 欄：所有 suite（含 ALL）都可引用（ Vacant 自己的訊號，不用評分器）
    flags = {c["suite"]: c for c in cit if c["signal"] == "vacant-flag"}
    assert set(flags) == {"polyglot_py", "dabstep", "ALL"}
    for c in flags.values():
        assert c["uses_scorer"] is False
        assert c["cap"] == 3 and c["n_units"] >= 1 and c["n_cells"] >= c["n_units"]
    assert flags["ALL"]["pass1_pct"] == 0.0 and flags["ALL"]["flag_pct"] == 0.0

    # visible-test 欄：只有「可見測試＝評分器」的 suite 進可引用區
    vis = {c["suite"]: c for c in cit if c["signal"] == "visible-test"}
    assert set(vis) == {"polyglot_py"}
    assert vis["polyglot_py"]["pass1_pct"] == 0.0
    assert vis["polyglot_py"]["test_pct"] == 100.0
    assert vis["polyglot_py"]["uses_scorer"] is False


def test_upper_bound_section_names_every_scorer_column():
    res = simulate(_fixture(), cap=3)
    ub = {u["suite"]: u for u in res["upper_bounds"]}
    assert set(ub) == {"dabstep", "ALL"}
    for u in ub.values():
        assert u["column"] == "test-restart"
        assert "評分器" in u["reason"]  # 理由寫得出來，不是裸數字
    assert "polyglot_py" not in ub


def test_render_marks_the_unquotable_columns_in_text():
    text = render(simulate(_fixture(), cap=3))
    # 表列上逐行標註
    assert "visible==grader" in text
    assert "hidden-grader(UB)" in text
    assert "mixed(UB)" in text
    # 兩個分區都在
    assert "可引用" in text
    assert "不可引用" in text
    # 不可引用區點名 ALL 的 test-restart（+15.4pp 那一類數字的家）
    ub_section = text.split("不可引用", 1)[1]
    assert "ALL" in ub_section and "test-restart" in ub_section
    # 可引用區帶 n 與 cap
    cit_section = text.split("可引用", 1)[1].split("不可引用", 1)[0]
    assert "cap=3" in cit_section and "cells" in cit_section


def test_fail_closed_unknown_suite_is_not_citable():
    """一個沒驗證過「可見測試＝評分器」的新 suite：test-restart 一律當上界。"""
    rows = _fixture()
    rows += [
        {"cell": "b3-newbank-x1-r1", "task_dir": "/srv/eval/staged/newbank/x1",
         "pass": False, "findings_final": []},
        {"cell": "b3-newbank-x1-r2", "task_dir": "/srv/eval/staged/newbank/x1",
         "pass": True, "findings_final": []},
    ]
    assert "newbank" not in VISIBLE_TESTS_ARE_GRADER
    res = simulate(rows, cap=3)
    assert res["rows"]["newbank"]["test_signal"] == "hidden-grader(UB)"
    assert {c["suite"] for c in res["citable"] if c["signal"] == "visible-test"} == {"polyglot_py"}
    assert "newbank" in {u["suite"] for u in res["upper_bounds"]}


def test_empty_visible_set_removes_all_visible_test_citations():
    """把驗證集合清空＝什麼都未驗證：visible-test 可引用區必須消失（fail-closed）。"""
    res = simulate(_fixture(), cap=3, visible_are_grader=frozenset())
    assert res["rows"]["polyglot_py"]["test_signal"] == "hidden-grader(UB)"
    assert [c for c in res["citable"] if c["signal"] == "visible-test"] == []
    assert "polyglot_py" in {u["suite"] for u in res["upper_bounds"]}


def test_json_roundtrip_is_stable():
    """同一份輸入 → 同一份結構化結果（dict 相等），可存檔再比對。"""
    a = simulate(_fixture(), cap=3)
    b = simulate(json.loads(json.dumps(_fixture())), cap=3)
    assert a == b
