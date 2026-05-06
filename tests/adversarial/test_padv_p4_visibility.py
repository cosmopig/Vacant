"""Padv P4 — visibility / LOCAL-leak attacks.

Spec anchors:
- `architecture/components/P4_registry.md` §3.2 (visibility filters)
- `dispatch/Padv_review.md` §"Visibility downgrade", §"LOCAL leak"
- `architecture/decisions/D007_padv_p4_findings.md` §2
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update

from vacant.core.crypto import keygen
from vacant.core.types import (
    CapabilityCard,
    SubstrateSpec,
    VacantId,
    VacantState,
)
from vacant.registry import (
    RegistryStore,
    Vacant,
    Visibility,
    VisibilityViolation,
    build_app,
    publish_halo,
    search_capability,
)


def _make_card_and_keys():  # type: ignore[no-untyped-def]
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text="x",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)
    return sk, vk, vid, card


@pytest_asyncio.fixture
async def rpc_client(
    registry_store: RegistryStore,
) -> AsyncIterator[tuple[AsyncClient, RegistryStore]]:
    app = build_app(registry_store)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, registry_store


# --- Attack 1: stranger lookup against LOCAL via direct API ------------------
# Defense (P): `RegistryStore.lookup_halo_for_caller` raises
# `VisibilityViolation` for non-owner callers when state forces NONE.


@pytest.mark.asyncio
async def test_attack_stranger_lookup_against_local_raises(
    registry_store: RegistryStore,
) -> None:
    sk, _vk, vid, card = _make_card_and_keys()
    await publish_halo(
        store=registry_store, card=card, runtime_state=VacantState.LOCAL, signing_key=sk
    )
    with pytest.raises(VisibilityViolation):
        await registry_store.lookup_halo_for_caller(vid.hex(), caller_pubkey_hex="ff" * 32)


# --- Attack 2: LOCAL leak via RPC (HTTP path) --------------------------------
# Defense (P): `/v1/capability_card/{vacant_id}` returns 403 for stranger
# callers when target is NONE-visibility (D007 §2 RPC layer check).


@pytest.mark.asyncio
async def test_attack_local_leak_via_rpc_blocked(
    rpc_client: tuple[AsyncClient, RegistryStore],
) -> None:
    ac, store = rpc_client
    sk, _vk, vid, card = _make_card_and_keys()
    await publish_halo(store=store, card=card, runtime_state=VacantState.LOCAL, signing_key=sk)
    # Anonymous (no `caller=` query) → 403.
    resp = await ac.get(f"/v1/capability_card/{vid.hex()}")
    assert resp.status_code == 403
    # Stranger caller → 403.
    resp = await ac.get(f"/v1/capability_card/{vid.hex()}?caller={'ff' * 32}")
    assert resp.status_code == 403


# --- Attack 3: search exclusion of LOCAL ------------------------------------
# Defense (P): `search_capability(include_local=False)` is the public
# default; `search_capability(include_local=True)` is the python-API
# affordance for owner/parent direct paths and is NOT exposed via RPC.


@pytest.mark.asyncio
async def test_attack_search_does_not_leak_local_by_default(
    registry_store: RegistryStore,
) -> None:
    sk, _vk, _vid, card = _make_card_and_keys()
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.LOCAL,
        signing_key=sk,
    )
    matches = await search_capability(store=registry_store, query="x", limit=10)
    assert matches == []


@pytest.mark.asyncio
async def test_attack_query_capability_rpc_does_not_expose_include_local(
    rpc_client: tuple[AsyncClient, RegistryStore],
) -> None:
    """Adversary tries to force the RPC layer to include LOCAL halos by
    smuggling `include_local=true` as a query param. The endpoint
    deliberately doesn't accept it (parameter-not-in-signature). Even if
    accepted by FastAPI's loose query handling, the search call doesn't
    forward it.
    """
    ac, store = rpc_client
    sk, _vk, vid, card = _make_card_and_keys()
    await publish_halo(store=store, card=card, runtime_state=VacantState.LOCAL, signing_key=sk)
    resp = await ac.post("/v1/query_capability?capability=x&include_local=true")
    assert resp.status_code == 200
    data = resp.json()
    # The vacant must NOT appear regardless of the smuggled parameter.
    matches = data["matches"]
    assert all(m["vacant_id"] != vid.hex() for m in matches)


# --- Attack 4: visibility downgrade silent --------------------------------
# Defense (D): `verify_vacant_index_consistent` recomputes visibility from
# the latest signed register event in the chain and compares to the index.
# Direct UPDATE of the visibility column → mismatch → False.


@pytest.mark.asyncio
async def test_attack_silent_visibility_downgrade_detected(
    registry_store: RegistryStore,
) -> None:
    sk, _vk, vid, card = _make_card_and_keys()
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    # Sanity: index agrees with log.
    assert await registry_store.verify_vacant_index_consistent(vid.hex()) is True

    # Attacker downgrades visibility directly via SQL — no signed event emitted.
    async with registry_store._sessionmaker() as s:
        await s.execute(
            update(Vacant)
            .where(Vacant.vacant_id == vid.hex())
            .values(visibility=Visibility.NONE.value)
        )
        await s.commit()

    # The index now lies about visibility. The verifier catches it.
    assert await registry_store.verify_vacant_index_consistent(vid.hex()) is False


@pytest.mark.asyncio
async def test_attack_silent_visibility_upgrade_detected(
    registry_store: RegistryStore,
) -> None:
    sk, _vk, vid, card = _make_card_and_keys()
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.LOCAL,
        signing_key=sk,
    )
    assert await registry_store.verify_vacant_index_consistent(vid.hex()) is True

    # Direct upgrade: NONE → PUBLIC without an event.
    async with registry_store._sessionmaker() as s:
        await s.execute(
            update(Vacant)
            .where(Vacant.vacant_id == vid.hex())
            .values(visibility=Visibility.PUBLIC.value)
        )
        await s.commit()

    assert await registry_store.verify_vacant_index_consistent(vid.hex()) is False


# --- Attack 5: re-publish records visibility transition ----------------------
# Defense (P): every `publish_halo` call emits a signed `register` event,
# so legitimate visibility changes are auditable.


@pytest.mark.asyncio
async def test_attack_visibility_transition_via_publish_is_logged(
    registry_store: RegistryStore,
) -> None:
    sk, _vk, vid, card = _make_card_and_keys()
    await publish_halo(
        store=registry_store, card=card, runtime_state=VacantState.ACTIVE, signing_key=sk
    )
    # Re-publish as LOCAL.
    await publish_halo(
        store=registry_store, card=card, runtime_state=VacantState.LOCAL, signing_key=sk
    )
    # Both register events are in the log; index agrees with the latest.
    events = await registry_store.list_events_for_vacant(vid.hex(), limit=10)
    register_events = [e for e in events if e.event_type == "register"]
    assert len(register_events) == 2
    assert await registry_store.verify_vacant_index_consistent(vid.hex()) is True
