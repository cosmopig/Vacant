"""文獻驅動的新攻擊面：迴歸判準（2026-08-07）。

這一輪加了三組東西，每一組都有一個「若退回去，報告的結論就不成立」的性質：

  A · Srivatsa model II–IV
      1. 四個模型在同一個工作週期上必須有**相同的期望作惡比例**——A1 宣稱
         「差的只有時間結構」，這句話成立與否全靠這一條。
      2. 四個模型必須真的不同（否則就是策略名打錯字靜默退化成 whitewash）。
      3. 未知策略名要爆掉，不准靜默退化。

  B · 評審端攻擊
      4. 對照臂真的是對照：`mode=none` 與 `collude_prob=0` 必須逐位相同，
         而且路由份額 ≈ 人口份額（沒有攻擊時不該有偏斜）。
      5. 防禦開關真的拆得掉：關掉 weight 內生 → 每票權重就是 1.0。
      6. 降權計數器只在**權重真的變小**時 +1（否則「哪一層承重」會被
         「這一層被呼叫過」冒充）。

  C · 見習期
      7. `probation_cap` / `probation_every` 真的送達 Registry；預設值
         必須與模組常數逐位相同（不然 E1–E24 全部要重跑）。

  另外：等預算比較要驗 `defected == BUDGET` 不是 `<=`（脈衝那一輪 4.5 節
  的教訓：`<=` 是恆成立的上界，永遠抓不到「預算根本沒綁住」）。
"""
from __future__ import annotations

import pytest

from vacant.collusion import CollusionConfig
from vacant.collusion import simulate as collude_sim
from vacant.entrycost import (KNOWN_STRATEGIES, SimConfig, _Agent, _geom,
                              _should_defect)
from vacant.entrycost import simulate as entry_sim
from vacant.registry import (PROBATION_EXPLORE_EVERY, PROBATION_SCORE_CAP,
                             Registry, ReviewDefenses)

OSC = ("pulse", "osc_exp", "osc_random", "osc_sine")


def _duty(strategy: str, seed: str, n: int = 4000) -> float:
    """把策略單獨跑 n 次，量它的作惡比例。

    **不經過路由**：路由會隨信譽變化而改變抽樣，量出來的就不是策略本身的
    工作週期，而是「策略 × 防禦」的合成量。要驗「四個模型工作週期相同」
    這個前提，就必須把策略從系統裡隔離出來量。
    """
    cfg = SimConfig(strategy=strategy, pulse_burst=5, pulse_recover=5,
                    probation_m=0, seed=seed)
    who = _Agent("attacker_g0", malicious=True)
    bad = 0
    for _ in range(n):
        d = _should_defect(who, cfg, {})
        who.deliveries += 1
        if cfg.strategy == "pulse":       # 相位機平時在主迴圈推進
            if d:
                who.phase_bad += 1
            else:
                who.phase_clean += 1
            if who.phase_bad >= cfg.pulse_burst and who.phase_clean >= cfg.pulse_recover:
                who.phase_bad = who.phase_clean = 0
        bad += int(d)
    return bad / n


# ── A1 的前提：四個模型的工作週期相同 ────────────────────────────────
@pytest.mark.parametrize("strategy", OSC)
def test_four_models_share_the_same_duty_cycle(strategy):
    """burst=recover=5 時四個模型的期望作惡比例都該是 0.5。

    Srivatsa 的 Figure 5 是好壞各半的方波；model III 的好度 g~U[0,1] 期望
    0.5；model IV 的 sin 平均 0.5。這一條若壞掉，A1 比較的就是「誰作惡比較
    多」而不是「時間結構」——那正是脈衝那一輪 4.5 節栽過的坑。
    """
    d = _duty(strategy, "duty0")
    assert 0.44 <= d <= 0.56, f"{strategy} 的工作週期 {d:.3f} 偏離 0.5 太多"


def test_four_models_are_actually_different():
    """四個模型必須產生不同的軌跡。

    `_should_defect` 的最後一行是 `return True`，所以策略名一旦打錯就會
    靜默退化成 whitewash（工作週期 1.0）——那份資料看起來完全正常。
    """
    res = {s: entry_sim(SimConfig(rounds=300, seed="diff", strategy=s,
                                  pulse_burst=5, pulse_recover=5,
                                  blindspot=0.5))["accepted_bad"]
           for s in OSC}
    assert len(set(res.values())) > 1, f"四個模型跑出同一個數字：{res}"


def test_unknown_strategy_fails_closed():
    with pytest.raises(ValueError):
        entry_sim(SimConfig(rounds=10, strategy="osc_typo"))
    assert set(OSC) <= set(KNOWN_STRATEGIES)


