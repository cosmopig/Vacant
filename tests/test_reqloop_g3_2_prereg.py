"""G3.2 預註冊驗收（工單 P20261111_1918-2）。

覆蓋：1) 題庫篩選工具 --selftest（子行程、VERDICT 行＋RC 0）；
      2) 假說檔欄位完整性（H0/H1/not_applicable/否決條件/停止規則/預算/人類核准）；
      3) 假說檔選題表 top4 與腳本實際輸出一致且同序（防文檔與工具漂移）。
全離線、0 model calls。
"""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "ops/audits/g3_2_bank_screen.py"
HYP = ROOT / "ops/reqloop/g3_2_candidate_hypothesis.md"
REQUIRED_FIELDS = (
    "H0", "H1", "not_applicable", "否決條件", "停止規則", "預算",
    "人類核准", "0 model calls",
)


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, timeout=120)


def test_screen_selftest_verdict() -> None:
    p = _run(["--selftest"])
    assert p.returncode == 0, p.stdout + p.stderr
    assert "VERDICT: G3_2_SCREEN_SELFTEST_OK" in p.stdout
    assert p.stdout.count("PASS ") >= 8, p.stdout


def test_hypothesis_file_fields() -> None:
    text = HYP.read_text(encoding="utf-8")
    missing = [f for f in REQUIRED_FIELDS if f not in text]
    assert not missing, f"假說檔缺欄位: {missing}"


def test_hypothesis_top4_matches_script_output() -> None:
    p = _run([])
    assert p.returncode == 0, p.stdout + p.stderr
    top4 = json.loads(p.stdout)["top4"]
    text = HYP.read_text(encoding="utf-8")
    pos = -1
    for tid in top4:
        m = re.search(rf"^\|\s*\d+\s*\|\s*{tid}\s*\|", text, re.M)
        assert m, f"top4 {tid} 不在假說檔選題表"
        assert m.start() > pos, f"選題表順序與腳本 top4 不一致（{tid}）"
        pos = m.start()


def test_top4_in_required_fields() -> None:
    p = _run([])
    top4 = json.loads(p.stdout)["top4"]
    text = HYP.read_text(encoding="utf-8")
    for tid in top4:
        assert tid in text, f"假說檔缺選題 {tid}"
