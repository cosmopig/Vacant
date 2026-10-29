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
    全綠不能蓋過 teardown 異常——舊 driver 的 setUp* 同根因）。

    且失敗記錄必須**指名 tearDownClass**、driver 正常收尾（有 end marker、
    rc=0）——不可靠 driver 撞 `_ErrorHolder` 炸掉後由父層合成 driver_error
    來「碰巧紅」（那是 driver bug 披著驗收結果的外衣，見 fixture-failure
    一節）。"""
    res = _run(TEARDOWNCLASS_BAD_FILE)
    assert res["all_pass"] is False, res
    assert any(c["ok"] is False for c in _cases(res)), res
    assert _file(res)["complete"] is False
    _assert_driver_clean(res)
    fixture = [c for c in _cases(res) if "tearDownClass" in c["message"]]
    assert fixture, f"沒有指名 tearDownClass 的顯式失敗記錄: {res}"
    assert any("teardown exploded" in c["message"] for c in _cases(res)), res
    # 案例本身確實跑過並成功——記錄保留，不被 fixture 失敗吞掉。
    assert any(c["case"] == "T.test_a" and c["ok"] is True for c in _cases(res)), res


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
    """tearDownModule 拋例外 ⇒ 整組**顯式紅**（同 tearDownClass，
    且指名 fixture、driver 正常收尾——同上一個註解）。"""
    res = _run(TEARDOWNMODULE_BAD_FILE)
    assert res["all_pass"] is False, res
    assert any(c["ok"] is False for c in _cases(res)), res
    assert _file(res)["complete"] is False
    _assert_driver_clean(res)
    fixture = [c for c in _cases(res) if "tearDownModule" in c["message"]]
    assert fixture, f"沒有指名 tearDownModule 的顯式失敗記錄: {res}"
    assert any("module teardown exploded" in c["message"] for c in _cases(res)), res
    assert any(c["case"] == "T.test_a" and c["ok"] is True for c in _cases(res)), res


# ── fixture 失敗的「壞對照」：顯式紅，不是 driver 崩潰 ───────────────
#
# CPython 把 setUpClass／tearDownClass／setUpModule／tearDownModule 的
# 失敗透過一個**合成物件**（`unittest._ErrorHolder`，沒有 `_testMethodName`）
# 交給 `TestResult.addError`。driver 若用 `test._testMethodName` 拼 case id，
# 遇到它就會 AttributeError 崩潰（rc=1、沒有 end marker）：結果**碰巧**
# fail-closed，但失敗記錄變成「driver 本身炸了」（driver_error、
# 『test process did not finish normally』）——把 harness bug 披在驗收
# 結果外面，且漏掉的 case 被記成「test process 提早結束」。
#
# P0-1 驗收要求這四組 fixture 的**好/壞對照**：壞對照必須是**指名該
# fixture 的、格式良好的失敗記錄**，driver 正常收尾（end marker、rc=0）。

def _assert_driver_clean(res: dict) -> None:
    """driver 正常收尾：沒有 driver_error、沒有『end marker missing』。

    父層只在「沒有 end marker」或「rc 非 0」時才合成
    『did not finish normally』記錄——兩樣都沒有 ⇒ driver 乾淨結束。"""
    for c in _cases(res):
        assert c["kind"] != "driver_error", f"driver 崩潰（不是驗收結果）: {res}"
        assert "did not finish normally" not in c.get("message", ""), \
            f"driver 沒有正常收尾: {res}"


SETUPCLASS_FAIL_FILE = """import unittest


class SolveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raise RuntimeError("setup exploded")

    def test_one(self):
        self.assertTrue(True)
"""


def test_setupclass_failure_is_explicit_not_driver_crash():
    """setUpClass 拋例外 ⇒ **指名 setUpClass 的顯式紅**：
    沒有 driver_error、沒有 end-marker-missing、driver rc=0 收尾；
    被跳過的宣告案例仍記錄為失敗（fail-closed，不靠崩潰碰紅）。"""
    res = _run(SETUPCLASS_FAIL_FILE)
    assert res["all_pass"] is False, res
    assert _file(res)["complete"] is False
    _assert_driver_clean(res)
    fixture = [c for c in _cases(res)
               if c["case"] in ("<file>", "<module>") and "setUpClass" in c["message"]]
    assert fixture, f"沒有指名 setUpClass 的檔案層失敗記錄: {res}"
    assert any("setup exploded" in c["message"] for c in _cases(res)), res
    assert any(c["case"] == "SolveTest.test_one" and c["ok"] is False
               for c in _cases(res)), res


SETUPMODULE_FAIL_FILE = """import unittest


