"""D1 離線 claim 重播的 pytest（零模型）。

跑法：python3 -m pytest tests/test_replay_claims.py -v
"""
import importlib.util
import json
import pathlib
import tempfile
from unittest.mock import patch

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("replay_claims", REPO / "ops/reqloop/extract/replay_claims.py")
rc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rc)

UT, INPUTS = rc.load_task("g3_2", "dab_725")
KEYS = [{"key": "mean1", "type": "number"}]


def test_selftest_all_controls_pass():
    assert rc.selftest() == 0


def test_negative_controls_non_deterministic():
    # deliverable = 輸入 CSV 路徑
    ok, reason = rc.judge_claim("answer_kv", "data/auto-mpg.csv", {"keys": KEYS}, UT, INPUTS)
    assert not ok and reason == "deliverable_is_input_file"
    # deliverable = 不存在的檔名
    ok, reason = rc.judge_claim("answer_kv", "no_such_output_9x7z.csv", {"keys": KEYS}, UT, INPUTS)
    assert not ok and reason.startswith("deliverable_not_in_request")
    # verifier 不在白名單
    ok, reason = rc.judge_claim("totally_bogus_verifier", "answer.txt", {}, UT, INPUTS)
    assert not ok and reason == "unknown_verifier:totally_bogus_verifier"


def test_positive_control_deterministic():
    ok, reason = rc.judge_claim("answer_kv", "answer.txt", {"keys": KEYS}, UT, INPUTS)
    assert ok and reason is None


def test_replay_reason_behavior():
    # D3: mean_col 已為 deterministic
    assert rc.replay_reason("unsupported_recompute_type:mean_col", UT, INPUTS, "plain_recomputed") == (True, None)
    # D3b: pearson 已為 deterministic
    assert rc.replay_reason("unsupported_recompute_type:pearson", UT, INPUTS, "plain_recomputed") == (True, None)
    # 未支援的虛構型別 → 非 deterministic
    assert rc.replay_reason("unsupported_recompute_type:bogus_stat_9x", UT, INPUTS, "plain_recomputed") == (
        False, "unsupported_recompute_type:bogus_stat_9x")
    # 已在支援集合的型別 → 翻 deterministic（D3 擴充後的行為形狀）
    assert rc.replay_reason("unsupported_recompute_type:zcount3", UT, INPUTS, "kv_recomputed") == (True, None)
    # missing_param → missing_raw，不造假
    assert rc.replay_reason("missing_param:values", UT, INPUTS) == (None, None)
    # model_declared_unverified → fail-closed
    assert rc.replay_reason("model_declared_unverified", UT, INPUTS)[0] is False


def test_baseline_totals():
    rows = rc.collect()
    s = rc.summarize(rows)
    assert s["total"] == 76
    assert s["missing_raw"] == 3  # 2 deterministic + 1 missing_param:values
    assert s["replayable"] == 73
    assert s["deterministic"] == 14  # D3 (12) + D3b (2) 全部 14 條 unsupported 皆已落地
    assert s["baseline"]["baseline_match"] is True
    assert s["baseline"]["deterministic_in_missing_raw"] == 2
    # 每行都有必要欄位
    for r in rows:
        assert r["replay_status"] in ("unverified", "deterministic", "missing_raw")
        assert r["task_id"] and r["claim_id"] and r["source"]


def test_reason_distribution_and_unsupported_types():
    s = rc.summarize(rc.collect())
    assert s["reason_distribution"]["deliverable_not_in_request:*"] == 52
    assert s["reason_distribution"]["deterministic"] == 14
    assert s["unsupported_recompute_types"] == {"mean_col": 8, "median_col": 2, "pearson": 2, "std_col": 2}


def test_gate_check_passes():
    """成效門機械檢驗綠燈：deterministic >= 30 且負控制 0 假 PASS。"""
    assert rc.gate_check() == 0


def test_gate_check_negative_control_fails_on_false_pass():
    """負控制：若有假 PASS，gate_check 必須失敗退出（exit 1）。"""
    with patch.object(rc, "judge_claim", return_value=(True, None)):
        assert rc.gate_check() == 1


def test_replay_claims_gate_flag(capsys):
    """P20261113_0846-3：--gate 命令列路徑執行成功，輸出含 GATE_CHECK: 與 VERDICT: PASS。"""
    assert rc.main(["--gate"]) == 0
    out = capsys.readouterr().out
    assert "GATE_CHECK:" in out and "VERDICT: PASS" in out
    assert rc.run_gate_check is rc.gate_check  # 票面函式名為同一實作


def test_replay_claims_verify_specs_flag(capsys):
    """P20261113_1206-3：--verify-specs 交叉驗證 4 題 G4 凍結規格（正控制必 PASS、負控制必非 PASS、0 假 PASS）。"""
    assert rc.main(["--verify-specs"]) == 0
    out = capsys.readouterr().out
    assert "FROZEN_SPECS:" in out and "VERDICT: PASS" in out


def test_replay_claims_verify_specs_flag_neg_control(tmp_path, capsys):
    """P20261113_1206-3 負控制：規格自 hash 被篡改 → verify_frozen_specs 必 FAIL（RC 1）。"""
    import copy
    src = REPO / "ops/reqloop/g4/specs/dab_725.json"
    raw = json.loads(src.read_text(encoding="utf-8"))
    raw = copy.deepcopy(raw)
    raw["items"][0]["quote"] = "TAMPERED"
    (tmp_path / "dab_725.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    for tid in ("dab_587", "dab_657", "dab_517"):
        (tmp_path / f"{tid}.json").write_bytes((REPO / "ops/reqloop/g4/specs" / f"{tid}.json").read_bytes())
    assert rc.verify_frozen_specs(tmp_path) == 1
    assert "FROZEN_SPECS FAIL" in capsys.readouterr().out


def test_replay_claims_json_flag(capsys):
    """P20261113_0948-3：--json 輸出機器可讀統計（K1 trusted）。

    驗證：RC 0、stdout 可被 json.loads 解析、"deterministic" 為整數（現值 66＝成效門口徑）、
    內含 "by_task"（每題 total/deterministic/unverified/missing_raw，分組合計＝76）。
    """
    assert rc.main(["--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert isinstance(doc["deterministic"], int)
    assert doc["deterministic"] == 66
    assert doc["totals"]["deterministic"] == 66
    by = doc["by_task"]
    assert isinstance(by, dict) and by
    assert sum(t["total"] for t in by.values()) == 76
    for t in by.values():
        assert t["total"] == t["deterministic"] + t["unverified"] + t["missing_raw"]
