"""Round 155 — GPT 審查 P0-2：真實任務庫 `*_test.py` 的 CLI e2e。

GPT 審查（`~/dev/ops/GPT_REVIEW_20261028.md` P0-2）的最強剩餘疑問：**有沒有
用任務庫的真實 `*_test.py` 檔**（不是合成檔）走完整收口（suite discovery →
dialect 路由 → unittest driver → 裁決 → 簽收據 → 驗收據）。round 131 的
`tests/test_p02_star_test_discovery.py` 用的是 3 case 的合成 `wordy_test.py`。

本檔用 e001 留存的**真 bank 檔** `bowling_test.py`（31 case，
`class BowlingTest(unittest.TestCase)`，exactly 審查懷疑的形狀）：

- 正控：`bowling_good.py`——依 31 個 case 全數通過而寫（e001 兩臂候選都
  fail，沒有「真實且正確」的候選可用；本地解，PROVENANCE 有記）。
- 負控：`bowling_bad.py`——**真實 agent 在 e001 A 臂失敗過的程式**
  （scorer 記 15/31），逐位元未改。

證據等級與邊界（誠實欄，勿刪）：
1. 這組檔案是 e001 run 留存的 visible test 與 agent 產物，**不是**
   `/srv/eval/staged/` 原件（本機 `Permission denied`，2026-10-28 重驗）。
   「staged 原件本身跑過」仍為 UNKNOWN，只能由有權者跑。
2. `bowling_bad.py` 的 15/31 是 **scorer（隱藏端）** 的計數；本 repo
   driver 在 visible 檔上的計數另記於 `visible_AC.json`，兩者不混用。
3. 兩臂（A／C）的 `bowling_test.py` 逐位元相同 ⇒ 是 bank 檔，非 agent 自寫。

Provenance: `tests/fixtures/p02_real_bank/PROVENANCE.md`
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vacant_network.vrun import acceptance, launcher, verify_receipts
from vacant_network.vrun.sandbox import make_sandbox

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures" / "p02_real_bank"
TEST_FILE = FIX / "bowling_test.py"
GOOD = FIX / "bowling_good.py"
BAD = FIX / "bowling_bad.py"

#: 固定 fixture 的 sha256——任何一個被改動，本組證據的來源聲明就失效。
EXPECTED_SHA = {
    "bowling_test.py": "6b9a80b6835828f575ce0aba66876850f75c59f764014ac509fe1df7e3a9ee20",
    "bowling_bad.py": "fd5dcbe9782103f939271b140c0c4ad91f631844e23c89a4bf612d86643c8dd7",
    "bowling_good.py": "9e92c89c7d0162f98a1b2933848bb66e7fb1b2d61edc6c427e03572c8690da38",
}
CASES = 31
TASK_ID = "pg_bowling_p02_real_bank"


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture()
def bench(tmp_path: Path):
    """`(workspace, suite_dir, run_dir)`；suite 裡只有真 bank 檔 bowling_test.py。"""
    ws, suite, rd = (tmp_path / "ws", tmp_path / "suite", tmp_path / "run")
    for d in (ws, suite, rd):
        d.mkdir()
    shutil.copy(TEST_FILE, suite / "bowling_test.py")
    return ws, suite, rd


def _place_candidate(ws: Path, src: Path) -> None:
    (ws / "bowling.py").write_bytes(src.read_bytes())


# ─────────────────────────────────────────────────────────────────────
# 0. fixture 本身的誠實性
# ─────────────────────────────────────────────────────────────────────

def test_fixture_files_pinned_sha256():
    for name, want in EXPECTED_SHA.items():
        p = FIX / name
        assert p.is_file(), f"missing fixture {p}"
        assert _sha256(p) == want, f"{name} 的 sha256 變了——PROVENANCE 的來源聲明失效"


def test_fixture_is_the_real_star_test_shape():
    """審查懷疑的正是這個形狀：`*_test.py` + unittest 方言。"""
    assert acceptance._is_test_name("bowling_test.py")
    assert not acceptance._is_test_name("test.py")  # 既有 pin，這裡只是對照
    assert acceptance.classify_dialect(TEST_FILE.read_bytes()) == "unittest"
    src = TEST_FILE.read_text(encoding="utf-8")
    assert "unittest.TestCase" in src
    assert "from bowling import" in src and "BowlingGame" in src
    # 真實 bank 檔的來源標記（exercism canonical-data 自動生成）
    assert "exercism/problem-specifications" in src


# ─────────────────────────────────────────────────────────────────────
# 1. 庫層：run_suite 對真 bank 檔的裁決
# ─────────────────────────────────────────────────────────────────────

def _library_run(ws: Path, suite: Path, candidate: Path, tmp_path: Path) -> dict:
    _place_candidate(ws, candidate)
    sandbox, _meta = make_sandbox("none", workdir=tmp_path / "sbx")
    return acceptance.run_suite(
        sandbox, ws, suite, suite="visible",
        task_id=TASK_ID, verify_root=tmp_path / "vroot", timeout_s=30)


def test_library_run_good_candidate_31_of_31(bench, tmp_path):
    ws, suite, _rd = bench
    r = _library_run(ws, suite, GOOD, tmp_path)
    assert r["all_pass"] is True
    assert r["passed"] == CASES and r["total"] == CASES
    cases = r["files"][0]["cases"]
    assert all(c["ok"] for c in cases)
    # 不許把裁決失敗偽裝成 driver/import/protocol 層錯誤（infra void 形狀）
    bad_kinds = {c["kind"] for c in cases} & {"import", "driver_error",
                                               "protocol", "timeout"}
    assert not bad_kinds, bad_kinds
    f = r["files"][0]
    assert f["file"] == "bowling_test.py" and f["complete"] is True
    assert len(f["declared"]) == CASES  # 宣告清單＝31 個 test_ 方法
    d = r["discovery"][0]
    assert (d["role"], d["dialect"], d["executed"]) == ("test", "unittest", True)


def test_library_run_real_failed_candidate_is_explicit_fail(bench, tmp_path):
    ws, suite, _rd = bench
    r = _library_run(ws, suite, BAD, tmp_path)
    assert r["all_pass"] is False
    assert r["total"] == CASES, "31 個 case 都必須被宣告並執行，不許半套"
    assert 0 < r["passed"] < CASES, (
        f"真實候選在 visible 檔上應部分通過（got {r['passed']}/{CASES}）")
    cases = r["files"][0]["cases"]
    assert sum(1 for c in cases if not c["ok"]) == CASES - r["passed"]
    # 每個 case 的裁決都在案；失敗是 assert/exception（真裁決），不是
    # driver/import/protocol（infra void 形狀）
    kinds = {c.get("kind") for c in cases}
    assert "pass" in kinds and ({"assert", "exception"} & kinds)
    assert not (kinds & {"driver_error", "import", "timeout"}), kinds


# ─────────────────────────────────────────────────────────────────────
# 2. CLI 層：`vacant run`（launcher.main）對真 bank 檔的端到端
# ─────────────────────────────────────────────────────────────────────

def _cli_run(ws: Path, suite: Path, rd: Path, candidate: Path,
             vacant_on: bool = True) -> subprocess.CompletedProcess:
    """走**真 CLI**（子行程 + argparse + launcher.main），不繞路。"""
    _place_candidate(ws, candidate)
    argv = [
        sys.executable, "-m", "vacant_network.vrun.launcher",
        "--workspace", str(ws),
        "--run-dir", str(rd),
        "--suite", str(suite),
        "--sandbox", "none",
        "--task-id", TASK_ID,
        "--vacant", "1" if vacant_on else "0",
        "--test-timeout", "30",
        "--json",
        "--",
        sys.executable, "-c", "pass",  # 候選已在 workspace；agent 是 no-op
    ]
    return subprocess.run(argv, capture_output=True, text=True,
                          timeout=180, check=False)


def _receipts(rd: Path) -> dict:
    """`verify_run` 的判決，收據鏈必須逐條驗得過。"""
    out = verify_receipts.verify_run(rd)
    assert out, "run 目錄裡沒有收據——signed receipt 缺失"
    return out


def test_cli_real_bank_positive_accepted_with_signed_receipt(bench):
    ws, suite, rd = bench
    p = _cli_run(ws, suite, rd, GOOD)
    assert p.returncode == launcher.EXIT_ACCEPTED, (
        f"exit={p.returncode}\nstdout={p.stdout[-1500:]}\nstderr={p.stderr[-1500:]}")
    summary = json.loads(p.stdout)
    assert summary["accepted"] is True and summary["refused"] is False
    assert summary["visible_passed"] == CASES
    assert summary["visible_total"] == CASES
    assert summary["stop_reason"] == "visible_pass"
    # 收據落盤且驗得過（A 級：attested=True 或至少無 failure）
    assert (rd / "rows.jsonl").exists()
    assert (rd / "receipts_RUN-ON.ndjson").exists()
    assert (rd / "receipts_RUN-ON.pub.json").exists()
    verdict = _receipts(rd)
    assert all(not rec.get("failures") for rec in verdict), verdict


def test_cli_real_bank_negative_refused_with_signed_receipt(bench):
    ws, suite, rd = bench
    p = _cli_run(ws, suite, rd, BAD)
    assert p.returncode == launcher.EXIT_REFUSED, (
        f"exit={p.returncode}\nstdout={p.stdout[-1500:]}\nstderr={p.stderr[-1500:]}")
    summary = json.loads(p.stdout)
    assert summary["refused"] is True and summary["accepted"] is False
    assert summary["stop_reason"] == "visible_fail", (
        "必須是**顯式裁決失敗**，不是 no_suite 假成功、不是 infra void")
    assert summary["visible_total"] == CASES
    assert 0 < summary["visible_passed"] < CASES
    # 負控的收據**也要簽得下去且驗得過**——拒絕本身是 accountable 的
    assert (rd / "rows.jsonl").exists()
    assert (rd / "receipts_RUN-ON.ndjson").exists()
    verdict = _receipts(rd)
    assert all(not rec.get("failures") for rec in verdict), verdict


def test_cli_real_bank_off_arm_is_ungated_tee(bench):
    """OFF 臂（vacant 0）＝純 tee：不驗收、不簽收據、不拒交（launcher 設計）。

    這把「門」和「收據」兩條軸分開驗：正控的裁決只在 ON 臂出；OFF 臂
    必須是 `ungated`／`accepted=None`，且**沒有**收據——OFF 臂出現
    裁決或收據都是漂移。
    """
    ws, suite, rd = bench
    p = _cli_run(ws, suite, rd, GOOD, vacant_on=False)
    assert p.returncode == launcher.EXIT_ACCEPTED, p.stdout[-1500:]
    summary = json.loads(p.stdout)
    assert summary["arm"] == launcher.ARM_OFF
    assert summary["stop_reason"] == "ungated"
    assert summary["accepted"] is None, "OFF 臂不裁決：accepted 必須是 None"
    assert not list(rd.glob("receipts_*.ndjson")), "OFF 臂不該有收據"


def test_cli_real_bank_suite_detection_via_test_files(bench):
    """launcher 的 `has_suite` 走 `acceptance.test_files`（`_is_test_name`
    單一來源）——真 bank 檔 `bowling_test.py` 必須被當成「有套件」。"""
    ws, suite, _rd = bench
    got = [p.name for p in acceptance.test_files(suite)]
    assert got == ["bowling_test.py"]
    # 對照：只有不合命名的檔時＝無套件（fail-closed，round 131 的 pin）
    empty = ws / "empty_suite"
    empty.mkdir()
    (empty / "notes.py").write_text("X = 1\n", encoding="utf-8")
    assert acceptance.test_files(empty) == []
