"""Hypothesis property tests for reputation invariants."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from vacant.core.crypto import keygen
from vacant.core.types import VacantId, VacantState
from vacant.reputation import (
    Aggregator,
    Beta,
    IneligibleReviewerError,
    VacantContext,
    apply_discount,
    five_d_with_priors,
)

_REP_DIMS = ("factual", "logical", "relevance", "honesty", "adoption")


@given(
    alpha=st.floats(min_value=0.001, max_value=100, allow_nan=False),
    beta=st.floats(min_value=0.001, max_value=100, allow_nan=False),
    signal=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    weight=st.floats(min_value=0.001, max_value=10, allow_nan=False),
)
@settings(max_examples=50, deadline=None)
def test_posterior_never_negative_after_update(
    alpha: float, beta: float, signal: float, weight: float
) -> None:
    b = Beta(alpha=alpha, beta=beta, alpha0=1.0, beta0=1.0, half_life_days=90, last_update_ts=0.0)
    out = b.update_with_signal(signal=signal, weight=weight, now_ts=0.0)
    assert out.alpha >= 0
    assert out.beta >= 0
    assert out.n_eff >= 0


@given(
    weight=st.floats(min_value=0.0, max_value=10, allow_nan=False),
    n_pulses=st.integers(min_value=0, max_value=20),
)
@settings(max_examples=30, deadline=None)
def test_total_weight_monotonic_until_discount(weight: float, n_pulses: int) -> None:
    """Without time decay or explicit discount, total alpha + beta increases (or stays)
    monotonically as we apply pulses.
    """
    b = Beta(alpha=1.0, beta=1.0, alpha0=1.0, beta0=1.0, half_life_days=999_999, last_update_ts=0.0)
    prev = b.alpha + b.beta
    for _ in range(n_pulses):
        b = b.update_with_signal(signal=0.5, weight=weight, now_ts=0.0)
        cur = b.alpha + b.beta
        assert cur >= prev - 1e-9
        prev = cur


@given(
    discount=st.floats(min_value=0.01, max_value=1.0, allow_nan=False),
    alpha=st.floats(min_value=1.0, max_value=100, allow_nan=False),
    beta=st.floats(min_value=1.0, max_value=100, allow_nan=False),
)
@settings(max_examples=40, deadline=None)
def test_discount_never_increases_n_eff(discount: float, alpha: float, beta: float) -> None:
    b = Beta(alpha=alpha, beta=beta, alpha0=1.0, beta0=1.0, n_eff=alpha + beta - 2.0)
    out = apply_discount(b, discount)
    assert out.n_eff <= b.n_eff + 1e-9


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "blocked_state",
    [VacantState.SUNK, VacantState.ARCHIVED, VacantState.STALE],
)
async def test_blocked_state_reviewer_always_rejected(
    blocked_state: VacantState,
) -> None:
    """SUNK / ARCHIVED / STALE reviewers are always rejected (P1 §4.1)."""
    _sk_a, vk_a = keygen()
    _sk_b, vk_b = keygen()
    a_id = VacantId.from_verify_key(vk_a)
    b_id = VacantId.from_verify_key(vk_b)
    contexts = {
        a_id: VacantContext(vacant_id=a_id, state=blocked_state),
        b_id: VacantContext(vacant_id=b_id),
    }
    agg = Aggregator(contexts=contexts)
    with pytest.raises(IneligibleReviewerError):
        await agg.record_review(a_id, b_id, dimensions={"factual": 1.0}, substrate="default")


def test_initial_priors_match_d008_table() -> None:
    """Regression guard: Beta5D base priors match the D008 §A canonical table."""
    rep = five_d_with_priors()
    assert (rep.factual.alpha0, rep.factual.beta0) == (1.0, 1.0)
    assert (rep.logical.alpha0, rep.logical.beta0) == (1.0, 1.0)
    assert (rep.relevance.alpha0, rep.relevance.beta0) == (1.0, 1.0)
    assert (rep.honesty.alpha0, rep.honesty.beta0) == (2.0, 1.0)
    assert (rep.adoption.alpha0, rep.adoption.beta0) == (1.0, 3.0)
    _ = _REP_DIMS
