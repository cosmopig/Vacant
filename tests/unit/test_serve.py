"""serve.py — incoming A2A router tests."""

from __future__ import annotations

from datetime import UTC, datetime

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
    InMemoryReplayStore,
    VacantEnvelope,
    build_a2a_app,
    to_a2a_jsonrpc,
)


def _form(state: VacantState = VacantState.ACTIVE):  # type: ignore[no-untyped-def]
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


async def _echo_behavior(env: VacantEnvelope) -> A2AMessage:
    return A2AMessage(
        role="ROLE_AGENT",
        parts=[A2APart(text=f"echo: {env.payload.parts[0].text}")],
    )


@pytest_asyncio.fixture
async def serve_client():  # type: ignore[no-untyped-def]
    sk, form = _form()
    store = InMemoryReplayStore()
    app = build_a2a_app(
        self_form=form,
        self_signing_key=sk,
        behavior=_echo_behavior,
        replay_store=store,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, sk, form, store


def _signed_request(*, caller_sk, caller_vid, target_vid, seq=1, prev=EMPTY_PREV_HASH):  # type: ignore[no-untyped-def]
    env = VacantEnvelope(
        from_vacant_id=caller_vid,
        to_vacant_id=target_vid,
        sequence_no=seq,
        timestamp=datetime(2026, 5, 6, tzinfo=UTC),
        prev_envelope_hash=prev,
        payload=A2AMessage(parts=[A2APart(text="hello")]),
    ).signed(caller_sk)
    return env


@pytest.mark.asyncio
async def test_serve_accepts_signed_envelope(serve_client) -> None:  # type: ignore[no-untyped-def]
    ac, _self_sk, self_form, _ = serve_client
    caller_sk, caller_vk = keygen()
    caller_vid = VacantId.from_verify_key(caller_vk)
    env = _signed_request(caller_sk=caller_sk, caller_vid=caller_vid, target_vid=self_form.identity)
    resp = await ac.post("/a2a/message/send", json=to_a2a_jsonrpc(env))
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["message"]["parts"][0]["text"].startswith("echo: hello")


@pytest.mark.asyncio
async def test_serve_rejects_bad_signature(serve_client) -> None:  # type: ignore[no-untyped-def]
    ac, _self_sk, self_form, _ = serve_client
    caller_sk, caller_vk = keygen()
    caller_vid = VacantId.from_verify_key(caller_vk)
    env = _signed_request(caller_sk=caller_sk, caller_vid=caller_vid, target_vid=self_form.identity)
    body = to_a2a_jsonrpc(env)
    # Tamper one byte of the signature.
    meta = body["params"]["message"]["metadata"]["urn:vacant:v1"]
    sig_bytes = bytearray.fromhex(meta["caller_signature"])
    sig_bytes[0] ^= 0xFF
    meta["caller_signature"] = sig_bytes.hex()
    resp = await ac.post("/a2a/message/send", json=body)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_serve_rejects_misdirected_envelope(serve_client) -> None:  # type: ignore[no-untyped-def]
    ac, _self_sk, _self_form, _ = serve_client
    caller_sk, caller_vk = keygen()
    other_sk, other_vk = keygen()
    other_vid = VacantId.from_verify_key(other_vk)
    env = _signed_request(
        caller_sk=caller_sk,
        caller_vid=VacantId.from_verify_key(caller_vk),
        target_vid=other_vid,  # NOT this server
    )
    resp = await ac.post("/a2a/message/send", json=to_a2a_jsonrpc(env))
    assert resp.status_code == 421
    _ = other_sk


@pytest.mark.asyncio
async def test_serve_replay_returns_409(serve_client) -> None:  # type: ignore[no-untyped-def]
    ac, _self_sk, self_form, _store = serve_client
    caller_sk, caller_vk = keygen()
    caller_vid = VacantId.from_verify_key(caller_vk)
    env = _signed_request(caller_sk=caller_sk, caller_vid=caller_vid, target_vid=self_form.identity)
    # First call accepted.
    r1 = await ac.post("/a2a/message/send", json=to_a2a_jsonrpc(env))
    assert r1.status_code == 200
    # Replay → 409.
    r2 = await ac.post("/a2a/message/send", json=to_a2a_jsonrpc(env))
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_serve_sunk_returns_410() -> None:
    sk, form = _form(state=VacantState.SUNK)
    store = InMemoryReplayStore()
    app = build_a2a_app(
        self_form=form, self_signing_key=sk, behavior=_echo_behavior, replay_store=store
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        caller_sk, caller_vk = keygen()
        env = _signed_request(
            caller_sk=caller_sk,
            caller_vid=VacantId.from_verify_key(caller_vk),
            target_vid=form.identity,
        )
        r = await ac.post("/a2a/message/send", json=to_a2a_jsonrpc(env))
        assert r.status_code == 410


@pytest.mark.asyncio
async def test_serve_archived_returns_410() -> None:
    sk, form = _form(state=VacantState.ARCHIVED)
    store = InMemoryReplayStore()
    app = build_a2a_app(
        self_form=form, self_signing_key=sk, behavior=_echo_behavior, replay_store=store
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        caller_sk, caller_vk = keygen()
        env = _signed_request(
            caller_sk=caller_sk,
            caller_vid=VacantId.from_verify_key(caller_vk),
            target_vid=form.identity,
        )
        r = await ac.post("/a2a/message/send", json=to_a2a_jsonrpc(env))
        assert r.status_code == 410


@pytest.mark.asyncio
async def test_serve_hibernating_returns_423() -> None:
    sk, form = _form(state=VacantState.HIBERNATING)
    store = InMemoryReplayStore()
    app = build_a2a_app(
        self_form=form, self_signing_key=sk, behavior=_echo_behavior, replay_store=store
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        caller_sk, caller_vk = keygen()
        env = _signed_request(
            caller_sk=caller_sk,
            caller_vid=VacantId.from_verify_key(caller_vk),
            target_vid=form.identity,
        )
        r = await ac.post("/a2a/message/send", json=to_a2a_jsonrpc(env))
        assert r.status_code == 423


@pytest.mark.asyncio
async def test_serve_malformed_envelope_returns_400(serve_client) -> None:  # type: ignore[no-untyped-def]
    ac, _self_sk, _self_form, _ = serve_client
    resp = await ac.post(
        "/a2a/message/send",
        json={"jsonrpc": "2.0", "id": "x", "method": "message/send", "params": {"message": {}}},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_serve_rejects_missing_jsonrpc_field(serve_client) -> None:  # type: ignore[no-untyped-def]
    """F3: spec requires `jsonrpc: "2.0"` envelope."""
    ac, _self_sk, _self_form, _ = serve_client
    resp = await ac.post(
        "/a2a/message/send",
        json={"id": "x", "method": "message/send", "params": {"message": {}}},
    )
    assert resp.status_code == 400
    assert "jsonrpc" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_serve_rejects_wrong_jsonrpc_version(serve_client) -> None:  # type: ignore[no-untyped-def]
    """F3: jsonrpc must be exactly '2.0'."""
    ac, _self_sk, _self_form, _ = serve_client
    resp = await ac.post(
        "/a2a/message/send",
        json={"jsonrpc": "1.0", "id": "x", "method": "message/send", "params": {"message": {}}},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_serve_rejects_wrong_method(serve_client) -> None:  # type: ignore[no-untyped-def]
    """F3: method must be 'message/send'."""
    ac, _self_sk, _self_form, _ = serve_client
    resp = await ac.post(
        "/a2a/message/send",
        json={"jsonrpc": "2.0", "id": "x", "method": "tools/call", "params": {"message": {}}},
    )
    assert resp.status_code == 400
    assert "method" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_serve_rejects_non_json_content_type(serve_client) -> None:  # type: ignore[no-untyped-def]
    """F3: only application/json envelopes accepted."""
    ac, _self_sk, _self_form, _ = serve_client
    resp = await ac.post(
        "/a2a/message/send",
        content=b"plain text body",
        headers={"content-type": "text/plain"},
    )
    # FastAPI itself rejects non-JSON bodies parsed as dict; we should
    # surface either 415 (our explicit guard) or 422 (FastAPI's parse).
    assert resp.status_code in (415, 422)
