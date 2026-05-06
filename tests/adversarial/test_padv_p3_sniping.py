"""Padv P3 -- sniping attacks (per-target review rate limiting).

Spec anchors:
- `architecture/CONSTANTS.md` §Review limits (`REVIEW_LIMIT_PER_TARGET_24H = 3`)
- `dispatch/Padv_review.md` §"Sniping"
- `architecture/decisions/D010_padv_p3_findings.md` §1
"""

from __future__ import annotations

import pytest

from vacant.core.crypto import keygen
from vacant.core.types import VacantId, VacantState
from vacant.reputation import (
    Aggregator,
    ReviewRateLimitError,
    VacantContext,
)


def _ctx(*, family: str = "claude", state: VacantState = VacantState.ACTIVE) -> VacantContext:
    _sk, vk = keygen()
    return VacantContext(
        vacant_id=VacantId.from_verify_key(vk),
        base_model_family=family,
        state=state,
        attestation_level="L1",
    )


def _agg(*ctxs: VacantContext, **kw) -> Aggregator:  # type: ignore[no-untyped-def]
    return Aggregator(contexts={c.vacant_id: c for c in ctxs}, **kw)


# --- Attack 1: single sniper floods reviews against one target -------------
# Defense (P): aggregator enforces `REVIEW_LIMIT_PER_TARGET_24H = 3` over
# a 24h sliding window. The 4th review against the same target within
# the window raises `ReviewRateLimitError` regardless of who submitted it.


@pytest.mark.asyncio
async def test_attack_sniper_blocked_at_default_3_per_24h() -> None:
    target = _ctx()
    sniper = _ctx(family="gemini")
    agg = _agg(target, sniper)

    # 3 reviews succeed.
    for _ in range(3):
        await agg.record_review(
            sniper.vacant_id,
            target.vacant_id,
            dimensions={"factual": 0.1},  # low score (downward sniping)
            substrate="default",
            source="caller_review",
        )
    # 4th raises.
    with pytest.raises(ReviewRateLimitError):
        await agg.record_review(
            sniper.vacant_id,
            target.vacant_id,
            dimensions={"factual": 0.1},
            substrate="default",
            source="caller_review",
        )


@pytest.mark.asyncio
async def test_attack_sniping_via_distinct_reviewers_still_blocked() -> None:
    """The rate limit is per-target, not per-reviewer -- three distinct
    reviewers can't bypass it by rotating identities."""
    target = _ctx()
    snipers = [_ctx(family=f"family-{i}") for i in range(5)]
    agg = _agg(target, *snipers)

    # First 3 reviewers each get one shot at the target.
    for s in snipers[:3]:
        await agg.record_review(
            s.vacant_id,
            target.vacant_id,
            dimensions={"factual": 0.1},
            substrate="default",
            source="caller_review",
        )
    # 4th reviewer is blocked even though it's their first review.
    with pytest.raises(ReviewRateLimitError):
        await agg.record_review(
            snipers[3].vacant_id,
            target.vacant_id,
            dimensions={"factual": 0.1},
            substrate="default",
            source="caller_review",
        )


@pytest.mark.asyncio
async def test_attack_separate_targets_independent_quotas() -> None:
    """Each target's quota is independent -- flooding one target doesn't
    reduce another target's available reviews."""
    target_a = _ctx()
    target_b = _ctx(family="gemini")
    sniper = _ctx(family="qwen")
    agg = _agg(target_a, target_b, sniper)

    for _ in range(3):
        await agg.record_review(
            sniper.vacant_id,
            target_a.vacant_id,
            dimensions={"factual": 0.5},
            substrate="default",
            source="caller_review",
        )
    # target_a is exhausted; target_b is still fresh.
    with pytest.raises(ReviewRateLimitError):
        await agg.record_review(
            sniper.vacant_id,
            target_a.vacant_id,
            dimensions={"factual": 0.5},
            substrate="default",
            source="caller_review",
        )
    # First-of-quota against target_b succeeds.
    await agg.record_review(
        sniper.vacant_id,
        target_b.vacant_id,
        dimensions={"factual": 0.5},
        substrate="default",
        source="caller_review",
    )


@pytest.mark.asyncio
async def test_attack_window_evicts_after_24h() -> None:
    """A review whose timestamp is > 24h old no longer counts toward the
    sliding-window quota."""
    target = _ctx()
    reviewer = _ctx(family="gemini")
    agg = _agg(target, reviewer)

    # Old reviews far in the past.
    base_ts = 1_000_000_000.0
    for i in range(3):
        await agg.record_review(
            reviewer.vacant_id,
            target.vacant_id,
            dimensions={"factual": 0.5},
            substrate="default",
            source="caller_review",
            ts=base_ts + i,
        )
    # 25h later, the old reviews evict.
    later = base_ts + 25 * 3600
    await agg.record_review(
        reviewer.vacant_id,
        target.vacant_id,
        dimensions={"factual": 0.5},
        substrate="default",
        source="caller_review",
        ts=later,
    )


@pytest.mark.asyncio
async def test_attack_custom_limit_honoured() -> None:
    """Operators can configure a different per-target limit (e.g. for
    integration tests / demo orchestration)."""
    target = _ctx()
    reviewer = _ctx(family="gemini")
    agg = _agg(target, reviewer, review_limit_per_target_24h=2)
    for _ in range(2):
        await agg.record_review(
            reviewer.vacant_id,
            target.vacant_id,
            dimensions={"factual": 0.5},
            substrate="default",
            source="caller_review",
        )
    with pytest.raises(ReviewRateLimitError):
        await agg.record_review(
            reviewer.vacant_id,
            target.vacant_id,
            dimensions={"factual": 0.5},
            substrate="default",
            source="caller_review",
        )
