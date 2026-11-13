"""e002_smoke_closure_check 單元測試（票 P20261112_2332-2；對齊 test_e005/test_e003_closure_check 架構）。

驗收：--selftest 在空 HOME（模擬本機 CI /var/tmp/ci-home）下返回 0、輸出含 VERDICT: E002_SMOKE_CLOSURE_OK；
另直接驗證 check() 正控制與 4 類篡改（A 臂 pass／M 臂 pass／A_vs_M McNemar p／BACKLOG 收口註記）必紅、
缺檔時乾淨退出不拋未捕獲異常（BACKLOG 第 40 行 sha256 釘住、改動即紅）。
"""
import importlib.util
import os
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO / "ops/audits/e002_smoke_closure_check.py"


def _load():
    spec = importlib.util.spec_from_file_location("e002_smoke_closure_check", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_selftest_ok_under_empty_home(tmp_path):
    env = {**os.environ, "HOME": str(tmp_path / "empty-home")}
    p = subprocess.run([sys.executable, str(SCRIPT), "--selftest"],
                       capture_output=True, text=True, timeout=120, env=env)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "VERDICT: E002_SMOKE_CLOSURE_OK" in p.stdout


def test_check_positive_and_four_negatives():
    mod = _load()
    report = mod.REPORT_DEFAULT.read_text(encoding="utf-8")
    packet = mod.PACKET_DEFAULT.read_text(encoding="utf-8")
    backlog = mod.BACKLOG_DEFAULT.read_text(encoding="utf-8")
    assert mod.check(report, packet, backlog, mod.RUNS_BASE) == []
    v = mod.check(report.replace('"pass": 2', '"pass": 1', 1), packet, backlog, mod.RUNS_BASE)
    assert any("per_arm[A]" in s for s in v)
    v = mod.check(report.replace('"pass": 1', '"pass": 0', 1), packet, backlog, mod.RUNS_BASE)
    assert any("per_arm[M]" in s for s in v)
    i = report.index('"A_vs_M"')
    v = mod.check(report[:i] + report[i:].replace('"mcnemar_p_two_sided": 1.0', '"mcnemar_p_two_sided": 0.5', 1),
                  packet, backlog, mod.RUNS_BASE)
    assert any("A_vs_M mcnemar_p_two_sided" in s for s in v)
    v = mod.check(report, packet, backlog.replace("已收口（10/30 17:0x 完賽）", "", 1), mod.RUNS_BASE)
    assert any("缺收口註記" in s for s in v)


def test_missing_file_clean_exit(tmp_path):
    p = subprocess.run([sys.executable, str(SCRIPT), "--report", str(tmp_path / "nope.json")],
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 1
    assert "missing file REPORT.json" in p.stdout
    assert "Traceback" not in p.stderr
