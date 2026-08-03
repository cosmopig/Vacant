"""脈衝攻擊與稽核盲區的迴歸判準（2026-08-03）。

這一輪要回答兩個問題：脈衝攻擊是什麼、它的具體影響是什麼。結論只有在
機制本身被釘死時才有意義，所以下面每一支都對應一個「若退回去就會讓結論
不成立」的性質：

  1. 脈衝相位機真的在放電/蓄積之間切換，且切換依據是**最終**的 bad 值
     （selective 或預算把一筆改成乾淨時，那筆要算蓄積不算放電）。
  2. 既有三種策略必須**逐位重現改動前的數字**。這條不是形式主義：
     SimConfig.digest() 同時是亂數種子，而它原本雜湊全部欄位，於是
     「為了新實驗多加一個選用參數」就換掉了整條隨機序列，E1–E16 的
     數字全部無聲位移。修法是讓後加的欄位在維持預設時不進摘要。
  3. 盲區的語意是「同源檢查者共同看不到」：落在盲區的壞交付，評審與稽核
     同時放行。這與 reviewer_correlation（有時一起錯）不同。
  4. 反應延遲的儀器（bursts）記錄的是「這一波第一次作惡」到「第一次被抓」，
     沒被抓過的波要算進 bursts_never_caught。
  5. 等預算對照真的把作惡總量鎖住。
"""
from __future__ import annotations

import pytest

from vacant.entrycost import SimConfig, simulate


def _cfg(**kw) -> SimConfig:
    base = dict(rounds=400, seed="t-pulse")
    base.update(kw)
    return SimConfig(**base)


# ── 1. 這次改動不准動到既有結論 ──────────────────────────────────────
#
# 下面這組數字是 2026-08-03 改動**之前**的實際輸出（seed="baseline"、
# rounds=400）。釘死它們，因為新增選用參數曾經無聲地擾動過既有結果：
# SimConfig.digest() 是亂數種子，而它原本雜湊全部欄位，於是多一個欄位
# 就換掉整條隨機序列。修法是讓後加的欄位在維持預設時不進摘要。
# 這一支若失敗，代表 E1–E16 的數字全部要重跑。
_FROZEN = {
    "whitewash": dict(kw=dict(strategy="whitewash"),
                      expect=dict(accepted_bad=0, caught=40, clean_paid=0,
                                  identities_used=41, routed_to_attacker=40),
                      digest="3e76f381c172"),
    "patient": dict(kw=dict(strategy="patient", build_rounds=15),
                    expect=dict(accepted_bad=1, caught=1, clean_paid=16,
                                identities_used=1, routed_to_attacker=18),
                    digest="2df9edf9f532"),
    "sybil": dict(kw=dict(strategy="sybil"),
                  expect=dict(accepted_bad=0, caught=40, clean_paid=0,
                              identities_used=401, routed_to_attacker=40),
                  digest="4a1cfc7d0e8d"),
}


@pytest.mark.parametrize("name", sorted(_FROZEN))
def test_existing_strategies_reproduce_pre_change_numbers(name):
    spec = _FROZEN[name]
    r = simulate(SimConfig(rounds=400, seed="baseline", **spec["kw"]))
    assert r["config_digest"] == spec["digest"], (
        f"{name} 的 config digest 變了（{r['config_digest']} != {spec['digest']}）"
        "——亂數種子被擾動，既有實驗數字會全部位移")
    for k, want in spec["expect"].items():
        assert r[k] == want, f"{name} 的 {k}：{r[k]} != {want}（改動前的值）"


# ── 2. 脈衝相位機 ────────────────────────────────────────────────────
def test_pulse_burst_bounds_consecutive_defections():
    """一波放電最多 burst 筆——相位機若壞掉，脈衝會退化成 whitewash。"""
    B = 3
    r = simulate(_cfg(strategy="pulse", pulse_burst=B, pulse_recover=8,
                      blindspot=1.0))          # 盲區拉滿讓它活得夠久，才看得到多波
    assert r["n_bursts"] >= 2, "盲區拉滿時應該要能跑完不只一波"
    assert r["max_burst_hits"] <= B, (
        f"單波得手 {r['max_burst_hits']} 超過 burst={B}，相位機沒有把放電關掉")


def test_pulse_with_zero_recover_is_continuous():
    """recover=0 時脈衝退化成「一直作惡」——參數空間要包含既有策略作為特例。"""
    cont = simulate(_cfg(strategy="pulse", pulse_burst=3, pulse_recover=0,
                         blindspot=1.0))
    # 每一次被路由都作惡（見習期那幾筆除外）
    assert cont["defected"] >= cont["routed_to_attacker"] - 3, (
        f"recover=0 應該近乎每次都作惡：作惡 {cont['defected']} / "
        f"被路由 {cont['routed_to_attacker']}")


