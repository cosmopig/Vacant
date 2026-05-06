"""Outgoing-call dispatch tests."""

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
    A2A_VACANT_METADATA_KEY,
    A2AMessage,
    A2APart,
    DispatchResult,
    TargetNotFoundError,
    call_capability,
    call_local,
    to_a2a_jsonrpc,
)


def _build_form_and_card(*, endpoint: str | None = "https://x.example/a2a"):  # type: ignore[no-untyped-def]
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    bundle = BehaviorBundle(system_prompt="be honest")
    spec = SubstrateSpec(allowed_substrates=["mock"])
    lb = Logbook()
    lb.append("genesis", {}, sk)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text="translate",
        substrate_spec=spec,
        endpoint=endpoint,
    ).signed(sk)
    form = ResidentForm(
        identity=vid,
        logbook=lb,
        behavior_bundle=bundle,
        substrate_spec=spec,
        runtime_state=VacantState.ACTIVE,
        capability_card=card,
    )
    return sk, vid, card, form


# --- transports -----------------------------------------------------------


def _make_echo_transport(target_signing_key, target_vid):  # type: ignore[no-untyped-def]
    """Build a transport that echoes the request payload back signed by the target.

    This simulates a legitimate target that ack's the call.
    """
    from vacant.protocol.envelope import VacantEnvelope, from_a2a_jsonrpc

    async def transport(url: str, body: dict[str, Any]) -> dict[str, Any]:
        request = from_a2a_jsonrpc(body)
        # Build a response envelope from target -> caller, seq=1.
        response = VacantEnvelope(
            from_vacant_id=target_vid,
            to_vacant_id=request.from_vacant_id,
            sequence_no=1,
            timestamp=datetime.now(UTC),
            payload=A2AMessage(parts=[A2APart(text=f"echo: {request.payload.parts[0].text}")]),
        ).signed(target_signing_key)
        wire = to_a2a_jsonrpc(response)
        return {"jsonrpc": "2.0", "id": "rsp", "result": {"message": wire["params"]["message"]}}

    return transport


# --- call_local ------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_local_round_trip() -> None:
    target_sk, target_vid, target_card, _target_form = _build_form_and_card()
    requester_sk, _r_vid, _r_card, requester_form = _build_form_and_card(
        endpoint="https://r.example/a2a"
    )
    transport = _make_echo_transport(target_sk, target_vid)
    payload = A2AMessage(parts=[A2APart(text="hello world")])
    result = await call_local(
        target_card=target_card,
        requester=requester_form,
        requester_signing_key=requester_sk,
        payload=payload,
        transport=transport,
    )
    assert isinstance(result, DispatchResult)
    assert result.response_envelope.payload.parts[0].text.startswith("echo: hello world")
    # Response envelope verifies under target's pubkey.
    assert result.response_envelope.verify(target_vid.verify_key()) is True


@pytest.mark.asyncio
async def test_call_local_rejects_card_with_no_endpoint() -> None:
    _t_sk, _t_vid, target_card, _ = _build_form_and_card(endpoint=None)
    requester_sk, _r_vid, _r_card, requester_form = _build_form_and_card()

    async def noop_transport(url: str, body: dict[str, Any]) -> dict[str, Any]:
        return {}

    with pytest.raises(TargetNotFoundError):
        await call_local(
            target_card=target_card,
            requester=requester_form,
            requester_signing_key=requester_sk,
            payload=A2AMessage(parts=[A2APart(text="x")]),
            transport=noop_transport,
        )


@pytest.mark.asyncio
async def test_call_local_rejects_unsigned_target_card() -> None:
    _t_sk, t_vid, _, _ = _build_form_and_card()
    bad_card = CapabilityCard(
        vacant_id=t_vid,
        capability_text="x",
        substrate_spec=SubstrateSpec(),
        endpoint="https://x.example/a2a",
    )
    requester_sk, _r_vid, _r_card, requester_form = _build_form_and_card()

    async def noop_transport(url: str, body: dict[str, Any]) -> dict[str, Any]:
        return {}

    from vacant.protocol.errors import EnvelopeSignatureError

    with pytest.raises(EnvelopeSignatureError):
        await call_local(
            target_card=bad_card,
            requester=requester_form,
            requester_signing_key=requester_sk,
            payload=A2AMessage(parts=[A2APart(text="x")]),
            transport=noop_transport,
        )


# --- call_capability + LOCAL exclusion -------------------------------------


@pytest.mark.asyncio
async def test_call_capability_uses_aggregation_then_dispatches_directly() -> None:
    target_sk, target_vid, target_card, _ = _build_form_and_card()
    requester_sk, _r_vid, _r_card, requester_form = _build_form_and_card()
    transport = _make_echo_transport(target_sk, target_vid)

    aggregation_calls: list[dict[str, Any]] = []

    async def fake_aggregation(*, query, include_local, limit):  # type: ignore[no-untyped-def]
        aggregation_calls.append({"query": query, "include_local": include_local, "limit": limit})
        return [target_card]  # search returns the card directly (test-stub shape)

    result = await call_capability(
        "translate",
        requester=requester_form,
        requester_signing_key=requester_sk,
        payload=A2AMessage(parts=[A2APart(text="hi")]),
        transport=transport,
        aggregation_search=fake_aggregation,
    )
    # Aggregation was queried for discovery only.
    assert len(aggregation_calls) == 1
    assert aggregation_calls[0]["include_local"] is False
    # Response signed by target; envelope went DIRECT, not via registry.
    assert result.response_envelope.verify(target_vid.verify_key()) is True


