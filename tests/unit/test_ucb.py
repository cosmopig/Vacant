"""UCB scoring tests."""

from __future__ import annotations

import pytest

from vacant.reputation import (
    Beta,
    Beta5D,
    call_score,
    cold_start_floor,
    exploration_boost,
    five_d_with_priors,
    lineage_prior_alpha,
    ucb_score,
    ucb_with_lineage_prior,
)


def _rep_with_means(means: dict[str, float], *, n: float = 30) -> Beta5D:
    rep = five_d_with_priors()
    new_dims = {}
    for d, m in means.items():
        # alpha = m * (n + 2), beta = (1 - m) * (n + 2) gives mean ~ m
        a = m * (n + 2.0) + 0.001
        b = (1.0 - m) * (n + 2.0) + 0.001
        new_dims[d] = Beta(
            alpha=a,
            beta=b,
            alpha0=1.0,
            beta0=1.0,
            n_eff=n,
            last_update_ts=0.0,
            half_life_days=90,
        )
    return rep.model_copy(update=new_dims)


def test_ucb_new_vacant_explores_above_established() -> None:
    """High-uncertainty new vacants beat established ones in UCB ranking."""
    new_rep = five_d_with_priors()  # n_eff = 0
    weights = {d: 0.2 for d in ("factual", "logical", "relevance", "honesty", "adoption")}
    new_score = ucb_score(new_rep, weights=weights, n_global=100)

    established_rep = _rep_with_means(
        {"factual": 0.5, "logical": 0.5, "relevance": 0.5, "honesty": 0.5, "adoption": 0.5},
        n=200,
    )
    established_score = ucb_score(established_rep, weights=weights, n_global=100)
    assert new_score > established_score


def test_ucb_high_quality_dominates_after_many_reviews() -> None:
    """Once both have many samples, high-quality dominates low-quality."""
    weights = {"factual": 0.5, "logical": 0.5, "relevance": 0.0, "honesty": 0.0, "adoption": 0.0}
    high = _rep_with_means(
        {"factual": 0.95, "logical": 0.92, "relevance": 0.5, "honesty": 0.5, "adoption": 0.5}, n=200
    )
    low = _rep_with_means(
        {"factual": 0.30, "logical": 0.25, "relevance": 0.5, "honesty": 0.5, "adoption": 0.5}, n=200
    )
    assert ucb_score(high, weights=weights, n_global=200) > ucb_score(
        low, weights=weights, n_global=200
    )


def test_ucb_default_weights_are_uniform() -> None:
    rep = _rep_with_means(
        {"factual": 0.5, "logical": 0.5, "relevance": 0.5, "honesty": 0.5, "adoption": 0.5},
        n=30,
    )
    # No weights → uniform.
    score = ucb_score(rep, n_global=10)
    assert 0 < score < 2


def test_ucb_negative_weight_rejected() -> None:
    rep = five_d_with_priors()
    with pytest.raises(ValueError):
        ucb_score(rep, weights={"factual": -0.1})


def test_lineage_prior_alpha_decays_with_depth() -> None:
    a0, b0 = lineage_prior_alpha(
        base_alpha=1.0,
        base_beta=1.0,
        parent_alpha=10.0,
        parent_beta=2.0,
        depth=0,
    )
    a1, b1 = lineage_prior_alpha(
        base_alpha=1.0,
        base_beta=1.0,
        parent_alpha=10.0,
        parent_beta=2.0,
        depth=2,
    )
    a3, b3 = lineage_prior_alpha(
        base_alpha=1.0,
        base_beta=1.0,
        parent_alpha=10.0,
        parent_beta=2.0,
        depth=5,
    )
    # Depth 0 inherits the most; depth 5 inherits the least.
    assert a0 > a1 > a3
    assert b0 > b1 > b3
    # Depth 5 still > base (decay never quite zero for finite depth).
    assert a3 > 1.0


def test_lineage_prior_alpha_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        lineage_prior_alpha(base_alpha=1, base_beta=1, parent_alpha=1, parent_beta=1, depth=-1)
    with pytest.raises(ValueError):
        lineage_prior_alpha(
            base_alpha=1, base_beta=1, parent_alpha=1, parent_beta=1, depth=0, inherit_fraction=2.0
        )
    with pytest.raises(ValueError):
        lineage_prior_alpha(
            base_alpha=1, base_beta=1, parent_alpha=1, parent_beta=1, depth=0, decay_lambda=-1
        )


