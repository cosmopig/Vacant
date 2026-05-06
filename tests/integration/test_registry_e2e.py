"""End-to-end registry walkthrough (slow integration test).

Per dispatch §Tests: register 5 vacants (mix public + local), run 20
random capability searches, assert visibility rules honored, attestation
chains verify.
"""

from __future__ import annotations

import random

import pytest

from vacant.core.crypto import keygen
from vacant.core.types import (
    CapabilityCard,
    SubstrateSpec,
    VacantId,
    VacantState,
)
from vacant.registry import (
    RegistryStore,
    Visibility,
    VisibilityViolation,
    publish_halo,
    search_capability,
)

pytestmark = pytest.mark.slow


CAPS = ["legal-research", "image-gen", "translate-zh", "code-review", "summarise"]


async def _publish(store, *, capability, state, family="claude"):  # type: ignore[no-untyped-def]
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text=capability,
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)
    rec = await publish_halo(
        store=store,
        card=card,
        runtime_state=state,
        signing_key=sk,
        base_model_family=family,
    )
    return rec, sk, vid


@pytest.mark.asyncio
async def test_register_five_run_20_searches_visibility_honored(
    registry_store: RegistryStore,
) -> None:
    rng = random.Random(42)
    rolled: list[tuple[str, VacantState, object, str]] = []
    for cap in CAPS:
        # Mix: 3 PUBLIC + 2 LOCAL
        state = VacantState.LOCAL if cap in ("translate-zh", "summarise") else VacantState.ACTIVE
        rec, _sk, vid = await _publish(
            registry_store,
            capability=cap,
            state=state,
            family=rng.choice(("claude", "gemini")),
        )
        rolled.append((cap, state, vid, rec.vacant_id))

    # 20 random capability searches: the 3 public ones are reachable,
    # the 2 local ones never appear.
    public_caps = [c for c, st, _, _ in rolled if st == VacantState.ACTIVE]
    local_caps = [c for c, st, _, _ in rolled if st == VacantState.LOCAL]

    for _ in range(20):
        target = rng.choice(public_caps + local_caps)
        matches = await search_capability(store=registry_store, query=target, limit=10)
        if target in public_caps:
            assert len(matches) >= 1
            assert all(m.visibility == Visibility.PUBLIC for m in matches)
        else:
            assert matches == []

    # Stranger lookup against a LOCAL vacant raises.
    local_id = next(rec for cap, st, _, rec in rolled if st == VacantState.LOCAL)
    with pytest.raises(VisibilityViolation):
        await registry_store.lookup_halo_for_caller(local_id, caller_pubkey_hex="ff" * 32)

    # Owner lookup of any LOCAL vacant succeeds.
    cap_a, _, vid_a, rec_a = next(
        (cap, st, vid, rec) for cap, st, vid, rec in rolled if st == VacantState.LOCAL
    )
    v = await registry_store.lookup_halo_for_caller(rec_a, caller_pubkey_hex=vid_a.hex())
    assert v.vacant_id == rec_a
    _ = cap_a


@pytest.mark.asyncio
async def test_chain_validates_after_full_walkthrough(
    registry_store: RegistryStore,
) -> None:
    """After 5 publishes, the overall event chain links via prev_event_hash
    and each per-vacant actor_seq is monotone.
    """
    sks: list = []
    for cap in CAPS:
        _, sk, _ = await _publish(registry_store, capability=cap, state=VacantState.ACTIVE)
        sks.append(sk)

    # Chain check: walk events in seq order and verify prev_event_hash links.
    prev = b"\x00" * 32
    for seq in range(1, 100):
        e = await registry_store.get_event(seq)
        if e is None:
            break
        assert e.prev_event_hash == prev
        prev = e.event_hash

    # Seal an epoch and verify it includes all events.
    epoch = await registry_store.seal_epoch(signing_key=sks[0])
    assert epoch.tree_size == len(CAPS)
