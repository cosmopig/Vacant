"""e016_closure_check 單元測試（票 P20261112_0923-2；對齊 test_l007_closure_check 架構）。

驗收：--selftest 在空 HOME（模擬本機 CI /var/tmp/ci-home）下返回 0、
輸出含 VERDICT: E016_CLOSURE_OK；另直接驗證 check() 正控制與 4 類篡改必紅、
快照 sha256 釘住（BACKLOG 共用檔接受目標行 sha256 相符）。
"""

import importlib.util
import os
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO / "ops/audits/e016_closure_check.py"


def _load():
    spec = importlib.util.spec_from_file_location("e016_closure_check", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_selftest_ok_under_empty_home(tmp_path):
    env = {**os.environ, "HOME": str(tmp_path / "empty-home")}
    p = subprocess.run([sys.executable, str(SCRIPT), "--selftest"],
                       capture_output=True, text=True, timeout=120, env=env)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "VERDICT: E016_CLOSURE_OK" in p.stdout


def test_check_positive_and_four_negatives():
    mod = _load()
    packet = mod.PACKET_DEFAULT.read_text(encoding="utf-8")
    verdict = mod.VERDICT_DEFAULT.read_text(encoding="utf-8")
    backlog = mod.BACKLOG_DEFAULT.read_text(encoding="utf-8")
    assert mod.check(packet, verdict, backlog) == []
    v = mod.check(packet, verdict.replace('"state": "NO_MECHANISM"', '"state": "MECHANISM_CONFIRMED"', 1), backlog)
    assert any("state" in s for s in v)
    v = mod.check(packet, verdict.replace('"pass": 18', '"pass": 19', 1), backlog)
    assert any("pass" in s for s in v)
    v = mod.check(packet, verdict, backlog.replace("- [x] **完賽後（round 906+）**", "- [ ] **完賽後（round 906+）**", 1))
    assert any("未勾選" in s for s in v)
    v = mod.check(packet, verdict, backlog.replace("裁決＝**NO_MECHANISM**", "裁決＝**REOPENED**", 1))
    assert any("結案註記" in s for s in v)


def test_snapshot_pins(tmp_path):
    mod = _load()
    assert mod.check_snapshot(mod.PACKET_DEFAULT, mod.PACKET_SHA256) == []
    assert mod.check_snapshot(mod.VERDICT_DEFAULT, mod.VERDICT_SHA256) == []
    assert mod.check_snapshot(mod.BACKLOG_DEFAULT, mod.BACKLOG_SHA256) == []
    f = tmp_path / "tampered.json"
    f.write_text("tampered\n", encoding="utf-8")
    assert any("sha256 drift" in s for s in mod.check_snapshot(f, mod.VERDICT_SHA256))
    # BACKLOG 共用檔：他項被勾選不影響 e016 目標行（行 sha 仍相符）；目標行被改必紅
    text = mod.BACKLOG_DEFAULT.read_text(encoding="utf-8")
    other = text.replace("- [ ] **e004 OpenCode", "- [x] **e004 OpenCode", 1)
    assert other != text
    f = tmp_path / "BACKLOG.md"
    f.write_text(other, encoding="utf-8")
    assert mod.check_snapshot(f, mod.BACKLOG_SHA256) == []
    f.write_text(other.replace("裁決＝**NO_MECHANISM**", "裁決＝**REOPENED**", 1), encoding="utf-8")
    assert any("sha256 drift" in s for s in mod.check_snapshot(f, mod.BACKLOG_SHA256))
