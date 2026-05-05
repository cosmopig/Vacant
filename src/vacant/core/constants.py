"""Numeric thresholds shared across components.

Every constant cites `architecture/CONSTANTS.md` plus the underlying spec
section. Adding a new constant here REQUIRES a matching row in CONSTANTS.md
(see `architecture/decisions/D002_p0_bootstrap_constants.md` for the P0
reconciliation between `dispatch/P0_bootstrap.md` and CONSTANTS.md).
"""

from __future__ import annotations

from typing import Final

# --- Lifecycle (P1 Runtime) ---------------------------------------------------

HEARTBEAT_BASE_PERIOD_S: Final[int] = 60
"""Demo-default heartbeat period for an Active vacant.
CONSTANTS.md §Lifecycle / P1 §D2."""

HEARTBEAT_HIBERNATING_PERIOD_S: Final[int] = 86_400
"""Heartbeat period while in HIBERNATING (one minimal attestation per 24h).
CONSTANTS.md §Lifecycle / P1 §D6 line 73."""

HEARTBEAT_DECAYED_PERIOD_S: Final[int] = HEARTBEAT_HIBERNATING_PERIOD_S
"""Back-compat alias for HEARTBEAT_HIBERNATING_PERIOD_S (kept since P0).
The "(Sunk)" label in CONSTANTS.md was an artefact of an earlier pass;
THEORY_V5 §4.2 splits SUNK out at 10 min. See D003."""

HEARTBEAT_SUNK_LIVENESS_PERIOD_S: Final[int] = 600
"""Sunk-state custody-attestation heartbeat period (10 min).
CONSTANTS.md §Lifecycle / THEORY_V5 §4.2 / §3 line 340."""

IDEMPOTENCY_WINDOW_S: Final[int] = 86_400
"""Window in which a (vacant_id, request_id) tuple must dedupe.
CONSTANTS.md §Lifecycle / P1 §3.2."""

STALE_AFTER_HIBERNATING_DAYS: Final[int] = 30
"""Hibernating → Stale-flag transition threshold (no service ≥ 30 days).
CONSTANTS.md §Lifecycle / D001."""

ARCHIVED_AFTER_SUNK_DAYS: Final[int] = 180
"""Sunk → Archived transition threshold (180 days post-Sunk).
CONSTANTS.md §Lifecycle / THEORY_V5 §3 line 318."""

WARMUP_WINDOW_S: Final[int] = 86_400
"""Warmup-ceremony observation window after Stale → Active.
CONSTANTS.md §Lifecycle / P1 §3.3.1 line 191."""

WARMUP_REQUIRED_HEARTBEATS: Final[int] = 5
"""Number of valid heartbeats required during warmup.
CONSTANTS.md §Lifecycle / P1 §3.3.1 line 205."""

# --- Behavioral fingerprinting -----------------------------------------------

STYLO_DRIFT_THRESHOLD: Final[float] = 3.5
"""Mahalanobis threshold on STYLO Vec16 used as drift trigger.
CONSTANTS.md §Lifecycle / THEORY_V5 §3 line 152. Heuristic, not a p-value."""

# --- Halo / Capability card --------------------------------------------------

DEFAULT_HALO_VERSION: Final[int] = 1
"""Initial value of `CapabilityCard.halo_version` when first published.
dispatch/P0_bootstrap.md §4."""

# --- Crypto primitives -------------------------------------------------------

HASH_DIGEST_BYTES: Final[int] = 32
"""Output size of `vacant.core.crypto.hash_blake2b` in bytes."""

ED25519_PUBLIC_KEY_BYTES: Final[int] = 32
"""Length of a raw Ed25519 public key (NaCl encoding)."""

ED25519_SIGNATURE_BYTES: Final[int] = 64
"""Length of a raw Ed25519 signature."""

# --- Identity (P2) -----------------------------------------------------------

PEER_ATTESTATION_FRESHNESS_WINDOW_DAYS: Final[int] = 30
"""Default validity window for a `PeerAttestation` (issued_at + 30d).
CONSTANTS.md §Identity / P2 §4."""

MIN_VOUCHERS_FOR_L3_PROMOTION: Final[int] = 3
"""Default minimum number of valid peer attestations required to promote
an `L2Identity` to `L3Identity`. CONSTANTS.md §Identity / P2 §2."""

FEDERATION_ROOT_THRESHOLD_MVP: Final[int] = 2
FEDERATION_ROOT_COUNT_MVP: Final[int] = 5
"""MVP attestation root set: 2-of-5. CONSTANTS.md §Identity /
T4_attestation_bootstrap."""

FEDERATION_ROOT_THRESHOLD_TARGET: Final[int] = 3
FEDERATION_ROOT_COUNT_TARGET: Final[int] = 9
"""Long-term target attestation root set: 3-of-9. CONSTANTS.md §Identity /
T4_attestation_bootstrap."""

WASH_COST_FALSE_CLAIM_WEIGHT_DEFAULT: Final[float] = 1.0
"""Multiplier on the per-history-entry forgery cost (P2 §3 / D004 §A).
Tests vary this to verify cost increases monotonically with false-claim
weight."""

# Ed25519 multicodec prefix used by the W3C `did:key` method (§6.1).
ED25519_MULTICODEC_PREFIX: Final[bytes] = b"\xed\x01"

# --- Registry (P4) -----------------------------------------------------------

MERKLE_SNAPSHOT_INTERVAL_S: Final[int] = 3600
"""Hourly Merkle epoch sealing cadence. CONSTANTS.md §Registry / P4 §3."""

EVENT_LOG_DEFAULT_PAGE_SIZE: Final[int] = 100
EVENT_LOG_MAX_PAGE_SIZE: Final[int] = 500
"""Read pagination caps for `/v1/event_log/{vid}` (P4 §3.2)."""

ANOMALY_REP_JUMP_THRESHOLD: Final[float] = 0.4
ANOMALY_REP_JUMP_WINDOW_S: Final[int] = 60
ANOMALY_REVIEW_PER_TARGET_HOUR: Final[int] = 5
ANOMALY_SPAWN_PER_PARENT_HOUR: Final[int] = 10
"""Rule-based anomaly thresholds (P4 §3.2 anomaly table). Surfaced as
signals; the engine raises a `triggered` flag rather than auto-blocking."""

REGISTRY_DB_DEFAULT_URL: Final[str] = "sqlite+aiosqlite:///:memory:"
"""Default SQLAlchemy async URL for in-memory testing. D006 §B."""
