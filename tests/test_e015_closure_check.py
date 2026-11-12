import importlib.util
import os
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO / "ops/audits/e015_closure_check.py"


def _selftest(tmp_path=None):
    env = {**os.environ}
    if tmp_path is not None:
        env["HOME"] = str(tmp_path / "empty-home")  # r1484 CI-home 根因回歸護欄：缺省路徑不得靠 Path.home()
    return subprocess.run([sys.executable, str(SCRIPT), "--selftest"],
                          capture_output=True, text=True, timeout=180, env=env)


def test_selftest_ok(tmp_path):
    p = _selftest(tmp_path)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "VERDICT: E015_CLOSURE_OK" in p.stdout
    assert "negative control FAIL" not in p.stdout
    assert "positive control OK" in p.stdout


def test_check_detects_tamper():
    spec = importlib.util.spec_from_file_location("e015_closure_check", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    report = mod.VERDICT_DEFAULT.read_text(encoding="utf-8")
    packet = mod.PACKET_DEFAULT.read_text(encoding="utf-8")
    backlog = mod.BACKLOG_DEFAULT.read_text(encoding="utf-8")
    assert mod.check(report, packet, backlog) == []
    v = mod.check(report.replace('"state": "NOT_BETTER_THAN_RANDOM"', '"state": "EFFECTIVE"'), packet, backlog)
    assert any("VERDICT state must be NOT_BETTER_THAN_RANDOM" in s for s in v)
    v2 = mod.check(report, packet, backlog.replace("- [x] **發射 Phase 1（round 900", "- [ ] **發射 Phase 1（round 900"))
    assert any("Backlog missing checked launch line" in s for s in v2)


def test_plain_mode_ok():
    p = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, timeout=180)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "VERDICT: E015_CLOSURE_OK" in p.stdout
    assert "VIOLATION" not in p.stdout
