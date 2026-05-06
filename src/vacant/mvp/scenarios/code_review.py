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
from vacant.reputation import Aggregator
from vacant.reputation.same_detect import same_controller

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
    aggregator = Aggregator(contexts=contexts, review_limit_per_target_24h=1_000)

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

    # --- Adversarial sub-scenario: same-controller detector evaluation ---
    # F5: run the *real* `same_controller(...)` detector on a seeded
    # colluding pair and a non-colluding control. The detector's actual
    # output (not a hardcoded SameDetectSignal) feeds the aggregator.
    #
    # Colluding pair: reviewers[0] and reviewers[1] share a declared
    # controller_id, exhibit correlated heartbeat timing, and have
    # near-identical behavioural fingerprints (the three signals T5
    # §3.2 stacks). Non-colluding control: reviewers[3] vs reviewers[4]
    # — distinct families and uncorrelated behaviour.
    rng_collude = seeded_random(s + 2)
    base_heartbeat = [rng_collude.uniform(0.3, 1.0) for _ in range(20)]

    def _correlated(series: list[float], jitter: float) -> list[float]:
        return [x + rng_collude.uniform(-jitter, jitter) for x in series]

    colluding_a = reviewers[0][1]
    colluding_b = reviewers[1][1]
    control_a = reviewers[3][1]
    control_b = reviewers[4][1]

    behavior_collude = [rng_collude.uniform(0.0, 1.0) for _ in range(16)]
    behavior_collude_b = _correlated(behavior_collude, jitter=0.01)
    behavior_control_a = [rng_collude.uniform(0.0, 1.0) for _ in range(16)]
    behavior_control_b = [rng_collude.uniform(0.0, 1.0) for _ in range(16)]

    colluding_signal = same_controller(
        colluding_a.identity,
        colluding_b.identity,
        declared_same=True,
        heartbeat_a=base_heartbeat,
        heartbeat_b=_correlated(base_heartbeat, jitter=0.02),
        behavior_a=behavior_collude,
        behavior_b=behavior_collude_b,
    )
    control_signal = same_controller(
        control_a.identity,
        control_b.identity,
        declared_same=False,
        heartbeat_a=[rng_collude.uniform(0.3, 1.0) for _ in range(20)],
        heartbeat_b=[rng_collude.uniform(0.3, 1.0) for _ in range(20)],
        behavior_a=behavior_control_a,
        behavior_b=behavior_control_b,
    )

    # TP / FP rate over a few seeded probes so the dashboard has something
    # numeric to display rather than a single point estimate.
    n_probes = 10
    tp_hits = 0
    fp_hits = 0
    for _ in range(n_probes):
        tp_sig = same_controller(
            colluding_a.identity,
            colluding_b.identity,
            declared_same=True,
            heartbeat_a=base_heartbeat,
            heartbeat_b=_correlated(base_heartbeat, jitter=0.02),
            behavior_a=behavior_collude,
            behavior_b=_correlated(behavior_collude, jitter=0.02),
        )
        if tp_sig.strength > 0.5:
            tp_hits += 1
        fp_sig = same_controller(
            control_a.identity,
            control_b.identity,
            declared_same=False,
            heartbeat_a=[rng_collude.uniform(0.3, 1.0) for _ in range(20)],
            heartbeat_b=[rng_collude.uniform(0.3, 1.0) for _ in range(20)],
            behavior_a=[rng_collude.uniform(0.0, 1.0) for _ in range(16)],
            behavior_b=[rng_collude.uniform(0.0, 1.0) for _ in range(16)],
        )
        if fp_sig.strength > 0.5:
            fp_hits += 1
    tp_rate = tp_hits / n_probes
    fp_rate = fp_hits / n_probes

    # Feed the *actual* detector output through the aggregator on a
    # caller_review against the suspected ring and observe the discount.
    pre_factual = (await aggregator.get_reputation(colluding_a.identity, "default")).factual.alpha
    await aggregator.record_review(
        author_form.identity,
        colluding_a.identity,
        dimensions={"factual": 0.95},
        substrate="default",
        source="caller_review",
        same_signals=[colluding_signal],
    )
    post_factual = (await aggregator.get_reputation(colluding_a.identity, "default")).factual.alpha
    bump_with_signal = post_factual - pre_factual

    pre_other = (await aggregator.get_reputation(control_a.identity, "default")).factual.alpha
    await aggregator.record_review(
        author_form.identity,
        control_a.identity,
        dimensions={"factual": 0.95},
        substrate="default",
        source="caller_review",
        same_signals=[control_signal],
    )
    post_other = (await aggregator.get_reputation(control_a.identity, "default")).factual.alpha
    bump_no_signal = post_other - pre_other

    result.metrics["ring_signal_strength"] = colluding_signal.strength
    result.metrics["control_signal_strength"] = control_signal.strength
    result.metrics["ring_signal_rationale"] = colluding_signal.rationale
    result.metrics["ring_signal_bump"] = bump_with_signal
    result.metrics["unflagged_bump"] = bump_no_signal
    # Cost-raising, not preventing (D015 §A): bump_with_signal must be
    # below the unflagged bump but never zero.
    result.metrics["ring_downweighted"] = (
        bump_with_signal < bump_no_signal and bump_with_signal > 0.0
    )
    result.metrics["same_controller_tp_rate"] = tp_rate
    result.metrics["same_controller_fp_rate"] = fp_rate
    # Spec thresholds the dashboard surfaces: TP >= 0.8, FP <= 0.1.
    result.metrics["same_controller_tp_meets_threshold"] = tp_rate >= 0.8
    result.metrics["same_controller_fp_meets_threshold"] = fp_rate <= 0.1

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
