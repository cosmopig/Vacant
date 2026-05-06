# D002 — P0 Bootstrap Constants Reconciliation

**Date:** 2026-05-05
**Author:** P0 implementation session
**Affected components:** P0 / core/constants.py, future P1 Runtime

---

## Background

`dispatch/P0_bootstrap.md` §4 lists a starter constants block that disagrees
with `architecture/CONSTANTS.md` (the canonical numeric source of truth) on
which lifecycle thresholds are time-based. Specifically the dispatch sketch
suggests:

```python
HEARTBEAT_INTERVAL_S: int = ...   # §3.x
HIBERNATING_AFTER_S: int = ...    # §3.x
STALE_AFTER_DAYS: int = 180       # §4.1
SUNK_AFTER_DAYS: int = ...        # §3.x
ARCHIVED_AFTER_DAYS: int = ...    # §3.x
```

`CONSTANTS.md` §Lifecycle and `THEORY_V5.md` §3 / D001 contradict three of
these:

| Dispatch sketch | Canonical reality |
|---|---|
| `HIBERNATING_AFTER_S` (time-based) | event-driven: budget exhausted OR explicit signal (D001) |
| `STALE_AFTER_DAYS = 180` cited as §4.1 | `STALE_AFTER_HIBERNATING_DAYS = 30` (D001 / CONSTANTS.md §Lifecycle) |
| `SUNK_AFTER_DAYS` (time-based) | event-driven: reputation/quality signal (NOT budget, NOT pure time) |

`§4.1` of THEORY_V5 covers *review eligibility per state*; the `180` figure
matches `Sunk → Archived = 180 days`, not Stale.

CLAUDE.md is explicit: "If a value here disagrees with a spec section, the
spec wins — open an ADR."

## Decision

For P0, `src/vacant/core/constants.py` ships **only** the numeric thresholds
that the canonical spec actually pins as time-based, plus the hash / halo
basics that downstream components will already need to import:

```python
HEARTBEAT_BASE_PERIOD_S         = 60      # CONSTANTS.md §Lifecycle / P1 §D2
HEARTBEAT_DECAYED_PERIOD_S      = 86400   # CONSTANTS.md §Lifecycle / P1 §D5
HEARTBEAT_SUNK_LIVENESS_PERIOD_S = 600    # CONSTANTS.md §Lifecycle / THEORY_V5 §3
IDEMPOTENCY_WINDOW_S            = 86400   # CONSTANTS.md §Lifecycle / P1 §3.2
STALE_AFTER_HIBERNATING_DAYS    = 30      # CONSTANTS.md §Lifecycle / D001
ARCHIVED_AFTER_SUNK_DAYS        = 180     # CONSTANTS.md §Lifecycle / THEORY_V5 §3 line 318
WARMUP_WINDOW_S                 = 86400   # CONSTANTS.md §Lifecycle / P1 §3.3.1
WARMUP_REQUIRED_HEARTBEATS      = 5       # CONSTANTS.md §Lifecycle / P1 §3.3.1
STYLO_DRIFT_THRESHOLD           = 3.5     # CONSTANTS.md §Lifecycle / THEORY_V5 §3
DEFAULT_HALO_VERSION            = 1       # P0 dispatch §4
HASH_DIGEST_BYTES               = 32      # blake2b digest used by core/crypto
```

Names that the dispatch sketch implied but that are **not exported** because
the underlying transition is event-driven, not timer-driven:

- `HIBERNATING_AFTER_S` — Active → Hibernating fires on budget-exhausted /
  explicit signal (D001 §1).
- `SUNK_AFTER_DAYS` — Any → Sunk fires on reputation/quality signal, not
  elapsed time (D001 §1, THEORY_V5 §3).

P1 owns the actual state-machine transition predicates and may introduce
event-driven thresholds (e.g. budget caps, reputation-floor multipliers) when
it needs them; CONSTANTS.md will be updated in the same PR.

The dispatch's `STALE_AFTER_DAYS = 180 # §4.1` line is a typo:
`STALE_AFTER_HIBERNATING_DAYS = 30` is the correct value, with the `180`
figure belonging to `ARCHIVED_AFTER_SUNK_DAYS`. P0 ships both with their
canonical names.

## Consequences

- Downstream P1 starts from a constants module that compiles and is
  self-consistent with CONSTANTS.md.
- No magic numbers introduced at the P0 layer. Adding event-driven
  thresholds is an explicit P1 task, gated by a CONSTANTS.md update.
- The `dispatch/P0_bootstrap.md` sketch is treated as informative, not
  normative; CONSTANTS.md is normative.
