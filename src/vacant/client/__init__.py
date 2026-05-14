"""`vacant.client` — caller-side SDK (technical.html §Layer 3 "Caller SDK").

A clean, narrow surface for *non-resident clients* — software that wants
to call vacants but is not itself a vacant. Wraps `protocol.dispatch`
with a stateful client that handles:

- Caller keypair management (an ephemeral keypair if no `signing_key`
  is supplied — clients are not residents, so they don't need
  long-lived identities).
- Registry lookup against an HTTP `RegistryRPC` (or a callable
  aggregation_search for unit tests).
- Capability-card resolution + direct A2A POST to `card.endpoint`.
- Optional per-pair response chain verification via a
  `ReplayStore` injection.

Why a separate package? Currently `vacant call <vid>` works via the
CLI, and library code can `import vacant.protocol.dispatch`, but neither
is named "Caller SDK". technical.html §Layer 3 explicitly factors this
out — clients shouldn't have to know about runtime state machines,
heartbeats, or the lifecycle. The SDK is just *call this capability,
get a response*.

Usage:

    from vacant.client import VacantClient

    async with VacantClient.ephemeral(registry_url="http://reg") as cli:
        result = await cli.call_capability(
            "summarize", "Hello, please summarize War and Peace."
        )
        print(result.response_text)

The SDK never exposes runtime / spawn / shadow-self APIs — those are
for residents.
"""

from __future__ import annotations

from vacant.client.client import (
    VacantCallResult,
    VacantClient,
    VacantClientError,
)
from vacant.client.transport import (
    AggregationSearch,
    HttpDispatchTransport,
    HttpRegistryAggregationSearch,
    make_httpx_dispatch_transport,
)

__all__ = [
    "AggregationSearch",
    "HttpDispatchTransport",
    "HttpRegistryAggregationSearch",
    "VacantCallResult",
    "VacantClient",
    "VacantClientError",
    "make_httpx_dispatch_transport",
]