def setUpModule():
    raise RuntimeError("module setup exploded")


class T(unittest.TestCase):
    def test_a(self):
        self.assertTrue(True)
"""


def test_setupmodule_failure_is_explicit_not_driver_crash():
    """setUpModule 拋例外 ⇒ 指名 setUpModule 的顯式紅（同 setUpClass）。"""
    res = _run(SETUPMODULE_FAIL_FILE)
    assert res["all_pass"] is False, res
    assert _file(res)["complete"] is False
    _assert_driver_clean(res)
    fixture = [c for c in _cases(res)
               if c["case"] in ("<file>", "<module>") and "setUpModule" in c["message"]]
    assert fixture, f"沒有指名 setUpModule 的檔案層失敗記錄: {res}"
    assert any("module setup exploded" in c["message"] for c in _cases(res)), res
    assert any(c["case"] == "T.test_a" and c["ok"] is False for c in _cases(res)), res


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


# ---------------------------------------------------------------------------
# P0-1 驗收準則「原 `check_*` 雜湊不變」——永久 driver 指紋釘住
# ---------------------------------------------------------------------------
#
# driver 源碼的 sha256。driver 改一個字節，這裡就紅——把「重構」變成
# 測試看得見的改變，而不是靠記憶或 commit message。
#
# - DRIVER_SRC（check dialect）必須逐字等於 round-149 前的雜湊：
#   P0-1 重構（1ada835b）只動 UNTEST_DRIVER_SRC，驗收準則
#   「原 `check_*` 雜湊不變」要求它保持不變。
# - UNTEST_DRIVER_SRC 是 round-149 修復後的基準（fixture 失敗不再崩潰
#   driver；setUp*/tearDown* 失敗發顯式 <file> 記錄）。有意改 driver 時
#   更新此雜湊並在 commit 說明。

DRIVER_SRC_SHA256 = "5c55928866c22b5be9b8954955438f4721d1f088443008d94108e4451fb259d3"
UNTEST_DRIVER_SRC_SHA256 = "cdc3e24b8674400e8986daf19aedeaa7f6c9e831454aa42f7511fab94e23fa64"


def _sha256_of(src: str) -> str:
    import hashlib
    return hashlib.sha256(src.encode("utf-8")).hexdigest()


def test_check_driver_fingerprint_unchanged():
    """check dialect driver（DRIVER_SRC）必須逐字等於 round-149 前雜湊——
    P0-1 驗收準則「原 `check_*` 雜湊不變」。"""
    assert _sha256_of(acceptance.DRIVER_SRC) == DRIVER_SRC_SHA256, (
        "DRIVER_SRC 改了！P0-1 驗收準則要求原 check_* driver 不變。"
        "若此改變是有意為之，更新 DRIVER_SRC_SHA256 並在 commit 說明。")


def test_unittest_driver_fingerprint_pinned():
    """unittest driver（UNTEST_DRIVER_SRC）釘在 round-149 修復後基準
    （fixture 失敗發顯式 <file> 記錄，不再崩潰 driver）。
    任何 driver 改變都必須更新此雜湊並說明。"""
    assert _sha256_of(acceptance.UNTEST_DRIVER_SRC) == UNTEST_DRIVER_SRC_SHA256, (
        "UNTEST_DRIVER_SRC 改了！若此改變是有意為之，"
        "更新 UNTEST_DRIVER_SRC_SHA256 並在 commit 說明。")


SETUPCLASS_PRINT_AND_FAIL_FILE = """import unittest


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("fixture diagnostic line")
        raise RuntimeError("setup boom")

    def test_a(self):
        self.assertEqual(1, 1)
"""


def test_setupclass_failure_preserves_fixture_stdout():
    """setUpClass／setUpModule／tearDownClass／tearDownModule 失敗時，fixture 期間印出的
    stdout／stderr 必須收進 `<file>` 記錄的 `output`，不可硬塞空字串。"""
    res = _run(SETUPCLASS_PRINT_AND_FAIL_FILE)
    assert res["all_pass"] is False, res
    fixture = [c for c in _cases(res)
               if c["case"] == "<file>" and "setUpClass" in c["message"]]
    assert len(fixture) == 1, res
    assert "fixture diagnostic line" in fixture[0]["output"], fixture[0]

