"""rc5：嘗試被單次時限切斷時，交件訊息與收據要講出來（只改訊息，政策不變）。"""
import json
import pathlib
import sys

from vacant_network.adapters import restart as R


def _proj(tmp_path):
    p = tmp_path / "proj"
    p.mkdir()
    (p / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (p / "test_calc.py").write_text(
        "import unittest, calc\nclass T(unittest.TestCase):\n    def test_add(self):\n"
        "        self.assertEqual(calc.add(2, 3), 5)\n", encoding="utf-8")
    return p


def _build(script: str):
    def build(prompt, ws):
        return R.Launch(argv=[sys.executable, "-c", script], env={})
    return build


def test_every_attempt_cut_says_raise_the_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    monkeypatch.setenv("VACANT_WORK", str(tmp_path / "vw"))
    p = _proj(tmp_path)
    res = R.run(p, _build("import time; time.sleep(30)"), "fix", max_attempts=2,
                attempt_timeout_s=2, budget_s=20, min_attempt_s=0.5)
    assert len(res["attempts"]) == 2 and all(a["timed_out"] for a in res["attempts"])
    assert all(a["time_limit_s"] <= 2.0 for a in res["attempts"])
    msg = R.summary(res)
    assert msg.count("was cut off at the 2s time limit") == 2
    assert "every attempt hit the time limit" in msg and "--attempt-timeout" in msg
    # 政策不變：沒過、交通過最多的那次（這裡兩次都 0/1，交最後一次）
    assert res["accepted"] is False


def test_no_cut_no_notice(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    monkeypatch.setenv("VACANT_WORK", str(tmp_path / "vw"))
    p = _proj(tmp_path)
    fix = "import pathlib; pathlib.Path('calc.py').write_text('def add(a, b):\\n    return a + b\\n')"
    res = R.run(p, _build(fix), "fix", max_attempts=2, attempt_timeout_s=20, budget_s=60)
    assert res["accepted"] is True
    msg = R.summary(res)
    assert "time limit" not in msg
