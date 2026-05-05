# P1 — Runtime

## Goal

Implement P1 Runtime: the 5-state lifecycle machine, heartbeat (with custody-attestation semantics for Sunk), shadow-self drift detection, and the D1–D5 self-replication paths.

## Read first (in order)

1. `/CLAUDE.md` — full
2. `architecture/components/P1_runtime.md` — the spec
3. `architecture/THEORY_V5.md` §3 (lifecycle), §3.6 (cold start), §4.1–4.3 (review eligibility, sunk heartbeat semantics, lineage)
4. `architecture/decisions/D001_hibernation_and_stale_revival.md`
5. `src/vacant/core/types.py` (already implemented in P0; extend, do not modify)

## Repo state at start

- P0 is merged. `src/vacant/core/` is complete.
- `src/vacant/runtime/` exists but only has `__init__.py` and `errors.py`.

## Scope

### 1. State machine — `src/vacant/runtime/state_machine.py`

- `Event(StrEnum)` — `TICK`, `HEARTBEAT`, `CALL_RECEIVED`, `REVIEW_RECEIVED`, `REVIVE_REQUESTED`, `ARCHIVE_REQUESTED`, `SPAWN_REQUESTED`.
- `VacantStateMachine` class with explicit `(state, event) → state'` table (dict-driven, not if/else cascades).
- `can_review(state) -> bool` — returns False for SUNK and ARCHIVED (§4.1). Actually used by P3 reputation.
- `can_be_called(state) -> bool` — ACTIVE and LOCAL only.
- `is_runnable(state) -> bool` — ACTIVE and LOCAL only (LOCAL is fully functional, just not publicly discoverable).
- `requires_revive(state) -> bool` — STALE only.

Encode the **Sunk heartbeat = identity custody attestation** semantics in the type system: when state is SUNK and event is HEARTBEAT, the resulting log entry's `payload` must include `key_in_custody: bool` and `liveness: false` (it's not alive, the key is just still in trusted hands).

### 2. Heartbeat — `src/vacant/runtime/heartbeat.py`

- `HeartbeatScheduler` — async scheduler; when running, signs and writes a HEARTBEAT entry to the logbook on `HEARTBEAT_INTERVAL_S` cadence.
- Payload differs per state:
  - `ACTIVE` / `LOCAL`: `{liveness: true}`
  - `HIBERNATING`: `{liveness: dormant, last_active: ts}`
  - `STALE`: `{liveness: false, awaiting_revive: true}`
  - `SUNK`: `{liveness: false, key_in_custody: true}` ← load-bearing; lineage attribution depends on this
  - `ARCHIVED`: scheduler does not run

### 3. Shadow-self — `src/vacant/runtime/shadow_self.py`

- `ShadowSelf` — STYLO-style behavioral fingerprint. For now, a stub that hashes the last N output windows projected to a 16-dim float vector. The real STYLO embedding plugs in via P3.
- `compute_drift(current_vec, anchor_distribution) -> float` — Mahalanobis distance.
- `is_drifting(drift, threshold=STYLO_DRIFT_THRESHOLD) -> bool`
- Drift events emit a `DRIFT_DETECTED` log entry (not auto-state-change; the policy layer decides).

### 4. Spawn / D-series — `src/vacant/runtime/spawn.py`

Implement the five self-replication paths. Each takes a parent `ResidentForm` and returns a child `ResidentForm` with `parent_id` set, fresh keypair, and inherited / mutated `behavior_bundle` per the path:

- **D1 clone-with-mutation** — new key, copy bundle, apply small policy mutation
- **D2 subagent-bud** — new key, narrowed `tool_whitelist` (closed child; default `registry_visibility=none`)
- **D3 capability-fork** — new key, new bundle aimed at a different capability declared by parent
- **D4 lineage-merge** — new key, bundle = merge of two parent bundles (requires both parents' signed consent)
- **D5 cross-substrate respawn** — new key, same bundle, different `substrate_spec`

**Path A is deprecated; do not implement.** Path Zero / B / C may be exposed via `bootstrap.py` later but are out of scope here.

Every spawn writes a `SPAWN` entry in parent's logbook AND a `BIRTH` entry in child's logbook referencing parent.

### 5. Lifecycle loop — `src/vacant/runtime/loop.py`

- `RuntimeLoop` — async; pumps events into the state machine, schedules heartbeats, persists logbook deltas.
- DI: takes a `LogbookStore` interface (so P4 can later supply the real backend).

### 6. Tests

- `tests/unit/test_state_machine.py` — every `(state, event)` pair tested. Property test: random valid event sequences never reach an invalid state.
- `tests/unit/test_heartbeat.py` — heartbeat signs correctly per state; SUNK heartbeat carries `key_in_custody` attestation.
- `tests/unit/test_shadow_self.py` — drift fires past threshold; doesn't fire on natural variance.
- `tests/unit/test_spawn.py` — each D1–D5 produces correct child structure; parent and child logbooks updated atomically.
- `tests/property/test_runtime_invariants.py`:
  - SUNK → ACTIVE only via REVIVE
  - SUNK `can_review()` always False
  - Logbook only grows
- `tests/integration/test_runtime_lifecycle.py` (`@pytest.mark.slow`) — vacant goes ACTIVE → HIBERNATING → STALE → SUNK over simulated time, full logbook chain valid throughout.

Coverage target on `src/vacant/runtime/`: ≥90%.

## Acceptance

- All P0 acceptance criteria still hold.
- `can_review(SUNK) is False` and `can_review(ARCHIVED) is False`.
- Each D1–D5 is exercised by a named test, listed in PR description.
- LOCAL is treated as runnable (`is_runnable(LOCAL) is True`).
- CI green.

## Output

PR titled **"P1: runtime — state machine + heartbeat + spawn"**.

## Out of scope

- Identity layer (P2 owns keys & wash cost; here you call `core.crypto` directly)
- Registry publication (P4)
- Reputation effects of drift (P3 consumes the drift signal)
