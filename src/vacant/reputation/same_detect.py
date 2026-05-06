"""Same-* detection (P3 §3.4 / T5 / dispatch §5).

Three lines, each returning a `SameDetectSignal`:

- `same_controller`: T5's three-layer pipeline (declared link → temporal
  correlation → behavioural similarity).
- `same_substrate`: shared base-model family.
- `same_stylo`: STYLO-Vec16 cosine similarity (consumes P1's
  `shadow_self.compute_embedding`).

**Framing (CLAUDE.md §Things to NOT do):** these *raise cost*, they do
**not prevent**. The signal output biases per-review weight in the
aggregator; nothing here blocks writes.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from vacant.core.constants import (
    SAME_CONTROLLER_BEHAVIOR_THRESHOLD,
    SAME_CONTROLLER_DECLARED_STRENGTH,
    SAME_CONTROLLER_TEMPORAL_THRESHOLD,
    SAME_SIGNAL_DISCOUNT_FLOOR,
)
from vacant.core.types import VacantId

__all__ = [
    "SameDetectSignal",
    "cosine_similarity",
    "cross_correlation",
    "discount_from_signals",
    "same_controller",
    "same_stylo",
    "same_substrate",
]


@dataclass(frozen=True)
class SameDetectSignal:
    """Output of every same-* detector.

    `strength` ∈ [0, 1] is monotone in suspicion. The aggregator uses
    `max(SAME_SIGNAL_DISCOUNT_FLOOR, 1 - max(strength))` as a per-review
    cost-raising multiplier, so strength=0 → no penalty and strength=1
    leaves at least the floor (CLAUDE.md «same-* is cost-raising not
    preventing» — D015).

    `suspected_cluster` includes both probe and target vacant ids when
    the signal fires; empty when strength is 0.
    """

    strength: float
    suspected_cluster: frozenset[VacantId]
    rationale: str


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity in [-1, 1] (returns 0.0 for zero-norm inputs)."""
    if len(a) != len(b):
        raise ValueError(f"vector dim mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def cross_correlation(a: Sequence[float], b: Sequence[float]) -> float:
    """Pearson correlation coefficient ∈ [-1, 1] for two equal-length
    series. Returns 0.0 if either has zero variance.
    """
    if len(a) != len(b):
        raise ValueError(f"series dim mismatch: {len(a)} vs {len(b)}")
    n = len(a)
    if n == 0:
        return 0.0
    mean_a = sum(a) / n
    mean_b = sum(b) / n
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b, strict=True))
    var_a = sum((x - mean_a) ** 2 for x in a)
    var_b = sum((y - mean_b) ** 2 for y in b)
    if var_a == 0 or var_b == 0:
        return 0.0
    return cov / math.sqrt(var_a * var_b)


# --- Same-controller (T5 three-layer pipeline) ------------------------------


def same_controller(
    a: VacantId,
    b: VacantId,
    *,
    declared_same: bool = False,
    common_ancestor: bool = False,
    heartbeat_a: Sequence[float] | None = None,
    heartbeat_b: Sequence[float] | None = None,
    behavior_a: Sequence[float] | None = None,
    behavior_b: Sequence[float] | None = None,
    temporal_threshold: float = SAME_CONTROLLER_TEMPORAL_THRESHOLD,
    behavior_threshold: float = SAME_CONTROLLER_BEHAVIOR_THRESHOLD,
) -> SameDetectSignal:
    """T5 §3.2 three-layer same-controller detection.

    Layer 0 (declared): `controller_id` match or shared ancestor → 1.0.
    Layer 1 (temporal): cross-correlation of heartbeat series; strength
    proportional to `(corr - threshold) / (1 - threshold)`.
    Layer 2 (behaviour): cosine similarity over behavioural fingerprints
    (capability text embedding or STYLO Vec16); strength proportional
    to `(sim - threshold) / (1 - threshold)`.

    The detector takes the **max** of all layers that fire -- once any
    layer is positive, downstream weight discount applies.
    """
    if a == b:
        return SameDetectSignal(
            strength=0.0,
            suspected_cluster=frozenset(),
            rationale="self-pair (a == b)",
        )

    rationale_parts: list[str] = []
    strength = 0.0

    # Layer 0
    if declared_same:
        rationale_parts.append("declared controller_id match")
        strength = max(strength, SAME_CONTROLLER_DECLARED_STRENGTH)
    elif common_ancestor:
        rationale_parts.append("common parent_id ancestor")
        strength = max(strength, SAME_CONTROLLER_DECLARED_STRENGTH)

    # Layer 1
    if heartbeat_a is not None and heartbeat_b is not None:
        corr = cross_correlation(heartbeat_a, heartbeat_b)
        if corr > temporal_threshold:
            l1 = (corr - temporal_threshold) / max(1.0 - temporal_threshold, 1e-9)
            l1 = min(max(l1, 0.0), 1.0)
            rationale_parts.append(f"heartbeat corr {corr:.2f} > {temporal_threshold:.2f}")
            strength = max(strength, l1)

    # Layer 2
    if behavior_a is not None and behavior_b is not None:
        sim = cosine_similarity(behavior_a, behavior_b)
        if sim > behavior_threshold:
            l2 = (sim - behavior_threshold) / max(1.0 - behavior_threshold, 1e-9)
            l2 = min(max(l2, 0.0), 1.0)
            rationale_parts.append(f"behaviour sim {sim:.2f} > {behavior_threshold:.2f}")
            strength = max(strength, l2)

    cluster = frozenset({a, b}) if strength > 0 else frozenset()
    return SameDetectSignal(
        strength=strength,
        suspected_cluster=cluster,
        rationale=" + ".join(rationale_parts) if rationale_parts else "no signal",
    )


