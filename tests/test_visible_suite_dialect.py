"""方言缺口的「現行誠實語義」釘住測試（round 51，實測＋設計輪）。

設計文件：`decisions/DECISION_20261025_VISIBLE_SUITE_DIALECTS.md`
量測腳本：`ops/ref/suite_dialect_gap.py`（polyglot_py 34 題，產品可跑 0/34；
1/34 是 `pg_paasio` 的工具檔 `test_utils.py` 誤中命名規則）。

unittest 方言 adapter **實作之前**，這批測試釘住的是：現行產品對這批題的
行為是**誠實的量不到**，而不是假通過——

  A  `*_test.py`（unittest 方言）        → 產品看不到 ⇒ `no_suite`／`ungated`
  B  同一個檔改名 `test_*.py`            → 看得到；driver 對「無 check_*／main」
                                          給一筆顯式 `driver_error` ⇒ 套件失敗
  C  名為 `test_*` 的工具檔              → 同 B，絕不變成通過
  D  check 方言（對照組）                → 照樣通過，adapter 不該碰到它

⚠ 這些是**實作前釘住**。adapter 落地後，B/C 的預期會從「0 案例失敗」變成
「按 unittest 方言執行」，A 的命名規則維持產品現狀——屆時本檔要依設計文件的
G1–G5 門條件同步改寫，而不是直接刪掉：被刪掉的釘住測試等于把語義變遷藏起來。

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


# ── B：改名 test_* ⇒ 看得到，但 0 案例 ⇒ 絕不通過（I-4） ────────────────
def test_unittest_renamed_is_discovered_and_explicitly_rejected(tmp_path: Path):
    """driver 對「既無 check_* 也無 main」的檔有一筆顯式 `driver_error`——
    不是靜默零案例，更不是通過（I-4 的另一面）。"""
    res = _run_suite(tmp_path, "test_wordy.py", UNITTEST_FILE)
    assert res["files"] and res["files"][0]["declared"] == []
    assert res["total"] == 1
    assert res["files"][0]["cases"][0]["kind"] == "driver_error"
    assert res["all_pass"] is False


def test_launcher_renamed_unittest_is_refused_not_passed(tmp_path: Path):
    ws = _ws(tmp_path, "ws")
    sd = _suite_dir(tmp_path, "suite", "test_wordy.py", UNITTEST_FILE)
    s = launcher.run([sys.executable, "-c", "pass"], workspace=ws,
                     run_dir=tmp_path / "run3", suite_dir=sd, vacant_on=True,
                     task_id="dialect-pin", sandbox_name="none")
    assert s["stop_reason"] == "visible_fail"
    assert s["accepted"] is False and s["refused"] is True
    assert launcher.exit_code(s) != 0


# ── C：名為 test_* 的工具檔（pg_paasio 的 test_utils.py 陷阱） ───────────
def test_helper_named_test_file_is_discovered_and_explicitly_rejected(tmp_path: Path):
    """工具檔被命名規則撿到 ⇒ 同樣落到顯式 `driver_error`，絕不變成通過。"""
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
