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
    # 原始失敗階段重跑：不支援的型別仍非 deterministic（用保證不存在的名字，不鎖死 D3 前的現狀）
    assert rc.replay_reason("unsupported_recompute_type:zz_no_such_type_9x", UT, INPUTS, "plain_recomputed") == (
        False, "unsupported_recompute_type:zz_no_such_type_9x")
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
    # claimed 模式下只有「支援集合擴充」能翻轉；交付物描述字串不會因任何改動自己變合法（D2 走 --trusted）
    for r in rows:
        if r["replay_status"] == "deterministic":
            assert r["original_reason"].startswith(("unsupported_recompute_type:", "unknown_verifier:"))
    assert s["baseline"]["baseline_match"] is True
    assert s["baseline"]["deterministic_in_missing_raw"] == 2
    # 每行都有必要欄位
    for r in rows:
        assert r["replay_status"] in ("unverified", "deterministic", "missing_raw")
        assert r["task_id"] and r["claim_id"] and r["source"]


def test_reason_distribution_and_unsupported_types():
    s = rc.summarize(rc.collect())
    assert sum(1 for r in rc.collect() if (r["original_reason"] or "").startswith("deliverable_not_in_request:")) == 52
    # 原始原因分布（不隨 D2/D3 改變）；replay 後的 reason_distribution 會隨改善變，不在此鎖
    assert sum(1 for r in rc.collect() if r["original_reason"] == "unsupported_recompute_type:mean_col") == 8
    assert s["unsupported_recompute_types"] == {"mean_col": 8, "median_col": 2, "pearson": 2, "std_col": 2}


# ---- argon 20261113_0353：量具缺陷回歸 ----

def test_improvement_does_not_break_baseline(monkeypatch):
    """舊版 baseline_match 寫死 deterministic==0：D3 一加型別，selftest 就紅（把改善判成量具失敗）。"""
    monkeypatch.setitem(rc.extract._RECOMPUTE_TYPES, "plain_recomputed",
                        rc.extract._RECOMPUTE_TYPES["plain_recomputed"] | {"mean_col"})
    s = rc.summarize(rc.collect())
    assert s["deterministic"] >= 5  # g3_2_fire 5 條 plain_recomputed mean_col 類
    assert s["baseline"]["baseline_match"] is True
    assert rc.selftest() == 0


def test_recompute_flip_is_upper_bound_not_proven(monkeypatch):
    """型別名進集合 ≠ 可檢查：子參數與交付物未存，只能算上界。"""
    monkeypatch.setitem(rc.extract._RECOMPUTE_TYPES, "plain_recomputed",
                        rc.extract._RECOMPUTE_TYPES["plain_recomputed"] | {"mean_col"})
    s = rc.summarize(rc.collect())
    assert s["deterministic_proven"] == 0
    assert s["deterministic_content"] >= 5


def test_trusted_mode_does_not_count_wrong_targets():
    """D2 若把每條 deliverable 一律改成 answer.txt：表格 verifier、講輸入檔的條目、tag_format 不能算 proven。"""
    rows = rc.collect(trusted=True)
    by = {(r["source"], r["task_id"], r["claim_id"]): r for r in rows}
    r2 = by[("g3_2_fire", "dab_725", "R2")]  # group_aggregate
    assert r2["replay_status"] == "unverified" and r2["replay_reason"].startswith("verifier_deliverable_mismatch")
    r6 = by[("g3_2_fire", "dab_725", "R6")]  # 「data/auto-mpg.csv 保持未修改」
    assert r6["replay_status"] == "unverified" and r6["replay_reason"] == "claimed_refers_to_input"
    r4 = by[("g3_2_fire", "dab_725", "R4")]  # tag_format
    assert r4["confidence"] == "upper_bound" and r4["check_class"] == "format"
    s = rc.summarize(rows)
    assert s["baseline"]["baseline_match"] is True
    assert s["deterministic_content_proven"] <= s["deterministic_proven"] <= s["deterministic"]


def test_rerun_does_not_dirty_output(tmp_path):
    out = tmp_path / "replay.json"
    assert rc.main(["--out", str(out)]) == 0
    first = out.read_bytes()
    assert rc.main(["--out", str(out)]) == 0
    assert out.read_bytes() == first  # generated_at 變了也不重寫
