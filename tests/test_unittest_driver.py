"""unittest 方言 driver（`UNTEST_DRIVER_SRC`）的自檢——設計 §五 的 G1/G2/G3。

`DECISION_20261025_VISIBLE_SUITE_DIALECTS.md` §五把 adapter 落地綁定在三組
自檢上。這支走**真的** `run_suite`（跟 `test_acceptance_completeness.py`
同路徑，不是 mock）：

- **G1 自檢**：對的實現要過；已知壞的 stub 要拒；零案例的 unittest 檔＝失敗；
  `mixed` 檔＝顯式失敗且**兩半都不跑**；工具檔（`none`）＝顯式失敗不是跳過；
  加上兩個實測確認的洞：`async def test_*` 在 unittest 裡**方法體一行不跑卻
  回報 pass**、`skipTest` 什麼都沒驗——兩者都必須顯式紅，不可靜默綠。
- **G2 跨方言一致**：同一組題目，`check_*` 寫法與 `unittest` 寫法的判準要
  一致——同一份對的實現兩邊都過，同一份錯的實現兩邊都紅（失敗 kind 是
  實實在在的 assert/exception，不是 protocol 雜訊）。
- **G3 check 方言迴歸**：check 方言的 `run_suite` 輸出（含結果雜湊
  `result_sha256`）與 adapter 落地前**逐位相同**。這兩個雜湊值是在改動
  `run_suite` 之前實測凍結的；driver/對帳/結果形狀任何一處漂移都會翻面。
"""
from __future__ import annotations

import pathlib
import tempfile

import pytest

from vacant_network.vrun import acceptance
from vacant_network.vrun import sandbox as sb


def _run(testfile: str, impl: str, suite_name: str = "visible") -> dict:
    """把一份測試檔＋一份 `solution.py` 丟進真的 `run_suite`，回結果。"""
    with tempfile.TemporaryDirectory() as td:
        t = pathlib.Path(td)
        ws = t / "ws"
        ws.mkdir()
        (ws / "solution.py").write_text(impl, encoding="utf-8")
        sdir = t / "suite"
        sdir.mkdir()
        (sdir / "test_main.py").write_text(testfile, encoding="utf-8")
        backend, _meta = sb.make_sandbox("auto", workdir=str(t / "vroot"))
        return acceptance.run_suite(
            backend, ws, sdir, suite=suite_name, task_id="u",
            verify_root=t / "vroot")


def _only_file(res: dict) -> dict:
    assert len(res["files"]) == 1
    return res["files"][0]


def _failing(res: dict) -> list[dict]:
    return [c for c in _only_file(res)["cases"] if not c["ok"]]


# ── G3：check 方言迴歸金標（adapter 落地前實測凍結）────────────────────

GOLDEN_CHECK_FILE = """from solution import solve

def check_one():
    assert solve(2, 3) == 6

def check_two():
    print("second case")
    assert solve(0, 5) == 0
"""
GOLDEN_GOOD_IMPL = "def solve(a, b):\n    return a * b\n"
GOLDEN_BAD_IMPL = "def solve(a, b):\n    return a * b if a else 99\n"

#: 2026-10-26 改動前實測凍結（task_id="u"、檔名 test_main.py；
#: `result_sha256` 含 task_id／suite／suite 內容／case 形狀，任何一處漂移都翻面）。
GOLDEN_PASS_DIGEST = "f6fe916c1cfde6666ef2d3c348eed3d7546233f467bfc430404ecad8209b6c24"
GOLDEN_FAIL_DIGEST = "4a7147058d4d6e66d8bb2dde4ee0d816770302111ac5cd5b5889ea272155a9c1"


def test_g3_check_dialect_pass_unchanged():
    res = _run(GOLDEN_CHECK_FILE, GOLDEN_GOOD_IMPL)
    assert res["all_pass"] is True
    assert res["complete"] is True
    assert (res["passed"], res["total"]) == (2, 2)
    assert res["result_sha256"] == GOLDEN_PASS_DIGEST


def test_g3_check_dialect_fail_unchanged():
    res = _run(GOLDEN_CHECK_FILE, GOLDEN_BAD_IMPL)
    assert res["all_pass"] is False
    assert (res["passed"], res["total"]) == (1, 2)
    assert res["result_sha256"] == GOLDEN_FAIL_DIGEST
    fails = _failing(res)
    assert [c["case"] for c in fails] == ["check_two"]
    assert fails[0]["kind"] == "assert"
    assert fails[0]["where"] == "test_main.py:8: assert solve(0, 5) == 0"


# ── G1：unittest driver 自檢 ────────────────────────────────────────────

UTEST_GOOD_FILE = """import unittest
from solution import solve


class SolveTest(unittest.TestCase):
    def test_one(self):
        self.assertEqual(solve(2, 3), 6)

    def test_two(self):
        self.assertEqual(solve(0, 5), 0)
"""


