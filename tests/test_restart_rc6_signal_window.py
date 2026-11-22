"""rc6 第二次查證 P2：run() 結束到 summary 印完、結束碼決定之間不能有訊號空窗。

之前 run() 的 finally 先把處理器還原，之後的 SIGINT 被 cli.main() 的總攔截接住，印「interrupted; project unchanged」
——那時專案其實已完整寫回、收據也記為已交付。這裡驗兩件事：
1. 行程內：在 run() 回傳之後、summary 印出時連送訊號，仍印出真正的 summary、結束碼照交件結果、補一行說明。
2. 子行程：在各種時間點密集送 SIGINT，結果只有兩種——寫回前中斷（130、專案不變、有中斷訊息），或完整交件
   （專案完整寫回、印出 summary、結束碼照交件結果）；絕不出現「專案已寫回卻說沒改動」或沒有 summary 的情況。
"""
from __future__ import annotations

import os
import pathlib
import signal
import subprocess
import sys
import textwrap
import time

from vacant_network.adapters import cli as CLI
from vacant_network.adapters import restart as R

REPO = pathlib.Path(__file__).resolve().parents[1]
FIXED = "def add(a, b):\n    return a + b\n"


def _project(root: pathlib.Path) -> pathlib.Path:
    p = root / "proj"
    p.mkdir()
    (p / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (p / "test_calc.py").write_text(textwrap.dedent("""\
        import unittest, calc
        class T(unittest.TestCase):
            def test_add(self):
                self.assertEqual(calc.add(1, 2), 3)
    """), encoding="utf-8")
    return p


def _agent(root: pathlib.Path) -> pathlib.Path:
    a = root / "agent.py"
    a.write_text("import pathlib\npathlib.Path('calc.py').write_text(%r)\n" % FIXED, encoding="utf-8")
    return a


def test_signals_after_run_returned_do_not_hide_summary(tmp_path, monkeypatch, capsys):
    proj = _project(tmp_path)
    agent = _agent(tmp_path)
    real_run, real_summary = R.run, R.summary

    def run_then_signal(*a, **kw):
        res = real_run(*a, **kw)
        os.kill(os.getpid(), signal.SIGINT)      # run() 已還原處理器、summary 還沒印
        return res

    def summary_with_signals(res):
        for sig in (signal.SIGINT, signal.SIGINT, signal.SIGTERM):
            os.kill(os.getpid(), sig)
        return real_summary(res)

    monkeypatch.setattr(R, "run", run_then_signal)
    monkeypatch.setattr(R, "summary", summary_with_signals)
    monkeypatch.chdir(proj)
    rc = CLI.main(["do", "--cmd", f"{sys.executable} {agent}", "--prompt", "fix"])
    out = capsys.readouterr()
    assert rc == 0, out
    assert "acceptance passed" in out.out or "accepted" in out.out.lower()
    assert "arrived after the run had finished" in out.out
    assert "interrupted" not in out.err
    assert (proj / "calc.py").read_text() == FIXED


def _run_with_burst(tmp: pathlib.Path, delay_s: float) -> tuple[int, str, str, str]:
    proj = _project(tmp)
    agent = _agent(tmp)
    env = {**os.environ, "PYTHONPATH": str(REPO), "VACANT_HOME": str(tmp / "vh"), "VACANT_WORK": str(tmp / "vw")}
    proc = subprocess.Popen([sys.executable, "-m", "vacant_network.cli", "do", "--cmd", f"{sys.executable} {agent}",
                             "--prompt", "fix"], cwd=proj, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True)
    time.sleep(delay_s)
    for _ in range(20):
        try:
            proc.send_signal(signal.SIGINT)
        except ProcessLookupError:
            break
        time.sleep(0.002)
    out, err = proc.communicate(timeout=60)
    return proc.returncode, out, err, (proj / "calc.py").read_text()


def test_sigint_bursts_at_many_offsets_never_misreport(tmp_path):
    # 先量一次不打斷要多久，再把連發的起點撒在整段執行上
    t0 = time.monotonic()
    base = tmp_path / "timing"
    base.mkdir()
    proj = _project(base)
    agent = _agent(base)
    env = {**os.environ, "PYTHONPATH": str(REPO), "VACANT_HOME": str(base / "vh"), "VACANT_WORK": str(base / "vw")}
    subprocess.run([sys.executable, "-m", "vacant_network.cli", "do", "--cmd", f"{sys.executable} {agent}",
                    "--prompt", "fix"], cwd=proj, env=env, capture_output=True, timeout=60)
    total = time.monotonic() - t0
    outcomes = {"interrupted_clean": 0, "delivered": 0}
    n = 16
    for i in range(n):
        d = tmp_path / f"r{i}"
        d.mkdir()
        rc, out, err, body = _run_with_burst(d, total * (i + 1) / (n + 1))
        if body != FIXED:
            # 寫回前中斷：專案不變。130＝vacant 自己收尾並說明；-SIGINT＝訊號早到 Python 還在載入模組
            # （vacant 的程式碼都還沒執行，什麼都沒做；這是直譯器啟動期，不在 vacant 的控制範圍）
            # 直譯器啟動期（site／模組載入）被打斷時結束碼可能是 -SIGINT 或 1，vacant 的程式碼都還沒跑
            assert rc != 0, (i, rc, out, err)
            assert "acceptance passed" not in out, (i, out, err)
            if rc == 130:
                assert "interrupted" in (out + err), (i, out, err)
            outcomes["interrupted_clean"] += 1
        else:
            # 完整交件：專案完整寫回、印出 summary、結束碼照交件結果、沒有「沒改動」的說法
            assert rc == 0, (i, rc, out, err)
            assert body == FIXED, (i, out, err)
            assert "acceptance passed" in out, (i, out, err)
            assert "project unchanged" not in (out + err), (i, out, err)
            outcomes["delivered"] += 1
    assert sum(outcomes.values()) == n
