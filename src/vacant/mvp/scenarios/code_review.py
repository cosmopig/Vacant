"""Scenario 2 -- code_review: 5 ACTIVE vacants race to review the same
PR; reputation diverges; same-controller signal demonstrably downweights
a colluding ring (P7_demo_seed §"Scenario 2 -- code_review").
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vacant.core.crypto import SigningKey
from vacant.core.types import ResidentForm, VacantState
from vacant.mvp.scenarios._harness import (
    ScenarioResult,
    VacantSeed,
    build_vacant,
    context_from_form,
    reputation_snapshot,
    seeded_random,
)
from vacant.mvp.scenarios._seeds import DEFAULT_SEEDS
from vacant.reputation import Aggregator, SameDetectSignal

if TYPE_CHECKING:
    from vacant.substrate.base import SubstrateBackend


SCENARIO_NAME = "code_review"
N_QUERIES = 100
N_REVIEWERS = 5


async def run(*, substrate: SubstrateBackend, seed: int | None = None) -> ScenarioResult:
    s = seed if seed is not None else DEFAULT_SEEDS[SCENARIO_NAME]
    rng = seeded_random(s)
    result = ScenarioResult(name=SCENARIO_NAME, seed=s)

    # 5 reviewers with different inherent quality profiles. The "true"
    # quality is encoded as the mean of the signal we deliver to the
    # aggregator -- top reviewers get rewarded with high signals,
    # bottom ones with low signals (simulating ground-truth check
    # outcomes).
    quality = [0.92, 0.88, 0.78, 0.55, 0.32]  # decreasing
    reviewers: list[tuple[SigningKey, ResidentForm, VacantSeed]] = []
    for i in range(N_REVIEWERS):
        seed_ = VacantSeed(
            name=f"reviewer-{i}",
            capability_text="code-review",
            base_model_family=("claude" if i < 3 else "gpt"),
            state=VacantState.ACTIVE,
        )
        sk, form = build_vacant(seed_, rng)
        reviewers.append((sk, form, seed_))

    # Author posts the PR (functions as the caller).
    author_seed = VacantSeed(
        name="author",
        capability_text="pr-author",
        base_model_family="gemini",
    )
    sk_author, author_form = build_vacant(author_seed, rng)

    # CI farm: multiple independent oracles emit ground-truth signals so
    # the per-pair novelty decay does not crush long runs.
    ci_seeds = tuple(
        VacantSeed(
            name=f"ci-{i}",
            capability_text="ci-truth-oracle",
            base_model_family="gemini",
        )
        for i in range(10)
    )
    cis = [build_vacant(cs, rng) for cs in ci_seeds]

    contexts = {form.identity: context_from_form(form, ds) for _, form, ds in reviewers}
    contexts[author_form.identity] = context_from_form(author_form, author_seed)
    for cs, (_sk, cform) in zip(ci_seeds, cis, strict=True):
        contexts[cform.identity] = context_from_form(cform, cs)
    aggregator = Aggregator(contexts=contexts)

    rng_jitter = seeded_random(s + 1)
    for q in range(N_QUERIES):
        # All 5 reviewers race; a rotating CI emits a ground-truth signal.
        ci_idx = q % len(cis)
        _sk_ci, ci_form = cis[ci_idx]
        for i, (_sk, form, _vs) in enumerate(reviewers):
            # Light jitter to break ties without flapping the ranking.
            signal = max(0.05, min(0.99, quality[i] + rng_jitter.uniform(-0.03, 0.03)))
            await aggregator.record_review(
                ci_form.identity,
                form.identity,
                dimensions={"factual": signal, "logical": signal, "relevance": signal},
                substrate="default",
                source="ground_truth",
            )
        # Author also gives a caller_review for the top-K reviewers.
        ranked = await aggregator.get_ranked("code-review", n=N_REVIEWERS)
        top3 = {vid for vid, _score in ranked[:3]}
        for vid in top3:
            await aggregator.record_review(
                author_form.identity,
                vid,
                dimensions={"relevance": 0.85},
                substrate="default",
                source="caller_review",
            )
        result.events.append(
            {
                "tick": q,
                "ranked": [(vid.short(), round(score, 3)) for vid, score in ranked],
            }
        )

    # Final ranking (last 20 should be stable; spot-check via metric).
    final_ranking = await aggregator.get_ranked("code-review", n=N_REVIEWERS)
    last20_rankings = [
        tuple(vid for vid, _ in entry["ranked"][:N_REVIEWERS]) for entry in result.events[-20:]
    ]
    distinct_top1 = len({r[0] for r in last20_rankings})
    result.metrics["last20_top1_distinct"] = distinct_top1
    result.metrics["ranking_stable"] = distinct_top1 == 1

    # --- Adversarial sub-scenario: same-controller ring -------------------
    # Re-run the last reviewer with the same controller_id and assert
    # that injecting `SameDetectSignal(strength=1.0)` discounts the
    # subsequent caller_review's effect on the target.
    target_form = reviewers[0][1]
    pre_factual = (await aggregator.get_reputation(target_form.identity, "default")).factual.alpha
    await aggregator.record_review(
        author_form.identity,
        target_form.identity,
        dimensions={"factual": 0.95},
        substrate="default",
        source="caller_review",
        same_signals=[
            SameDetectSignal(strength=1.0, suspected_cluster=frozenset(), rationale="ring")
        ],
    )
    post_factual = (await aggregator.get_reputation(target_form.identity, "default")).factual.alpha
    bump_with_signal = post_factual - pre_factual

    # Compare to a similar review with no same-* signal.
    other_target = reviewers[1][1]
    pre_other = (await aggregator.get_reputation(other_target.identity, "default")).factual.alpha
    await aggregator.record_review(
        author_form.identity,
        other_target.identity,
        dimensions={"factual": 0.95},
        substrate="default",
        source="caller_review",
    )
    post_other = (await aggregator.get_reputation(other_target.identity, "default")).factual.alpha
    bump_no_signal = post_other - pre_other

    # The ring-flagged review's contribution is at most half the
    # un-flagged review's contribution.
    result.metrics["ring_signal_bump"] = bump_with_signal
    result.metrics["unflagged_bump"] = bump_no_signal
    result.metrics["ring_downweighted"] = bump_with_signal <= 0.5 * bump_no_signal + 1e-9

    # Snapshot.
    for i, (_sk, form, _vs) in enumerate(reviewers):
        label = f"reviewer_{i}"
        result.vacants[label] = {
            "vacant_id": form.identity.hex(),
            "state": form.runtime_state.value,
            "capability": form.capability_card.capability_text if form.capability_card else "",
            "quality_seed": quality[i],
        }
        result.reputation[label] = reputation_snapshot(aggregator, form.identity)

    chains_ok = (
        all(form.logbook.verify_chain(form.identity.verify_key()) for _, form, _ in reviewers)
        and author_form.logbook.verify_chain(author_form.identity.verify_key())
        and all(cf.logbook.verify_chain(cf.identity.verify_key()) for _, cf in cis)
    )
    result.logbook_chains_ok = chains_ok
    result.metrics["final_ranking"] = [vid.short() for vid, _ in final_ranking]
    result.metrics["n_queries"] = N_QUERIES
    _ = sk_author
    return result


__all__ = ["SCENARIO_NAME", "run"]
