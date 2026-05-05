"""Wash cost tests — monotonicity + parameter sensitivity."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from vacant.identity.errors import IdentityError
from vacant.identity.wash_cost import WashCostWeights, compute_wash_cost


def test_baseline_zero_inputs_yields_zero_cost() -> None:
    assert compute_wash_cost(0, 0, 0) == 0.0


def test_history_term_dominates() -> None:
    only_history = compute_wash_cost(10, 0, 0)
    only_attest = compute_wash_cost(0, 10, 0)
    only_substrate = compute_wash_cost(0, 0, 10)
    assert only_history > only_attest > only_substrate


@given(depth=st.integers(min_value=0, max_value=100))
@settings(max_examples=20, deadline=None)
def test_monotonic_in_history_depth(depth: int) -> None:
    less = compute_wash_cost(depth, 0, 0)
    more = compute_wash_cost(depth + 1, 0, 0)
    assert more >= less


@given(n=st.integers(min_value=0, max_value=50))
@settings(max_examples=20, deadline=None)
def test_monotonic_in_attestation_count(n: int) -> None:
    assert compute_wash_cost(0, n + 1, 0) >= compute_wash_cost(0, n, 0)


@given(n=st.integers(min_value=0, max_value=50))
@settings(max_examples=20, deadline=None)
def test_monotonic_in_substrate_diversity(n: int) -> None:
    assert compute_wash_cost(0, 0, n + 1) >= compute_wash_cost(0, 0, n)


@given(
    depth=st.integers(min_value=1, max_value=50),
    weight=st.floats(min_value=0.0, max_value=10.0, allow_nan=False),
    delta=st.floats(min_value=0.01, max_value=5.0, allow_nan=False),
)
@settings(max_examples=30, deadline=None)
def test_monotonic_in_false_claim_weight(depth: int, weight: float, delta: float) -> None:
    """For nonzero claimed_history_depth, increasing false_claim_weight
    must strictly increase wash cost.
    """
    lo = compute_wash_cost(depth, 0, 0, false_claim_weight=weight)
    hi = compute_wash_cost(depth, 0, 0, false_claim_weight=weight + delta)
    assert hi > lo


def test_false_claim_weight_no_effect_when_history_is_zero() -> None:
    a = compute_wash_cost(0, 5, 5, false_claim_weight=0.0)
    b = compute_wash_cost(0, 5, 5, false_claim_weight=100.0)
    assert a == b


def test_negative_inputs_raise() -> None:
    with pytest.raises(IdentityError):
        compute_wash_cost(-1, 0, 0)
    with pytest.raises(IdentityError):
        compute_wash_cost(0, -1, 0)
    with pytest.raises(IdentityError):
        compute_wash_cost(0, 0, -1)
    with pytest.raises(IdentityError):
        compute_wash_cost(0, 0, 0, false_claim_weight=-0.1)


def test_weights_must_be_nonnegative() -> None:
    with pytest.raises(IdentityError):
        WashCostWeights(history_unit_cost=-1.0)
    with pytest.raises(IdentityError):
        WashCostWeights(attestation_unit_cost=-1.0)
    with pytest.raises(IdentityError):
        WashCostWeights(substrate_unit_cost=-1.0)


def test_custom_weights_are_respected() -> None:
    cheap = compute_wash_cost(10, 10, 10, weights=WashCostWeights(0.0, 0.0, 0.0))
    assert cheap == 0.0
    expensive = compute_wash_cost(1, 0, 0, weights=WashCostWeights(history_unit_cost=1000.0))
    assert expensive >= 1000.0
