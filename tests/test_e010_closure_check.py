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


def test_selftest_ok(tmp_path):
    # r1484（CI 紅燈根因回歸護欄）：HOME 指向空目錄（模擬本機 CI 的 /var/tmp/ci-home）
    # 也須綠——缺省證據路徑不得依賴 PATH/HOME 解析到 ~/dev/ops。
    import os
    env = {**os.environ, "HOME": str(tmp_path / "empty-home")}
    p = subprocess.run([sys.executable, str(SCRIPT), "--selftest"],
                       capture_output=True, text=True, timeout=120, env=env)
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


def test_check_envelope_pass():
    assert _load().check_envelope(_load().RUNS_BASE) == []


def test_snapshots_match_pins():
    mod = _load()
    assert mod.check_snapshot(mod.PACKET_DEFAULT, mod.PACKET_SHA256) == []
    assert mod.check_snapshot(mod.BACKLOG_DEFAULT, mod.BACKLOG_SHA256) == []


def test_snapshot_pin_catches_drift(tmp_path):
    mod = _load()
    f = tmp_path / "tampered.md"
    f.write_text("tampered\n", encoding="utf-8")
    assert any("sha256 drift" in s for s in mod.check_snapshot(f, mod.PACKET_SHA256))
    assert mod.check_snapshot(tmp_path / "nope.md", mod.PACKET_SHA256)  # 缺檔也紅


def test_backlog_snapshot_allows_closing_unrelated_items_but_catches_e010_line_tamper(tmp_path):
    mod = _load()
    text = mod.BACKLOG_DEFAULT.read_text(encoding="utf-8")
    other_closed = text.replace("- [ ] **e004 OpenCode", "- [x] **e004 OpenCode", 1)
    p_other = tmp_path / "BACKLOG.md"
    p_other.write_text(other_closed, encoding="utf-8")
    assert mod.check_snapshot(p_other, mod.BACKLOG_SHA256) == []
    p_bad = tmp_path / "BACKLOG_bad.md"
    p_bad.write_text(text.replace("1,077,331 B", "9,999,999 B", 1), encoding="utf-8")
    assert any("sha256 drift" in s for s in mod.check_snapshot(p_bad, mod.BACKLOG_SHA256))
