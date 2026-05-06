"""Padv P3 -- Sybil-ring attacks against the reputation aggregator.

Spec anchors:
- `architecture/components/P3_reputation.md` §3.4.1 (same-base-model
  discount), §3.4.3 (novelty), §3.4.4 (collusion graph)
- `architecture/research/T5_same_controller.md` §3.2 (three-layer pipeline)
- `dispatch/Padv_review.md` §"Sybil ring"
- `architecture/decisions/D010_padv_p3_findings.md` (this PR's findings)
"""

from __future__ import annotations

import pytest

from vacant.core.crypto import keygen
from vacant.core.types import VacantId, VacantState
from vacant.reputation import (
    Aggregator,
    SameDetectSignal,
    VacantContext,
    discount_from_signals,
    same_substrate,
)


def _ctx(*, family: str = "claude", state: VacantState = VacantState.ACTIVE) -> VacantContext:
    _sk, vk = keygen()
    return VacantContext(
        vacant_id=VacantId.from_verify_key(vk),
        base_model_family=family,
        state=state,
        capability_text="x",
        attestation_level="L1",
    )


def _agg(*ctxs: VacantContext, **kw) -> Aggregator:  # type: ignore[no-untyped-def]
    return Aggregator(
        contexts={c.vacant_id: c for c in ctxs},
        review_limit_per_target_24h=10_000,
        **kw,
    )


# --- Attack 1: Sybil ring of same-base-model peers --------------------------
# Defense (D, cost-raising): same-substrate detector fires (strength=1),
# the aggregator halves the review weight (`SAME_BASE_MODEL_DISCOUNT = 0.5`),
# and the 6th+ same-model review against the same target is further
# discounted to 0.25x (`SAME_MODEL_HEAVY_DISCOUNT`). Combined with
# novelty decay (per-(reviewer, target) pair) the ring's effective
# weight on the target decays sharply.


@pytest.mark.asyncio
async def test_attack_same_family_ring_review_weight_halved() -> None:
    target = _ctx(family="claude")
    ring_member = _ctx(family="claude")
    independent_reviewer = _ctx(family="gemini")
    agg = _agg(target, ring_member, independent_reviewer)

    # First review: same-family peer (gets halved).
    await agg.record_review(
        ring_member.vacant_id,
        target.vacant_id,
        dimensions={"factual": 1.0},
        substrate="default",
        source="peer_review",
    )
    same_alpha = (await agg.get_reputation(target.vacant_id, "default")).factual.alpha

    # Reset; now an independent (different-family) reviewer.
    agg2 = _agg(target, ring_member, independent_reviewer)
    await agg2.record_review(
        independent_reviewer.vacant_id,
        target.vacant_id,
        dimensions={"factual": 1.0},
        substrate="default",
        source="peer_review",
    )
    different_alpha = (await agg2.get_reputation(target.vacant_id, "default")).factual.alpha
    assert different_alpha > same_alpha


@pytest.mark.asyncio
async def test_attack_same_family_ring_caught_by_same_substrate_signal() -> None:
    a = _ctx(family="claude")
    b = _ctx(family="claude")
    sig = same_substrate(a.vacant_id, b.vacant_id, family_a="claude", family_b="claude")
    assert sig.strength == 1.0
    assert {a.vacant_id, b.vacant_id} == sig.suspected_cluster


@pytest.mark.asyncio
async def test_attack_independent_reviewers_not_flagged_as_same() -> None:
    a = _ctx(family="claude")
    b = _ctx(family="gemini")
    sig = same_substrate(a.vacant_id, b.vacant_id, family_a="claude", family_b="gemini")
    assert sig.strength == 0.0


# --- Attack 2: novelty decay on repeated reviews ----------------------------
# Defense (P): per-(reviewer, target) novelty factor decays each repeat
# review's weight. `discount_from_signals([{strength=0.7}, ...]) → 0.3`
# composes the same-* signals into the per-review weight multiplier.


@pytest.mark.asyncio
async def test_attack_repeat_reviews_decay_via_novelty() -> None:
    target = _ctx(family="gemini")
    reviewer = _ctx(family="gemini")
    agg = _agg(target, reviewer)
    alphas = []
    for _ in range(5):
        await agg.record_review(
            reviewer.vacant_id,
            target.vacant_id,
            dimensions={"factual": 1.0},
            substrate="default",
            source="peer_review",
        )
        alphas.append((await agg.get_reputation(target.vacant_id, "default")).factual.alpha)
    # Each successive review's bump shrinks (novelty + heavy-discount kick in).
    bumps = [alphas[i + 1] - alphas[i] for i in range(len(alphas) - 1)]
    # Each bump is non-increasing.
    from itertools import pairwise

    for prev, cur in pairwise(bumps):
        assert cur <= prev + 1e-9


@pytest.mark.asyncio
async def test_attack_caller_bypassing_signals_via_signal_param() -> None:
    """A caller-provided same-* signal collection composes correctly."""
    target = _ctx(family="claude")
    reviewer = _ctx(family="gemini")
    agg = _agg(target, reviewer)

    high_strength = [
        SameDetectSignal(strength=0.9, suspected_cluster=frozenset(), rationale="x"),
    ]
    await agg.record_review(
        reviewer.vacant_id,
        target.vacant_id,
        dimensions={"factual": 1.0},
        substrate="default",
        source="peer_review",
        same_signals=high_strength,
    )
    rep_after_flagged = (await agg.get_reputation(target.vacant_id, "default")).factual.alpha

    agg2 = _agg(target, reviewer)
    await agg2.record_review(
        reviewer.vacant_id,
        target.vacant_id,
        dimensions={"factual": 1.0},
        substrate="default",
        source="peer_review",
        same_signals=[],
    )
    rep_unflagged = (await agg2.get_reputation(target.vacant_id, "default")).factual.alpha
    # Flagged review contributes much less.
    assert rep_after_flagged < rep_unflagged


@pytest.mark.asyncio
async def test_attack_discount_from_signals_takes_max_strength() -> None:
    sigs = [
        SameDetectSignal(strength=0.2, suspected_cluster=frozenset(), rationale="a"),
        SameDetectSignal(strength=0.95, suspected_cluster=frozenset(), rationale="b"),
        SameDetectSignal(strength=0.4, suspected_cluster=frozenset(), rationale="c"),
    ]
    # Conservative composition: max(SAME_SIGNAL_DISCOUNT_FLOOR, 1 - max(0.95))
    # = max(0.1, 0.05) = 0.1 (D015 §A — cost-raising, not preventing).
    from vacant.core.constants import SAME_SIGNAL_DISCOUNT_FLOOR

    assert discount_from_signals(sigs) == pytest.approx(SAME_SIGNAL_DISCOUNT_FLOOR)
