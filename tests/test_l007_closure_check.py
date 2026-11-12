"""l007_closure_check 單元測試（對齊 test_e010_closure_check 架構）。

驗收：--selftest 在空 HOME（模擬本機 CI /var/tmp/ci-home）下返回 0、
輸出含 VERDICT: L007_CLOSURE_OK；另直接驗證 check() 與快照 sha256 釘住。
"""

import importlib.util
import os
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO / "ops/audits/l007_closure_check.py"


def _load():
    spec = importlib.util.spec_from_file_location("l007_closure_check", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_selftest_ok_under_empty_home(tmp_path):
    env = {**os.environ, "HOME": str(tmp_path / "empty-home")}
    p = subprocess.run([sys.executable, str(SCRIPT), "--selftest"],
                       capture_output=True, text=True, timeout=120, env=env)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "VERDICT: L007_CLOSURE_OK" in p.stdout


def test_check_and_snapshots(tmp_path):
    mod = _load()
    assert mod.check(mod.L007_DEFAULT, mod.BACKLOG_DEFAULT) == []
    assert mod.check_snapshot(mod.L007_DEFAULT, mod.L007_SHA256) == []
    assert mod.check_snapshot(mod.BACKLOG_DEFAULT, mod.BACKLOG_SHA256) == []
    f = tmp_path / "tampered.md"
    f.write_text("tampered\n", encoding="utf-8")
    assert any("sha256 drift" in s for s in mod.check_snapshot(f, mod.L007_SHA256))
