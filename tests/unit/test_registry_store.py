"""Registry store CRUD + signature-verified writes."""

from __future__ import annotations

import pytest

from vacant.core.crypto import hash_blake2b, keygen, sign
from vacant.core.types import (
    CapabilityCard,
    SubstrateSpec,
    VacantId,
    VacantState,
)
from vacant.registry import (
    IdempotencyConflict,
    NotFoundError,
    RegistryStore,
    SequenceMonotonicityError,
    SignatureRejected,
    SignedEventDraft,
    Vacant,
    Visibility,
    canonical_event_bytes,
    canonical_json,
    now_ms,
    publish_halo,
)


def _make_card_and_keys():  # type: ignore[no-untyped-def]
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text="thing",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)
    return sk, vk, vid, card


def _make_signed_event_draft(*, sk, vid, actor_seq: int, payload, ts: int | None = None):  # type: ignore[no-untyped-def]
    pl = canonical_json(payload).encode("utf-8")
    payload_hash = hash_blake2b(pl)
    ts = ts if ts is not None else now_ms()
    idem = f"test-event-{actor_seq}-{ts}"
    canonical = canonical_event_bytes(
        event_type="register",
        actor_vacant_id=vid.hex(),
        subject_vacant_id=None,
        payload_hash=payload_hash,
        idempotency_key=idem,
        signed_by_pubkey=vid.pubkey_bytes,
        ts=ts,
        actor_seq=actor_seq,
    )
    return SignedEventDraft(
        event_type="register",
        actor_vacant_id=vid.hex(),
        subject_vacant_id=None,
        payload=payload,
        idempotency_key=idem,
        signed_by_pubkey=vid.pubkey_bytes,
        signature=sign(sk, canonical),
        actor_seq=actor_seq,
        ts=ts,
    )


@pytest.mark.asyncio
async def test_publish_halo_inserts_vacant_and_register_event(
    registry_store: RegistryStore,
) -> None:
    sk, _vk, vid, card = _make_card_and_keys()
    rec = await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    assert rec.vacant_id == vid.hex()
    assert rec.event_seq >= 1

    v = await registry_store.get_vacant(rec.vacant_id)
    assert v is not None
    assert v.public_key == vid.pubkey_bytes
    assert v.visibility == Visibility.PUBLIC.value


@pytest.mark.asyncio
async def test_publish_halo_with_unsigned_card_rejected(
    registry_store: RegistryStore,
) -> None:
    sk, _vk, vid, _card = _make_card_and_keys()
    unsigned = CapabilityCard(
        vacant_id=vid,
        capability_text="x",
        substrate_spec=SubstrateSpec(),
    )
    from vacant.registry.errors import RegistryWriteError

    with pytest.raises(RegistryWriteError):
        await publish_halo(
            store=registry_store,
            card=unsigned,
            runtime_state=VacantState.ACTIVE,
            signing_key=sk,
        )


@pytest.mark.asyncio
async def test_submit_event_rejects_bad_signature(
    registry_store: RegistryStore,
) -> None:
    sk, _vk, vid, card = _make_card_and_keys()
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    # Build a draft with a tampered signature.
    draft = _make_signed_event_draft(sk=sk, vid=vid, actor_seq=2, payload={"k": "v"})
    bad = SignedEventDraft(
        event_type=draft.event_type,
        actor_vacant_id=draft.actor_vacant_id,
        subject_vacant_id=draft.subject_vacant_id,
        payload=draft.payload,
        idempotency_key=draft.idempotency_key + "tamper",
        signed_by_pubkey=draft.signed_by_pubkey,
        signature=draft.signature,  # signed for the OLD idempotency_key
        actor_seq=draft.actor_seq,
        ts=draft.ts,
    )
    with pytest.raises(SignatureRejected):
        await registry_store.submit_event(bad)


@pytest.mark.asyncio
async def test_submit_event_rejects_non_monotonic_seq(
    registry_store: RegistryStore,
) -> None:
    sk, _vk, vid, card = _make_card_and_keys()
    rec = await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    # Last actor_seq is 1 (set by publish_halo's register event); skipping to 5 should fail.
    skip_draft = _make_signed_event_draft(sk=sk, vid=vid, actor_seq=5, payload={"x": 1})
    with pytest.raises(SequenceMonotonicityError):
        await registry_store.submit_event(skip_draft)
    # And replaying the same seq is also rejected (must be strictly +1).
    replay_draft = _make_signed_event_draft(sk=sk, vid=vid, actor_seq=1, payload={"x": 2})
    with pytest.raises(SequenceMonotonicityError):
        await registry_store.submit_event(replay_draft)
    _ = rec


