"""Track A 四臂 harness 的確定性自驗（vacant/research.py）。

用 StubBrain + 合成任務（每類 10 題）鎖住指標與 H0 因果拆解的算術，
確保管線/統計不被改壞。數字為刻意設計、非實證（見 research.py docstring）。
"""

from __future__ import annotations

from vacant.research import (
    decompose,
    discordance,
    mcnemar_exact,
    metrics,
    run_suite,
    synthetic_suite,
)


def _fixture(k: int = 3):
    brain, tasks = synthetic_suite(per_class=10)
    results = run_suite(tasks, brain.generate, k)
    return results, metrics(results)


def test_arm_accuracy_ladder():
    """四臂準確率階梯：25% → 25% → 50% → 75%。"""
    _, m = _fixture()
    assert m["plain1"]["M1_acc"] == 0.25
    assert m["plainK"]["M1_acc"] == 0.25          # 純算力無加值（stub 確定性）
    assert m["bok_v"]["M1_acc"] == 0.50           # 需求驗證 +25%
    assert m["vacant"]["M1_acc"] == 0.75          # 責任修補 +25%


def test_h0_decomposition():
    """責任貢獻(+50%) 遠大於算力貢獻(0%) —— H0 的因果證據。"""
    _, m = _fixture()
    dec = decompose(m)
    assert abs(dec["G_compute"] - 0.0) < 1e-9
    assert abs(dec["G_verify"] - 0.25) < 1e-9
    assert abs(dec["G_resp"] - 0.25) < 1e-9
    assert abs(dec["responsibility"] - 0.50) < 1e-9
    assert dec["responsibility"] > dec["G_compute"]


def test_h1_discordance_and_mcnemar():
    """plain1 vs vacant：可復原 b=20、回歸 c=0（零回歸）、McNemar 顯著。"""
    results, _ = _fixture()
    b, c, bw = discordance(results, "plain1", "vacant")
    assert (b, c, bw) == (20, 0, 10)
    assert mcnemar_exact(b, c) < 1e-4
    assert mcnemar_exact(0, 0) == 1.0             # 無不一致對 → 不顯著


def test_h3_honest_accountability():
    """責任層讓自信錯誤率歸零、宣稱達標即真達標。"""
    _, m = _fixture()
    assert m["plain1"]["M4_confwrong"] == 0.75     # plain 永遠宣稱 → 錯也宣稱
    assert m["vacant"]["M4_confwrong"] == 0.0      # vacant 只在過 V 才宣稱
    assert m["vacant"]["M2_vprec"] == 1.0          # 宣稱達標子集全對


def test_equal_compute_calls():
    """等算力檢查：plain1=1、plainK=K、vacant/bok_v 早停 ≤K。"""
    _, m = _fixture(k=3)
    assert m["plain1"]["M5_calls"] == 1.0
    assert m["plainK"]["M5_calls"] == 3.0
    assert m["vacant"]["M5_calls"] <= 3.0
    assert m["bok_v"]["M5_calls"] <= 3.0


# === 預註冊統計四函式（17 §P0-6／G7）的手算對照 ================================
# 每個對照值都附手算來源；零 scipy，對照不依賴任何外部套件。

import math

import pytest

from vacant.research import (
    holm_bonferroni,
    mcnemar_n_required,
    mcnemar_power,
    tost_equiv_boot,
    wilcoxon_signed_rank_exact,
)


class TestHolmBonferroni:
    def test_three_hypotheses_hand_computed(self):
        # 手算：m=3；排序 0.01<0.03<0.04 → adj = 3·0.01=0.03, 2·0.03=0.06,
        # 1·0.04=0.04；累積最大 → [0.03, 0.06, 0.06]（與 R p.adjust(,,"holm") 一致）。
        out = holm_bonferroni([0.01, 0.04, 0.03])
        assert out == [0.03, 0.06, 0.06]

    def test_single_and_monotone_cap(self):
        assert holm_bonferroni([0.05]) == [0.05]
        # 手算：兩個 0.5 → 2·0.5=1.0（cap），次個累積最大仍 1.0
        assert holm_bonferroni([0.5, 0.5]) == [1.0, 1.0]

    def test_stepdown_running_max(self):
        # 手算：3·0.001=0.003，2·0.001=0.002→被累積最大拉回 0.003，0.9 不動
        assert holm_bonferroni([0.001, 0.001, 0.9]) == [0.003, 0.003, 0.9]

    def test_empty_and_invalid(self):
        assert holm_bonferroni([]) == []
        with pytest.raises(ValueError):
            holm_bonferroni([-0.01])
        with pytest.raises(ValueError):
            holm_bonferroni([1.5])


