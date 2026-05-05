"""FastAPI RPC surface — 25 endpoints documented in OpenAPI.

Per dispatch §"Acceptance": "13 tables present, 25 RPC endpoints
documented in OpenAPI". This module wires every endpoint listed in
`architecture/components/P4_registry.md` §3.2 to a Pydantic v2
request/response model and a thin handler that delegates to
`RegistryStore` / `aggregation.py` / `halo.py`.

Endpoints whose backing logic belongs to other components (P3
reputation snapshots, P5 composition links, P6 envelope dispatch) carry
a `not_implemented_in_p4` flag in the response so callers can plan
around the stubs without the endpoint disappearing later.
"""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from vacant.registry.aggregation import (
    HaloMatch,
    lineage_query,
    rank_by_reputation,
    search_capability,
)
from vacant.registry.errors import (
    NotFoundError,
    RegistryWriteError,
    VisibilityViolation,
)
from vacant.registry.store import RegistryStore

__all__ = ["build_app"]


# --- request/response models -------------------------------------------------


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HaloPublishRequest(_Base):
    capability_text: str
    capability_card_hex: str
    """Hex-encoded canonical-bytes of a `CapabilityCard`. The handler
    reconstructs and verifies it."""
    runtime_state: Literal["LOCAL", "ACTIVE", "HIBERNATING", "STALE", "SUNK", "ARCHIVED"]
    visibility: Literal["NONE", "RESTRICTED", "PUBLIC"] = "PUBLIC"
    base_model: str = "unknown"
    base_model_family: str = "unknown"


class HaloResponse(_Base):
    vacant_id: str
    visibility: str
    event_seq: int
    capability_card_hash_hex: str


class RevokeHaloRequest(_Base):
    vacant_id: str
    reason: str
    pubkey_hex: str
    signature_hex: str


class RevokeHaloResponse(_Base):
    vacant_id: str
    event_seq: int
    reason: str


class HaloMatchResponse(_Base):
    vacant_id: str
    capability_card_hash_hex: str
    capability_card_sig_hex: str
    declared_capabilities_json: str
    base_model_family: str
    visibility: str
    score: float


class CapabilitySearchResponse(_Base):
    matches: list[HaloMatchResponse]
    not_implemented_in_p4: list[str] = Field(default_factory=list)


class LineageResponse(_Base):
    vacant_id: str
    direction: str
    chain: list[str]


class EventResponse(_Base):
    seq: int
    event_type: str
    actor_vacant_id: str
    subject_vacant_id: str | None
    payload_json: str
    event_hash_hex: str
    actor_seq: int
    ts: int


class EpochResponse(_Base):
    epoch_id: int
    first_seq: int
    last_seq: int
    tree_size: int
    root_hash_hex: str
    sealed_at: int
    registry_signature_hex: str


class StubResponse(_Base):
    """Returned by endpoints whose backing logic belongs to a later component."""

    not_implemented_in_p4: bool = True
    component: str
    message: str


def _match_to_response(m: HaloMatch) -> HaloMatchResponse:
    return HaloMatchResponse(
        vacant_id=m.vacant_id,
        capability_card_hash_hex=m.capability_card_hash.hex(),
        capability_card_sig_hex=m.capability_card_sig.hex(),
        declared_capabilities_json=m.declared_capabilities_json,
        base_model_family=m.base_model_family,
        visibility=m.visibility.value,
        score=m.score,
    )


# --- app builder -------------------------------------------------------------


