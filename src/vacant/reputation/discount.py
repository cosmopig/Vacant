"""STYLO-distance reputation discount (P3 §4.3 / dispatch §3).

When a vacant's behavioral fingerprint drifts substantially between
epochs, the old evidence is *less* informative about the new behavior.
The discount shrinks the effective sample size (alpha and beta scale together,
preserving the mean while widening uncertainty).

This is the mechanism that bites self-evolution at the **individual
vacant** level. New lineage members get a clean posterior -- see
`reputation/cold_start.py::initial_prior` and §4.3 ("lineage as the
subject of evolution").

Discount curve:

```
distance = 0       → discount = 1.0  (no change)
distance ~ 1.5sigma    → discount ~ 0.85
distance ~ STYLO_DRIFT_THRESHOLD (3.5) → discount ~ 0.40
distance → ∞       → discount → discount_floor (0.10)
```

`compute_discount` is shaped as a sigmoid centered just below the drift
threshold; `apply_discount` rescales alpha and beta toward their priors so the
posterior preserves its mean while shedding evidence.
"""

from __future__ import annotations

import math

from vacant.core.constants import STYLO_DRIFT_THRESHOLD
from vacant.reputation.posterior import Beta, Beta5D

__all__ = [
    "apply_discount",
    "apply_discount_5d",
    "compute_discount",
]


_DISCOUNT_FLOOR = 0.10
_HIGH_PLATEAU = 0.85  # discount at distance ~ 1.5sigma
_LOW_PLATEAU = 0.40  # discount at distance ~ STYLO_DRIFT_THRESHOLD
_MIDPOINT_OFFSET = 1.5  # distance at which discount ~ 0.85


def compute_discount(stylo_distance: float, *, threshold: float = STYLO_DRIFT_THRESHOLD) -> float:
    """Map STYLO distance → discount multiplier in `(discount_floor, 1.0]`.

    Curve shape:
    - `distance == 0` → 1.0 (no change).
    - Smooth sigmoid descent passing through ~0.85 at `_MIDPOINT_OFFSET`.
    - Approaches `_DISCOUNT_FLOOR` as distance → ∞.
    """
    if stylo_distance < 0:
        raise ValueError(f"stylo_distance must be >= 0; got {stylo_distance}")
    if stylo_distance == 0:
        return 1.0
    # Logistic centered around the threshold, scaled so distance == 0 → ~1.0.
    # `1 / (1 + exp(k * (d - threshold)))` is in (0, 1); we re-scale to
    # ensure `d == 0 → 1.0` and `d → ∞ → _DISCOUNT_FLOOR`.
    k = math.log(_HIGH_PLATEAU / (1.0 - _HIGH_PLATEAU)) / max(threshold - _MIDPOINT_OFFSET, 1e-9)
    sigmoid = 1.0 / (1.0 + math.exp(k * (stylo_distance - threshold)))
    span = 1.0 - _DISCOUNT_FLOOR
    return _DISCOUNT_FLOOR + span * sigmoid


def apply_discount(beta: Beta, discount: float) -> Beta:
    """Shrink alpha and beta toward priors by `discount` ∈ (0, 1].

    Preserves the mean (alpha / (alpha+beta)) but reduces effective sample size:

    ```
    alpha' = alpha0 + discount * (alpha - alpha0)
    beta' = beta0 + discount * (beta - beta0)
    n_eff' = discount * n_eff
    ```
    """
    if not (0.0 < discount <= 1.0):
        raise ValueError(f"discount must be in (0, 1]; got {discount}")
    return beta.model_copy(
        update={
            "alpha": beta.alpha0 + discount * (beta.alpha - beta.alpha0),
            "beta": beta.beta0 + discount * (beta.beta - beta.beta0),
            "n_eff": discount * beta.n_eff,
        }
    )


def apply_discount_5d(rep: Beta5D, discount: float) -> Beta5D:
    """Apply a single discount to all five dimensions."""
    return Beta5D(
        factual=apply_discount(rep.factual, discount),
        logical=apply_discount(rep.logical, discount),
        relevance=apply_discount(rep.relevance, discount),
        honesty=apply_discount(rep.honesty, discount),
        adoption=apply_discount(rep.adoption, discount),
    )


# --- Cumulative drift detector (Padv-P3 finding D010 §2) -------------------


from collections import deque  # noqa: E402

from vacant.core.constants import (  # noqa: E402
    CUMULATIVE_DRIFT_THRESHOLD_MULTIPLIER,
    CUMULATIVE_DRIFT_WINDOW_EPOCHS,
)


class CumulativeDriftTracker:
    """Rolling-window sum of per-epoch STYLO drifts.

    Single-shot `compute_discount` is fooled by an attacker who keeps
    each epoch's drift just below `STYLO_DRIFT_THRESHOLD` while
    accumulating change across many epochs (P3 §3.4 Padv-P3 §2). This
    tracker keeps a rolling window of the last `window` per-epoch
    drifts and trips when their sum exceeds
    `threshold * threshold_multiplier`.

    Tracker is per (vacant, substrate); the aggregator owns one per
    target it scores.
    """

    __slots__ = ("_threshold", "_threshold_multiplier", "_window")

    def __init__(
        self,
        *,
        window: int = CUMULATIVE_DRIFT_WINDOW_EPOCHS,
        threshold: float = STYLO_DRIFT_THRESHOLD,
        threshold_multiplier: float = CUMULATIVE_DRIFT_THRESHOLD_MULTIPLIER,
    ) -> None:
        if window < 1:
            raise ValueError(f"window must be >= 1; got {window}")
        if threshold <= 0:
            raise ValueError(f"threshold must be > 0; got {threshold}")
        if threshold_multiplier <= 0:
            raise ValueError(f"threshold_multiplier must be > 0; got {threshold_multiplier}")
        self._window: deque[float] = deque(maxlen=window)
        self._threshold = threshold
        self._threshold_multiplier = threshold_multiplier

    def observe(self, distance: float) -> None:
        if distance < 0:
            raise ValueError(f"distance must be >= 0; got {distance}")
        self._window.append(distance)

    @property
    def cumulative(self) -> float:
        return sum(self._window)

    @property
    def trip_threshold(self) -> float:
        return self._threshold * self._threshold_multiplier

    def is_tripped(self) -> bool:
        return self.cumulative >= self.trip_threshold


# --- Dimension correlation alert (Padv-P3 finding D010 §3) -----------------


def dimension_imbalance_alert(rep: Beta5D, *, threshold: float | None = None) -> bool:
    """Detect dimension imbalance (P3 §3.6 防線 4 / dispatch §"Dimension imbalance").

    True iff at least one dimension's mean exceeds the threshold's gap
    above the **lowest** dimension's mean. This catches the attack
    pattern "pump only F while leaving A low":

    - all-similar means → False (healthy distribution)
    - one dim spiked while others stay near prior → True (imbalanced)

    `threshold` defaults to `DIMENSION_CORRELATION_ALERT_THRESHOLD = 0.6`.
    The implementation uses `max - min` as a quick proxy for the
    correlation alert; a full pairwise correlation matrix is future work.
    """
    from vacant.core.constants import DIMENSION_CORRELATION_ALERT_THRESHOLD

    thr = threshold if threshold is not None else DIMENSION_CORRELATION_ALERT_THRESHOLD
    means = list(rep.means().values())
    if not means:
        return False
    return (max(means) - min(means)) >= thr
