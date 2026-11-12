"""e015 現盤 VERDICT 哨兵單元測試（r1528、票 P20261112_1930-1 重拆件）。
3 測試：空 HOME selftest（正＋3 負控制）／現盤在位時 0 違規（缺位時 UNKNOWN rc=2）／快照 sha 釘住。
"""
import hashlib
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
GUARD = REPO / "ops/audits/e015_live_verdict_check.py"
LIVE = pathlib.Path("/srv/vlab/runs/e015_h_multi_review/VERDICT.json")
SNAP = REPO / "ops/audits/e015_h_multi_review_verdict.json"
SNAP_SHA256 = "d0e2988411ad3aeaf55c044e4e7272ce1bcdf055ed5b2d7c358769cb4d7c2fb9"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GUARD), *args],
                          capture_output=True, text=True, timeout=120)


def test_selftest_green_empty_home(tmp_path):
    env = {"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}
    p = subprocess.run([sys.executable, str(GUARD), "--selftest"],
                       capture_output=True, text=True, timeout=120, env=env)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "VERDICT: E015_LIVE_VERDICT_OK" in p.stdout


def test_live_repaired_or_unknown():
    if not LIVE.is_file():
        # 無 /srv/vlab 環境（CI-home）：哨兵必須報 UNKNOWN（rc=2），嚴禁判 PASS
        p = _run()
        assert p.returncode == 2, p.stdout + p.stderr
        assert "UNKNOWN" in p.stdout
        return
    p = _run()
    assert p.returncode == 0, p.stdout + p.stderr
    assert "0 違規" in p.stdout


def test_snapshot_sha_pinned():
    assert SNAP.is_file()
    assert hashlib.sha256(SNAP.read_bytes()).hexdigest() == SNAP_SHA256
