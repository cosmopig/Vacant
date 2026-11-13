"""e011_closure_check 單元測試（票 R20261113_0041-1；對齊 test_e007/test_e005_closure_check 架構）。

驗收：--selftest 在空 HOME（模擬本機 CI /var/tmp/ci-home）下返回 0、
輸出含 VERDICT: E011_CLOSURE_OK；另直接驗證 check() 正控制與 4 類篡改必紅、
缺檔時乾淨退出不拋未捕獲異常（BACKLOG 第 71 行 行＋換行 sha256 釘住 e8a98f34…、改動即紅）。
"""
import importlib.util
import os
import pathlib
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO / "ops/audits/e011_closure_check.py"


def _load():
    spec = importlib.util.spec_from_file_location("e011_closure_check", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_selftest_ok_under_empty_home(tmp_path):
    env = {**os.environ, "HOME": str(tmp_path / "empty-home")}
    p = subprocess.run([sys.executable, str(SCRIPT), "--selftest"],
                       capture_output=True, text=True, timeout=120, env=env)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "VERDICT: E011_CLOSURE_OK" in p.stdout


def test_check_positive_and_four_negatives():
    mod = _load()
    report = mod.REPORT_DEFAULT.read_text(encoding="utf-8")
    loop = mod.LOOP_DOC_DEFAULT.read_text(encoding="utf-8")
    backlog = mod.BACKLOG_DEFAULT.read_text(encoding="utf-8")
    assert mod.check(report, loop, backlog, mod.RUNS_BASE) == []
    v = mod.check(report.replace('"pass": 5', '"pass": 4', 1), loop, backlog, mod.RUNS_BASE)
    assert any("per_arm[A]" in s for s in v)
    v = mod.check(report.replace('"mcnemar_p_two_sided": 1.0', '"mcnemar_p_two_sided": 0.01', 1), loop, backlog, mod.RUNS_BASE)
    assert any("A_vs_C" in s for s in v)
    with tempfile.TemporaryDirectory() as t:
        v = mod.check(report, loop, backlog, mod.tamper_envelope_base(pathlib.Path(t)))
    assert any("envelope C 臂 PASS/FAIL" in s for s in v)
    v = mod.check(report, loop, backlog.replace("e009/e011 完賽時數 infra 格＋原因", "e009 完賽時數 infra 格＋原因", 1), mod.RUNS_BASE)
    assert any("缺跟進註記" in s for s in v)


def test_missing_file_clean_exit(tmp_path):
    p = subprocess.run([sys.executable, str(SCRIPT), "--report", str(tmp_path / "nope.json")],
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 1
    assert "missing file REPORT.json" in p.stdout
    assert "Traceback" not in p.stderr
