"""Shadow-self drift detection (P1 §3.4 stub).

P1 needs a behavioural fingerprint that downstream code (P3 honesty signal,
P5 graduation gate) can call before the real STYLO Vec16 / PROBE
embeddings land. This module provides:

* `compute_embedding(windows)` — deterministic 16-dim float vector built
  from the BLAKE2b digest of N output windows. Pure stdlib, pure function.
* `AnchorDistribution` — diagonal-covariance Gaussian over the embedding
  space (mean + per-dim std), enough to evaluate Mahalanobis-style drift
  without bringing in numpy. With diagonal covariance the Mahalanobis
  distance reduces to standardised Euclidean — a reasonable demo-scale
  approximation noted in `architecture/research/T1_behavioral_fingerprint.md`.
* `compute_drift(current, anchor)` → float Mahalanobis-style distance.
* `is_drifting(drift, threshold=STYLO_DRIFT_THRESHOLD)` → bool.
* `drift_log_entry(...)` — convenience that writes a `DRIFT_DETECTED`
  log entry; **no automatic state change** (per dispatch §3, the policy
  layer decides what to do with the signal).

The real STYLO Vec16 lands with P3 (research/T1) and will replace
`compute_embedding`; this module's API stays put.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from vacant.core.constants import STYLO_DRIFT_THRESHOLD
from vacant.core.crypto import SigningKey
from vacant.core.types import Logbook, LogEntry

__all__ = [
    "DRIFT_LOG_KIND",
    "EMBEDDING_DIM",
    "AnchorDistribution",
    "compute_drift",
    "compute_embedding",
    "drift_log_entry",
    "is_drifting",
]


EMBEDDING_DIM = 16
"""STYLO Vec16 dimensionality (T1 research)."""

DRIFT_LOG_KIND = "DRIFT_DETECTED"

_EMBED_DIGEST_BYTES = EMBEDDING_DIM  # one float per byte


def _bytes_to_unit_vec(digest: bytes) -> list[float]:
    return [b / 255.0 for b in digest]


def compute_embedding(windows: Sequence[bytes]) -> list[float]:
    """Hash-projection placeholder for STYLO Vec16.

    Returns an `EMBEDDING_DIM`-dim float vector in `[0, 1]^16`. Empty input
    is treated as `[0.0] * EMBEDDING_DIM`.

    Deterministic, pure, no LLM calls — suitable for unit tests and demo
    runs until P3 wires the real embedding.
    """
    h = hashlib.blake2b(digest_size=_EMBED_DIGEST_BYTES)
    for w in windows:
        h.update(len(w).to_bytes(4, "big"))
        h.update(w)
    return _bytes_to_unit_vec(h.digest())


@dataclass(frozen=True)
class AnchorDistribution:
    """Diagonal-covariance reference distribution over embedding space.

    `mean[i]` and `std[i]` describe the historical distribution of feature
    `i`. Std values are floored to `min_std` to avoid division-by-zero on
    constant features (a known artefact of the demo-scale embedding).
    """

    mean: tuple[float, ...]
    std: tuple[float, ...]
    min_std: float = 1e-3

    def __post_init__(self) -> None:
        if len(self.mean) != len(self.std):
            raise ValueError("AnchorDistribution: mean and std length mismatch")
        if any(s < 0 for s in self.std):
            raise ValueError("AnchorDistribution: std must be non-negative")

    @classmethod
    def from_history(cls, history: Iterable[Sequence[float]]) -> AnchorDistribution:
        """Build a diagonal Gaussian from an iterable of past embeddings."""
        rows = [list(r) for r in history]
        if not rows:
            raise ValueError("AnchorDistribution.from_history: history is empty")
        dim = len(rows[0])
        if any(len(r) != dim for r in rows):
            raise ValueError("AnchorDistribution.from_history: ragged rows")
        n = len(rows)
        mean = [sum(col) / n for col in zip(*rows, strict=True)]
        if n == 1:
            std = [0.0] * dim
        else:
            std = [
                math.sqrt(sum((v - mean[i]) ** 2 for v in col) / (n - 1))
                for i, col in enumerate(zip(*rows, strict=True))
            ]
        return cls(mean=tuple(mean), std=tuple(std))


def compute_drift(current: Sequence[float], anchor: AnchorDistribution) -> float:
    """Standardised-Euclidean distance (diagonal-Mahalanobis) from `anchor`.

    Equivalent to `sqrt(sum_i ((x_i - mean_i) / max(std_i, min_std))^2)`.
    """
    if len(current) != len(anchor.mean):
        raise ValueError(
            f"compute_drift: vector dim {len(current)} != anchor dim {len(anchor.mean)}"
        )
    acc = 0.0
    for i, x in enumerate(current):
        sigma = max(anchor.std[i], anchor.min_std)
        z = (x - anchor.mean[i]) / sigma
        acc += z * z
    return math.sqrt(acc)


def is_drifting(drift: float, threshold: float = STYLO_DRIFT_THRESHOLD) -> bool:
    """True iff `drift` ≥ `threshold` (default = `STYLO_DRIFT_THRESHOLD`)."""
    return drift >= threshold


def drift_log_entry(
    *,
    logbook: Logbook,
    signing_key: SigningKey,
    drift: float,
    embedding: Sequence[float],
    threshold: float = STYLO_DRIFT_THRESHOLD,
) -> LogEntry:
    """Append a `DRIFT_DETECTED` log entry. No automatic state change."""
    payload = {
        "drift": drift,
        "threshold": threshold,
        "embedding": list(embedding),
        "above_threshold": is_drifting(drift, threshold),
    }
    return logbook.append(DRIFT_LOG_KIND, payload, signing_key)
