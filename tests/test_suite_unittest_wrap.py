"""套件可以用「單個 check_* 包住一個 unittest 模組」的方式驗收。

2026-10-26 live batch（~/dev/ops/live_batch/）實測時用的就是這個形狀：
polyglot 任務的驗收檔是 `unittest` 模組（`<stem>_test.py`，沒有
`test_` 前綴、不是 `check_*`），driver 只認頂層 `def check_*`。
包裝法：

    suite/
      thing_test.py   # 任務原本的 unittest 模組（helper，不被當成測試檔）
      test_wrap.py    # def check_all(): 跑 unittest，失敗就 raise

這個測試把那一層**鎖住**：

- helper 檔（沒有 `test_` 前綴）不會被當成第二支測試檔；
- 解法對 ⇒ 一個 case、`all_pass=True`；
- 解法錯 ⇒ `all_pass=False`，失敗訊息帶著 unittest 的 fail/error 數；
- 解法缺（`ModuleNotFoundError`，live batch 裡 pg_bowling 第一擊的形狀）
  ⇒ 同樣是明確的失敗，不是「量不到」被當成過。
"""
from __future__ import annotations

import pathlib

from vacant_network.vrun import acceptance, sandbox as sb

WRAP = '''import unittest

def check_all():
    import thing_test
    suite = unittest.defaultTestLoader.loadTestsFromModule(thing_test)
    r = unittest.TextTestRunner(verbosity=0).run(suite)
    assert r.wasSuccessful(), \\
        f"{{len(r.failures)}} failures, {{len(r.errors)}} errors"
'''

THING_TEST = '''import unittest
from thing import add

class ThingTest(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)

    def test_add_negative(self):
        self.assertEqual(add(-1, 1), 0)
'''


def _run(tmp_path: pathlib.Path, solution: str) -> dict:
    ws = tmp_path / "ws"
    suite = tmp_path / "suite"
    ws.mkdir()
    suite.mkdir()
    if solution:
        (ws / "thing.py").write_text(solution, encoding="utf-8")
    (suite / "thing_test.py").write_text(THING_TEST, encoding="utf-8")
    (suite / "test_wrap.py").write_text(WRAP, encoding="utf-8")
    return acceptance.run_suite(sb.NoneSandbox(), ws, suite, suite="visible",
                                task_id="t", verify_root=tmp_path / "_v",
                                timeout_s=20)


def test_helper_file_is_not_a_second_test_file(tmp_path):
    res = _run(tmp_path, "def add(a, b):\n    return a + b\n")
    assert [f["file"] for f in res["files"]] == ["test_wrap.py"]
    assert res["files"][0]["declared"] == ["check_all"]


def test_correct_solution_passes_as_one_case(tmp_path):
    res = _run(tmp_path, "def add(a, b):\n    return a + b\n")
    assert res["all_pass"] is True
    assert res["complete"] is True
    assert (res["passed"], res["total"]) == (1, 1)


def test_wrong_solution_fails_with_the_counts_in_the_message(tmp_path):
    res = _run(tmp_path, "def add(a, b):\n    return a - b\n")
    assert res["all_pass"] is False
    bad = acceptance.failing_cases(res)
    assert len(bad) == 1 and bad[0]["kind"] == "assert"
    assert "failures" in bad[0]["message"] and "errors" in bad[0]["message"]


def test_missing_solution_is_a_clear_failure_not_unknown(tmp_path):
    """pg_bowling live 第一擊：`ModuleNotFoundError: No module named 'bowling'`。"""
    res = _run(tmp_path, solution="")
    assert res["all_pass"] is False
    bad = acceptance.failing_cases(res)
    assert len(bad) == 1
    assert bad[0]["kind"] == "exception"
    assert "No module named" in bad[0]["message"]
