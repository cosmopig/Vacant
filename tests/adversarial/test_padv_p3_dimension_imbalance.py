"""Padv P3 -- dimension-imbalance attacks.

Spec anchors:
- `architecture/components/P3_reputation.md` §3.6 防線 4 (cross-dimension
  divergence check)
- `architecture/CONSTANTS.md` §Reputation (`DIMENSION_CORRELATION_ALERT_THRESHOLD = 0.6`)
- `dispatch/Padv_review.md` §"Dimension imbalance"
- `architecture/decisions/D010_padv_p3_findings.md` §3
"""

from __future__ import annotations

from vacant.reputation import (
    Beta,
    Beta5D,
    dimension_imbalance_alert,
    five_d_with_priors,
)


def _seed(rep: Beta5D, dim: str, *, n: int, signal: float) -> Beta5D:
    """Apply `n` reviews with `signal` to one dimension and return updated."""
    for _ in range(n):
        rep = rep.update_dim(dim, signal=signal, weight=1.0, now_ts=0.0)
    return rep


# --- Attack 1: pump factual while leaving adoption near prior --------------
# Defense (D): `dimension_imbalance_alert` returns True when max-min mean
# exceeds the canonical threshold (0.6) -- flagging the imbalance to UI /
# caveats.


def test_attack_factual_only_pump_triggers_alert() -> None:
    rep = five_d_with_priors()
    # Pump factual to high; leave adoption at its pessimistic prior (0.25).
    rep = _seed(rep, "factual", n=50, signal=0.99)
    assert dimension_imbalance_alert(rep) is True


def test_attack_balanced_high_does_not_trigger_alert() -> None:
    """All five dims pumped uniformly -- a healthy distribution."""
    rep = five_d_with_priors()
    for d in ("factual", "logical", "relevance", "honesty", "adoption"):
        rep = _seed(rep, d, n=50, signal=0.85)
    assert dimension_imbalance_alert(rep) is False


def test_attack_balanced_low_does_not_trigger_alert() -> None:
    """All dims pulled low together -- also balanced (but bad performance)."""
    rep = five_d_with_priors()
    for d in ("factual", "logical", "relevance", "honesty", "adoption"):
        rep = _seed(rep, d, n=50, signal=0.10)
    # All means are low and similar; no imbalance alert.
    assert dimension_imbalance_alert(rep) is False


def test_dimension_imbalance_alert_respects_custom_threshold() -> None:
    rep = five_d_with_priors()
    # Modest imbalance: F = 0.7, A = 0.25 → diff ~ 0.45.
    rep = _seed(rep, "factual", n=50, signal=0.7)
    # Default threshold 0.6 → False (0.45 < 0.6).
    assert dimension_imbalance_alert(rep) is False
    # Lower threshold catches the imbalance.
    assert dimension_imbalance_alert(rep, threshold=0.3) is True


def test_dimension_imbalance_alert_handles_fresh_prior() -> None:
    """Cold-start state should not spuriously fire (prior means are
    F/L/R = 0.5, H = 0.667, A = 0.25 → max-min ≈ 0.42 < 0.6)."""
    rep = five_d_with_priors()
    assert dimension_imbalance_alert(rep) is False


def test_dimension_imbalance_alert_with_zeroed_dim() -> None:
    """An attacker drives one dim to zero while keeping others high."""
    rep = five_d_with_priors()
    # Pump F/L/R high.
    for d in ("factual", "logical", "relevance"):
        rep = _seed(rep, d, n=50, signal=0.95)
    # Pump A negative (low-signal pile).
    rep = _seed(rep, "adoption", n=50, signal=0.05)
    assert dimension_imbalance_alert(rep) is True
    # The dim with the lowest mean is adoption; F is the highest.
    means = rep.means()
    assert (max(means.values()) - min(means.values())) > 0.6
    _ = Beta  # silence unused
