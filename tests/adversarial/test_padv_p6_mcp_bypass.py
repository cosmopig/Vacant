"""Padv P6 -- MCP bridge bypass (D009 / dispatch §"MCP bridge bypass").

Spec anchors:
- `architecture/components/P6_protocol.md` §3.4 (MCP bridge mirrors A2A)
- `architecture/decisions/D009_p6_protocol_reconciliation.md` §G
- `dispatch/Padv_review.md` §"P6 Protocol attacks to consider"

Attack premise: an MCP-aware client could try to call a vacant via the
MCP `tools/call` path and skip the envelope-verify + replay-protect that
the A2A serve path enforces. The defense is that `VacantAsMCPServer.call_tool("vacant_call", ...)`
runs the *same* checks as `serve.py`'s `/a2a/message/send`:
1. Signature verification.
2. State (`can_be_called`).
3. Replay protection.
4. Behaviour dispatch.
5. Signed response envelope.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from vacant.core.crypto import keygen
from vacant.core.types import (
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
    EnvelopeSignatureError,
    InMemoryReplayStore,
    PairKey,
    VacantAsMCPServer,
    VacantEnvelope,
    to_a2a_jsonrpc,
)


def _make(state: VacantState = VacantState.ACTIVE):  # type: ignore[no-untyped-def]
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
        endpoint="http://test/mcp",
    ).signed(sk)
    return (
        sk,
        vid,
        ResidentForm(
            identity=vid,
            logbook=lb,
            behavior_bundle=bundle,
            substrate_spec=spec,
            runtime_state=state,
            capability_card=card,
        ),
    )


async def _ack_behavior(env: VacantEnvelope) -> A2AMessage:
    return A2AMessage(role="ROLE_AGENT", parts=[A2APart(text="ack")])


def _envelope(*, sk, frm, to, seq=1, text="hello"):  # type: ignore[no-untyped-def]
    from vacant.core.types import EMPTY_PREV_HASH

    return VacantEnvelope(
        from_vacant_id=frm,
        to_vacant_id=to,
        sequence_no=seq,
        timestamp=datetime(2026, 5, 6, tzinfo=UTC),
        prev_envelope_hash=EMPTY_PREV_HASH,
        payload=A2AMessage(parts=[A2APart(text=text)]),
    ).signed(sk)


# --- Attack 1: skip signature check via MCP bridge ------------------------
# Defense (P): MCP path calls `request_env.verify_or_raise(...)` before
# dispatching to the behaviour callback.


@pytest.mark.asyncio
async def test_attack_mcp_unsigned_envelope_rejected() -> None:
    """An attacker submits an envelope through the MCP bridge with
    a tampered signature; verify_or_raise rejects it the same way
    serve.py would."""
    target_sk, target_vid, target_form = _make()
    store = InMemoryReplayStore()
    server = VacantAsMCPServer(
        self_form=target_form,
        self_signing_key=target_sk,
        behavior=_ack_behavior,
        replay_store=store,
    )
    caller_sk, caller_vk = keygen()
    caller_vid = VacantId.from_verify_key(caller_vk)
    env = _envelope(sk=caller_sk, frm=caller_vid, to=target_vid)
    body = to_a2a_jsonrpc(env)
    # Flip a signature byte before submitting.
    meta = body["params"]["message"]["metadata"]["urn:vacant:v1"]
    sig = bytearray.fromhex(meta["caller_signature"])
    sig[0] ^= 0x01
    meta["caller_signature"] = sig.hex()
    with pytest.raises(EnvelopeSignatureError):
        await server.call_tool("vacant_call", {"envelope": body})


# --- Attack 2: replay an envelope through the MCP bridge ------------------
# Defense (P): the MCP bridge calls `replay_store.check_and_advance` --
# the *same* store the A2A serve path uses. So replays are rejected
# whichever bridge they come through.


@pytest.mark.asyncio
async def test_attack_mcp_replay_rejected_via_shared_replay_store() -> None:
    target_sk, target_vid, target_form = _make()
    store = InMemoryReplayStore()
    server = VacantAsMCPServer(
        self_form=target_form,
        self_signing_key=target_sk,
        behavior=_ack_behavior,
        replay_store=store,
    )
    caller_sk, caller_vk = keygen()
    env = _envelope(sk=caller_sk, frm=VacantId.from_verify_key(caller_vk), to=target_vid)
    body = to_a2a_jsonrpc(env)
    out1 = await server.call_tool("vacant_call", {"envelope": body})
    assert "message" in out1
    # Replay -- replay_store rejects with ReplayDetectedError, which the
    # caller surfaces. Either way the malicious replay does not produce
    # a "successful" tool result.
    from vacant.protocol.errors import ReplayDetectedError

    with pytest.raises(ReplayDetectedError):
        await server.call_tool("vacant_call", {"envelope": body})


# --- Attack 3: MCP bridge to a SUNK vacant rejected -----------------------
# Defense (P): MCP bridge checks `can_be_called(self_form.runtime_state)`,
# matching serve.py's gate.


@pytest.mark.asyncio
async def test_attack_mcp_sunk_vacant_does_not_accept_calls() -> None:
    target_sk, target_vid, target_form = _make(state=VacantState.SUNK)
    store = InMemoryReplayStore()
    server = VacantAsMCPServer(
        self_form=target_form,
        self_signing_key=target_sk,
        behavior=_ack_behavior,
        replay_store=store,
    )
    caller_sk, caller_vk = keygen()
    env = _envelope(sk=caller_sk, frm=VacantId.from_verify_key(caller_vk), to=target_vid)
    out = await server.call_tool("vacant_call", {"envelope": to_a2a_jsonrpc(env)})
    assert "error" in out
    assert "sunk" in out["error"].lower() or "not accepting" in out["error"].lower()


# --- Attack 4: MCP `vacant_describe` does not leak signing key material --
# Sanity: the describe tool returns capability text + halo metadata only,
# not the private key (regression guard against future refactors).


@pytest.mark.asyncio
async def test_attack_mcp_describe_does_not_leak_secrets() -> None:
    target_sk, target_vid, target_form = _make()
    store = InMemoryReplayStore()
    server = VacantAsMCPServer(
        self_form=target_form,
        self_signing_key=target_sk,
        behavior=_ack_behavior,
        replay_store=store,
    )
    out = await server.call_tool("vacant_describe", {})
    # Must NOT return any of these fields.
    forbidden_substrings = ["private", "secret", "signing_key", "seed"]
    payload = repr(out).lower()
    for s in forbidden_substrings:
        assert s not in payload
    # Should return capability_text + halo_version + endpoint.
    assert "capability_text" in out
    assert "halo_version" in out
    _ = target_vid


# --- Attack 5: MCP and A2A share the same per-pair chain state ------------
# Defense (P): the dispatcher advances *both directions* of the per-pair
# chain whether the request came in over A2A or MCP. So an attacker
# cannot use MCP to issue seq=1 and then A2A to issue seq=1 again.


@pytest.mark.asyncio
async def test_attack_mcp_and_a2a_share_replay_state() -> None:
    target_sk, target_vid, target_form = _make()
    shared_store = InMemoryReplayStore()
    server = VacantAsMCPServer(
        self_form=target_form,
        self_signing_key=target_sk,
        behavior=_ack_behavior,
        replay_store=shared_store,
    )
    caller_sk, caller_vk = keygen()
    caller_vid = VacantId.from_verify_key(caller_vk)
    env = _envelope(sk=caller_sk, frm=caller_vid, to=target_vid, seq=1)
    out = await server.call_tool("vacant_call", {"envelope": to_a2a_jsonrpc(env)})
    assert "message" in out
    # Now check the chain state advanced on the (caller -> target) pair.
    state = await shared_store.get(PairKey(from_vid=caller_vid, to_vid=target_vid))
    assert state.last_sequence_no == 1


# --- Attack 6: misdirected envelope through MCP rejected ------------------
# Regression-guard: MCP `vacant_call` rejects envelopes addressed to
# someone else (matches serve.py's 421 check).


@pytest.mark.asyncio
async def test_attack_mcp_misdirected_envelope_rejected() -> None:
    target_sk, target_vid, target_form = _make()
    _other_sk, other_vk = keygen()
    other_vid = VacantId.from_verify_key(other_vk)
    store = InMemoryReplayStore()
    server = VacantAsMCPServer(
        self_form=target_form,
        self_signing_key=target_sk,
        behavior=_ack_behavior,
        replay_store=store,
    )
    caller_sk, caller_vk = keygen()
    env = _envelope(sk=caller_sk, frm=VacantId.from_verify_key(caller_vk), to=other_vid)
    out = await server.call_tool("vacant_call", {"envelope": to_a2a_jsonrpc(env)})
    assert "error" in out
    assert "to_mismatch" in out["error"] or "envelope_to_mismatch" in out["error"]
    _ = target_vid


def _silence_unused() -> None:
    _ = (datetime, UTC, Any)
