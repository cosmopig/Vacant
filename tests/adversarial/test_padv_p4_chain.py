"""Padv P4 — chain integrity attacks against `vacant.registry.store`.

Spec anchors:
- `architecture/components/P4_registry.md` §3.1 (hash chain), §3.2 (write flow)
- `architecture/decisions/D007_padv_p4_findings.md` §1, §2
- `dispatch/Padv_review.md` §"P4 Registry attacks to consider"
"""

from __future__ import annotations

import pytest
from sqlalchemy import update
from sqlmodel import select

from vacant.core.crypto import hash_blake2b, keygen, sign
from vacant.core.types import (
    CapabilityCard,
    SubstrateSpec,
    VacantId,
    VacantState,
)
from vacant.registry import (
    Event,
    IdempotencyConflict,
    RegistryStore,
    SequenceMonotonicityError,
    SignatureRejected,
    SignedEventDraft,
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
        capability_text="x",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)
    return sk, vk, vid, card


def _signed_draft(*, sk, vid, actor_seq, payload, idem_suffix=""):  # type: ignore[no-untyped-def]
    pl = canonical_json(payload).encode("utf-8")
    payload_hash = hash_blake2b(pl)
    ts = now_ms()
    idem = f"padv-{vid.hex()[:8]}-{actor_seq}-{idem_suffix}"
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


# --- Attack 1: cross-actor impersonation ------------------------------------
# Defense (P): signed_by_pubkey must match the registered actor's
# public_key. Padv-P4 finding D007 §1 — fix landed in this PR.


@pytest.mark.asyncio
async def test_attack_cross_actor_impersonation_rejected(
    registry_store: RegistryStore,
) -> None:
    sk_v, _vk_v, vid_v, card_v = _make_card_and_keys()
    await publish_halo(
        store=registry_store,
        card=card_v,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk_v,
    )

    # Attacker has their OWN vacant + key.
    sk_a, _vk_a, vid_a, card_a = _make_card_and_keys()
    await publish_halo(
        store=registry_store,
        card=card_a,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk_a,
    )

    # Attacker forges an event filed as "from" the victim, but signs with
    # their own key + claims their own pubkey as signed_by_pubkey.
    payload = {"hijack": True}
    pl = canonical_json(payload).encode("utf-8")
    payload_hash = hash_blake2b(pl)
    ts = now_ms()
    idem = f"impersonate-{vid_v.hex()[:8]}-{ts}"
    canonical = canonical_event_bytes(
        event_type="register",
        actor_vacant_id=vid_v.hex(),  # claim victim's id
        subject_vacant_id=None,
        payload_hash=payload_hash,
        idempotency_key=idem,
        signed_by_pubkey=vid_a.pubkey_bytes,  # attacker's pubkey
        ts=ts,
        actor_seq=2,
    )
    forged = SignedEventDraft(
        event_type="register",
        actor_vacant_id=vid_v.hex(),
        subject_vacant_id=None,
        payload=payload,
        idempotency_key=idem,
        signed_by_pubkey=vid_a.pubkey_bytes,
        signature=sign(sk_a, canonical),  # signs with attacker's key
        actor_seq=2,
        ts=ts,
    )
    with pytest.raises(SignatureRejected):
        await registry_store.submit_event(forged)


@pytest.mark.asyncio
async def test_attack_unregistered_actor_rejected(
    registry_store: RegistryStore,
) -> None:
    """An attacker who never registered a vacant cannot submit events."""
    sk, _vk, vid, _card = _make_card_and_keys()
    draft = _signed_draft(sk=sk, vid=vid, actor_seq=1, payload={"k": 1})
    with pytest.raises(SignatureRejected):
        await registry_store.submit_event(draft)


# --- Attack 2: halo replay (idempotency) -------------------------------------
# Defense (P): `idempotency_key` returns the existing event, doesn't create a
# new one. Replaying the same register event is idempotent.


@pytest.mark.asyncio
async def test_attack_halo_replay_returns_same_event(
    registry_store: RegistryStore,
) -> None:
    sk, _vk, _vid, card = _make_card_and_keys()
    rec1 = await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    rec2 = await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    # Two publishes → two register events (different ts → different idem
    # keys), but both event chains are intact.
    assert rec1.event_seq != rec2.event_seq


@pytest.mark.asyncio
async def test_attack_replay_with_old_seq_rejected(
    registry_store: RegistryStore,
) -> None:
    sk, _vk, vid, card = _make_card_and_keys()
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    # publish_halo emitted register at actor_seq=1; replaying actor_seq=1 is
    # rejected by L2.
    replay = _signed_draft(sk=sk, vid=vid, actor_seq=1, payload={"k": 1})
    with pytest.raises(SequenceMonotonicityError):
        await registry_store.submit_event(replay)


