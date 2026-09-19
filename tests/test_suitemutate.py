"""suitemutate 的確定性測試——「這把尺量得出強弱」這句話的可執行版本。

分成四組：
  §1 變異器本身：造得出哪幾類、造出來的都是合法 Python、便宜的等價過濾有作用
  §2 **負向控制**：弱套件必須拿低分、強套件必須拿高分（沒有這一條，分數只是裝飾）
  §3 紅線：致死率**不是**閘門——`MutationOutcome` 沒有 `ok`，
     `suitegauge` 的合格語意一個字都沒被改
  §4 誠實邊界句釘死（模組 docstring 的「下界」那幾句是規格的一部分）

§2 的兩條跑**真沙箱**（`vacant_network.checks.run_python_check`）：負向控制的主張就是
「真的跑起來分得開」，用假 runner 測只會測到假 runner。零模型呼叫、零 API、
零 `runs/` 寫入；逾時壓到 2 秒，免得無窮迴圈的變異體把測試拖住。
"""

from __future__ import annotations

import ast

import pytest

from vacant_network.suitegauge import gauge_suite
from vacant_network.suitemutate import (
    MutationOutcome,
    build_mutants,
    mutant_sources,
    score_suite,
)

IS_PRIME = """
def is_prime(n):
    if n < 2:
        return False
    i = 2
    while i * i <= n:
        if n % i == 0:
            return False
        i += 1
    return True
"""

STRONG = "\n".join([
    "assert is_prime(2) is True",
    "assert is_prime(3) is True",
    "assert is_prime(4) is False",
    "assert is_prime(1) is False",
    "assert is_prime(0) is False",
    "assert is_prime(9) is False",
    "assert is_prime(17) is True",
    "assert is_prime(25) is False",
])
WEAK = "assert is_prime(4) is False"

RICH = '''
def classify(items, flag):
    """docstring 不該被變異。"""
    out = []
    for x in items:
        if x < 0 and flag:
            continue
        if not flag:
            break
        out.append(x + 1)
    if out:
        return ".,!?"
    return out
'''


def real_runner(code, check_code, entry_point, timeout_s):
    """真沙箱，與 `gain_run.meets_demand` 同一顆（只是不帶 ops 的 import 白名單）。"""
    from vacant_network.checks import run_python_check
    ok = run_python_check(
        code, check_code, timeout=timeout_s,
        allowed_entry_points=(entry_point,) if entry_point else (),
    )
    return ok, "" if ok else "sandbox_check_failed"


def marker_runner(dead: set[str]):
    """假 runner：碼裡含指定片段就判失敗。給不需要真執行的線路測試用。"""
    def _run(code, check_code, entry_point, timeout_s):
        bad = any(m in code for m in dead)
        return (not bad), ("" if not bad else "marked")
    return _run


# ── 1. 變異器本身 ──────────────────────────────────────────────────────────
def test_operator_families_are_all_reachable():
    """規格要求的每一類都造得出來（清單漂了這條會紅）。"""
    ops = {m.operator for m in build_mutants(IS_PRIME)}
    ops |= {m.operator for m in build_mutants(RICH)}
    for want in ("num_plus_1", "num_minus_1", "cmp_flip", "bool_op_swap",
                 "not_remove", "not_insert", "bin_op_swap", "continue_to_pass",
                 "break_to_pass", "str_truncate", "return_const",
                 "bool_const_flip"):
        assert want in ops, f"{want} 造不出來"


def test_every_mutant_is_valid_python():
    for src in (IS_PRIME, RICH):
        for m in build_mutants(src):
            compile(m.code, "<mutant>", "exec")          # 語法錯＝量到的是 parse 失敗


def test_no_mutant_equals_the_normalized_baseline():
    """便宜的等價過濾（模組 docstring §1）：跟基準逐字相同的一律丟掉。"""
    for src in (IS_PRIME, RICH):
        base = ast.unparse(ast.parse(src))
        assert all(m.code != base for m in build_mutants(src))


def test_docstrings_are_not_mutated():
    """改 docstring 必定是等價變異體，白花一次沙箱。"""
    for m in build_mutants(RICH):
        assert "docstring 不該被變異" in m.code


def test_diff_points_at_a_real_line():
    for m in build_mutants(IS_PRIME):
        assert m.lineno >= 1 and m.before and m.after and m.before != m.after


def test_limit_is_deterministic_and_spreads_across_operators():
    a = [(m.operator, m.code) for m in build_mutants(IS_PRIME, limit=6, seed="x")]
    b = [(m.operator, m.code) for m in build_mutants(IS_PRIME, limit=6, seed="x")]
    c = [(m.operator, m.code) for m in build_mutants(IS_PRIME, limit=6, seed="y")]
    assert a == b                                        # 同 seed 逐字可重放
    assert len({op for op, _ in a}) >= 3                 # 輪流抽，不是同一類抽六個
    assert len(a) == 6 and len(c) == 6


