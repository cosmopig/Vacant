"""halo.publish_halo / revoke_halo tests beyond the visibility suite."""

from __future__ import annotations

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
    RegistryWriteError,
    Visibility,
    publish_halo,
    revoke_halo,
)


def _make_card(sk, vk):  # type: ignore[no-untyped-def]
    return CapabilityCard(
        vacant_id=VacantId.from_verify_key(vk),
        capability_text="x",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)


@pytest.mark.asyncio
async def test_revoke_halo_round_trip(registry_store: RegistryStore) -> None:
    sk, vk = keygen()
    card = _make_card(sk, vk)
    rec = await publish_halo(
        store=registry_store, card=card, runtime_state=VacantState.ACTIVE, signing_key=sk
    )
    rev = await revoke_halo(
        store=registry_store,
        vacant_id=rec.vacant_id,
        reason="key compromised",
        signing_key=sk,
        pubkey_bytes=bytes(vk),
    )
    assert rev.reason == "key compromised"
    v = await registry_store.get_vacant(rec.vacant_id)
    assert v is not None and v.status == "revoked"


@pytest.mark.asyncio
async def test_revoke_halo_rejects_empty_reason(registry_store: RegistryStore) -> None:
    sk, vk = keygen()
    card = _make_card(sk, vk)
    rec = await publish_halo(
        store=registry_store, card=card, runtime_state=VacantState.ACTIVE, signing_key=sk
    )
    with pytest.raises(RegistryWriteError):
        await revoke_halo(
            store=registry_store,
            vacant_id=rec.vacant_id,
            reason="   ",
            signing_key=sk,
            pubkey_bytes=bytes(vk),
        )


@pytest.mark.asyncio
async def test_revoke_unknown_vacant_raises(registry_store: RegistryStore) -> None:
    sk, vk = keygen()
    with pytest.raises(RegistryWriteError):
        await revoke_halo(
            store=registry_store,
            vacant_id="aa" * 32,
            reason="x",
            signing_key=sk,
            pubkey_bytes=bytes(vk),
        )


@pytest.mark.asyncio
async def test_publish_halo_repeat_updates_visibility(
    registry_store: RegistryStore,
) -> None:
    sk, vk = keygen()
    card = _make_card(sk, vk)
    rec1 = await publish_halo(
        store=registry_store, card=card, runtime_state=VacantState.ACTIVE, signing_key=sk
    )
    rec2 = await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.LOCAL,  # forces NONE
        signing_key=sk,
    )
    assert rec1.vacant_id == rec2.vacant_id
    assert rec2.visibility == Visibility.NONE
