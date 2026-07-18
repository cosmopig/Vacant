"""Track A 四臂 harness 的確定性自驗（vacant/research.py）。

用 StubBrain + 合成任務（每類 10 題）鎖住指標與 H0 因果拆解的算術，
確保管線/統計不被改壞。數字為刻意設計、非實證（見 research.py docstring）。
"""

from __future__ import annotations

from vacant.research import (
    decompose,
    discordance,
    holm_adjust,
    mcnemar_exact,
    mcnemar_power,
    mcnemar_sample_size,
    metrics,
    paired_tost,
    run_suite,
    synthetic_suite,
    wilcoxon_exact,
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


def test_holm_adjust_basic_hand_calc():
    """課本例：p=[0.01,0.02,0.03,0.04,0.05] 依序乘 5,4,3,2,1 再取累積最大 → [0.05,0.08,0.09,0.09,0.09]（手算）。"""
    adj = holm_adjust([0.01, 0.02, 0.03, 0.04, 0.05])
    expected = [0.05, 0.08, 0.09, 0.09, 0.09]
    for got, exp in zip(adj, expected):
        assert abs(got - exp) < 1e-9


def test_holm_adjust_single_and_ties():
    """n=1 恆等；相同 p 值（ties）校正後仍需單調不減。"""
    assert holm_adjust([0.03]) == [0.03]
    adj = holm_adjust([0.05, 0.05])
    assert abs(adj[0] - 0.10) < 1e-9
    assert abs(adj[1] - 0.10) < 1e-9


def test_holm_adjust_empty_and_invalid():
    """空輸入回空列表；p 值超出 [0,1] 明確拋錯。"""
    assert holm_adjust([]) == []
    try:
        holm_adjust([0.5, 1.2])
        assert False, "should raise"
    except ValueError:
        pass
    try:
        holm_adjust([-0.1])
        assert False, "should raise"
    except ValueError:
        pass


def test_paired_tost_clear_equivalence_hand_calc():
    """d=[1]*5、界=(-2,2)：兩側各 P(K>=5|n=5,.5)=1/32=0.03125<alpha=0.05 → 判定等效（手算）。"""
    x = [1.0] * 5
    y = [0.0] * 5
    res = paired_tost(x, y, -2.0, 2.0, alpha=0.05)
    assert abs(res["p_lower"] - 1 / 32) < 1e-12
    assert abs(res["p_upper"] - 1 / 32) < 1e-12
    assert abs(res["p_tost"] - 1 / 32) < 1e-12
    assert res["equivalent"] is True


def test_paired_tost_boundary_ties_dropped():
    """d=[0,0,0,2,2,2]、界=(0,2)：邊界值整對剔除，兩側各剩 3 對，p=P(K>=3|3,.5)=0.125（手算）。"""
    x = [0.0, 0.0, 0.0, 2.0, 2.0, 2.0]
    y = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    res = paired_tost(x, y, 0.0, 2.0, alpha=0.05)
    assert abs(res["p_lower"] - 0.125) < 1e-12
    assert abs(res["p_upper"] - 0.125) < 1e-12
    assert res["equivalent"] is False


def test_paired_tost_all_zero_one_side_conservative():
    """d 全等於 low：下側配對全被剔除 → p_lower=1.0（保守，不宣稱等效）。"""
    x = [0.0, 0.0, 0.0]
    y = [0.0, 0.0, 0.0]
    res = paired_tost(x, y, 0.0, 5.0, alpha=0.05)
    assert res["p_lower"] == 1.0
    assert res["equivalent"] is False


def test_paired_tost_invalid_params():
    """low>=high、alpha 越界、長度不一、空輸入皆明確拋錯。"""
    try:
        paired_tost([1.0], [0.0], 2.0, 1.0)
        assert False, "should raise"
    except ValueError:
        pass
    try:
        paired_tost([1.0], [0.0], -1.0, 1.0, alpha=1.5)
        assert False, "should raise"
    except ValueError:
        pass
    try:
        paired_tost([1.0, 2.0], [0.0], -1.0, 1.0)
        assert False, "should raise"
    except ValueError:
        pass
    try:
        paired_tost([], [], -1.0, 1.0)
        assert False, "should raise"
    except ValueError:
        pass


def test_wilcoxon_exact_no_ties_hand_calc():
    """d=[1,2,3]（無 tie、無 0）：W+=6,W-=0；2^3=8 組合僅全負一組 s<=0，p=2*1/8=0.25（手算枚舉）。"""
    res = wilcoxon_exact([1.0, 2.0, 3.0])
    assert res["W_plus"] == 6.0
    assert res["W_minus"] == 0.0
    assert res["n_nonzero"] == 3
    assert abs(res["p_two_sided"] - 0.25) < 1e-12


def test_wilcoxon_exact_mixed_signs_hand_calc():
    """d=[1,-2,3]：W+=4,W-=2；枚舉 8 組合中 s<=2 者 3 組，p=2*3/8=0.75（手算枚舉）。"""
    res = wilcoxon_exact([1.0, -2.0, 3.0])
    assert res["W_plus"] == 4.0
    assert res["W_minus"] == 2.0
    assert abs(res["p_two_sided"] - 0.75) < 1e-12


def test_wilcoxon_exact_ties_midrank_hand_calc():
    """d=[1,-1,2]：|1| 同分→midrank 1.5,1.5；|2|→rank3。枚舉 8 組合 s<=1.5 者 3 組，p=0.75（手算）。"""
    res = wilcoxon_exact([1.0, -1.0, 2.0])
    assert abs(res["W_plus"] - 4.5) < 1e-12
    assert abs(res["W_minus"] - 1.5) < 1e-12
    assert abs(res["p_two_sided"] - 0.75) < 1e-12


def test_wilcoxon_exact_zero_drop_and_cap():
    """d=[0,0,1,-1]：兩個 0 被剔除，剩 [1,-1] 同分 midrank=1.5；枚舉得 p=2*3/4=1.5 → 封頂 1.0。"""
    res = wilcoxon_exact([0.0, 0.0, 1.0, -1.0])
    assert res["n_nonzero"] == 2
    assert abs(res["p_two_sided"] - 1.0) < 1e-12


def test_wilcoxon_exact_all_zero_and_invalid():
    """全零差值 → p=1.0（無資訊）；空輸入、長度不一、非零配對數>20 皆明確拋錯。"""
    res = wilcoxon_exact([0.0, 0.0, 0.0])
    assert res["n_nonzero"] == 0
    assert res["p_two_sided"] == 1.0
    try:
        wilcoxon_exact([])
        assert False, "should raise"
    except ValueError:
        pass
    try:
        wilcoxon_exact([1.0, 2.0], [1.0])
        assert False, "should raise"
    except ValueError:
        pass
    try:
        wilcoxon_exact([float(v) for v in range(1, 22)])  # 21 個非零差值
        assert False, "should raise"
    except ValueError:
        pass


def test_mcnemar_power_delta_zero_closed_form():
    """delta=0 的封閉解：z_beta=-z_{alpha/2} ⇒ power=Phi(-z_{alpha/2})=alpha/2，與 n、p_disc 無關（手算核對）。"""
    for n, p_disc, alpha in [(50, 0.3, 0.05), (10, 0.1, 0.05), (500, 0.5, 0.10)]:
        power = mcnemar_power(n, p_disc, 0.0, alpha=alpha)
        assert abs(power - alpha / 2.0) < 1e-6


def test_mcnemar_power_monotonic_in_n():
    """固定 p_disc、delta，power 隨 n 增加而遞增（漸近檢定力的方向性對照）。"""
    p1 = mcnemar_power(20, 0.3, 0.1, alpha=0.05)
    p2 = mcnemar_power(200, 0.3, 0.1, alpha=0.05)
    p3 = mcnemar_power(2000, 0.3, 0.1, alpha=0.05)
    assert p1 < p2 < p3
    assert p3 > 0.99


def test_mcnemar_power_invalid_params():
    """n<=0、p_disc 越界、|delta|>=p_disc、alpha 越界皆明確拋錯。"""
    try:
        mcnemar_power(0, 0.3, 0.1)
        assert False, "should raise"
    except ValueError:
        pass
    try:
        mcnemar_power(10, 1.5, 0.1)
        assert False, "should raise"
    except ValueError:
        pass
    try:
        mcnemar_power(10, 0.2, 0.3)
        assert False, "should raise"
    except ValueError:
        pass
    try:
        mcnemar_power(10, 0.2, 0.1, alpha=1.0)
        assert False, "should raise"
    except ValueError:
        pass


def test_mcnemar_sample_size_roundtrip():
    """round-trip：以求得的 n 代回 mcnemar_power 應達到（不小於）目標 power，n-1 則不高於 n 的檢定力。"""
    p_disc, delta, alpha, power = 0.3, 0.1, 0.05, 0.8
    n = mcnemar_sample_size(p_disc, delta, alpha=alpha, power=power)
    assert n > 0
    achieved = mcnemar_power(n, p_disc, delta, alpha=alpha)
    assert achieved >= power - 1e-4
    if n > 1:
        achieved_minus = mcnemar_power(n - 1, p_disc, delta, alpha=alpha)
        assert achieved_minus <= achieved


def test_mcnemar_sample_size_invalid_params():
    """delta=0、|delta|>=p_disc、p_disc/alpha/power 越界皆明確拋錯。"""
    try:
        mcnemar_sample_size(0.3, 0.0)
        assert False, "should raise"
    except ValueError:
        pass
    try:
        mcnemar_sample_size(0.2, 0.3)
        assert False, "should raise"
    except ValueError:
        pass
    try:
        mcnemar_sample_size(1.5, 0.1)
        assert False, "should raise"
    except ValueError:
        pass
    try:
        mcnemar_sample_size(0.3, 0.1, alpha=1.5)
        assert False, "should raise"
    except ValueError:
        pass
    try:
        mcnemar_sample_size(0.3, 0.1, power=1.5)
        assert False, "should raise"
    except ValueError:
        pass