def test_mutant_sources_feeds_gauge_suite_unchanged():
    """簽章相容：`gauge_suite(..., broken_stubs=...)` 直接吃 `list[str]`。"""
    srcs = mutant_sources(IS_PRIME, limit=3, seed="x")
    assert all(isinstance(s, str) for s in srcs)
    g = gauge_suite(STRONG, IS_PRIME, srcs, entry_point="is_prime",
                    runner=marker_runner({"def is_prime"}), timeout_s=2)
    assert g.n_broken == 3


# ── 2. 負向控制：量表要有鑑別力（真沙箱）────────────────────────────────
def test_weak_suite_scores_low_strong_suite_scores_high():
    """同一份參考解、同一組變異體，弱套件與強套件必須分得開。

    這是本模組存在的理由：`suitegauge` 對這兩套都給 `ok=True`
    （兩者都擋得住 `return None` 那一個壞樁），致死率把它們拉開。
    """
    strong = score_suite(STRONG, IS_PRIME, entry_point="is_prime",
                         runner=real_runner, timeout_s=2)
    weak = score_suite(WEAK, IS_PRIME, entry_point="is_prime",
                       runner=real_runner, timeout_s=2)
    assert strong.ref_passed and weak.ref_passed
    assert strong.normalized_passed and weak.normalized_passed
    assert strong.total == weak.total >= 20              # 同一組變異體，才比得起來
    assert strong.score >= 0.95, strong.as_dict()
    assert weak.score <= 0.60, weak.as_dict()
    assert strong.score - weak.score >= 0.35             # 鑑別力，不是雜訊
    assert weak.survivors and not strong.survivors
    assert {m.operator for m in weak.survivors} <= set(weak.by_operator)


def test_the_gauge_cannot_tell_those_two_apart():
    """負向控制的另一半：**現行閘門**對強弱兩套件都給綠燈。

    這條會紅只有一種可能——有人改了 `suitegauge` 的合格語意。
    """
    from vacant_network.suitegauge import broken_stub
    stub = [broken_stub("is_prime")]
    for suite in (STRONG, WEAK):
        g = gauge_suite(suite, IS_PRIME, stub, entry_point="is_prime",
                        runner=real_runner, timeout_s=2)
        assert g.ok is True


# ── 3. 紅線：致死率不是閘門 ────────────────────────────────────────────────
def test_outcome_has_no_pass_fail_verdict():
    """`MutationOutcome` 不准長出 `ok`／`all_rejected` 這種合格判準。"""
    assert not hasattr(MutationOutcome, "ok")
    assert not hasattr(MutationOutcome, "all_rejected")
    out = score_suite(WEAK, IS_PRIME, entry_point="is_prime", limit=2,
                      runner=marker_runner({"i = 3"}), timeout_s=2)
    assert "ok" not in out.as_dict()


def test_score_is_reported_even_when_survivors_exist():
    """活下來一個**不會**讓整份量測作廢——那是 `ok` 的語意，不是這裡的。"""
    out = score_suite(WEAK, IS_PRIME, entry_point="is_prime", limit=4, seed="x",
                      runner=marker_runner({"i = 3"}), timeout_s=2)
    assert out.total == 4 and 0 < out.killed < out.total
    assert out.score == out.killed / out.total
    assert len(out.survivors) == out.total - out.killed
    assert sum(t for _, t in out.by_operator.values()) == out.total
    assert sum(k for k, _ in out.by_operator.values()) == out.killed


def test_broken_normalization_is_visible_not_a_silent_perfect_score():
    """`ast.unparse` 往返若把語義弄壞，每個變異體都會「被擋住」＝假性滿分。

    `normalized_passed=False` 讓它看得見（模組 docstring §3）。
    """
    norm = ast.unparse(ast.parse(IS_PRIME))

    def only_normalized_fails(code, check_code, entry_point, timeout_s):
        return (code != norm), ""

    out = score_suite(STRONG, IS_PRIME, entry_point="is_prime", limit=3,
                      runner=only_normalized_fails, timeout_s=2)
    assert out.ref_passed is True
    assert out.normalized_passed is False                 # ← 假性滿分被指名
    assert out.score == 0.0

    off = score_suite(STRONG, IS_PRIME, entry_point="is_prime", limit=3,
                      runner=only_normalized_fails, timeout_s=2,
                      verify_baseline=False)
    assert off.normalized_passed is None


def test_runner_exceptions_are_not_swallowed():
    """「量不起來」與「量到 0」必須分得開（06-30 稽核紀律）。"""
    class Boom(Exception):
        pass

    def boom(*a, **k):
        raise Boom

    with pytest.raises(Boom):
        score_suite(STRONG, IS_PRIME, entry_point="is_prime", limit=1, runner=boom)


# ── 4. 誠實邊界句釘死 ──────────────────────────────────────────────────────
def test_honest_boundary_sentences_survive_edits():
    """致死率是下界、100% ≠ 涵蓋需求、不綁 `ok`——三句都是規格的一部分。"""
    import vacant_network.suitemutate as sm
    doc = sm.__doc__ or ""
    assert "下界" in doc
    assert "等價變異體" in doc
    assert "不准" in doc and "涵蓋需求" in doc
    assert "GaugeOutcome.ok" in doc
    assert "永遠是下界" in (MutationOutcome.score.__doc__ or "")
