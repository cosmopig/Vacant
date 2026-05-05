"""Visibility unit tests + LOCAL-vs-stranger lookup contract."""

from __future__ import annotations

import pytest
import pytest_asyncio

from vacant.core.crypto import keygen
from vacant.core.types import (
    CapabilityCard,
    SubstrateSpec,
    VacantId,
    VacantState,
)
from vacant.registry import (
    NotFoundError,
    RegistryStore,
    Visibility,
    VisibilityViolation,
    effective_visibility,
    publish_halo,
)


def test_visibility_enum_values() -> None:
    assert {v.value for v in Visibility} == {"NONE", "RESTRICTED", "PUBLIC"}


@pytest.mark.parametrize("declared", list(Visibility))
def test_local_state_forces_none(declared: Visibility) -> None:
    assert effective_visibility(VacantState.LOCAL, declared) == Visibility.NONE


@pytest.mark.parametrize(
    ("state", "declared", "expected"),
    [
        (VacantState.ACTIVE, Visibility.PUBLIC, Visibility.PUBLIC),
        (VacantState.ACTIVE, Visibility.RESTRICTED, Visibility.RESTRICTED),
        (VacantState.ACTIVE, Visibility.NONE, Visibility.NONE),
        (VacantState.HIBERNATING, Visibility.PUBLIC, Visibility.PUBLIC),
        (VacantState.SUNK, Visibility.PUBLIC, Visibility.PUBLIC),
        (VacantState.ARCHIVED, Visibility.PUBLIC, Visibility.PUBLIC),
    ],
)
def test_non_local_states_pass_through(
    state: VacantState, declared: Visibility, expected: Visibility
) -> None:
    assert effective_visibility(state, declared) == expected


# --- LOCAL discovery contract -----------------------------------------------


@pytest_asyncio.fixture
async def published_local_vacant(registry_store: RegistryStore):  # type: ignore[no-untyped-def]
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text="local-only",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)
    rec = await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.LOCAL,
        signing_key=sk,
        visibility=Visibility.PUBLIC,  # caller asks PUBLIC, state forces NONE
    )
    return rec, sk, vid


@pytest.mark.asyncio
async def test_local_vacant_records_none_visibility(
    registry_store: RegistryStore, published_local_vacant
) -> None:  # type: ignore[no-untyped-def]
    rec, _sk, _vid = published_local_vacant
    assert rec.visibility == Visibility.NONE


@pytest.mark.asyncio
async def test_stranger_lookup_against_local_raises(
    registry_store: RegistryStore, published_local_vacant
) -> None:  # type: ignore[no-untyped-def]
    rec, _sk, _vid = published_local_vacant
    with pytest.raises(VisibilityViolation):
        await registry_store.lookup_halo_for_caller(rec.vacant_id, caller_pubkey_hex="ff" * 32)


@pytest.mark.asyncio
async def test_anonymous_lookup_against_local_raises(
    registry_store: RegistryStore, published_local_vacant
) -> None:  # type: ignore[no-untyped-def]
    rec, _sk, _vid = published_local_vacant
    with pytest.raises(VisibilityViolation):
        await registry_store.lookup_halo_for_caller(rec.vacant_id, caller_pubkey_hex=None)


@pytest.mark.asyncio
async def test_owner_self_lookup_returns_card(
    registry_store: RegistryStore, published_local_vacant
) -> None:  # type: ignore[no-untyped-def]
    rec, _sk, vid = published_local_vacant
    v = await registry_store.lookup_halo_for_caller(rec.vacant_id, caller_pubkey_hex=vid.hex())
    assert v.vacant_id == rec.vacant_id


@pytest.mark.asyncio
async def test_lookup_unknown_vacant_raises_not_found(
    registry_store: RegistryStore,
) -> None:
    with pytest.raises(NotFoundError):
        await registry_store.lookup_halo_for_caller("00" * 32, caller_pubkey_hex=None)


@pytest.mark.asyncio
async def test_public_vacant_is_visible_to_anonymous(
    registry_store: RegistryStore,
) -> None:
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text="public-thing",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    v = await registry_store.lookup_halo_for_caller(vid.hex(), caller_pubkey_hex=None)
    assert v.visibility == Visibility.PUBLIC.value
