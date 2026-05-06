"""Padv P4 — concurrent-write attacks.

Spec anchors:
- `architecture/components/P4_registry.md` §3.2 (write flow)
- `dispatch/Padv_review.md` §"Concurrent write race"
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
    SequenceMonotonicityError,
    SignedEventDraft,
    canonical_event_bytes,
    canonical_json,
    now_ms,
    publish_halo,
)


def _signed_draft(*, sk, vid, actor_seq, payload, idem_suffix=""):  # type: ignore[no-untyped-def]
    pl = canonical_json(payload).encode("utf-8")
    payload_hash = hash_blake2b(pl)
    ts = now_ms()
    idem = f"padv-conc-{vid.hex()[:8]}-{actor_seq}-{idem_suffix}"
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


# --- Attack 1: dual writers racing for actor_seq=2 ---------------------------
# Defense (P): the store's internal `asyncio.Lock` serialises the chain
# update. Two concurrent submits for the same actor_seq value: one wins,
# the other gets `SequenceMonotonicityError` because the first commit
# bumped `last_for_actor` to seq=2 already.


@pytest.mark.asyncio
async def test_attack_dual_writers_for_same_seq_one_wins(
    registry_store: RegistryStore,
) -> None:
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

    d1 = _signed_draft(sk=sk, vid=vid, actor_seq=2, payload={"v": 1}, idem_suffix="a")
    d2 = _signed_draft(sk=sk, vid=vid, actor_seq=2, payload={"v": 2}, idem_suffix="b")

    results = await asyncio.gather(
        registry_store.submit_event(d1),
        registry_store.submit_event(d2),
        return_exceptions=True,
    )
    successes = [r for r in results if not isinstance(r, Exception)]
    failures = [r for r in results if isinstance(r, Exception)]
    assert len(successes) == 1
    assert len(failures) == 1
    assert isinstance(failures[0], SequenceMonotonicityError)


# --- Attack 2: 20 writers from different actors interleaving -----------------
# Defense (P): even with high contention, the chain stays valid (single
# `prev_event_hash` cursor protected by lock).


@pytest.mark.asyncio
async def test_attack_20_writers_no_chain_corruption(
    registry_store: RegistryStore,
) -> None:
    n = 20
    writers = []
    for _ in range(n):
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

    async def _emit(sk, vid):  # type: ignore[no-untyped-def]
        d = _signed_draft(sk=sk, vid=vid, actor_seq=2, payload={"k": "v"})
        await registry_store.submit_event(d)

    await asyncio.gather(*(_emit(sk, vid) for sk, vid in writers))

    # Chain still validates end-to-end.
    assert await registry_store.verify_event_chain() is True


# --- Attack 3: idempotency-replay storm during a race -----------------------
# Defense (P): idempotency dedup happens INSIDE the write lock; concurrent
# submits with identical idem keys land on the same row.


@pytest.mark.asyncio
async def test_attack_concurrent_idempotent_replays_dedupe(
    registry_store: RegistryStore,
) -> None:
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
    d = _signed_draft(sk=sk, vid=vid, actor_seq=2, payload={"v": 1}, idem_suffix="dup")

    results = await asyncio.gather(
        *[registry_store.submit_event(d) for _ in range(8)],
        return_exceptions=True,
    )
    # All 8 succeed and return the same seq (idempotent dedup).
    seqs = [r.seq for r in results if not isinstance(r, Exception)]
    assert len(seqs) == 8
    assert all(s == seqs[0] for s in seqs)
