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


# --- Pfix3 B5: republish overwrites the whole card row ---------------------


def _make_card_v2(sk, vk, *, capability_text: str = "y"):  # type: ignore[no-untyped-def]
    """Bumped halo_version + different capability_text → fresh signed card."""
    return CapabilityCard(
        vacant_id=VacantId.from_verify_key(vk),
        capability_text=capability_text,
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
        halo_version=2,
    ).signed(sk)


@pytest.mark.asyncio
async def test_publish_halo_republish_overwrites_card_columns(
    registry_store: RegistryStore,
) -> None:
    """Pre-Pfix3 the existing-vacant branch only flipped visibility; the
    capability_card_hash/sig/blob, base_model, version columns went stale
    while the audit chain advanced with a new card_hash. After B5 the row
    must track the new card."""
    sk, vk = keygen()
    card_v1 = _make_card(sk, vk)
    await publish_halo(
        store=registry_store,
        card=card_v1,
        runtime_state=VacantState.ACTIVE,
        base_model="claude-3",
        version="0.1.0",
        signing_key=sk,
    )
    v_after_first = await registry_store.get_vacant(card_v1.vacant_id.hex())
    assert v_after_first is not None
    hash_v1 = v_after_first.capability_card_hash

    card_v2 = _make_card_v2(sk, vk, capability_text="upgraded")
    await publish_halo(
        store=registry_store,
        card=card_v2,
        runtime_state=VacantState.ACTIVE,
        base_model="claude-4",
        version="0.2.0",
        signing_key=sk,
    )
    v_after_repub = await registry_store.get_vacant(card_v1.vacant_id.hex())
    assert v_after_repub is not None
    assert v_after_repub.capability_card_hash != hash_v1, (
        "republish should rewrite capability_card_hash"
    )
    assert v_after_repub.base_model == "claude-4"
    assert v_after_repub.version == "0.2.0"
    # capability_card_blob carries the new card; the new capability_text
    # should be inside it.
    assert b"upgraded" in v_after_repub.capability_card_blob


@pytest.mark.asyncio
async def test_publish_halo_republish_rejects_parent_id_change(
    registry_store: RegistryStore,
) -> None:
    sk, vk = keygen()
    card = _make_card(sk, vk)
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )  # parent_id default is None
    card_v2 = _make_card_v2(sk, vk)
    with pytest.raises(RegistryWriteError, match="parent_id is immutable"):
        await publish_halo(
            store=registry_store,
            card=card_v2,
            runtime_state=VacantState.ACTIVE,
            parent_id="aa" * 32,  # was None, now claims a parent
            signing_key=sk,
        )


@pytest.mark.asyncio
async def test_publish_halo_republish_rejects_halo_version_downgrade(
    registry_store: RegistryStore,
) -> None:
    sk, vk = keygen()
    card_v2 = _make_card_v2(sk, vk)
    await publish_halo(
        store=registry_store,
        card=card_v2,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    card_v1 = _make_card(sk, vk)  # halo_version defaults to 1
    with pytest.raises(RegistryWriteError, match="halo_version must be monotonic"):
        await publish_halo(
            store=registry_store,
            card=card_v1,
            runtime_state=VacantState.ACTIVE,
            signing_key=sk,
        )
