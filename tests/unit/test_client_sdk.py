"""C9 — `vacant.client` caller SDK.

Tests:
- Ephemeral client constructs without crashing.
- `call_local(target_card, prompt)` works against an in-process behavior
  stub through `protocol.serve.build_a2a_app` + an `httpx.MockTransport`-
  backed transport.
- SelfEval round-trips on the response.
- Missing aggregation_search → `VacantClientError` from `call_capability`.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

from vacant.client import (
    HttpDispatchTransport,
    VacantCallResult,
    VacantClient,
    VacantClientError,
)
from vacant.core.crypto import SigningKey, VerifyKey, keygen
from vacant.core.types import (
    BehaviorBundle,
    CapabilityCard,
    Logbook,
    ResidentForm,
    SubstrateSpec,
    VacantId,
    VacantState,
)
from vacant.protocol.envelope import A2AMessage, A2APart, SelfEval, VacantEnvelope
from vacant.protocol.replay_protect import InMemoryReplayStore
from vacant.protocol.serve import build_a2a_app


async def _echoing_behavior(env: VacantEnvelope) -> A2AMessage:
    """Behavior that echoes the user prompt + attaches a SelfEval the
    SDK can read back."""
    user_text = "".join(p.text for p in env.payload.parts if p.type == "text")
    return A2AMessage(
        role="ROLE_AGENT",
        parts=[A2APart(type="text", text=f"echo: {user_text}")],
        self_eval=SelfEval(factual=0.9, logical=0.8, confidence=0.7),
    )


def _make_server() -> tuple[FastAPI, ResidentForm, SigningKey]:
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    form = ResidentForm(
        identity=vid,
        logbook=Logbook(),
        behavior_bundle=BehaviorBundle(system_prompt="echo"),
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
        capability_card=CapabilityCard(
            vacant_id=vid,
            capability_text="echo",
            substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
            endpoint="http://test.local/a2a/message/send",
        ).signed(sk),
        runtime_state=VacantState.ACTIVE,
    )
    app = build_a2a_app(
        self_form=form,
        self_signing_key=sk,
        behavior=_echoing_behavior,
        replay_store=InMemoryReplayStore(),
    )
    return app, form, sk


def test_ephemeral_client_constructs() -> None:
    cli = VacantClient.ephemeral()
    assert cli.client_vacant_id is not None


@pytest.mark.asyncio
async def test_call_capability_without_registry_raises() -> None:
    cli = VacantClient.ephemeral()
    with pytest.raises(VacantClientError):
        await cli.call_capability("anything", "hi")
    await cli.aclose()


@pytest.mark.asyncio
async def test_call_local_round_trip_through_asgi() -> None:
    """End-to-end: SDK → A2A POST → in-process behavior → response with
    SelfEval. Uses `httpx.ASGITransport` so we never touch a real socket."""
    app, server_form, _server_sk = _make_server()

    transport_http = httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test.local"
    )
    sdk_transport = HttpDispatchTransport(client=transport_http)

    cli = VacantClient.ephemeral(transport=sdk_transport)
    assert server_form.capability_card is not None
    result = await cli.call_local(server_form.capability_card, "hello world")

    assert isinstance(result, VacantCallResult)
    assert result.response_text == "echo: hello world"
    assert result.self_eval is not None
    assert result.self_eval.factual == pytest.approx(0.9)
    assert result.self_eval.confidence == pytest.approx(0.7)
    assert result.target_vacant_id == server_form.identity

    await transport_http.aclose()


@pytest.mark.asyncio
async def test_sdk_can_send_self_eval_on_request() -> None:
    """Clients that *are* themselves vacants can attach their own
    SelfEval; the server-side behavior receives the envelope with it
    present (the in-process echo doesn't act on it, but the transport
    layer must preserve it through signing + parsing)."""
    received_envs: list[VacantEnvelope] = []

    async def _capture_behavior(env: VacantEnvelope) -> A2AMessage:
        received_envs.append(env)
        return A2AMessage(
            role="ROLE_AGENT",
            parts=[A2APart(type="text", text="ok")],
        )

    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    form = ResidentForm(
        identity=vid,
        logbook=Logbook(),
        behavior_bundle=BehaviorBundle(system_prompt="capture"),
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
        capability_card=CapabilityCard(
            vacant_id=vid,
            capability_text="capture",
            substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
            endpoint="http://test.local/a2a/message/send",
        ).signed(sk),
        runtime_state=VacantState.ACTIVE,
    )
    app = build_a2a_app(
        self_form=form,
        self_signing_key=sk,
        behavior=_capture_behavior,
        replay_store=InMemoryReplayStore(),
    )

    transport_http = httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test.local"
    )
    sdk_transport = HttpDispatchTransport(client=transport_http)
    cli = VacantClient.ephemeral(transport=sdk_transport)
    assert form.capability_card is not None

    se = SelfEval(factual=0.3, confidence=0.2)
    await cli.call_local(form.capability_card, "ping", self_eval=se)
    assert len(received_envs) == 1
    assert received_envs[0].payload.self_eval == se

    await transport_http.aclose()


_ = VerifyKey  # keep ruff happy on the type-only import
