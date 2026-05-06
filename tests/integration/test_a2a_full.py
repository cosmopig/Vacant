"""End-to-end A2A: two vacants, one calls the other, both chains advance.

This test verifies the dispatch acceptance criterion: dispatch never
routes through the registry. The test wires a fake registry whose
search records every call; after the test we assert the fake registry
saw exactly one search call and zero relay attempts.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

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
    VacantEnvelope,
    build_a2a_app,
    call_capability,
    call_local,
)

pytestmark = pytest.mark.slow


def _make(*, capability: str = "translate") -> tuple[Any, ResidentForm]:
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    bundle = BehaviorBundle(system_prompt="x")
    spec = SubstrateSpec(allowed_substrates=["mock"])
    lb = Logbook()
    lb.append("genesis", {}, sk)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text=capability,
        substrate_spec=spec,
        endpoint=f"http://test/{vid.short()}",
    ).signed(sk)
    form = ResidentForm(
        identity=vid,
        logbook=lb,
        behavior_bundle=bundle,
        substrate_spec=spec,
        runtime_state=VacantState.ACTIVE,
        capability_card=card,
    )
    return sk, form


@pytest.mark.asyncio
async def test_two_vacants_a_calls_b_chains_advance_no_registry_relay() -> None:
    a_sk, a_form = _make()
    b_sk, b_form = _make()

    # B's serve app + replay store.
    b_store = InMemoryReplayStore()

    async def b_behavior(env: VacantEnvelope) -> A2AMessage:
        return A2AMessage(
            role="ROLE_AGENT",
            parts=[A2APart(text=f"B says hello to {env.from_vacant_id.short()}")],
        )

    b_app = build_a2a_app(
        self_form=b_form,
        self_signing_key=b_sk,
        behavior=b_behavior,
        replay_store=b_store,
    )

    # In-process transport pinning to B's app.
    b_transport_obj = ASGITransport(app=b_app)
    b_client = AsyncClient(transport=b_transport_obj, base_url="http://test")

    async def transport(url: str, body: dict[str, Any]) -> dict[str, Any]:
        # Acceptance check: URL must equal B's published endpoint, NOT
        # any registry URL.
        assert url == b_form.capability_card.endpoint
        # Strip the host prefix for the in-process client.
        path = "/a2a/message/send"
        r = await b_client.post(path, json=body)
        return r.json()

    # Fake registry that just records lookups.
    registry_log: list[dict[str, Any]] = []

    async def registry_search(*, query, include_local, limit):  # type: ignore[no-untyped-def]
        registry_log.append({"op": "search", "query": query})
        return [b_form.capability_card]

    try:
        result = await call_capability(
            "translate",
            requester=a_form,
            requester_signing_key=a_sk,
            payload=A2AMessage(parts=[A2APart(text="please translate")]),
            transport=transport,
            aggregation_search=registry_search,
        )
    finally:
        await b_client.aclose()

    # Response signed by B and verifies under B's pubkey.
    assert result.response_envelope.verify(b_form.identity.verify_key()) is True

    # Registry was queried exactly ONCE for discovery, with zero relay calls.
    assert len(registry_log) == 1
    assert registry_log[0]["op"] == "search"

    # B's replay store advanced on both directions:
    # - (A → B) chain at seq=1 from A's request
    # - (B → A) chain at seq=1 from B's response
    from vacant.protocol import PairKey

    a_to_b = await b_store.get(PairKey(from_vid=a_form.identity, to_vid=b_form.identity))
    b_to_a = await b_store.get(PairKey(from_vid=b_form.identity, to_vid=a_form.identity))
    assert a_to_b.last_sequence_no == 1
    assert b_to_a.last_sequence_no == 1


@pytest.mark.asyncio
async def test_call_local_against_local_state_vacant() -> None:
    """LOCAL vacants are unreachable via public dispatch but reachable via call_local."""
    a_sk, a_form = _make()
    b_sk, b_form_active = _make(capability="local-thing")

    # Make B LOCAL; rebuild app accordingly.
    b_form = b_form_active.model_copy(update={"runtime_state": VacantState.LOCAL})

    b_store = InMemoryReplayStore()

    async def b_behavior(env: VacantEnvelope) -> A2AMessage:
        return A2AMessage(role="ROLE_AGENT", parts=[A2APart(text="local hi")])

    b_app = build_a2a_app(
        self_form=b_form,
        self_signing_key=b_sk,
        behavior=b_behavior,
        replay_store=b_store,
    )
    b_client = AsyncClient(transport=ASGITransport(app=b_app), base_url="http://test")

    async def transport(url: str, body: dict[str, Any]) -> dict[str, Any]:
        r = await b_client.post("/a2a/message/send", json=body)
        return r.json()

    try:
        # call_local goes direct, even against LOCAL state.
        result = await call_local(
            target_card=b_form.capability_card,
            requester=a_form,
            requester_signing_key=a_sk,
            payload=A2AMessage(parts=[A2APart(text="hi")]),
            transport=transport,
        )
        assert result.response_envelope.verify(b_form.identity.verify_key()) is True
    finally:
        await b_client.aclose()
