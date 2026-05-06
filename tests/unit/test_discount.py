"""STYLO discount tests."""

from __future__ import annotations

import pytest

from vacant.core.constants import STYLO_DRIFT_THRESHOLD
from vacant.reputation import (
    Beta,
    apply_discount,
    apply_discount_5d,
    compute_discount,
    five_d_with_priors,
)


def test_compute_discount_zero_distance_returns_one() -> None:
    assert compute_discount(0.0) == 1.0


def test_compute_discount_negative_raises() -> None:
    with pytest.raises(ValueError):
        compute_discount(-1.0)


def test_compute_discount_decreases_monotonically() -> None:
    a = compute_discount(0.5)
    b = compute_discount(2.0)
    c = compute_discount(STYLO_DRIFT_THRESHOLD)
    d = compute_discount(10.0)
    assert 1.0 >= a > b > c > d > 0.0


def test_compute_discount_at_threshold_below_one() -> None:
    """At the canonical drift threshold, discount is well below 1.0."""
    val = compute_discount(STYLO_DRIFT_THRESHOLD)
    assert 0.2 < val < 0.7


def test_apply_discount_halves_evidence_at_half() -> None:
    b = Beta(
        alpha=5.0,
        beta=5.0,
        alpha0=1.0,
        beta0=1.0,
        n_eff=8.0,
        last_update_ts=0.0,
        half_life_days=90,
    )
    half = apply_discount(b, 0.5)
    assert half.alpha == pytest.approx(1.0 + 0.5 * (5.0 - 1.0))  # 3
    assert half.beta == pytest.approx(1.0 + 0.5 * (5.0 - 1.0))  # 3
    assert half.n_eff == pytest.approx(4.0)


def test_apply_discount_full_one_is_identity() -> None:
    b = Beta(alpha=5.0, beta=3.0, alpha0=1.0, beta0=1.0, n_eff=6.0)
    same = apply_discount(b, 1.0)
    assert same.alpha == 5.0
    assert same.beta == 3.0
    assert same.n_eff == 6.0


def test_apply_discount_rejects_zero_or_above_one() -> None:
    b = Beta(alpha=2.0, beta=2.0)
    with pytest.raises(ValueError):
        apply_discount(b, 0.0)
    with pytest.raises(ValueError):
        apply_discount(b, 1.5)


def test_apply_discount_shrinks_mean_toward_prior() -> None:
    """Per P3 §3.2 the decay rule shrinks evidence toward the prior, so
    post-discount mean shifts toward the prior's mean (not preserved).

    Symmetric prior (1, 1) has prior-mean 0.5; a high-mean evidence
    posterior moves toward 0.5 as discount -> 0.
    """
    b = Beta(alpha=10.0, beta=4.0, alpha0=1.0, beta0=1.0, n_eff=12.0)
    prior_mean = b.alpha0 / (b.alpha0 + b.beta0)
    high_disc = apply_discount(b, 0.99).mean
    low_disc = apply_discount(b, 0.05).mean
    # As discount shrinks, mean moves toward prior_mean (0.5).
    assert abs(low_disc - prior_mean) < abs(high_disc - prior_mean)


def test_apply_discount_5d_applies_to_all_dims() -> None:
    rep = five_d_with_priors().model_copy(
        update={
            "factual": Beta(alpha=5, beta=5, alpha0=1, beta0=1, n_eff=8),
            "logical": Beta(alpha=5, beta=5, alpha0=1, beta0=1, n_eff=8),
        }
    )
    half = apply_discount_5d(rep, 0.5)
    assert half.factual.n_eff == pytest.approx(4.0)
    assert half.logical.n_eff == pytest.approx(4.0)


def test_compute_discount_large_distance_approaches_floor() -> None:
    """Discount approaches floor as distance → ∞ (never zero)."""
    very_far = compute_discount(100.0)
    assert very_far > 0.05
    assert very_far < 0.2


def test_small_drift_preserves_evidence() -> None:
    """Per dispatch §3: small drift → discount close to 1, large → halves."""
    small = compute_discount(0.5)
    large = compute_discount(STYLO_DRIFT_THRESHOLD * 2)
    assert small > 0.85
    assert large < 0.5
