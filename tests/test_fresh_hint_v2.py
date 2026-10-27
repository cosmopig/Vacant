# -*- coding: utf-8 -*-
"""round 96 — fresh_hint v2：診斷內容必須活著到模型眼前。

v5 的投遞稽核（`ops/realrun/hint_diagnostic_loss.py`）顯示：舊版
`ln[:120]` 頭截斷在 85/86 份真實 hint 上把診斷內容（失敗測試名、
AssertionError 的實際值）截掉了——模型收到的是「有東西失敗了，避開它」，
而不是「什麼失敗了」。v5 的 UNRESOLVED 因此**可能**是投遞缺陷的偽影。

本檔釘死 v2 的契約（與 v5 同一個 380B 預算，只改**內容選擇**）：

  1. 真實失敗形狀（pg_connect 的 assert 與 import 兩種）裡，失敗測試名、
     錯誤類型+訊息必須出現在 hint 內；
  2. 預算：≤380 bytes（v5 prereg 的預算不變）；
  3. 純函數：只吃 `failures`（可見驗收的渲染結果，呼叫端契約）；
  4. 空輸入回退到通用句；KS-1 把關照舊（KS1Violation）；
  5. round 95 的寬鬆測試（`test_fresh_hint_renders_clean_memory`）保持綠。
"""
from __future__ import annotations

import re

import pytest

from vacant_network.memory import KS1Violation
from vacant_network.vrun import retry as R


# ── 真實形狀：v5 run 資料裡的兩類 failures 原文（逐字取自 run JSON） ──

# C_fresh_hint3/pg_connect/run/run_RUN-ON.json，attempt 0 的 failures：
_PG_CONNECT_ASSERT = (
    "test_visible.py::check_visible_suite — assert: 4/10 visible tests failed. first: "
    "Traceback (most recent call last): |   "
    "File \"/home/user1/dev/ops/realrun/runs_v5_r1/C_fresh_hint3/pg_connect/ws/test_visible.py\","
    " line 53, in test_illegal_diagonal_does_not_make_a_winner |"
    "     self.assertEqual(winner, \"\") |"
    " AssertionError: 'X' != '' | - X | +"
    " [test_visible.py:127: raise AssertionError(f\"{bad}/{n} visible tests failed. first: {detail}\")]"
)

# 同檔 attempt 1 的 failures（import 失敗）：
_PG_CONNECT_IMPORT = (
    "test_visible.py::<module> — import: SyntaxError: invalid syntax (connect.py, line 1)"
    " [test_visible.py:7: from connect import (]"
)


def test_real_assert_shape_keeps_test_name_and_values():
    hint = R.render_fresh_hint(_PG_CONNECT_ASSERT, attempt=1, max_attempts=3)
    # 診斷三件事都要在：失敗測試名、assertion 的實際值、N/M 摘要
    assert "test_illegal_diagonal_does_not_make_a_winner" in hint
    assert "AssertionError" in hint and "'X' != ''" in hint
    assert "4/10" in hint


def test_real_import_shape_keeps_error_message_whole():
    hint = R.render_fresh_hint(_PG_CONNECT_IMPORT, attempt=2, max_attempts=3)
    # v5 把它截在「[te」；v2 必須帶出完整的錯誤類型+訊息
    assert "SyntaxError: invalid syntax (connect.py, line 1)" in hint
    assert hint.count("[te\n") == 0 and not hint.rstrip().endswith("[te")


def test_budget_and_template_unchanged():
    for failures in (_PG_CONNECT_ASSERT, _PG_CONNECT_IMPORT):
        hint = R.render_fresh_hint(failures, attempt=1, max_attempts=3)
        assert len(hint.encode("utf-8")) <= 380
        # 模板三件（v5 既有，agent 與評測都依賴）
        assert "clean origin" in hint
        assert "Previous attempt failed acceptance check:" in hint
        assert "Avoid this failure in your clean implementation." in hint


def test_multiline_render_failures_shape():
    # `acceptance.render_failures` 的形狀：case 行 + 縮排 output 行
    failures = (
        "test_visible.py::test_a — assert: boom [test_visible.py:12: assert a() == 1]\n"
        "    assert a() == 1\n    AssertionError: 2 != 1\n"
        "test_visible.py::test_b — assert: boom [test_visible.py:20: assert b() == 2]\n"
        "    AssertionError: 3 != 2\n"
    )
    hint = R.render_fresh_hint(failures, attempt=1, max_attempts=3)
    # 兩題的診斷都要在（預算 225B 裝得下）；至少各有一個辨識符號
    assert ("test_a" in hint) and ("test_b" in hint)
    assert "2 != 1" in hint and "3 != 2" in hint
    assert len(hint.encode("utf-8")) <= 380


def test_empty_failures_falls_back_to_generic():
    hint = R.render_fresh_hint("", attempt=1, max_attempts=3)
    assert "clean origin" in hint
    assert "did not pass visible test assertions" in hint
    assert len(hint.encode("utf-8")) <= 380


def test_garbage_no_keyword_does_not_crash_and_stays_in_budget():
    garbage = "x" * 2000 + "\n" + "y z w v u" * 300
    hint = R.render_fresh_hint(garbage, attempt=1, max_attempts=3)
    assert 0 < len(hint.encode("utf-8")) <= 380
    assert "clean origin" in hint


def test_multibyte_content_respects_byte_budget():
    # 中文明錯誤訊息：字元數截斷會超 byte 預算，v2 必須按 bytes 收
    failures = "test_t::case — assert: 失敗了 " + "測" * 500
    hint = R.render_fresh_hint(failures, attempt=1, max_attempts=3)
    assert len(hint.encode("utf-8")) <= 380
    assert "失敗了" in hint  # 診斷開頭保得住


def test_ks1_violation_still_raised():
    with pytest.raises(KS1Violation):
        R.render_fresh_hint("you are responsible for this", attempt=1, max_attempts=3)


def test_pure_function_of_failures_input():
    a = R.render_fresh_hint(_PG_CONNECT_ASSERT, attempt=1, max_attempts=3)
    b = R.render_fresh_hint(_PG_CONNECT_ASSERT, attempt=1, max_attempts=3)
    assert a == b
    # attempt 只進模板，不進診斷內容
    c = R.render_fresh_hint(_PG_CONNECT_ASSERT, attempt=2, max_attempts=3)
    assert "Attempt 2 failed" in c and "test_illegal_diagonal" in c
