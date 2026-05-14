"""Unit tests for `vacant.registry.ots_anchor` — OpenTimestamps pending
receipt + upgrade flow.

Covers:
- `compute_pending_proof` rejects malformed roots
- `serialize_proof_file` / `deserialize_proof_file` round-trip
- `is_upgraded_proof` distinguishes pending vs upgraded
- `upgrade_pending_proof` requires the OTS magic header
- store integration: `seal_epoch(ots_anchor=True)` writes the pending
  digest; `record_ots_upgrade` replaces it with the real-proof digest
  and stamps `ots_upgraded_at`.
"""

from __future__ import annotations

import pytest

from vacant.core.crypto import keygen
from vacant.core.types import CapabilityCard, SubstrateSpec, VacantId, VacantState
from vacant.registry import (
    OTS_PENDING_MAGIC,
    OTSAnchorError,
    RegistryStore,
    compute_pending_proof,
    deserialize_proof_file,
    is_upgraded_proof,
    ots_proof_digest,
    publish_halo,
    serialize_proof_file,
    upgrade_pending_proof,
)
from vacant.registry.ots_anchor import OTS_UPGRADED_MAGIC


def _make_card(sk, vk):  # type: ignore[no-untyped-def]
    return CapabilityCard(
        vacant_id=VacantId.from_verify_key(vk),
        capability_text="x",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)


def test_compute_pending_proof_rejects_non_32_byte_root() -> None:
    with pytest.raises(OTSAnchorError):
        compute_pending_proof(root=b"too short")


def test_compute_pending_proof_requires_calendar_urls() -> None:
    with pytest.raises(OTSAnchorError):
        compute_pending_proof(root=b"\x00" * 32, calendar_urls=())


def test_pending_proof_round_trip() -> None:
    proof = compute_pending_proof(
        root=b"\xaa" * 32,
        calendar_urls=("https://example.com",),
        now_ms=1_700_000_000_000,
    )
    blob = serialize_proof_file(proof)
    assert blob.startswith(OTS_PENDING_MAGIC + b"\n")
    parsed = deserialize_proof_file(blob)
    assert parsed == proof


def test_deserialize_rejects_real_ots_proof() -> None:
    # A pretend-real .ots blob — should NOT parse as a pending receipt.
    real_blob = OTS_UPGRADED_MAGIC + b"\x00" * 32
    with pytest.raises(OTSAnchorError):
        deserialize_proof_file(real_blob)


def test_is_upgraded_proof_routing() -> None:
    proof = compute_pending_proof(root=b"\xaa" * 32)
    assert is_upgraded_proof(serialize_proof_file(proof)) is False
    assert is_upgraded_proof(OTS_UPGRADED_MAGIC + b"\x00" * 32) is True


def test_upgrade_pending_proof_requires_magic() -> None:
    pending = compute_pending_proof(root=b"\xaa" * 32)
    with pytest.raises(OTSAnchorError):
        upgrade_pending_proof(pending=pending, upgraded_bytes=b"not really ots")


def test_upgrade_pending_proof_records_digest() -> None:
    pending = compute_pending_proof(root=b"\xaa" * 32)
    real = OTS_UPGRADED_MAGIC + b"\xff" * 64
    digest, upgraded_at = upgrade_pending_proof(
        pending=pending,
        upgraded_bytes=real,
        now_ms=1_800_000_000_000,
    )
    assert digest == ots_proof_digest(real)
    assert upgraded_at == 1_800_000_000_000


@pytest.mark.asyncio
async def test_seal_epoch_with_ots_writes_pending_digest(
    registry_store: RegistryStore,
) -> None:
    sk, vk = keygen()
    card = _make_card(sk, vk)
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    epoch = await registry_store.seal_epoch(signing_key=sk, ots_anchor=True)
    assert epoch.ots_proof_hash is not None
    assert len(epoch.ots_proof_hash) == 32
    assert epoch.ots_upgraded_at is None  # still pending


@pytest.mark.asyncio
async def test_record_ots_upgrade_replaces_digest(
    registry_store: RegistryStore,
) -> None:
    sk, vk = keygen()
    card = _make_card(sk, vk)
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    epoch = await registry_store.seal_epoch(signing_key=sk, ots_anchor=True)
    pending_digest = epoch.ots_proof_hash
    fake_real = OTS_UPGRADED_MAGIC + b"\xfe" * 64
    digest, upgraded_at = await registry_store.record_ots_upgrade(
        int(epoch.epoch_id or 0), upgraded_bytes=fake_real
    )
    assert digest != pending_digest
    assert digest == ots_proof_digest(fake_real)
    refreshed = await registry_store.get_merkle_epoch(int(epoch.epoch_id or 0))
    assert refreshed is not None
    assert refreshed.ots_proof_hash == digest
    assert refreshed.ots_upgraded_at == upgraded_at


@pytest.mark.asyncio
async def test_record_ots_upgrade_rejects_bogus_payload(
    registry_store: RegistryStore,
) -> None:
    sk, vk = keygen()
    card = _make_card(sk, vk)
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    epoch = await registry_store.seal_epoch(signing_key=sk, ots_anchor=True)
    with pytest.raises(OTSAnchorError):
        await registry_store.record_ots_upgrade(
            int(epoch.epoch_id or 0), upgraded_bytes=b"definitely not an ots file"
        )
