"""`mcnemar_n_required` 要**又對又跑得完**。

這支在架構裡承重什麼
────────────────────
預註冊的事前檢定力表靠它。2026-09-19 寫 R535 預註冊時撞到兩次「10 分鐘未收斂」：
舊版從 n=1 線性掃到 `n_max=20000`，而 `mcnemar_power` 是全枚舉的精確檢定、
大致 O(n²)（實測 n=400 要 2.98 s）⇒ 那個預設從來不是一個可用的值。

改成倍增＋二分之後，**正確性不准退**：回傳的 n 必須是真的最小。
這裡用三個獨立算出來的答案釘死。

⚠ 另記一個**差點做錯**的設計：本來想用「常態近似 n > n_max ⇒ 精確 n > n_max」
來快速失敗，實測發現近似**方向不固定**——
`p_disc=0.40, ψ=0.875` 近似 42.2 但精確只要 41（高估），
而 ψ=0.75 近似 95.1 精確 98（低估）。拿它當單邊守衛會把「其實做得到」誤判成
「做不到」。所以近似只進錯誤訊息，不進判斷。下面 `test_the_normal_approximation_is_not_a_bound`
把這件事釘住，免得有人再「優化」一次。
"""
from __future__ import annotations

import statistics
import time

import pytest

from vacant_network.research import mcnemar_n_required, mcnemar_power

# (p_disc, psi, alpha, power, 期望 n)。獨立算出來的，不是從實作回填的。
KNOWN = [
    (0.40, 0.875, 0.025, 0.80, 41),     # Δ=+30pp
    (0.40, 0.750, 0.025, 0.80, 98),     # Δ=+20pp
]


@pytest.mark.parametrize("p_disc,psi,alpha,power,want", KNOWN)
def test_returns_the_true_minimum(p_disc, psi, alpha, power, want):
    n = mcnemar_n_required(p_disc, psi, alpha=alpha, power=power)
    assert n == want
    # 最小性要**當場證明**，不是相信回傳值
    assert mcnemar_power(n, p_disc, psi, alpha=alpha) >= power
    assert mcnemar_power(n - 1, p_disc, psi, alpha=alpha) < power


@pytest.mark.parametrize("p_disc,psi,alpha,power,want", KNOWN)
def test_it_finishes_fast(p_disc, psi, alpha, power, want):
    """倍增＋二分 ⇒ 秒級。這條紅了代表有人改回線性掃描。"""
    t0 = time.time()
    mcnemar_n_required(p_disc, psi, alpha=alpha, power=power)
    assert time.time() - t0 < 20, "太慢——是不是又變成線性掃描了"


def test_unreachable_target_raises_with_a_usable_hint():
    """達不到要丟例外，而且訊息要**說得出大概要多少**。"""
    with pytest.raises(ValueError) as e:
        mcnemar_n_required(0.40, 0.5625, alpha=0.025, power=0.80, n_max=120)
    msg = str(e.value)
    assert "達不到" in msg
    assert "n≈" in msg, "沒給估計值，呼叫端不知道 n_max 要調到多少"


def test_h0_and_bad_power_still_rejected():
    with pytest.raises(ValueError):
        mcnemar_n_required(0.40, 0.5)            # ψ=0.5 是 H0
    with pytest.raises(ValueError):
        mcnemar_n_required(0.40, 0.75, power=0.0)
    with pytest.raises(ValueError):
        mcnemar_n_required(0.40, 0.75, power=1.5)


def test_the_normal_approximation_is_not_a_bound():
    """⚠ 釘住那個**差點做錯**的事：近似高估與低估都會發生。

    有人若想拿它當單邊守衛去快速失敗，這一條會提醒他方向不固定。
    """
    nd = statistics.NormalDist()

    def approx(p_disc, psi, power=0.80, alpha=0.025):
        d = p_disc * (2 * psi - 1)
        return ((nd.inv_cdf(1 - alpha / 2) + nd.inv_cdf(power)) ** 2) * p_disc / (d * d)

    over = approx(0.40, 0.875)      # 精確 41
    under = approx(0.40, 0.750)     # 精確 98
    assert over > 41, f"近似不再高估了（{over:.1f}）——這條註記要重寫"
    assert under < 98, f"近似不再低估了（{under:.1f}）——這條註記要重寫"


def test_n_max_default_is_affordable():
    """`n_max` 預設不准回到 20000：單次 n=20000 的呼叫要數小時。"""
    import inspect
    sig = inspect.signature(mcnemar_n_required)
    assert sig.parameters["n_max"].default <= 4000
