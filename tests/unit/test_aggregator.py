"""Aggregator API tests + reviewer-eligibility check."""

from __future__ import annotations

import pytest

from vacant.core.crypto import keygen
from vacant.core.types import Logbook, VacantId, VacantState
from vacant.reputation import (
    Aggregator,
    ChainTamperError,
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


# --- F4 / D015 §D: signed REVIEW_EVENT audit trail --------------------------


def _ctx_with_keys(
    *, family: str = "claude", state: VacantState = VacantState.ACTIVE
) -> tuple[VacantContext, Logbook, object]:
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    ctx = VacantContext(
        vacant_id=vid,
        base_model_family=family,
        state=state,
        capability_text="x",
        attestation_level="L1",
    )
    lb = Logbook()
    lb.append("genesis", {}, sk)
    return ctx, lb, sk


@pytest.mark.asyncio
async def test_record_review_appends_signed_review_event() -> None:
    """F4 regression: every reputation change leaves a signed audit trail."""
    a_ctx, a_lb, a_sk = _ctx_with_keys()
    b_ctx, b_lb, b_sk = _ctx_with_keys(family="gemini")
    agg = Aggregator(
        contexts={a_ctx.vacant_id: a_ctx, b_ctx.vacant_id: b_ctx},
        review_limit_per_target_24h=10_000,
        logbooks={a_ctx.vacant_id: a_lb, b_ctx.vacant_id: b_lb},
        signing_keys={a_ctx.vacant_id: a_sk, b_ctx.vacant_id: b_sk},
    )
    initial_chain_len = len(a_lb.entries)
    await agg.record_review(
        a_ctx.vacant_id,
        b_ctx.vacant_id,
        dimensions={"factual": 1.0},
        substrate="default",
        source="caller_review",
    )
    assert len(a_lb.entries) == initial_chain_len + 1
    appended = a_lb.entries[-1]
    assert appended.kind == "REVIEW_EVENT"
    assert appended.payload["target"] == b_ctx.vacant_id.hex()
    assert appended.payload["source"] == "caller_review"
    assert a_lb.verify_chain(a_ctx.vacant_id.verify_key())


@pytest.mark.asyncio
async def test_record_review_with_tampered_logbook_rejects_and_does_not_update_posterior() -> None:
    """F4 regression: tamper the audit chain → ChainTamperError + posterior frozen."""
    a_ctx, a_lb, a_sk = _ctx_with_keys()
    b_ctx, b_lb, b_sk = _ctx_with_keys(family="gemini")
    agg = Aggregator(
        contexts={a_ctx.vacant_id: a_ctx, b_ctx.vacant_id: b_ctx},
        review_limit_per_target_24h=10_000,
        logbooks={a_ctx.vacant_id: a_lb, b_ctx.vacant_id: b_lb},
        signing_keys={a_ctx.vacant_id: a_sk, b_ctx.vacant_id: b_sk},
    )

    # First, record a clean review so a posterior exists.
    await agg.record_review(
        a_ctx.vacant_id,
        b_ctx.vacant_id,
        dimensions={"factual": 1.0},
        substrate="default",
        source="caller_review",
    )
    pre = (await agg.get_reputation(b_ctx.vacant_id, "default")).factual.alpha

    # Now tamper the reviewer's logbook: replace last entry's signature.
    last = a_lb.entries[-1]
    a_lb.entries[-1] = last.model_copy(update={"signature": b"\x00" * 64})

    with pytest.raises(ChainTamperError):
        await agg.record_review(
            a_ctx.vacant_id,
            b_ctx.vacant_id,
            dimensions={"factual": 0.99},
            substrate="default",
            source="caller_review",
        )

    post = (await agg.get_reputation(b_ctx.vacant_id, "default")).factual.alpha
    assert post == pre, "posterior must not change when audit chain fails"


def test_register_audit_attaches_logbook_and_key() -> None:
    a_ctx, a_lb, a_sk = _ctx_with_keys()
    agg = Aggregator(contexts={a_ctx.vacant_id: a_ctx}, review_limit_per_target_24h=10_000)
    assert agg._audit_enabled_for(a_ctx.vacant_id) is False
    agg.register_audit(a_ctx.vacant_id, logbook=a_lb, signing_key=a_sk)
    assert agg._audit_enabled_for(a_ctx.vacant_id) is True


def test_add_context_then_get_context() -> None:
    a_ctx, _lb, _sk = _ctx_with_keys()
    agg = Aggregator()
    agg.add_context(a_ctx)
    assert agg.get_context(a_ctx.vacant_id) is a_ctx


def test_get_context_unknown_raises() -> None:
    agg = Aggregator()
    ghost = VacantId.from_verify_key(keygen()[1])
    with pytest.raises(InvalidSignalError):
        agg.get_context(ghost)


@pytest.mark.asyncio
async def test_record_review_without_audit_registration_is_legacy_path() -> None:
    """Legacy callers (no signing keys) keep working — the audit step is a
    no-op for them. Read paths never require audit setup."""
    a_ctx, _alb, _ask = _ctx_with_keys()
    b_ctx, _blb, _bsk = _ctx_with_keys(family="gemini")
    agg = Aggregator(
        contexts={a_ctx.vacant_id: a_ctx, b_ctx.vacant_id: b_ctx},
        review_limit_per_target_24h=10_000,
    )
    await agg.record_review(
        a_ctx.vacant_id,
        b_ctx.vacant_id,
        dimensions={"factual": 0.7},
        substrate="default",
        source="caller_review",
    )
    rep = await agg.get_reputation(b_ctx.vacant_id, "default")
    assert rep.factual.alpha > 1.0
