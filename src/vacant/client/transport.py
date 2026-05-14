"""Transport adapters for the caller SDK.

Two stitched layers:

1. `AggregationSearch` — a typed Protocol the SDK uses to discover
   capable vacants. The MVP implementation,
   `HttpRegistryAggregationSearch`, calls a `vacant serve` registry's
   `/v1/search_capability` endpoint over HTTP.
2. `HttpDispatchTransport` — the per-call POST against a vacant's
   `card.endpoint`. Wraps `httpx.AsyncClient`; same wire format
   `protocol.dispatch.call_local` expects.

Both are async + structural so a test can swap them without subclassing.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import httpx

from vacant.protocol.capability_card import deserialize as deserialize_card
from vacant.protocol.dispatch import DispatchTransport

__all__ = [
    "AggregationSearch",
    "HttpDispatchTransport",
    "HttpRegistryAggregationSearch",
    "make_httpx_dispatch_transport",
]


class AggregationSearch(Protocol):
    """Callable contract for capability search.

    Matches `protocol.dispatch.call_capability(aggregation_search=...)`'s
    expected shape: keyword-only `query` / `include_local` / `limit`,
    returning a list of search results that each carry a
    `capability_card` (raw bytes or already-parsed CapabilityCard).
    """

    async def __call__(
        self,
        *,
        query: str,
        include_local: bool = False,
        limit: int = 20,
    ) -> list[Any]: ...


class _AggMatch:
    """Lightweight ad-hoc match record carrying just `capability_card`.

    `protocol.dispatch._match_to_card` accepts anything with a
    `capability_card` attribute (or a CapabilityCard directly); we
    construct one of these per-result rather than depending on the
    registry's `HaloMatch` row type, so the SDK doesn't need a
    SQLModel dep.
    """

    def __init__(self, capability_card: Any) -> None:
        self.capability_card = capability_card


class HttpRegistryAggregationSearch:
    """`AggregationSearch` over a `vacant serve` registry's HTTP API.

    Calls `GET <registry_url>/v1/search_capability?q=<query>&limit=<n>`
    and parses the response into `_AggMatch` objects. Discovery only —
    the call itself goes direct to `card.endpoint` (the registry is
    never POSTed through, D009 §C).

    Args:
        registry_url: Base URL of a `vacant serve` registry.
        client: Optional pre-existing `httpx.AsyncClient`. When omitted,
            each call creates its own short-lived client.
        timeout_s: Per-request timeout.
    """

    def __init__(
        self,
        registry_url: str,
        *,
        client: httpx.AsyncClient | None = None,
        timeout_s: float = 15.0,
    ) -> None:
        if not registry_url:
            raise ValueError("HttpRegistryAggregationSearch: registry_url is required")
        self._registry_url = registry_url.rstrip("/")
        self._client = client
        self._timeout_s = timeout_s

    async def __call__(
        self,
        *,
        query: str,
        include_local: bool = False,
        limit: int = 20,
    ) -> list[Any]:
        params: dict[str, str | int] = {
            "q": query,
            "limit": int(limit),
            "include_local": str(bool(include_local)).lower(),
        }
        url = f"{self._registry_url}/v1/search_capability"
        if self._client is not None:
            resp = await self._client.get(url, params=params, timeout=self._timeout_s)
        else:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                resp = await client.get(url, params=params)
        resp.raise_for_status()
        rows = resp.json()
        out: list[Any] = []
        for r in rows:
            card_field = r.get("capability_card") if isinstance(r, dict) else None
            if card_field is None:
                continue
            if isinstance(card_field, (bytes, bytearray)):
                card = deserialize_card(bytes(card_field))
            elif isinstance(card_field, str):
                card = deserialize_card(bytes.fromhex(card_field))
            else:
                # Already a structured dict — pass through; the dispatch
                # layer will reject it if shape is wrong.
                card = card_field
            out.append(_AggMatch(capability_card=card))
        return out


class HttpDispatchTransport:
    """`DispatchTransport` over `httpx.AsyncClient`.

    Wraps `make_httpx_dispatch_transport` in a class so SDK consumers
    can hold a single `client` across many calls (one TLS handshake
    amortised over many requests). Stateless from the SDK's
    perspective; the underlying `httpx.AsyncClient` is the only
    resource.
    """

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        timeout_s: float = 30.0,
    ) -> None:
        self._owned = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_s)
        self._timeout_s = timeout_s

    async def __call__(self, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
        resp = await self._client.post(endpoint, json=body, timeout=self._timeout_s)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise TypeError(
                f"HttpDispatchTransport: response from {endpoint!r} is not a dict ({type(data).__name__})"
            )
        return data

    async def aclose(self) -> None:
        """Close the underlying client if the transport owns it."""
        if self._owned:
            await self._client.aclose()


def make_httpx_dispatch_transport(
    *,
    timeout_s: float = 30.0,
) -> Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]:
    """Free-function variant for callers that prefer a plain callable.

    Each invocation opens a fresh `httpx.AsyncClient`. For repeated
    calls prefer `HttpDispatchTransport(client=shared_client)` to reuse
    the connection pool.
    """
    transport: DispatchTransport

    async def _go(endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(endpoint, json=body)
            resp.raise_for_status()
            data = resp.json()
        if not isinstance(data, dict):
            raise TypeError(
                f"make_httpx_dispatch_transport: response from {endpoint!r} is not a dict"
            )
        return data

    transport = _go
    return transport
