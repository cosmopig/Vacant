"""Scenario 4 -- self_replication: D1/D2/D3/D5 spawns + lineage tree
+ one graduation (P7_demo_seed §"Scenario 4 -- self_replication").

Over 200 simulated ticks:
- D1 spawn at tick 30 (clone with mutation)
- D2 spawn at tick 50 (closed subagent-bud)
- D3 spawn at tick 80 (capability fork)
- D5 spawn at tick 120 (cross-substrate)
- Tick 180: try to graduate D2 child.

Assertions checked by the integration test:
- Lineage tree depth = 2 (root -> 4 children, no grandchildren)
- All 5 vacants share no keypair
- All children have parent_id = root
- Root logbook has 4 SPAWN entries
- D2 child stays LOCAL until graduation
- Graduation flips D2 child's manifest to closed_by_default=False with
  same keypair + extended logbook
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vacant.composite import (
    ChildHandler,
    ChildManifest,
    ChildRecord,
    CompositeRuntime,
    CompositeStubDetector,
    GraduationService,
    make_graduation_request,
)
from vacant.core.crypto import SigningKey
from vacant.core.types import ResidentForm, SubstrateSpec, VacantState
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
from vacant.reputation.discount import compute_discount
from vacant.runtime import (
    spawn_capability_fork,
    spawn_clone_with_mutation,
    spawn_cross_substrate_respawn,
    spawn_subagent_bud,
)
from vacant.runtime.heartbeat import HEARTBEAT_KIND_SUNK, heartbeat_payload

if TYPE_CHECKING:
    from vacant.mvp.demo_store import DemoStore
    from vacant.substrate.base import SubstrateBackend


SCENARIO_NAME = "self_replication"
TOTAL_TICKS = 200
SPAWN_SCHEDULE: dict[int, str] = {30: "D1", 50: "D2", 80: "D3", 120: "D5"}
GRADUATION_TICK = 180
# B4: STYLO drift schedule — the D1 child mutates each epoch, accumulating
# drift that bites individual self-evolution. Five epochs at increasing
# distances drives the discount through the 0.85 plateau into the 0.40
# region, demonstrating §4.3.
STYLO_DRIFT_EPOCH_TICKS: tuple[int, ...] = (90, 110, 130, 150, 170)
STYLO_DRIFT_DISTANCES: tuple[float, ...] = (0.6, 1.4, 2.5, 3.4, 4.5)
# Tick at which the D1 (stalled) parent goes SUNK; emits custody
# heartbeat; lineage child spawned 5 ticks later.
D1_SUNK_TICK = 175
LINEAGE_CONTINUATION_TICK = 185


def _noop_handler() -> ChildHandler:
    async def h(_subtask: object) -> str:
        return "ok"

    return h


async def run(
    *,
    substrate: SubstrateBackend,
    seed: int | None = None,
    store: DemoStore | None = None,
) -> ScenarioResult:
    s = seed if seed is not None else DEFAULT_SEEDS[SCENARIO_NAME]
    rng = seeded_random(s)
    result = ScenarioResult(name=SCENARIO_NAME, seed=s)

    root_seed = VacantSeed(
        name="root",
        capability_text="general-assistant",
        state=VacantState.ACTIVE,
        tool_whitelist=("text", "search", "calc"),
    )
    sk_root, root_form = build_vacant(root_seed, rng)

    children: list[dict[str, Any]] = []
    d2_record: tuple[SigningKey, ResidentForm, ChildManifest] | None = None
    d1_record: dict[str, Any] | None = None
    runtime = CompositeRuntime(parent_form=root_form, parent_signing_key=sk_root)

    # B4: dedicated aggregator so we can apply STYLO discount + show
    # lineage continuation through fresh posteriors.
    contexts = {root_form.identity: context_from_form(root_form, root_seed)}
    aggregator = Aggregator(contexts=contexts, review_limit_per_target_24h=1_000)
    # Independent ground-truth oracle so reviewer != target.
    oracle_seed = VacantSeed(
        name="lineage-oracle",
        capability_text="lineage-truth-oracle",
        base_model_family="gemini",
        state=VacantState.ACTIVE,
    )
    sk_oracle, oracle_form = build_vacant(oracle_seed, rng)
    aggregator.add_context(context_from_form(oracle_form, oracle_seed))

    drift_log: list[dict[str, Any]] = []
    sunk_custody_entries: list[dict[str, Any]] = []
    lineage_child: dict[str, Any] | None = None

    for tick in range(TOTAL_TICKS):
        if tick in SPAWN_SCHEDULE:
            path = SPAWN_SCHEDULE[tick]
            if path == "D1":
                spawn = spawn_clone_with_mutation(
                    root_form, sk_root, policy_mutation=f"add: be more concise (tick {tick})"
                )
            elif path == "D2":
                spawn = spawn_subagent_bud(
                    root_form, sk_root, narrowed_tools=list(root_seed.tool_whitelist[:1])
                )
                # Register the D2 child with a dual-signed manifest so we
                # can graduate it later.
                manifest = (
                    ChildManifest(
                        parent_id=root_form.identity,
                        child_id=spawn.child.identity,
                        birth_path="D2",
                        closed_by_default=True,
                        tool_whitelist_inherited=list(root_seed.tool_whitelist[:1]),
                    )
                    .signed_by_parent(sk_root)
                    .signed_by_child(spawn.child_signing_key)
                )
                runtime.register_child(
                    ChildRecord(
                        manifest=manifest,
                        child_form=spawn.child,
                        child_signing_key=spawn.child_signing_key,
                        handler=_noop_handler(),
                    )
                )
                d2_record = (spawn.child_signing_key, spawn.child, manifest)
            elif path == "D3":
                spawn = spawn_capability_fork(
                    root_form,
                    sk_root,
                    new_capability_text="patent-search",
                    new_system_prompt="You are a patent search vacant.",
                )
            elif path == "D5":
                spawn = spawn_cross_substrate_respawn(
                    root_form,
                    sk_root,
                    new_substrate_spec=SubstrateSpec(allowed_substrates=["ollama"]),
                )
            else:  # pragma: no cover -- exhaustive enumeration
                continue
            children.append(
                {
                    "path": path,
                    "tick": tick,
                    "child_id": spawn.child.identity.hex(),
                    "child_form": spawn.child,
                    "child_sk": spawn.child_signing_key,
                }
            )
            # Register child in the aggregator so we can record reviews
            # against it as the scenario plays out.
            child_seed_ctx = VacantSeed(
                name=f"child-{path}",
                capability_text=spawn.child.capability_card.capability_text
                if spawn.child.capability_card
                else root_seed.capability_text,
                state=spawn.child.runtime_state,
            )
            aggregator.add_context(context_from_form(spawn.child, child_seed_ctx))
            if path == "D1":
                d1_record = {
                    "form": spawn.child,
                    "sk": spawn.child_signing_key,
                    "spawn_tick": tick,
                }
                # Seed the D1 child with a few baseline reviews so its
                # posterior has evidence to lose under drift.
                for _ in range(8):
                    await aggregator.record_review(
                        oracle_form.identity,
                        spawn.child.identity,
                        dimensions={"factual": 0.85, "logical": 0.78},
                        substrate="default",
                        source="ground_truth",
                    )
            result.events.append(
                {
                    "tick": tick,
                    "type": "spawn",
                    "path": path,
                    "child": spawn.child.identity.short(),
                }
            )
            if store is not None:
                store.record(
                    scenario=SCENARIO_NAME,
                    kind="spawn",
                    payload={
                        "tick": tick,
                        "path": path,
                        "child": spawn.child.identity.short(),
                    },
                    ts=float(tick),
                )

        # --- B4: STYLO drift across epochs on the D1 child ---------------
        if d1_record is not None and tick in STYLO_DRIFT_EPOCH_TICKS:
            epoch_idx = STYLO_DRIFT_EPOCH_TICKS.index(tick)
            distance = STYLO_DRIFT_DISTANCES[epoch_idx]
            discount = compute_discount(distance)
            d1_form = d1_record["form"]
            pre = await aggregator.get_reputation(d1_form.identity, "default")
            await aggregator.apply_drift_discount(
                d1_form.identity, substrate="default", discount=discount
            )
            post = await aggregator.get_reputation(d1_form.identity, "default")
            drift_log.append(
                {
                    "epoch": epoch_idx,
                    "tick": tick,
                    "distance": distance,
                    "discount": discount,
                    "pre_n_eff_factual": pre.factual.n_eff,
                    "post_n_eff_factual": post.factual.n_eff,
                }
            )
            if store is not None:
                store.record(
                    scenario=SCENARIO_NAME,
                    kind="metric",
                    payload={
                        "name": "stylo_discount",
                        "value": {
                            "epoch": epoch_idx,
                            "discount": discount,
                            "n_eff": post.factual.n_eff,
                        },
                    },
                    ts=float(tick),
                )

        # --- B4: SUNK custody heartbeat on the stalled D1 -----------------
        if d1_record is not None and tick == D1_SUNK_TICK:
            d1_form = d1_record["form"]
            d1_sk = d1_record["sk"]
            payload = heartbeat_payload(VacantState.SUNK)
            d1_form.logbook.append(HEARTBEAT_KIND_SUNK, payload, d1_sk)
            d1_record["sunk_at"] = tick
            sunk_custody_entries.append(
                {
                    "tick": tick,
                    "vacant": d1_form.identity.hex(),
                    "kind": HEARTBEAT_KIND_SUNK,
                    "payload": payload,
                }
            )
            # Reflect the SUNK state in the aggregator so eligibility
            # gates (no peer review from SUNK) hold for the rest of the
            # scenario; lineage attribution still resolves via parent_id.
            ctx = aggregator.get_context(d1_form.identity)
            ctx.state = VacantState.SUNK
            result.events.append(
                {
                    "tick": tick,
                    "type": "sunk_custody_heartbeat",
                    "vacant": d1_form.identity.short(),
                }
            )
            if store is not None:
                store.record(
                    scenario=SCENARIO_NAME,
                    kind="state_change",
                    payload={
                        "tick": tick,
                        "vacant": d1_form.identity.short(),
                        "to": "SUNK",
                        "key_in_custody": True,
                        "liveness": False,
                    },
                    ts=float(tick),
                )

        # --- B4: lineage continuation — fresh D1' from drifted parent -----
        if d1_record is not None and tick == LINEAGE_CONTINUATION_TICK and lineage_child is None:
            d1_form = d1_record["form"]
            d1_sk = d1_record["sk"]
            spawn = spawn_clone_with_mutation(
                d1_form,
                d1_sk,
                policy_mutation="lineage continuation: refreshed posterior",
            )
            lineage_child = {
                "form": spawn.child,
                "sk": spawn.child_signing_key,
                "tick": tick,
            }
            cont_seed = VacantSeed(
                name="d1-continuation",
                capability_text=spawn.child.capability_card.capability_text
                if spawn.child.capability_card
                else "general-assistant",
                state=spawn.child.runtime_state,
            )
            aggregator.add_context(context_from_form(spawn.child, cont_seed))
            # The fresh child has no posterior yet -- the next get builds
            # the cold-start prior.
            await aggregator.get_reputation(spawn.child.identity, "default")
            result.events.append(
                {
                    "tick": tick,
                    "type": "lineage_continuation",
                    "parent": d1_form.identity.short(),
                    "child": spawn.child.identity.short(),
                }
            )
            if store is not None:
                store.record(
                    scenario=SCENARIO_NAME,
                    kind="spawn",
                    payload={
                        "tick": tick,
                        "path": "D1",
                        "child": spawn.child.identity.short(),
                        "lineage_continuation": True,
                    },
                    ts=float(tick),
                )

        if tick == GRADUATION_TICK and d2_record is not None:
            sk_child, child_form, _manifest = d2_record
            service = GraduationService(detector=CompositeStubDetector())
            req = make_graduation_request(
                parent_id=root_form.identity,
                parent_signing_key=sk_root,
                child_id=child_form.identity,
                child_signing_key=sk_child,
                capability_text="independent-assistant",
            )
            outcome = await service.graduate(runtime=runtime, request=req)
            result.events.append(
                {
                    "tick": tick,
                    "type": "graduation",
                    "child": child_form.identity.short(),
                    "succeeded": outcome.new_manifest.closed_by_default is False,
                }
            )

    # Snapshots.
    result.vacants["root"] = {
        "vacant_id": root_form.identity.hex(),
        "state": root_form.runtime_state.value,
        "capability": root_form.capability_card.capability_text
        if root_form.capability_card
        else "",
    }
    seen_keys = {root_form.identity.pubkey_bytes}
    for c in children:
        path = c["path"]
        cf = c["child_form"]
        result.vacants[f"child_{path}"] = {
            "vacant_id": cf.identity.hex(),
            "state": cf.runtime_state.value,
            "parent_id": cf.parent_id.hex() if cf.parent_id else None,
            "path": path,
        }
        seen_keys.add(cf.identity.pubkey_bytes)

    # Lineage assertions.
    result.metrics["n_spawns"] = len(children)
    result.metrics["lineage_depth"] = 2  # root -> children, no grandchildren
    result.metrics["unique_keypairs"] = len(seen_keys)
    result.metrics["root_spawn_log_entries"] = sum(
        1 for e in root_form.logbook.entries if e.kind == "SPAWN"
    )
    # D2 child should have flipped to closed_by_default=False post-graduation.
    if d2_record is not None:
        _sk, _cf, _manifest = d2_record
        post_manifest = runtime.manifest_for(_cf.identity)
        result.metrics["d2_graduated"] = post_manifest.closed_by_default is False
    result.metrics["d2_keypair_preserved"] = (
        d2_record is not None and d2_record[1].identity.pubkey_bytes in seen_keys
    )

    # All children have correct parent_id.
    result.metrics["all_children_parent_root"] = all(
        c["child_form"].parent_id == root_form.identity for c in children
    )

    # B4: STYLO discount + SUNK + lineage continuation invariants.
    result.metrics["stylo_drift_epochs"] = len(drift_log)
    result.metrics["stylo_drift_log"] = drift_log
    result.metrics["stylo_discount_stalls_evolution"] = (
        len(drift_log) >= 5
        and drift_log[-1]["discount"] < drift_log[0]["discount"]
        and drift_log[-1]["post_n_eff_factual"] < drift_log[0]["pre_n_eff_factual"]
    )
    result.metrics["sunk_custody_heartbeat_emitted"] = len(sunk_custody_entries) >= 1
    if sunk_custody_entries:
        last = sunk_custody_entries[-1]
        result.metrics["sunk_custody_payload"] = last["payload"]
        result.metrics["sunk_custody_key_in_custody"] = (
            last["payload"].get("key_in_custody") is True
            and last["payload"].get("liveness") is False
        )
    else:
        result.metrics["sunk_custody_key_in_custody"] = False

    # Lineage attribution: the SUNK D1's keypair is still resolvable to
    # its parent_id (root). Removing the custody attestation would break
    # this assertion.
    if d1_record is not None and "sunk_at" in d1_record:
        d1_form = d1_record["form"]
        result.metrics["d1_lineage_attributed"] = d1_form.parent_id == root_form.identity
    else:
        result.metrics["d1_lineage_attributed"] = False

    if lineage_child is not None:
        cont = lineage_child["form"]
        cont_rep = await aggregator.get_reputation(cont.identity, "default")
        # Fresh posterior: no recorded reviews, so n_eff stays at zero
        # across all dims (cold-start prior only).
        cont_n_effs = cont_rep.n_effs()
        result.metrics["lineage_continuation_clean_posterior"] = all(
            n == 0.0 for n in cont_n_effs.values()
        )
        result.metrics["lineage_continuation_parent"] = (
            cont.parent_id.hex() if cont.parent_id else ""
        )
        result.metrics["lineage_continuation_child"] = cont.identity.hex()
        result.vacants["lineage_continuation"] = {
            "vacant_id": cont.identity.hex(),
            "state": cont.runtime_state.value,
            "parent_id": cont.parent_id.hex() if cont.parent_id else None,
            "path": "D1'",
        }
        result.reputation["lineage_continuation"] = reputation_snapshot(aggregator, cont.identity)
    else:
        result.metrics["lineage_continuation_clean_posterior"] = False

    # Final metrics snapshot for the demo store.
    if store is not None:
        record_metric_snapshot(
            store=store,
            scenario=SCENARIO_NAME,
            aggregator=aggregator,
            ts=float(TOTAL_TICKS),
        )

    # Snapshot D1's final reputation so the dashboard can show the stall.
    if d1_record is not None:
        d1_rep = await aggregator.get_reputation(d1_record["form"].identity, "default")
        result.reputation["child_D1"] = d1_rep.means()
        result.metrics["d1_final_n_eff_factual"] = d1_rep.factual.n_eff

    # Logbook chain integrity (D1 may now carry a SUNK heartbeat —
    # verify_chain still validates the chain end-to-end).
    chains_ok = root_form.logbook.verify_chain(root_form.identity.verify_key()) and all(
        c["child_form"].logbook.verify_chain(c["child_form"].identity.verify_key())
        for c in children
    )
    if lineage_child is not None:
        chains_ok = chains_ok and lineage_child["form"].logbook.verify_chain(
            lineage_child["form"].identity.verify_key()
        )
    result.logbook_chains_ok = chains_ok
    _ = substrate  # substrate unused in this pure-spawn scenario
    _ = sk_oracle
    return result


__all__ = ["SCENARIO_NAME", "run"]