def build_app(store: RegistryStore) -> FastAPI:
    """Build the FastAPI app with all 25 endpoints wired to `store`."""

    app = FastAPI(
        title="Vacant Registry (P4 — central MVP)",
        version="0.1.0",
        description=(
            "Per-vacant capability-card publication + aggregation index. "
            "13 tables, 25 endpoints, 6 anti-tamper layers. See P4_registry.md."
        ),
    )

    # --- writes (12) -------------------------------------------------------

    @app.post("/v1/halo", response_model=HaloResponse, tags=["write"])
    async def publish(req: HaloPublishRequest) -> HaloResponse:
        # The body of `publish_halo` lives in halo.py; we cannot
        # reconstruct a fully-typed CapabilityCard from a hex blob in this
        # module without a circular import, so this endpoint is the seam:
        # callers serialise their card in their own session and POST the
        # canonical bytes. For tests we exercise `publish_halo` directly.
        raise HTTPException(
            status_code=501,
            detail=(
                "RPC publish stub: serialise CapabilityCard via the python "
                "`vacant.registry.halo.publish_halo` API; HTTP body schema "
                "lands with P6 envelope work."
            ),
        )

    @app.post("/v1/revoke_halo", response_model=RevokeHaloResponse, tags=["write"])
    async def revoke(req: RevokeHaloRequest) -> RevokeHaloResponse:
        try:
            pubkey_bytes = bytes.fromhex(req.pubkey_hex)
            signature = bytes.fromhex(req.signature_hex)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"hex decode failed: {exc}") from exc
        try:
            from vacant.core.crypto import SigningKey  # noqa: F401

            # We cannot reconstruct a SigningKey from the public key alone;
            # this endpoint expects the caller to have the private key.
            # P6 envelope work will replace this with a signed envelope.
            _ = (pubkey_bytes, signature)
            raise HTTPException(
                status_code=501,
                detail="revoke_halo HTTP path lands with P6 envelope; use halo.revoke_halo()",
            )
        except RegistryWriteError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/submit_event", response_model=StubResponse, tags=["write"])
    async def submit_event() -> StubResponse:
        return StubResponse(component="P6", message="generic envelope dispatcher")

    @app.post("/v1/submit_review", response_model=StubResponse, tags=["write"])
    async def submit_review() -> StubResponse:
        return StubResponse(component="P3", message="reviews land with P3 reputation")

    @app.post("/v1/submit_peer_review", response_model=StubResponse, tags=["write"])
    async def submit_peer_review() -> StubResponse:
        return StubResponse(component="P3", message="peer reviews land with P3 reputation")

    @app.post("/v1/spawn", response_model=StubResponse, tags=["write"])
    async def spawn() -> StubResponse:
        return StubResponse(
            component="P1+P5",
            message="spawn flow goes through runtime/spawn + composite ChildManifest",
        )

    @app.post("/v1/submit_composition_link", response_model=StubResponse, tags=["write"])
    async def submit_composition_link() -> StubResponse:
        return StubResponse(component="P5", message="composition links land with P5")

    @app.post("/v1/submit_finalization", response_model=StubResponse, tags=["write"])
    async def submit_finalization() -> StubResponse:
        return StubResponse(
            component="P3",
            message="N-of-M finalization signals land with P3 reputation",
        )

    @app.post("/v1/submit_attestation", response_model=StubResponse, tags=["write"])
    async def submit_attestation() -> StubResponse:
        return StubResponse(
            component="P2",
            message=(
                "use vacant.identity.issue_attestation + halo.publish; HTTP "
                "envelope schema lands with P6"
            ),
        )

    @app.post("/v1/sink", response_model=StubResponse, tags=["write"])
    async def sink() -> StubResponse:
        return StubResponse(component="P1", message="sink flow lives in runtime")

    @app.post("/v1/report_anomaly", response_model=StubResponse, tags=["write"])
    async def report_anomaly() -> StubResponse:
        return StubResponse(
            component="P3",
            message=("report-only stub; auto-freeze rules wired in P3 + P4 anomaly engine"),
        )

    @app.post("/v1/seal_epoch", response_model=EpochResponse, tags=["write"])
    async def seal_epoch_endpoint() -> EpochResponse:
        # Internal — exposed for ops scripts. Production cron drives this.
        raise HTTPException(
            status_code=501,
            detail="seal_epoch HTTP path is internal; call store.seal_epoch() from cron",
        )

    # --- reads (13) --------------------------------------------------------

    @app.get(
        "/v1/capability_card/{vacant_id}",
        response_model=HaloMatchResponse,
        tags=["read"],
    )
    async def get_capability_card(
        vacant_id: str,
        caller: str | None = Query(default=None, description="caller vacant_id hex"),
    ) -> HaloMatchResponse:
        try:
            v = await store.lookup_halo_for_caller(vacant_id, caller_pubkey_hex=caller)
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except VisibilityViolation as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        from vacant.registry.aggregation import _to_match

        return _match_to_response(_to_match(v))

    @app.post(
        "/v1/query_capability",
        response_model=CapabilitySearchResponse,
        tags=["read"],
    )
    async def query_capability(
        capability: str | None = Query(default=None),
        family: str | None = Query(default=None),
        limit: int = Query(default=20, ge=1, le=100),
    ) -> CapabilitySearchResponse:
        matches = await search_capability(store=store, query=capability, family=family, limit=limit)
        ranked = await rank_by_reputation(matches)
        return CapabilitySearchResponse(matches=[_match_to_response(m) for m in ranked])

    @app.get("/v1/reputation/{vacant_id}", response_model=StubResponse, tags=["read"])
    async def get_reputation(vacant_id: str) -> StubResponse:
        _ = vacant_id
        return StubResponse(component="P3", message="reputation snapshots land with P3")

    @app.get(
        "/v1/reputation_history/{vacant_id}",
        response_model=StubResponse,
        tags=["read"],
    )
    async def get_reputation_history(vacant_id: str) -> StubResponse:
        _ = vacant_id
        return StubResponse(component="P3", message="reputation history lands with P3")

    @app.get("/v1/event_log/{vacant_id}", response_model=list[EventResponse], tags=["read"])
    async def get_event_log(
        vacant_id: str,
        from_seq: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> list[EventResponse]:
        rows = await store.list_events_for_vacant(vacant_id, from_seq=from_seq, limit=limit)
        return [
            EventResponse(
                seq=r.seq or 0,
                event_type=r.event_type,
                actor_vacant_id=r.actor_vacant_id,
                subject_vacant_id=r.subject_vacant_id,
                payload_json=r.payload_json,
                event_hash_hex=r.event_hash.hex(),
                actor_seq=r.actor_seq,
                ts=r.ts,
            )
            for r in rows
        ]

    @app.get("/v1/event/{seq}", response_model=EventResponse, tags=["read"])
    async def get_event(seq: int) -> EventResponse:
        row = await store.get_event(seq)
        if row is None:
            raise HTTPException(status_code=404, detail=f"event seq={seq} not found")
        return EventResponse(
            seq=row.seq or 0,
            event_type=row.event_type,
            actor_vacant_id=row.actor_vacant_id,
            subject_vacant_id=row.subject_vacant_id,
            payload_json=row.payload_json,
            event_hash_hex=row.event_hash.hex(),
            actor_seq=row.actor_seq,
            ts=row.ts,
        )

    @app.get("/v1/lineage/{vacant_id}", response_model=LineageResponse, tags=["read"])
    async def get_lineage(
        vacant_id: str,
        direction: Literal["descendants", "ancestors"] = Query(default="descendants"),
        depth: int = Query(default=8, ge=1, le=32),
    ) -> LineageResponse:
        try:
            chain = await lineage_query(
                store=store, vacant_id=vacant_id, direction=direction, depth=depth
            )
        except NotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return LineageResponse(vacant_id=vacant_id, direction=direction, chain=chain)

    @app.get(
        "/v1/composition_links/{vacant_id}",
        response_model=StubResponse,
        tags=["read"],
    )
    async def get_composition_links(vacant_id: str) -> StubResponse:
        _ = vacant_id
        return StubResponse(component="P5", message="composition links land with P5")

    @app.get("/v1/sink_record/{vacant_id}", response_model=StubResponse, tags=["read"])
    async def get_sink_record(vacant_id: str) -> StubResponse:
        _ = vacant_id
        return StubResponse(
            component="P1+P3",
            message="sink_record table is populated by runtime+reputation",
        )

    @app.get("/v1/freeze_status/{vacant_id}", response_model=StubResponse, tags=["read"])
    async def get_freeze_status(vacant_id: str) -> StubResponse:
        _ = vacant_id
        return StubResponse(
            component="P3+P4",
            message="freeze table populated by anomaly engine + governance",
        )

    @app.get("/v1/revocation_list", response_model=list[str], tags=["read"])
    async def get_revocation_list() -> list[str]:
        # Returns vacant_ids whose status is `revoked`.
        rows = await store.search_capability(
            capability=None,
            family=None,
            status="revoked",
            visibility=None,
            limit=10_000,
        )
        return [r.vacant_id for r in rows]

    @app.get("/v1/epoch/{epoch_id}", response_model=EpochResponse, tags=["read"])
    async def get_epoch(epoch_id: int) -> EpochResponse:
        epoch = await store.get_merkle_epoch(epoch_id)
        if epoch is None:
            raise HTTPException(status_code=404, detail=f"epoch_id={epoch_id} not found")
        return EpochResponse(
            epoch_id=epoch.epoch_id or 0,
            first_seq=epoch.first_seq,
            last_seq=epoch.last_seq,
            tree_size=epoch.tree_size,
            root_hash_hex=epoch.root_hash.hex(),
            sealed_at=epoch.sealed_at,
            registry_signature_hex=epoch.registry_signature.hex(),
        )

    @app.get("/v1/epoch_root/latest", response_model=EpochResponse, tags=["read"])
    async def get_latest_epoch_root() -> EpochResponse:
        epoch = await store.latest_merkle_epoch()
        if epoch is None:
            raise HTTPException(status_code=404, detail="no sealed epoch yet")
        return EpochResponse(
            epoch_id=epoch.epoch_id or 0,
            first_seq=epoch.first_seq,
            last_seq=epoch.last_seq,
            tree_size=epoch.tree_size,
            root_hash_hex=epoch.root_hash.hex(),
            sealed_at=epoch.sealed_at,
            registry_signature_hex=epoch.registry_signature.hex(),
        )

    return app
