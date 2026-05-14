"""`vacant serve` runtime: build the FastAPI app from local-store state.

Split from `commands.py` so unit tests can import `build_serve_app`
directly without going through `subprocess.Popen`. The `serve` CLI
command is a thin wrapper that hands the result to `uvicorn.run`.

The behaviour callback is intentionally minimal — it echoes the request
text back, signed by the vacant's own key. P7 demos / production
deployments swap in a substrate-driven behaviour by re-using the
underlying `build_a2a_app` directly. For the A2/A4 acceptance tests
("vacant serve + vacant call from another shell completes a real network
roundtrip") echo is enough — what's load-bearing is that the response
envelope verifies under the vacant's pubkey on the wire.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from vacant.cli import local_store as ls
from vacant.core.crypto import SigningKey
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
)
from vacant.runtime.self_growth import verify_review_signature

__all__ = [
    "ServeBundle",
    "build_serve_app",
    "echo_behavior",
]

_REVIEW_DIMS = ("factual", "logical", "relevance")


BehaviorFn = Callable[[VacantEnvelope], Awaitable[A2AMessage]]


@dataclass
class ServeBundle:
    """The four objects `vacant serve` produces from local-store state."""

    app: FastAPI
    form: ResidentForm
    signing_key: SigningKey
    replay_store: InMemoryReplayStore


async def echo_behavior(env: VacantEnvelope) -> A2AMessage:
    """Echo the incoming text back, prefixed with the vacant's short id.

    Default behaviour for `vacant serve` — keeps the acceptance tests
    self-contained (no LLM key required). Real deployments pass a
    different `behavior` to `build_serve_app`.
    """
    text = " ".join(p.text for p in env.payload.parts)
    short = env.to_vacant_id.short()
    return A2AMessage(
        role="ROLE_AGENT",
        parts=[A2APart(text=f"echo from {short}: {text}")],
    )


def build_serve_app(
    name: str,
    *,
    behavior: BehaviorFn | None = None,
    endpoint: str | None = None,
    home: Path | None = None,
) -> ServeBundle:
    """Hydrate a `vacant serve` FastAPI app from `~/.vacant/<name>/`.

    `endpoint` overrides the meta endpoint when set (uvicorn assigns
    the bind address but the capability card needs a publishable URL).

    `home` overrides VACANT_HOME for the `/reviews/ingest` write
    target — useful for in-process integration tests that need two
    vacants writing to different roots. Production passes None and
    reads `$VACANT_HOME` lazily.
    """
    meta = ls.load_meta(name)
    sk = ls.load_signing_key(name)
    lb = ls.load_logbook(name)
    vid = VacantId(pubkey_bytes=bytes.fromhex(meta.vacant_id_hex))

    spec = SubstrateSpec(allowed_substrates=["mock"])
    bundle = BehaviorBundle(system_prompt="vacant serve")

    effective_endpoint = endpoint or meta.endpoint
    cap_text = meta.capability_text or "echo"
    card = CapabilityCard(
        vacant_id=vid,
        capability_text=cap_text,
        substrate_spec=spec,
        endpoint=effective_endpoint,
    ).signed(sk)

    form = ResidentForm(
        identity=vid,
        logbook=lb if lb.entries else Logbook(),
        behavior_bundle=bundle,
        substrate_spec=spec,
        runtime_state=VacantState(meta.state),
        capability_card=card,
    )

    replay_store = InMemoryReplayStore()
    app = build_a2a_app(
        self_form=form,
        self_signing_key=sk,
        behavior=behavior or echo_behavior,
        replay_store=replay_store,
    )

    @app.get("/card")
    async def get_card() -> dict[str, object]:
        from vacant.protocol.capability_card import serialize as serialize_card

        return {
            "vacant_id": vid.hex(),
            "capability_text": cap_text,
            "endpoint": effective_endpoint,
            "halo_version": card.halo_version,
            "capability_card_blob_hex": serialize_card(card).hex(),
        }

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {
            "vacant_id": vid.hex(),
            "state": form.runtime_state.value,
            "name": name,
        }

    @app.post("/reviews/ingest")
    async def ingest_review(request: Request) -> JSONResponse:
        """Accept a signed peer review whose target == this vacant.

        Per P6 §3.3 Peer Review envelope: a reviewer (another vacant)
        POSTs a signed review record. We verify the Ed25519 signature
        against the claimed reviewer pubkey (the row's `reviewer` is
        the reviewer's vacant_id, which IS their pubkey in this
        codebase), reject if target != self, dedupe by signature_hex,
        and append to `home/<self_name>/reviews_received.jsonl`.

        The decentralized, registry-less form: every vacant is its own
        review sink (CLAUDE.md: "Registry is per-vacant"). An optional
        aggregator can later pull from this jsonl across many vacants.
        """
        try:
            record = await request.json()
        except Exception as exc:
            return JSONResponse({"ok": False, "error": f"bad_json: {exc}"}, status_code=400)
        if not isinstance(record, dict):
            return JSONResponse({"ok": False, "error": "payload_not_object"}, status_code=400)
        target_hex = record.get("target")
        if target_hex != vid.hex():
            return JSONResponse(
                {"ok": False, "error": "target_mismatch", "self": vid.hex()},
                status_code=422,
            )
        dims = record.get("dimensions")
        if not isinstance(dims, dict) or set(dims).intersection(_REVIEW_DIMS) != set(_REVIEW_DIMS):
            return JSONResponse({"ok": False, "error": "dimensions_missing_FLR"}, status_code=422)
        for k in _REVIEW_DIMS:
            v = dims.get(k)
            if not isinstance(v, (int, float)) or not (0.0 <= float(v) <= 1.0):
                return JSONResponse(
                    {"ok": False, "error": f"dimension_out_of_range:{k}"},
                    status_code=422,
                )
        if not verify_review_signature(record):
            return JSONResponse({"ok": False, "error": "signature_invalid"}, status_code=401)

        home_dir = (home if home is not None else ls.vacant_home()) / name
        home_dir.mkdir(parents=True, exist_ok=True)
        jsonl = home_dir / "reviews_received.jsonl"

        sig_hex = record.get("signature_hex")
        if jsonl.exists():
            # Idempotency: skip a row we've already accepted (by signature).
            try:
                for line in jsonl.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    try:
                        existing = json.loads(line)
                    except ValueError:
                        continue
                    if existing.get("signature_hex") == sig_hex:
                        return JSONResponse(
                            {"ok": True, "duplicate": True, "signature_hex": sig_hex}
                        )
            except OSError as exc:
                return JSONResponse(
                    {"ok": False, "error": f"jsonl_read_failed: {exc}"}, status_code=500
                )

        try:
            with jsonl.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, sort_keys=True) + "\n")
        except OSError as exc:
            return JSONResponse(
                {"ok": False, "error": f"jsonl_write_failed: {exc}"}, status_code=500
            )

        return JSONResponse(
            {
                "ok": True,
                "duplicate": False,
                "reviewer": record.get("reviewer"),
                "signature_hex": sig_hex,
            }
        )

    return ServeBundle(app=app, form=form, signing_key=sk, replay_store=replay_store)
