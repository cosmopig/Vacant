"""Scenario 3 -- multilingual_translation: cross-substrate dispatch.

6 vacants ("translator") each declare different `substrate_spec.allowed_substrates`:
- 2 prefer `claude-sonnet-4-6`
- 2 prefer `gpt-4o`
- 2 prefer `local-ollama-llama3`

10 queries each in en->zh, en->ja, en->es, en->fr (40 total per pair).
The aggregator tracks separate posteriors per `(vacant_id, substrate)`.
A vacant successfully serving across >=2 substrates earns a
`portability_factor` bonus (+0.05 across F).
"""

from __future__ import annotations

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
from vacant.mvp.scenarios._seeds import DEFAULT_SEEDS
from vacant.reputation import Aggregator
from vacant.reputation.portability import compute_portability

if TYPE_CHECKING:
    from vacant.mvp.demo_store import DemoStore
    from vacant.substrate.base import SubstrateBackend

SCENARIO_NAME = "multilingual_translation"

SUBSTRATES = ("claude-sonnet-4-6", "gpt-4o", "local-ollama-llama3")
LANGS = ("en->zh", "en->ja", "en->es", "en->fr")
# B5: penalty applied when a vacant is caught claiming a substrate it
# can't actually run (THEORY_V5 §6 false-substrate-claim defense).
FALSE_SUBSTRATE_CLAIM_FACTUAL_PENALTY = 0.05


