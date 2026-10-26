"""v4 live-resample batch：預註冊計畫 vs. 落盤分析的一致性釘死。

`ops/realrun/prereg_v4.json`（34 題 polyglot_py × 2 臂 × 3 reps，n=102 pairs）
在首個 model call 之前提交；`ops/realrun/analyze_v4.json` 是該批的分析結果
（2026-10-26，3/3 reps 全數完成、0 infra_void）。本檔不重跑實驗，只做
「結果檔沒有漂離預註冊」的可重跑檢查：

1. 分析檔指向同一個 prereg id；n_pairs、arms、alpha 與註冊值一致。
2. 落報的 p 可由落報的 (b, c) 用專案自己的 `mcnemar_exact` 逐位元組重算——
   註冊統計量是 exact two-sided McNemar（primary unit＝(task, rep) pair），
   任何一個數字被事後改動都會讓本測試翻紅。
3. 決定狀態等於「預註冊決定規則套用到 (b, c, p, alpha)」——不是「顯著就
   EFFECTIVE」的任意規則；方向守衛在負對照裡釘死。
4. 3 個註冊 rep 全數在檔（INCOMPLETE 規則未觸發）；scorer 未使用
   （真實訊號列，不是上界列）；34 題全數計入（無事後任務選擇）。

負對照（規則本身必須有牙）：
- 鏡像 (b=15, c=5) → CONTRADICTS（顯著但反方向：無效果結論，更沒有
  「有害」結論——R532 AMEND1 方向守衛）；
- (b=5, c=5) → UNRESOLVED（對稱分歧＝無方向）；
- (b=5, c=15, p≥alpha) → UNRESOLVED（c>b 但未達 α）。

口徑：EFFECTIVE 只表示「本批上 B 接受的比 A 多」，不是「證明變好」
（單一模型、單一槽位、H-12）；引用時必須帶 n=102 pairs 與 scorer=false。
"""
from __future__ import annotations

import json
from pathlib import Path

from vacant_network.research import mcnemar_exact

REPO = Path(__file__).resolve().parent.parent
HERE = REPO / "ops" / "realrun"
PREREG = HERE / "prereg_v4.json"
ANALYZE = HERE / "analyze_v4.json"


def _load(p: Path) -> dict:
    assert p.exists(), f"missing {p}（v4 預註冊/結果檔必須在 repo 裡才可被引用）"
    return json.loads(p.read_text(encoding="utf-8"))


def decision_state(b: int, c: int, p: float, alpha: float) -> str:
    """prereg_v4.json decision_states 的機械化（EFFECTIVE/CONTRADICTS/UNRESOLVED）。

    INCOMPLETE 是「rep 數量不足」的狀態，屬於批次完整性，不在 (b, c, p) 上判定，
    由 test_v4_all_registered_reps_present 單獨釘。
    """
    if c > b and p < alpha:
        return "EFFECTIVE"
    if c < b and p < alpha:
        return "CONTRADICTS"
    return "UNRESOLVED"


def test_v4_analyze_points_at_registered_prereg() -> None:
    pr, an = _load(PREREG), _load(ANALYZE)
    assert an["prereg_id"] == pr["id"]
    assert an["prereg_file"].endswith("prereg_v4.json")
    assert an["alpha"] == pr["analysis"]["alpha"] == 0.05
    assert an["arm_a"] == "A_none" and an["arm_b"] == "B_resample3"
    assert pr["fixed"]["scorer_used"] is False
    assert pr["fixed"]["visible_equals_grader"] is True
    assert len(pr["fixed"]["tasks"]) == 34
    assert an["n_pairs"] == 34 * pr["fixed"]["reps"] == 102
    assert an["n_runs_per_arm"] == 102


def test_v4_reported_p_recomputes_from_reported_b_c() -> None:
    an = _load(ANALYZE)
    pooled = an["pooled"]
    assert isinstance(pooled["b"], int) and isinstance(pooled["c"], int)
    assert pooled["b"] >= 0 and pooled["c"] >= 0
    assert pooled["b"] + pooled["c"] <= an["n_pairs"]
    # 註冊統計量＝exact two-sided McNemar；落報 p 必須逐位元組等於重算值
    assert pooled["p"] == mcnemar_exact(pooled["b"], pooled["c"])
    for rep in an["per_rep"]:
        assert rep["b"] >= 0 and rep["c"] >= 0
        assert rep["b"] + rep["c"] <= rep["n_pairs"]
        assert rep["p"] == mcnemar_exact(rep["b"], rep["c"])
    # per_rep 的分歧對加總＝pooled（同批內一致）
    assert sum(r["b"] for r in an["per_rep"]) == pooled["b"]
    assert sum(r["c"] for r in an["per_rep"]) == pooled["c"]


def test_v4_state_is_the_registered_rule_applied() -> None:
    an = _load(ANALYZE)
    pooled = an["pooled"]
    expect = decision_state(pooled["b"], pooled["c"], pooled["p"], an["alpha"])
    assert an["state"] == expect
    # 決定狀態的文本必須來自預註冊（不被事後改寫）
    pr = _load(PREREG)
    assert an["states_from_plan"][expect] == pr["decision_states"][expect]


def test_v4_all_registered_reps_present() -> None:
    an = _load(ANALYZE)
    pr = _load(PREREG)
    assert len(an["per_rep"]) == pr["fixed"]["reps"] == 3
    assert [r["rep"] for r in an["per_rep"]] == [1, 2, 3]
    for r in an["per_rep"]:
        assert r["n_pairs"] == 34  # 34 題全數計入，無事後任務選擇
        assert r["voids"] == []    # infra_void 出分母、單獨報告——本批為 0
    assert "INCOMPLETE" not in an["state"]


def test_v4_negative_controls_state_rule_is_directional() -> None:
    # 反方向顯著：CONTRADICTS，不是「顯著＝EFFECTIVE」
    assert decision_state(15, 5, mcnemar_exact(15, 5), 0.05) == "CONTRADICTS"
    # 對稱分歧：無方向
    assert decision_state(5, 5, mcnemar_exact(5, 5), 0.05) == "UNRESOLVED"
    # c > b 但 p 未達 α：UNRESOLVED（null 不是 negative）
    assert decision_state(5, 15, 0.9, 0.05) == "UNRESOLVED"
    # 本批實際落點：c=15 > b=5 且 p=0.0414 < 0.05 → EFFECTIVE
    p = mcnemar_exact(5, 15)
    assert p < 0.05
    assert decision_state(5, 15, p, 0.05) == "EFFECTIVE"


def test_v4_state_text_forbids_overclaim() -> None:
    an = _load(ANALYZE)
    txt = an["states_from_plan"]["EFFECTIVE"]
    assert "May NOT state 'proves better'" in txt
    assert "n=102 pairs" in txt
    assert "H-12" in txt
