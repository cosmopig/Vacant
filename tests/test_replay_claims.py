"""D1 離線 claim 重播的 pytest（零模型）。

跑法：python3 -m pytest tests/test_replay_claims.py -v
"""
import importlib.util
import json
import pathlib

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
    # 原始失敗階段重跑：D3 擴充後 mean_col 已入支援集合 → 翻 deterministic
    assert rc.replay_reason("unsupported_recompute_type:mean_col", UT, INPUTS, "plain_recomputed") == (True, None)
    # D3b（P20261113_0344-1）：pearson 已入支援集合 → 翻 deterministic
    assert rc.replay_reason("unsupported_recompute_type:pearson", UT, INPUTS, "plain_recomputed") == (True, None)
    # 已在支援集合的型別 → 翻 deterministic（D3 擴充後的行為形狀）
    assert rc.replay_reason("unsupported_recompute_type:zcount3", UT, INPUTS, "kv_recomputed") == (True, None)
    # 不在支援集合的型別 → 維持原 reason
    assert rc.replay_reason("unsupported_recompute_type:zcount99", UT, INPUTS, "kv_recomputed") == (
        False, "unsupported_recompute_type:zcount99")
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
    # D3（P20261113_0300-3）＋D3b（P20261113_0344-1）：mean_col/median_col/std_col 12 條＋pearson 2 條翻 deterministic
    assert s["deterministic"] == 14
    assert s["unverified"] == 59  # 76 − 3 missing_raw − 14 deterministic
    assert s["baseline"]["baseline_match"] is True
    assert s["baseline"]["deterministic_in_missing_raw"] == 2
    # 每行都有必要欄位
    for r in rows:
        assert r["replay_status"] in ("unverified", "deterministic", "missing_raw")
        assert r["task_id"] and r["claim_id"] and r["source"]


def test_reason_distribution_and_unsupported_types():
    s = rc.summarize(rc.collect())
    # D3/D3b 後：12 條 mean/median/std＋2 條 pearson 已翻 deterministic，不再留在 unverified 分布
    assert s["reason_distribution"]["deliverable_not_in_request:*"] == 52
    assert s["reason_distribution"]["deterministic"] == 14
    assert s["reason_distribution"]["model_declared_unverified"] == 4
    assert s["reason_distribution"]["unknown_verifier:missing"] == 3
    assert "unsupported_recompute_type:mean_col" not in s["reason_distribution"]
    # 原始 reason 仍保留（歷史證據不抹除）：12 條 D3 型別＋2 條 D3b pearson
    assert s["unsupported_recompute_types"] == {"mean_col": 8, "median_col": 2, "pearson": 2, "std_col": 2}