@pytest.mark.asyncio
async def test_idempotency_returns_existing(registry_store: RegistryStore) -> None:
    sk, _vk, vid, card = _make_card_and_keys()
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    draft = _make_signed_event_draft(sk=sk, vid=vid, actor_seq=2, payload={"y": 1})
    e1 = await registry_store.submit_event(draft)
    e2 = await registry_store.submit_event(draft)
    assert e1.seq == e2.seq


@pytest.mark.asyncio
async def test_idempotency_with_different_payload_conflict(
    registry_store: RegistryStore,
) -> None:
    sk, _vk, vid, card = _make_card_and_keys()
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    d1 = _make_signed_event_draft(sk=sk, vid=vid, actor_seq=2, payload={"y": 1})
    await registry_store.submit_event(d1)
    # Different payload + same idempotency_key, signed correctly.
    pl2 = canonical_json({"y": 2}).encode("utf-8")
    payload_hash2 = hash_blake2b(pl2)
    canonical2 = canonical_event_bytes(
        event_type="register",
        actor_vacant_id=vid.hex(),
        subject_vacant_id=None,
        payload_hash=payload_hash2,
        idempotency_key=d1.idempotency_key,  # reuse the key
        signed_by_pubkey=vid.pubkey_bytes,
        ts=d1.ts,
        actor_seq=3,
    )
    d2 = SignedEventDraft(
        event_type="register",
        actor_vacant_id=vid.hex(),
        subject_vacant_id=None,
        payload={"y": 2},
        idempotency_key=d1.idempotency_key,
        signed_by_pubkey=vid.pubkey_bytes,
        signature=sign(sk, canonical2),
        actor_seq=3,
        ts=d1.ts,
    )
    with pytest.raises(IdempotencyConflict):
        await registry_store.submit_event(d2)


@pytest.mark.asyncio
async def test_event_chain_links_via_prev_event_hash(
    registry_store: RegistryStore,
) -> None:
    sk, _vk, vid, card = _make_card_and_keys()
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    last_overall = await registry_store.latest_event_overall()
    assert last_overall is not None
    d2 = _make_signed_event_draft(sk=sk, vid=vid, actor_seq=2, payload={"k": 1})
    e2 = await registry_store.submit_event(d2)
    assert e2.prev_event_hash == last_overall.event_hash


@pytest.mark.asyncio
async def test_update_vacant_status_round_trip(registry_store: RegistryStore) -> None:
    sk, _vk, _vid, card = _make_card_and_keys()
    rec = await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    await registry_store.update_vacant_status(rec.vacant_id, "frozen")
    v = await registry_store.get_vacant(rec.vacant_id)
    assert v is not None
    assert v.status == "frozen"


@pytest.mark.asyncio
async def test_update_unknown_vacant_status_raises(
    registry_store: RegistryStore,
) -> None:
    with pytest.raises(NotFoundError):
        await registry_store.update_vacant_status("ghost", "frozen")


@pytest.mark.asyncio
async def test_models_metadata_has_13_tables() -> None:
    """Acceptance: 13 tables present."""
    from sqlmodel import SQLModel

    table_names = {t.name for t in SQLModel.metadata.sorted_tables}
    expected = {
        "vacant",
        "attestation",
        "event",
        "event_finalization",
        "merkle_epoch",
        "epoch_witness",
        "reputation_snapshot",
        "composition_link",
        "sink_record",
        "freeze",
        "revocation",
        "read_audit",
        "anomaly_window",
    }
    assert expected.issubset(table_names)
    assert len(expected) == 13


@pytest.mark.asyncio
async def test_vacant_row_round_trip(registry_store: RegistryStore) -> None:
    sk, _vk, vid, _card = _make_card_and_keys()
    row = Vacant(
        vacant_id=vid.hex(),
        public_key=vid.pubkey_bytes,
        base_model="mock",
        base_model_family="mock",
        version="0.0.1",
        declared_capabilities_json='["x"]',
        capability_card_hash=b"\x00" * 32,
        capability_card_sig=b"\x00" * 64,
        registered_at=now_ms(),
    )
    await registry_store.insert_vacant(row)
    v = await registry_store.get_vacant(vid.hex())
    assert v is not None and v.vacant_id == vid.hex()
    _ = sk
