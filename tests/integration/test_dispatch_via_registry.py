"""F3 regression: dispatch over the registry's `HaloMatch` carries the
signed capability card end-to-end (D015 §C).

Spec: registry lookup → `HaloMatch` → `dispatch.call_capability` → A2A
POST. The HTTP layer is mocked, but the `HaloMatch → CapabilityCard`
flow is real (no test-stub `CapabilityCard` is injected; the dispatch
must extract the card from the registry row via `capability_card_blob`).
"""

from __future__ import annotations

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
    VacantEnvelope,
    build_envelope,
    call_capability,
    from_a2a_jsonrpc,
    to_a2a_jsonrpc,
)
from vacant.registry import (
    RegistryStore,
    Visibility,
    publish_halo,
    search_capability,
)

pytestmark = pytest.mark.slow


async def _publish_target(store: RegistryStore, *, capability: str, endpoint: str) -> Any:
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text=capability,
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
        endpoint=endpoint,
    ).signed(sk)
    await publish_halo(
        store=store,
        card=card,
        runtime_state=VacantState.ACTIVE,
        signing_key=sk,
        base_model_family="mock",
        visibility=Visibility.PUBLIC,
    )
    return sk, vid, card


def _make_requester() -> tuple[Any, ResidentForm]:
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    lb = Logbook()
    lb.append("genesis", {}, sk)
    form = ResidentForm(
        identity=vid,
        logbook=lb,
        behavior_bundle=BehaviorBundle(system_prompt="x"),
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
        runtime_state=VacantState.ACTIVE,
    )
    return sk, form


@pytest.mark.asyncio
async def test_halo_match_carries_signed_card_end_to_end(
    registry_store: RegistryStore,
) -> None:
    target_sk, target_vid, target_card = await _publish_target(
        registry_store, capability="translate-zh", endpoint="http://target.test/v1"
    )
    req_sk, req_form = _make_requester()

    matches = await search_capability(store=registry_store, query="translate-zh")
    assert matches, "registry must surface the published target"
    m = matches[0]
    assert m.capability_card is not None, (
        "F3 regression: HaloMatch must carry the signed CapabilityCard "
        "(D015 §C). Without it dispatch cannot reach card.endpoint."
    )
    assert m.capability_card.endpoint == "http://target.test/v1"
    assert m.capability_card.verify(), "card signature must verify post-deserialize"

    posted_url: dict[str, str] = {}

    async def fake_transport(url: str, body: dict[str, Any]) -> dict[str, Any]:
        posted_url["url"] = url
        env = from_a2a_jsonrpc(body)
        response_payload = A2AMessage(role="ROLE_AGENT", parts=[A2APart(text="ok")])
        response_env = build_envelope(
            from_vid=target_vid,
            to_vid=env.from_vacant_id,
            payload=response_payload,
            sequence_no=env.sequence_no + 1,
            prev_envelope_hash=env.compute_hash(),
            signing_key=target_sk,
        )
        request_body = to_a2a_jsonrpc(response_env)
        return {
            "jsonrpc": "2.0",
            "id": body["id"],
            "result": {"message": request_body["params"]["message"]},
        }

    async def aggregation_search(**kwargs: Any) -> list[Any]:
        return await search_capability(store=registry_store, **kwargs)

    result = await call_capability(
        "translate-zh",
        requester=req_form,
        requester_signing_key=req_sk,
        payload=A2AMessage(role="ROLE_USER", parts=[A2APart(text="hi")]),
        transport=fake_transport,
        aggregation_search=aggregation_search,
    )
    assert posted_url["url"] == "http://target.test/v1", (
        "dispatch must POST to card.endpoint extracted from HaloMatch — not to the registry"
    )
    assert isinstance(result.response_envelope, VacantEnvelope)
    assert result.target.vacant_id == target_vid
    _ = target_card  # signature verified above on the deserialized copy
