"""v7 prereg 守衛（2026-11-06，round 115）：把**已凍結的 plan** 與**已落盤的分析結果**
都釘成測試，防止後來的改動悄悄改口徑（同 v4/v5 模式，見 test_realrun_v5_prereg.py）。

v7 = 「同一行（visible-test 失敗驅動的重試 vs. 不重試）在**第二個本地模型**上還成不成立」
（H-12 的跨模型複製；qwen/qwen3.8-27b 上 v4/v6 已建立這一行）。
- prereg：`ops/realrun/prereg_v7.json`（round 109 註冊、第一次模型呼叫前凍結）。
- 分析：`ops/realrun/analyze_v7.json`（5 rep 齊後由凍結 plan 判定，round 115 落盤）。
- 判定口徑（prereg 明文）：b = (A_none pass, B_resample3 fail)、c = (A_none fail, B_resample3 pass)；
  REPLICATED = c > b 且 p < 0.05；CONTRADICTS = b > c 且 p < 0.05；否則 NOT_REPLICATED；
  完成 rep 數 < 5 → INCOMPLETE（不給決定狀態）。

零模型呼叫：本檔只讀檔＋重算 p（mcnemar_exact）。
"""
from __future__ import annotations

import json
import pathlib

from vacant_network.research import mcnemar_exact

ROOT = pathlib.Path(__file__).resolve().parents[1]
PR = json.loads((ROOT / "ops" / "realrun" / "prereg_v7.json").read_text(encoding="utf-8"))
AN = json.loads((ROOT / "ops" / "realrun" / "analyze_v7.json").read_text(encoding="utf-8"))

ARM_A = "A_none"        # 對照：不重試
ARM_B = "B_resample3"   # 處理：visible test 失敗驅動、最多 3 次
N_REPS = 5
N_TASKS = 34
ALPHA = 0.05


def _state(b: int, c: int, p: float, alpha: float) -> str:
    """prereg 的機械判定（方向護衛，R532 AMEND1 模式）。"""
    if c > b and p < alpha:
        return "REPLICATED"
    if b > c and p < alpha:
        return "CONTRADICTS"
    return "NOT_REPLICATED"


# ── prereg 本身（第一次模型呼叫前已凍結）─────────────────────────────

def test_prereg_frozen_before_first_model_call():
    assert PR["frozen_before_first_model_call"] is True
    assert PR["id"] == "v7_live_resample_crossmodel_34tasks_20261027"
    assert PR["fixed"]["reps"] == N_REPS
    assert len(PR["fixed"]["tasks"]) == N_TASKS
    assert set(PR["fixed"]["arms"]) == {ARM_A, ARM_B}
    # 同一行、只換模型：retry 臂的參數是 resample（不是 hint）。
    assert PR["fixed"]["arms"][ARM_B] == ["--retry", "resample", "--max-attempts", "3"]
    assert PR["analysis"]["alpha"] == ALPHA


def test_prereg_task_set_is_the_v4_set():
    """34 題＝v4 的同一組 polyglot_py（無事後挑選，H-12 複製的前提）。"""
    v4 = json.loads((ROOT / "ops" / "realrun" / "prereg_v4.json").read_text(encoding="utf-8"))
    assert sorted(PR["fixed"]["tasks"]) == sorted(v4["fixed"]["tasks"])


def test_prereg_decision_states_and_direction_guard():
    ds = PR["decision_states"]
    assert set(ds) == {"REPLICATED", "CONTRADICTS", "NOT_REPLICATED", "INCOMPLETE"}
    # 方向護衛：REPLICATED 是 c > b（處理優於對照）；CONTRADICTS 是 b > c。
    assert "c > b" in ds["REPLICATED"] and "p < 0.05" in ds["REPLICATED"]
    assert "b > c" in ds["CONTRADICTS"] and "p < 0.05" in ds["CONTRADICTS"]
    # 不可中途改設計、5 rep 齊才判定。
    assert "不可中途改設計" in ds["INCOMPLETE"]
    assert "5 rep" in ds["INCOMPLETE"]


def test_prereg_replicated_text_forbids_overclaim():
    t = PR["decision_states"]["REPLICATED"]
    assert "proves better" in t            # 明文禁止「證明更好」
    assert "n=170 pairs" in t              # 可引用口徑帶分母
    assert "scorer=false" in t             # 無 scorer，只有 visible test 失敗訊號
    assert "gemma-4-12b-it-qat" in t       # 第二個模型（H-12 複製的對象）
    assert "R460R" in t and "R529" in t    # 不可搬 qwen 上其他行的數字


