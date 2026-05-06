"""MCP bridge integration: vacant exposed as MCP server is callable;
vacant calling MCP server records the call."""

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
    InMemoryReplayStore,
    MCPClientSubstrate,
    VacantAsMCPServer,
    VacantEnvelope,
    to_a2a_jsonrpc,
)
from vacant.substrate import SubstrateRequest

pytestmark = pytest.mark.slow


def _make():  # type: ignore[no-untyped-def]
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
            runtime_state=VacantState.ACTIVE,
            capability_card=card,
        ),
    )


@pytest.mark.asyncio
async def test_vacant_as_mcp_server_describe() -> None:
    sk, _vid, form = _make()
    store = InMemoryReplayStore()

    async def behavior(env: VacantEnvelope) -> A2AMessage:
        return A2AMessage(parts=[A2APart(text="ack")])

    server = VacantAsMCPServer(
        self_form=form,
        self_signing_key=sk,
        behavior=behavior,
        replay_store=store,
    )
    out = await server.call_tool("vacant_describe", {})
    assert out["vacant_id"] == form.identity.hex()
    assert out["capability_text"] == "echo"


@pytest.mark.asyncio
async def test_vacant_as_mcp_server_call_round_trip() -> None:
    target_sk, target_vid, target_form = _make()
    store = InMemoryReplayStore()

    async def echo_behavior(env: VacantEnvelope) -> A2AMessage:
        return A2AMessage(
            role="ROLE_AGENT",
            parts=[A2APart(text=f"echo: {env.payload.parts[0].text}")],
        )

    server = VacantAsMCPServer(
        self_form=target_form,
        self_signing_key=target_sk,
        behavior=echo_behavior,
        replay_store=store,
    )
    # Build a signed envelope from caller -> target.
    caller_sk, caller_vk = keygen()
    caller_vid = VacantId.from_verify_key(caller_vk)
    env = VacantEnvelope(
        from_vacant_id=caller_vid,
        to_vacant_id=target_vid,
        sequence_no=1,
        timestamp=datetime(2026, 5, 6, tzinfo=UTC),
        payload=A2AMessage(parts=[A2APart(text="hello")]),
    ).signed(caller_sk)
    out = await server.call_tool("vacant_call", {"envelope": to_a2a_jsonrpc(env)})
    assert "message" in out
    assert "echo: hello" in out["message"]["parts"][0]["text"]


@pytest.mark.asyncio
async def test_vacant_as_mcp_server_unknown_tool_returns_error() -> None:
    sk, _vid, form = _make()
    store = InMemoryReplayStore()

    async def behavior(env: VacantEnvelope) -> A2AMessage:
        return A2AMessage(parts=[A2APart(text="ack")])

    server = VacantAsMCPServer(
        self_form=form, self_signing_key=sk, behavior=behavior, replay_store=store
    )
    out = await server.call_tool("vacant_unknown", {})
    assert "error" in out


@pytest.mark.asyncio
async def test_vacant_as_mcp_server_misdirected_envelope_errors() -> None:
    sk, _vid, form = _make()
    other_sk, other_vk = keygen()
    other_vid = VacantId.from_verify_key(other_vk)
    store = InMemoryReplayStore()

    async def behavior(env: VacantEnvelope) -> A2AMessage:
        return A2AMessage(parts=[A2APart(text="ack")])

    server = VacantAsMCPServer(
        self_form=form, self_signing_key=sk, behavior=behavior, replay_store=store
    )
    caller_sk, caller_vk = keygen()
    env = VacantEnvelope(
        from_vacant_id=VacantId.from_verify_key(caller_vk),
        to_vacant_id=other_vid,  # not this server
        sequence_no=1,
        timestamp=datetime(2026, 5, 6, tzinfo=UTC),
        payload=A2AMessage(parts=[A2APart(text="x")]),
    ).signed(caller_sk)
    out = await server.call_tool("vacant_call", {"envelope": to_a2a_jsonrpc(env)})
    assert "error" in out
    _ = other_sk


@pytest.mark.asyncio
async def test_mcp_client_substrate_calls_through_transport() -> None:
    captured: dict[str, Any] = {}

    async def transport(url: str, body: dict[str, Any]) -> dict[str, Any]:
        captured["url"] = url
        captured["body"] = body
        return {"text": "translated text"}

    substrate = MCPClientSubstrate(
        server_url="http://mcp.example/v1",
        tool_name="translate",
        transport=transport,
    )
    response = await substrate.infer(
        SubstrateRequest(system_prompt="be precise", user_prompt="hello")
    )
    assert response.text == "translated text"
    assert response.model_id == "translate"
    assert captured["url"] == "http://mcp.example/v1"
    assert captured["body"]["method"] == "tools/call"
