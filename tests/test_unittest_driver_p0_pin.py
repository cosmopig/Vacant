"""GPT 審查（2026-10-28）P0-1 的兩個 unittest driver 缺陷——釘住測試。

背景（~/dev/ops/GPT_REVIEW_20261028.md 第三節 P0 (A)(B)，工單 001）：

- **P0-1(A)** `setUpClass`／`setUpModule` 依賴的合法 TestCase 被誤判。
  round-124（9960d9f3）已改用標準 `TestSuite` 機件修復；本檔案把修復後的
  語義**釘住**（這兩組應該是**綠的**——若翻紅，是回歸）。
- **P0-1(B)** `@unittest.expectedFailure` 案例被**靜默當 PASS**（假通過）：
  unittest 把「如期失敗」記進 `res.expectedFailure`，`failures`／`errors`
  都是空的，舊 driver 掉進 `else` 分支回報 `ok=True, kind="pass"`。
  對驗收門來說，一個「預期候選是壞的」案例驗證不了候選任何事——
  **不可靜默當 PASS**。本檔案要求它顯式紅（`kind="expected_failure"`）。
  相對地 `unexpectedSuccess`（標記 expectedFailure 但實際成功）測試確實
  跑過並成功，要求**顯式記錄**（`kind="unexpected_success"`），不靜默寫成
  `"pass"`。

全部走**真的** `run_suite`（真 sandbox、真 driver、真對帳），與
`tests/test_unittest_driver.py` 同路徑。
"""
from __future__ import annotations

import pathlib
import tempfile

from vacant_network.vrun import acceptance
from vacant_network.vrun import sandbox as sb

IMPL = "def solve(a, b):\n    return a * b\n"


def _run(testfile: str, *, timeout_s: float | None = None) -> dict:
    with tempfile.TemporaryDirectory() as td:
        t = pathlib.Path(td)
        ws = t / "ws"
        ws.mkdir()
        (ws / "solution.py").write_text(IMPL, encoding="utf-8")
        sdir = t / "suite"
        sdir.mkdir()
        (sdir / "test_main.py").write_text(testfile, encoding="utf-8")
        backend, _meta = sb.make_sandbox("auto", workdir=str(t / "vroot"))
        kw = {"timeout_s": timeout_s} if timeout_s is not None else {}
        return acceptance.run_suite(
            backend, ws, sdir, suite="visible", task_id="u",
            verify_root=t / "vroot", **kw)


def _run_with_marker(testfile: str, marker_name: str) -> tuple[dict, str]:
    """執行後**在同一個暫存目錄內**讀 tearDown 副作用 marker 檔。

    必須在 TemporaryDirectory 存活期間檢查：tearDownClass／tearDownModule
    的副作用寫進工作區，若 driver 靜默跳過 hook，這檔就不會存在。
    回 `(結果, marker 內容)`；marker 不存在 ⇒ 空字串。"""
    with tempfile.TemporaryDirectory() as td:
        t = pathlib.Path(td)
        ws = t / "ws"
        ws.mkdir()
        (ws / "solution.py").write_text(IMPL, encoding="utf-8")
        sdir = t / "suite"
        sdir.mkdir()
        (sdir / "test_main.py").write_text(testfile, encoding="utf-8")
        backend, _meta = sb.make_sandbox("auto", workdir=str(t / "vroot"))
        res = acceptance.run_suite(
            backend, ws, sdir, suite="visible", task_id="u",
            verify_root=t / "vroot")
        marker = ws / marker_name
        content = marker.read_text(encoding="utf-8") if marker.exists() else ""
        return res, content


def _cases(res: dict) -> list[dict]:
    assert len(res["files"]) == 1
    return res["files"][0]["cases"]


def _file(res: dict) -> dict:
    assert len(res["files"]) == 1
    return res["files"][0]


# ── P0-1(A)：round-124 已修；釘住「合法＝過」──────────────────────────

SETUPCLASS_FILE = """import unittest
from solution import solve


class SolveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.factor = 2

    def test_one(self):
        # solve(2, 3) = 2 * 3 = 6 = self.factor * 3——只有 setUpClass 真跑了
        # （self.factor 被設成 2）這行才過。
        self.assertEqual(solve(2, 3), self.factor * 3)

    def test_two(self):
        self.assertEqual(solve(0, 5), 0)
"""


