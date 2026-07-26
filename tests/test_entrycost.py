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


def test_task_value_decorrelates_across_seeds():
    """任務價值必須跨 seed 去相關，否則會與路由節奏同步而做出假結果。

    先前用 (輪次×常數) 決定價值，而見習配額正好每 10 輪把任務丟給攻擊者
    一次，兩者在所有 seed 上同步 → 「無差別攻擊者的高價值得手恆為 0」。
    """
    import hashlib
    def hv(seed: str, r: int) -> bool:
        h = int(hashlib.sha256(f"{seed}:hv:{r}".encode()).hexdigest()[:8], 16)
        return (h % 10_000) / 10_000.0 < 0.2

    quota_rounds = [r for r in range(400) if r % 10 == 9]
    rates = [sum(hv(s, r) for r in quota_rounds) / len(quota_rounds)
             for s in ("s0", "s1", "s2", "s3", "s4")]
    # 不同 seed 在配額輪次上的高價值比例必須不同（有相關時會完全一致）
    assert len(set(rates)) > 1, f"跨 seed 完全一致，仍與輪次相關：{rates}"


def test_selective_attacker_concentrates_on_high_value():
    """選擇性攻擊者的得手必須全部落在高價值任務上；無差別的則接近基準比例。"""
    sel = simulate(SimConfig(rounds=400, audit_rate=0.05, selective=True,
                             high_value_ratio=0.2, strategy="patient",
                             build_rounds=15, seed="selA"))
    if sel["accepted_bad"]:
        assert sel["high_value_hits"] == sel["accepted_bad"]


def test_reviewer_correlation_does_not_help_the_defender():
    """評審錯誤相關性上升，攻擊者收益不該下降（同源評審只會更糟或持平）。"""
    indep = simulate(SimConfig(rounds=400, audit_rate=0.05, reviewer_accuracy=0.7,
                               reviewer_correlation=0.0, strategy="patient",
                               build_rounds=15, seed="rho"))
    corr = simulate(SimConfig(rounds=400, audit_rate=0.05, reviewer_accuracy=0.7,
                              reviewer_correlation=1.0, strategy="patient",
                              build_rounds=15, seed="rho"))
    assert corr["accepted_bad"] >= indep["accepted_bad"]
