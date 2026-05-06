"""Aggregator API tests + reviewer-eligibility check."""

from __future__ import annotations

import pytest

from vacant.core.crypto import keygen
from vacant.core.types import VacantId, VacantState
from vacant.reputation import (
    Aggregator,
    IneligibleReviewerError,
    InvalidDimensionError,
    InvalidSignalError,
    VacantContext,
)


def _ctx(
    *, family: str = "claude", state: VacantState = VacantState.ACTIVE, capability: str = "x"
) -> VacantContext:
    _sk, vk = keygen()
    return VacantContext(
        vacant_id=VacantId.from_verify_key(vk),
        base_model_family=family,
        state=state,
        capability_text=capability,
        attestation_level="L1",
    )


def _agg(*ctxs: VacantContext) -> Aggregator:
    return Aggregator(contexts={c.vacant_id: c for c in ctxs}, review_limit_per_target_24h=10_000)


@pytest.mark.asyncio
async def test_record_review_updates_target_posterior() -> None:
    a, b = _ctx(), _ctx(family="gemini")
    agg = _agg(a, b)
    initial = await agg.get_reputation(b.vacant_id, "default")
    initial_alpha = initial.factual.alpha
    await agg.record_review(
        a.vacant_id,
        b.vacant_id,
        dimensions={"factual": 1.0},
        substrate="default",
        source="caller_review",
    )
    after = await agg.get_reputation(b.vacant_id, "default")
    assert after.factual.alpha > initial_alpha


@pytest.mark.asyncio
async def test_record_review_rejects_self_review() -> None:
    a = _ctx()
    agg = _agg(a)
    with pytest.raises(InvalidSignalError):
        await agg.record_review(
            a.vacant_id,
            a.vacant_id,
            dimensions={"factual": 1.0},
            substrate="default",
        )


@pytest.mark.asyncio
async def test_record_review_rejects_unknown_reviewer_or_target() -> None:
    a = _ctx()
    agg = _agg(a)
    ghost = VacantId.from_verify_key(keygen()[1])
    with pytest.raises(InvalidSignalError):
        await agg.record_review(
            ghost, a.vacant_id, dimensions={"factual": 1.0}, substrate="default"
        )
    with pytest.raises(InvalidSignalError):
        await agg.record_review(
            a.vacant_id, ghost, dimensions={"factual": 1.0}, substrate="default"
        )


@pytest.mark.asyncio
async def test_record_review_rejects_ineligible_reviewer_sunk() -> None:
    """SUNK vacants cannot review (P1 §4.1 / dispatch acceptance)."""
    a = _ctx(state=VacantState.SUNK)
    b = _ctx(family="gemini")
    agg = _agg(a, b)
    with pytest.raises(IneligibleReviewerError):
        await agg.record_review(
            a.vacant_id,
            b.vacant_id,
            dimensions={"factual": 1.0},
            substrate="default",
        )


@pytest.mark.asyncio
async def test_record_review_rejects_archived_reviewer() -> None:
    a = _ctx(state=VacantState.ARCHIVED)
    b = _ctx(family="gemini")
    agg = _agg(a, b)
    with pytest.raises(IneligibleReviewerError):
        await agg.record_review(
            a.vacant_id, b.vacant_id, dimensions={"factual": 1.0}, substrate="default"
        )


@pytest.mark.asyncio
async def test_record_review_rejects_stale_reviewer() -> None:
    """STALE also can't review per THEORY_V5 §4.1 (D003 §A)."""
    a = _ctx(state=VacantState.STALE)
    b = _ctx(family="gemini")
    agg = _agg(a, b)
    with pytest.raises(IneligibleReviewerError):
        await agg.record_review(
            a.vacant_id, b.vacant_id, dimensions={"factual": 1.0}, substrate="default"
        )


@pytest.mark.asyncio
async def test_record_review_unknown_dim_raises() -> None:
    a, b = _ctx(), _ctx(family="gemini")
    agg = _agg(a, b)
    with pytest.raises(InvalidDimensionError):
        await agg.record_review(
            a.vacant_id, b.vacant_id, dimensions={"creativity": 0.5}, substrate="default"
        )