def test_ucb_with_lineage_prior_does_not_inherit_parent_score() -> None:
    """F2 regression: child's UCB score MUST NOT depend on parent posterior.

    CLAUDE.md §Load-bearing theory decisions / D015 §B: lineage (the
    parent_id chain) is the subject of evolution, not individual vacants.
    A high-reputation parent must not lift its newborn child's UCB score —
    new lineage members reset the clock.
    """
    child = Beta(alpha=1.0, beta=1.0, alpha0=1.0, beta0=1.0)
    high_parent = Beta(alpha=100.0, beta=2.0, alpha0=1.0, beta0=1.0)
    low_parent = Beta(alpha=2.0, beta=100.0, alpha0=1.0, beta0=1.0)
    no_parent = Beta(alpha=1.0, beta=1.0, alpha0=1.0, beta0=1.0)

    score_high = ucb_with_lineage_prior(
        child_beta=child, parent_beta=high_parent, n_global=10, depth=0
    )
    score_low = ucb_with_lineage_prior(
        child_beta=child, parent_beta=low_parent, n_global=10, depth=0
    )
    score_none = ucb_with_lineage_prior(
        child_beta=child, parent_beta=no_parent, n_global=10, depth=0
    )
    score_no_arg = ucb_with_lineage_prior(child_beta=child, n_global=10)

    assert score_high == pytest.approx(score_low)
    assert score_high == pytest.approx(score_none)
    assert score_high == pytest.approx(score_no_arg)


def test_ucb_with_lineage_prior_depth_is_metadata_only() -> None:
    """Depth is accepted for caller-side ranking but does not move the score."""
    child = Beta(alpha=1.0, beta=1.0)
    parent = Beta(alpha=99.0, beta=1.0)
    a = ucb_with_lineage_prior(child_beta=child, parent_beta=parent, n_global=10, depth=0)
    b = ucb_with_lineage_prior(child_beta=child, parent_beta=parent, n_global=10, depth=8)
    assert a == pytest.approx(b)


def test_lineage_prior_alpha_helper_still_decays() -> None:
    """`lineage_prior_alpha` remains usable as a research helper outside UCB."""
    a0, _ = lineage_prior_alpha(
        base_alpha=1.0, base_beta=1.0, parent_alpha=10.0, parent_beta=2.0, depth=0
    )
    a3, _ = lineage_prior_alpha(
        base_alpha=1.0, base_beta=1.0, parent_alpha=10.0, parent_beta=2.0, depth=5
    )
    assert a0 > a3 > 1.0


def test_exploration_boost_decays_to_zero_when_n_reaches_n_min() -> None:
    boost_low = exploration_boost(n_eff=1.0, n_min=30, n_global=100)
    boost_high = exploration_boost(n_eff=29.0, n_min=30, n_global=100)
    boost_at_min = exploration_boost(n_eff=30.0, n_min=30, n_global=100)
    boost_above = exploration_boost(n_eff=50.0, n_min=30, n_global=100)
    assert boost_low > boost_high > 0
    assert boost_at_min == 0.0
    assert boost_above == 0.0


def test_cold_start_floor_by_level() -> None:
    assert cold_start_floor("L0") == 0.0
    assert cold_start_floor("L1") == 0.05
    assert cold_start_floor("L2") == 0.10
    assert cold_start_floor("L3") == 0.15
    assert cold_start_floor("Lx") == 0.0  # unknown → 0


def test_call_score_includes_stake_attestation_portability() -> None:
    rep = _rep_with_means(
        {"factual": 0.5, "logical": 0.5, "relevance": 0.5, "honesty": 0.5, "adoption": 0.5},
        n=30,
    )
    base = call_score(rep, n_global=10, stake_amount=0, attestation_level="L0")
    full = call_score(
        rep,
        n_global=10,
        stake_amount=200.0,
        attestation_level="L1",
        portability_bonus=0.05,
    )
    # Stake bonus + L1 floor + portability all add up.
    assert full > base


def test_call_score_rejects_negative_stake() -> None:
    rep = five_d_with_priors()
    with pytest.raises(ValueError):
        call_score(rep, n_global=10, stake_amount=-1.0)
    with pytest.raises(ValueError):
        call_score(rep, n_global=10, portability_bonus=-1.0)
