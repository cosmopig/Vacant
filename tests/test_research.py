"""Track A 四臂 harness 的確定性自驗（vacant/research.py）。

用 StubBrain + 合成任務（每類 10 題）鎖住指標與 H0 因果拆解的算術，
確保管線/統計不被改壞。數字為刻意設計、非實證（見 research.py docstring）。
"""

from __future__ import annotations

from vacant.research import (
    decompose,
    discordance,
    mcnemar_exact,
    metrics,
    run_suite,
    synthetic_suite,
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
