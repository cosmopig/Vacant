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

HEARTBEAT_DECAYED_PERIOD_S: Final[int] = 86_400
"""Heartbeat period for a Sunk vacant (decayed cadence).
CONSTANTS.md §Lifecycle / P1 §D5 line 59."""

HEARTBEAT_SUNK_LIVENESS_PERIOD_S: Final[int] = 600
"""Sunk-state custody-attestation heartbeat period (10 min).
CONSTANTS.md §Lifecycle / THEORY_V5 §3 line 340."""

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