def test_selective_downgrade_counts_as_recovery_not_burst():
    """selective 把一筆改成乾淨時，那筆算蓄積不算放電。

    若算成放電，攻擊者會在低價值任務上「空放」掉整個 burst 額度，
    做出「選擇性攻擊比較弱」的假結論。
    """
    r = simulate(_cfg(strategy="pulse", pulse_burst=3, pulse_recover=5,
                      selective=True, high_value_ratio=0.2, blindspot=1.0))
    # 選擇性之下，得手的每一筆都必須是高價值
    assert r["accepted_bad"] == r["high_value_hits"], (
        f"選擇性攻擊卻有非高價值的得手：得手 {r['accepted_bad']}、"
        f"高價值 {r['high_value_hits']}")


# ── 3. 盲區語意 ──────────────────────────────────────────────────────
def test_blindspot_one_means_never_caught():
    """盲區＝1 時，稽核抽中也抓不到——這是「加更多檢查者也沒用」的形式化。"""
    r = simulate(_cfg(strategy="pulse", pulse_burst=3, pulse_recover=5,
                      blindspot=1.0, audit_rate=1.0))
    assert r["caught"] == 0, f"盲區拉滿卻還是抓到了 {r['caught']} 筆"
    assert r["defected"] == r["accepted_bad"], "盲區拉滿時作惡等於得手"
    assert r["blind_passes"] > 0, "應該要記錄到「抽中了但看不出來」的筆數"


def test_blindspot_zero_keeps_audit_oracle():
    """盲區＝0 且 audit_rate=1 時，稽核仍是 oracle：作惡必被抓。"""
    r = simulate(_cfg(strategy="pulse", pulse_burst=5, pulse_recover=5,
                      blindspot=0.0, audit_rate=1.0))
    assert r["accepted_bad"] == 0, (
        f"全稽核＋零盲區之下仍有 {r['accepted_bad']} 筆得手")
    assert r["blind_passes"] == 0


def test_blindspot_is_monotone_in_hits():
    """盲區越大，得手越多——這是本輪的核心宣稱，必須單調。"""
    hits = []
    for blind in (0.0, 0.5, 1.0):
        tot = sum(simulate(_cfg(strategy="pulse", pulse_burst=3, pulse_recover=8,
                                blindspot=blind, seed=f"mono{i}"))["accepted_bad"]
                  for i in range(6))
        hits.append(tot)
    assert hits[0] <= hits[1] <= hits[2], f"得手數對盲區不單調：{hits}"
    assert hits[2] > hits[0], f"盲區拉滿沒有比零盲區更嚴重：{hits}"


# ── 4. 反應延遲儀器 ──────────────────────────────────────────────────
def test_burst_instrumentation_shape():
    """bursts 的欄位要對得起來：波次、每波得手、沒被抓的波。"""
    r = simulate(_cfg(strategy="pulse", pulse_burst=3, pulse_recover=8,
                      blindspot=1.0))
    assert r["n_bursts"] >= 1
    assert r["bursts_never_caught"] <= r["n_bursts"]
    # 盲區拉滿＝從沒被抓過，所以每一波都是「沒被抓的波」，且無反應延遲可言
    assert r["bursts_never_caught"] == r["n_bursts"]
    assert r["react_lag_mean"] is None, "從沒被抓到卻算得出反應延遲"


# ── 5. 等預算對照 ────────────────────────────────────────────────────
@pytest.mark.parametrize("strategy", ["whitewash", "patient", "pulse"])
def test_defect_budget_caps_total_defections(strategy):
    """預算上限真的鎖住作惡總量——等預算對照的前提。"""
    BUDGET = 5
    r = simulate(_cfg(strategy=strategy, defect_budget=BUDGET,
                      blindspot=1.0, rounds=800))
    assert r["defected"] <= BUDGET, (
        f"{strategy} 作惡 {r['defected']} 筆超過預算 {BUDGET}")


# ── 6. 決定性 ────────────────────────────────────────────────────────
def test_pulse_is_deterministic():
    """同一組參數必得同一個結果——沒有這條，任何比較都不成立。"""
    kw = dict(strategy="pulse", pulse_burst=3, pulse_recover=7,
              blindspot=0.4, audit_accuracy=0.8)
    a = simulate(_cfg(**kw))
    b = simulate(_cfg(**kw))
    assert a == b, "同參數兩次跑出不同結果"
