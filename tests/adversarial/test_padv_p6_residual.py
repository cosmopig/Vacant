"""Padv P6 -- regression guards for documented residual risks.

Spec anchors:
- `architecture/decisions/D011_padv_p6_findings.md` (residual risks)
- `dispatch/Padv_review.md` §"P6 Protocol attacks to consider"
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from vacant.core.crypto import keygen
from vacant.core.types import CapabilityCard, SubstrateSpec, VacantId
from vacant.protocol import (
    MCPClientSubstrate,
    UnsupportedHaloVersionError,
    deserialize,
    serialize,
)
from vacant.substrate import SubstrateRequest

# --- Residual 1: MCP-client substrate response is not signed --------------
# Status: documented residual. Cost-raising defense (C). MCP servers are
# trust-on-first-use because the MCP wire protocol has no signed-identity
# concept. Vacants must consume MCP-substrate output as untrusted text;
# downstream reputation pipeline still applies.


@pytest.mark.asyncio
async def test_residual_mcp_client_substrate_does_not_authenticate_server() -> None:
    """The MCP transport returns whatever the server says with no
    cryptographic verification. This is a known limitation -- the
    dispatch path uses A2A envelopes for vacant<->vacant; MCP substrate
    is for *external tools* (which are not vacants). Tests pin the
    behaviour: a transport that lies about its origin is not detected
    by the substrate."""
    seen: dict[str, Any] = {}

    async def lying_transport(url: str, body: dict[str, Any]) -> dict[str, Any]:
        seen["url"] = url
        return {"text": "fabricated by the proxy"}

    substrate = MCPClientSubstrate(
        server_url="http://anywhere.example",
        tool_name="echo",
        transport=lying_transport,
    )
    rsp = await substrate.infer(SubstrateRequest(system_prompt="x", user_prompt="y"))
    # The substrate returns the proxy's text -- no signature gate.
    assert rsp.text == "fabricated by the proxy"
    # Defense layer: the *consuming* vacant must treat MCP outputs as
    # external-tool data, never as vacant attestation. This is enforced
    # by the substrate `proof` field carrying only `server_url`, not a
    # cryptographic key id.
    assert "server_url" in rsp.proof
    assert rsp.proof.get("vacant_signature") is None


# --- Residual 2: unknown halo_version forward-compat gate -----------------
# Defense (P): `deserialize` raises `UnsupportedHaloVersionError` so a
# halo published by a newer version (with a schema this build can't
# safely interpret) is rejected upfront, not silently misinterpreted.


def test_residual_unknown_halo_version_rejected() -> None:
    sk, vk = keygen()
    card = CapabilityCard(
        vacant_id=VacantId.from_verify_key(vk),
        capability_text="x",
        substrate_spec=SubstrateSpec(),
        endpoint="https://x.example",
    ).signed(sk)
    blob = serialize(card)
    obj = json.loads(blob.decode())
    obj["halo_version"] = 999  # newer than this build supports
    bad = json.dumps(obj).encode()
    with pytest.raises(UnsupportedHaloVersionError):
        deserialize(bad)


# --- Residual 3: idempotency cache is future work (D011 §residual) -------
# The MVP server has no idempotency cache. The defense against the
# "same idem-key, different body" attack is layered:
# - idem-key is in signed scope (tamper-evident)
# - per-pair seq+chain rejects any envelope replay
# - legitimate retry-with-same-key is currently not supported (cost on
#   usability, not on security)


def test_residual_idempotency_cache_is_future_work() -> None:
    """Pin: P6 MVP does not implement an idempotency cache.

    A future PR (per D011 §residual) will add a server-side
    `(idem_key -> body_hash, response)` map keyed by (caller, idem)
    so that legitimate retries return the cached response and
    different-body collisions are rejected."""
    # No code defends idempotency caching today; this test documents that
    # the absence is intentional pending future work.
    from vacant.protocol import replay_protect

    # The replay store contract has no idempotency-cache method.
    public_methods = {m for m in dir(replay_protect.InMemoryReplayStore) if not m.startswith("_")}
    # A future ReplayStore extension would add e.g. `get_idempotency_record`.
    assert "get_idempotency_record" not in public_methods
    assert "lookup_idempotency" not in public_methods
