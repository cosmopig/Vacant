"""R529 主指標的統計核心：分層配對精確檢定＋異質性卡方（手算對照）。

這支在架構裡承重什麼：`DECISION_20260911_R529_CROSS_BANK_PREREG.md` §六-1 的
公式**要是可執行的**，不是寫在文件裡的散文。主指標判 EFFECTIVE 還是 INCONCLUSIVE
就靠這兩支，所以每一格都要有手算對照值（對照值寫在註解裡）。

另外釘一條**誠實邊界**：分層統計量與「把各層的不一致對直接加起來做一次
`mcnemar_exact`」在數值上**完全相同**。預註冊 §六-1 的方框逐字寫了這件事，
這裡用測試把它釘住——哪天有人「改進」成不相同的東西，那就是改了預註冊。
"""

from __future__ import annotations

import math

import pytest

from vacant.research import (
    bc_heterogeneity_chisq,
    holm_bonferroni,
    mcnemar_exact,
    stratified_mcnemar_exact,
)


# ── 分層精確檢定 ──────────────────────────────────────────────────────────
def test_single_stratum_reduces_to_plain_mcnemar():
    """K=1 時必須與 `mcnemar_exact` 逐位元相同（R460 的 b/c = 22/6）。"""
    r = stratified_mcnemar_exact([(22, 6)])
    assert r["b"] == 22 and r["c"] == 6 and r["n_discordant"] == 28
    assert r["p"] == mcnemar_exact(22, 6)
    assert r["k_strata"] == 1


def test_pooling_identity_is_pinned():
    """§六-1 的方框：分層統計量 ≡ 把不一致對加起來做一次 McNemar。"""
    strata = [(22, 6), (5, 2), (9, 8), (11, 10)]
    r = stratified_mcnemar_exact(strata)
    assert (r["b"], r["c"]) == (47, 26)
    assert r["p"] == mcnemar_exact(47, 26)


def test_hand_computed_two_stratum_case():
    """手算：b=(3,2) c=(1,0) ⇒ B=5, N=6。

    p = 2 · P(X ≤ 1)，X ~ Bin(6, 1/2)
      = 2 · (C(6,0) + C(6,1)) / 2^6 = 2 · 7/64 = 14/64 = 0.21875
    """
    r = stratified_mcnemar_exact([(3, 1), (2, 0)])
    assert r["b"] == 5 and r["c"] == 1 and r["n_discordant"] == 6
    assert abs(r["p"] - 0.21875) < 1e-12


def test_all_concordant_gives_p_one():
    r = stratified_mcnemar_exact([(0, 0), (0, 0)])
    assert r["n_discordant"] == 0 and r["p"] == 1.0


def test_per_stratum_values_are_reported_verbatim():
    """逐層的 b/c 必須照實回傳——「合併顯著」不准蓋掉「某一層反向」。"""
    r = stratified_mcnemar_exact([(10, 1), (1, 6)])
    assert [(d["b"], d["c"]) for d in r["per_stratum"]] == [(10, 1), (1, 6)]
    assert r["per_stratum"][1]["b"] < r["per_stratum"][1]["c"]   # 反向那一層看得見


def test_direction_is_symmetric():
    a = stratified_mcnemar_exact([(12, 3), (4, 1)])
    b = stratified_mcnemar_exact([(3, 12), (1, 4)])
    assert a["p"] == b["p"]          # 雙尾
    assert (a["b"], a["c"]) == (b["c"], b["b"])


def test_negative_counts_are_rejected():
    with pytest.raises(ValueError):
        stratified_mcnemar_exact([(1, -1)])


def test_family_of_two_under_holm():
    """§六-2 的家族：兩個對照、Holm、α=0.05。最小的 p 乘 2。"""
    p_conform = stratified_mcnemar_exact([(30, 10), (12, 5)])["p"]
    p_off = stratified_mcnemar_exact([(60, 5), (25, 2)])["p"]
    adj = holm_bonferroni([p_conform, p_off])
    assert len(adj) == 2
    assert adj[1] == pytest.approx(min(1.0, 2 * min(p_conform, p_off)))
    assert adj[0] >= p_conform and adj[1] >= p_off


# ── 異質性卡方（描述性）───────────────────────────────────────────────────
def test_homogeneous_strata_give_zero_chi2():
    """三層的 b:c 比例完全相同 ⇒ chi2 = 0、df = 2。"""
    r = bc_heterogeneity_chisq([(6, 3), (4, 2), (2, 1)])
    assert r["df"] == 2
    assert abs(r["chi2"]) < 1e-12
    assert r["p"] == pytest.approx(1.0)


def test_opposite_strata_give_the_hand_computed_chi2():
    """手算：兩層 (10,0) 與 (0,10)。

    p̂ = 10/20 = 0.5；每層期望 (5,5)。
    chi2 = 4 · (5^2 / 5) = 4 · 5 = 20；df = 1。
    """
    r = bc_heterogeneity_chisq([(10, 0), (0, 10)])
    assert r["df"] == 1
    assert r["chi2"] == pytest.approx(20.0)
    assert r["p"] < 1e-4
    assert r["min_expected"] == pytest.approx(5.0)


def test_degenerate_cases_do_not_explode():
    for strata in ([(0, 0), (0, 0)], [(5, 0), (3, 0)], [(7, 2)]):
        r = bc_heterogeneity_chisq(strata)
        assert r["p"] == 1.0 and r["chi2"] == 0.0


def test_min_expected_is_reported_so_small_cells_cannot_hide():
    r = bc_heterogeneity_chisq([(9, 1), (1, 1)])
    assert r["min_expected"] < 5.0        # ⇒ 報告裡要講「卡方近似在這裡不準」
    assert not r["degenerate"]


@pytest.mark.parametrize("x,df,want", [
    (3.841, 1, 0.05), (5.991, 2, 0.05), (7.815, 3, 0.05),
    (1.0, 1, 0.31731), (0.0, 3, 1.0), (11.345, 3, 0.01),
])
def test_chisq_tail_matches_published_critical_values(x, df, want):
    """零 scipy 的卡方上尾：對表定臨界值（誤差 < 5e-4）。"""
    from vacant.research import _chisq_sf
    assert math.isclose(_chisq_sf(x, df), want, abs_tol=5e-4)
