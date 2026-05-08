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


async def _signed_publish_body(  # type: ignore[no-untyped-def]
    *,
    sk,
    vid,
    capability_text: str = "echo",
    endpoint: str | None = "http://test",
    actor_seq: int = 1,
    ts_ms: int | None = None,
    visibility: str = "PUBLIC",
    runtime_state: str = "ACTIVE",
) -> dict[str, object]:
    from vacant.core.crypto import hash_blake2b, sign
    from vacant.protocol.capability_card import serialize as serialize_card
    from vacant.registry.halo import (
        RegisterEventDraftInputs,
        register_event_canonical_bytes,
    )
    from vacant.registry.visibility import Visibility

    card = CapabilityCard(
        vacant_id=vid,
        capability_text=capability_text,
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
        endpoint=endpoint,
    ).signed(sk)
    blob_hex = serialize_card(card).hex()
    if ts_ms is None:
        from vacant.registry.store import now_ms

        ts_ms = now_ms()
    idempotency_key = f"register:{vid.hex()}:{ts_ms}:{actor_seq}"
    inputs = RegisterEventDraftInputs(
        vacant_id=vid.hex(),
        capability_card_hash=hash_blake2b(card.signing_payload()),
        halo_version=card.halo_version,
        visibility=Visibility(visibility),
        ts_ms=ts_ms,
        actor_seq=actor_seq,
        idempotency_key=idempotency_key,
    )
    canonical = register_event_canonical_bytes(inputs, signed_by_pubkey=vid.pubkey_bytes)
    sig = sign(sk, canonical)
    return {
        "capability_card_blob_hex": blob_hex,
        "runtime_state": runtime_state,
        "visibility": visibility,
        "event_ts_ms": ts_ms,
        "event_actor_seq": actor_seq,
        "event_idempotency_key": idempotency_key,
        "event_signature_hex": sig.hex(),
    }


@pytest.mark.asyncio
async def test_halo_publish_success(
    rpc_client: tuple[AsyncClient, RegistryStore],
) -> None:
    """F5: signed halo publish over HTTP lands a row + a register event."""
    ac, store = rpc_client
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    body = await _signed_publish_body(sk=sk, vid=vid)
    resp = await ac.post("/v1/halo", json=body)
    assert resp.status_code == 200, resp.text
    out = resp.json()
    assert out["vacant_id"] == vid.hex()
    assert out["visibility"] == "PUBLIC"
    assert out["event_seq"] >= 1
    # Side effect: vacant row + register event persisted.
    row = await store.get_vacant(vid.hex())
    assert row is not None
    last = await store.latest_event_for_actor(vid.hex())
    assert last is not None
    assert last.event_type == "register"


