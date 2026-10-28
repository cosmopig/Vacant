"""方言缺口釘住測試（round 51 實作前寫下；B 段依設計 §五 於 round 126 改寫）。

設計文件：`decisions/DECISION_20261025_VISIBLE_SUITE_DIALECTS.md`
量測腳本：`ops/ref/suite_dialect_gap.py`（polyglot_py 34 題，產品可跑 0/34；
1/34 是 `pg_paasio` 的工具檔 `test_utils.py` 誤中命名規則）。

這批測試釘住產品對這批題的語義——誠實、不是假通過：

  A  `*_test.py`（unittest 方言）        → 產品看不到（預設命名維持現狀）⇒
                                          `no_suite`／`ungated`
  B  同一個檔改名 `test_*.py`            → 看得到；adapter 落地後按 unittest
                                          方言執行：對的實現要過，錯的實現
                                          照樣紅（負對照保留原釘住意圖）
  C  名為 `test_*` 的工具檔              → `none` 方言，照樣顯式 `driver_error`，
                                          絕不變成通過
  D  check 方言（對照組）                → 照樣通過；G3 金標雜湊保證與
                                          adapter 前逐位相同

**實作前（round 51）B 的釘住是**「0 案例 ⇒ 顯式 `driver_error`、絕不通過」；
adapter 落地（round 124，G1–G3 綠）後，依設計 §五的要求 B **改寫**（不是
刪除）為落地後語義，並加一筆「錯的實現仍拒」的負對照——原釘住的意圖
（這條路徑不能靜默變成通過）保留；C/D 不變；A 的命名規則仍是產品現狀
（opt-in 命名是獨立門 G5，不屬於本檔）。
被刪掉的釘住測試等于把語義變遷藏起來，所以這裡連舊語義都寫在註解裡。

零模型呼叫：agent 是 `python3 -c pass`（不發任何請求）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vacant_network.vrun import acceptance, launcher
from vacant_network.vrun.sandbox import make_sandbox  # noqa: E402

UNITTEST_FILE = '''\
import unittest


class WordyTest(unittest.TestCase):
    def test_says_wordy(self):
        from solution import greeting
        self.assertEqual(greeting(), "wordy")
'''

CHECK_FILE = '''\
def check_says():
    from solution import greeting
    assert greeting() == "wordy"
'''


def _ws(tmp_path: Path, name: str) -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / "solution.py").write_text(
        "def greeting():\n    return 'wordy'\n", encoding="utf-8")
    return d


def _suite_dir(tmp_path: Path, name: str, filename: str, body: str) -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / filename).write_text(body, encoding="utf-8")
    return d


def _run_suite(tmp_path: Path, filename: str, body: str) -> dict:
    ws = _ws(tmp_path, "ws")
    sd = _suite_dir(tmp_path, "suite", filename, body)
    sb, _meta = make_sandbox("none", workdir=tmp_path / "sbwork")
    return acceptance.run_suite(sb, ws, sd, suite="visible",
                                task_id="dialect-pin",
                                verify_root=tmp_path / "verify")


# ── A：*_test.py（unittest 方言）＝ 產品今天看不到的那 33/34 題 ──────────
def test_unittest_test_named_file_is_invisible_to_product(tmp_path: Path):
    """34 題 polyglot_py 的真實形狀。現行規則下＝無訊號，**不是**通過。"""
    sd = _suite_dir(tmp_path, "suite", "wordy_test.py", UNITTEST_FILE)
    assert acceptance.test_files(sd) == []


def test_launcher_unittest_suite_dir_is_no_signal(tmp_path: Path):
    ws = _ws(tmp_path, "ws")
    sd = _suite_dir(tmp_path, "suite", "wordy_test.py", UNITTEST_FILE)
    s = launcher.run([sys.executable, "-c", "pass"], workspace=ws,
                     run_dir=tmp_path / "run1", suite_dir=sd, vacant_on=True,
                     task_id="dialect-pin", sandbox_name="none")
    assert s["stop_reason"] == "no_suite"
    assert s["refused"] is True
    assert launcher.exit_code(s) != 0


def test_launcher_unittest_suite_dir_with_allow_is_null_not_true(tmp_path: Path):
    ws = _ws(tmp_path, "ws")
    sd = _suite_dir(tmp_path, "suite", "wordy_test.py", UNITTEST_FILE)
    s = launcher.run([sys.executable, "-c", "pass"], workspace=ws,
                     run_dir=tmp_path / "run2", suite_dir=sd, vacant_on=True,
                     allow_no_suite=True, task_id="dialect-pin",
                     sandbox_name="none")
    assert s["stop_reason"] == "ungated"
    assert s["accepted"] is None        # 量不到 ≠ 通過；收據不得寫 True


# ── B：改名 test_* ⇒ 看得到，按 unittest 方言執行（round 126 改寫，設計 §五）──
# [round 51 實作前釘住] 舊預期：0 案例 ⇒ 一筆顯式 `driver_error` ⇒ 絕不通過
# （I-4 的另一面）。adapter 落地後同一檔案是**真訊號**：對的實現要過，
# 錯的實現仍紅——「不能靜默變成通過」的意圖由 B3 負對照保留。
def test_unittest_renamed_is_discovered_and_executed(tmp_path: Path):
    """[B1] 對的實現 ⇒ unittest 方言照樣跑、照樣過（adapter 的目的）。

    case id ＝ 宣告清單的 `ClassName.method`；對帳完整（G1 自檢同路徑）。"""
    res = _run_suite(tmp_path, "test_wordy.py", UNITTEST_FILE)
    f = res["files"][0]
    assert f["declared"] == ["WordyTest.test_says_wordy"]
    assert f["cases"][0]["case"] == "WordyTest.test_says_wordy"
    assert f["cases"][0]["kind"] == "pass"
    assert f["complete"] is True
    assert res["all_pass"] is True


def test_launcher_renamed_unittest_correct_impl_is_delivered(tmp_path: Path):
    """[B2] launcher 層：同一套件的對的實現 ⇒ `visible_pass`、accepted=True。"""
    ws = _ws(tmp_path, "ws")
    sd = _suite_dir(tmp_path, "suite", "test_wordy.py", UNITTEST_FILE)
    s = launcher.run([sys.executable, "-c", "pass"], workspace=ws,
                     run_dir=tmp_path / "run3", suite_dir=sd, vacant_on=True,
                     task_id="dialect-pin", sandbox_name="none")
    assert s["stop_reason"] == "visible_pass"
    assert s["accepted"] is True


def test_launcher_renamed_unittest_wrong_impl_is_refused(tmp_path: Path):
    """[B3] 原釘住意圖的負對照：改名後的 unittest 檔**絕不靜默變成通過**——
    實現錯了仍要紅，且紅在實實在在的 assert（不是 protocol 雜訊）。"""
    ws = tmp_path / "ws4"
    ws.mkdir()
    (ws / "solution.py").write_text(
        "def greeting():\n    return 'brief'\n", encoding="utf-8")
    sd = _suite_dir(tmp_path, "suite4", "test_wordy.py", UNITTEST_FILE)
    s = launcher.run([sys.executable, "-c", "pass"], workspace=ws,
                     run_dir=tmp_path / "run4", suite_dir=sd, vacant_on=True,
                     task_id="dialect-pin", sandbox_name="none")
    assert s["stop_reason"] == "visible_fail"
    assert s["accepted"] is False and s["refused"] is True
    assert launcher.exit_code(s) != 0


# ── C：名為 test_* 的工具檔（pg_paasio 的 test_utils.py 陷阱） ───────────
# `none` 方言（無 check_*／main、無 TestCase 子類）：adapter 不改它的語義，
# 仍落到顯式 `driver_error`（設計 §4.2：none 不是靜默跳過）。round 126 核對。
def test_helper_named_test_file_is_discovered_and_explicitly_rejected(tmp_path: Path):
    """工具檔被命名規則撿到 ⇒ 落到顯式 `driver_error`，絕不變成通過。"""
    res = _run_suite(tmp_path, "test_utils.py", "def helper():\n    return 1\n")
    assert res["files"] and res["files"][0]["declared"] == []
    assert res["total"] == 1
    assert res["files"][0]["cases"][0]["kind"] == "driver_error"
    assert res["all_pass"] is False


# ── D：check 方言對照組（adapter 不該碰到它） ────────────────────────────
def test_check_dialect_still_passes(tmp_path: Path):
    res = _run_suite(tmp_path, "test_check.py", CHECK_FILE)
    assert res["total"] >= 1
    assert res["all_pass"] is True
