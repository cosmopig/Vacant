"""Same-* detection tests."""

from __future__ import annotations

import pytest

from vacant.core.constants import SAME_SIGNAL_DISCOUNT_FLOOR
from vacant.core.crypto import keygen
from vacant.core.types import VacantId
from vacant.reputation import (
    SameDetectSignal,
    cosine_similarity,
    cross_correlation,
    discount_from_signals,
    same_controller,
    same_stylo,
    same_substrate,
)


def _two_ids() -> tuple[VacantId, VacantId]:
    return (
        VacantId.from_verify_key(keygen()[1]),
        VacantId.from_verify_key(keygen()[1]),
    )


def test_cosine_similarity_orthogonal_zero() -> None:
    assert cosine_similarity([1, 0, 0], [0, 1, 0]) == 0.0


def test_cosine_similarity_identical_one() -> None:
    assert cosine_similarity([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)


def test_cosine_similarity_zero_norm_returns_zero() -> None:
    assert cosine_similarity([0, 0], [1, 1]) == 0.0


def test_cosine_similarity_dim_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        cosine_similarity([1, 2], [1, 2, 3])


def test_cross_correlation_identical_one() -> None:
    series = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert cross_correlation(series, series) == pytest.approx(1.0)


def test_cross_correlation_zero_variance_returns_zero() -> None:
    assert cross_correlation([1, 1, 1], [1, 2, 3]) == 0.0
    assert cross_correlation([], []) == 0.0


def test_cross_correlation_negative_returns_negative() -> None:
    a = [1.0, 2.0, 3.0, 4.0, 5.0]
    b = [5.0, 4.0, 3.0, 2.0, 1.0]
    assert cross_correlation(a, b) < 0


# --- same-controller ---


def test_same_controller_declared_full_strength() -> None:
    a, b = _two_ids()
    sig = same_controller(a, b, declared_same=True)
    assert sig.strength == 1.0
    assert {a, b} == sig.suspected_cluster


def test_same_controller_common_ancestor_full_strength() -> None:
    a, b = _two_ids()
    sig = same_controller(a, b, common_ancestor=True)
    assert sig.strength == 1.0


def test_same_controller_no_signal_when_independent() -> None:
    a, b = _two_ids()
    sig = same_controller(
        a,
        b,
        heartbeat_a=[1, 2, 3, 4, 5],
        heartbeat_b=[5, 4, 3, 2, 1],
        behavior_a=[1, 0, 0, 0],
        behavior_b=[0, 0, 0, 1],
    )
    assert sig.strength == 0.0
    assert sig.suspected_cluster == frozenset()


def test_same_controller_strong_temporal_corr_fires() -> None:
    a, b = _two_ids()
    series = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
    sig = same_controller(a, b, heartbeat_a=series, heartbeat_b=series)
    assert sig.strength > 0.0


def test_same_controller_strong_behavior_sim_fires() -> None:
    a, b = _two_ids()
    sig = same_controller(
        a,
        b,
        behavior_a=[1.0, 1.0, 1.0, 1.0],
        behavior_b=[1.0, 1.0, 1.0, 1.0],
    )
    assert sig.strength > 0.0


def test_same_controller_self_pair_no_signal() -> None:
    a = VacantId.from_verify_key(keygen()[1])
    sig = same_controller(a, a, declared_same=True)
    assert sig.strength == 0.0


# --- same-substrate ---


def test_same_substrate_same_family_full_strength() -> None:
    a, b = _two_ids()
    sig = same_substrate(a, b, family_a="claude", family_b="claude")
    assert sig.strength == 1.0


def test_same_substrate_distinct_families_no_signal() -> None:
    a, b = _two_ids()
    sig = same_substrate(a, b, family_a="claude", family_b="gemini")
    assert sig.strength == 0.0


def test_same_substrate_self_pair_no_signal() -> None:
    a = VacantId.from_verify_key(keygen()[1])
    sig = same_substrate(a, a, family_a="claude", family_b="claude")
    assert sig.strength == 0.0


# --- same-stylo ---


def test_same_stylo_high_sim_fires() -> None:
    a, b = _two_ids()
    sig = same_stylo(
        a,
        b,
        embedding_a=[1.0, 0.99, 0.98, 0.97],
        embedding_b=[0.99, 1.0, 0.98, 0.96],
    )
    assert sig.strength > 0.0


def test_same_stylo_low_sim_no_signal() -> None:
    a, b = _two_ids()
    sig = same_stylo(
        a,
        b,
        embedding_a=[1.0, 0.0, 0.0, 0.0],
        embedding_b=[0.0, 1.0, 0.0, 0.0],
    )
    assert sig.strength == 0.0


def test_same_stylo_self_pair_no_signal() -> None:
    a = VacantId.from_verify_key(keygen()[1])
    sig = same_stylo(a, a, embedding_a=[1, 1], embedding_b=[1, 1])
    assert sig.strength == 0.0


# --- composite discount ---


def test_discount_from_signals_takes_max_strength() -> None:
    a, b = _two_ids()
    sigs = [
        SameDetectSignal(strength=0.2, suspected_cluster=frozenset(), rationale="x"),
        SameDetectSignal(strength=0.7, suspected_cluster=frozenset(), rationale="y"),
        SameDetectSignal(strength=0.4, suspected_cluster=frozenset(), rationale="z"),
    ]
    # 1 - max(0.7) = 0.3
    assert discount_from_signals(sigs) == pytest.approx(0.3)
    _ = (a, b)


def test_discount_from_signals_empty_returns_one() -> None:
    assert discount_from_signals([]) == 1.0


def test_discount_from_signals_full_strength_respects_floor() -> None:
    """F1 regression: strength=1.0 must not zero the reviewer's weight.

    Same-* detection is cost-raising, not preventing (CLAUDE.md §Load-bearing
    theory decisions / D015). At strength=1.0 the residual weight equals the
    floor, never zero — that would convert detection into a unilateral mute.
    """
    sigs = [SameDetectSignal(strength=1.0, suspected_cluster=frozenset(), rationale="x")]
    discount = discount_from_signals(sigs)
    assert discount == pytest.approx(SAME_SIGNAL_DISCOUNT_FLOOR)
    assert discount > 0.0


def test_discount_from_signals_above_floor_at_lower_strengths() -> None:
    sigs = [SameDetectSignal(strength=0.4, suspected_cluster=frozenset(), rationale="m")]
    # 1 - 0.4 = 0.6; floor never bites here.
    assert discount_from_signals(sigs) == pytest.approx(0.6)


def test_discount_from_signals_floor_holds_for_any_signal_combination() -> None:
    """Floor binds even when several maximal signals stack."""
    sigs = [
        SameDetectSignal(strength=1.0, suspected_cluster=frozenset(), rationale="a"),
        SameDetectSignal(strength=1.0, suspected_cluster=frozenset(), rationale="b"),
        SameDetectSignal(strength=0.95, suspected_cluster=frozenset(), rationale="c"),
    ]
    assert discount_from_signals(sigs) >= SAME_SIGNAL_DISCOUNT_FLOOR
