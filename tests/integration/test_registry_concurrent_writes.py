"""Concurrent-write integration test (slow).

10 concurrent writers issuing events to a single registry. The store's
internal `asyncio.Lock` serialises the chain-update critical section, so
there should be no lost updates and the resulting chain should still
validate end-to-end.
"""

from __future__ import annotations

import asyncio

import pytest

from vacant.core.crypto import hash_blake2b, keygen, sign
from vacant.core.types import (
    CapabilityCard,
    SubstrateSpec,
    VacantId,
    VacantState,
)
from vacant.registry import (
    RegistryStore,
    SignedEventDraft,
    canonical_event_bytes,
    canonical_json,
    now_ms,
    publish_halo,
)

pytestmark = pytest.mark.slow


def _make_signed_draft(*, sk, vid, actor_seq, payload):  # type: ignore[no-untyped-def]
    pl = canonical_json(payload).encode("utf-8")
    payload_hash = hash_blake2b(pl)
    ts = now_ms()
    idem = f"concurrent-{vid.hex()[:8]}-{actor_seq}"
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
async def test_ten_concurrent_writers_no_lost_updates(
    registry_store: RegistryStore,
) -> None:
    # 10 vacants, each emits 5 events serially. The 10 vacants run in
    # parallel so submission threads interleave.
    n_writers = 10
    n_events_each = 5

    writers = []
    for _ in range(n_writers):
        sk, vk = keygen()
        vid = VacantId.from_verify_key(vk)
        card = CapabilityCard(
            vacant_id=vid,
            capability_text="x",
            substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
        ).signed(sk)
        await publish_halo(
            store=registry_store,
            card=card,
            runtime_state=VacantState.ACTIVE,
            signing_key=sk,
        )
        writers.append((sk, vid))

    async def _run_writer(sk, vid):  # type: ignore[no-untyped-def]
        # actor_seq starts at 2 because publish_halo emitted the register at seq=1.
        for i in range(2, 2 + n_events_each):
            draft = _make_signed_draft(sk=sk, vid=vid, actor_seq=i, payload={"i": i})
            await registry_store.submit_event(draft)

    await asyncio.gather(*(_run_writer(sk, vid) for sk, vid in writers))

    # Verify chain integrity end-to-end.
    expected_total = n_writers + n_writers * n_events_each
    prev = b"\x00" * 32
    seen = 0
    for seq in range(1, expected_total + 1):
        e = await registry_store.get_event(seq)
        assert e is not None
        assert e.prev_event_hash == prev
        prev = e.event_hash
        seen += 1
    assert seen == expected_total

    # Per-vacant actor_seq is contiguous 1..(1+n_events_each).
    for sk, vid in writers:
        events = await registry_store.list_events_for_vacant(vid.hex(), limit=500)
        seqs = [e.actor_seq for e in events]
        assert seqs == list(range(1, 1 + 1 + n_events_each))
        _ = sk