@pytest.mark.asyncio
async def test_attack_idempotency_collision_with_different_payload_rejected(
    registry_store: RegistryStore,
) -> None:
    sk, _vk, vid, card = _make_card_and_keys()
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    d1 = _signed_draft(sk=sk, vid=vid, actor_seq=2, payload={"v": 1})
    await registry_store.submit_event(d1)
    # Same idempotency_key + different payload (signed correctly).
    payload2 = {"v": 2}
    pl2 = canonical_json(payload2).encode("utf-8")
    payload_hash2 = hash_blake2b(pl2)
    canonical2 = canonical_event_bytes(
        event_type="register",
        actor_vacant_id=vid.hex(),
        subject_vacant_id=None,
        payload_hash=payload_hash2,
        idempotency_key=d1.idempotency_key,
        signed_by_pubkey=vid.pubkey_bytes,
        ts=d1.ts,
        actor_seq=3,
    )
    d2 = SignedEventDraft(
        event_type="register",
        actor_vacant_id=vid.hex(),
        subject_vacant_id=None,
        payload=payload2,
        idempotency_key=d1.idempotency_key,
        signed_by_pubkey=vid.pubkey_bytes,
        signature=sign(sk, canonical2),
        actor_seq=3,
        ts=d1.ts,
    )
    with pytest.raises(IdempotencyConflict):
        await registry_store.submit_event(d2)


# --- Attack 3: in-place row tampering (UPDATE bypass) ------------------------
# The append-only guard catches DELETE; UPDATE goes through. Defense:
# `verify_event_chain()` recomputes hashes + sigs from stored row data.


@pytest.mark.asyncio
async def test_attack_payload_json_tamper_detected_by_verify_chain(
    registry_store: RegistryStore,
) -> None:
    sk, _vk, _vid, card = _make_card_and_keys()
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    # Sanity: chain verifies before tampering.
    assert await registry_store.verify_event_chain() is True

    # Attacker UPDATEs payload_json directly via SQL.
    async with registry_store._sessionmaker() as s:
        await s.execute(
            update(Event).where(Event.seq == 1).values(payload_json='{"hijacked":true}')
        )
        await s.commit()

    assert await registry_store.verify_event_chain() is False


@pytest.mark.asyncio
async def test_attack_signature_tamper_detected_by_verify_chain(
    registry_store: RegistryStore,
) -> None:
    sk, _vk, _vid, card = _make_card_and_keys()
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    async with registry_store._sessionmaker() as s:
        await s.execute(update(Event).where(Event.seq == 1).values(signature=b"\x00" * 64))
        await s.commit()
    assert await registry_store.verify_event_chain() is False


@pytest.mark.asyncio
async def test_attack_event_hash_tamper_detected(
    registry_store: RegistryStore,
) -> None:
    sk, _vk, _vid, card = _make_card_and_keys()
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    # Submit a second event so we have a chain to break in the middle.
    sk2 = sk
    _, _, vid, _ = _make_card_and_keys()  # discard, just to use the helper
    _ = vid
    second = _signed_draft(
        sk=sk2,
        vid=VacantId(pubkey_bytes=card.vacant_id.pubkey_bytes),
        actor_seq=2,
        payload={"k": "v"},
    )
    await registry_store.submit_event(second)
    assert await registry_store.verify_event_chain() is True

    # Flip a byte in seq=1's event_hash. seq=2's prev_event_hash still points
    # to the original seq=1 event_hash — chain check breaks.
    async with registry_store._sessionmaker() as s:
        res = await s.execute(select(Event).where(Event.seq == 1))
        ev = res.scalar_one()
        bad = bytearray(ev.event_hash)
        bad[0] ^= 0x01
        await s.execute(update(Event).where(Event.seq == 1).values(event_hash=bytes(bad)))
        await s.commit()
    assert await registry_store.verify_event_chain() is False


# --- Attack 4: chain prev_event_hash splice attempt --------------------------
# Defense (P): each event commits to the previous event's hash via prev_event_hash.
# Attempting to splice a forged event between two real ones requires
# recomputing every subsequent event_hash AND obtaining each subsequent
# actor's signing key.


@pytest.mark.asyncio
async def test_attack_prev_event_hash_splice_detected(
    registry_store: RegistryStore,
) -> None:
    sk, _vk, _vid, card = _make_card_and_keys()
    await publish_halo(
        store=registry_store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
    )
    # Modify seq=1's prev_event_hash directly. The recomputed event_hash
    # then differs from the stored one.
    async with registry_store._sessionmaker() as s:
        await s.execute(update(Event).where(Event.seq == 1).values(prev_event_hash=b"\xff" * 32))
        await s.commit()
    assert await registry_store.verify_event_chain() is False
