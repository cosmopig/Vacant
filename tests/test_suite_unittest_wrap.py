"""套件可以用「單個 check_* 包住一個 unittest 模組」的方式驗收——
**以及 P0-2 之後這個形狀的真實行為**（本檔是語意過渡的 pin，不是舊 pin）。

2026-10-26 live batch（~/dev/ops/live_batch/）實測時用的就是這個形狀：
polyglot 任務的驗收檔是 `unittest` 模組（`<stem>_test.py`，沒有
`test_` 前綴、不是 `check_*`），當時 driver 只認 `test_*.py`，所以靠
包裝法讓它被發現：

    suite/
      thing_test.py   # 任務原本的 unittest 模組（當時＝helper，不被當成測試檔）
      test_wrap.py    # def check_all(): 跑 unittest，失敗就 raise

**P0-2（round 131，`ops/vlab/packets/p02_testpy_discovery.md`，GPT review
P0-2）之後命名規則是 `test_*.py` **加** `*_test.py`**：`thing_test.py`
現在本身就被發現、按 unittest 方言直接執行。這個形狀仍然成立，而且
**更嚴**——同一份測試跑兩條路，兩條路都過才算過：

- `thing_test.py` → unittest driver，2 個 case；
- `test_wrap.py`  → check driver，1 個 case（`check_all` 內部再跑一次
  unittest，失敗帶 fail/error 數）。

舊 pin 的「helper 檔不會被當成第二支測試檔」**不再成立**（那是舊命名
規則的產物，round 51 的「`none` 檔不靜默跳過」pin 由
`tests/test_visible_suite_dialect.py` 與 `tests/test_p02_star_test_discovery.py`
繼續鎖）。本檔鎖的是過渡後的語意：

- 解法對 ⇒ `all_pass=True`（3 個 case：2 直接 + 1 包裝）；
- 解法錯 ⇒ `all_pass=False`，**兩條路都敗**：直接 unittest 的 assert
  加上包裝的 fail/error 數訊息；
- 解法缺（`ModuleNotFoundError`，live batch 裡 pg_bowling 第一擊的形狀）
  ⇒ 全是**明確失敗**（`import`／`exception`），沒有「量不到」被當成過。
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


def test_both_files_are_discovered_and_executed(tmp_path):
    """P0-2 命名：`*_test.py` 與 `test_*.py` 都是測試檔（discovery 可查）。"""
    res = _run(tmp_path, "def add(a, b):\n    return a + b\n")
    assert [f["file"] for f in res["files"]] == ["test_wrap.py", "thing_test.py"]
    by_file = {d["name"]: d for d in res["discovery"]}
    assert by_file["thing_test.py"]["role"] == "test"
    assert by_file["thing_test.py"]["dialect"] == "unittest"
    assert by_file["thing_test.py"]["executed"] is True
    assert by_file["test_wrap.py"]["role"] == "test"
    assert by_file["test_wrap.py"]["dialect"] == "check"


def test_correct_solution_passes_as_three_cases(tmp_path):
    res = _run(tmp_path, "def add(a, b):\n    return a + b\n")
    assert res["all_pass"] is True
    assert res["complete"] is True
    assert (res["passed"], res["total"]) == (3, 3)
    per = {f["file"]: (f["passed"], f["total"]) for f in res["files"]}
    assert per == {"test_wrap.py": (1, 1), "thing_test.py": (2, 2)}


def test_wrong_solution_fails_on_both_paths(tmp_path):
    res = _run(tmp_path, "def add(a, b):\n    return a - b\n")
    assert res["all_pass"] is False
    bad = acceptance.failing_cases(res)
    # 兩條路都敗：直接 unittest 的兩個 assert，加包裝的 fail/error 數訊息。
    assert {b["file"] for b in bad} == {"test_wrap.py", "thing_test.py"}
    wrapped = [b for b in bad if b["file"] == "test_wrap.py"][0]
    assert wrapped["kind"] == "assert"
    assert "failures" in wrapped["message"] and "errors" in wrapped["message"]
    direct = [b for b in bad if b["file"] == "thing_test.py"]
    assert len(direct) == 2 and all(b["kind"] == "assert" for b in direct)


def test_missing_solution_is_a_clear_failure_not_unknown(tmp_path):
    """pg_bowling live 第一擊：`ModuleNotFoundError: No module named 'bowling'`。"""
    res = _run(tmp_path, solution="")
    assert res["all_pass"] is False
    assert res["complete"] is False
    bad = acceptance.failing_cases(res)
    # 全是明確失敗（import/exception），沒有「量不到」被當成過。
    assert bad and all(b["kind"] in ("import", "exception") for b in bad)
    # 根因訊息在原始 import/exception 筆上（`not run` 筆只記「沒跑到」）。
    assert any("No module named" in b["message"] for b in bad)
