"""End-to-end reputation simulation: 20 vacants, 1000 calls.

Per dispatch §Tests: 20-vacant network, 1000 calls, reputation
distribution stabilizes with high-quality on top, low-quality below 0.3
mean across dimensions.
"""

from __future__ import annotations

import random

import pytest

from vacant.core.crypto import keygen
from vacant.core.types import VacantId, VacantState
from vacant.reputation import (
    Aggregator,
    VacantContext,
)

pytestmark = pytest.mark.slow


@pytest.mark.asyncio
async def test_reputation_distribution_stabilises_after_1000_reviews() -> None:
    rng = random.Random(42)
    n = 20

    # Half high-quality (signal ~ 0.85), half low-quality (signal ~ 0.20).
    high_quality_ids: list[VacantId] = []
    low_quality_ids: list[VacantId] = []
    contexts: dict[VacantId, VacantContext] = {}
    for i in range(n):
        _sk, vk = keygen()
        vid = VacantId.from_verify_key(vk)
        contexts[vid] = VacantContext(
            vacant_id=vid,
            base_model_family="claude" if i % 2 == 0 else "gemini",
            state=VacantState.ACTIVE,
            capability_text="task",
            attestation_level="L1",
        )
        if i < n // 2:
            high_quality_ids.append(vid)
        else:
            low_quality_ids.append(vid)

    agg = Aggregator(contexts=contexts, review_limit_per_target_24h=10_000)

    all_ids = list(contexts.keys())
    for _ in range(1000):
        target = rng.choice(all_ids)
        # Reviewer is any other vacant.
        candidates = [v for v in all_ids if v != target]
        reviewer = rng.choice(candidates)
        if target in high_quality_ids:
            base_score = 0.85
        else:
            base_score = 0.20
        # Add noise so the distribution isn't trivially separable on N=1.
        score = max(0.0, min(1.0, base_score + rng.gauss(0, 0.08)))
        await agg.record_review(
            reviewer,
            target,
            dimensions={"factual": score, "logical": score, "relevance": score},
            substrate="default",
            source="caller_review",
        )

    # Now check the distribution.
    high_means = []
    for vid in high_quality_ids:
        rep = await agg.get_reputation(vid, "default")
        high_means.append(rep.factual.mean)
    low_means = []
    for vid in low_quality_ids:
        rep = await agg.get_reputation(vid, "default")
        low_means.append(rep.factual.mean)

    avg_high = sum(high_means) / len(high_means)
    avg_low = sum(low_means) / len(low_means)
    # High-quality must dominate.
    assert avg_high > avg_low
    # Low-quality must drop below 0.3 (per dispatch acceptance).
    assert avg_low < 0.3, f"low-quality avg should be < 0.3 after 1000 reviews; got {avg_low:.3f}"
    # High-quality stays high (relaxed: > 0.6 -- discounts and noise eat
    # the absolute level).
    assert avg_high > 0.6, (
        f"high-quality avg should be > 0.6 after 1000 reviews; got {avg_high:.3f}"
    )


@pytest.mark.asyncio
async def test_reputation_e2e_chain_stays_consistent() -> None:
    """After many updates, no posterior goes negative or NaN."""
    rng = random.Random(137)
    contexts: dict[VacantId, VacantContext] = {}
    ids: list[VacantId] = []
    for _ in range(8):
        _sk, vk = keygen()
        vid = VacantId.from_verify_key(vk)
        contexts[vid] = VacantContext(vacant_id=vid)
        ids.append(vid)
    agg = Aggregator(contexts=contexts, review_limit_per_target_24h=10_000)
    for _ in range(200):
        a, b = rng.sample(ids, 2)
        score = rng.uniform(0, 1)
        await agg.record_review(
            a,
            b,
            dimensions={"factual": score},
            substrate="default",
            source="peer_review",
        )
    # All reputations finite + non-negative.
    for vid in ids:
        rep = await agg.get_reputation(vid, "default")
        for d in ("factual", "logical", "relevance", "honesty", "adoption"):
            beta = rep.get(d)
            assert beta.alpha >= 0
            assert beta.beta >= 0
            assert 0 <= beta.mean <= 1
