"""v6 live resample scale-up batch：預註冊計畫 vs. 落盤分析的一致性釘死。

`ops/realrun/prereg_v6.json`（34 題 polyglot_py × 2 臂 × 5 reps，n=170 pairs）
在首個 model call 之前凍結（`frozen_before_first_model_call: true`）；
`ops/realrun/analyze_v6.json` 將是該批的分析結果。本檔不重跑實驗，只做
「結果沒有漂離預註冊」的可重跑檢查：

1. 預註冊檔本身：凍結旗標、scorer=false、visible_equals_grader、34 題（與 v4/v5
   同一任務集）、臂＝A_none（control）vs B_resample3（treatment）、5 reps、
   決定狀態四態齊備、INCOMPLETE 規則含「不可中途改設計」。
2. 分析檔（存在時）指向同一個 prereg id；n_pairs、arms、alpha 與註冊值一致。
3. 落報的 p 可由落報的 (b, c) 用專案自己的 `mcnemar_exact` 逐位元組重算——
   註冊統計量是 exact two-sided McNemar（primary unit＝(task, rep) pair）。
4. 決定狀態等於「預註冊決定規則套用到 (b, c, p, alpha)」；方向守衛在負對照
   裡釘死（CONTRADICTS ≠ 有害；UNRESOLVED 是合法結果）。
5. 5 個註冊 rep 全數在檔（INCOMPLETE 規則未觸發）；scorer 未使用；34 題全數
   計入（無事後任務選擇）。

v6 對照方向（與 v4 同行，別抄錯臂角色）：
  b = control（none）接受 且 treatment（resample）未接受
  c = control 未接受 且 treatment 接受
  EFFECTIVE = c > b 且 p < 0.05 =「本批上 resample 接受的多於 none」

v6 就是 v4 的同一行（round 76–77, n=102, p=0.0414 貼著 α）在更高功效下的複驗；
不測試新機制。口徑：EFFECTIVE 只表示上述，不是「證明變好」（單一模型、單一槽位、
H-12）；引用時必須帶 n=170 pairs 與 scorer=false。v6 與 v1–v5 不 pool。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from vacant_network.research import mcnemar_exact

REPO = Path(__file__).resolve().parent.parent
HERE = REPO / "ops" / "realrun"
PREREG = HERE / "prereg_v6.json"
PREREG_V4 = HERE / "prereg_v4.json"
PREREG_V5 = HERE / "prereg_v5.json"
ANALYZE = HERE / "analyze_v6.json"

ARM_A = "A_none"        # control：單發（無重試）
ARM_B = "B_resample3"   # treatment：可見驗收失敗時乾淨重抽、最多 3 次、不給失敗原文
N_TASKS = 34
REPS = 5
N_PAIRS = N_TASKS * REPS  # 170


def _load(p: Path) -> dict:
    assert p.exists(), f"missing {p}（v6 預註冊/結果檔必須在 repo 裡才可被引用）"
    return json.loads(p.read_text(encoding="utf-8"))


def decision_state(b: int, c: int, p: float, alpha: float) -> str:
    """prereg_v6.json decision_states 的機械化（EFFECTIVE/CONTRADICTS/UNRESOLVED）。

    INCOMPLETE 是「rep 數量不足」的狀態，屬於批次完整性，不在 (b, c, p) 上判定，
    由 analyze 檔的 rep 齊全測試單獨釘。
    """
    if c > b and p < alpha:
        return "EFFECTIVE"
    if b > c and p < alpha:
        return "CONTRADICTS"
    return "UNRESOLVED"


# ---------------------------------------------------------------- prereg pins

def test_v6_prereg_is_frozen_and_complete() -> None:
    pr = _load(PREREG)
    assert pr["frozen_before_first_model_call"] is True
    assert pr["fixed"]["scorer_used"] is False
    assert pr["fixed"]["visible_equals_grader"] is True
    assert len(pr["fixed"]["tasks"]) == N_TASKS
    assert set(pr["fixed"]["arms"]) == {ARM_A, ARM_B}
    assert pr["fixed"]["arm_roles"]["control"] == ARM_A
    assert pr["fixed"]["arm_roles"]["treatment"] == ARM_B
    assert pr["fixed"]["reps"] == REPS
    assert "McNemar" in pr["analysis"]["primary_statistic"]
    assert pr["analysis"]["alpha"] == 0.05
    assert set(pr["decision_states"]) == {
        "EFFECTIVE", "CONTRADICTS", "UNRESOLVED", "INCOMPLETE"}
    # INCOMPLETE 規則必須含「可續跑」與「不可中途改設計」
    inc = pr["decision_states"]["INCOMPLETE"]
    assert "續跑" in inc and "不可中途改設計" in inc
    # 方向守衛的文本必須存在（不寫「有害」結論）
    assert "不寫「有害」" in pr["decision_states"]["CONTRADICTS"]


def test_v6_prereg_task_set_matches_v4_v5() -> None:
    # 同 v4/v5 的 34 題：無事後任務選擇，跨批比對才有描述性意義
    v6 = _load(PREREG)["fixed"]["tasks"]
    v4 = _load(PREREG_V4)["fixed"]["tasks"]
    v5 = _load(PREREG_V5)["fixed"]["tasks"]
    assert sorted(v6) == sorted(v4)
    assert sorted(v6) == sorted(v5)
    assert len(v6) == len(set(v6)) == N_TASKS


def test_v6_prereg_honesty_binds_overclaim() -> None:
    pr = _load(PREREG)
    eff = pr["decision_states"]["EFFECTIVE"]
    assert "May NOT state 'proves better'" in eff
    assert "n=170 pairs" in eff
    assert "scorer=false" in eff
    # 同一行複驗的定位必須寫死（不是新機制）
    assert "v4" in pr["question"]
    # 不跨批 pool（v1–v5 不可合併成一個大 n）
    assert "v1/v2/v3/v4/v5" in pr["analysis"]["not_done"][0]


def test_v6_negative_controls_state_rule_is_directional() -> None:
    # 反方向顯著（none 比 resample 好）：CONTRADICTS，不是「顯著＝EFFECTIVE」，
    # 也**不是**「有害」結論（R532 AMEND1 方向守衛）
    assert mcnemar_exact(15, 5) < 0.05
    assert decision_state(15, 5, mcnemar_exact(15, 5), 0.05) == "CONTRADICTS"
    # 對稱分歧：無方向
    assert decision_state(5, 5, mcnemar_exact(5, 5), 0.05) == "UNRESOLVED"
    # c > b 但 p 未達 α：UNRESOLVED（null 不是 negative）
    assert decision_state(5, 15, 0.9, 0.05) == "UNRESOLVED"
    # 同 (b, c) 不同方向不可混：(5,15) 顯著時是 EFFECTIVE
    assert decision_state(5, 15, mcnemar_exact(5, 15), 0.05) == "EFFECTIVE"
    # v6 期望效應的量級（v4 的點估計 b~8, c=24 在 170 pairs 上）應遠低於 α
    # （mcnemar_exact(8,24)=0.007，比 v4 的 0.0414 更顯著）
    assert mcnemar_exact(8, 24) < 0.01


# ------------------------------------------------------- analyze file (when it lands)

def _analyze_or_skip() -> dict:
    if not ANALYZE.exists():
        pytest.skip("analyze_v6.json not mirrored yet — batch still incomplete "
                    "(prereg INCOMPLETE rule: decision only after 5 reps)")
    return _load(ANALYZE)


def test_v6_analyze_points_at_registered_prereg() -> None:
    an = _analyze_or_skip()
    pr = _load(PREREG)
    assert an["prereg_id"] == pr["id"]
    assert an["prereg_file"].endswith("prereg_v6.json")
    assert an["alpha"] == pr["analysis"]["alpha"] == 0.05
    assert an["arm_a"] == ARM_A and an["arm_b"] == ARM_B
    assert an["n_pairs"] == N_TASKS * pr["fixed"]["reps"] == N_PAIRS
    assert an["n_runs_per_arm"] == N_PAIRS


def test_v6_reported_p_recomputes_from_reported_b_c() -> None:
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


def test_v6_state_is_the_registered_rule_applied() -> None:
    an = _analyze_or_skip()
    pr = _load(PREREG)
    pooled = an["pooled"]
    expect = decision_state(pooled["b"], pooled["c"], pooled["p"], an["alpha"])
    assert an["state"] == expect
    # 決定狀態的文本必須來自預註冊（不被事後改寫）
    assert an["states_from_plan"][expect] == pr["decision_states"][expect]


def test_v6_all_registered_reps_present() -> None:
    an = _analyze_or_skip()
    pr = _load(PREREG)
    assert len(an["per_rep"]) == pr["fixed"]["reps"] == REPS
    assert [r["rep"] for r in an["per_rep"]] == [1, 2, 3, 4, 5]
    for r in an["per_rep"]:
        assert r["n_pairs"] == N_TASKS  # 34 題全數計入，無事後任務選擇
        assert r["voids"] == []        # infra_void 出分母、單獨報告
    assert "INCOMPLETE" not in an["state"]


def test_v6_state_text_forbids_overclaim() -> None:
    an = _analyze_or_skip()
    txt = an["states_from_plan"]["EFFECTIVE"]
    assert "May NOT state 'proves better'" in txt
    assert "n=170 pairs" in txt
    assert "H-12" in txt