def test_g1_correct_unittest_impl_passes():
    res = _run(UTEST_GOOD_FILE, GOLDEN_GOOD_IMPL)
    assert res["all_pass"] is True
    assert res["complete"] is True
    assert (res["passed"], res["total"]) == (2, 2)
    cases = _only_file(res)["cases"]
    assert [c["case"] for c in cases] == [
        "SolveTest.test_one", "SolveTest.test_two"]
    assert all(c["kind"] == "pass" for c in cases)


def test_g1_known_bad_value_fails_as_assert():
    res = _run(UTEST_GOOD_FILE, GOLDEN_BAD_IMPL)
    assert res["all_pass"] is False
    fails = _failing(res)
    assert [c["case"] for c in fails] == ["SolveTest.test_two"]
    assert fails[0]["kind"] == "assert"
    assert fails[0]["where"] is not None and "test_main.py:" in fails[0]["where"]


def test_g1_known_bad_exception_fails_as_exception():
    impl = "def solve(a, b):\n    raise RuntimeError('boom')\n"
    res = _run(UTEST_GOOD_FILE, impl)
    assert res["all_pass"] is False
    assert {c["kind"] for c in _failing(res)} == {"exception"}


def test_g1_zero_case_unittest_file_is_a_failure():
    file = """import unittest


class NoCases(unittest.TestCase):
    def helper(self):
        self.assertEqual(1, 1)
"""
    res = _run(file, GOLDEN_GOOD_IMPL)
    assert res["all_pass"] is False
    f = _only_file(res)
    assert f["complete"] is False
    kinds = [c["kind"] for c in f["cases"]]
    assert "driver_error" in kinds


def test_g1_mixed_file_fails_and_neither_half_runs():
    file = """import unittest


def check_half():
    open("CHECK_HALF_RAN", "w").close()
    assert True


class UnTestHalf(unittest.TestCase):
    def test_marker(self):
        open("UNTEST_HALF_RAN", "w").close()
        self.assertTrue(True)
"""
    with tempfile.TemporaryDirectory() as td:
        t = pathlib.Path(td)
        ws = t / "ws"
        ws.mkdir()
        (ws / "solution.py").write_text("X = 1\n", encoding="utf-8")
        sdir = t / "suite"
        sdir.mkdir()
        (sdir / "test_main.py").write_text(file, encoding="utf-8")
        backend, _meta = sb.make_sandbox("auto", workdir=str(t / "vroot"))
        res = acceptance.run_suite(
            backend, ws, sdir, suite="visible", task_id="u",
            verify_root=t / "vroot")
    assert res["all_pass"] is False
    f = _only_file(res)
    assert f["complete"] is False
    assert f["rc"] is None  # driver 根本沒被跑
    assert len(f["cases"]) == 1
    c = f["cases"][0]
    assert c["kind"] == "protocol"
    assert "two dialects" in c["message"]
    # 兩半都沒有執行：工作區裡兩支半身的標記檔都必須不存在。
    assert not (ws / "CHECK_HALF_RAN").exists()
    assert not (ws / "UNTEST_HALF_RAN").exists()


def test_g1_tool_file_none_dialect_fails_not_skipped():
    file = """def build_report():
    return 'report'
"""
    res = _run(file, GOLDEN_GOOD_IMPL)
    assert res["all_pass"] is False
    f = _only_file(res)
    assert f["complete"] is False
    kinds = [c["kind"] for c in f["cases"]]
    assert "driver_error" in kinds
    assert "neither check_*() nor main()" in f["cases"][0]["message"]


def test_g1_async_unittest_case_fails_explicitly_not_silently():
    """實測確認的洞：unittest 跑 `async def test_*` 只調用、不等候——方法體
    一行不執行、回報 pass。driver 必須把它記成顯式失敗（kind=protocol），
    並且方法體**確實沒有跑**（標記檔不存在）。"""
    file = """import unittest


class AsyncTest(unittest.TestCase):
    async def test_never_runs(self):
        open("ASYNC_RAN", "w").close()
        assert False, "body must not execute"
"""
    with tempfile.TemporaryDirectory() as td:
        t = pathlib.Path(td)
        ws = t / "ws"
        ws.mkdir()
        (ws / "solution.py").write_text("X = 1\n", encoding="utf-8")
        sdir = t / "suite"
        sdir.mkdir()
        (sdir / "test_main.py").write_text(file, encoding="utf-8")
        backend, _meta = sb.make_sandbox("auto", workdir=str(t / "vroot"))
        res = acceptance.run_suite(
            backend, ws, sdir, suite="visible", task_id="u",
            verify_root=t / "vroot")
    assert res["all_pass"] is False
    f = _only_file(res)
    # 對帳本身是乾淨的（宣告了、也回報了）——紅的是案例結果，不是對帳。
    assert f["complete"] is True
    c = [x for x in f["cases"] if x["case"] == "AsyncTest.test_never_runs"]
    assert len(c) == 1
    assert c[0]["kind"] == "protocol"
    assert "async" in c[0]["message"]
    assert not (ws / "ASYNC_RAN").exists()


