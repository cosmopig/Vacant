"""Hypothesis property tests for the logbook hash-chain invariants."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from vacant.core.crypto import keygen, verify
from vacant.core.errors import HashChainError
from vacant.core.types import EMPTY_PREV_HASH, Logbook

_PRIMITIVE = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(10**6), max_value=10**6),
    st.text(max_size=32),
)
PAYLOADS = st.dictionaries(st.text(min_size=1, max_size=8), _PRIMITIVE, max_size=4)


@given(
    kinds=st.lists(
        st.text(min_size=1, max_size=10).filter(lambda s: s.strip()), min_size=1, max_size=8
    ),
    payloads=st.lists(PAYLOADS, min_size=1, max_size=8),
)
@settings(max_examples=50, deadline=None)
def test_logbook_chain_round_trip(kinds: list[str], payloads: list[dict[str, object]]) -> None:
    sk, vk = keygen()
    lb = Logbook()
    n = min(len(kinds), len(payloads))
    for i in range(n):
        lb.append(kinds[i], payloads[i], sk)
    assert lb.verify_chain(vk) is True

    expected_prev = EMPTY_PREV_HASH
    for entry in lb.entries:
        assert entry.prev_hash == expected_prev
        assert verify(vk, entry.signing_payload(), entry.signature)
        expected_prev = entry.compute_hash()


@given(
    payloads=st.lists(PAYLOADS, min_size=2, max_size=6),
    target_idx=st.integers(min_value=0, max_value=5),
    new_value=st.integers(),
)
@settings(max_examples=50, deadline=None)
def test_tampering_any_entry_breaks_chain(
    payloads: list[dict[str, object]], target_idx: int, new_value: int
) -> None:
    sk, vk = keygen()
    lb = Logbook()
    for p in payloads:
        lb.append("kind", p, sk)
    idx = target_idx % len(lb.entries)
    bad = lb.entries[idx].model_copy(update={"payload": {"hijacked": new_value}})
    lb.entries[idx] = bad
    assert lb.verify_chain(vk) is False


@given(garbage=st.binary(min_size=0, max_size=80))
@settings(max_examples=50, deadline=None)
def test_random_bytes_never_verify_as_signature(garbage: bytes) -> None:
    sk, vk = keygen()
    msg = b"canonical message"
    real_sig = sk.sign(msg).signature
    if garbage == real_sig:
        return
    assert verify(vk, msg, garbage) is False


@given(payloads=st.lists(PAYLOADS, min_size=2, max_size=5))
@settings(max_examples=30, deadline=None)
def test_reorder_breaks_chain(payloads: list[dict[str, object]]) -> None:
    sk, vk = keygen()
    lb = Logbook()
    for p in payloads:
        lb.append("k", p, sk)
    lb.entries.reverse()
    assert lb.verify_chain(vk) is False


@given(payloads=st.lists(PAYLOADS, min_size=1, max_size=4))
@settings(max_examples=30, deadline=None)
def test_verify_chain_or_raise_matches_verify_chain(
    payloads: list[dict[str, object]],
) -> None:
    sk, vk = keygen()
    lb = Logbook()
    for p in payloads:
        lb.append("k", p, sk)
    lb.verify_chain_or_raise(vk)
    bad = lb.entries[0].model_copy(update={"signature": b"\x00" * 64})
    lb.entries[0] = bad
    assert lb.verify_chain(vk) is False
    with pytest.raises(HashChainError):
        lb.verify_chain_or_raise(vk)


def test_unicode_payload_round_trip() -> None:
    sk, vk = keygen()
    lb = Logbook()
    lb.append("評論", {"訊息": "你好"}, sk, ts=datetime(2026, 5, 5, tzinfo=UTC))
    assert lb.verify_chain(vk) is True