@pytest.mark.asyncio
async def test_call_capability_local_excluded_from_search() -> None:
    """LOCAL halos must not be returned to public dispatch."""
    requester_sk, _r_vid, _r_card, requester_form = _build_form_and_card()

    async def fake_aggregation(*, query, include_local, limit):  # type: ignore[no-untyped-def]
        # Honest aggregation returns no LOCAL halos when include_local=False.
        if include_local is False:
            return []
        return [...]

    async def noop_transport(url, body):  # type: ignore[no-untyped-def]
        return {}

    with pytest.raises(TargetNotFoundError):
        await call_capability(
            "translate",
            requester=requester_form,
            requester_signing_key=requester_sk,
            payload=A2AMessage(parts=[A2APart(text="x")]),
            transport=noop_transport,
            aggregation_search=fake_aggregation,
        )


@pytest.mark.asyncio
async def test_call_capability_picks_ucb_winner_via_oracle() -> None:
    target_sk_a, t_vid_a, t_card_a, _ = _build_form_and_card(endpoint="https://a.example/a2a")
    target_sk_b, t_vid_b, t_card_b, _ = _build_form_and_card(endpoint="https://b.example/a2a")
    requester_sk, _r_vid, _r_card, requester_form = _build_form_and_card()

    async def aggregation(*, query, include_local, limit):  # type: ignore[no-untyped-def]
        return [t_card_a, t_card_b]

    class FavorBOracle:
        async def score(self, vacant_id, dimensions) -> float:  # type: ignore[no-untyped-def]
            return 1.0 if vacant_id == t_vid_b.hex() else 0.0

    async def transport(url, body):  # type: ignore[no-untyped-def]
        # Verify the URL is B's.
        assert url == t_card_b.endpoint
        return _build_response(target_sk_b, t_vid_b, body)

    await call_capability(
        "translate",
        requester=requester_form,
        requester_signing_key=requester_sk,
        payload=A2AMessage(parts=[A2APart(text="x")]),
        transport=transport,
        aggregation_search=aggregation,
        reputation_oracle=FavorBOracle(),
    )
    _ = (target_sk_a, t_vid_a)


@pytest.mark.asyncio
async def test_call_capability_no_match_raises() -> None:
    requester_sk, _r_vid, _r_card, requester_form = _build_form_and_card()

    async def empty_aggregation(*, query, include_local, limit):  # type: ignore[no-untyped-def]
        return []

    async def noop(url, body):  # type: ignore[no-untyped-def]
        return {}

    with pytest.raises(TargetNotFoundError):
        await call_capability(
            "missing",
            requester=requester_form,
            requester_signing_key=requester_sk,
            payload=A2AMessage(parts=[A2APart(text="x")]),
            transport=noop,
            aggregation_search=empty_aggregation,
        )


@pytest.mark.asyncio
async def test_call_capability_aggregation_search_required() -> None:
    requester_sk, _r_vid, _r_card, requester_form = _build_form_and_card()

    async def noop(url, body):  # type: ignore[no-untyped-def]
        return {}

    with pytest.raises(TargetNotFoundError):
        await call_capability(
            "x",
            requester=requester_form,
            requester_signing_key=requester_sk,
            payload=A2AMessage(parts=[A2APart(text="x")]),
            transport=noop,
            aggregation_search=None,
        )


# --- A2A wire shape sanity ------------------------------------------------


@pytest.mark.asyncio
async def test_dispatched_envelope_carries_vacant_metadata() -> None:
    target_sk, target_vid, target_card, _ = _build_form_and_card()
    requester_sk, _r_vid, _r_card, requester_form = _build_form_and_card()
    captured: dict[str, Any] = {}

    async def capture_transport(url: str, body: dict[str, Any]) -> dict[str, Any]:
        captured["body"] = body
        return _build_response(target_sk, target_vid, body)

    await call_local(
        target_card=target_card,
        requester=requester_form,
        requester_signing_key=requester_sk,
        payload=A2AMessage(parts=[A2APart(text="x")]),
        transport=capture_transport,
    )
    body = captured["body"]
    meta = body["params"]["message"]["metadata"][A2A_VACANT_METADATA_KEY]
    assert meta["from_vacant_id"] == requester_form.identity.hex()
    assert meta["to_vacant_id"] == target_vid.hex()


# --- helpers ---------------------------------------------------------------


def _build_response(target_sk, target_vid, request_body):  # type: ignore[no-untyped-def]
    from vacant.protocol.envelope import VacantEnvelope, from_a2a_jsonrpc

    request = from_a2a_jsonrpc(request_body)
    response = VacantEnvelope(
        from_vacant_id=target_vid,
        to_vacant_id=request.from_vacant_id,
        sequence_no=1,
        timestamp=datetime.now(UTC),
        payload=A2AMessage(parts=[A2APart(text="ack")]),
    ).signed(target_sk)
    wire = to_a2a_jsonrpc(response)
    return {"jsonrpc": "2.0", "id": "rsp", "result": {"message": wire["params"]["message"]}}
