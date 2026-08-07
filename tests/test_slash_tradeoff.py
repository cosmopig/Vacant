"""slash 取捨參數 λ、悔改者臂、與配對前提的迴歸判準（2026-08-07）。

這一組判準守的是「1.1 的取捨曲線量得準」。每一支都對應一個**如果退回去，
曲線就會變成假的**的性質，並且在說明裡記下當時的錯誤數字，讓退化無法無聲發生。

背景（兩次相反方向的更正，都不是 bug）：

  1. 2026-07-26 獨立審查 P0-1：原本 slash 是「α、β 同乘 factor」，那嚴格保持
     證據比，數學上等於「老化一個半衰期」。實測後果——連 60 筆 0 分的破壞者
     每 slash 一次 mean **反而上升**（0.016→0.105）；高信譽者 slash 後 n 減半
     → UCB 探索項變大 → **被懲罰者更常被派工**。改成 β += (α+β)(1/f−1)。

  2. 2026-08-03 對抗式複驗：上面那個修正同時把 n 加倍，而 n 是回歸時間的
     指數係數（觀測 3.4 要 ~1e8 次觀測、觀測 48 要 ~1e66 次才回得來）。
     **懲罰把自己的赦免通道一起關小了**，而且資深者關得更小。

λ 不是第三次更正，是把這兩件事拆成兩個可以分別選的軸。所以判準要驗的是
**解耦本身**：均值下降與 λ 無關、n 上升與 λ 成正比。
"""
from __future__ import annotations

import pytest

from vacant.entrycost import SimConfig, _Agent, _should_defect, simulate
from vacant.reputation import Beta, Reputation, DIMS, get_slash_n_factor, slash_n_factor


# ── 1. 解耦本身 ──────────────────────────────────────────────────────
@pytest.mark.parametrize("lam", [0.0, 0.25, 0.5, 0.75, 1.0])
@pytest.mark.parametrize("factor", [0.5, 0.7, 0.85, 0.95])
def test_mean_drop_is_lambda_invariant(lam, factor):
    """後驗均值一律變成 factor 倍，**與 λ 無關**。

    這是取捨曲線成立的前提：如果 λ 也動到均值，那 λ 這條軸上量到的差異就
    分不出是「n 的效果」還是「罰得比較輕」，整條曲線失去意義。
    """
    b = Beta(alpha=9.0, beta=3.0)      # mean=0.75、n=10
    m0 = b.mean
    b.slash(factor, now=0, n_factor=lam)
    assert b.mean == pytest.approx(factor * m0, rel=1e-12), (
        f"λ={lam} 之下均值變成 {b.mean}，不是 factor×{m0}={factor * m0}")


