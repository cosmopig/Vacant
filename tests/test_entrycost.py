"""入場成本模擬的判準（2026-07-26 實驗套件）。

這支模擬的結論會被寫進設計決策，所以它自己必須先可信：
確定性、走真實機制、極端參數下的行為符合機制的定義。
"""

from __future__ import annotations

from vacant.entrycost import EntryPolicy, SimConfig, simulate


def test_simulation_is_deterministic():
    """同 seed 同結果——否則跨格比較沒有意義。"""
    cfg = SimConfig(rounds=60, seed="det")
    a, b = simulate(cfg), simulate(cfg)
    for k in ("accepted_bad", "caught", "clean_paid", "identities_used",
              "routed_to_attacker"):
        assert a[k] == b[k], f"{k} 不可重現：{a[k]} vs {b[k]}"


def test_full_audit_blocks_every_defection():
    """p=1.0 時每一次作惡都會被抓——稽核錨的定義性質。"""
    r = simulate(SimConfig(rounds=120, audit_rate=1.0, strategy="patient",
                           build_rounds=3, seed="full"))
    assert r["accepted_bad"] == 0


def test_probation_forced_audit_blocks_whitewash():
    """見習期強制稽核是擋洗白的那個機制：m=0 會漏，m>=1 不會。

    這條是 E3 的單元版本——E3 掃描顯示全部防禦價值都在 m=0→1 這一步。
    """
    leaky = simulate(SimConfig(rounds=200, probation_m=0, audit_rate=0.05,
                               strategy="whitewash", seed="m0"))
    tight = simulate(SimConfig(rounds=200, probation_m=1, audit_rate=0.05,
                               strategy="whitewash", seed="m0"))
    assert leaky["accepted_bad"] > 0
    assert tight["accepted_bad"] == 0


def test_reviewer_accuracy_is_load_bearing():
    """評審準確率降低必須讓攻擊者收益上升——否則模擬沒有建模到互審。

    E12 的單元版本：這是整組模擬最重要的敏感度參數。
    """
    good = simulate(SimConfig(rounds=300, audit_rate=0.05, reviewer_accuracy=1.0,
                              strategy="patient", build_rounds=15, seed="acc"))
    blind = simulate(SimConfig(rounds=300, audit_rate=0.05, reviewer_accuracy=0.0,
                               strategy="patient", build_rounds=15, seed="acc"))
    assert blind["accepted_bad"] > good["accepted_bad"]


def test_endorse_liability_damages_honest_endorsers():
    """背書連坐必須真的傷到背書者——這是它的代價，不可只報好處。"""
    none_ = simulate(SimConfig(rounds=150, audit_rate=0.05, strategy="whitewash",
                               entry=EntryPolicy("endorse", endorse_liability=1.0),
                               seed="end"))
    hard = simulate(SimConfig(rounds=150, audit_rate=0.05, strategy="whitewash",
                              entry=EntryPolicy("endorse", endorse_liability=0.5),
                              seed="end"))
    assert none_["honest_damage"] == 0.0
    assert hard["honest_damage"] > 0.0


def test_roi_is_none_when_cost_is_zero():
    """成本為 0 時 ROI 不可寫成一個數字——「入場免費」是有意義的結論，
    但把它折成 inf 或 0 都會誤導。"""
    r = simulate(SimConfig(rounds=60, strategy="whitewash", seed="roi"))
    if r["cost"] == 0:
        assert r["roi"] is None
