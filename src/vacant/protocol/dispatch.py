"""Outgoing call dispatch.

`call_capability(query, requester, ...)`:

1. Look up via the registry's `aggregation.search_capability(query)`
   (excludes LOCAL by default).
2. (Optionally) score with a `ReputationOracle` and pick the UCB winner.
3. Build a `VacantEnvelope`, sign with the requester's key, POST direct
   to `card.endpoint`. **The registry is never POSTed through.**

`call_local(target_card, requester, ...)`: bypass discovery and post
directly to a known `target_card.endpoint` — for owner / parent direct
paths against LOCAL-visibility vacants.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from vacant.core.crypto import SigningKey
from vacant.core.types import (
    EMPTY_PREV_HASH,
    CapabilityCard,
    ResidentForm,
    VacantId,
)
from vacant.protocol.envelope import (
    A2AMessage,
    A2APart,
    VacantEnvelope,
    from_a2a_jsonrpc,
    to_a2a_jsonrpc,
)
from vacant.protocol.errors import (
    EnvelopeFormatError,
    EnvelopeSignatureError,
    TargetNotFoundError,
)
from vacant.protocol.replay_protect import ReplayStore

__all__ = [
    "DispatchResult",
    "DispatchTransport",
    "build_envelope",
    "call_capability",
    "call_local",
]


# A transport callable: takes endpoint URL + JSON-RPC body + optional
# pubkey to verify the response signature against, returns the parsed
# response envelope. Tests pass an in-process function; production uses
# httpx via `make_httpx_transport()` (see below).
DispatchTransport = Callable[
    [str, dict[str, Any]],
    Awaitable[dict[str, Any]],
]


class DispatchResult:
    """Result of a successful dispatch."""

    __slots__ = ("request_envelope", "response_envelope", "target")

    def __init__(
        self,
        *,
        request_envelope: VacantEnvelope,
        response_envelope: VacantEnvelope,
        target: CapabilityCard,
    ) -> None:
        self.request_envelope = request_envelope
        self.response_envelope = response_envelope
        self.target = target


def build_envelope(
    *,
    from_vid: VacantId,
    to_vid: VacantId,
    payload: A2AMessage,
    sequence_no: int = 1,
    prev_envelope_hash: bytes = EMPTY_PREV_HASH,
    idempotency_key: str | None = None,
    timestamp: datetime | None = None,
    signing_key: SigningKey,
) -> VacantEnvelope:
    """Build + sign a `VacantEnvelope` for direct dispatch."""
    return VacantEnvelope(
        from_vacant_id=from_vid,
        to_vacant_id=to_vid,
        sequence_no=sequence_no,
        timestamp=timestamp or datetime.now(UTC),
        prev_envelope_hash=prev_envelope_hash,
        payload=payload,
        idempotency_key=idempotency_key or str(uuid.uuid4()),
    ).signed(signing_key)


# --- public dispatch -------------------------------------------------------


async def call_capability(
    query: str,
    *,
    requester: ResidentForm,
    requester_signing_key: SigningKey,
    payload: A2AMessage,
    transport: DispatchTransport,
    aggregation_search: Callable[..., Awaitable[list[Any]]] | None = None,
    reputation_oracle: Any | None = None,
    sequence_no: int = 1,
    prev_envelope_hash: bytes = EMPTY_PREV_HASH,
    caller_response_replay_store: ReplayStore | None = None,
) -> DispatchResult:
    """Discover + call a remote vacant offering `query`.

    `aggregation_search` is the registry's
    `vacant.registry.aggregation.search_capability` (or a test stub
    matching the same signature). The function is *kept abstract* so
    P6 doesn't hard-import P4 — making P6 unit tests independent of
    the registry stack.

    `reputation_oracle.score(vacant_hex, dims)` is consulted to pick the
    UCB winner if provided; otherwise the first match is used.

    The registry is queried for discovery only; the call goes directly
    to `card.endpoint` via `transport`. **No registry write endpoint is
    invoked from this path** (D009 §C, dispatch acceptance).
    """
    if aggregation_search is None:
        raise TargetNotFoundError("call_capability: aggregation_search is required for discovery")
    matches = await aggregation_search(query=query, include_local=False, limit=20)
    matches = [m for m in matches if _match_endpoint(m)]
    if not matches:
        raise TargetNotFoundError(f"no public vacant offers capability {query!r}")

    chosen = await _pick_winner(matches, reputation_oracle)
    target_card = _match_to_card(chosen)
    return await call_local(
        target_card=target_card,
        requester=requester,
        requester_signing_key=requester_signing_key,
        payload=payload,
        transport=transport,
        sequence_no=sequence_no,
        prev_envelope_hash=prev_envelope_hash,
        caller_response_replay_store=caller_response_replay_store,
    )


async def call_local(
    *,
    target_card: CapabilityCard,
    requester: ResidentForm,
    requester_signing_key: SigningKey,
    payload: A2AMessage,
    transport: DispatchTransport,
    sequence_no: int = 1,
    prev_envelope_hash: bytes = EMPTY_PREV_HASH,
    caller_response_replay_store: ReplayStore | None = None,
) -> DispatchResult:
    """Direct call against a known capability card. Used by owner /
    parent paths to reach LOCAL-visibility vacants the public lookup
    excludes.

    ``caller_response_replay_store`` (Pfix3 B6): when provided, the
    incoming response envelope is run through ``check_and_advance`` on
    the ``(target → requester)`` chain, so responses can be checked for
    replay / out-of-order / chain-fork on the caller side. Default
    ``None`` keeps existing in-process tests (which use synthetic
    transports that don't track response chains) green.
    """
    if not target_card.endpoint:
        raise TargetNotFoundError(f"target {target_card.vacant_id.short()} has no endpoint URL")
    if not target_card.verify():
        raise EnvelopeSignatureError(
            f"target capability card for {target_card.vacant_id.short()} does not verify"
        )

    request = build_envelope(
        from_vid=requester.identity,
        to_vid=target_card.vacant_id,
        payload=payload,
        sequence_no=sequence_no,
        prev_envelope_hash=prev_envelope_hash,
        signing_key=requester_signing_key,
    )

    body = to_a2a_jsonrpc(request)
    response_body = await transport(target_card.endpoint, body)

    try:
        result = response_body["result"]
        response_message = result["message"]
        wrapped = {
            "jsonrpc": "2.0",
            "id": "rsp",
            "method": "message/send",
            "params": {"message": response_message},
        }
    except (KeyError, TypeError) as exc:
        raise EnvelopeFormatError(f"transport response is not a valid A2A result: {exc}") from exc

    response_env = from_a2a_jsonrpc(wrapped)
    response_env.verify_or_raise(target_card.vacant_id.verify_key())

    # Pfix3 B6: caller-side response validation. The signature check
    # above only proves "someone with target's key signed this"; the
    # routing checks below prove "this response is on our (target → me)
    # chain", and the replay store catches duplicate / out-of-order /
    # forked responses.
    if response_env.from_vacant_id != target_card.vacant_id:
        raise EnvelopeFormatError(
            "response envelope from_vacant_id "
            f"{response_env.from_vacant_id.short()} != target "
            f"{target_card.vacant_id.short()}"
        )
    if response_env.to_vacant_id != requester.identity:
        raise EnvelopeFormatError(
            "response envelope to_vacant_id "
            f"{response_env.to_vacant_id.short()} != requester "
            f"{requester.identity.short()}"
        )
    if caller_response_replay_store is not None:
        await caller_response_replay_store.check_and_advance(response_env)

    return DispatchResult(
        request_envelope=request,
        response_envelope=response_env,
        target=target_card,
    )


# --- helpers ---------------------------------------------------------------


def _match_endpoint(match: Any) -> bool:
    """True iff `match` has a non-empty endpoint we can call against.

    `match` is either a P4 `HaloMatch` or a `CapabilityCard`. We accept
    either for unit-test friendliness.
    """
    card = _match_to_card(match)
    return bool(card.endpoint)


def _match_to_card(match: Any) -> CapabilityCard:
    """Extract a `CapabilityCard` from the search result.

    Supports two shapes:
    - A `CapabilityCard` instance directly (test stubs / `call_local`).
    - A P4 `HaloMatch` carrying `capability_card` (D015 §C). Registry
      rows now persist the canonical-JSON serialized signed card, so
      `HaloMatch.capability_card` is populated for every published vacant
      and dispatch can call `card.endpoint` without re-querying.
    """
    if isinstance(match, CapabilityCard):
        return match
    card = getattr(match, "capability_card", None)
    if isinstance(card, CapabilityCard):
        return card
    raise EnvelopeFormatError(
        f"search result {type(match).__name__} carries no signed CapabilityCard "
        "(HaloMatch.capability_card is None — was the row published before the "
        "capability_card_blob column existed?)"
    )


async def _pick_winner(matches: list[Any], reputation_oracle: Any | None) -> Any:
    if reputation_oracle is None or not matches:
        return matches[0]
    scored: list[tuple[float, Any]] = []
    dims = ("factual", "logical", "relevance", "honesty", "adoption")
    for m in matches:
        card = _match_to_card(m)
        score = await reputation_oracle.score(card.vacant_id.hex(), dims)
        scored.append((float(score), m))
    scored.sort(key=lambda p: p[0], reverse=True)
    return scored[0][1]


# --- httpx transport (real network) ---------------------------------------


def make_httpx_transport(
    *,
    timeout: float = 60.0,
) -> DispatchTransport:
    """Build a transport callable that POSTs JSON-RPC via httpx.

    Imports httpx lazily so the module is testable without a network
    stack — tests pass a custom `DispatchTransport` callable instead.
    """
    import httpx

    async def _transport(url: str, body: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, json=body)
            r.raise_for_status()
            data: dict[str, Any] = r.json()
            return data

    return _transport


_ = A2APart  # silence unused-import lint