@pytest.mark.asyncio
async def test_record_review_unknown_source_raises() -> None:
    a, b = _ctx(), _ctx(family="gemini")
    agg = _agg(a, b)
    with pytest.raises(InvalidSignalError):
        await agg.record_review(
            a.vacant_id,
            b.vacant_id,
            dimensions={"factual": 0.5},
            substrate="default",
            source="bogus",
        )


@pytest.mark.asyncio
async def test_record_review_signal_out_of_range_raises() -> None:
    a, b = _ctx(), _ctx(family="gemini")
    agg = _agg(a, b)
    with pytest.raises(InvalidSignalError):
        await agg.record_review(
            a.vacant_id, b.vacant_id, dimensions={"factual": 1.5}, substrate="default"
        )


@pytest.mark.asyncio
async def test_get_ranked_filters_to_running_vacants() -> None:
    a = _ctx(capability="legal")
    b = _ctx(capability="legal", state=VacantState.SUNK)
    c = _ctx(capability="legal")
    agg = _agg(a, b, c)
    ranked = await agg.get_ranked("legal", n=10)
    ids = {vid for vid, _ in ranked}
    assert b.vacant_id not in ids
    assert a.vacant_id in ids and c.vacant_id in ids


@pytest.mark.asyncio
async def test_get_ranked_filters_by_capability_query() -> None:
    a = _ctx(capability="legal-research")
    b = _ctx(capability="image-gen")
    agg = _agg(a, b)
    ranked = await agg.get_ranked("legal", n=10)
    ids = {vid for vid, _ in ranked}
    assert a.vacant_id in ids and b.vacant_id not in ids


@pytest.mark.asyncio
async def test_score_method_satisfies_p4_protocol() -> None:
    """Aggregator.score(vacant_hex, dims) -> float matches P4's
    ReputationOracle Protocol.
    """
    a, b = _ctx(), _ctx(family="gemini")
    agg = _agg(a, b)
    score = await agg.score(b.vacant_id.hex(), ["factual", "logical"])
    assert 0.0 <= score <= 1.0


@pytest.mark.asyncio
async def test_score_unknown_vacant_returns_zero() -> None:
    a = _ctx()
    agg = _agg(a)
    assert await agg.score("00" * 32, ["factual"]) == 0.0


@pytest.mark.asyncio
async def test_apply_drift_discount_shrinks_n_eff() -> None:
    a, b = _ctx(), _ctx(family="gemini")
    agg = _agg(a, b)
    for _ in range(5):
        await agg.record_review(
            a.vacant_id,
            b.vacant_id,
            dimensions={"factual": 1.0},
            substrate="default",
            source="caller_review",
        )
    pre = await agg.get_reputation(b.vacant_id, "default")
    pre_n = pre.factual.n_eff
    await agg.apply_drift_discount(b.vacant_id, substrate="default", discount=0.5)
    post = await agg.get_reputation(b.vacant_id, "default")
    assert post.factual.n_eff == pytest.approx(pre_n * 0.5)


@pytest.mark.asyncio
async def test_same_model_review_is_discounted() -> None:
    """Same-base-model reviewer's weight is halved per §3.4.1."""
    same_fam_reviewer = _ctx(family="claude")
    cross_fam_reviewer = _ctx(family="gemini")
    target = _ctx(family="claude")
    agg = _agg(same_fam_reviewer, cross_fam_reviewer, target)

    # Two parallel sims: cross-family review vs same-family review.
    # Cross-family should bump alpha more (no discount).
    await agg.record_review(
        cross_fam_reviewer.vacant_id,
        target.vacant_id,
        dimensions={"factual": 1.0},
        substrate="default",
        source="peer_review",
    )
    cross = (await agg.get_reputation(target.vacant_id, "default")).factual.alpha

    # Reset by building a fresh aggregator.
    agg2 = _agg(same_fam_reviewer, cross_fam_reviewer, target)
    await agg2.record_review(
        same_fam_reviewer.vacant_id,
        target.vacant_id,
        dimensions={"factual": 1.0},
        substrate="default",
        source="peer_review",
    )
    same = (await agg2.get_reputation(target.vacant_id, "default")).factual.alpha
    # Same-model gets halved → smaller alpha bump.
    assert same < cross
