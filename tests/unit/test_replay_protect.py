"""Replay-protect store unit tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from vacant.core.crypto import keygen
from vacant.core.types import EMPTY_PREV_HASH, VacantId
from vacant.protocol import (
    A2AMessage,
    A2APart,
    ChainForkError,
    InMemoryReplayStore,
    PairKey,
    ReplayDetectedError,
    ReplayState,
    SqliteReplayStore,
    VacantEnvelope,
)


def _envelope(*, sk, frm, to, seq, prev=EMPTY_PREV_HASH):  # type: ignore[no-untyped-def]
    return VacantEnvelope(
        from_vacant_id=frm,
        to_vacant_id=to,
        sequence_no=seq,
        timestamp=datetime(2026, 5, 6, tzinfo=UTC),
        prev_envelope_hash=prev,
        payload=A2AMessage(parts=[A2APart(text=f"msg-{seq}")]),
    ).signed(sk)


def _pair():  # type: ignore[no-untyped-def]
    sk_a, vk_a = keygen()
    sk_b, vk_b = keygen()
    return (sk_a, VacantId.from_verify_key(vk_a), sk_b, VacantId.from_verify_key(vk_b))


# --- in-memory ------------------------------------------------------------


@pytest.mark.asyncio
async def test_in_memory_first_envelope_accepted() -> None:
    sk_a, frm, _sk_b, to = _pair()
    store = InMemoryReplayStore()
    env = _envelope(sk=sk_a, frm=frm, to=to, seq=1)
    await store.check_and_advance(env)
    state = await store.get(PairKey(from_vid=frm, to_vid=to))
    assert state.last_sequence_no == 1
    assert state.chain_tip == env.compute_hash()


@pytest.mark.asyncio
async def test_in_memory_consecutive_envelopes_accepted() -> None:
    sk_a, frm, _sk_b, to = _pair()
    store = InMemoryReplayStore()
    env1 = _envelope(sk=sk_a, frm=frm, to=to, seq=1)
    await store.check_and_advance(env1)
    env2 = _envelope(sk=sk_a, frm=frm, to=to, seq=2, prev=env1.compute_hash())
    await store.check_and_advance(env2)


@pytest.mark.asyncio
async def test_in_memory_replay_rejected() -> None:
    sk_a, frm, _sk_b, to = _pair()
    store = InMemoryReplayStore()
    env1 = _envelope(sk=sk_a, frm=frm, to=to, seq=1)
    await store.check_and_advance(env1)
    with pytest.raises(ReplayDetectedError):
        await store.check_and_advance(env1)


@pytest.mark.asyncio
async def test_in_memory_out_of_order_rejected() -> None:
    sk_a, frm, _sk_b, to = _pair()
    store = InMemoryReplayStore()
    env1 = _envelope(sk=sk_a, frm=frm, to=to, seq=1)
    await store.check_and_advance(env1)
    # Skip seq=2, send seq=3 → strict +1 rejection.
    env3 = _envelope(sk=sk_a, frm=frm, to=to, seq=3, prev=env1.compute_hash())
    with pytest.raises(ReplayDetectedError):
        await store.check_and_advance(env3)


@pytest.mark.asyncio
async def test_in_memory_forked_chain_rejected() -> None:
    sk_a, frm, _sk_b, to = _pair()
    store = InMemoryReplayStore()
    env1 = _envelope(sk=sk_a, frm=frm, to=to, seq=1)
    await store.check_and_advance(env1)
    # seq=2 with WRONG prev_hash (forked) — should reject.
    forked = _envelope(sk=sk_a, frm=frm, to=to, seq=2, prev=b"\xff" * 32)
    with pytest.raises(ChainForkError):
        await store.check_and_advance(forked)


@pytest.mark.asyncio
async def test_in_memory_separate_pairs_independent() -> None:
    sk_a, a_id, sk_b, b_id = _pair()
    store = InMemoryReplayStore()
    a_to_b = _envelope(sk=sk_a, frm=a_id, to=b_id, seq=1)
    b_to_a = _envelope(sk=sk_b, frm=b_id, to=a_id, seq=1)
    # Both seq=1 but different pairs → both accepted.
    await store.check_and_advance(a_to_b)
    await store.check_and_advance(b_to_a)
    state_ab = await store.get(PairKey(from_vid=a_id, to_vid=b_id))
    state_ba = await store.get(PairKey(from_vid=b_id, to_vid=a_id))
    assert state_ab.last_sequence_no == 1
    assert state_ba.last_sequence_no == 1
    assert state_ab.chain_tip != state_ba.chain_tip


@pytest.mark.asyncio
async def test_in_memory_get_missing_pair_returns_default() -> None:
    _sk_a, a_id, _sk_b, b_id = _pair()
    store = InMemoryReplayStore()
    state = await store.get(PairKey(from_vid=a_id, to_vid=b_id))
    assert state.last_sequence_no == 0
    assert state.chain_tip == EMPTY_PREV_HASH


# --- SQLite-backed --------------------------------------------------------


@pytest.mark.asyncio
async def test_sqlite_replay_store_round_trip() -> None:
    sk_a, frm, _sk_b, to = _pair()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    store = SqliteReplayStore(engine)
    await store.init_schema()
    env1 = _envelope(sk=sk_a, frm=frm, to=to, seq=1)
    await store.check_and_advance(env1)
    state = await store.get(PairKey(from_vid=frm, to_vid=to))
    assert state.last_sequence_no == 1

    env2 = _envelope(sk=sk_a, frm=frm, to=to, seq=2, prev=env1.compute_hash())
    await store.check_and_advance(env2)

    with pytest.raises(ReplayDetectedError):
        await store.check_and_advance(env2)
    await engine.dispose()


@pytest.mark.asyncio
async def test_sqlite_replay_store_chain_fork_rejected() -> None:
    sk_a, frm, _sk_b, to = _pair()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    store = SqliteReplayStore(engine)
    await store.init_schema()
    env1 = _envelope(sk=sk_a, frm=frm, to=to, seq=1)
    await store.check_and_advance(env1)
    bad = _envelope(sk=sk_a, frm=frm, to=to, seq=2, prev=b"\x99" * 32)
    with pytest.raises(ChainForkError):
        await store.check_and_advance(bad)
    await engine.dispose()


# --- Pfix3 F1: InMemoryReplayStore.seed() ---------------------------------


@pytest.mark.asyncio
async def test_in_memory_replay_store_seed_then_advance() -> None:
    """Pfix3 F1: seed() rehydrates pair state so the next envelope on a
    pair is checked against the seeded last_seq + chain_tip, not the
    empty initial state. Used by the CLI to continue an envelope chain
    across process restarts."""
    sk_a, frm, _sk_b, to = _pair()
    store = InMemoryReplayStore()

    env1 = _envelope(sk=sk_a, frm=frm, to=to, seq=1)
    await store.check_and_advance(env1)

    # Re-create the store (simulating process restart) and seed from
    # the stored state.
    new_store = InMemoryReplayStore()
    key = PairKey(from_vid=frm, to_vid=to)
    new_store.seed(
        key,
        ReplayState(last_sequence_no=1, chain_tip=env1.compute_hash()),
    )
    state = await new_store.get(key)
    assert state.last_sequence_no == 1
    assert state.chain_tip == env1.compute_hash()

    # seq=2 chained from env1's hash succeeds against the seeded store.
    env2 = _envelope(sk=sk_a, frm=frm, to=to, seq=2, prev=env1.compute_hash())
    await new_store.check_and_advance(env2)

    # seq=2 again is rejected as replay (the seeded store advanced).
    with pytest.raises(ReplayDetectedError):
        await new_store.check_and_advance(env2)


@pytest.mark.asyncio
async def test_in_memory_replay_store_seed_overwrites_existing_pair() -> None:
    """seed() unconditionally writes — used by CLI to resync with disk
    state. No 'merge' semantics."""
    sk_a, frm, _sk_b, to = _pair()
    store = InMemoryReplayStore()
    env1 = _envelope(sk=sk_a, frm=frm, to=to, seq=1)
    await store.check_and_advance(env1)

    key = PairKey(from_vid=frm, to_vid=to)
    store.seed(
        key,
        ReplayState(last_sequence_no=42, chain_tip=b"\x55" * 32),
    )
    state = await store.get(key)
    assert state.last_sequence_no == 42
    assert state.chain_tip == b"\x55" * 32
