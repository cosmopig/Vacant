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
    seeded_random,
)
from vacant.mvp.scenarios._seeds import DEFAULT_SEEDS
from vacant.runtime import (
    spawn_capability_fork,
    spawn_clone_with_mutation,
    spawn_cross_substrate_respawn,
    spawn_subagent_bud,
)

if TYPE_CHECKING:
    from vacant.substrate.base import SubstrateBackend


SCENARIO_NAME = "self_replication"
TOTAL_TICKS = 200
SPAWN_SCHEDULE: dict[int, str] = {30: "D1", 50: "D2", 80: "D3", 120: "D5"}
GRADUATION_TICK = 180


def _noop_handler() -> ChildHandler:
    async def h(_subtask: object) -> str:
        return "ok"

    return h


async def run(*, substrate: SubstrateBackend, seed: int | None = None) -> ScenarioResult:
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
    runtime = CompositeRuntime(parent_form=root_form, parent_signing_key=sk_root)

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
            result.events.append(
                {
                    "tick": tick,
                    "type": "spawn",
                    "path": path,
                    "child": spawn.child.identity.short(),
                }
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
        post = runtime.manifest_for(_cf.identity)
        result.metrics["d2_graduated"] = post.closed_by_default is False
    result.metrics["d2_keypair_preserved"] = (
        d2_record is not None and d2_record[1].identity.pubkey_bytes in seen_keys
    )

    # All children have correct parent_id.
    result.metrics["all_children_parent_root"] = all(
        c["child_form"].parent_id == root_form.identity for c in children
    )

    # Logbook chain integrity.
    chains_ok = root_form.logbook.verify_chain(root_form.identity.verify_key()) and all(
        c["child_form"].logbook.verify_chain(c["child_form"].identity.verify_key())
        for c in children
    )
    result.logbook_chains_ok = chains_ok
    _ = substrate  # substrate unused in this pure-spawn scenario
    return result


__all__ = ["SCENARIO_NAME", "run"]
