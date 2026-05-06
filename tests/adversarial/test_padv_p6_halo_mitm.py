"""Padv P6 -- halo-to-direct call MITM (D009 / dispatch §"Halo-to-direct call mismatch").

Spec anchors:
- `architecture/components/P6_protocol.md` §3 (direct dispatch never relays via registry)
- `architecture/decisions/D009_p6_protocol_reconciliation.md` §C
- `dispatch/Padv_review.md` §"P6 Protocol attacks to consider"

The defense is layered:
- The capability card's signed payload covers `endpoint`, so an attacker
  cannot rewrite the endpoint without invalidating the card signature.
- The response envelope must be signed by `target_card.vacant_id`'s
  pubkey, NOT by whatever key terminates the network connection. So
  even if an attacker hijacks the URL host (DNS / TLS pinning failure),
  they cannot produce a response that verifies under the target's key.
"""

from __future__ import annotations

import json
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
    call_local,
    deserialize,
    serialize,
)


def _build_form(*, endpoint: str = "https://victim.example/a2a"):  # type: ignore[no-untyped-def]
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    bundle = BehaviorBundle(system_prompt="x")
    spec = SubstrateSpec(allowed_substrates=["mock"])
    lb = Logbook()
    lb.append("genesis", {}, sk)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text="translate",
        substrate_spec=spec,
        endpoint=endpoint,
    ).signed(sk)
    return (
        sk,
        vid,
        card,
        ResidentForm(
            identity=vid,
            logbook=lb,
            behavior_bundle=bundle,
            substrate_spec=spec,
            runtime_state=VacantState.ACTIVE,
            capability_card=card,
        ),
    )


# --- Attack 1: rewrite endpoint after victim signed the halo --------------
# Defense (P): endpoint is in the capability card's signed payload, so
# tampering breaks `card.verify()`.


def test_attack_endpoint_rewrite_after_sign_breaks_card_signature() -> None:
    _sk, _vid, victim_card, _form = _build_form(endpoint="https://victim.example/a2a")
    blob = serialize(victim_card)
    obj = json.loads(blob.decode())
    obj["endpoint"] = "https://attacker.example/a2a"
    tampered_blob = json.dumps(obj).encode()
    parsed = deserialize(tampered_blob)
    assert parsed.endpoint == "https://attacker.example/a2a"
    # Card no longer verifies under the victim's signature.
    assert parsed.verify() is False


# --- Attack 2: MITM at the URL serves a response signed by the attacker ---
# Defense (P): `call_local` verifies the response envelope under
# `target_card.vacant_id`'s pubkey, not the URL host's TLS cert. The
# attacker has no access to the victim's signing key, so the response
# fails verification.


@pytest.mark.asyncio
async def test_attack_mitm_response_signed_by_attacker_rejected() -> None:
    """Discovery returns victim's signed halo (endpoint URL = victim's URL),
    but at network time the request reaches an attacker-controlled host
    that responds with an envelope signed under the attacker's key.
    The dispatcher rejects it because the response sig doesn't verify
    under the target's vacant_id."""
    _victim_sk, victim_vid, victim_card, _victim_form = _build_form()
    attacker_sk, attacker_vk = keygen()
    attacker_vid = VacantId.from_verify_key(attacker_vk)
    requester_sk, _r_vid, _r_card, requester_form = _build_form(
        endpoint="https://requester.example/a2a"
    )

    from datetime import UTC, datetime

    from vacant.protocol import VacantEnvelope, to_a2a_jsonrpc

    async def attacker_transport(url: str, body: dict[str, Any]) -> dict[str, Any]:
        # Attacker cannot sign as victim, so they sign with their own key.
        # The response envelope claims to be from victim_vid (so the
        # dispatcher's `verify(target_card.vacant_id.verify_key())`
        # rejects the response as forged).
        from vacant.protocol.envelope import from_a2a_jsonrpc

        request = from_a2a_jsonrpc(body)
        # Build a response: claim to be from victim_vid but sign with attacker_sk.
        response = VacantEnvelope(
            from_vacant_id=victim_vid,
            to_vacant_id=request.from_vacant_id,
            sequence_no=1,
            timestamp=datetime.now(UTC),
            payload=A2AMessage(parts=[A2APart(text="malicious response")]),
        ).signed(attacker_sk)
        wire = to_a2a_jsonrpc(response)
        return {
            "jsonrpc": "2.0",
            "id": "rsp",
            "result": {"message": wire["params"]["message"]},
        }

    with pytest.raises(EnvelopeSignatureError):
        await call_local(
            target_card=victim_card,
            requester=requester_form,
            requester_signing_key=requester_sk,
            payload=A2AMessage(parts=[A2APart(text="x")]),
            transport=attacker_transport,
        )
    _ = attacker_vid


