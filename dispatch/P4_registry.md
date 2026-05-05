# P4 — Registry

## Goal

Implement P4 Registry — the announcement/discovery substrate. Per the ontology refactor, Registry is **NOT** a routed-through node; it is a per-vacant self-published `capability_card` (the halo) plus an aggregation index layer. Direct vacant-to-vacant calls bypass it.

## Read first (in order)

1. `/CLAUDE.md`
2. `architecture/components/P4_registry.md` — 13 SQLite tables, 25 RPC endpoints, 6 anti-tamper layers
3. `architecture/research/P4_registry_research.md`
4. `architecture/THEORY_V5.md` §7.1 (Registry ontology — per-vacant + 3 implementation models: central MVP / federated / DHT)
5. `architecture/decisions/D001_hibernation_and_stale_revival.md`

## Repo state at start

- P0 and P2 merged.
- `src/vacant/registry/` has only `__init__.py` and `errors.py`.

## Scope

### 1. Models — `src/vacant/registry/models.py`

13 `SQLModel` tables per spec. Migrations in `alembic/versions/`.

Key tables (consult spec for the full 13):

- `vacants` — VacantId, current state, current capability_card hash, last_heartbeat
- `capability_cards` — full halo records, history (versioned, never deleted)
- `attestations` — peer attestations
- `lineage` — parent_id chain
- `audit_log` — append-only signed write log

### 2. Store — `src/vacant/registry/store.py`

Typed CRUD layer over SQLite. **Every write is signature-verified before commit.** Failed verification → `RegistryWriteError`, no partial state.

Async only (`aiosqlite` under the hood). DI: takes a connection factory.

### 3. Halo emission — `src/vacant/registry/halo.py`

- `publish_halo(card, vacant_state) -> HaloRecord` — every active vacant emits its own `CapabilityCard`; registry stores a SIGNED COPY plus index entries.
- LOCAL-state vacants are **not** stored centrally (visibility=none).
- `revoke_halo(vid, reason, signing_key) -> RevocationRecord`

### 4. RPC — `src/vacant/registry/rpc.py`

25 FastAPI endpoints per spec. Each endpoint has Pydantic v2 request/response models. OpenAPI auto-generated. Endpoints include (consult spec for full list):

- `POST /halo` — publish/update
- `GET /halo/{vid}`, `GET /halo?capability=...`
- `POST /attestation`, `DELETE /attestation/{att_id}`
- `GET /lineage/{vid}`, `GET /lineage/{vid}/descendants`
- `GET /audit/snapshot/{ts}` — Merkle snapshot
- ... (full 25 per spec)

### 5. Anti-tamper — `src/vacant/registry/antitamper.py`

The 6 layers from the spec. At minimum:

1. **Signature verify** on every write
2. **Sequence-number monotonicity** per vacant_id (rejects out-of-order writes)
3. **Freshness window** on attestations (default 30 days; configurable)
4. **Merkle-root snapshots** emitted hourly; verifiers can pull historical snapshots
5. **Anomaly counters** per vacant_id (rate of writes, rate of attestation churn) — surfaced as a signal, not a block
6. **Append-only audit log** (no DELETE permitted on this table)

Each layer has its own attack-test suite (see Tests).

### 6. Aggregation — `src/vacant/registry/aggregation.py`

The index layer that consumers query:

- `search_capability(query: str, filters: dict, limit: int) -> list[HaloMatch]` — text + dimension filters
- `rank_by_reputation(matches, dimensions) -> list[HaloMatch]` — uses P3's reputation surface (define a Protocol; P3 plugs in; for now use a stub)
- `lineage_query(vid, direction='descendants'|'ancestors', depth=...) -> list[VacantId]`

Result objects always include the halo signature so consumers can verify independently.

### 7. Visibility — `src/vacant/registry/visibility.py`

- `Visibility(StrEnum)` — `NONE`, `RESTRICTED`, `PUBLIC`.
- `effective_visibility(state, registry_visibility) -> Visibility` — LOCAL state forces NONE regardless of registry_visibility setting.
- Discovery path filters out NONE entries; owner/parent direct lookup bypasses the public path.

## Tests

- `tests/unit/test_registry_store.py` — every CRUD path including reject-invalid-signature
- `tests/unit/test_antitamper.py` — each defense layer has its own attack test that **tries to bypass** and verifies the defense catches it
- `tests/unit/test_visibility.py` — LOCAL is unreachable by stranger lookup; reachable via owner direct path
- `tests/property/test_merkle_snapshot.py` — hypothesis: any single modified row invalidates the snapshot root
- `tests/integration/test_registry_e2e.py` (`@pytest.mark.slow`) — register 5 vacants (mix public + local), run 20 random capability searches, assert visibility rules honored, attestation chains verify
- `tests/integration/test_registry_concurrent_writes.py` (`@pytest.mark.slow`) — 10 concurrent writers, no lost updates, no chain corruption

Coverage target on `src/vacant/registry/`: ≥90%.

## Acceptance

- 13 tables present, 25 RPC endpoints documented in OpenAPI, 6 anti-tamper layers with at least one attack test each
- LOCAL vacants are reachable by owner direct path only (test: stranger lookup returns empty; owner lookup returns the card)
- Architected so the swap from central → federated/DHT is local to one module (a `RegistryBackend` Protocol)
- All previous criteria hold

## Output

PR titled **"P4: registry — schema, RPC, halo aggregation, anti-tamper"**.

## Out of scope

- Federated and DHT backends (post-MVP — central only)
- P3's actual reputation values (use a stub Protocol; P3 plugs in later)
