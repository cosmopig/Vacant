"""Cold-start mechanism tests + 1-vacant-vs-9 simulation."""

from __future__ import annotations

import pytest

from vacant.core.crypto import keygen
from vacant.core.types import VacantId, VacantState
from vacant.reputation import (
    Aggregator,
    BirthPath,
    VacantContext,
    birth_path_bonus,
    five_d_with_priors,
    initial_prior,
    is_eligible_for_low_stakes_probe,
    niche_bonus,
    should_idle_review_target,
    show_label,
)


def test_initial_prior_no_attestation_matches_base() -> None:
    rep = initial_prior(attestation_level="L0", stake_amount=0)
    base = five_d_with_priors()
    assert rep.factual.alpha == base.factual.alpha
    assert rep.honesty.alpha == base.honesty.alpha


def test_initial_prior_l1_boosts_flr() -> None:
    rep = initial_prior(attestation_level="L1")
    assert rep.factual.alpha == pytest.approx(1.5)
    assert rep.factual.alpha0 == pytest.approx(1.5)
    assert rep.logical.alpha == pytest.approx(1.5)
    # H not boosted by L1 directly.
    assert rep.honesty.alpha == 2.0


def test_initial_prior_stake_boost_capped() -> None:
    rep_small = initial_prior(stake_amount=100)  # = S_REF
    rep_huge = initial_prior(stake_amount=1_000_000)
    assert rep_huge.factual.alpha > rep_small.factual.alpha
    # Capped at +2.0 split half-each → +1.0 per dim max.
    assert rep_huge.factual.alpha <= 1.0 + 1.0 + 1e-6


def test_initial_prior_l3_vouches_boost_h() -> None:
    rep = initial_prior(n_l1_plus_vouchers=3)
    # Each vouch adds 0.3 alpha to H.
    assert rep.honesty.alpha == pytest.approx(2.0 + 0.9)


def test_initial_prior_birth_path_zero_boosts() -> None:
    rep = initial_prior(birth_path=BirthPath.PATH_ZERO)
    assert rep.factual.alpha > 1.0
    assert rep.honesty.alpha > 2.0


def test_birth_path_bonus_d_series_is_small() -> None:
    """D-series gets minimal direct boost; lineage prior carries the signal."""
    for d in (BirthPath.D1, BirthPath.D2, BirthPath.D3, BirthPath.D5):
        flr, h = birth_path_bonus(d)
        assert flr == 0.0
        assert h == 0.0


def test_niche_bonus_decreases_with_supply() -> None:
    a = niche_bonus(capability_supply=0)
    b = niche_bonus(capability_supply=5)
    c = niche_bonus(capability_supply=10)
    d = niche_bonus(capability_supply=100)
    assert a > b > c == 0
    assert d == 0


def test_niche_bonus_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        niche_bonus(capability_supply=-1)
    with pytest.raises(ValueError):
        niche_bonus(capability_supply=0, saturation_supply=0)
    with pytest.raises(ValueError):
        niche_bonus(capability_supply=0, max_bonus=-0.1)


def test_is_eligible_for_low_stakes_probe_true_at_cold_start() -> None:
    rep = five_d_with_priors()
    assert is_eligible_for_low_stakes_probe(rep) is True


def test_should_idle_review_target_requires_idle_and_low_n() -> None:
    assert should_idle_review_target(reviewer_idle_seconds=10_000, target_n_eff_min=2.0) is True
    assert should_idle_review_target(reviewer_idle_seconds=100, target_n_eff_min=2.0) is False
    assert should_idle_review_target(reviewer_idle_seconds=10_000, target_n_eff_min=200) is False


def test_show_label_insufficient_for_cold_start() -> None:
    rep = five_d_with_priors()
    label = show_label(rep)
    assert label.label == "INSUFFICIENT_DATA"
    assert not label.show_scalar
    assert label.caveats.insufficient_data is True


def test_show_label_sufficient_after_n_show() -> None:
    rep = five_d_with_priors()
    # Push every dim above n_show=10.
    for d in ("factual", "logical", "relevance", "honesty", "adoption"):
        rep = rep.update_dim(d, signal=0.5, weight=15.0, now_ts=0.0)
    label = show_label(rep)
    assert label.label == "OK"
    assert label.show_scalar is True


# --- cold-start simulation: 1 new vacant + 9 established ----------------


@pytest.mark.asyncio
async def test_cold_start_simulation_new_gets_traction() -> None:
    """Dispatch acceptance: new vacant gets >0 calls within 100 ticks.

    Setup: 1 new vacant + 9 established. Run 100 ticks of UCB-greedy
    selection with caller weights uniform across dims; the new vacant
    must be selected at least once.
    """
    contexts: dict[VacantId, VacantContext] = {}
    # 9 established vacants, each with the same capability text.
    for _ in range(9):
        _sk, vk = keygen()
        vid = VacantId.from_verify_key(vk)
        contexts[vid] = VacantContext(
            vacant_id=vid,
            base_model_family="claude",
            state=VacantState.ACTIVE,
            capability_text="translate",
            attestation_level="L1",
        )

    # 1 new vacant -- different family (no shared-substrate review pile-on).
    _sk, vk = keygen()
    new_vid = VacantId.from_verify_key(vk)
    contexts[new_vid] = VacantContext(
        vacant_id=new_vid,
        base_model_family="gemini",
        state=VacantState.ACTIVE,
        capability_text="translate",
        attestation_level="L1",
    )

    agg = Aggregator(contexts=contexts)

    # Seed established vacants with history across ALL 5 dims so their
    # harmonic-mean n_eff grows -> explore term shrinks. With only F/L/R
    # reviewed, the unreviewed honesty/adoption dims keep n_w ~ 0 and
    # both groups get the same enormous explore boost.
    estab_ids = [vid for vid in contexts if vid != new_vid]
    full_dims = {
        "factual": 0.85,
        "logical": 0.85,
        "relevance": 0.85,
        "honesty": 0.85,
        "adoption": 0.85,
    }
    for established in estab_ids:
        reviewer = next(v for v in estab_ids if v != established)
        for _ in range(15):
            await agg.record_review(
                reviewer=reviewer,
                target=established,
                dimensions=full_dims,
                substrate="default",
                source="peer_review",
            )

    new_vacant_calls = 0
    for _ in range(100):
        ranked = await agg.get_ranked("translate", n=1)
        assert ranked
        chosen, _score = ranked[0]
        review_dims = {
            "factual": 0.7,
            "logical": 0.7,
            "relevance": 0.7,
            "honesty": 0.7,
            "adoption": 0.7,
        }
        if chosen == new_vid:
            new_vacant_calls += 1
            # Reward the new vacant so we don't infinitely loop on it.
            await agg.record_review(
                reviewer=estab_ids[0],
                target=new_vid,
                dimensions=review_dims,
                substrate="default",
                source="caller_review",
            )
        else:
            # Established vacant gets a steady review so n_eff grows.
            reviewer = next(v for v in estab_ids if v != chosen)
            await agg.record_review(
                reviewer=reviewer,
                target=chosen,
                dimensions=review_dims,
                substrate="default",
                source="peer_review",
            )

    assert new_vacant_calls > 0, (
        "new vacant must be selected at least once in 100 ticks (UCB exploration)"
    )
