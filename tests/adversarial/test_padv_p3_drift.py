"""Padv P3 -- STYLO discount evasion (cumulative drift).

Spec anchors:
- `architecture/components/P3_reputation.md` §3.4 (STYLO Vec16 + drift
  threshold)
- `dispatch/Padv_review.md` §"STYLO discount evasion"
- `architecture/decisions/D010_padv_p3_findings.md` §2
"""

from __future__ import annotations

import pytest

from vacant.core.constants import (
    CUMULATIVE_DRIFT_THRESHOLD_MULTIPLIER,
    CUMULATIVE_DRIFT_WINDOW_EPOCHS,
    STYLO_DRIFT_THRESHOLD,
)
from vacant.reputation import (
    Beta,
    CumulativeDriftTracker,
    apply_discount,
    compute_discount,
)

# --- Attack 1: single-shot drift below threshold escapes single-shot
# discount, but cumulative tracker catches the accumulated change ----------


def test_attack_single_shot_below_threshold_escapes_discount() -> None:
    """An attacker keeps each epoch's drift just below `STYLO_DRIFT_THRESHOLD`
    so `compute_discount` returns ~0.85 instead of ~0.40 -- barely any
    evidence shed.
    """
    just_below = STYLO_DRIFT_THRESHOLD - 1.5
    d = compute_discount(just_below)
    # The single-shot discount is high (close to 1.0), so most evidence is
    # preserved. This is the attacker's window.
    assert d > 0.8


def test_attack_cumulative_drift_tracker_trips_on_accumulated_small_drifts() -> None:
    """Five consecutive 'just-below-threshold' drifts trip the cumulative
    tracker even though no individual epoch crosses the per-epoch threshold.
    """
    tracker = CumulativeDriftTracker(window=CUMULATIVE_DRIFT_WINDOW_EPOCHS)
    # 5 small drifts, each ~ 1.5 (below the per-epoch threshold of 3.5).
    for _ in range(5):
        tracker.observe(1.5)
    # Cumulative = 7.5 > 3.5 * 1.5 = 5.25 trip threshold.
    assert tracker.cumulative == pytest.approx(7.5)
    assert tracker.is_tripped() is True


def test_attack_cumulative_tracker_does_not_trip_on_natural_variance() -> None:
    """Small drifts in a stable behaviour stay below the cumulative
    threshold -- the tracker doesn't false-fire on noise."""
    tracker = CumulativeDriftTracker(window=CUMULATIVE_DRIFT_WINDOW_EPOCHS)
    for _ in range(5):
        tracker.observe(0.5)  # natural variance
    # 2.5 < trip_threshold (3.5 * 1.5 = 5.25).
    assert tracker.is_tripped() is False


def test_attack_cumulative_tracker_window_evicts_old_drifts() -> None:
    """The rolling window evicts older drifts, so a single spike doesn't
    trip the tracker forever."""
    tracker = CumulativeDriftTracker(window=3)
    tracker.observe(3.0)
    tracker.observe(3.0)
    # Cumulative 6.0 > trip threshold (3.5 * 1.5 = 5.25).
    assert tracker.is_tripped() is True
    # Three small drifts evict the spikes from the window.
    for _ in range(3):
        tracker.observe(0.1)
    assert tracker.is_tripped() is False


def test_cumulative_tracker_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        CumulativeDriftTracker(window=0)
    with pytest.raises(ValueError):
        CumulativeDriftTracker(threshold=0)
    with pytest.raises(ValueError):
        CumulativeDriftTracker(threshold_multiplier=0)
    tracker = CumulativeDriftTracker()
    with pytest.raises(ValueError):
        tracker.observe(-1.0)


def test_cumulative_tracker_thresholds_match_constants() -> None:
    """Regression guard: the tracker's defaults track the canonical
    constants in `core.constants`."""
    tracker = CumulativeDriftTracker()
    assert tracker.trip_threshold == pytest.approx(
        STYLO_DRIFT_THRESHOLD * CUMULATIVE_DRIFT_THRESHOLD_MULTIPLIER
    )


# --- Attack 2: incremental shrink via repeated half-discount applications --
# Defense (D): each `apply_discount` call moves the posterior toward the
# prior. An attacker repeatedly applying small discounts can shrink
# n_eff but never below 0; the prior is preserved.


def test_attack_repeated_small_discounts_shrink_n_eff_to_zero_not_below() -> None:
    b = Beta(alpha=10.0, beta=4.0, alpha0=1.0, beta0=1.0, n_eff=12.0)
    for _ in range(50):
        b = apply_discount(b, 0.5)
    # n_eff approaches 0 but stays >= 0; prior is preserved.
    assert b.n_eff >= 0
    assert b.n_eff < 1e-6  # tiny
    # Mean has moved toward the prior's mean (0.5).
    assert abs(b.mean - 0.5) < 0.05
