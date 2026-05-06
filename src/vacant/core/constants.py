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
"""Hibernating → Stale-flag transition threshold (no service >= 30 days).
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

# --- Reputation (P3) ---------------------------------------------------------

REPUTATION_DIMS: Final[tuple[str, ...]] = (
    "factual",
    "logical",
    "relevance",
    "honesty",
    "adoption",
)
"""Five reputation dimensions. P3 §3.2 / D008 §A."""

BETA_BASE_PRIORS: Final[dict[str, tuple[float, float]]] = {
    "factual": (1.0, 1.0),
    "logical": (1.0, 1.0),
    "relevance": (1.0, 1.0),
    "honesty": (2.0, 1.0),
    "adoption": (1.0, 3.0),
}
"""Base Beta priors per dimension. P3 §3.2 / D008 §A.

CONSTANTS.md previously listed (1.5, 1.0) for F/L/R; that was the
worked example's L1-attestation-applied value being mistakenly imported
as the base. The L1 +0.5alpha boost is applied separately in cold_start.py
so the bonus is auditable rather than baked in."""

DIM_HALF_LIFE_DAYS: Final[dict[str, int]] = {
    "factual": 90,
    "logical": 180,
    "relevance": 60,
    "honesty": 30,
    "adoption": 90,
}
"""Per-dimension half-life. P3 §3.2 / CONSTANTS.md §Reputation."""

SOURCE_BASE_WEIGHTS: Final[dict[str, float]] = {
    "ground_truth": 1.0,
    "caller_review": 0.6,
    "peer_review": 0.4,
    "self_eval": 0.05,
    "adoption_event": 0.3,
    "redteam_probe": 0.8,
}
"""Per-source base weights. P3 §3.4 table 1 / CONSTANTS.md §Reputation."""

SAME_BASE_MODEL_DISCOUNT: Final[float] = 0.5
SAME_MODEL_HEAVY_DISCOUNT: Final[float] = 0.25
"""Same-base-model peer review discount; >5 reviews/30d → heavier discount.
P3 §3.4.1."""

REVIEWER_CREDIBILITY_FLOOR: Final[float] = 0.3
"""Reviewer credibility floor; even low-rep reviewers count for at least 0.3.
P3 §3.4.2."""

NOVELTY_DECAY_COEFFICIENT: Final[float] = 0.4
"""Per-repeat-review novelty decay. P3 §3.4.3."""

COLLUSION_DENSITY_THRESHOLD: Final[float] = 0.6
COLLUSION_RECIPROCITY_THRESHOLD: Final[float] = 0.7
COLLUSION_SEVERE_DENSITY: Final[float] = 0.8
COLLUSION_SEVERE_MULTIPLIER: Final[float] = 0.1
"""Collusion graph thresholds. P3 §3.4.4."""

UCB_C_BASE: Final[float] = 1.0
UCB_C_EXPLORE: Final[float] = 0.5
UCB_CONSERVATIVE_C_EXPLORE: Final[float] = 0.1
"""UCB exploration coefficients. P3 §3.7."""

N_MIN_FOR_STABLE_SCORE: Final[int] = 30
N_SHOW_MIN_THRESHOLD: Final[int] = 10
"""Sample-size thresholds for stable scoring + UI display. P3 §3.7-§3.8."""

COLD_START_FLOORS_BY_LEVEL: Final[dict[str, float]] = {
    "L0": 0.0,
    "L1": 0.05,
    "L2": 0.10,
    "L3": 0.15,
}
"""Cold-start UCB floor by attestation level. P3 §3.7."""

S_REF_USDC: Final[float] = 100.0
"""Reference stake amount (USDC equivalent) for stake-bonus normalisation.
P3 §3.7."""

L1_ATTESTATION_ALPHA_BOOST: Final[float] = 0.5
L3_VOUCH_ALPHA_BOOST: Final[float] = 0.3
"""Cold-start alpha boosts for L1 attestation (per F/L/R dim) and L3 vouch
(per voucher, applied to H). P3 §3.8."""

NETWORK_EXPLORATION_FLOOR: Final[float] = 0.01
"""Minimum fraction of traffic reserved for new vacants. P3 §3.7 line 343."""

DIMENSION_CORRELATION_ALERT_THRESHOLD: Final[float] = 0.6
"""Cross-dimension correlation alert (anti-Goodhart). P3 §3.6 line 290."""

PORTABILITY_FACTOR_MAX_BONUS: Final[float] = 0.10
"""Maximum portability bonus added to UCB call_score for vacants serving
multiple substrates. P3-derived; CONSTANTS.md §Reputation."""

IDLE_REVIEW_THRESHOLD_S: Final[int] = 3600
"""How long a vacant must be idle before being eligible to peer-review
new vacants. Cold-start §3.6 hook."""

SAME_CONTROLLER_TEMPORAL_THRESHOLD: Final[float] = 0.70
SAME_CONTROLLER_BEHAVIOR_THRESHOLD: Final[float] = 0.88
SAME_CONTROLLER_DECLARED_STRENGTH: Final[float] = 1.0
"""Same-controller detection thresholds. T5 §3.3 / D008 §C."""
