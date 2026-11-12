"""e014_closure_check 單元測試（票 P20261112_1125-1；0 model calls、只讀）。
三項：--selftest 正控制＋4 負控制全綠；4 負控制各自必紅；空目錄 CI 模擬（路徑注入、
不依賴 Path.home()）依然全綠。"""
import importlib.util
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO / "ops/audits/e014_closure_check.py"
REPORT = pathlib.Path("/srv/vlab/runs/e014_dabstep_block/REPORT.json")
PACKET = REPO / "ops/vlab/packets/e014_dabstep_block.md"
BACKLOG = REPO / "ops/BACKLOG.md"

def _mod():
    spec = importlib.util.spec_from_file_location("e014_closure_check", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def test_selftest_ok():
    r = subprocess.run([sys.executable, str(SCRIPT), "--selftest"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "VERDICT: E014_CLOSURE_OK" in r.stdout

def test_four_negative_controls_red():
    m = _mod()
    r = REPORT.read_text(encoding="utf-8")
    p = PACKET.read_text(encoding="utf-8")
    b = BACKLOG.read_text(encoding="utf-8")
    v1 = m.check(r.replace('"pass": 13', '"pass": 12', 1), p, b)
    assert v1 and any("pass" in s for s in v1)
    v2 = m.check(r.replace('"mcnemar_p_two_sided": 1.0', '"mcnemar_p_two_sided": 0.05', 1), p, b)
    assert v2 and any("mcnemar" in s for s in v2)
    v3 = m.check(r, p, b.replace("- [x] **e014 完賽（round 894 裁決", "- [ ] **e014 完賽（round 894 裁決", 1))
    assert v3 and any("未勾選 [x]" in s for s in v3)
    v4 = m.check(r, p, b.replace("H1（blocking>evidence）在 DABStep 被否", "H1（blocking>evidence）待裁決", 1))
    assert v4 and any("裁決註記" in s for s in v4)

def test_ci_home_empty_dir_green(tmp_path):
    (tmp_path / "r.json").write_bytes(REPORT.read_bytes())
    (tmp_path / "p.md").write_bytes(PACKET.read_bytes())
    (tmp_path / "b.md").write_bytes(BACKLOG.read_bytes())
    r = subprocess.run([sys.executable, str(SCRIPT), "--report", str(tmp_path / "r.json"),
                        "--packet", str(tmp_path / "p.md"), "--backlog", str(tmp_path / "b.md"),
                        "--selftest"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "VERDICT: E014_CLOSURE_OK" in r.stdout

def test_missing_file_clean_red():
    r = subprocess.run([sys.executable, str(SCRIPT), "--report", "/nonexistent/report.json", "--selftest"],
                       capture_output=True, text=True)
    assert r.returncode == 1 and "missing file" in r.stdout and "Traceback" not in r.stderr
