"""FastAPI RPC surface tests — verifies the 25 endpoints + OpenAPI doc."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from vacant.core.crypto import keygen
from vacant.core.types import (
    CapabilityCard,
    SubstrateSpec,
    VacantId,
    VacantState,
)
from vacant.registry import (
    RegistryStore,
    build_app,
    publish_halo,
)


@pytest_asyncio.fixture
async def rpc_client(
    registry_store: RegistryStore,
) -> AsyncIterator[tuple[AsyncClient, RegistryStore]]:
    app = build_app(registry_store)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, registry_store


def test_app_has_25_v1_endpoints() -> None:
    """Acceptance: 25 RPC endpoints documented in OpenAPI."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    app = build_app(RegistryStore(engine))
    paths = {r.path for r in app.routes if getattr(r, "path", "").startswith("/v1/")}
    assert len(paths) == 25, sorted(paths)


@pytest.mark.asyncio
async def test_openapi_schema_lists_all_v1(
    rpc_client: tuple[AsyncClient, RegistryStore],
) -> None:
    ac, _ = rpc_client
    resp = await ac.get("/openapi.json")
    assert resp.status_code == 200
    spec = resp.json()
    v1_paths = [p for p in spec["paths"] if p.startswith("/v1/")]
    assert len(v1_paths) == 25


@pytest.mark.asyncio
async def test_get_capability_card_404_for_unknown(
    rpc_client: tuple[AsyncClient, RegistryStore],
) -> None:
    ac, _ = rpc_client
    resp = await ac.get("/v1/capability_card/" + "00" * 32)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_capability_card_returns_match_for_public(
    rpc_client: tuple[AsyncClient, RegistryStore],
) -> None:
    ac, store = rpc_client
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text="public-thing",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)
    await publish_halo(store=store, card=card, runtime_state=VacantState.ACTIVE, signing_key=sk)
    resp = await ac.get(f"/v1/capability_card/{vid.hex()}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["vacant_id"] == vid.hex()
    assert data["visibility"] == "PUBLIC"


@pytest.mark.asyncio
async def test_get_capability_card_403_for_local_stranger(
    rpc_client: tuple[AsyncClient, RegistryStore],
) -> None:
    ac, store = rpc_client
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text="x",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)
    await publish_halo(store=store, card=card, runtime_state=VacantState.LOCAL, signing_key=sk)
    resp = await ac.get(f"/v1/capability_card/{vid.hex()}")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_query_capability_returns_matches(
    rpc_client: tuple[AsyncClient, RegistryStore],
) -> None:
    ac, store = rpc_client
    sk, vk = keygen()
    card = CapabilityCard(
        vacant_id=VacantId.from_verify_key(vk),
        capability_text="legal-research",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)
    await publish_halo(store=store, card=card, runtime_state=VacantState.ACTIVE, signing_key=sk)
    resp = await ac.post("/v1/query_capability?capability=legal-research")
    assert resp.status_code == 200
    body = resp.json()
    assert body["matches"]
    assert "legal-research" in body["matches"][0]["declared_capabilities_json"]


@pytest.mark.asyncio
async def test_event_log_empty_for_unknown(
    rpc_client: tuple[AsyncClient, RegistryStore],
) -> None:
    ac, _ = rpc_client
    resp = await ac.get("/v1/event_log/" + "00" * 32)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_event_log_returns_register_event(
    rpc_client: tuple[AsyncClient, RegistryStore],
) -> None:
    ac, store = rpc_client
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text="x",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)
    await publish_halo(store=store, card=card, runtime_state=VacantState.ACTIVE, signing_key=sk)
    resp = await ac.get(f"/v1/event_log/{vid.hex()}")
    assert resp.status_code == 200
    rows = resp.json()
    assert any(r["event_type"] == "register" for r in rows)


@pytest.mark.asyncio
async def test_event_lookup_404_for_missing(
    rpc_client: tuple[AsyncClient, RegistryStore],
) -> None:
    ac, _ = rpc_client
    resp = await ac.get("/v1/event/9999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_lineage_404_for_unknown(
    rpc_client: tuple[AsyncClient, RegistryStore],
) -> None:
    ac, _ = rpc_client
    resp = await ac.get("/v1/lineage/ghost")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_revocation_list_returns_revoked(
    rpc_client: tuple[AsyncClient, RegistryStore],
) -> None:
    ac, store = rpc_client
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text="x",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)
    await publish_halo(store=store, card=card, runtime_state=VacantState.ACTIVE, signing_key=sk)
    await store.update_vacant_status(vid.hex(), "revoked")
    resp = await ac.get("/v1/revocation_list")
    assert resp.status_code == 200
    assert vid.hex() in resp.json()


@pytest.mark.asyncio
async def test_epoch_404_when_none(
    rpc_client: tuple[AsyncClient, RegistryStore],
) -> None:
    ac, _ = rpc_client
    resp = await ac.get("/v1/epoch_root/latest")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_epoch_round_trip(
    rpc_client: tuple[AsyncClient, RegistryStore],
) -> None:
    ac, store = rpc_client
    sk, vk = keygen()
    card = CapabilityCard(
        vacant_id=VacantId.from_verify_key(vk),
        capability_text="x",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
    ).signed(sk)
    await publish_halo(store=store, card=card, runtime_state=VacantState.ACTIVE, signing_key=sk)
    epoch = await store.seal_epoch(signing_key=sk)
    resp = await ac.get(f"/v1/epoch/{epoch.epoch_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["root_hash_hex"] == epoch.root_hash.hex()


@pytest.mark.asyncio
async def test_publish_endpoint_returns_501_stub(
    rpc_client: tuple[AsyncClient, RegistryStore],
) -> None:
    ac, _ = rpc_client
    resp = await ac.post(
        "/v1/halo",
        json={
            "capability_text": "x",
            "capability_card_hex": "deadbeef",
            "runtime_state": "ACTIVE",
        },
    )
    assert resp.status_code == 501


@pytest.mark.asyncio
async def test_stub_endpoints_return_not_implemented_in_p4(
    rpc_client: tuple[AsyncClient, RegistryStore],
) -> None:
    ac, _ = rpc_client
    for path in (
        "/v1/submit_event",
        "/v1/submit_review",
        "/v1/submit_peer_review",
        "/v1/spawn",
        "/v1/submit_composition_link",
        "/v1/submit_finalization",
        "/v1/submit_attestation",
        "/v1/sink",
        "/v1/report_anomaly",
    ):
        resp = await ac.post(path)
        assert resp.status_code == 200, path
        assert resp.json()["not_implemented_in_p4"] is True
