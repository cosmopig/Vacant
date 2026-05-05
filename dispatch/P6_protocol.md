# P6 — Protocol

## Goal

Implement P6 Protocol — A2A/MCP envelope wrapping, capability card serialization, **direct vacant-to-vacant calls (NEVER routed through registry)**, signature verification on every envelope, replay protection.

## Read first (in order)

1. `/CLAUDE.md`
2. `architecture/components/P6_protocol.md`
3. `architecture/THEORY_V5.md` §5 (protocol layer), §7 (registry ontology — confirm direct-call invariant)
4. The A2A v0.4 and MCP v1.0 specs (linked from `P6_protocol.md`). Read enough to ensure envelope compatibility.

## Repo state at start

- P0, P1, P2, P4 merged. (P3 may or may not be merged — if not, use the stub `ReputationProtocol`.)
- `src/vacant/protocol/` has only `__init__.py` and `errors.py`.

## Scope

### 1. Envelope — `src/vacant/protocol/envelope.py`

`VacantEnvelope(BaseModel)` wrapping an A2A message:

- `from_vacant_id: VacantId`
- `to_vacant_id: VacantId`
- `sequence_no: int` (per-pair monotonic)
- `timestamp: datetime`
- `prev_envelope_hash: bytes` (per-pair chain — not the global logbook chain)
- `payload: A2AMessage` (Pydantic typed)
- `signature: bytes` (over canonical-json of all the above except signature)

Methods: `sign(signing_key)`, `verify(pubkey)`, `compute_hash()`.

### 2. Capability card serialization — `src/vacant/protocol/capability_card.py`

- `serialize(card: CapabilityCard) -> bytes` — canonical JSON for halo emission and signing
- `deserialize(b: bytes) -> CapabilityCard`
- `halo_version` field gates forward-compat; deserialize raises `UnsupportedHaloVersionError` if version is unknown to this build

### 3. Dispatch (outgoing) — `src/vacant/protocol/dispatch.py`

`async def call_capability(query: str, requester: ResidentForm, ...) -> A2AResponse`:

1. Look up via `registry.aggregation.search_capability(query)`
2. Score with `reputation.aggregator.get_ranked` → pick UCB winner
3. **Filter**: LOCAL vacants are excluded from the public lookup pool (their visibility is NONE)
4. Build `VacantEnvelope`, sign with requester's key, POST direct to target's A2A endpoint (URL discovered from `capability_card.endpoint`)
5. **Never POST through the registry.** The registry is queried for discovery only; the call goes directly.

For owner→LOCAL-vacant calls, expose a separate `async def call_local(target_vid, ...)` that bypasses lookup and goes direct.

### 4. Serve (incoming) — `src/vacant/protocol/serve.py`

FastAPI router mounted at `/a2a` (and `/mcp` for MCP-adapter calls). For each incoming request:

1. Verify envelope signature against `from_vacant_id`'s pubkey (look up via registry; if not in registry, this is a direct LOCAL call and the caller must already know the vacant)
2. Check `state_machine.can_be_called(my_state)` — reject with 410 GONE if SUNK/ARCHIVED, 423 LOCKED if HIBERNATING
3. Verify `sequence_no` monotonicity for this `(from, to)` pair (replay protection — see §6)
4. Dispatch to the vacant's `behavior_bundle` (this is where the substrate runs)
5. Sign and return response envelope; both directions written to per-pair envelope chain

### 5. MCP adapter — `src/vacant/protocol/mcp_adapter.py`

Bridge between vacant runtime and MCP:

- `VacantAsMCPServer` — exposes a vacant's capabilities as an MCP server so existing MCP-aware clients can call it
- `MCPClientSubstrate` — lets a vacant call MCP servers as part of its behavior (counts as a `substrate_spec` entry)

### 6. Replay protection — `src/vacant/protocol/replay_protect.py`

- Per-pair `(from_vid, to_vid)` sequence-no store
- Reject any envelope where `sequence_no <= last_seen[(from, to)]`
- Reject any envelope where `prev_envelope_hash != stored_chain_tip[(from, to)]`
- Persistent (survives restart); SQLite table or part of P4's schema

## Tests

- `tests/unit/test_envelope.py` — sign/verify roundtrip; tampered envelope rejected; serialization round-trip stable
- `tests/unit/test_capability_card.py` — serialize/deserialize; unknown halo_version rejected
- `tests/unit/test_dispatch.py` — picks UCB winner; LOCAL excluded from public lookup; owner-direct call works against LOCAL
- `tests/unit/test_replay_protect.py`:
  - Replay attempt rejected
  - Out-of-order envelope rejected
  - Forked chain rejected (`prev_envelope_hash` mismatch)
- `tests/integration/test_a2a_full.py` (`@pytest.mark.slow`) — two vacants in-process, one calls the other with a capability request, response is signed, both per-pair chains advance, attestations write to logbooks correctly
- `tests/integration/test_mcp_bridge.py` (`@pytest.mark.slow`) — vacant exposed as MCP server is callable; vacant calling MCP server records the call in its logbook
- `tests/property/test_envelope_chain.py` — hypothesis: any reordering or insertion in a per-pair envelope chain is detected

Coverage target on `src/vacant/protocol/`: ≥90%.

## Acceptance

- Dispatch never routes through registry (verified by integration test asserting registry's RPC log shows only lookup, no relay)
- LOCAL vacants are inaccessible via public dispatch but reachable via `call_local`
- SUNK / ARCHIVED endpoints reject incoming calls with proper status codes
- Replay protection passes attack-tests
- All previous criteria hold

## Output

PR titled **"P6: protocol — envelope, dispatch, MCP bridge, replay protect"**.

## Out of scope

- Substrate execution itself (see `src/vacant/substrate/`; that's a small, parallel piece — implement minimal `MockSubstrate` and `AnthropicSubstrate` here if needed for tests; the full substrate work is part of P7's demo)
- Federated registry routing (post-MVP)
