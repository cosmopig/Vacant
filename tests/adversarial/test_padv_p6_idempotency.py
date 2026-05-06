"""Padv P6 -- idempotency_key collision (D009 / dispatch §"Idempotency key collision").

Spec anchors:
- `architecture/components/P6_protocol.md` §6 (replay protection)
- `architecture/decisions/D009_p6_protocol_reconciliation.md`
- `architecture/decisions/D011_padv_p6_findings.md` §"Idempotency residual"
- `dispatch/Padv_review.md` §"P6 Protocol attacks to consider"

The dispatch lists the attack: replay with the same `idempotency_key` on
a different request body. The spec's stated defense is "server stores
body hash next to key". For P6 MVP the server does NOT implement an
idempotency cache -- the *primary* defense against replay is the
per-pair (sequence_no, chain_tip) check, which dedupes envelopes
regardless of idem-key. The structural mitigations against the
"different body, same idem-key" variant of the attack:

1. `idempotency_key` is in the envelope's signed scope -- an attacker
   cannot rewrite it without invalidating the signature.
2. Two envelopes with same idem-key but different bodies have different
   signatures and different `compute_hash()` outputs, so a server that
   *does* implement idem caching can detect the collision.
3. The MVP's per-pair seq+chain prevents *any* envelope replay,
   collapsing the attack surface to "honest legitimate retry would also
   be rejected" -- a usability cost, not a security flaw. Future work
   (D011 §residual) layers an idempotency cache on top of seq+chain.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from vacant.core.crypto import keygen
from vacant.core.types import EMPTY_PREV_HASH, VacantId
from vacant.protocol import (
    A2AMessage,
    A2APart,
    InMemoryReplayStore,
    ReplayDetectedError,
    VacantEnvelope,
    to_a2a_jsonrpc,
)


def _make_id():  # type: ignore[no-untyped-def]
    sk, vk = keygen()
    return sk, VacantId.from_verify_key(vk)


def _envelope(*, sk, frm, to, idem, seq=1, text="hi"):  # type: ignore[no-untyped-def]
    return VacantEnvelope(
        from_vacant_id=frm,
        to_vacant_id=to,
        sequence_no=seq,
        timestamp=datetime(2026, 5, 6, tzinfo=UTC),
        prev_envelope_hash=EMPTY_PREV_HASH,
        payload=A2AMessage(parts=[A2APart(text=text)]),
        idempotency_key=idem,
    ).signed(sk)


# --- Attack 1: idempotency_key tamper after sign breaks signature ---------
# Defense (P): idem-key is in `signing_dict()["idem"]` -- swapping it
# invalidates the Ed25519 signature.


def test_attack_idempotency_key_tamper_breaks_signature() -> None:
    sk_a, a_id = _make_id()
    _sk_b, b_id = _make_id()
    env = _envelope(sk=sk_a, frm=a_id, to=b_id, idem="key-A", text="hi")
    swapped = env.model_copy(update={"idempotency_key": "key-B"})
    assert swapped.verify(a_id.verify_key()) is False


# --- Attack 2: same idem-key, different body, distinct signatures ---------
# Property: two envelopes with the same idem-key but different bodies
# produce *different* envelope hashes. A future idem-cache could use
# this to detect the collision; the MVP's seq+chain replay store
# already rejects either envelope as a replay if both arrive on the
# same pair.


def test_attack_same_idem_different_body_distinct_envelope_hashes() -> None:
    sk_a, a_id = _make_id()
    _sk_b, b_id = _make_id()
    e1 = _envelope(sk=sk_a, frm=a_id, to=b_id, idem="dup", text="approve $5")
    e2 = _envelope(sk=sk_a, frm=a_id, to=b_id, idem="dup", text="approve $50000")
    # Bodies differ, so hashes differ even though idem-keys match.
    assert e1.compute_hash() != e2.compute_hash()
    # Both verify under the sender's pubkey -- bug surface only exists
    # if the receiver dedupes by idem-key alone (which the MVP does not do).
    assert e1.verify(a_id.verify_key()) is True
    assert e2.verify(a_id.verify_key()) is True


# --- Attack 3: same idem-key, same body, same sig -- replay store catches -
# Sanity: legitimate retry (same envelope, same idem-key) is detected by
# the per-pair seq+chain check, independent of idem-cache.


@pytest.mark.asyncio
async def test_attack_same_idem_same_body_replay_caught_by_seq_chain() -> None:
    sk_a, a_id = _make_id()
    _sk_b, b_id = _make_id()
    store = InMemoryReplayStore()
    env = _envelope(sk=sk_a, frm=a_id, to=b_id, idem="retry-1", seq=1)
    await store.check_and_advance(env)
    with pytest.raises(ReplayDetectedError):
        await store.check_and_advance(env)


# --- Attack 4: idem-key collision across different pairs is not pollution -
# Even if an attacker uses the same idem-key when calling target B and
# target C, the per-pair chain state is independent.


@pytest.mark.asyncio
async def test_attack_idem_key_reused_across_pairs_independent_state() -> None:
    sk_a, a_id = _make_id()
    _sk_b, b_id = _make_id()
    _sk_c, c_id = _make_id()
    store = InMemoryReplayStore()
    e_ab = _envelope(sk=sk_a, frm=a_id, to=b_id, idem="dup-key", text="x")
    e_ac = _envelope(sk=sk_a, frm=a_id, to=c_id, idem="dup-key", text="x")
    await store.check_and_advance(e_ab)
    # Same idem-key works across (A -> C) -- pair state is independent.
    await store.check_and_advance(e_ac)


# --- Attack 5: jsonrpc id derived from idem-key is not the dedupe key ----
# Regression-guard: `to_a2a_jsonrpc` uses the idem-key as the JSON-RPC
# `id` field, but the MVP server does NOT use jsonrpc id for dedupe --
# the per-pair seq+chain is the source of truth.


def test_attack_jsonrpc_id_falls_back_to_envelope_hash_when_idem_empty() -> None:
    """When idem-key is empty, jsonrpc id falls back to the envelope hash --
    not the empty string. Otherwise an attacker could trivially force
    `id == ""` collisions."""
    sk_a, a_id = _make_id()
    _sk_b, b_id = _make_id()
    env = _envelope(sk=sk_a, frm=a_id, to=b_id, idem="", text="hi")
    body = to_a2a_jsonrpc(env)
    assert body["id"] != ""
    assert body["id"] == env.compute_hash().hex()