def test_prereg_contradicts_text_has_direction_guard():
    """R532 AMEND1 的方向護衛帶進 v7：顯著反向也**不**預註冊「有害」結論。"""
    t = PR["decision_states"]["CONTRADICTS"]
    assert "harmful" in t or "有害" in t
    assert "不寫「有害」" in t


def test_prereg_not_replicated_is_not_a_negative_result():
    assert "not a negative result" in PR["decision_states"]["NOT_REPLICATED"]
    assert "does not invalidate v4/v6" in PR["decision_states"]["NOT_REPLICATED"]


# ── 判定規則的機械對照（p 重算＋狀態映射）────────────────────────────

def test_state_rule_negative_controls():
    # 實測方向：c=21 > b=7 且 p<0.05 → REPLICATED（v7 落盤結果走這支路徑）。
    p = mcnemar_exact(7, 21)
    assert p < ALPHA and _state(7, 21, p, ALPHA) == "REPLICATED"
    # 反向顯著 → CONTRADICTS（規則對稱、非「有害」）。
    p2 = mcnemar_exact(21, 7)
    assert p2 < ALPHA and _state(21, 7, p2, ALPHA) == "CONTRADICTS"
    # 不顯著 → NOT_REPLICATED（空結果）。
    p3 = mcnemar_exact(10, 10)
    assert p3 >= ALPHA and _state(10, 10, p3, ALPHA) == "NOT_REPLICATED"
    # 邊界：b == c（無方向）→ NOT_REPLICATED。
    assert _state(5, 5, mcnemar_exact(5, 5), ALPHA) == "NOT_REPLICATED"


# ── analyze_v7.json（5 rep 齊後落盤，round 115）──────────────────────

def test_analyze_points_at_this_prereg():
    assert AN["prereg_id"] == PR["id"]
    assert AN["alpha"] == ALPHA
    assert AN["arm_a"] == ARM_A and AN["arm_b"] == ARM_B
    assert set(AN["states_from_plan"]) == {"REPLICATED", "CONTRADICTS", "NOT_REPLICATED", "INCOMPLETE"}


def test_analyze_all_five_reps_complete_no_voids():
    assert len(AN["per_rep"]) == N_REPS
    for r in AN["per_rep"]:
        assert r["complete"] is True
        assert r["n_pairs"] == N_TASKS          # 34 題全數計入（無缺格）
        assert r["voids"] == []                # 無 infra_void（有的話照舊剔除並記錄）
    assert AN["state_note"] and "5 registered reps complete" in AN["state_note"]


def test_analyze_p_recomputes_from_b_c_and_state_matches_rule():
    pooled = AN["pooled"]
    b, c = pooled["b"], pooled["c"]
    assert (b, c) == (7, 21)                   # 落盤的discordant 計數
    # p 可由 (b, c) 用同一支 mcnemar_exact 重算（口徑＝prereg 的 primary_statistic）。
    assert abs(mcnemar_exact(b, c) - pooled["p"]) < 1e-12
    assert AN["state"] == _state(b, c, pooled["p"], ALPHA) == "REPLICATED"
    # 5 rep 的 discordant 加總＝pooled（無偷漏）。
    assert sum(r["b"] for r in AN["per_rep"]) == b
    assert sum(r["c"] for r in AN["per_rep"]) == c
    assert AN["n_pairs"] == N_TASKS * N_REPS == 170
    assert AN["n_runs_per_arm"] == 170


def test_replicated_wording_carries_the_prereg_limits():
    """落盤結論可引用，但口徑＝prereg 明文（n=170 pairs、scorer=false、第二個模型）。
    注意：`states_from_plan` 是**逐字引用 plan 的措辭表**（其中本就含
    「May NOT state 'proves better'」等禁止句），所以禁止性檢查釘在 plan 文本上
    （test_prereg_replicated_text_forbids_overclaim），而**結論欄位**（state/state_note）
    不得出現超口徑措辭。"""
    assert AN["state"] == "REPLICATED"
    assert "proven superior" not in json.dumps(AN, ensure_ascii=False)
    note = AN["state_note"]
    assert "proves better" not in note and "R460R" not in note and "R529" not in note
    # 分析器引用的是 plan 的**同一份**措辭（禁止句在內、未被改寫）。
    assert AN["states_from_plan"]["REPLICATED"] == PR["decision_states"]["REPLICATED"]
    assert AN["states_from_plan"]["CONTRADICTS"] == PR["decision_states"]["CONTRADICTS"]
