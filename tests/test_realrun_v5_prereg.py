"""v5 live fresh_hint batch：預註冊計畫 vs. 落盤分析的一致性釘死。

`ops/realrun/prereg_v5.json`（34 題 polyglot_py × 2 臂 × 3 reps，n=102 pairs）
在首個 model call 之前凍結（`frozen_before_first_model_call: true`）；
`ops/realrun/analyze_v5.json` 將是該批的分析結果。本檔不重跑實驗，只做
「結果沒有漂離預註冊」的可重跑檢查：

1. 預註冊檔本身：凍結旗標、scorer=false、visible_equals_grader、34 題（與 v4
   同一任務集）、臂＝B_resample3（control）vs C_fresh_hint3（treatment）、
   3 reps、決定狀態四態齊備、INCOMPLETE 規則含「不可中途改設計」。
2. 分析檔（存在時）指向同一個 prereg id；n_pairs、arms、alpha 與註冊值一致。
3. 落報的 p 可由落報的 (b, c) 用專案自己的 `mcnemar_exact` 逐位元組重算——
   註冊統計量是 exact two-sided McNemar（primary unit＝(task, rep) pair）。
4. 決定狀態等於「預註冊決定規則套用到 (b, c, p, alpha)」；方向守衛在負對照
   裡釘死（CONTRADICTS ≠ 有害；UNRESOLVED 是合法結果）。
5. 3 個註冊 rep 全數在檔（INCOMPLETE 規則未觸發）；scorer 未使用；34 題全數
   計入（無事後任務選擇）。

v5 對照方向（與 v4 不同，別抄錯）：
  b = control（resample）接受 且 treatment（fresh_hint）未接受
  c = control 未接受 且 treatment 接受
  EFFECTIVE = c > b 且 p < 0.05 =「本批上 fresh_hint 接受的多於 resample」

口徑：EFFECTIVE 只表示上述，不是「證明變好」（單一模型、單一槽位、H-12）；
引用時必須帶 n=102 pairs 與 scorer=false。v5 與 v1–v4 不 pool。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from vacant_network.research import mcnemar_exact

REPO = Path(__file__).resolve().parent.parent
HERE = REPO / "ops" / "realrun"
PREREG = HERE / "prereg_v5.json"
PREREG_V4 = HERE / "prereg_v4.json"
ANALYZE = HERE / "analyze_v5.json"

ARM_A = "B_resample3"      # control：乾淨重抽
ARM_B = "C_fresh_hint3"    # treatment：乾淨重抽 + ≤380B 失敗提示檔


def _load(p: Path) -> dict:
    assert p.exists(), f"missing {p}（v5 預註冊/結果檔必須在 repo 裡才可被引用）"
    return json.loads(p.read_text(encoding="utf-8"))


def decision_state(b: int, c: int, p: float, alpha: float) -> str:
    """prereg_v5.json decision_states 的機械化（EFFECTIVE/CONTRADICTS/UNRESOLVED）。

    INCOMPLETE 是「rep 數量不足」的狀態，屬於批次完整性，不在 (b, c, p) 上判定，
    由 analyze 檔的 rep 齊全測試單獨釘。
    """
    if c > b and p < alpha:
        return "EFFECTIVE"
    if b > c and p < alpha:
        return "CONTRADICTS"
    return "UNRESOLVED"


# ---------------------------------------------------------------- prereg pins

def test_v5_prereg_is_frozen_and_complete() -> None:
    pr = _load(PREREG)
    assert pr["frozen_before_first_model_call"] is True
    assert pr["fixed"]["scorer_used"] is False
    assert pr["fixed"]["visible_equals_grader"] is True
    assert len(pr["fixed"]["tasks"]) == 34
    assert set(pr["fixed"]["arms"]) == {ARM_A, ARM_B}
    assert pr["fixed"]["arm_roles"]["control"] == ARM_A
    assert pr["fixed"]["arm_roles"]["treatment"] == ARM_B
    assert pr["fixed"]["reps"] == 3
    assert pr["analysis"]["statistic"].startswith("exact two-sided McNemar")
    assert pr["analysis"]["alpha"] == 0.05
    assert set(pr["decision_states"]) == {
        "EFFECTIVE", "CONTRADICTS", "UNRESOLVED", "INCOMPLETE"}
    # INCOMPLETE 規則必須含「可續跑」與「不可中途改設計」
    inc = pr["decision_states"]["INCOMPLETE"]
    assert "續跑" in inc and "不可中途改設計" in inc
    # 方向守衛的文本必須存在（不寫「有害」結論）
    assert "不寫「有害」" in pr["decision_states"]["CONTRADICTS"]


def test_v5_prereg_task_set_matches_v4() -> None:
    # 同 v4 的 34 題：無事後任務選擇，v4-B 與 v5-B 的跨批比對才有描述性意義
    v5 = _load(PREREG)["fixed"]["tasks"]
    v4 = _load(PREREG_V4)["fixed"]["tasks"]
    assert sorted(v5) == sorted(v4)
    assert len(v5) == len(set(v5)) == 34


def test_v5_prereg_honesty_binds_overclaim() -> None:
    pr = _load(PREREG)
    eff = pr["decision_states"]["EFFECTIVE"]
    assert "May NOT state 'proves better'" in eff
    assert "n=102 pairs" in eff
    assert "scorer=false" in eff
    honesty = "\n".join(pr["honesty"])
    assert "H-12" in honesty
    # 兩臂輸入端差異的界：只有 treatment attempt≥2 的 hint
    assert "只可能是" in honesty
    # 不跨批 pool（v1–v4 不可合併成一個大 n）
    assert "不跨批 pool" in pr["analysis"]["pooling"]


def test_v5_negative_controls_state_rule_is_directional() -> None:
    # 反方向顯著（resample 比 fresh_hint 好）：CONTRADICTS，不是「顯著＝EFFECTIVE」，
    # 也**不是**「有害」結論（R532 AMEND1 方向守衛）
    assert mcnemar_exact(15, 5) < 0.05
    assert decision_state(15, 5, mcnemar_exact(15, 5), 0.05) == "CONTRADICTS"
    # 對稱分歧：無方向
    assert decision_state(5, 5, mcnemar_exact(5, 5), 0.05) == "UNRESOLVED"
    # c > b 但 p 未達 α：UNRESOLVED（null 不是 negative）
    assert decision_state(5, 15, 0.9, 0.05) == "UNRESOLVED"
    # 同 (b, c) 不同方向不可混：(5,15) 顯著時是 EFFECTIVE
    assert decision_state(5, 15, mcnemar_exact(5, 15), 0.05) == "EFFECTIVE"


# ------------------------------------------------------- analyze file (when it lands)

def _analyze_or_skip() -> dict:
    if not ANALYZE.exists():
        pytest.skip("analyze_v5.json not mirrored yet — batch still incomplete "
                    "(prereg INCOMPLETE rule: decision only after 3 reps)")
    return _load(ANALYZE)


def test_v5_analyze_points_at_registered_prereg() -> None:
    an = _analyze_or_skip()
    pr = _load(PREREG)
    assert an["prereg_id"] == pr["id"]
    assert an["prereg_file"].endswith("prereg_v5.json")
    assert an["alpha"] == pr["analysis"]["alpha"] == 0.05
    assert an["arm_a"] == ARM_A and an["arm_b"] == ARM_B
    assert an["n_pairs"] == 34 * pr["fixed"]["reps"] == 102
    assert an["n_runs_per_arm"] == 102


def test_v5_reported_p_recomputes_from_reported_b_c() -> None:
    an = _analyze_or_skip()
    pooled = an["pooled"]
    assert isinstance(pooled["b"], int) and isinstance(pooled["c"], int)
    assert pooled["b"] >= 0 and pooled["c"] >= 0
    assert pooled["b"] + pooled["c"] <= an["n_pairs"]
    assert pooled["p"] == mcnemar_exact(pooled["b"], pooled["c"])
    for rep in an["per_rep"]:
        assert rep["b"] >= 0 and rep["c"] >= 0
        assert rep["b"] + rep["c"] <= rep["n_pairs"]
        assert rep["p"] == mcnemar_exact(rep["b"], rep["c"])
    # per_rep 的分歧對加總＝pooled（同批內一致）
    assert sum(r["b"] for r in an["per_rep"]) == pooled["b"]
    assert sum(r["c"] for r in an["per_rep"]) == pooled["c"]


def test_v5_state_is_the_registered_rule_applied() -> None:
    an = _analyze_or_skip()
    pr = _load(PREREG)
    pooled = an["pooled"]
    expect = decision_state(pooled["b"], pooled["c"], pooled["p"], an["alpha"])
    assert an["state"] == expect
    # 決定狀態的文本必須來自預註冊（不被事後改寫）
    assert an["states_from_plan"][expect] == pr["decision_states"][expect]


def test_v5_all_registered_reps_present() -> None:
    an = _analyze_or_skip()
    pr = _load(PREREG)
    assert len(an["per_rep"]) == pr["fixed"]["reps"] == 3
    assert [r["rep"] for r in an["per_rep"]] == [1, 2, 3]
    for r in an["per_rep"]:
        assert r["n_pairs"] == 34  # 34 題全數計入，無事後任務選擇
        assert r["voids"] == []    # infra_void 出分母、單獨報告
    assert "INCOMPLETE" not in an["state"]


def test_v5_state_text_forbids_overclaim() -> None:
    an = _analyze_or_skip()
    txt = an["states_from_plan"]["EFFECTIVE"]
    assert "May NOT state 'proves better'" in txt
    assert "n=102 pairs" in txt
    assert "H-12" in txt
