"""e013 成本重算量具（ops/audits/e013_recompute.py）單元測試。

驗收口徑（票 P20261112_0748-1）：--selftest 回 0、輸出含
VERDICT: E013_RECOMPUTE_OK、兩負控制全數生效（缺 metrics 標記異常而非 0.0
合格；pass=None infra 格嚴排除分母）。
"""
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "ops" / "audits" / "e013_recompute.py"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, timeout=120,
    )


def test_selftest_exit_zero_and_verdict():
    r = _run("--selftest")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "VERDICT: E013_RECOMPUTE_OK" in r.stdout


def test_negative_controls_all_active():
    r = _run("--selftest")
    out = r.stdout
    assert "[FAIL]" not in out, out
    assert "[PASS] negative1: missing metrics isolated" in out, out
    assert "[PASS] negative2: infra pass=None excluded" in out, out


def test_default_path_runs_and_reports_both_arms():
    r = _run()
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Arm A" in r.stdout and "Arm C" in r.stdout