def test_geom_mean_is_near_target():
    """幾何取樣的期望值要接近 mean，否則 model II/III 的週期不是我們說的那個。"""
    for m in (2.0, 5.0, 10.0):
        vals = [_geom(i / 500.0, m) for i in range(1, 500)]
        got = sum(vals) / len(vals)
        assert 0.75 * m <= got <= 1.35 * m, f"mean={m} 實測 {got:.2f}"
    assert _geom(0.5, 1.0) == 1 and _geom(0.99, 0.0) == 1   # 退化值仍回 1


@pytest.mark.parametrize("strategy", OSC)
def test_osc_models_are_deterministic(strategy):
    kw = dict(rounds=250, seed="det", strategy=strategy, pulse_burst=4,
              pulse_recover=6, blindspot=0.4)
    assert entry_sim(SimConfig(**kw)) == entry_sim(SimConfig(**kw))


def test_srivatsa_cost_decomposes():
    """cost = build_y − misuse_x，且 cost = mean_bh − mean_tv。

    只報 cost 不報分量＝違反紀律 1：兩個攻擊可以有同一個 cost 卻在
    「濫用多少」與「付出多少」上完全不同。這一條把恆等式釘死，
    讓報告裡的分解不會在改碼後悄悄對不上。
    """
    r = entry_sim(SimConfig(rounds=400, seed="cost", strategy="osc_random",
                            pulse_burst=5, pulse_recover=5, blindspot=0.5))
    assert abs(r["srivatsa_cost"] - (r["build_y"] - r["misuse_x"])) < 1e-3
    assert abs(r["srivatsa_cost"] - (r["mean_bh"] - r["mean_tv"])) < 1e-3


@pytest.mark.parametrize("strategy", OSC)
def test_defect_budget_actually_binds(strategy):
    """等預算比較要驗 `==` 不是 `<=`（脈衝那一輪 4.5 節）。

    `<=` 是恆成立的上界，抓不到「預算根本沒綁住」——E19 就是這樣把一個
    「其實不是等預算」的比較當成等預算比較報出去的。
    """
    BUDGET = 1
    r = entry_sim(SimConfig(rounds=800, seed="bud", strategy=strategy,
                            pulse_burst=5, pulse_recover=5, blindspot=1.0,
                            defect_budget=BUDGET))
    assert r["defected"] == BUDGET, (
        f"{strategy} 只作惡 {r['defected']} 筆，預算 {BUDGET} 沒綁住 "
        "→ 這一格不是等預算比較")


# ── B 評審端 ─────────────────────────────────────────────────────────
def _c(**kw) -> CollusionConfig:
    base = dict(rounds=90, warmup=12, n_honest=4, n_colluders=2,
                defect_rate=0.5, seed="tc")
    base.update(kw)
    return CollusionConfig(**base)


def test_control_arm_has_no_routing_skew():
    """對照臂：所有人行為相同時，路由份額應該接近人口份額。

    這一條若壞掉，B 系列量到的所有偏斜都可能只是模擬本身的偏差。
    **必須把 defect_rate 也歸零**：共謀者若照樣交付壞東西，路由偏斜就是
    「被抓到而失去路由」的正常後果，不是模擬偏差——初版判準忘了這件事，
    量到 0.1 才發現。這正是「對照臂必須只差一個變數」的實例。
    """
    r = collude_sim(_c(mode="none", defect_rate=0.0))
    assert 0.6 <= r["route_share_ratio"] <= 1.6, (
        f"行為完全相同時路由就已經偏斜：{r['route_share_ratio']}")
    assert r["n_collusive_votes"] == 0
    # 反面：一旦共謀者真的交付壞東西，路由份額必須掉下來（懲罰有效）
    bad = collude_sim(_c(mode="none", defect_rate=1.0))
    assert bad["route_share_ratio"] < r["route_share_ratio"]


def test_zero_strength_equals_control():
    """collude_prob=0 必須與 mode=none 逐位相同——強度軸的原點要真的是原點。"""
    a = collude_sim(_c(mode="slander", collude_prob=0.0))
    b = collude_sim(_c(mode="none"))
    for k in ("honest_rep_end", "colluder_rep_end", "route_share_ratio",
              "accepted_bad", "mean_w_honest", "mean_w_colluder"):
        assert a[k] == b[k], f"{k}：強度 0 ({a[k]}) != 對照 ({b[k]})"