def test_setupclass_dependency_passes():
    res = _run(SETUPCLASS_FILE)
    assert res["all_pass"] is True, res
    assert res["complete"] is True
    assert (res["passed"], res["total"]) == (2, 2)
    assert all(c["kind"] == "pass" for c in _cases(res))


SETUPMODULE_FILE = """import unittest
from solution import solve

SCALE = 0   # 初值故意是錯的：只有 setUpModule 真跑了，下面的案例才會過


def setUpModule():
    global SCALE
    SCALE = 1


class SolveTest(unittest.TestCase):
    def test_one(self):
        self.assertEqual(solve(2, 3), SCALE * 6)

    def test_two(self):
        self.assertEqual(solve(0, 5), 0)
"""


def test_setupmodule_dependency_passes():
    res = _run(SETUPMODULE_FILE)
    assert res["all_pass"] is True, res
    assert (res["passed"], res["total"]) == (2, 2)
    assert all(c["kind"] == "pass" for c in _cases(res))


# ── P0-1(B)：expectedFailure 不可靜默當 PASS（目前假通過 ⇒ 紅）────────

EXPECTED_FAILURE_FILE = """import unittest
from solution import solve


class SolveTest(unittest.TestCase):
    @unittest.expectedFailure
    def test_known_broken(self):
        self.assertEqual(solve(2, 3), 999)   # 作者預期這會失敗

    def test_plain(self):
        self.assertEqual(solve(2, 3), 6)
"""


def test_expectedfailure_not_silently_passed():
    """一個「預期候選是壞的」案例驗證不了候選任何事——整組不可當 PASS，
    且該案例要**顯式**標為 expected_failure（不是 assert／不是 pass）。"""
    res = _run(EXPECTED_FAILURE_FILE)
    assert res["all_pass"] is False, res
    by_case = {c["case"]: c for c in _cases(res)}
    ef = by_case["SolveTest.test_known_broken"]
    assert ef["ok"] is False, ef
    assert ef["kind"] == "expected_failure", ef
    # 同檔裡正常的案例不受影響。
    assert by_case["SolveTest.test_plain"]["ok"] is True
    assert by_case["SolveTest.test_plain"]["kind"] == "pass"


UNEXPECTED_SUCCESS_FILE = """import unittest
from solution import solve


class SolveTest(unittest.TestCase):
    @unittest.expectedFailure
    def test_now_fixed(self):
        self.assertEqual(solve(2, 3), 6)     # 標記預期失敗，但實際成功
"""


def test_unexpectedsuccess_is_explicit_not_silent():
    """測試確實跑過並成功——不可靜默寫成普通 `"pass"`，要顯式 kind。"""
    res = _run(UNEXPECTED_SUCCESS_FILE)
    by_case = {c["case"]: c for c in _cases(res)}
    case = by_case["SolveTest.test_now_fixed"]
    assert case["kind"] == "unexpected_success", case
    assert case["ok"] is True, case


# ── P0-1 checklist 缺口（round-143）：inherited tests／tearDown*／timeout ──

INHERIT_GOOD_FILE = """import unittest
from solution import solve


class Base(unittest.TestCase):
    def test_base(self):
        self.assertEqual(solve(2, 3), 6)


class Sub(Base):
    def test_sub(self):
        self.assertEqual(solve(0, 5), 0)
"""


def test_inherited_tests_pass_and_all_three_declared():
    """`Sub(Base)`：loader 從 `dir(Sub)` 收集，`Sub` 也會執行 `Base` 的
    `test_base`（case id `Sub.test_base`）。宣告清單與對帳必須數到全部三筆，
    否則每個繼承 case 都是「未宣告的 id」⇒ 正確套件被誤判 protocol 失敗
    （round-143 實測的缺陷：宣告只有 `Base.test_base`）。"""
    res = _run(INHERIT_GOOD_FILE)
    assert res["all_pass"] is True, res
    assert (res["passed"], res["total"]) == (3, 3), res
    assert set(c["case"] for c in _cases(res)) == {
        "Base.test_base", "Sub.test_base", "Sub.test_sub"}


INHERIT_BAD_FILE = """import unittest
from solution import solve


class Base(unittest.TestCase):
    def test_base(self):
        self.assertEqual(solve(2, 3), 6)


class Sub(Base):
    def test_sub(self):
        self.assertEqual(solve(2, 3), 999)   # 錯的：必須紅
"""