# --- Attack 3: attacker substitutes their own from_vacant_id in response --
# Defense (P): the dispatcher verifies the response under
# `target_card.vacant_id.verify_key()` -- the response's from_vacant_id
# field doesn't matter, only what verifies under the *expected* pubkey.


@pytest.mark.asyncio
async def test_attack_response_with_attacker_from_id_rejected() -> None:
    """Attacker MITMs and returns a response with from_vacant_id set to
    attacker's own id, signed by attacker's key. Dispatcher rejects: the
    response key check uses the *target card's* pubkey, not the
    response's claimed sender."""
    _victim_sk, _victim_vid, victim_card, _victim_form = _build_form()
    attacker_sk, attacker_vk = keygen()
    attacker_vid = VacantId.from_verify_key(attacker_vk)
    requester_sk, _r_vid, _r_card, requester_form = _build_form(
        endpoint="https://requester.example/a2a"
    )

    from datetime import UTC, datetime

    from vacant.protocol import VacantEnvelope, to_a2a_jsonrpc

    async def attacker_transport(url: str, body: dict[str, Any]) -> dict[str, Any]:
        from vacant.protocol.envelope import from_a2a_jsonrpc

        request = from_a2a_jsonrpc(body)
        # Attacker now claims to be themselves in the response, with valid sig
        # under their own key. Dispatcher still rejects because it verifies
        # under the *target_card.vacant_id*'s pubkey, not the response's
        # from_vacant_id.
        response = VacantEnvelope(
            from_vacant_id=attacker_vid,
            to_vacant_id=request.from_vacant_id,
            sequence_no=1,
            timestamp=datetime.now(UTC),
            payload=A2AMessage(parts=[A2APart(text="hi from attacker")]),
        ).signed(attacker_sk)
        wire = to_a2a_jsonrpc(response)
        return {
            "jsonrpc": "2.0",
            "id": "rsp",
            "result": {"message": wire["params"]["message"]},
        }

    with pytest.raises(EnvelopeSignatureError):
        await call_local(
            target_card=victim_card,
            requester=requester_form,
            requester_signing_key=requester_sk,
            payload=A2AMessage(parts=[A2APart(text="x")]),
            transport=attacker_transport,
        )


# --- Attack 4: unsigned target capability card rejected at dispatch entry -
# Defense (P): `call_local` calls `target_card.verify()` before issuing
# any request -- attacker who fabricates a card with no signature
# cannot trick a requester into sending a payload to attacker's URL.


@pytest.mark.asyncio
async def test_attack_unsigned_capability_card_rejected() -> None:
    _sk, vid, _card, _form = _build_form()
    requester_sk, _r_vid, _r_card, requester_form = _build_form()
    fake_card = CapabilityCard(
        vacant_id=vid,
        capability_text="x",
        substrate_spec=SubstrateSpec(),
        endpoint="https://attacker.example/a2a",
    )

    posted: list[str] = []

    async def watching_transport(url: str, body: dict[str, Any]) -> dict[str, Any]:
        posted.append(url)
        return {}

    with pytest.raises(EnvelopeSignatureError):
        await call_local(
            target_card=fake_card,
            requester=requester_form,
            requester_signing_key=requester_sk,
            payload=A2AMessage(parts=[A2APart(text="x")]),
            transport=watching_transport,
        )
    # Crucially: no request was POSTed -- the dispatcher refused the card
    # before reaching the network.
    assert posted == []