# --- Same-substrate ---------------------------------------------------------


def same_substrate(
    a: VacantId,
    b: VacantId,
    *,
    family_a: str,
    family_b: str,
) -> SameDetectSignal:
    """Strength = 1.0 iff `family_a == family_b`, else 0.

    "Strength = 1" means full P3 §3.4.1 discount applies; the aggregator
    halves weight (and quarter-weight if many recent reviews) at the
    review-weighting step. The actual numeric discount lives in
    `aggregator.py`; this detector just emits the binary signal.
    """
    if a == b:
        return SameDetectSignal(
            strength=0.0,
            suspected_cluster=frozenset(),
            rationale="self-pair (a == b)",
        )
    if family_a == family_b:
        return SameDetectSignal(
            strength=1.0,
            suspected_cluster=frozenset({a, b}),
            rationale=f"shared base_model_family {family_a!r}",
        )
    return SameDetectSignal(
        strength=0.0,
        suspected_cluster=frozenset(),
        rationale=f"distinct families ({family_a} vs {family_b})",
    )


# --- Same-stylo -------------------------------------------------------------


def same_stylo(
    a: VacantId,
    b: VacantId,
    *,
    embedding_a: Sequence[float],
    embedding_b: Sequence[float],
    threshold: float = SAME_CONTROLLER_BEHAVIOR_THRESHOLD,
) -> SameDetectSignal:
    """STYLO-Vec16 similarity detector.

    Consumes embeddings produced by P1's
    `vacant.runtime.shadow_self.compute_embedding` (or the real STYLO
    encoder once it lands). Strength is `(sim - threshold) /
    (1 - threshold)` clipped to [0, 1].
    """
    if a == b:
        return SameDetectSignal(
            strength=0.0,
            suspected_cluster=frozenset(),
            rationale="self-pair (a == b)",
        )
    sim = cosine_similarity(embedding_a, embedding_b)
    if sim <= threshold:
        return SameDetectSignal(
            strength=0.0,
            suspected_cluster=frozenset(),
            rationale=f"sim {sim:.2f} <= {threshold:.2f}",
        )
    raw = (sim - threshold) / max(1.0 - threshold, 1e-9)
    strength = min(max(raw, 0.0), 1.0)
    return SameDetectSignal(
        strength=strength,
        suspected_cluster=frozenset({a, b}),
        rationale=f"STYLO sim {sim:.2f} > {threshold:.2f}",
    )


# --- Composite weighting ----------------------------------------------------


def discount_from_signals(signals: Sequence[SameDetectSignal]) -> float:
    """Compose multiple `SameDetectSignal`s into a single weight multiplier.

    `max(SAME_SIGNAL_DISCOUNT_FLOOR, 1 - max(strength))` is conservative:
    any one detector firing reduces weight by its `strength`; the strongest
    detector dominates so we don't compound penalties (the dispatch's
    explicit framing — these are signals, not evidence to be summed).

    The floor (D015) is load-bearing: same-* detection is *cost-raising,
    not preventing* (CLAUDE.md §Load-bearing theory decisions). Even at
    `strength=1.0` we must not zero a reviewer's contribution — that
    would convert a probabilistic suspicion into a unilateral mute.
    """
    if not signals:
        return 1.0
    max_strength = max(s.strength for s in signals)
    return max(SAME_SIGNAL_DISCOUNT_FLOOR, 1.0 - max_strength)
