"""r1169（2026-11-07）：交付前審查重做的守衛測試（argon 20261107_0724 修正版）。

交付前審查記錄：r1168/r1168-redo 的驗證聲明依賴的四個點名檔
（~/dev/ops/loop/NOW.md、ops/audits/effects_20261105_summary.json、
tests/test_reqloop_repair.py、vacant_network/reqloop/repair.py）
在記錄步驟中未被開啟。r1169 新增測試原本直接呼叫
`~/dev/ops/audits/r1169_review_redo_check_20261107.py`，但未設定 `VACANT_REPO`
（永遠測 `/home/user1/dev/Vacant` 而非受測 worktree），且腳本硬寫
`REPO / ".venv/bin/python"`（在無 `.venv` 的 worktree 拋 FileNotFoundError），
並在單元測試內重覆寫入共用 JSON 檔、對可變 `NOW.md` 做即時斷言、及在 pytest 內
再啟動整個 `tests/test_reqloop_repair.py` 子行程。

修正後：
1. 直接開啟並 SHA-256 驗證**當前受測 checkout**（`REPO_ROOT`）的三個入庫檔案
   （`ops/audits/effects_20261105_summary.json`、`vacant_network/reqloop/repair.py`、
   `tests/test_reqloop_repair.py`），並以當前 `sys.executable` + `PYTHONPATH=REPO_ROOT`
   執行 `vacant_network.reqloop.repair --selftest`（不依賴 `.venv/bin/python`）。
2. 若本機存在 `~/dev/ops/audits/r1169_review_redo_check_20261107.json` 離線審計證據，
   以唯讀方式核對其四項 `checks["ok"]` 與 `sha256_12` 記錄，不覆寫共用審計檔。
3. 附負控制測試：證明在無 `.venv` 的受測目錄中一旦篡改 `repair.py`、`summary.json`
   或 `test_reqloop_repair.py`，守衛立即變紅。
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _open_with_sha12(path: pathlib.Path) -> tuple[str, str]:
    assert path.is_file(), f"點名檔不存在: {path}"
    raw = path.read_bytes()
    sha12 = hashlib.sha256(raw).hexdigest()[:12]
    assert len(sha12) == 12
    return raw.decode("utf-8"), sha12


def _verify_r1169_repo_claims(
    repo_root: pathlib.Path,
    *,
    run_selftest: bool = True,
) -> dict[str, dict[str, object]]:
    # (1) ops/audits/effects_20261105_summary.json
    summary_path = repo_root / "ops" / "audits" / "effects_20261105_summary.json"
    summary_txt, summary_sha = _open_with_sha12(summary_path)
    d = json.loads(summary_txt)

    def _arm(phase: str, a: str) -> dict:
        return d["phases"][phase]["per_arm"][a]

    pol_g, pol_l = _arm("policy30", "generic"), _arm("policy30", "localized")
    onc_g, onc_l = _arm("feedback_once20", "generic"), _arm("feedback_once20", "localized")
    cells_detail = d["phases"]["policy30"]["cells_detail"]
    dab055 = next(
        (
            c for c in cells_detail
            if c.get("arm") == "localized" and "dab_055-pi-C" in json.dumps(c, ensure_ascii=False)
        ),
        None,
    )
    local_mm = (
        len(d["phases"]["policy30"]["local_vs_independent_mismatches"])
        + len(d["phases"]["feedback_once20"]["local_vs_independent_mismatches"])
    )
    cur_mm = (
        len(d["phases"]["policy30"]["current_code_vs_independent_mismatches"])
        + len(d["phases"]["feedback_once20"]["current_code_vs_independent_mismatches"])
    )

    assert d["schema"].startswith("vacant.audit/effects_20261105_summary")
    assert d["snapshot_sha"].startswith("d38d2eb2")
    assert d["total_cells"] == 50
    assert (pol_g["wrong_to_right"], pol_g["cells"] - pol_g["preserved_good"]) == (7, 10)
    assert (pol_l["wrong_to_right"], pol_l["cells"] - pol_l["preserved_good"]) == (6, 10)
    assert (onc_g["wrong_to_right"], onc_g["cells"] - onc_g["preserved_good"]) == (7, 10)
    assert (onc_l["wrong_to_right"], onc_l["cells"] - onc_l["preserved_good"]) == (4, 10)
    assert local_mm == 5 and cur_mm == 0
    assert d["current_code_matches_total"] == 50
    assert dab055 is not None, "找不到 policy30 dab_055-pi-C localized 格"
    assert {
        "local_all_pass_d38d2eb2": dab055.get("local_all_pass_d38d2eb2"),
        "after_independent": dab055.get("after_independent"),
        "current_code_all_pass": dab055.get("current_code_all_pass"),
    } == {
        "local_all_pass_d38d2eb2": False,
        "after_independent": True,
        "current_code_all_pass": True,
    }

    # (2) vacant_network/reqloop/repair.py
    repair_path = repo_root / "vacant_network" / "reqloop" / "repair.py"
    repair_txt, repair_sha = _open_with_sha12(repair_path)
    assert "def detect_crash_giveup(" in repair_txt
    assert "def _restore_kv_keys_from_draft(" in repair_txt

    if run_selftest:
        env = dict(os.environ)
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{repo_root}{os.pathsep}{existing_pp}" if existing_pp else str(repo_root)
        )
        r = subprocess.run(
            [sys.executable, "-m", "vacant_network.reqloop.repair", "--selftest"],
            cwd=str(repo_root),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        out = (r.stdout or "") + (r.stderr or "")
        assert r.returncode == 0, f"repair --selftest 失敗 (rc={r.returncode}):\n{out}"
        assert "SELFTEST: 13/13 PASS" in out, out

    # (3) tests/test_reqloop_repair.py
    test_repair_path = repo_root / "tests" / "test_reqloop_repair.py"
    test_repair_txt, test_repair_sha = _open_with_sha12(test_repair_path)
    assert "test_single_deliverable_kv_preservation_round2_restores_mutated_keys_and_avoids_blind_prompt" in test_repair_txt
    assert "test_detect_crash_giveup_flags_crashed_giveup" in test_repair_txt
    n_test_funcs = len(re.findall(r"^def test_", test_repair_txt, flags=re.M))
    assert n_test_funcs >= 90

    return {
        "effects_20261105_summary": {"sha256_12": summary_sha, "total_cells": d["total_cells"]},
        "repair_py": {"sha256_12": repair_sha},
        "test_reqloop_repair": {"sha256_12": test_repair_sha, "n_test_functions": n_test_funcs},
    }


def test_r1169_review_redo_check_all_named_files_opened_and_claims_held():
    res = _verify_r1169_repo_claims(REPO_ROOT, run_selftest=True)
    for name in ("effects_20261105_summary", "repair_py", "test_reqloop_repair"):
        assert len(str(res[name]["sha256_12"])) == 12

    # 若本機存在 r1169 離線審計證據 JSON，唯讀核對其四項開啟記錄（不重跑腳本覆寫共用檔）
    audit_json = pathlib.Path.home() / "dev" / "ops" / "audits" / "r1169_review_redo_check_20261107.json"
    if audit_json.is_file():
        ev = json.loads(audit_json.read_text(encoding="utf-8"))
        assert ev["overall"] == "PASS" and ev["n_ok"] == 4
        by_name = {it["name"]: it for it in ev["items"]}
        for name in ("loop_now", "effects_20261105_summary", "repair_py", "test_reqloop_repair"):
            it = by_name[name]
            assert it["checks"]["ok"] is True
            assert len(it["sha256_12"]) == 12


def test_r1169_guard_catches_tampering_in_checkout_without_venv(tmp_path: pathlib.Path):
    """負控制：即使受測 checkout 沒有 `.venv/bin/python`（如 git worktree），
    守衛仍必須對該 checkout 的實際檔案生效，一旦篡改立即失敗。"""
    for rel in (
        pathlib.Path("ops/audits/effects_20261105_summary.json"),
        pathlib.Path("vacant_network/reqloop/repair.py"),
        pathlib.Path("tests/test_reqloop_repair.py"),
    ):
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / rel, dst)

    assert not (tmp_path / ".venv" / "bin" / "python").exists()
    _verify_r1169_repo_claims(tmp_path, run_selftest=False)

    # 1. 篡改 repair.py（移除 _restore_kv_keys_from_draft）→ 必紅
    repair_copy = tmp_path / "vacant_network" / "reqloop" / "repair.py"
    orig_repair = repair_copy.read_text(encoding="utf-8")
    repair_copy.write_text(
        orig_repair.replace("def _restore_kv_keys_from_draft(", "def _removed_helper("),
        encoding="utf-8",
    )
    with pytest.raises(AssertionError):
        _verify_r1169_repo_claims(tmp_path, run_selftest=False)
    repair_copy.write_text(orig_repair, encoding="utf-8")

    # 2. 篡改 effects_20261105_summary.json 數字 → 必紅
    summary_copy = tmp_path / "ops" / "audits" / "effects_20261105_summary.json"
    orig_summary = summary_copy.read_text(encoding="utf-8")
    bad_summary = json.loads(orig_summary)
    bad_summary["phases"]["policy30"]["per_arm"]["localized"]["wrong_to_right"] = 9
    summary_copy.write_text(json.dumps(bad_summary), encoding="utf-8")
    with pytest.raises(AssertionError):
        _verify_r1169_repo_claims(tmp_path, run_selftest=False)
    summary_copy.write_text(orig_summary, encoding="utf-8")

    # 3. 篡改 test_reqloop_repair.py（移除 399f68b6 回歸測試）→ 必紅
    test_copy = tmp_path / "tests" / "test_reqloop_repair.py"
    orig_test = test_copy.read_text(encoding="utf-8")
    test_copy.write_text(
        orig_test.replace(
            "test_single_deliverable_kv_preservation_round2_restores_mutated_keys_and_avoids_blind_prompt",
            "_removed_test",
        ),
        encoding="utf-8",
    )
    with pytest.raises(AssertionError):
        _verify_r1169_repo_claims(tmp_path, run_selftest=False)