@pytest.mark.parametrize("lam", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_n_rise_is_exactly_lambda_times_delta(lam):
    """有效觀測數上升 **λ·Δ**，Δ=(α+β)(1/f−1)。λ=0 時 n 完全不動。

    複驗的 4.6 節就是在說 n 這條軸：n 在回歸時間的指數上，所以
    「罰得重」與「赦得回」是同一個機制的兩面。λ 是把它們分開的把手。
    """
    b = Beta(alpha=9.0, beta=3.0)
    n0, s = b.n, b.alpha + b.beta
    delta = s * (1.0 / 0.5 - 1.0)
    b.slash(0.5, now=0, n_factor=lam)
    assert b.n == pytest.approx(n0 + lam * delta, rel=1e-12), (
        f"λ={lam}：n 從 {n0} 變成 {b.n}，預期 {n0 + lam * delta}")


def test_lambda_one_is_bit_identical_to_current_implementation():
    """λ=1 必須與 2026-07-26 P0-1 之後的實作**逐位相同**。

    不是「近似相同」：`f*(S/f)` 的浮點結果不保證等於 S，若把 λ=1 也走通式，
    既有凍結數字（tests/test_pulse.py 的 _FROZEN、B 層六情境判準）會位移，
    而且是無聲位移——那正是 2026-08-03 SimConfig.digest() 踩過的坑的翻版。
    """
    for a0, b0, f in [(9.0, 3.0, 0.5), (1.0, 1.0, 0.5), (100.0, 7.0, 0.83),
                      (2.5, 61.0, 0.95)]:
        got = Beta(alpha=a0, beta=b0)
        got.slash(f, now=0, n_factor=1.0)
        want_beta = b0 + (a0 + b0) * (1.0 / f - 1.0)
        assert got.alpha == a0, "λ=1 不該動 α"
        assert got.beta == want_beta, f"λ=1 的 β：{got.beta} != {want_beta}（逐位）"


@pytest.mark.parametrize("lam", [0.0, 0.5, 1.0])
def test_slash_stays_composable(lam):
    """兩次 slash(0.5) 的均值等於一次 slash(0.25)——P0-1 的三個性質之一，
    在所有 λ 下都必須保留（因為 m'=f·m 與 λ 無關）。"""
    two = Beta(alpha=9.0, beta=3.0)
    two.slash(0.5, now=0, n_factor=lam)
    two.slash(0.5, now=0, n_factor=lam)
    one = Beta(alpha=9.0, beta=3.0)
    one.slash(0.25, now=0, n_factor=lam)
    assert two.mean == pytest.approx(one.mean, rel=1e-12)


@pytest.mark.parametrize("lam", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_n_is_monotone_under_slash(lam):
    """n 只增不減。λ<1 把質量從 α 搬到 β（α 可低於先驗 1.0），但 α+β 不減，
    所以 `Beta.n` 的單調性不因 λ 而破。"""
    b = Beta(alpha=1.4, beta=1.1)
    for _ in range(5):
        n0 = b.n
        b.slash(0.5, now=0, n_factor=lam)
        assert b.n >= n0 - 1e-12, f"λ={lam}：n 從 {n0} 掉到 {b.n}"


def test_lambda_zero_erases_some_earned_credit():
    """λ<1 的代價要看得見：α 會被打折。

    現行版本（λ=1）的語意是「α 不動 → 已賺到的好評不被抹掉」。λ=0 買到
    「n 不上升」，付出的正是這一句。判準把代價釘死，免得日後有人把 λ=0
    講成純粹的改良。
    """
    b = Beta(alpha=9.0, beta=3.0)
    b.slash(0.5, now=0, n_factor=0.0)
    assert b.alpha == pytest.approx(4.5), "λ=0 應該把 α 乘上 factor"
    assert b.n == pytest.approx(10.0), "λ=0 的 n 應該完全不動"


def test_module_level_lambda_is_restored_after_context():
    """`slash_n_factor()` 是行程層級的全域。離開 context 必須還原，
    否則一次掃描會汙染同一個行程裡後面所有的 run（B 層六情境就是這樣被串跑的）。"""
    assert get_slash_n_factor() == 1.0
    with slash_n_factor(0.0):
        assert get_slash_n_factor() == 0.0
        rep = Reputation()
        rep.record_review("s", "main", "sim", {d: 1.0 for d in DIMS}, weight=10.0)
        n0 = rep.observations("s", "main", "sim")
        rep.slash("s", "main", "sim", 0.5)
        assert rep.observations("s", "main", "sim") == pytest.approx(n0)
    assert get_slash_n_factor() == 1.0


# ── 2. 配對前提：懲罰參數不進亂數種子 ────────────────────────────────
def test_punishment_params_do_not_perturb_the_random_world():
    """λ 與 slash_factor **不進 config digest**（＝不進亂數種子）。

    為什麼這條是判準而不是實作細節：`digest()` 同時是亂數種子，而
    `_peer_reviews` 的「這位評審有沒有看出來」是從那條序列抽的。若懲罰參數
    進了種子，掃描 λ 就同時換掉整個隨機世界，量到的差異會混著「λ 的效果」
    與「換了一組評審運氣」——配對比較直接失效，而且失效得無聲無息。

    代價要一起釘：digest 因此不能拿來當「同一個設定」的判準，那件事歸 run_key。
    """
    a = SimConfig(rounds=100, seed="x", strategy="pulse")
    b = SimConfig(rounds=100, seed="x", strategy="pulse",
                  slash_n_factor=0.0, slash_factor=0.9)
    assert a.digest() == b.digest(), "懲罰參數擾動了亂數種子，配對比較不成立"
    assert a.run_key() != b.run_key(), "run_key 必須分得出兩個不同設定"


def test_default_config_digest_unchanged_by_new_fields():
    """新增 slash_n_factor / slash_factor 不得位移既有實驗的隨機序列。

    2026-08-03 加入脈衝與盲區參數時踩過這個坑：多一個欄位就換掉整條序列，
    E1–E16 的數字會在下次重跑時全部無聲位移。下面三個 digest 是
    tests/test_pulse.py 釘死的改動前實際值。
    """
    assert SimConfig(rounds=400, seed="baseline",
                     strategy="whitewash").digest() == "3e76f381c172"
    assert SimConfig(rounds=400, seed="baseline", strategy="patient",
                     build_rounds=15).digest() == "2df9edf9f532"
    assert SimConfig(rounds=400, seed="baseline",
                     strategy="sybil").digest() == "4a1cfc7d0e8d"


# ── 3. 悔改者臂 ──────────────────────────────────────────────────────
def test_repent_and_persist_are_identical_before_the_first_slash():
    """悔改者與頑固者在被抓之前的行為必須逐筆相同。

    兩臂的差別只准是「被抓之後怎麼辦」。如果連被抓之前都不一樣，
    排除軸與贖回軸就跑在不同的攻擊姿態上，兩條曲線不能並排看。
    """
    rep_cfg = SimConfig(strategy="repent")
    per_cfg = SimConfig(strategy="patient", build_rounds=0)
    for deliveries in range(0, 8):
        a = _Agent("a", malicious=True)
        a.deliveries = deliveries
        b = _Agent("b", malicious=True)
        b.deliveries = deliveries
        assert _should_defect(a, rep_cfg, {}) == _should_defect(b, per_cfg, {}), (
            f"deliveries={deliveries} 時兩臂的作惡決定不同")


def test_repent_stops_defecting_after_the_first_slash():
    """悔改者被 slash 之後**永久**只交好貨——沒有這一條就量不到贖回，
    只量得到排除（`accepted_bad_after_slash` 恆為 0 是它的定義）。"""
    r = simulate(SimConfig(rounds=600, seed="p1", strategy="repent",
                           blindspot=0.0))
    assert r["first_slash_round"] is not None, "這個 seed 應該要被抓到過"
    assert r["accepted_bad_after_slash"] == 0, (
        f"悔改者在被 slash 之後又得手了 {r['accepted_bad_after_slash']} 筆")


def test_never_caught_is_not_the_same_as_never_returned():
    """「沒被抓過」與「被抓了但沒回來」必須分得開。

    複驗推翻 pulse.starvation 的方式正是這個混淆：原始證據說「被抓過的 16 個
    seed 之後都零路由」，但同一格裡**從未被抓**的 14 個 seed 也一樣停擺，
    所以那 16/16 無法歸因於被抓。儀器層面要先分得開，聚合時才有辦法不混。
    """
    r = simulate(SimConfig(rounds=200, seed="p2", strategy="repent",
                           blindspot=1.0, audit_rate=0.0))
    assert r["first_slash_round"] is None, "audit_rate=0 不該有人被抓"
    assert r["rounds_to_next_route"] is None
    assert r["rounds_after_slash"] is None, (
        "沒被抓過的 seed 不該有『還剩幾輪可翻身』——那是右設限的分母，"
        "填 0 會讓它被當成『被抓了但沒回來』")


def test_lambda_changes_obs_at_slash_but_not_score_at_slash():
    """整條模擬層級的解耦驗證：同一個 seed 換 λ，**被 slash 的輪次與當下的
    信譽分完全相同**，只有觀測數不同。

    這是配對設計＋解耦兩件事同時成立的證據。實測（seed=p1、rounds=800、
    slash_factor=0.5）：first_slash_round 都是 39、score_at_slash 都是 0.2887，
    而 obs_at_slash 是 λ=0 → 0.7186、λ=1 → 3.4373（差 4.78 倍）。後果直接可見：
    λ=0 這一臂在 slash 後第 10 輪就再被路由、之後拿到 74 次工作；λ=1 這一臂
    在剩下的 761 輪裡**一次都沒有再被路由**。

    注意 `rounds` 本身進 digest（它該進），所以換輪數會換掉整條隨機序列——
    這組數字只在 rounds=800 成立。第一版判準抄了 rounds=1200 的
    score_at_slash=0.2917，跑起來是 0.2887；那個落差不是 bug，是提醒：
    釘數字時連跑出它的參數一起釘。
    """
    kw = dict(rounds=800, seed="p1", strategy="repent", blindspot=0.0,
              slash_factor=0.5)
    a = simulate(SimConfig(slash_n_factor=0.0, **kw))
    b = simulate(SimConfig(slash_n_factor=1.0, **kw))
    assert a["first_slash_round"] == b["first_slash_round"] == 39
    assert a["score_at_slash"] == b["score_at_slash"] == 0.2887
    assert a["obs_at_slash"] == 0.7186 and b["obs_at_slash"] == 3.4373, (
        f"obs_at_slash：λ=0 → {a['obs_at_slash']}、λ=1 → {b['obs_at_slash']}"
        "（預期 0.7186 / 3.4373）")
    assert a["rounds_to_next_route"] == 10 and b["rounds_to_next_route"] is None, (
        "λ 對『回不回得來』的效果消失了："
        f"λ=0 → {a['rounds_to_next_route']}、λ=1 → {b['rounds_to_next_route']}")
    assert a["routes_after_slash"] == 74 and b["routes_after_slash"] == 0


def test_slash_factor_is_honoured_by_the_simulation():
    """`slash_factor` 真的走進 `Registry.apply_slash`——否則整條 f 軸是裝飾。

    判準用「換 f 會改變被 slash 當下的信譽分」而不是硬編某個數字，
    因為 f 的絕對值取決於當時累積的評審，會隨其他機制改動而變。
    """
    kw = dict(rounds=800, seed="p1", strategy="repent", blindspot=0.0)
    lo = simulate(SimConfig(slash_factor=0.5, **kw))["score_at_slash"]
    hi = simulate(SimConfig(slash_factor=0.95, **kw))["score_at_slash"]
    assert lo < hi, f"f=0.5 罰得應該比 f=0.95 重：{lo} vs {hi}"
