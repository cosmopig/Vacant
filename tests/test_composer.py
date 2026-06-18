"""驗證 Composer 邏輯：verify-fix / best-of-N 在隨機模型上應顯著贏過單次。

用一個「每次獨立 p 機率答對」的隨機模型（不靠 vacant，只測組合邏輯的數學）：
  plain ≈ p；vacant verify-fix(k) ≈ 1-(1-p)^k。p=0.4、k=3 → 0.40 vs 0.78。
"""

from __future__ import annotations

import random

from vacant.composer import Composer


def _stochastic_generate(p: float):
    def generate(_feedback: str) -> str:
        return "RIGHT" if random.random() < p else "WRONG"
    return generate


_CHECK = lambda a: a == "RIGHT"  # noqa: E731  客觀 verifier（yes/no）


def test_verifyfix_beats_plain():
    random.seed(1234)
    p, k, trials = 0.4, 3, 500
    plain_hits = vacant_hits = 0
    plain_calls = vacant_calls = 0
    for _ in range(trials):
        r = Composer(_stochastic_generate(p), _CHECK).plain()
        plain_hits += r.correct; plain_calls += r.calls
        r = Composer(_stochastic_generate(p), _CHECK).vacant(k)
        vacant_hits += r.correct; vacant_calls += r.calls
    plain_acc, vacant_acc = plain_hits / trials, vacant_hits / trials
    # verify-fix 應大幅勝出（理論 0.40 -> 0.78）
    assert plain_acc < 0.5
    assert vacant_acc > 0.7
    assert vacant_acc - plain_acc > 0.25
    # 早停：verify-fix 平均呼叫數應 < k（答對就收）
    assert vacant_calls / trials < k


def test_vacant_never_worse_when_solvable():
    """模型有非零成功率時，verify-fix 的正確率 >= plain（只多不少）。"""
    random.seed(7)
    p, k, trials = 0.25, 4, 400
    plain_hits = vacant_hits = 0
    for _ in range(trials):
        plain_hits += Composer(_stochastic_generate(p), _CHECK).plain().correct
        vacant_hits += Composer(_stochastic_generate(p), _CHECK).vacant(k).correct
    assert vacant_hits >= plain_hits


def test_vacant_cannot_invent_when_impossible():
    """誠實邊界：模型完全不會（p=0），verify-fix 也救不回（不會無中生有）。"""
    random.seed(0)
    c = Composer(_stochastic_generate(0.0), _CHECK)
    r = c.vacant(5)
    assert r.correct is False and r.calls == 5  # 試滿、仍錯