class TestWilcoxonExact:
    def test_all_positive_n3(self):
        # 手算：ranks 1,2,3 全正，W+=6。2^3=8 指派下 W∈{0..6}，
        # 極端 |W−3|≥3 僅 W=0,6 → p=2/8=0.25。
        r = wilcoxon_signed_rank_exact([1.0, 2.0, 3.0])
        assert r["method"] == "exact"
        assert r["w_plus"] == 6.0
        assert abs(r["p"] - 0.25) < 1e-12

    def test_mixed_signs(self):
        # 手算：|d| 秩 1,2,3；W+=1+3=4。極端 |W−3|≥1 → W∈{0,1,2,4,5,6} → p=6/8=0.75。
        r = wilcoxon_signed_rank_exact([1.0, -2.0, 3.0])
        assert r["w_plus"] == 4.0
        assert abs(r["p"] - 0.75) < 1e-12

    def test_ties_midrank(self):
        # 手算：|d|={2,2,1} → midrank 2.5,2.5,1；W+=5。8 指派中 |W−3|≥2 為
        # W∈{0,1,5,6} → p=4/8=0.5。
        r = wilcoxon_signed_rank_exact([2.0, 2.0, -1.0])
        assert r["w_plus"] == 5.0
        assert abs(r["p"] - 0.5) < 1e-12

    def test_zeros_dropped_and_symmetric_cancel(self):
        # 手算：去零後 n=2、ranks 1,2、W+=3 → 極端 W∈{0,3} → p=2/4=0.5。
        r = wilcoxon_signed_rank_exact([0.0, 1.0, 2.0])
        assert r["n"] == 2.0
        assert abs(r["p"] - 0.5) < 1e-12
        # 等大反向：兩個 midrank 1.5，W+=1.5＝均值 → p=1.0
        r2 = wilcoxon_signed_rank_exact([5.0, -5.0])
        assert abs(r2["p"] - 1.0) < 1e-12

    def test_all_zero_raises(self):
        with pytest.raises(ValueError):
            wilcoxon_signed_rank_exact([0.0, 0.0])


class TestTostEquivBoot:
    def test_zero_diffs_equivalent(self):
        # 常數 0 差 → CI 退化 [0,0]，必落 [−0.05,+0.05]（手算）。
        r = tost_equiv_boot([0.0] * 10, 0.05, seed=1)
        assert r["equivalent"] is True
        assert r["ci_lo"] == 0.0 and r["ci_hi"] == 0.0

    def test_large_diffs_not_equivalent(self):
        # 常數 1.0 差 → CI [1,1] 整條在 δ=0.05 外（手算）。
        r = tost_equiv_boot([1.0] * 10, 0.05, seed=1)
        assert r["equivalent"] is False

    def test_small_noise_equivalent(self):
        # ±0.1 對稱噪音、δ=0.5：任何重抽均值必在 [−0.1,0.1] ⊂ [−0.5,0.5]（手算）。
        diffs = [0.1, -0.1, 0.05, -0.05] * 5
        r = tost_equiv_boot(diffs, 0.5, seed=7)
        assert r["equivalent"] is True

    def test_invalid_inputs(self):
        with pytest.raises(ValueError):
            tost_equiv_boot([0.1], 0.0)
        with pytest.raises(ValueError):
            tost_equiv_boot([], 0.5)


class TestMcNemarPower:
    def test_n5_always_pass_never_rejects(self):
        # 手算：k=5 不一致對、b=5,c=0 的精確 p=2·(1/32)=0.0625>0.05
        # → 拒絕域為空 → power=0（哪怕 ψ=1 全往一邊）。
        assert mcnemar_power(5, 1.0, 1.0) == 0.0

    def test_n6_perfect_direction_always_rejects(self):
        # 手算：k=6、b=6 的精確 p=2·(1/64)=0.03125≤0.05 → 拒絕域 {0,6}，
        # ψ=1 時 B 恆為 6 → power=1。
        assert mcnemar_power(6, 1.0, 1.0) == 1.0

    def test_half_discordance_exact_value(self):
        # 手算：n=6、p_disc=0.5、ψ=1：只有 K=6（機率 0.5^6=1/64）有非空拒絕域
        # 且必拒絕 → power=0.015625。
        assert abs(mcnemar_power(6, 0.5, 1.0) - 0.015625) < 1e-12

    def test_null_size_bounded_by_alpha(self):
        # ψ=0.5（H0 為真）→ power＝檢定 size，精確檢定保守、必 ≤ α。
        assert mcnemar_power(20, 1.0, 0.5) <= 0.05
        assert mcnemar_power(50, 0.6, 0.5) <= 0.05

    def test_x1_magnitude_replicates_power_table(self):
        # 16 號 power 表量級：T=215、p_disc≈0.35、ψ=0.7（H-A1 後半段 +8pp 對應的
        # 不一致對方向比）→ power 應 ≥0.85（常態近似估 ≈0.99，精確值同量級）。
        assert mcnemar_power(215, 0.35, 0.7) >= 0.85

    def test_n_required_hand_computed(self):
        # 手算：ψ=1 時 n=5 power=0、n=6 power=1 → 最小 n=6。
        assert mcnemar_n_required(1.0, 1.0, power=1.0) == 6
        # X1 量級：0.85 檢定力所需 n 不得超過預註冊的 T=215。
        assert mcnemar_n_required(0.35, 0.7, power=0.85) <= 215
        with pytest.raises(ValueError):
            mcnemar_n_required(0.35, 0.5)  # H0 下永遠達不到
