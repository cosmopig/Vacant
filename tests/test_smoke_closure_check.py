"""smoke_closure_check 單元測試（票 P20261113_0132-1；對齊 test_e002_smoke_closure_check 架構）。

驗收：--selftest 在空 HOME（模擬本機 CI /var/tmp/ci-home）下返回 0、輸出含 VERDICT: SMOKE_CLOSURE_OK；
另直接驗證 check() 正控制與 4 類篡改（REPORT cells_scored／C 臂 vacant_sha／envelope C 臂 NO_EVIDENCE 數／
delivery mode）必紅、缺檔時乾淨退出不拋未捕獲異常（2 格 A/C、envelope NO_EVIDENCE 誠實狀態；0 model calls）。
"""
import importlib.util
import os
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO / "ops/audits/smoke_closure_check.py"


def _load():
    spec = importlib.util.spec_from_file_location("smoke_closure_check", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_selftest_ok_under_empty_home(tmp_path):
    env = {**os.environ, "HOME": str(tmp_path / "empty-home")}
    p = subprocess.run([sys.executable, str(SCRIPT), "--selftest"],
                       capture_output=True, text=True, timeout=120, env=env)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "VERDICT: SMOKE_CLOSURE_OK" in p.stdout


def test_check_positive_and_four_negatives(tmp_path):
    mod = _load()
    report = mod.REPORT_DEFAULT.read_text(encoding="utf-8")
    delivery = mod.DELIVERY_DEFAULT.read_text(encoding="utf-8")
    cell = mod.CELL_DEFAULT.read_text(encoding="utf-8")
    assert mod.check(report, delivery, cell, mod.RUNS_BASE) == []
    v = mod.check(report.replace('"cells_scored": 2', '"cells_scored": 3', 1), delivery, cell, mod.RUNS_BASE)
    assert any("cells_scored" in s for s in v)
    v = mod.check(report.replace(mod.C_VACANT_SHA, "0" * 40, 1), delivery, cell, mod.RUNS_BASE)
    assert any("per_arm[C] vacant_sha" in s for s in v)
    v = mod.check(report, delivery, cell, mod.make_tampered_envelope_base(tmp_path, mod.REPORT_DEFAULT.parent))
    assert any("envelope C" in s for s in v)
    v = mod.check(report, delivery.replace('"mode": "evidence"', '"mode": "claim"', 1), cell, mod.RUNS_BASE)
    assert any("delivery mode" in s for s in v)


def test_missing_file_clean_exit(tmp_path):
    p = subprocess.run([sys.executable, str(SCRIPT), "--report", str(tmp_path / "nope.json")],
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 1
    assert "missing file REPORT.json" in p.stdout
    assert "Traceback" not in p.stderr
