# D009 — P6 Protocol Spec Reconciliation

**Date:** 2026-05-06
**Author:** P6 implementation session
**Affected components:** P6 Protocol / `core/types.py` (additive) / `core/constants.py`

---

## Background

`dispatch/P6_protocol.md` references several fields and behaviours that
either don't yet exist on P0 types or that the spec describes more
richly than the dispatch. This ADR pins the resolved interpretation.

### Issue A — `capability_card.endpoint` field

Dispatch §3 says dispatch "POST direct to target's A2A endpoint (URL
discovered from `capability_card.endpoint`)". P0's `CapabilityCard` has
no `endpoint` field — its fields are `vacant_id`, `capability_text`,
`substrate_spec`, `halo_version`, `signature`.

P6 component spec §3.1 has a much richer Vacant Capability Card
extending the A2A Agent Card (with `endpoint_url`, `interface`, etc.).

### Issue B — `prev_envelope_hash` is a per-pair chain, not the global chain

Dispatch §1 explicitly notes "per-pair chain — not the global logbook
chain". The chain links `(from_vacant_id, to_vacant_id)` envelopes
across calls. Replay protection §6 keys both `sequence_no` and
`prev_envelope_hash` on this pair.

### Issue C — Direct-call invariant + LOCAL exclusion

Dispatch §3 acceptance: "Dispatch never routes through registry".
THEORY_V5 §7.1 confirms: "vacants call each other directly; the
registry is never a routed-through component". LOCAL halos are
excluded from public lookup; owner-direct path uses a separate
`call_local`.

### Issue D — A2A v0.4 / MCP v1.0 envelope detail

The P6 component spec §3.2 shows full A2A `metadata["urn:vacant:v1"]`
mounting. The dispatch's `VacantEnvelope` is a more abstract Pydantic
model. Both can coexist: the Pydantic model is the in-process API; the
A2A wire format is the on-the-wire encoding when traversing HTTPS.

### Issue E — Replay-protect persistence

Dispatch §6: "Persistent (survives restart); SQLite table or part of
P4's schema". For MVP we ship an `InMemoryReplayStore` (sufficient for
unit/integration tests) plus a `SQLiteReplayStore` that uses the same
SQLAlchemy `AsyncEngine` as P4. No new P4 table; the store creates its
own `replay_protect` table.

## Decision

### A. `CapabilityCard` gains an additive `endpoint: str | None = None`

P0's `CapabilityCard` is extended with one optional field:

```python
class CapabilityCard(BaseModel):
    ...
    endpoint: str | None = None
    """A2A endpoint URL for direct calls. None for LOCAL or yet-to-be-
    deployed vacants. P6 dispatch reads this to POST directly."""
```

Default `None` so existing P0/P1/P2/P4 code is unaffected; the
existing tests pass without modification. The card's signing payload
includes `endpoint` so an attacker can't substitute the URL after
issuance.

This is a *purely additive* P0 extension matching the pattern P1 used
for `ResidentForm.parent_id` and the rationale in D003 §C.

### B. `VacantEnvelope` is the P6 Pydantic abstraction

`protocol/envelope.py::VacantEnvelope` carries:

```python
class VacantEnvelope(BaseModel):
    from_vacant_id: VacantId
    to_vacant_id: VacantId
    sequence_no: int
    timestamp: datetime
    prev_envelope_hash: bytes  # 32 bytes, EMPTY_PREV_HASH for first
    payload: A2AMessage
    signature: bytes
```

`A2AMessage` is a small Pydantic wrapper carrying `parts: list[A2APart]`
mirroring the A2A v0.4 `message/send` `params.message` shape. Direct
A2A wire traversal (HTTP body) is `to_a2a_jsonrpc()` / `from_a2a_jsonrpc()`
helpers.

### C. Dispatch never POSTs through the registry

`dispatch.call_capability(...)` queries the registry's
`search_capability` endpoint *for discovery only*; it then opens an
HTTPX client directly against `card.endpoint` and POSTs the envelope.
The registry's `submit_event` and other write endpoints are never
called from this path. An integration test asserts the registry's RPC
log records only `query_capability` reads, no relays.

`call_local(target_card, requester_form, requester_signing_key,
payload, transport)` bypasses the discovery step entirely — used by
owner/parent direct paths.

### D. A2A wire format is via `to_a2a_jsonrpc` helper, not a re-implementation

The Pydantic `VacantEnvelope` is the canonical in-process type. When
emitting on the wire, `to_a2a_jsonrpc(envelope)` produces a JSON-RPC
2.0 `message/send` request whose
`params.message.metadata["urn:vacant:v1"]` carries the
caller_signature, idempotency_key, and sequence_no. `from_a2a_jsonrpc`
parses + verifies in the reverse direction.

For P6 MVP we ship the helpers and exercise them in unit tests; the
HTTP transport itself uses `httpx.AsyncClient` against a `serve.py`
FastAPI router.

### E. Replay-protect ships InMemory + SQLite; same SQLAlchemy engine as P4

`protocol/replay_protect.py` defines:

```python
class ReplayStore(Protocol):
    async def check_and_advance(self, key, sequence_no, prev_hash, new_hash) -> None: ...
```

with two concrete impls: `InMemoryReplayStore` (a dict for tests) and
`SqliteReplayStore` (uses an `AsyncEngine`; creates a `replay_protect`
table on first init). Tests use `InMemoryReplayStore`; the integration
test exercises `SqliteReplayStore` against a fresh in-memory SQLite.

### F. No A2APart subtypes beyond `text`

For MVP the `A2APart` model accepts only `type: "text"` with a `text`
string. Extending to `image / audio / file` parts can land with P7
demo work — the wire schema reserves the field shape.

### G. MCP adapter is minimal

`VacantAsMCPServer` and `MCPClientSubstrate` are implemented as
*adapter classes* with mock-friendly transports — the full MCP wire
protocol is not implemented in P6 (would require pulling in the MCP
SDK). The adapter's contract:

- `VacantAsMCPServer.call_tool(name, arguments) -> dict` translates
  MCP tool calls into in-process `VacantEnvelope` dispatches.
- `MCPClientSubstrate(name, transport).infer(req) -> SubstrateResponse`
  satisfies the P0 `SubstrateBackend` Protocol; the transport is a
  callable handed in by the test/demo.

## Consequences

- One additive field on `CapabilityCard`; no breaking change.
- Dispatch + serve + replay are clean modules with direct-call
  invariant verifiable via integration test.
- LOCAL exclusion from public dispatch + owner-direct path are local
  to dispatch.py.
- MCP adapter is a small, mock-friendly seam; the full wire MCP
  protocol lands with P7 demo as needed.
