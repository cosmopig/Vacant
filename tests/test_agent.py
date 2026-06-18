"""產品門面 Vacant：verify-fix 讓同一顆腦更好 + 每次互動可究責（簽章鏈可驗）。"""

from __future__ import annotations

import random

from vacant.agent import Vacant, checkable_cases


class MockBrain:
    name = "mock"

    def __init__(self, p: float) -> None:
        self.p = p

    def generate(self, prompt: str) -> str:
        return "RIGHT" if random.random() < self.p else "WRONG"


_CHECK = lambda a: a == "RIGHT"  # noqa: E731


def test_vacant_beats_plain():
    random.seed(11)
    n = 300
    p_hits = v_hits = 0
    for _ in range(n):
        p_hits += Vacant(MockBrain(0.4), k=3).plain("solve x", _CHECK).verified
        v_hits += Vacant(MockBrain(0.4), k=3).solve("solve x", _CHECK).verified
    assert v_hits / n - p_hits / n > 0.2  # verify-fix 顯著勝出


def test_vacant_is_accountable():
    random.seed(1)
    v = Vacant(MockBrain(0.5), k=3)
    r = v.solve("solve x", _CHECK)
    assert r.accountable is True               # 簽章鏈可驗
    assert v.vacant_id and v.vacant_id.startswith("z")
    assert len(v.logbook) >= 1


def test_cannot_invent_when_impossible():
    random.seed(0)
    r = Vacant(MockBrain(0.0), k=5).solve("solve x", _CHECK)
    assert r.verified is False and r.calls == 5  # 模型完全不會 → verify-fix 救不回


def test_bench_report_shape():
    random.seed(3)
    v = Vacant(MockBrain(0.5), k=3)
    cases = [("solve x", _CHECK) for _ in range(20)]
    rep = v.bench(cases)
    assert rep["n"] == 20 and rep["k"] == 3
    assert rep["vacant_acc"] >= rep["plain_acc"]
    assert rep["vacant_calls_per"] <= 3.0


def test_checkable_cases_builds_pairs():
    cases = checkable_cases(5)
    assert len(cases) == 5
    prompt, verifier = cases[0]
    assert isinstance(prompt, str) and callable(verifier)
