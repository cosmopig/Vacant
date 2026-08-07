"""多向環境模擬的判準（M1–M5 的單元版本）。

這支模擬的結論會被寫進設計決策與展場說法，所以它自己必須先可信：
確定性、走真實機制、**在可以手算的極端參數下對得上理論值**。

最後一條是這裡最重要的：`test_matches_independent_theory` 是模擬的自我檢核——
通道全部關掉時，共同放行率必須回到 β + (1−β)·(1−acc)^K。對不上就代表模擬裡
還有沒被指認的相關來源，那時候任何「多向降低了相關性」的宣稱都不成立。
"""

from __future__ import annotations

import json

from vacant.multiway import MWConfig, simulate_mw

ROUNDS = 130
SEEDS = ["u0", "u1", "u2", "u3", "u4"]
BOTH = dict(seal_reviews=True, hide_reputation=True)
ONEWAY = dict(seal_reviews=False, hide_reputation=False)


def _pool(**kw) -> dict:
    """跨 seed pool 計數再算比率——單 run 的壞交付只有數十筆，比率噪音太大。"""
    runs = [simulate_mw(MWConfig(rounds=ROUNDS, seed=s, **kw)) for s in SEEDS]
    bad = sum(r["bad_reviewed"] for r in runs)
    return {
        "bad": bad,
        "all_miss": sum(r["all_miss_n"] for r in runs) / bad,
        "miss": sum(r["miss_votes"] for r in runs) / sum(r["total_votes"] for r in runs),
        "accepted_bad": sum(r["accepted_bad"] for r in runs),
        "quality": sum(r["accepted_good"] for r in runs) / sum(r["accepted_total"] for r in runs),
        "unassigned": sum(r["unassigned"] for r in runs),
        "runs": runs,
    }


def test_simulation_is_deterministic():
    """同 seed 同結果——否則跨臂比較沒有意義。"""
    cfg = MWConfig(rounds=80, seed="det", **BOTH)
    a, b = simulate_mw(cfg), simulate_mw(cfg)
    assert a["route_line"] == b["route_line"]
    for k in ("accepted_bad", "all_miss_n", "caught", "bad_reviewed"):
        assert a[k] == b[k], f"{k} 不可重現"


def test_matches_independent_theory_when_channels_are_closed():
    """通道全關 ⇒ 共同放行率回到 β + (1−β)(1−acc)^K。**模擬的自我檢核。**

    對不上就代表模擬裡還有沒被指認的相關來源，M1 的分解會是假的。
    """
    for beta in (0.0, 0.3):
        p = _pool(blindspot=beta, reviewer_accuracy=0.7, **BOTH)
        theory = beta + (1 - beta) * 0.3 ** 3
        assert abs(p["all_miss"] - theory) < 0.06, (
            f"β={beta}：觀測 {p['all_miss']:.4f} vs 理論 {theory:.4f}"
            f"（n={p['bad']}）——通道全關卻仍有殘餘相關"
        )


def test_architecture_manufactures_co_blindness():
    """單向架構在 β=0（模型家族沒有共同盲區）時仍造出共同盲區。

    這是整個階段的核心主張：我們量到的「共同盲區」有一部分是架構自己造的。
    判準寫成「明顯大於獨立預測」而不是一個精確值——精確值隨 cascade_p /
    authority_w 而變，而那兩個參數沒有外部錨定。
    """
    one = _pool(blindspot=0.0, **ONEWAY)
    multi = _pool(blindspot=0.0, **BOTH)
    assert one["all_miss"] > multi["all_miss"] + 0.15, (
        f"單向 {one['all_miss']:.4f} vs 多向 {multi['all_miss']:.4f}"
    )
    assert multi["all_miss"] < 0.10, "β=0 時多向應該接近 (1−acc)^3 = 0.027"


def test_channel_strength_zero_equals_multiway():
    """單向架構但把兩條汙染通道的強度設成 0，數值上必須等於多向。

    這條擋的是「開關其實還改了別的東西」——若不等，兩臂的差就不只是通道分離。
    """
    off = _pool(blindspot=0.3, cascade_p=0.0, authority_w=0.0, **ONEWAY)
    multi = _pool(blindspot=0.3, **BOTH)
    assert abs(off["all_miss"] - multi["all_miss"]) < 0.05
    assert abs(off["miss"] - multi["miss"]) < 0.05


