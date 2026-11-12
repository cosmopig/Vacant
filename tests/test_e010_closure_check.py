"""e010_closure_check 單元測試（票 P20261112_0320-1）。

驗收：--selftest 返回 0、輸出含 VERDICT: E010_CLOSURE_OK；
另直接驗證 check() 對篡改（byte 數）必報違規。
"""

import importlib.util
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO / "ops/audits/e010_closure_check.py"


def _load():
    spec = importlib.util.spec_from_file_location("e010_closure_check", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_selftest_ok():
    p = subprocess.run([sys.executable, str(SCRIPT), "--selftest"],
                       capture_output=True, text=True, timeout=120)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "VERDICT: E010_CLOSURE_OK" in p.stdout


def test_check_detects_byte_tamper():
    mod = _load()
    cell = mod.CELL_DEFAULT.read_text(encoding="utf-8")
    packet = mod.PACKET_DEFAULT.read_text(encoding="utf-8")
    backlog = mod.BACKLOG_DEFAULT.read_text(encoding="utf-8")
    assert mod.check(cell, packet, backlog) == []
    v = mod.check(cell.replace('"vacant_home_bytes": 1077331',
                               '"vacant_home_bytes": 999999999', 1), packet, backlog)
    assert any("vacant_home_bytes" in s for s in v)
