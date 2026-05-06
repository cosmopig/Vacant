"""Incoming-call serve: FastAPI router mounted at `/a2a` (and `/mcp`).

Per dispatch §4 the inbound flow is:

1. Verify envelope signature against `from_vacant_id`'s pubkey.
2. Check `state_machine.can_be_called(my_state)` — reject SUNK/ARCHIVED
   with 410 GONE and HIBERNATING/STALE with 423 LOCKED.
3. Verify `sequence_no` monotonicity for the `(from, to)` pair via
   `replay_protect.ReplayStore`.
4. Hand the payload to the vacant's `behavior_bundle` (this is where
   the substrate runs).
5. Sign and return a response envelope; both directions advance the
   per-pair envelope chain via `replay_protect`.

The `behavior` parameter is a callable that takes a `VacantEnvelope`
and returns an `A2AMessage`. P7 demo wires this to a real substrate;
unit tests pass a lambda.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request

from vacant.core.crypto import SigningKey
from vacant.core.types import EMPTY_PREV_HASH, ResidentForm, VacantState
from vacant.protocol.envelope import (
    A2AMessage,
    VacantEnvelope,
    from_a2a_jsonrpc,
    to_a2a_jsonrpc,
)
from vacant.protocol.errors import (
    EnvelopeFormatError,
    EnvelopeSignatureError,
)
from vacant.protocol.replay_protect import (
    PairKey,
    ReplayStore,
)
from vacant.runtime.state_machine import can_be_called

__all__ = [
    "BehaviorHandler",
    "build_a2a_app",
    "build_a2a_router",
    "make_response_envelope",
]


BehaviorHandler = Callable[[VacantEnvelope], Awaitable[A2AMessage]]


async def make_response_envelope(
    *,
    request: VacantEnvelope,
    response_payload: A2AMessage,
    self_signing_key: SigningKey,
    response_replay_store: ReplayStore,
    self_form: ResidentForm,
) -> VacantEnvelope:
    """Build the response envelope (vacant → caller).

    Uses the `(self → caller)` direction of the per-pair chain (ours).
    """
    inverse_key = PairKey(from_vid=self_form.identity, to_vid=request.from_vacant_id)
    cur = await response_replay_store.get(inverse_key)
    response = VacantEnvelope(
        from_vacant_id=self_form.identity,
        to_vacant_id=request.from_vacant_id,
        sequence_no=cur.last_sequence_no + 1,
        timestamp=datetime.now(UTC),
        prev_envelope_hash=cur.chain_tip if cur.last_sequence_no > 0 else EMPTY_PREV_HASH,
        payload=response_payload,
        idempotency_key=str(uuid.uuid4()),
    ).signed(self_signing_key)
    # Record the response so the next response on this pair chains correctly.
    await response_replay_store.check_and_advance(response)
    return response


def build_a2a_router(
    *,
    self_form: ResidentForm,
    self_signing_key: SigningKey,
    behavior: BehaviorHandler,
    replay_store: ReplayStore,
    state_provider: Callable[[], VacantState] | None = None,
    prefix: str = "/a2a",
) -> APIRouter:
    """Build a FastAPI router serving inbound A2A `message/send` requests.

    `state_provider` (defaults to `lambda: self_form.runtime_state`)
    determines whether the vacant accepts the call:

    - SUNK / ARCHIVED → 410 GONE
    - HIBERNATING / STALE → 423 LOCKED
    - LOCAL / ACTIVE → accepted
    """
    router = APIRouter(prefix=prefix)
    state_fn = state_provider or (lambda: self_form.runtime_state)

    @router.post("/message/send")
    async def message_send(request: Request, body: dict[str, Any]) -> dict[str, Any]:
        # F3: spec-shape validation BEFORE we hand bytes to the parser.
        # FastAPI normally parses application/json automatically, but a
        # client sending text/plain or a non-JSON-RPC envelope must be
        # rejected with a structured 400 — silently coercing causes
        # subtle replay-protection bugs downstream.
        content_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
        if content_type and content_type != "application/json":
            raise HTTPException(
                status_code=415,
                detail=f"unsupported content-type {content_type!r}; expected application/json",
            )
        if body.get("jsonrpc") != "2.0":
            raise HTTPException(
                status_code=400,
                detail=f"jsonrpc field must be '2.0'; got {body.get('jsonrpc')!r}",
            )
        method = body.get("method")
        if method != "message/send":
            raise HTTPException(
                status_code=400,
                detail=f"method must be 'message/send'; got {method!r}",
            )

        # 1. Parse envelope.
        try:
            request_env = from_a2a_jsonrpc(body)
        except EnvelopeFormatError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if request_env.to_vacant_id != self_form.identity:
            raise HTTPException(
                status_code=421,  # Misdirected Request
                detail=(
                    f"envelope addressed to {request_env.to_vacant_id.short()}; "
                    f"this server is {self_form.identity.short()}"
                ),
            )

        # 2. Verify state can_be_called.
        state = state_fn()
        if state in (VacantState.SUNK, VacantState.ARCHIVED):
            raise HTTPException(
                status_code=410,
                detail=f"vacant is {state.value}; calls permanently rejected",
            )
        if not can_be_called(state):
            raise HTTPException(
                status_code=423,
                detail=f"vacant is {state.value}; not accepting calls",
            )

        # 3. Verify signature.
        try:
            request_env.verify_or_raise(request_env.from_vacant_id.verify_key())
        except EnvelopeSignatureError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

        # 4. Replay-protect on the (caller → self) chain.
        try:
            await replay_store.check_and_advance(request_env)
        except Exception as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        # 5. Dispatch to behavior.
        response_payload = await behavior(request_env)

        # 6. Build + return response envelope on the (self → caller) chain.
        response_env = await make_response_envelope(
            request=request_env,
            response_payload=response_payload,
            self_signing_key=self_signing_key,
            response_replay_store=replay_store,
            self_form=self_form,
        )
        # Wrap the response envelope inside a JSON-RPC 2.0 `result`. The
        # dispatcher unwraps `result.message` and re-parses it via
        # `from_a2a_jsonrpc`, so the carried message keeps the same
        # `params.message` field shape.
        wire = to_a2a_jsonrpc(response_env)
        return {
            "jsonrpc": "2.0",
            "id": body.get("id"),
            "result": {"message": wire["params"]["message"]},
        }

    return router


def build_a2a_app(
    *,
    self_form: ResidentForm,
    self_signing_key: SigningKey,
    behavior: BehaviorHandler,
    replay_store: ReplayStore,
    state_provider: Callable[[], VacantState] | None = None,
) -> FastAPI:
    """Convenience: a `FastAPI` app with the A2A router mounted."""
    app = FastAPI(
        title=f"Vacant A2A serve ({self_form.identity.short()})",
        version="0.1.0",
    )
    app.include_router(
        build_a2a_router(
            self_form=self_form,
            self_signing_key=self_signing_key,
            behavior=behavior,
            replay_store=replay_store,
            state_provider=state_provider,
        )
    )
    return app
