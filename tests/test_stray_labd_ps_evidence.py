"""stray labd 審計工具測試（ticket R20261111_1152-2；2026-11-11 r1444 重做：全部測試皆實際斷言，無 pass 空轉）。

覆蓋：
- is_labd 正/負控制（真 labd cmdline vs 僅 prompt 文字含 "labd.py" 的進程）
- audit 正控制（shell 父、VACANT_PI_* 父環境、多實例 → VIOLATION）
- audit 負控制（受管單一實例 → OK）
- --selftest 子程序：退出碼 0、VERDICT 行、每組控制 PASS（舊版兩分支皆 OK 的空轉已除）
- scan_repo_shell_scripts：無守護 labd 啟動點 → finding；有 flock 守護 → 無
"""
import os
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.audits.stray_labd_ps_evidence import (  # noqa: E402
    P, audit, is_labd, scan_repo_shell_scripts)

SCRIPT = ROOT / "ops" / "audits" / "stray_labd_ps_evidence.py"


def test_is_labd_positive():
    assert is_labd(["python3", "/srv/vlab/bin/labd.py"]) is True
    assert is_labd(["/usr/bin/python3", "/srv/vlab/bin/labd.py", "--queue", "x"]) is True


def test_is_labd_negative_prompt_text():
    # pi session 的 argv 含工單文字「labd.py」但不以 labd.py 參數結尾 → 不算
    assert is_labd(["pi", "-p", "工單提到 labd.py 及其父進程審計"]) is False
    assert is_labd(["grep", "labd.py", "file.txt"]) is False


def test_managed_single_ok():
    res = audit([P()])
    assert res["status"] == "OK"
    assert res["instances"] == 1
    assert res["violations"] == []


def test_shell_parent_violation():
    res = audit([P(ppid=7, parent_cmdline=["/bin/bash", "-c", "x"])])
    assert res["status"] == "VIOLATION"
    assert res["violations"][0]["type"] == "stray_shell_parent"
    assert res["violations"][0]["parent_pid"] == 7


def test_pi_env_parent_violation():
    res = audit([P(ppid=9, parent_cmdline=["/usr/bin/python3", "pi"],
                   parent_env={"VACANT_PI_PARENT": "true", "HOME": "/x"})])
    assert res["status"] == "VIOLATION"
    v = res["violations"][0]
    assert v["type"] == "stray_pi_env_parent"
    assert v["vars"] == ["VACANT_PI_PARENT"]


def test_multiple_instances_violation():
    res = audit([P(pid=1), P(pid=2)])
    assert res["status"] == "VIOLATION"
    assert res["violations"][0]["type"] == "multiple_instances"
    assert res["violations"][0]["pids"] == [1, 2]


def test_selftest_subprocess_all_controls_pass():
    out = subprocess.run([sys.executable, str(SCRIPT), "--selftest"],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "VERDICT: STRAY_LABD_AUDIT_OK" in out.stdout
    for name in ("A", "B", "C", "D", "E_matcher_pos", "E_matcher_neg"):
        line = next(l for l in out.stdout.splitlines() if l.startswith(f"control {name}"))
        assert line.endswith("PASS"), line
    assert "FAIL" not in out.stdout


def test_scan_repo_shell_scripts_guarded_and_unguarded(tmp_path):
    (tmp_path / "bad.sh").write_text("nohup python3 /srv/vlab/bin/labd.py &\n", encoding="utf-8")
    (tmp_path / "good.sh").write_text("flock /tmp/labd.pid python3 /srv/vlab/bin/labd.py\n", encoding="utf-8")
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / "old.sh").write_text("python3 /srv/vlab/bin/labd.py\n", encoding="utf-8")
    findings = scan_repo_shell_scripts(str(tmp_path))
    files = [f["file"] for f in findings]
    assert any(f.endswith("bad.sh") for f in files)
    assert not any(f.endswith("good.sh") for f in files)
    assert not any("old.sh" in f for f in files)  # runs/ 歷史實驗腳本排除
