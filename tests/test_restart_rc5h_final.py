"""rc5 定案收尾（第三次查證）：非套件測試目錄的 import 順序、load_error 訊息。"""
import sys

from vacant_network.adapters import restart as R


def _build(script: str):
    def build(prompt, ws):
        return R.Launch(argv=[sys.executable, "-c", script], env={})
    return build


def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    monkeypatch.setenv("VACANT_WORK", str(tmp_path / "vw"))


def test_nonpackage_tests_dir_resolves_test_dir_before_root(tmp_path, monkeypatch):
    """tests/ 沒有 __init__.py、tests/expected.py（對照值，被固定住）與根目錄 expected.py 並存；
    agent 只改根目錄那個、bug 沒修 ⇒ 必須不通過（和 unittest discover -s tests／pytest 一致）。"""
    _env(tmp_path, monkeypatch)
    p = tmp_path / "proj"
    (p / "tests").mkdir(parents=True)
    (p / "mycal.py").write_text("def days_in_feb(y):\n    return 28\n", encoding="utf-8")
    (p / "expected.py").write_text("EXPECTED = 0   # unrelated app constant\n", encoding="utf-8")
    (p / "tests" / "expected.py").write_text("EXPECTED = 29   # oracle used by tests\n", encoding="utf-8")
    (p / "tests" / "test_cal.py").write_text(
        "import unittest\nfrom expected import EXPECTED\nfrom mycal import days_in_feb\n"
        "class T(unittest.TestCase):\n    def test_leap(self):\n        self.assertEqual(days_in_feb(2024), EXPECTED)\n",
        encoding="utf-8")
    agent = "import pathlib; pathlib.Path('expected.py').write_text('EXPECTED = 28\\n')"
    res = R.run(p, _build(agent), "fix", max_attempts=1, attempt_timeout_s=20, budget_s=60)
    assert res["accepted"] is False
    assert res["attempts"][0]["passed"] == 0 and res["attempts"][0]["run"] == 1


def test_nonpackage_tests_dir_correct_fix_still_passes(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch)
    p = tmp_path / "proj"
    (p / "tests").mkdir(parents=True)
    (p / "mycal.py").write_text("def days_in_feb(y):\n    return 28\n", encoding="utf-8")
    (p / "tests" / "expected.py").write_text("EXPECTED = 29\n", encoding="utf-8")
    (p / "tests" / "test_cal.py").write_text(
        "import unittest\nfrom expected import EXPECTED\nfrom mycal import days_in_feb\n"
        "class T(unittest.TestCase):\n    def test_leap(self):\n        self.assertEqual(days_in_feb(2024), EXPECTED)\n",
        encoding="utf-8")
    fix = ("import pathlib; pathlib.Path('mycal.py').write_text("
           "'def days_in_feb(y):\\n    return 29 if y % 4 == 0 else 28\\n')")
    res = R.run(p, _build(fix), "fix", max_attempts=1, attempt_timeout_s=20, budget_s=60)
    assert res["accepted"] is True


def test_load_error_first_line_in_summary(tmp_path, monkeypatch):
    """src/ 排法沒有 PYTHONPATH：照真實行為不過，但交件訊息要印出 ModuleNotFoundError 那一行。"""
    _env(tmp_path, monkeypatch)
    p = tmp_path / "proj"
    (p / "src" / "pkg").mkdir(parents=True)
    (p / "tests").mkdir()
    (p / "src" / "pkg" / "__init__.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (p / "tests" / "test_pkg.py").write_text(
        "import unittest, pkg\nclass T(unittest.TestCase):\n    def test_add(self):\n"
        "        self.assertEqual(pkg.add(2, 3), 5)\n", encoding="utf-8")
    res = R.run(p, _build("pass"), "fix", max_attempts=1, attempt_timeout_s=20, budget_s=60)
    msg = R.summary(res)
    assert "tests could not be loaded:" in msg and "ModuleNotFoundError" in msg
