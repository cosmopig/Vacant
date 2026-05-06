"""Scenario 1 -- law_firm: composite parent + 2 closed sub-vacants
(P7_demo_seed §"Scenario 1 -- law_firm").

Composite "法律問答 vacant" delegates each query to:
- "專利查詢" (factual lookup) -- high F signals.
- "條款草擬" (logical drafting) -- high L signals.

After 30 simulated calls the composite parent earns from successful
delegation; both sub-vacants stay LOCAL (no graduation triggered in
this scenario).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vacant.composite import (
    ChildHandler,
    ChildManifest,
    ChildRecord,
    CompositeRuntime,
)
from vacant.core.crypto import keygen
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
from vacant.reputation import Aggregator, VacantContext

if TYPE_CHECKING:
    from vacant.substrate.base import SubstrateBackend


SCENARIO_NAME = "law_firm"
N_CALLS = 30


def _build_handler(substrate: SubstrateBackend, capability: str) -> ChildHandler:
    async def handler(subtask: object) -> dict[str, str]:
        from vacant.substrate.base import SubstrateRequest

        text = str(subtask) if not isinstance(subtask, dict) else subtask.get("text", "")
        rsp = await substrate.infer(
            SubstrateRequest(
                system_prompt=f"You are a {capability} sub-vacant.",
                user_prompt=text,
            )
        )
        return {"capability": capability, "answer": rsp.text}

    return handler


async def run(*, substrate: SubstrateBackend, seed: int | None = None) -> ScenarioResult:
    s = seed if seed is not None else DEFAULT_SEEDS[SCENARIO_NAME]
    rng = seeded_random(s)
    result = ScenarioResult(name=SCENARIO_NAME, seed=s)

    parent_seed = VacantSeed(
        name="法律問答",
        capability_text="legal-qa",
        state=VacantState.ACTIVE,
        tool_whitelist=("text", "search"),
    )
    sub_factual_seed = VacantSeed(
        name="專利查詢",
        capability_text="patent-search",
        state=VacantState.LOCAL,
        tool_whitelist=("text", "search"),
    )
    sub_logical_seed = VacantSeed(
        name="條款草擬",
        capability_text="clause-drafting",
        state=VacantState.LOCAL,
        tool_whitelist=("text",),
    )
    client_seeds = tuple(
        VacantSeed(
            name=f"客戶-{i}",
            capability_text="legal-client",
            base_model_family="gemini",
            state=VacantState.ACTIVE,
        )
        for i in range(5)
    )

    sk_p, parent_form = build_vacant(parent_seed, rng)
    sk_f, factual_form = build_vacant(sub_factual_seed, rng)
    sk_l, logical_form = build_vacant(sub_logical_seed, rng)
    clients = [build_vacant(cs, rng) for cs in client_seeds]

    contexts = {
        parent_form.identity: context_from_form(parent_form, parent_seed),
        factual_form.identity: context_from_form(factual_form, sub_factual_seed),
        logical_form.identity: context_from_form(logical_form, sub_logical_seed),
    }
    for cs, (_sk, cform) in zip(client_seeds, clients, strict=True):
        contexts[cform.identity] = context_from_form(cform, cs)
    aggregator = Aggregator(contexts=contexts)
    runtime = CompositeRuntime(parent_form=parent_form, parent_signing_key=sk_p)
    for child_seed_, sk_child, child_form in (
        (sub_factual_seed, sk_f, factual_form),
        (sub_logical_seed, sk_l, logical_form),
    ):
        manifest = (
            ChildManifest(
                parent_id=parent_form.identity,
                child_id=child_form.identity,
                birth_path="D2",
                closed_by_default=True,
                tool_whitelist_inherited=list(child_seed_.tool_whitelist),
            )
            .signed_by_parent(sk_p)
            .signed_by_child(sk_child)
        )
        runtime.register_child(
            ChildRecord(
                manifest=manifest,
                child_form=child_form,
                child_signing_key=sk_child,
                handler=_build_handler(substrate, child_seed_.capability_text),
            )
        )

    queries = [
        ("專利", "查詢 USPTO 編號 US123 的專利狀態"),
        ("條款", "草擬一段保密條款"),
    ]

    for i in range(N_CALLS):
        kind, q = queries[i % 2]
        target_form = factual_form if kind == "專利" else logical_form
        target_seed = sub_factual_seed if kind == "專利" else sub_logical_seed
        await runtime.delegate(child_id=target_form.identity, subtask={"text": q})
        result.events.append(
            {
                "tick": i,
                "type": "delegate",
                "child": target_seed.name,
                "query": q,
            }
        )
        # Rotate caller across the 5 clients so novelty discount doesn't
        # crush the signal. ground_truth source (weight 1.0) is the
        # cleanest signal for a deterministic demo.
        _client_sk, caller_form = clients[i % len(clients)]
        await aggregator.record_review(
            caller_form.identity,
            parent_form.identity,
            dimensions={
                "factual": 0.95 if kind == "專利" else 0.85,
                "relevance": 0.9,
            },
            substrate="default",
            source="ground_truth",
        )
        await aggregator.record_review(
            caller_form.identity,
            target_form.identity,
            dimensions={
                ("factual" if kind == "專利" else "logical"): (0.95 if kind == "專利" else 0.9),
            },
            substrate="default",
            source="ground_truth",
        )

    # Aggregate-step: parent emits a summary log entry per spec.
    runtime.aggregate(
        [],
        combiner=lambda _: {"summary": f"{N_CALLS} legal queries handled"},
    )

    # Snapshot.
    for label, form in (
        ("parent", parent_form),
        ("factual_sub", factual_form),
        ("logical_sub", logical_form),
    ):
        result.vacants[label] = {
            "vacant_id": form.identity.hex(),
            "state": form.runtime_state.value,
            "capability": form.capability_card.capability_text if form.capability_card else "",
        }
        result.reputation[label] = reputation_snapshot(aggregator, form.identity)
    for i, (_sk, cform) in enumerate(clients):
        label = f"client_{i}"
        result.vacants[label] = {
            "vacant_id": cform.identity.hex(),
            "state": cform.runtime_state.value,
            "capability": cform.capability_card.capability_text if cform.capability_card else "",
        }

    # Logbook chain check on every vacant.
    chains_ok = (
        parent_form.logbook.verify_chain(parent_form.identity.verify_key())
        and factual_form.logbook.verify_chain(factual_form.identity.verify_key())
        and logical_form.logbook.verify_chain(logical_form.identity.verify_key())
        and all(cf.logbook.verify_chain(cf.identity.verify_key()) for _, cf in clients)
    )
    result.logbook_chains_ok = chains_ok

    # Closed children stayed LOCAL.
    result.metrics["closed_children_remained_local"] = (
        runtime.manifest_for(factual_form.identity).closed_by_default
        and runtime.manifest_for(logical_form.identity).closed_by_default
    )
    result.metrics["n_calls"] = N_CALLS
    result.metrics["parent_logbook_entries"] = len(parent_form.logbook.entries)

    _ = keygen  # silence unused-import warnings
    return result


__all__ = ["SCENARIO_NAME", "run"]


# Module-level reference so type-checkers see VacantContext as used.
_ = VacantContext
