"""Property tests for the per-pair envelope chain (P6 §6)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from vacant.core.crypto import keygen
from vacant.core.types import EMPTY_PREV_HASH, VacantId
from vacant.protocol import (
    A2AMessage,
    A2APart,
    InMemoryReplayStore,
    VacantEnvelope,
)
from vacant.protocol.errors import ChainForkError, ReplayDetectedError


def _build_chain(*, sk, frm, to, n: int) -> list[VacantEnvelope]:
    chain: list[VacantEnvelope] = []
    prev = EMPTY_PREV_HASH
    for i in range(1, n + 1):
        env = VacantEnvelope(
            from_vacant_id=frm,
            to_vacant_id=to,
            sequence_no=i,
            timestamp=datetime(2026, 5, 6, tzinfo=UTC),
            prev_envelope_hash=prev,
            payload=A2AMessage(parts=[A2APart(text=f"msg-{i}")]),
        ).signed(sk)
        chain.append(env)
        prev = env.compute_hash()
    return chain


def _pair():  # type: ignore[no-untyped-def]
    sk, vk = keygen()
    _sk2, vk2 = keygen()
    return sk, VacantId.from_verify_key(vk), VacantId.from_verify_key(vk2)


@given(n=st.integers(min_value=2, max_value=8))
@settings(max_examples=10, deadline=None)
@pytest.mark.asyncio
async def test_clean_chain_accepted(n: int) -> None:
    sk, frm, to = _pair()
    chain = _build_chain(sk=sk, frm=frm, to=to, n=n)
    store = InMemoryReplayStore()
    for env in chain:
        await store.check_and_advance(env)


@given(
    n=st.integers(min_value=3, max_value=8),
    swap_idx=st.integers(min_value=0, max_value=6),
)
@settings(max_examples=20, deadline=None)
@pytest.mark.asyncio
async def test_reordering_chain_rejected(n: int, swap_idx: int) -> None:
    sk, frm, to = _pair()
    chain = _build_chain(sk=sk, frm=frm, to=to, n=n)
    idx = swap_idx % (n - 1)
    if idx == 0:
        idx = 1
    # Apply 1..idx-1 cleanly, then submit idx+1 BEFORE idx → strict +1
    # rejection.
    store = InMemoryReplayStore()
    for env in chain[:idx]:
        await store.check_and_advance(env)
    # Submit a later envelope first.
    later = chain[idx + 1] if idx + 1 < n else chain[-1]
    if later.sequence_no <= chain[idx - 1].sequence_no + 1:
        return  # not a reordering for this idx; skip
    with pytest.raises(ReplayDetectedError):
        await store.check_and_advance(later)


@given(n=st.integers(min_value=2, max_value=6))
@settings(max_examples=15, deadline=None)
@pytest.mark.asyncio
async def test_inserted_envelope_with_wrong_prev_hash_rejected(n: int) -> None:
    sk, frm, to = _pair()
    chain = _build_chain(sk=sk, frm=frm, to=to, n=n)
    store = InMemoryReplayStore()
    await store.check_and_advance(chain[0])
    # Build an envelope at seq=2 but with a fabricated prev_envelope_hash.
    fabricated = VacantEnvelope(
        from_vacant_id=frm,
        to_vacant_id=to,
        sequence_no=2,
        timestamp=datetime(2026, 5, 6, tzinfo=UTC),
        prev_envelope_hash=b"\xdd" * 32,
        payload=A2AMessage(parts=[A2APart(text="injected")]),
    ).signed(sk)
    with pytest.raises(ChainForkError):
        await store.check_and_advance(fabricated)


@given(n=st.integers(min_value=2, max_value=6))
@settings(max_examples=15, deadline=None)
@pytest.mark.asyncio
async def test_replayed_envelope_rejected(n: int) -> None:
    sk, frm, to = _pair()
    chain = _build_chain(sk=sk, frm=frm, to=to, n=n)
    store = InMemoryReplayStore()
    for env in chain:
        await store.check_and_advance(env)
    # Replay the last one.
    with pytest.raises(ReplayDetectedError):
        await store.check_and_advance(chain[-1])