def test_inherited_bad_still_red_and_others_recorded():
    """繼承 case 進分母的另一面：`Sub.test_sub` 失敗 ⇒ 整組紅；
    同檔正常的 `Base.test_base` 與繼承的 `Sub.test_base` 照樣被記錄。"""
    res = _run(INHERIT_BAD_FILE)
    assert res["all_pass"] is False, res
    by_case = {c["case"]: c for c in _cases(res)}
    assert by_case["Sub.test_sub"]["ok"] is False
    assert by_case["Base.test_base"]["ok"] is True
    assert by_case["Sub.test_base"]["ok"] is True


TEARDOWNCLASS_GOOD_FILE = """import unittest


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.factor = 2

    @classmethod
    def tearDownClass(cls):
        # 副作用寫進工作區：driver 若靜默跳過 tearDownClass，這檔不會存在。
        with open("tdclass_ran.txt", "w") as f:
            f.write("done")

    def test_one(self):
        self.assertEqual(self.factor * 3, 6)
"""


def test_teardownclass_runs_and_passes():
    res, content = _run_with_marker(TEARDOWNCLASS_GOOD_FILE, "tdclass_ran.txt")
    assert res["all_pass"] is True, res
    assert content == "done", "tearDownClass 沒有被執行（副作用 marker 不存在）"


TEARDOWNCLASS_BAD_FILE = """import unittest


class T(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        raise RuntimeError("teardown exploded")

    def test_a(self):
        self.assertTrue(True)
"""


def test_teardownclass_failure_is_explicit_red():
    """tearDownClass 拋例外 ⇒ 整組**顯式紅**（不可靜默當 PASS：案例本身
    全綠不能蓋過 teardown 異常——舊 driver 的 setUp* 同根因）。"""
    res = _run(TEARDOWNCLASS_BAD_FILE)
    assert res["all_pass"] is False, res
    assert any(c["ok"] is False for c in _cases(res)), res
    assert _file(res)["complete"] is False


TEARDOWNMODULE_GOOD_FILE = """import unittest


def tearDownModule():
    # 副作用寫進工作區：driver 若靜默跳過 tearDownModule，這檔不會存在。
    with open("tdmodule_ran.txt", "w") as f:
        f.write("done")


class T(unittest.TestCase):
    def test_one(self):
        self.assertTrue(True)
"""


def test_teardownmodule_runs_and_passes():
    res, content = _run_with_marker(TEARDOWNMODULE_GOOD_FILE, "tdmodule_ran.txt")
    assert res["all_pass"] is True, res
    assert content == "done", "tearDownModule 沒有被執行（副作用 marker 不存在）"


TEARDOWNMODULE_BAD_FILE = """import unittest


def tearDownModule():
    raise RuntimeError("module teardown exploded")


class T(unittest.TestCase):
    def test_a(self):
        self.assertTrue(True)
"""


def test_teardownmodule_failure_is_explicit_red():
    """tearDownModule 拋例外 ⇒ 整組**顯式紅**（同 tearDownClass）。"""
    res = _run(TEARDOWNMODULE_BAD_FILE)
    assert res["all_pass"] is False, res
    assert any(c["ok"] is False for c in _cases(res)), res
    assert _file(res)["complete"] is False


TIMEOUT_FILE = """import unittest
import time


class T(unittest.TestCase):
    def test_hang(self):
        while True:
            time.sleep(0.05)
"""


def test_timeout_is_explicit_red_and_bounded():
    """卡死的測試 ⇒ 顯式紅（`kind="timeout"` 檔案層＋案例層 incomplete）、
    wall 時間有界（不能被卡住）。"""
    import time as _time
    t0 = _time.monotonic()
    res = _run(TIMEOUT_FILE, timeout_s=3)
    elapsed = _time.monotonic() - t0
    assert res["all_pass"] is False, res
    f = _file(res)
    assert f["timed_out"] is True
    assert any(c["ok"] is False and c["kind"] == "timeout" for c in _cases(res)), res
    assert any(c["ok"] is False and c["kind"] == "incomplete" and c["case"] == "T.test_hang"
               for c in _cases(res)), res
    assert elapsed < 30, f"wall 時間 {elapsed:.1f}s 超出有界預期"
