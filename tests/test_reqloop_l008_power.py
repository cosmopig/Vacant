"""L008 檢定力量具單元測試（票 P20261112_1125-2；0 model calls、純本地離線）。
三項：--selftest 綠且 VERDICT；3 負控制各自必紅；報告 JSON 生成且數值在 [0,1]。"""
import copy
import importlib.util
import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO / "ops/audits/l008_power_analysis.py"
REPORT = REPO / "ops/audits/l008_power_report.json"


def _mod():
    spec = importlib.util.spec_from_file_location("l008_power_analysis", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_selftest_ok_and_report_range():
    r = subprocess.run([sys.executable, str(SCRIPT), "--selftest"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "VERDICT: L008_POWER_OK" in r.stdout
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    assert rep["alpha"] == 0.05 and rep["phase1_n"] == 60 and rep["generated_at"]
    assert len(rep["grid"]) == 12 and len(rep["mde_summary"]) == 12
    for cell in rep["grid"]:
        assert 0.0 <= cell["power"] <= 1.0
    for cell in rep["mde_summary"]:
        assert isinstance(cell["n_required"], int) and cell["n_required"] >= 1


def test_three_negative_controls_red():
    m = _mod()
    rep = m.build_report()
    t1 = copy.deepcopy(rep)  # 負控 1：篡改報告 power 必被抓
    t1["grid"][0]["power"] = round(t1["grid"][0]["power"] + 0.01, 6)
    assert m.verify_report(t1), "power 篡改未抓出"
    try:  # 負控 2：ψ=0.5 達 80% power 必 raise ValueError
        m.mcnemar_n_required(0.25, 0.5, alpha=0.05, power=0.80)
        raise AssertionError("ψ=0.5 未 raise ValueError")
    except ValueError:
        pass
    t3 = copy.deepcopy(rep)  # 負控 3：篡改 phase1_n 必報違規
    t3["phase1_n"] = 59
    assert m.verify_report(t3), "phase1_n 篡改未報違規"
