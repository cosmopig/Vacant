"""e015_closure_check 單元測試（票 P20261112_1136-1）。

驗收：--selftest 返回 0、輸出含 VERDICT: E015_CLOSURE_OK、4 個負控制全數生效（無 FAIL 行）；
另驗證 check() 對 state 篡改／取消勾選必報違規；HOME 指向空目錄（模擬 CI-home）也須綠。
"""

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
    assert mod.check(report, packet, backlog, mod.VERDICT_DEFAULT) == []
    # n1: state tamper
    v = mod.check(report.replace('"state": "NOT_BETTER_THAN_RANDOM"', '"state": "EFFECTIVE"'), 
                   packet, backlog, mod.VERDICT_DEFAULT)
    assert any("state=EFFECTIVE != NOT_BETTER_THAN_RANDOM" in s for s in v)
    # n2: Y tamper (Y should be 7)
    v = mod.check(report.replace('"Y": 7', '"Y": 13'), packet, backlog, mod.VERDICT_DEFAULT)
    assert any("Y=13 != 7" in s for s in v)
    # n3: BACKLOG uncheck
    v = mod.check(report, packet, backlog.replace("- [x] **發射 Phase 1", "- [ ] **發射 Phase 1"), 
                   mod.VERDICT_DEFAULT)
    assert any("未勾選 [x]" in s for s in v)
    # n4: BACKLOG delete NOT_BETTER_THAN_RANDOM
    v = mod.check(report, packet, backlog.replace("NOT_BETTER_THAN_RANDOM", ""), 
                   mod.VERDICT_DEFAULT)
    assert any("缺結案註記" in s for s in v)


def test_plain_mode_ok():
    p = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, timeout=180)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "VIOLATION" not in p.stdout
