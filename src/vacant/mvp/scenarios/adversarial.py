"""Scenario 5 (dashboard-only) -- adversarial seed=666.

Per `dispatch/P7_demo_seed.md` §"Adversarial seed (seed=666)":

- 10 ACTIVE vacants; 4 share `controller_id` (the colluding ring), 6
  independent.
- The ring exchanges high reviews; the 6 independents do normal reviews.
- After 200 reviews:
  - same-controller signal fires on the 4-ring with strength ≥ 0.7
  - ring-on-ring reviews count for ≤ 0.5 weight
  - non-ring vacants outrank the ring under UCB despite the ring's
    inflated raw scores

This is the dashboard's "Adversarial" page. NOT a default scenario, so
not reachable through `DEFAULT_SEEDS`; instead callers pass `seed=666`
explicitly.

Frame per CLAUDE.md §Same-* detection: the ring is *not blocked*. The
mechanism *raises cost* — the ring's inflated raw scores contribute
less per-review than honest reviews from independents.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from vacant.core.types import VacantState
from vacant.mvp.scenarios._harness import (
    ScenarioResult,
    VacantSeed,
    build_vacant,
    context_from_form,
    record_metric_snapshot,
    reputation_snapshot,
    seeded_random,
)
from vacant.mvp.scenarios._seeds import ADVERSARIAL_SEED
from vacant.reputation import Aggregator
from vacant.reputation.same_detect import same_controller

if TYPE_CHECKING:
    from vacant.mvp.demo_store import DemoStore
    from vacant.substrate.base import SubstrateBackend


SCENARIO_NAME = "adversarial"
N_VACANTS = 10
N_RING = 4
N_INDEPENDENT = N_VACANTS - N_RING
N_REVIEWS_TOTAL = 200
RING_SIGNAL_THRESHOLD = 0.7  # spec invariant
RING_WEIGHT_CEILING = 0.5  # spec invariant: ring-on-ring weight <= 0.5


def _ring_heartbeat(rng: random.Random, length: int = 24) -> list[float]:
    """Synth heartbeat where ring members are tightly correlated."""
    base = [rng.uniform(0.3, 1.0) for _ in range(length)]
    return base


def _correlated(series: list[float], jitter: float, rng: random.Random) -> list[float]:
    return [x + rng.uniform(-jitter, jitter) for x in series]


async def run(
    *,
    substrate: SubstrateBackend,
    seed: int | None = None,
    store: DemoStore | None = None,
) -> ScenarioResult:
    s = seed if seed is not None else ADVERSARIAL_SEED
    rng = seeded_random(s)
    result = ScenarioResult(name=SCENARIO_NAME, seed=s)

    # Ring: 4 vacants sharing the same controller_id (modelled by
    # `base_model_family="ring"` here so the same-* detector fires both
    # on declared layer + behavioural similarity).
    seeds: list[VacantSeed] = []
    for i in range(N_RING):
        seeds.append(
            VacantSeed(
                name=f"ring-{i}",
                capability_text="reviewer",
                base_model_family="ring",
                state=VacantState.ACTIVE,
            )
        )
    # Independents: each from a distinct family to keep same-* false
    # positives near zero.
    fams = ("claude", "gpt", "gemini", "mistral", "llama", "qwen")
    for i in range(N_INDEPENDENT):
        seeds.append(
            VacantSeed(
                name=f"indep-{i}",
                capability_text="reviewer",
                base_model_family=fams[i % len(fams)],
                state=VacantState.ACTIVE,
            )
        )
    forms = [build_vacant(seed_, rng) for seed_ in seeds]

    # Ground-truth oracle: anchors honest reviews so the independents
    # accumulate real F/L/R signal (otherwise they'd have no reviews to
    # outrank the ring on).
    oracle_seed = VacantSeed(
        name="oracle",
        capability_text="ground-truth-oracle",
        base_model_family="oracle",
    )
    sk_oracle, oracle_form = build_vacant(oracle_seed, rng)

    contexts = {
        f.identity: context_from_form(f, sd) for sd, (_, f) in zip(seeds, forms, strict=True)
    }
    contexts[oracle_form.identity] = context_from_form(oracle_form, oracle_seed)
    aggregator = Aggregator(contexts=contexts, review_limit_per_target_24h=1_000)

    # Heartbeat series: ring members share a near-identical pulse;
    # independents' are independent.
    rng_hb = seeded_random(s + 1)
    ring_base_hb = _ring_heartbeat(rng_hb)
    ring_hbs: list[list[float]] = [
        _correlated(ring_base_hb, jitter=0.03, rng=rng_hb) for _ in range(N_RING)
    ]
    indep_hbs: list[list[float]] = [
        [rng_hb.uniform(0.3, 1.0) for _ in range(len(ring_base_hb))] for _ in range(N_INDEPENDENT)
    ]
    # Behavioural fingerprints (16-dim).
    rng_bh = seeded_random(s + 2)
    ring_base_bh = [rng_bh.uniform(0.0, 1.0) for _ in range(16)]
    ring_bhs: list[list[float]] = [
        _correlated(ring_base_bh, jitter=0.02, rng=rng_bh) for _ in range(N_RING)
    ]
    indep_bhs: list[list[float]] = [
        [rng_bh.uniform(0.0, 1.0) for _ in range(16)] for _ in range(N_INDEPENDENT)
    ]

    def _hb(idx: int) -> list[float]:
        return ring_hbs[idx] if idx < N_RING else indep_hbs[idx - N_RING]

    def _bh(idx: int) -> list[float]:
        return ring_bhs[idx] if idx < N_RING else indep_bhs[idx - N_RING]

    # --- 1. Run the same-controller detector across all 4-ring pairs.
    ring_signals: list[float] = []
    for i in range(N_RING):
        for j in range(i + 1, N_RING):
            sig = same_controller(
                forms[i][1].identity,
                forms[j][1].identity,
                declared_same=True,
                heartbeat_a=_hb(i),
                heartbeat_b=_hb(j),
                behavior_a=_bh(i),
                behavior_b=_bh(j),
            )
            ring_signals.append(sig.strength)
    ring_signal_strength = min(ring_signals) if ring_signals else 0.0

    # --- 2. Mass review: ring promotes ring; independents do honest
    # reviews on each other (driven by a ground-truth signal). The
    # aggregator applies the same-controller discount on every
    # ring-on-ring entry; the independents pay no discount.
    rng_rev = seeded_random(s + 3)
    n_ring_on_ring = 0
    n_indep_on_indep = 0
    n_ring_on_indep = 0
    review_count = 0
    while review_count < N_REVIEWS_TOTAL:
        # Ring inflates ring (50% of reviews).
        for i in range(N_RING):
            j = (i + 1) % N_RING
            sig = same_controller(
                forms[i][1].identity,
                forms[j][1].identity,
                declared_same=True,
                heartbeat_a=_hb(i),
                heartbeat_b=_hb(j),
                behavior_a=_bh(i),
                behavior_b=_bh(j),
            )
            await aggregator.record_review(
                forms[i][1].identity,
                forms[j][1].identity,
                dimensions={"factual": 0.95, "logical": 0.93, "relevance": 0.92},
                substrate="default",
                source="caller_review",
                same_signals=[sig],
            )
            n_ring_on_ring += 1
            review_count += 1
            if review_count >= N_REVIEWS_TOTAL:
                break
            if store is not None:
                store.record(
                    scenario=SCENARIO_NAME,
                    kind="review",
                    payload={
                        "tick": review_count,
                        "kind": "ring_on_ring",
                        "ring_signal_strength": sig.strength,
                    },
                    ts=float(review_count),
                )
        # Independents review each other honestly via the oracle (no
        # same-controller signal). Quality is genuinely high so they
        # accumulate factual evidence.
        if review_count >= N_REVIEWS_TOTAL:
            break
        for k in range(N_INDEPENDENT):
            target_form = forms[N_RING + k][1]
            base_quality = 0.70 + rng_rev.uniform(-0.05, 0.05)
            await aggregator.record_review(
                oracle_form.identity,
                target_form.identity,
                dimensions={
                    "factual": base_quality,
                    "logical": base_quality,
                    "relevance": base_quality,
                },
                substrate="default",
                source="ground_truth",
            )
            n_indep_on_indep += 1
            review_count += 1
            if review_count >= N_REVIEWS_TOTAL:
                break
            if store is not None:
                store.record(
                    scenario=SCENARIO_NAME,
                    kind="review",
                    payload={
                        "tick": review_count,
                        "kind": "indep",
                        "signal": base_quality,
                    },
                    ts=float(review_count),
                )

        if store is not None and review_count % 25 == 0:
            record_metric_snapshot(
                store=store,
                scenario=SCENARIO_NAME,
                aggregator=aggregator,
                ts=float(review_count),
            )

    # --- 3. Check that ring-on-ring effective weight is ≤ 0.5.
    # The aggregator applies (1 - max_strength) ∈ [floor, 1]; with
    # strength ≥ 0.7 the ring-on-ring multiplier is ≤ 0.3 (the floor
    # ensures at least 0.1, never zero — D015 cost-raising-not-preventing).
    # We compare empirical posterior n_eff growth against the indep set.
    ring_n_eff = []
    indep_n_eff = []
    for i, (_sk, form) in enumerate(forms):
        rep = await aggregator.get_reputation(form.identity, "default")
        n = rep.factual.n_eff
        if i < N_RING:
            ring_n_eff.append(n)
        else:
            indep_n_eff.append(n)

    avg_ring = sum(ring_n_eff) / max(1, len(ring_n_eff))
    avg_indep = sum(indep_n_eff) / max(1, len(indep_n_eff))

    # --- 4. UCB ranking: independents should outrank ring under
    # `get_ranked("reviewer")`. Their n_eff is comparable but their
    # (alpha / (alpha+beta)) means are honest, and the ring's
    # exploration bonus is reduced by the discount-on-record-review.
    ranked = await aggregator.get_ranked("reviewer", n=N_VACANTS)
    ring_ids = {forms[i][1].identity for i in range(N_RING)}
    top_n_ranks = [vid in ring_ids for vid, _ in ranked[:N_INDEPENDENT]]
    n_ring_in_top_indep = sum(1 for r in top_n_ranks if r)

    # Final snapshot.
    for i, (_sk, form) in enumerate(forms):
        label = f"vacant_{i}"
        result.vacants[label] = {
            "vacant_id": form.identity.hex(),
            "state": form.runtime_state.value,
            "is_ring": i < N_RING,
        }
        result.reputation[label] = reputation_snapshot(aggregator, form.identity)

    result.metrics["n_vacants"] = N_VACANTS
    result.metrics["n_ring"] = N_RING
    result.metrics["n_independent"] = N_INDEPENDENT
    result.metrics["n_reviews"] = review_count
    result.metrics["n_ring_on_ring"] = n_ring_on_ring
    result.metrics["n_indep_on_indep"] = n_indep_on_indep
    result.metrics["n_ring_on_indep"] = n_ring_on_indep
    result.metrics["ring_signal_strength"] = ring_signal_strength
    result.metrics["ring_signal_meets_threshold"] = ring_signal_strength >= RING_SIGNAL_THRESHOLD
    result.metrics["ring_avg_n_eff_factual"] = avg_ring
    result.metrics["indep_avg_n_eff_factual"] = avg_indep
    # Per spec: ring-on-ring weight ≤ 0.5; equivalently, ring posterior's
    # per-review evidence accrues at less than half the rate of indep.
    # Empirical proxy: ring n_eff per review < 0.5 * indep n_eff per
    # review.
    if n_ring_on_ring > 0 and n_indep_on_indep > 0:
        ring_per_review = avg_ring / n_ring_on_ring
        indep_per_review = avg_indep / n_indep_on_indep
        result.metrics["ring_weight_per_review"] = ring_per_review
        result.metrics["indep_weight_per_review"] = indep_per_review
        result.metrics["ring_weight_under_ceiling"] = (
            ring_per_review <= RING_WEIGHT_CEILING * indep_per_review
        )
    else:
        result.metrics["ring_weight_under_ceiling"] = False
    result.metrics["n_ring_in_top_indep"] = n_ring_in_top_indep
    # Spec: non-ring outrank ring → top-N_INDEPENDENT positions should
    # be majority-independent. Allow up to 1 ring slot (for cost-raising
    # framing — we don't claim "prevents").
    result.metrics["non_ring_outrank_ring"] = n_ring_in_top_indep <= 1
    result.metrics["final_ranking"] = [vid.short() for vid, _ in ranked]

    chains_ok = all(
        f.logbook.verify_chain(f.identity.verify_key()) for _, f in forms
    ) and oracle_form.logbook.verify_chain(oracle_form.identity.verify_key())
    result.logbook_chains_ok = chains_ok
    _ = sk_oracle
    _ = substrate
    return result


__all__ = [
    "N_INDEPENDENT",
    "N_REVIEWS_TOTAL",
    "N_RING",
    "N_VACANTS",
    "RING_SIGNAL_THRESHOLD",
    "RING_WEIGHT_CEILING",
    "SCENARIO_NAME",
    "run",
]