def test_defense_switches_are_really_switches():
    """關掉 weight 內生 → 每票權重恆為 1.0；全關 → 沒有任何降權命中。

    「拆掉它數字沒變＝裝飾」這條驗收的前提是**真的拆得掉**。
    """
    off = collude_sim(_c(mode="mixed",
                         defenses=ReviewDefenses(False, False, False, False)))
    assert off["mean_w_honest"] == 1.0 and off["mean_w_colluder"] == 1.0
    for bucket in ("downweight_on_colluder", "downweight_on_honest"):
        assert sum(off[bucket].values()) == 0, f"{bucket} 在全關時仍有命中"
    on = collude_sim(_c(mode="mixed"))
    assert on["mean_w_honest"] < 1.0, "全開時權重竟然沒有被內生化"


def test_downweight_counter_only_counts_real_reductions():
    """降權計數器只在權重**真的變小**時 +1。

    否則「這一層承重」會被「這一層被呼叫過」冒充——而 min(w, cap) 在
    w 已經比 cap 小的時候是個 no-op。
    """
    r = collude_sim(_c(mode="mixed", shared_controller=True))
    n_reviews = r["reviews_by_colluder"] + r["reviews_by_honest"]
    # 一筆 review 最多命中兩層：{自報同源, 行為同源} 是 elif 二選一，
    # 未證明遞減是另外一道。所以逐層都不得超過 review 總數。
    for layer in ("same_controller", "behavior", "unproven"):
        hits = (r["downweight_on_colluder"][layer]
                + r["downweight_on_honest"][layer])
        assert hits <= n_reviews, f"{layer} 命中 {hits} 次 > review 總數 {n_reviews}"
    # 自報同源開著且共謀者自報同一個 controller → 這一層必須真的打到人，
    # 否則「S 層在最有利條件下也是裝飾」這句話會沒有對照。
    assert r["downweight_on_colluder"]["same_controller"] > 0


def test_collusion_is_deterministic():
    assert collude_sim(_c(mode="mixed")) == collude_sim(_c(mode="mixed"))


def test_slander_actually_depresses_honest_reputation():
    """抹黑必須真的把誠實者壓低——這是 B 系列存在的理由，也是最容易在
    重構中悄悄失效的一條（例如 reviewer 抽樣改回「前三位誠實居民」）。"""
    base = collude_sim(_c(mode="none", rounds=150, warmup=15))
    slan = collude_sim(_c(mode="slander", rounds=150, warmup=15))
    assert slan["honest_rep_end"] < base["honest_rep_end"] - 0.05, (
        f"抹黑沒有壓低誠實者：{slan['honest_rep_end']} vs {base['honest_rep_end']}")


# ── C 見習期參數 ─────────────────────────────────────────────────────
def test_probation_params_reach_the_registry():
    reg = Registry()
    assert reg.probation_cap == PROBATION_SCORE_CAP
    assert reg.probation_every == PROBATION_EXPLORE_EVERY
    r2 = Registry(probation_cap=1.0, probation_every=3)
    assert r2.probation_cap == 1.0 and r2.probation_every == 3


def test_probation_knobs_change_outcomes():
    """三個旋鈕至少要動得到結果，否則 C1–C3 掃的是空氣。"""
    base = dict(rounds=400, seed="prob", strategy="whitewash", blindspot=0.25)
    ref = entry_sim(SimConfig(**base))
    variants = {
        "m": entry_sim(SimConfig(probation_m=16, **base)),
        "cap": entry_sim(SimConfig(probation_cap=1.0, **base)),
        "every": entry_sim(SimConfig(probation_every=2, **base)),
    }
    changed = [k for k, v in variants.items()
               if (v["accepted_bad"], v["routed_to_attacker"])
               != (ref["accepted_bad"], ref["routed_to_attacker"])]
    assert len(changed) >= 2, f"見習期旋鈕幾乎動不到結果：只有 {changed} 有反應"


def test_default_probation_params_do_not_shift_frozen_numbers():
    """顯式帶入預設值 == 不帶（digest 與結果都一樣）。

    這條擋的是「加參數順手改了預設」——那會讓 E1–E24 全部要重跑。
    """
    a = entry_sim(SimConfig(rounds=400, seed="baseline", strategy="patient",
                            build_rounds=15))
    b = entry_sim(SimConfig(rounds=400, seed="baseline", strategy="patient",
                            build_rounds=15, identity_cost=0.0,
                            probation_cap=PROBATION_SCORE_CAP,
                            probation_every=PROBATION_EXPLORE_EVERY))
    assert a["config_digest"] == b["config_digest"] == "2df9edf9f532"
    assert a["accepted_bad"] == b["accepted_bad"] == 1
