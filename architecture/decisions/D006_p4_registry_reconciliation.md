# D006 — P4 Registry Spec Reconciliation

**Date:** 2026-05-05
**Author:** P4 implementation session
**Affected components:** P4 Registry / `core/constants.py` / `architecture/CONSTANTS.md`

---

## Background

`dispatch/P4_registry.md` and `architecture/components/P4_registry.md`
together describe a full registry (13 SQLite tables, 25 RPC endpoints, 6
anti-tamper layers, federated/DHT roadmap). Several decisions need
pinning before code lands.

### Issue A — BLAKE3 vs BLAKE2b

`components/P4_registry.md` §3.1 specifies `event_hash = BLAKE3(...)` and
`payload_hash = BLAKE3(canonicalize_json(...))`. The repo's canonical
hash since P0 has been BLAKE2b-256 (`vacant.core.crypto.hash_blake2b`),
which is also what P0 / P1 / P2 logbook entries already use. Adding
BLAKE3 as a runtime dep purely for parity with the spec text introduces
a new transitive dependency for one usage.

### Issue B — Async story

The dispatch says "Async only (`aiosqlite` under the hood)". `sqlmodel`
ships first-class async via `sqlalchemy.ext.asyncio.AsyncSession`. The
combined stack is `sqlalchemy + aiosqlite + sqlmodel`.

### Issue C — Genesis event

The component spec §3.1 calls for a synthetic `seq=1, event_type='register',
actor='registry'` row that anchors the chain. P0/P1/P2 logbooks do not
have a synthetic genesis — chains start at `EMPTY_PREV_HASH`.

### Issue D — 25 RPC endpoints scope

The spec lists 12 write endpoints + 16 read endpoints = 28 endpoints
(some are `internal`). The dispatch caps at 25. The dispatch's example
list is 8 endpoints; the spec's table is the authoritative count.

### Issue E — Anti-tamper layer numbering

The spec lists L1-L6 (§2.4). The dispatch lists 6 layers but in a slightly
different order and combines some. The dispatch is the immediate task
contract.

### Issue F — JCS canonical JSON

`components/P4_registry.md` §3.1 specifies RFC 8785 (JCS) for
canonicalization. The repo already has a private `_canonical_json` in
`core.types` that uses `json.dumps(sort_keys=True, separators=(",", ":"),
ensure_ascii=False)`. JCS is stricter (it specifies number representation
rules); for MVP demo scale the simpler `sort_keys` form suffices and
matches what P0 logbooks already use.

## Decision

### A. BLAKE2b is canonical; BLAKE3 not introduced

Use `vacant.core.crypto.hash_blake2b` (already 32-byte output) for all
P4 hashing. This keeps one canonical hash across the codebase and
avoids introducing `blake3` as a new runtime dep. Spec text is treated
as informative; the cryptographic property required (collision-resistant
32-byte digest) is satisfied by either.

If a future revision standardises on BLAKE3 (e.g. for Sigstore parity),
the swap is local to `core/crypto.py`; P4 imports it through that module
to keep the hash function pluggable.

### B. Async via SQLAlchemy AsyncSession + aiosqlite

`registry/store.py` exposes async-only methods. The store accepts a
SQLAlchemy `AsyncEngine` at construction (DI seam from the dispatch).
For tests we use `sqlite+aiosqlite:///:memory:` or `tmp_path`-backed
files.

### C. No synthetic genesis row

The first event written to a registry instance chains from
`EMPTY_PREV_HASH` (32 zero bytes), matching how P0 logbooks behave. The
spec's "registry-signed genesis" is a Merkle-anchor concept (used to
produce the first epoch root), not a stored row. The
`seal_epoch` Merkle build computes its first leaf from the first real
event.

### D. Endpoint count: ship the canonical 25 the spec table lists; document the rest as future work

The 25 endpoints implemented are the union of the dispatch's "minimum
list" and the spec §3.2 tables, deduped. Bodies for endpoints whose
backing logic belongs to other components (P3 reputation snapshots,
P5 composition links, P6 envelope dispatch) are minimal — they validate
input + return 501 if their backing component isn't wired. OpenAPI
documents all 25.

### E. Anti-tamper layers — exact 6 from dispatch

The 6 layers implemented are the dispatch's enumeration:

1. Signature verify on every write
2. Sequence-number monotonicity per vacant_id
3. Freshness window on attestations (default 30 days)
4. Merkle-root snapshots emitted hourly
5. Anomaly counters per vacant_id (signal, not block)
6. Append-only audit log (DELETE rejected)

The component spec's L5 OTS Bitcoin anchor and L6 federated witness
cosignatures are out of scope for this PR (post-MVP per the spec
§3.4 federation roadmap).

### F. JSON canonicalisation: reuse `core.types._canonical_json`

The same sort-keys + tight separator JSON form used by P0 logbooks is
reused for P4 event payloads. JCS-strict canonicalisation is future
work (would require a dedicated library or hand-rolled implementation).

### G. New constants

`core/constants.py` and `architecture/CONSTANTS.md` add:

- `MERKLE_SNAPSHOT_INTERVAL_S = 3600` — hourly Merkle epoch sealing
  (CONSTANTS.md §Registry, P4 §3 already lists "Merkle snapshot
  interval | 1 hour").
- `REGISTRY_DB_DEFAULT_URL = "sqlite+aiosqlite:///:memory:"` —
  in-memory default for tests.
- `EVENT_LOG_DEFAULT_PAGE_SIZE = 100`,
  `EVENT_LOG_MAX_PAGE_SIZE = 500` — pagination caps from spec §3.2.
- `ANOMALY_REP_JUMP_THRESHOLD = 0.4`,
  `ANOMALY_REP_JUMP_WINDOW_S = 60`,
  `ANOMALY_REVIEW_PER_TARGET_HOUR = 5`,
  `ANOMALY_SPAWN_PER_PARENT_HOUR = 10` — rule-based anomaly thresholds
  (spec §3.2 anomaly table).

## Consequences

- One canonical hash function across the codebase (BLAKE2b).
- The store is async; downstream components consume via `async def`.
- `RegistryBackend` Protocol exists so the swap to federated/DHT is
  local to one module (acceptance criterion).
- The 5 layers of anti-tamper that fit MVP scope are exercised by
  attack tests; L5/L6 (OTS, witness cosign) are documented as future
  work.
