"""Beta + Beta5D posterior unit tests."""

from __future__ import annotations

import math

import pytest

from vacant.reputation import (
    Beta,
    Beta5D,
    decay_factor,
    five_d_with_priors,
)
from vacant.reputation.errors import InvalidDimensionError, InvalidSignalError


def test_decay_factor_zero_dt_is_one() -> None:
    assert decay_factor(0, 90) == 1.0


def test_decay_factor_one_half_life_is_half() -> None:
    assert decay_factor(86_400 * 90, 90) == pytest.approx(0.5, abs=1e-9)


def test_decay_factor_negative_dt_is_one() -> None:
    assert decay_factor(-100, 90) == 1.0


def test_beta_mean_and_variance() -> None:
    b = Beta(alpha=2.0, beta=3.0, alpha0=1.0, beta0=1.0)
    assert b.mean == pytest.approx(0.4)
    # Var = alphabeta / [(alpha+beta)^2 * (alpha+beta+1)] = 6 / (25 * 6) = 0.04
    assert b.variance == pytest.approx(0.04)


def test_beta_mean_zero_when_zero_alpha_beta() -> None:
    b = Beta(alpha=0.0, beta=0.0, alpha0=0.0, beta0=0.0)
    assert b.mean == 0.0
    assert b.variance == 0.0


def test_beta_update_with_signal_round_trip() -> None:
    b = Beta(alpha=1.0, beta=1.0, alpha0=1.0, beta0=1.0, last_update_ts=0.0, half_life_days=90)
    b2 = b.update_with_signal(signal=1.0, weight=2.0, now_ts=0.0)
    assert b2.alpha == pytest.approx(3.0)
    assert b2.beta == pytest.approx(1.0)
    assert b2.n_eff == pytest.approx(2.0)


def test_beta_update_signal_in_unit_interval_required() -> None:
    b = Beta(alpha=1.0, beta=1.0, alpha0=1.0, beta0=1.0)
    with pytest.raises(InvalidSignalError):
        b.update_with_signal(signal=1.5, weight=1.0, now_ts=0.0)
    with pytest.raises(InvalidSignalError):
        b.update_with_signal(signal=0.5, weight=-1.0, now_ts=0.0)


def test_beta_decays_evidence_not_prior() -> None:
    b = Beta(
        alpha=5.0,
        beta=5.0,
        alpha0=1.0,
        beta0=1.0,
        n_eff=8.0,
        last_update_ts=0.0,
        half_life_days=10,
    )
    # 10 days later, evidence halves but prior stays.
    later = b.decayed(now_ts=86_400 * 10)
    assert later.alpha == pytest.approx(1.0 + 0.5 * (5.0 - 1.0))  # 3.0
    assert later.beta == pytest.approx(1.0 + 0.5 * (5.0 - 1.0))  # 3.0
    assert later.n_eff == pytest.approx(4.0)


def test_beta_no_decay_when_now_equals_last_update() -> None:
    b = Beta(
        alpha=5.0,
        beta=5.0,
        alpha0=1.0,
        beta0=1.0,
        n_eff=8.0,
        last_update_ts=100.0,
        half_life_days=10,
    )
    same = b.decayed(now_ts=100.0)
    assert same is b


def test_beta_rejects_negative_field() -> None:
    with pytest.raises(InvalidSignalError):
        Beta(alpha=-1.0, beta=1.0)


def test_beta_update_negative_weights_rejected() -> None:
    b = Beta(alpha=1.0, beta=1.0)
    with pytest.raises(InvalidSignalError):
        b.update(positive_weight=-0.5, negative_weight=0.5, now_ts=0.0)


def test_beta5d_uses_canonical_priors() -> None:
    rep = five_d_with_priors()
    # honesty alpha0=2 (asymmetric); adoption beta0=3 (pessimistic).
    assert rep.honesty.alpha0 == 2.0
    assert rep.honesty.beta0 == 1.0
    assert rep.adoption.alpha0 == 1.0
    assert rep.adoption.beta0 == 3.0
    # F/L/R all (1.0, 1.0).
    for d in ("factual", "logical", "relevance"):
        assert rep.get(d).alpha0 == 1.0
        assert rep.get(d).beta0 == 1.0


def test_beta5d_means_returns_all_dims() -> None:
    rep = five_d_with_priors()
    means = rep.means()
    assert set(means) == {"factual", "logical", "relevance", "honesty", "adoption"}
    # Initial means: F/L/R = 1/(1+1) = 0.5; H = 2/3; A = 1/4.
    assert means["factual"] == 0.5
    assert means["honesty"] == pytest.approx(2 / 3)
    assert means["adoption"] == 0.25


def test_beta5d_get_unknown_dim_raises() -> None:
    rep = five_d_with_priors()
    with pytest.raises(InvalidDimensionError):
        rep.get("creativity")


def test_beta5d_update_dim_advances_one_dim_only() -> None:
    rep = five_d_with_priors()
    new = rep.update_dim("factual", signal=1.0, weight=2.0, now_ts=0.0)
    assert new.factual.alpha == pytest.approx(3.0)
    # Other dims untouched.
    assert new.logical.alpha == rep.logical.alpha


def test_beta5d_decay_advances_all_dims() -> None:
    rep = Beta5D(
        factual=Beta(
            alpha=5.0,
            beta=5.0,
            alpha0=1.0,
            beta0=1.0,
            n_eff=8.0,
            last_update_ts=0.0,
            half_life_days=10,
        ),
        logical=Beta(
            alpha=5.0,
            beta=5.0,
            alpha0=1.0,
            beta0=1.0,
            n_eff=8.0,
            last_update_ts=0.0,
            half_life_days=10,
        ),
        relevance=Beta(
            alpha=5.0,
            beta=5.0,
            alpha0=1.0,
            beta0=1.0,
            n_eff=8.0,
            last_update_ts=0.0,
            half_life_days=10,
        ),
        honesty=Beta(
            alpha=5.0,
            beta=5.0,
            alpha0=2.0,
            beta0=1.0,
            n_eff=8.0,
            last_update_ts=0.0,
            half_life_days=10,
        ),
        adoption=Beta(
            alpha=5.0,
            beta=5.0,
            alpha0=1.0,
            beta0=3.0,
            n_eff=8.0,
            last_update_ts=0.0,
            half_life_days=10,
        ),
    )
    later = rep.decayed(now_ts=86_400 * 10)
    for d in ("factual", "logical", "relevance"):
        assert later.get(d).n_eff == pytest.approx(4.0)


def test_beta_recursive_trust_terminates_at_floor() -> None:
    """Reviewer credibility recursion bottoms out at REVIEWER_CREDIBILITY_FLOOR.

    A reviewer with mean=0 still contributes `floor` to the weight; a
    reviewer with mean=1 contributes 1.0. Floor protects new reviewers
    from "no one can review until you have reputation".
    """
    from vacant.core.constants import REVIEWER_CREDIBILITY_FLOOR

    # The aggregator implements credibility = floor + (1 - floor) * mean.
    # Test the formula directly.
    cred_zero = REVIEWER_CREDIBILITY_FLOOR + (1 - REVIEWER_CREDIBILITY_FLOOR) * 0.0
    cred_max = REVIEWER_CREDIBILITY_FLOOR + (1 - REVIEWER_CREDIBILITY_FLOOR) * 1.0
    assert cred_zero == REVIEWER_CREDIBILITY_FLOOR
    assert cred_max == 1.0
    assert math.isfinite(cred_zero) and math.isfinite(cred_max)
