"""L2 方言偵測（`classify_dialect`）與 unittest 宣告清單（`declared_unittest_cases`）
的純函數測試。

對應設計：`decisions/DECISION_20261025_VISIBLE_SUITE_DIALECTS.md` §4.2／§4.3。
這是 unittest 方言 adapter 的**地基**：分類與宣告都發生在任何候選碼跑起來之前，
所以這裡只用純 AST 函數驗，不進沙箱、零模型呼叫。

負向控制（G1 的「量具先自證」精神，AGENTS.md H-0）：
  - 對的形狀要判對（check→check、unittest→unittest、mixed→mixed、none→none）。
  - 容易誤判的工具檔（`test_utils.py`）、`import unittest` 但沒有 TestCase 子類、
    巢狀 TestCase、本地 `class TestCase`（非 unittest）——都要落到**正確**的那一格，
    尤其**不能**把工具檔判成 `unittest`（那會把它當真測試跑，讓分數說謊）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vacant_network.vrun import acceptance  # noqa: E402

C = acceptance.DIALECT_CHECK
U = acceptance.DIALECT_UNTEST
M = acceptance.DIALECT_MIXED
N = acceptance.DIALECT_NONE


def cls(src: str) -> str:
    return acceptance.classify_dialect(src.encode("utf-8"))


# ── check 方言（現行 driver 的形狀）─────────────────────────────────────
def test_check_underscore_functions():
    assert cls("def check_a():\n    pass\n") == C


def test_check_main_only():
    assert cls("def main():\n    pass\n") == C


def test_check_async_function():
    assert cls("async def check_a():\n    pass\n") == C


def test_check_takes_precedence_and_is_not_unittest():
    # 有 check_* 但沒有 unittest ⇒ 純 check，不能因為「可能混」就升級成 mixed。
    assert cls("def check_a():\n    pass\ndef helper():\n    pass\n") == C


# ── unittest 方言 ──────────────────────────────────────────────────────
def test_unittest_import_and_class():
    assert cls(
        "import unittest\n"
        "class T(unittest.TestCase):\n"
        "    def test_a(self):\n        pass\n"
    ) == U


def test_unittest_from_import_and_class():
    assert cls(
        "from unittest import TestCase\n"
        "class T(TestCase):\n"
        "    def test_a(self):\n        pass\n"
    ) == U


def test_unittest_aliased_import():
    assert cls(
        "import unittest as ut\n"
        "class T(ut.TestCase):\n"
        "    def test_a(self):\n        pass\n"
    ) == U


# ── mixed：兩套語義都在＝顯式失敗的候選，不猜 ─────────────────────────
def test_mixed_check_and_unittest():
    assert cls(
        "import unittest\n"
        "class T(unittest.TestCase):\n"
        "    def test_a(self):\n        pass\n"
        "def check_b():\n    pass\n"
    ) == M


def test_mixed_main_and_unittest():
    assert cls(
        "import unittest\n"
        "class T(unittest.TestCase):\n"
        "    def test_a(self):\n        pass\n"
        "def main():\n    pass\n"
    ) == M


# ── none：工具檔／無訊號／認不出 ───────────────────────────────────────
def test_none_helper_file():
    # 題庫的 test_utils.py 形狀：只有工具函式，絕不能被判成 unittest 當真測試跑。
    assert cls("def make_fixture():\n    return 1\n") == N


def test_none_unittest_import_but_no_case_class():
    # import 了 unittest（例如只是型別註解），但沒有 TestCase 子類 ⇒ 不是測試檔。
    assert cls(
        "import unittest\n"
        "def helper() -> None:\n    pass\n"
    ) == N


def test_none_local_class_named_testcase_without_import():
    # 本地自己定義了一個叫 TestCase 的類，但沒有 import unittest ⇒ 不是 unittest 方言。
    assert cls(
        "class TestCase:\n    pass\n"
        "class T(TestCase):\n"
        "    def test_a(self):\n        pass\n"
    ) == N


def test_none_nested_testcase_not_toplevel():
    # 設計「只認頂層」：巢狀 TestCase 不在宣告/分類範圍內 ⇒ none。
    assert cls(
        "import unittest\n"
        "def build():\n"
        "    class T(unittest.TestCase):\n"
        "        def test_a(self):\n            pass\n"
        "    return T\n"
    ) == N


def test_none_empty_file():
    assert cls("") == N


def test_none_syntax_error_is_not_crash():
    assert cls("def check_a(:\n    pass\n") == N


def test_none_comment_only():
    assert cls("# just a comment\n") == N


# ── declared_unittest_cases：宣告清單＝對帳分母 ────────────────────────
def dec(src: str) -> list[str]:
    return acceptance.declared_unittest_cases(src.encode("utf-8"))


def test_declared_multiple_methods_in_definition_order():
    assert dec(
        "import unittest\n"
        "class T(unittest.TestCase):\n"
        "    def test_b(self):\n        pass\n"
        "    def test_a(self):\n        pass\n"
    ) == ["T.test_b", "T.test_a"]


def test_declared_multiple_classes():
    assert dec(
        "import unittest\n"
        "class A(unittest.TestCase):\n"
        "    def test_a(self):\n        pass\n"
        "class B(unittest.TestCase):\n"
        "    def test_b(self):\n        pass\n"
    ) == ["A.test_a", "B.test_b"]


def test_declared_excludes_non_test_methods():
    assert dec(
        "import unittest\n"
        "class T(unittest.TestCase):\n"
        "    def setUp(self):\n        pass\n"
        "    def test_a(self):\n        pass\n"
        "    def tearDown(self):\n        pass\n"
        "    def helper(self):\n        pass\n"
    ) == ["T.test_a"]


def test_declared_excludes_non_case_classes():
    assert dec(
        "import unittest\n"
        "class Data:\n"
        "    def test_notacase(self):\n        pass\n"
        "class T(unittest.TestCase):\n"
        "    def test_a(self):\n        pass\n"
    ) == ["T.test_a"]


def test_declared_excludes_nested_classes():
    # 巢狀 TestCase 不在宣告範圍（設計「只認頂層」）。
    assert dec(
        "import unittest\n"
        "def build():\n"
        "    class T(unittest.TestCase):\n"
        "        def test_a(self):\n            pass\n"
        "    return T\n"
        "class Real(unittest.TestCase):\n"
        "    def test_r(self):\n        pass\n"
    ) == ["Real.test_r"]


def test_declared_async_test_method_counts():
    # async test 方法會被執行（unittest 支援），宣告清單要數到它。
    assert dec(
        "import unittest\n"
        "class T(unittest.TestCase):\n"
        "    async def test_a(self):\n        pass\n"
    ) == ["T.test_a"]


def test_declared_exact_name_test_counts():
    # unittest 的 TestLoader 認 `test` 前綴；`test` 本身也算。
    assert dec(
        "import unittest\n"
        "class T(unittest.TestCase):\n"
        "    def test(self):\n        pass\n"
    ) == ["T.test"]


def test_declared_dedupes_repeated_names():
    assert dec(
        "import unittest\n"
        "class T(unittest.TestCase):\n"
        "    def test_a(self):\n        pass\n"
        "    def test_a(self):\n        pass\n"
    ) == ["T.test_a"]


def test_declared_zero_cases_is_empty_list():
    # 有 TestCase 但零 test 方法 ⇒ 空清單。driver 端會把它對帳成「零案例＝失敗」，
    # 而不是「空＝過」（I-4）。這裡只驗宣告清單本身是空的。
    assert dec(
        "import unittest\n"
        "class T(unittest.TestCase):\n"
        "    def setUp(self):\n        pass\n"
    ) == []


def test_declared_non_unittest_file_is_empty():
    assert dec("def check_a():\n    pass\n") == []


def test_declared_syntax_error_is_empty_not_crash():
    assert dec("import unittest\nclass T(unittest.TestCase(:\n    pass\n") == []


# ── round-143 GPT 審查 P0-1「inherited tests」：宣告與 TestLoader 同形 ──
def test_declared_inherits_test_methods_from_in_module_base():
    # loader 從 dir(Sub) 收集：Sub 也會執行 Base.test_base（case id Sub.test_base）。
    # 宣告清單必須數到它，否則每個繼承 case 都是「未宣告的 id」⇒ protocol 失敗。
    assert dec(
        "import unittest\n"
        "class Base(unittest.TestCase):\n"
        "    def test_base(self):\n        pass\n"
        "class Sub(Base):\n"
        "    def test_sub(self):\n        pass\n"
    ) == ["Base.test_base", "Sub.test_sub", "Sub.test_base"]


def test_declared_inherited_override_dedupes_to_one_case():
    # Sub 覆寫 test_a：dir(Sub) 只有一個 test_a ⇒ 只算 Sub.test_a 一筆。
    assert dec(
        "import unittest\n"
        "class Base(unittest.TestCase):\n"
        "    def test_a(self):\n        pass\n"
        "class Sub(Base):\n"
        "    def test_a(self):\n        pass\n"
    ) == ["Base.test_a", "Sub.test_a"]


def test_declared_three_level_chain_inherits_all():
    assert dec(
        "import unittest\n"
        "class A(unittest.TestCase):\n"
        "    def test_a(self):\n        pass\n"
        "class B(A):\n"
        "    def test_b(self):\n        pass\n"
        "class C(B):\n"
        "    def test_c(self):\n        pass\n"
    ) == ["A.test_a", "B.test_b", "B.test_a", "C.test_c", "C.test_b", "C.test_a"]


def test_declared_non_testcase_base_contributes_nothing():
    # 非 TestCase 的頂層類別（Data）不是 case 類別；它的 test* 也不進任何
    # 清單（沒有 TestCase 子類繼承它）。
    assert dec(
        "import unittest\n"
        "class Data:\n"
        "    def test_data(self):\n        pass\n"
        "class T(unittest.TestCase):\n"
        "    def test_a(self):\n        pass\n"
    ) == ["T.test_a"]


def test_declared_base_with_only_setup_contributes_nothing():
    # base 只有 setUp（沒有 test*）⇒ 它自己零案例；Sub 只算自己的。
    assert dec(
        "import unittest\n"
        "class Base(unittest.TestCase):\n"
        "    def setUp(self):\n        pass\n"
        "class Sub(Base):\n"
        "    def test_sub(self):\n        pass\n"
    ) == ["Sub.test_sub"]
