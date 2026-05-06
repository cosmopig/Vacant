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
    reputation_snapshot,
    seeded_random,
)
from vacant.mvp.scenarios._seeds import DEFAULT_SEEDS
from vacant.reputation import Aggregator

if TYPE_CHECKING:
    from vacant.substrate.base import SubstrateBackend

SCENARIO_NAME = "multilingual_translation"

SUBSTRATES = ("claude-sonnet-4-6", "gpt-4o", "local-ollama-llama3")
LANGS = ("en->zh", "en->ja", "en->es", "en->fr")


async def run(*, substrate: SubstrateBackend, seed: int | None = None) -> ScenarioResult:
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
    aggregator = Aggregator(contexts=contexts)

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

    rng_jitter = seeded_random(s + 1)
    n_queries_per_lang = 10
    for lang in LANGS:
        for _q in range(n_queries_per_lang):
            for sub in SUBSTRATES:
                for vid_idx, (_sk, form) in enumerate(forms):
                    q = quality(vid_idx, sub)
                    if q is None:
                        continue
                    signal = max(0.05, min(0.99, q + rng_jitter.uniform(-0.04, 0.04)))
                    await aggregator.record_review(
                        ci_form.identity,
                        form.identity,
                        dimensions={"factual": signal, "relevance": signal},
                        substrate=sub,
                        source="ground_truth",
                    )
                    result.events.append(
                        {
                            "lang": lang,
                            "substrate": sub,
                            "vacant": form.identity.short(),
                            "signal": signal,
                        }
                    )
                    # A vacant claiming to serve a substrate it can't run
                    # on would be detected here -- but we model
                    # `quality is None` as "no call attempted", which
                    # mirrors how the dispatcher would skip incompatible
                    # vacants. The reputation system never sees a fake
                    # successful run.

    # Per-(vacant, substrate) posteriors -- the spec asserts these are
    # tracked separately.
    n_substrate_specific = 0
    for vid_idx, (_sk, form) in enumerate(forms):
        substrate_reputation = {}
        for sub in SUBSTRATES:
            if quality(vid_idx, sub) is None:
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

    chains_ok = all(
        form.logbook.verify_chain(form.identity.verify_key()) for _, form in forms
    ) and (ci_form.logbook.verify_chain(ci_form.identity.verify_key()))
    result.logbook_chains_ok = chains_ok
    _ = sk_ci
    return result


__all__ = ["SCENARIO_NAME", "run"]