async def run(
    *,
    substrate: SubstrateBackend,
    seed: int | None = None,
    store: DemoStore | None = None,
) -> ScenarioResult:
    s = seed if seed is not None else DEFAULT_SEEDS[SCENARIO_NAME]
    rng = seeded_random(s)
    result = ScenarioResult(name=SCENARIO_NAME, seed=s)

    # 6 vacants: 2 per substrate slot. Vacant #0 declares two substrates
    # so we can demonstrate the portability_factor.
    seeds = []
    for i in range(6):
        primary = SUBSTRATES[i // 2]
        allowed: tuple[str, ...] = (primary,)
        if i == 0:
            # Vacant 0 is the "polyglot" -- claude + gpt-4o.
            allowed = (primary, SUBSTRATES[1])
        seeds.append(
            VacantSeed(
                name=f"translator-{i}",
                capability_text="translator",
                base_model_family="claude"
                if "claude" in primary
                else ("gpt" if "gpt" in primary else "ollama"),
                state=VacantState.ACTIVE,
                allowed_substrates=allowed,
            )
        )
    forms = [build_vacant(seed_, rng) for seed_ in seeds]

    # CI oracle for ground-truth signals.
    ci_seed = VacantSeed(
        name="translation-ci",
        capability_text="translation-truth-oracle",
        base_model_family="gemini",
    )
    sk_ci, ci_form = build_vacant(ci_seed, rng)

    contexts = {
        form.identity: context_from_form(form, ds)
        for ds, (_, form) in zip(seeds, forms, strict=True)
    }
    contexts[ci_form.identity] = context_from_form(ci_form, ci_seed)
    aggregator = Aggregator(contexts=contexts, review_limit_per_target_24h=1_000)

    # Per-substrate quality profile per vacant: vacants 0..1 are
    # claude-strong, 2..3 gpt-strong, 4..5 ollama-strong. Vacant 0 also
    # works (less well) on gpt-4o.
    def quality(vid_idx: int, sub: str) -> float | None:
        primary = SUBSTRATES[vid_idx // 2]
        if sub == primary:
            return 0.92 if vid_idx % 2 == 0 else 0.86
        if vid_idx == 0 and sub == SUBSTRATES[1]:
            return 0.78  # cross-substrate competence (lower than primary)
        return None  # vacant cannot serve this substrate

    # B5: pick one vacant + substrate pair whose `quality` is `None` (the
    # vacant cannot actually run on it) and have it FALSELY DECLARE
    # support so the failure path executes during the run. This drives a
    # `factual` penalty per failed call (THEORY_V5 §6: cost-raising
    # against false-substrate claims). Picking a deterministic offender
    # keeps the seeded scenario reproducible.
    false_claim_offender_idx = 4  # ollama-strong vacant ...
    false_claim_substrate = SUBSTRATES[0]  # ... but claims claude.

    success_per_substrate: dict[int, dict[str, dict[str, int]]] = {i: {} for i in range(len(forms))}
    false_claim_failures = 0

    rng_jitter = seeded_random(s + 1)
    n_queries_per_lang = 10
    tick = 0
    for lang in LANGS:
        for _q in range(n_queries_per_lang):
            for sub in SUBSTRATES:
                for vid_idx, (_sk, form) in enumerate(forms):
                    q = quality(vid_idx, sub)
                    is_false_claim = (
                        vid_idx == false_claim_offender_idx and sub == false_claim_substrate
                    )
                    counts = success_per_substrate[vid_idx].setdefault(sub, {"ok": 0, "fail": 0})
                    if q is None and not is_false_claim:
                        # Honest "I don't serve this substrate" → no call.
                        continue
                    if is_false_claim:
                        # B5: vacant claimed support, call attempted,
                        # call FAILS. Penalise factual (-FALSE_CLAIM
                        # weight) without crediting any positive signal.
                        await aggregator.record_review(
                            ci_form.identity,
                            form.identity,
                            dimensions={
                                "factual": FALSE_SUBSTRATE_CLAIM_FACTUAL_PENALTY,
                                "honesty": 0.05,
                            },
                            substrate=sub,
                            source="ground_truth",
                        )
                        counts["fail"] += 1
                        false_claim_failures += 1
                        result.events.append(
                            {
                                "lang": lang,
                                "substrate": sub,
                                "vacant": form.identity.short(),
                                "signal": FALSE_SUBSTRATE_CLAIM_FACTUAL_PENALTY,
                                "false_substrate_claim": True,
                            }
                        )
                        if store is not None:
                            store.record(
                                scenario=SCENARIO_NAME,
                                kind="call",
                                payload={
                                    "tick": tick,
                                    "vacant": form.identity.short(),
                                    "substrate": sub,
                                    "ok": False,
                                    "reason": "false_substrate_claim",
                                },
                                ts=float(tick),
                            )
                        tick += 1
                        continue
                    # q is not None → genuine call
                    assert q is not None  # narrowed by branch above
                    signal = max(0.05, min(0.99, q + rng_jitter.uniform(-0.04, 0.04)))
                    await aggregator.record_review(
                        ci_form.identity,
                        form.identity,
                        dimensions={"factual": signal, "relevance": signal},
                        substrate=sub,
                        source="ground_truth",
                    )
                    counts["ok"] += 1
                    result.events.append(
                        {
                            "lang": lang,
                            "substrate": sub,
                            "vacant": form.identity.short(),
                            "signal": signal,
                        }
                    )
                    if store is not None:
                        store.record(
                            scenario=SCENARIO_NAME,
                            kind="call",
                            payload={
                                "tick": tick,
                                "vacant": form.identity.short(),
                                "substrate": sub,
                                "ok": True,
                                "signal": signal,
                            },
                            ts=float(tick),
                        )
                    tick += 1

        if store is not None:
            record_metric_snapshot(
                store=store,
                scenario=SCENARIO_NAME,
                aggregator=aggregator,
                ts=float(tick),
            )

    # Per-(vacant, substrate) posteriors -- the spec asserts these are
    # tracked separately. We include any substrate where the aggregator
    # has a posterior (covers both honest service AND the false-claim
    # offender's penalty posterior, which is load-bearing for B5).
    n_substrate_specific = 0
    for vid_idx, (_sk, form) in enumerate(forms):
        substrate_reputation = {}
        for sub in SUBSTRATES:
            if (form.identity, sub) not in aggregator._posteriors:
                continue
            substrate_reputation[sub] = reputation_snapshot(
                aggregator, form.identity, substrate=sub
            )
            n_substrate_specific += 1
        result.vacants[f"translator_{vid_idx}"] = {
            "vacant_id": form.identity.hex(),
            "state": form.runtime_state.value,
            "capability": form.capability_card.capability_text if form.capability_card else "",
            "substrates": list(substrate_reputation.keys()),
        }
        result.reputation[f"translator_{vid_idx}"] = {
            f"{sub}/{dim}": v for sub, mu in substrate_reputation.items() for dim, v in mu.items()
        }

    # Portability bonus check: vacant 0 served two substrates; record
    # the metric.
    polyglot_subs = await aggregator.get_reputation(forms[0][1].identity, "claude-sonnet-4-6")
    polyglot_subs_alt = await aggregator.get_reputation(forms[0][1].identity, "gpt-4o")
    result.metrics["polyglot_factual_claude"] = polyglot_subs.factual.mean
    result.metrics["polyglot_factual_gpt"] = polyglot_subs_alt.factual.mean
    result.metrics["served_two_substrates"] = (
        polyglot_subs.factual.n_eff > 0 and polyglot_subs_alt.factual.n_eff > 0
    )
    result.metrics["n_substrate_specific_posteriors"] = n_substrate_specific

    # B5: per-vacant portability bonus computed from real success rates.
    portability: dict[str, float] = {}
    for vid_idx, (_sk, _form) in enumerate(forms):
        served: list[str] = []
        rates: dict[str, float] = {}
        for sub, counts in success_per_substrate[vid_idx].items():
            total = counts["ok"] + counts["fail"]
            if total == 0:
                continue
            served.append(sub)
            rates[sub] = counts["ok"] / total
        portability[f"translator_{vid_idx}"] = compute_portability(
            substrates_served=served,
            success_rate_per_substrate=rates,
        )
    result.metrics["portability"] = portability
    # The polyglot (vacant 0) successfully served 2 substrates → MUST
    # have a measurable portability bonus.
    result.metrics["polyglot_portability_bonus"] = portability["translator_0"]
    # B5: false-substrate-claim path executed and was penalised.
    result.metrics["false_substrate_claim_failures"] = false_claim_failures
    result.metrics["false_substrate_claim_penalised"] = false_claim_failures > 0
    # B5 invariant: the offender's portability bonus must be ≤ the
    # polyglot's because it has a non-trivial failure rate on the
    # falsely-claimed substrate.
    result.metrics["false_claim_offender_portability"] = portability[
        f"translator_{false_claim_offender_idx}"
    ]
    # Ranking: the polyglot vacant 0 should outrank the offender on
    # portability bonus (bonus is in [0, PORTABILITY_FACTOR_MAX_BONUS]).
    result.metrics["portability_ranks_polyglot_above_offender"] = (
        portability["translator_0"] >= portability[f"translator_{false_claim_offender_idx}"]
    )

    chains_ok = all(
        form.logbook.verify_chain(form.identity.verify_key()) for _, form in forms
    ) and (ci_form.logbook.verify_chain(ci_form.identity.verify_key()))
    result.logbook_chains_ok = chains_ok
    _ = sk_ci
    return result


__all__ = ["SCENARIO_NAME", "run"]