@pytest.mark.asyncio
async def test_halo_publish_bad_signature_rejected(
    rpc_client: tuple[AsyncClient, RegistryStore],
) -> None:
    """F5: tampered event signature → 401."""
    ac, _ = rpc_client
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    body = await _signed_publish_body(sk=sk, vid=vid)
    sig = bytearray.fromhex(body["event_signature_hex"])  # type: ignore[arg-type]
    sig[0] ^= 0xFF
    body["event_signature_hex"] = sig.hex()
    resp = await ac.post("/v1/halo", json=body)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_halo_publish_malformed_card_rejected(
    rpc_client: tuple[AsyncClient, RegistryStore],
) -> None:
    """F5: a non-CapabilityCard hex blob → 400."""
    ac, _ = rpc_client
    resp = await ac.post(
        "/v1/halo",
        json={
            "capability_card_blob_hex": "deadbeef",
            "runtime_state": "ACTIVE",
            "event_ts_ms": 0,
            "event_actor_seq": 1,
            "event_idempotency_key": "x",
            "event_signature_hex": "00" * 64,
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_halo_publish_http_republish_preserves_unspecified_metadata(
    rpc_client: tuple[AsyncClient, RegistryStore],
) -> None:
    """Pfix3 F2: HTTP republish that omits base_model / version / etc.
    must NOT clobber the existing row with kwarg defaults — only the
    card-derived columns + visibility update."""
    ac, store = rpc_client
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)

    # First publish carries metadata explicitly.
    body = await _signed_publish_body(sk=sk, vid=vid, actor_seq=1)
    body["base_model"] = "claude-3.5"
    body["base_model_family"] = "claude"
    body["version"] = "0.5.0"
    body["owner_org"] = "acme corp"
    r1 = await ac.post("/v1/halo", json=body)
    assert r1.status_code == 200, r1.text
    pre = await store.get_vacant(vid.hex())
    assert pre is not None and pre.version == "0.5.0"

    # Republish with bumped halo_version + a new capability_text, but
    # NO metadata kwargs in the request body.
    body2 = await _signed_publish_body(
        sk=sk,
        vid=vid,
        capability_text="upgraded",
        actor_seq=2,
        ts_ms=int(body["event_ts_ms"]) + 1,  # type: ignore[arg-type]
    )
    r2 = await ac.post("/v1/halo", json=body2)
    assert r2.status_code == 200, r2.text
    post = await store.get_vacant(vid.hex())
    assert post is not None
    # Metadata preserved (defaults are None → skipped from update).
    assert post.base_model == "claude-3.5"
    assert post.base_model_family == "claude"
    assert post.version == "0.5.0"
    assert post.owner_org == "acme corp"
    # Card-derived columns moved (intrinsic to republish).
    assert post.capability_card_hash != pre.capability_card_hash


@pytest.mark.asyncio
async def test_halo_publish_replay_same_seq_idempotent(
    rpc_client: tuple[AsyncClient, RegistryStore],
) -> None:
    """F5: same idempotency_key + payload → returns the same event (no
    duplicate), but a *different* publish under the same actor_seq with
    a different idempotency_key is a replay → 409."""
    ac, _ = rpc_client
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    body = await _signed_publish_body(sk=sk, vid=vid, actor_seq=1)
    r1 = await ac.post("/v1/halo", json=body)
    assert r1.status_code == 200
    # Same body again is idempotent (same key, same payload_hash).
    r2 = await ac.post("/v1/halo", json=body)
    assert r2.status_code == 200
    assert r2.json()["event_seq"] == r1.json()["event_seq"]
    # A second publish with actor_seq=1 (re-using a sequence) is rejected.
    body2 = await _signed_publish_body(sk=sk, vid=vid, actor_seq=1, ts_ms=body["event_ts_ms"] + 1)  # type: ignore[operator]
    r3 = await ac.post("/v1/halo", json=body2)
    assert r3.status_code == 409


@pytest.mark.asyncio
async def test_query_capability_uses_provided_oracle() -> None:
    """F6: build_app(reputation_oracle=...) threads through to ranking
    so /v1/query_capability orders by mean reputation, not insertion."""
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import create_async_engine

    from vacant.registry import RegistryStore, build_app

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    store = RegistryStore(engine)
    await store.init_schema()
    sk1, vk1 = keygen()
    sk2, vk2 = keygen()
    vid1 = VacantId.from_verify_key(vk1)
    vid2 = VacantId.from_verify_key(vk2)
    # Publish two halos under the same capability.
    for sk_, vid_ in ((sk1, vid1), (sk2, vid2)):
        card = CapabilityCard(
            vacant_id=vid_,
            capability_text="rank-me",
            substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
        ).signed(sk_)
        from vacant.registry import publish_halo

        await publish_halo(
            store=store,
            card=card,
            runtime_state=VacantState.ACTIVE,
            signing_key=sk_,
        )

    class _BiasedOracle:
        def __init__(self, winner: str) -> None:
            self.winner = winner

        async def score(self, vacant_id: str, dimensions: Sequence[str]) -> float:
            _ = dimensions
            return 1.0 if vacant_id == self.winner else 0.1

    oracle = _BiasedOracle(winner=vid2.hex())
    app = build_app(store, reputation_oracle=oracle)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/v1/query_capability?capability=rank-me")
        assert r.status_code == 200
        matches = r.json()["matches"]
        # Oracle bias must surface vid2 first regardless of insertion order.
        assert matches[0]["vacant_id"] == vid2.hex()
        assert matches[0]["score"] > matches[1]["score"]
    await engine.dispose()


@pytest.mark.asyncio
async def test_capability_card_response_carries_blob_hex(
    rpc_client: tuple[AsyncClient, RegistryStore],
) -> None:
    """The read endpoint must surface the signed card blob so `vacant
    call` can dispatch directly."""
    ac, store = rpc_client
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text="echo",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
        endpoint="http://test/a2a",
    ).signed(sk)
    await publish_halo(store=store, card=card, runtime_state=VacantState.ACTIVE, signing_key=sk)
    r = await ac.get(f"/v1/capability_card/{vid.hex()}")
    assert r.status_code == 200
    blob_hex = r.json()["capability_card_blob_hex"]
    assert blob_hex
    from vacant.protocol.capability_card import deserialize as deserialize_card

    rebuilt = deserialize_card(bytes.fromhex(blob_hex))
    assert rebuilt.vacant_id == vid
    assert rebuilt.endpoint == "http://test/a2a"
    assert rebuilt.verify()


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
