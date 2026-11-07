"""r1169（2026-11-07）：交付前審查重做的守衛測試。

交付前審查記錄：r1168/r1168-redo 的驗證聲明依賴的四個點名檔
（~/dev/ops/loop/NOW.md、ops/audits/effects_20261105_summary.json、
tests/test_reqloop_repair.py、vacant_network/reqloop/repair.py）
在記錄步驟中未被開啟。r1169 把重做固化成一條指令：
~/dev/ops/audits/r1169_review_redo_check_20261107.py —— 四個檔逐一開啟
（opened 才有資格 ok），再核對 r1168 記錄的每個可偽證聲明。

本測試斷言該指令 RC 0、四項全 ok、關鍵數字與 r1168-redo 記錄一致
（50 格；policy30 7/10・6/10；once20 7/10・4/10；local 分歧 5 格皆舊
checker、current 50/50；dab_055-pi-C-localized 三態 false→true/true；
repair selftest 13/13；test_reqloop_repair 全綠且 399f68b6 測試在位）。
腳本在 ~/dev/ops（本機審計證據）；若缺席（CI 他主機）則 skip，不視為失敗。
若 repair.py 被回復（缺 _restore_kv_keys_from_draft／detect_crash_giveup）
或 summary 數字被改，本測試即紅。零模型呼叫、離線。
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys


def test_r1169_review_redo_check_all_named_files_opened_and_claims_held():
    import pytest

    script = pathlib.Path.home() / "dev" / "ops" / "audits" / "r1169_review_redo_check_20261107.py"
    if not script.is_file():
        pytest.skip("r1169 重做檢查腳本不在本機（~/dev/ops/audits），無法交叉驗證")
    r = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True, timeout=900,
    )
    out = r.stdout + r.stderr
    assert r.returncode == 0, f"RC={r.returncode}\n{out[-2000:]}"
    assert "OVERALL: PASS (4/4 items" in out, out[-2000:]

    ev = json.loads(
        (script.with_suffix(".json")).read_text(encoding="utf-8")
    )
    assert ev["overall"] == "PASS" and ev["n_ok"] == 4
    by_name = {it["name"]: it for it in ev["items"]}
    # 四個點名檔都要被實際開啟（有 sha 才算讀過）
    for name in ("loop_now", "effects_20261105_summary", "repair_py", "test_reqloop_repair"):
        it = by_name[name]
        assert it["checks"]["ok"] is True, f"{name}: {it['checks']}"
        assert len(it["sha256_12"]) == 12, f"{name}: 未見開啟證據（sha 缺失）"

    s = by_name["effects_20261105_summary"]["checks"]
    assert s["total_cells"] == 50
    assert (s["policy30_generic_wrong_to_right"], s["policy30_generic_denominator"]) == (7, 10)
    assert (s["policy30_localized_wrong_to_right"], s["policy30_localized_denominator"]) == (6, 10)
    assert (s["once20_generic_wrong_to_right"], s["once20_generic_denominator"]) == (7, 10)
    assert (s["once20_localized_wrong_to_right"], s["once20_localized_denominator"]) == (4, 10)
    assert s["local_vs_independent_mismatches"] == 5
    assert s["current_code_vs_independent_mismatches"] == 0
    assert s["current_code_matches_total"] == 50
    assert s["dab_055_pi_C_localized"] == {
        "local_all_pass_d38d2eb2": False, "after_independent": True, "current_code_all_pass": True,
    }

    rp = by_name["repair_py"]["checks"]
    assert rp["has_detect_crash_giveup"] and rp["has_restore_kv_keys_from_draft"]
    assert rp["selftest_rc"] == 0 and rp["selftest_line"] is True

    tf = by_name["test_reqloop_repair"]["checks"]
    assert tf["has_kv_preservation_round2_blind_prompt_test"]
    assert tf["has_crash_giveup_test"]
    assert tf["pytest_rc"] == 0 and tf["pytest_passed"] == tf["n_test_functions"]