def test_sealing_alone_does_not_change_the_marginal_much():
    """密封切斷的是**相關**不是**準確率**：邊際漏看率不該被它大幅改動。

    這條分開兩件事：權威通道會把邊際推高（評審放水），瀑布通道主要動的是
    聯合分布。混在一起講就會把「評審變準了」和「評審不再互相抄」搞混。
    """
    base = _pool(blindspot=0.3, authority_w=0.0, seal_reviews=False,
                 hide_reputation=False)
    seal = _pool(blindspot=0.3, authority_w=0.0, seal_reviews=True,
                 hide_reputation=False)
    assert abs(base["miss"] - seal["miss"]) < 0.12
    assert seal["all_miss"] < base["all_miss"]


def test_blindspot_is_not_reachable_by_channel_separation():
    """通道分離改不動 β：把 β 拉到 1，兩臂的共同放行率都是 1。

    偵測機率是單一乘積 (1−β)×抽樣率×準確率，三者同軸——不可以把
    「拆掉架構相關性」講成「降低了盲區」。
    """
    for kw in (ONEWAY, BOTH):
        p = _pool(blindspot=1.0, **kw)
        assert p["all_miss"] == 1.0
        assert p["accepted_bad"] > 0


def test_declination_costs_coverage():
    """拒絕原語有代價：會出現沒有人接的任務。只報好處不報成本是不誠實的。"""
    p = _pool(blindspot=0.3, declination=True, decliner="honest", **BOTH)
    assert p["unassigned"] > 0
    q = _pool(blindspot=0.3, **BOTH)
    assert q["unassigned"] == 0


def test_cherrypicker_is_not_caught_by_calibration():
    """**反例測試**：只挑簡單任務的 agent，在 calibration 兩種計分下都不難看。

    這條測的是設計的失敗而不是成功——如果哪天它開始失敗（挑食者真的被
    calibration 抓到了），那是好消息，但要先確認不是把判準改鬆了。
    擋這個博弈的量是 coverage（接受率），不是 calibration。
    """
    runs = [simulate_mw(MWConfig(rounds=ROUNDS, seed=s, blindspot=0.3,
                                 declination=True, decliner="cherrypick", **BOTH))
            for s in SEEDS]
    naive = [r["per_agent"]["h0"]["calib_naive"] for r in runs]
    cover = [r["per_agent"]["h0"]["coverage"] for r in runs if r["per_agent"]["h0"]["coverage"]]
    assert sum(naive) / len(naive) > 0.0, "挑食者在計數版 calibration 上是正分"
    assert sum(cover) / len(cover) < 0.75, "而 coverage 明顯偏低——這才是抓得到它的量"


def test_intervention_budget_is_hard():
    """等預算：介入次數**恰好**等於預算，不是小於等於（除非一次都沒開火）。"""
    for human in ("terminal_random", "terminal_flag", "midcourse_flag"):
        for s in SEEDS:
            r = simulate_mw(MWConfig(rounds=ROUNDS, seed=s, blindspot=0.3,
                                     human=human, human_round=40, human_budget=1,
                                     **BOTH))
            assert r["interventions_fired"] in (0, 1)
            if r["interventions_fired"] == 1:
                assert r["fire_round"] is not None and r["fire_round"] >= 40
            else:
                assert r["fire_round"] is None


def test_midcourse_halt_blocks_before_acceptance():
    """中途介入與末端稽核的機制差別：前者擋得下來，後者只補扣分。"""
    mid = [simulate_mw(MWConfig(rounds=ROUNDS, seed=s, blindspot=0.0,
                                audit_rate=0.0, human="midcourse_flag",
                                human_round=30, **BOTH)) for s in SEEDS]
    ter = [simulate_mw(MWConfig(rounds=ROUNDS, seed=s, blindspot=0.0,
                                audit_rate=0.0, human="terminal_flag",
                                human_round=30, **BOTH)) for s in SEEDS]
    fired_m = [r for r in mid if r["interventions_fired"] == 1]
    fired_t = [r for r in ter if r["interventions_fired"] == 1]
    assert fired_m and fired_t, "測試前提：兩臂都要有開火的 seed"
    # 同樣抓到一筆壞的，中途臂會少接受一筆（audit_rate=0 讓常規抽樣完全不干擾）
    assert sum(r["accepted_bad"] for r in fired_m) <= sum(r["accepted_bad"] for r in fired_t)


def test_rows_land_on_disk(tmp_path):
    """鐵律 3：全 I/O JSONL 落盤。每一輪一行，欄位齊全。"""
    p = tmp_path / "rows.jsonl"
    r = simulate_mw(MWConfig(rounds=40, seed="io", **BOTH), log_path=p)
    rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 40
    for k in ("round", "to", "bad", "blind", "votes", "audit_ran", "caught",
              "accepted", "dispersed"):
        assert k in rows[0], k
    assert r["route_line"] and len(r["route_line"]) == 40
