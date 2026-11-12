"""L008 放大率預註冊前置量具單元測試（票 P20261112_0723-2；0 model calls）。
驗收：--selftest 返回 0、輸出含 VERDICT: L008_PRECHECK_OK、3 個負控制全部生效；
另驗證 repo 快照 ops/loop/L008.md 在案且記錄先驗兩點／三態表／不池化句。
"""

import importlib.util
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
PRE = REPO / "ops/audits/l008_precheck.py"
SNAP = REPO / "ops/loop/L008.md"


def _load():
    spec = importlib.util.spec_from_file_location("l008_precheck_mod", PRE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_selftest_exit0_and_verdict():
    r = subprocess.run([sys.executable, str(PRE), "--selftest"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "VERDICT: L008_PRECHECK_OK" in r.stdout


def test_three_negative_controls_active():
    m = _load()
    assert m.eval_l008_amplification(6.0, 10.0, -24.0, -3.5, 0.01)[0] == "REVERSED"
    assert m.eval_l008_amplification(12.0, 10.0, -4.0, 8.0, 0.42)[0] == "FLAT"
    pts = [{"run": "R460R", "use": "motivation"}, {"run": "R532", "use": "motivation"}]
    assert m.check_nonpooling(dict(points=pts, pooled_n=956, pooled_delta=9.13)), "池化合併大 n 必報違規"
    assert not m.check_nonpooling({"points": pts})


def test_l008_snapshot_recorded_in_repo():
    t = SNAP.read_text(encoding="utf-8")
    for tok in ("R460R", "18.33", "R532", "7.89", "AMPLIFIED", "FLAT", "REVERSED", "不池化"):
        assert tok in t, tok
