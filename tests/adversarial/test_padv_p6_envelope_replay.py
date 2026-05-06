"""Padv P6 -- envelope replay / cross-pair forgery (D009 / dispatch §"Envelope replay across pairs").

Spec anchors:
- `architecture/components/P6_protocol.md` §6 (replay protection)
- `architecture/decisions/D009_p6_protocol_reconciliation.md` §B (per-pair chain)
- `dispatch/Padv_review.md` §"P6 Protocol attacks to consider"
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from vacant.core.crypto import keygen
from vacant.core.types import (
    EMPTY_PREV_HASH,
    BehaviorBundle,
    CapabilityCard,
    Logbook,
    ResidentForm,
    SubstrateSpec,
    VacantId,
    VacantState,
)
from vacant.protocol import (
    A2AMessage,
    A2APart,
    ChainForkError,
    InMemoryReplayStore,
    PairKey,
    ReplayDetectedError,
    VacantEnvelope,
    build_a2a_app,
    to_a2a_jsonrpc,
)


def _make_id():  # type: ignore[no-untyped-def]
    sk, vk = keygen()
    return sk, VacantId.from_verify_key(vk)


def _envelope(*, sk, frm, to, seq=1, prev=EMPTY_PREV_HASH, text="hi"):  # type: ignore[no-untyped-def]
    return VacantEnvelope(
        from_vacant_id=frm,
        to_vacant_id=to,
        sequence_no=seq,
        timestamp=datetime(2026, 5, 6, tzinfo=UTC),
        prev_envelope_hash=prev,
        payload=A2AMessage(parts=[A2APart(text=text)]),
        idempotency_key="idem-1",
    ).signed(sk)


# --- Attack 1: cross-pair forgery (replay an envelope from A->B as A->C) ----
# Defense (P, write-time): the envelope's signing payload includes
# `to_vacant_id`, so swapping the recipient breaks the Ed25519 signature.
# The serve handler also short-circuits with 421 if `to_vacant_id` doesn't
# match the server's own identity.


def test_attack_cross_pair_replay_swap_to_breaks_signature() -> None:
    """An attacker captures (A -> B) envelope, swaps the to-id to C, signature fails."""
    sk_a, a_id = _make_id()
    _sk_b, b_id = _make_id()
    _sk_c, c_id = _make_id()
    env_ab = _envelope(sk=sk_a, frm=a_id, to=b_id, seq=1)

    # Forge the same envelope but with to=C.
    forged = env_ab.model_copy(update={"to_vacant_id": c_id})
    assert forged.verify(a_id.verify_key()) is False


@pytest.mark.asyncio
async def test_attack_cross_pair_replay_at_serve_layer_returns_421() -> None:
    """Replay via HTTP serve: even if the metadata is rewritten end-to-end
    by an attacker (regenerating the ID), the misdirected request short-
    circuits before signature verification."""
    _sk_b, b_form = _build_form()
    sk_c, c_form = _build_form()  # serve C

    store = InMemoryReplayStore()

    async def echo(env: VacantEnvelope) -> A2AMessage:
        return A2AMessage(parts=[A2APart(text="ack")])

    app = build_a2a_app(
        self_form=c_form,
        self_signing_key=sk_c,
        behavior=echo,
        replay_store=store,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        sk_a, a_id = _make_id()
        env_ab = _envelope(sk=sk_a, frm=a_id, to=b_form.identity, seq=1)
        # Send the (A -> B) envelope to C's serve endpoint -- 421 misdirected.
        r = await ac.post("/a2a/message/send", json=to_a2a_jsonrpc(env_ab))
        assert r.status_code == 421


# --- Attack 2: same-pair replay (resend captured envelope) -----------------
# Defense (P): per-pair (sequence_no, chain_tip) state in the replay store
# rejects any envelope whose seq <= last_seen.


@pytest.mark.asyncio
async def test_attack_same_envelope_replayed_to_same_pair_rejected() -> None:
    sk_a, a_id = _make_id()
    _sk_b, b_id = _make_id()
    store = InMemoryReplayStore()
    env = _envelope(sk=sk_a, frm=a_id, to=b_id, seq=1)
    await store.check_and_advance(env)
    with pytest.raises(ReplayDetectedError):
        await store.check_and_advance(env)


@pytest.mark.asyncio
async def test_attack_serve_returns_409_on_replay() -> None:
    """End-to-end: replay the same signed envelope through the serve
    endpoint; second submission returns HTTP 409 (replay)."""
    sk, form = _build_form()
    store = InMemoryReplayStore()

    async def behavior(env: VacantEnvelope) -> A2AMessage:
        return A2AMessage(parts=[A2APart(text="ack")])

    app = build_a2a_app(self_form=form, self_signing_key=sk, behavior=behavior, replay_store=store)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        caller_sk, caller_id = _make_id()
        env = _envelope(sk=caller_sk, frm=caller_id, to=form.identity, seq=1)
        body = to_a2a_jsonrpc(env)
        r1 = await ac.post("/a2a/message/send", json=body)
        assert r1.status_code == 200
        r2 = await ac.post("/a2a/message/send", json=body)
        assert r2.status_code == 409


# --- Attack 3: chain-fork (skip seq, forge prev_hash) ----------------------
# Defense (P): strict +1 monotonicity AND prev_hash equality with the
# stored chain_tip.


@pytest.mark.asyncio
async def test_attack_skip_seq_rejected() -> None:
    """Attacker tries to send seq=3 after seq=1; rejected as non-monotonic."""
    sk_a, a_id = _make_id()
    _sk_b, b_id = _make_id()
    store = InMemoryReplayStore()
    env1 = _envelope(sk=sk_a, frm=a_id, to=b_id, seq=1)
    await store.check_and_advance(env1)
    env3 = _envelope(sk=sk_a, frm=a_id, to=b_id, seq=3, prev=env1.compute_hash())
    with pytest.raises(ReplayDetectedError):
        await store.check_and_advance(env3)


@pytest.mark.asyncio
async def test_attack_forged_prev_hash_rejected() -> None:
    """Attacker submits seq=2 with attacker-chosen prev_hash; rejected
    as chain fork."""
    sk_a, a_id = _make_id()
    _sk_b, b_id = _make_id()
    store = InMemoryReplayStore()
    env1 = _envelope(sk=sk_a, frm=a_id, to=b_id, seq=1)
    await store.check_and_advance(env1)
    forked = _envelope(sk=sk_a, frm=a_id, to=b_id, seq=2, prev=b"\xaa" * 32)
    with pytest.raises(ChainForkError):
        await store.check_and_advance(forked)


# --- Attack 4: tamper signature/seq/prev after sign breaks signature -------
# Defense (P): the signed payload covers (from, to, seq, ts, prev, idem,
# payload). Any field tamper invalidates the signature.


def test_attack_tamper_seq_after_sign_breaks_signature() -> None:
    sk_a, a_id = _make_id()
    _sk_b, b_id = _make_id()
    env = _envelope(sk=sk_a, frm=a_id, to=b_id, seq=1)
    bumped = env.model_copy(update={"sequence_no": 5})
    assert bumped.verify(a_id.verify_key()) is False


def test_attack_tamper_prev_hash_after_sign_breaks_signature() -> None:
    sk_a, a_id = _make_id()
    _sk_b, b_id = _make_id()
    env = _envelope(sk=sk_a, frm=a_id, to=b_id, seq=1, prev=b"\x00" * 32)
    rewired = env.model_copy(update={"prev_envelope_hash": b"\xff" * 32})
    assert rewired.verify(a_id.verify_key()) is False


def test_attack_tamper_payload_after_sign_breaks_signature() -> None:
    sk_a, a_id = _make_id()
    _sk_b, b_id = _make_id()
    env = _envelope(sk=sk_a, frm=a_id, to=b_id, seq=1, text="please pay $5")
    swapped = env.model_copy(
        update={"payload": A2AMessage(parts=[A2APart(text="please pay $5000")])}
    )
    assert swapped.verify(a_id.verify_key()) is False


# --- Attack 5: separate pairs use independent counters ---------------------
# Regression-guard: an attacker cannot poison pair (A, C)'s state by
# advancing pair (A, B).


@pytest.mark.asyncio
async def test_attack_separate_pairs_have_independent_seq_counters() -> None:
    sk_a, a_id = _make_id()
    _sk_b, b_id = _make_id()
    _sk_c, c_id = _make_id()
    store = InMemoryReplayStore()
    # Advance (A -> B) to seq=1.
    await store.check_and_advance(_envelope(sk=sk_a, frm=a_id, to=b_id, seq=1))
    # First (A -> C) at seq=1 still accepted; pairs are independent.
    await store.check_and_advance(_envelope(sk=sk_a, frm=a_id, to=c_id, seq=1))
    state_ac = await store.get(PairKey(from_vid=a_id, to_vid=c_id))
    state_ab = await store.get(PairKey(from_vid=a_id, to_vid=b_id))
    assert state_ab.last_sequence_no == 1
    assert state_ac.last_sequence_no == 1
    assert state_ab.chain_tip != state_ac.chain_tip


# --- helpers ---------------------------------------------------------------


def _build_form(state: VacantState = VacantState.ACTIVE) -> tuple[Any, ResidentForm]:
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    bundle = BehaviorBundle(system_prompt="x")
    spec = SubstrateSpec(allowed_substrates=["mock"])
    lb = Logbook()
    lb.append("genesis", {}, sk)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text="echo",
        substrate_spec=spec,
        endpoint="http://test",
    ).signed(sk)
    return sk, ResidentForm(
        identity=vid,
        logbook=lb,
        behavior_bundle=bundle,
        substrate_spec=spec,
        runtime_state=state,
        capability_card=card,
    )


_ = pytest_asyncio  # silence unused-import lint