def test_g1_skipped_case_fails_not_passes():
    """`skipTest` 什麼都沒驗——算過等於把分母藏掉（I-4）。"""
    file = """import unittest


class SkipMe(unittest.TestCase):
    def test_skipped(self):
        self.skipTest("not yet")
"""
    res = _run(file, GOLDEN_GOOD_IMPL)
    assert res["all_pass"] is False
    f = _only_file(res)
    assert f["complete"] is True
    c = [x for x in f["cases"] if x["case"] == "SkipMe.test_skipped"]
    assert len(c) == 1
    assert c[0]["kind"] == "protocol"
    assert "skip" in c[0]["message"].lower()


# ── G2：跨方言一致（同一題，check_* 與 unittest 兩種寫法）─────────────

PROBLEMS = [
    dict(
        name="add",
        good="def add(a, b):\n    return a + b\n",
        bad="def add(a, b):\n    return a * b\n",
        check="""from solution import add


def check_basic():
    assert add(1, 2) == 3


def check_negative():
    assert add(-1, 1) == 0
""",
        untest="""import unittest
from solution import add


class AddTest(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(add(1, 2), 3)

    def test_negative(self):
        self.assertEqual(add(-1, 1), 0)
"""),
    dict(
        name="palindrome",
        good="""def is_palindrome(s):
    s = ''.join(ch for ch in s.lower() if ch.isalnum())
    return s == s[::-1]
""",
        bad="def is_palindrome(s):\n    return s == s[::-1]\n",
        check="""from solution import is_palindrome


def check_plain():
    assert is_palindrome('aba') is True


def check_noise():
    assert is_palindrome('A man, a plan, a canal: Panama') is True


def check_not():
    assert is_palindrome('ab') is False
""",
        untest="""import unittest
from solution import is_palindrome


class PalTest(unittest.TestCase):
    def test_plain(self):
        self.assertTrue(is_palindrome('aba'))

    def test_noise(self):
        self.assertTrue(is_palindrome('A man, a plan, a canal: Panama'))

    def test_not(self):
        self.assertFalse(is_palindrome('ab'))
"""),
    dict(
        name="word_count",
        good="""def word_count(text):
    out = {}
    for w in text.split():
        out[w] = out.get(w, 0) + 1
    return out
""",
        bad="""def word_count(text):
    out = {}
    for ch in text:
        if ch.isspace():
            continue
        out[ch] = out.get(ch, 0) + 1
    return out
""",
        check="""from solution import word_count


def check_words():
    assert word_count('ab ab c') == {'ab': 2, 'c': 1}


def check_single():
    assert word_count('xy') == {'xy': 1}
""",
        untest="""import unittest
from solution import word_count


class WordTest(unittest.TestCase):
    def test_words(self):
        self.assertEqual(word_count('ab ab c'), {'ab': 2, 'c': 1})

    def test_single(self):
        self.assertEqual(word_count('xy'), {'xy': 1})
"""),
    dict(
        name="clamp",
        good="def clamp(x, lo, hi):\n    return max(lo, min(hi, x))\n",
        bad="def clamp(x, lo, hi):\n    return max(hi, min(lo, x))\n",
        check="""from solution import clamp


def check_inside():
    assert clamp(5, 0, 10) == 5


def check_below():
    assert clamp(-1, 0, 10) == 0


def check_above():
    assert clamp(11, 0, 10) == 10
""",
        untest="""import unittest
from solution import clamp


class ClampTest(unittest.TestCase):
    def test_inside(self):
        self.assertEqual(clamp(5, 0, 10), 5)

    def test_below(self):
        self.assertEqual(clamp(-1, 0, 10), 0)

    def test_above(self):
        self.assertEqual(clamp(11, 0, 10), 10)
"""),
    dict(
        name="first_even",
        good="""def first_even(nums):
    for n in nums:
        if n % 2 == 0:
            return n
    return None
""",
        bad="""def first_even(nums):
    evens = [n for n in nums if n % 2 == 0]
    return evens[-1] if evens else None
""",
        check="""from solution import first_even


def check_first():
    assert first_even([1, 3, 4, 6]) == 4


def check_none():
    assert first_even([1, 3]) is None
""",
        untest="""import unittest
from solution import first_even


class EvenTest(unittest.TestCase):
    def test_first(self):
        self.assertEqual(first_even([1, 3, 4, 6]), 4)

    def test_none(self):
        self.assertIsNone(first_even([1, 3]))
"""),
]


@pytest.mark.parametrize("p", PROBLEMS, ids=[p["name"] for p in PROBLEMS])
def test_g2_cross_dialect_agreement(p):
    good_check = _run(p["check"], p["good"])
    good_untest = _run(p["untest"], p["good"])
    assert good_check["all_pass"] is True, p["name"]
    assert good_untest["all_pass"] is True, p["name"]
    assert good_check["complete"] is True
    assert good_untest["complete"] is True

    bad_check = _run(p["check"], p["bad"])
    bad_untest = _run(p["untest"], p["bad"])
    for res in (bad_check, bad_untest):
        assert res["all_pass"] is False, p["name"]
        # 紅得乾淨：至少一條**實實在在**的失敗（assert/exception），
        # 不是 protocol/timeout 雜訊把紅燈頂上去。
        kinds = {c["kind"] for c in _failing(res)}
        assert kinds & {"assert", "exception"}, (p["name"], kinds)
