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
from vacant.protocol.envelope import from_a2a_jsonrpc
from vacant.protocol.replay_protect import PairKey, ReplayState
from vacant.reputation.blinded_review import (
    BLINDED_COMMITMENT_SCHEME,
    BlindedReviewBatch,
    RevealEnvelope,
)
from vacant.runtime.self_growth import verify_review_signature
from vacant.core.types import EMPTY_PREV_HASH

__all__ = [
    "ServeBundle",
    "build_serve_app",
    "echo_behavior",
]

_REVIEW_DIMS = ("factual", "logical", "relevance")
_BLINDED_BATCH_MIN_REVEAL = 3
"""Default batch threshold for the blinded-review path. THEORY_V5
§3.9 #4 doesn't pin a number; 3 matches the auto-spawn streak so a
single tit-for-tat reviewer can't unblind themselves by also
submitting two complicit reviews."""


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

    # --- Blinded peer review (THEORY_V5 §3.9 #4) ----------------------
    # In-memory accumulator + spent-commitment set, scoped to this
    # build_serve_app instance. The set defends against an attacker
    # who tries to re-ingest a commitment to inflate the batch toward
    # the reveal threshold; once a commitment has been seen, further
    # ingestions of the same commitment are rejected as duplicates.
    blinded_batch = BlindedReviewBatch(min_reveal_size=_BLINDED_BATCH_MIN_REVEAL)
    spent_commitments: set[str] = set()

    @app.post("/reviews/blinded_ingest")
    async def ingest_blinded_review(request: Request) -> JSONResponse:
        """Accept a `(blinded_record, reveal_envelope)` pair for this
        vacant. The blinded record carries `reviewer_commitment` in
        place of `reviewer`; the envelope carries the commitment's
        preimage but is **buffered** until the batch reaches
        `_BLINDED_BATCH_MIN_REVEAL`, at which point all buffered pairs
        are unblinded together and the unblinded rows are appended to
        `reviews_received.jsonl`.

        Threat model: the buffering defeats real-time tit-for-tat —
        Bob's grow loop can't see Alice's identity from Alice's
        blinded review until at least N-1 *other* reviewers have also
        committed, by which time the immediate retaliation window
        has closed. Replay protection: a commitment may only be
        ingested once across the lifetime of this server process.
        """
        try:
            body = await request.json()
        except Exception as exc:
            return JSONResponse({"ok": False, "error": f"bad_json: {exc}"}, status_code=400)
        if not isinstance(body, dict) or "record" not in body or "reveal" not in body:
            return JSONResponse(
                {"ok": False, "error": "expected {record:..., reveal:...}"},
                status_code=400,
            )
        record = body["record"]
        reveal_dict = body["reveal"]
        if not isinstance(record, dict) or not isinstance(reveal_dict, dict):
            return JSONResponse(
                {"ok": False, "error": "record/reveal must be objects"}, status_code=400
            )
        if record.get("commitment_scheme") != BLINDED_COMMITMENT_SCHEME:
            return JSONResponse(
                {"ok": False, "error": f"wrong commitment_scheme; expected {BLINDED_COMMITMENT_SCHEME}"},
                status_code=400,
            )
        if record.get("target") != vid.hex():
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
                    {"ok": False, "error": f"dimension_out_of_range:{k}"}, status_code=422
                )
        commitment_hex = record.get("reviewer_commitment")
        if not isinstance(commitment_hex, str) or len(commitment_hex) != 64:
            return JSONResponse(
                {"ok": False, "error": "reviewer_commitment_invalid"}, status_code=422
            )
        if commitment_hex in spent_commitments:
            return JSONResponse(
                {"ok": False, "error": "commitment_already_spent", "commitment": commitment_hex},
                status_code=409,
            )
        try:
            envelope = RevealEnvelope.from_dict(reveal_dict)
        except (KeyError, ValueError) as exc:
            return JSONResponse(
                {"ok": False, "error": f"reveal_envelope_invalid: {exc}"}, status_code=422
            )

        try:
            blinded_batch.add(record, envelope)
        except ValueError as exc:
            return JSONResponse(
                {"ok": False, "error": f"batch_add_rejected: {exc}"}, status_code=422
            )
        spent_commitments.add(commitment_hex)

        flushed: list[dict[str, object]] = []
        if blinded_batch.is_ready_to_reveal():
            unblinded_rows = blinded_batch.flush_reveals()
            if unblinded_rows:
                home_dir_local = (home if home is not None else ls.vacant_home()) / name
                home_dir_local.mkdir(parents=True, exist_ok=True)
                jsonl_local = home_dir_local / "reviews_received.jsonl"
                with jsonl_local.open("a", encoding="utf-8") as f:
                    for row in unblinded_rows:
                        f.write(json.dumps(row, sort_keys=True) + "\n")
                flushed = unblinded_rows
            # If flush_reveals returned [] (verification failure), the
            # buffer is preserved for audit; we leave the spent set as-is
            # so a malicious operator can't replay the bad pair.

        return JSONResponse(
            {
                "ok": True,
                "buffered": blinded_batch.pending_count,
                "threshold": _BLINDED_BATCH_MIN_REVEAL,
                "flushed_count": len(flushed),
                "commitment": commitment_hex,
            }
        )

    @app.post("/a2a/chain/reset")
    async def chain_reset(request: Request) -> JSONResponse:
        """Allow a peer to ask us to forget our replay-store state for
        the (peer, self) pair so they can re-establish the chain from
        seq=1 / prev=EMPTY.

        Without this, once a peer's outbound chain drifts out of sync
        with ours (lost ACKs, peer restart, etc.), every subsequent
        probe is rejected as non-monotonic and the link is permanently
        broken with no recovery path.

        Request body: full A2A JSON-RPC envelope wire format. The
        payload text MUST be exactly "RESET_CHAIN". We verify the
        envelope signature against the claimed `from_vacant_id` and
        require timestamp within ±5 minutes of now (anti-replay of an
        old reset). We then `seed()` our replay store to a fresh
        ReplayState(0, EMPTY_PREV_HASH) for that pair.
        """
        from datetime import datetime, UTC

        try:
            wire = await request.json()
            env = from_a2a_jsonrpc(wire)
        except Exception as exc:
            return JSONResponse({"ok": False, "error": f"bad_envelope: {exc}"}, status_code=400)
        # Verify the requester's signature on their reset envelope.
        try:
            env.verify_or_raise(env.from_vacant_id.verify_key())
        except Exception as exc:
            return JSONResponse({"ok": False, "error": f"signature_invalid: {exc}"}, status_code=401)
        # Payload must be the literal RESET_CHAIN sentinel — we don't want
        # a generic /a2a/message/send envelope to accidentally count as a reset.
        payload_text = " ".join(p.text for p in env.payload.parts).strip()
        if payload_text != "RESET_CHAIN":
            return JSONResponse({"ok": False, "error": "payload_not_reset_chain"}, status_code=400)
        # Anti-replay: timestamp must be fresh.
        age_s = abs((datetime.now(UTC) - env.timestamp).total_seconds())
        if age_s > 300:
            return JSONResponse(
                {"ok": False, "error": f"stale_reset_request: age={age_s:.0f}s"},
                status_code=400,
            )
        # Verify the reset envelope is addressed to us.
        if env.to_vacant_id.hex() != vid.hex():
            return JSONResponse({"ok": False, "error": "not_addressed_to_self"}, status_code=422)
        # Reset BOTH directions for this pair — defensive.
        peer_vid = env.from_vacant_id
        fresh = ReplayState(last_sequence_no=0, chain_tip=EMPTY_PREV_HASH)
        replay_store.seed(PairKey(from_vid=peer_vid, to_vid=vid), fresh)
        replay_store.seed(PairKey(from_vid=vid, to_vid=peer_vid), fresh)
        return JSONResponse(
            {
                "ok": True,
                "reset_for_peer": peer_vid.hex(),
                "reset_at": datetime.now(UTC).isoformat(),
            }
        )

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
