"""Portability factor tests."""

from __future__ import annotations

import pytest

from vacant.core.constants import PORTABILITY_FACTOR_MAX_BONUS
from vacant.reputation import compute_portability


def test_no_substrates_zero() -> None:
    assert compute_portability(substrates_served=[], success_rate_per_substrate={}) == 0.0


def test_single_substrate_perfect_capped_low() -> None:
    bonus = compute_portability(
        substrates_served=["claude"], success_rate_per_substrate={"claude": 1.0}
    )
    # Single substrate, low diversity → small bonus.
    assert 0 < bonus < PORTABILITY_FACTOR_MAX_BONUS


def test_diverse_substrates_perfect_full_bonus() -> None:
    bonus = compute_portability(
        substrates_served=["claude", "gemini", "qwen", "ollama"],
        success_rate_per_substrate={"claude": 1.0, "gemini": 1.0, "qwen": 1.0, "ollama": 1.0},
    )
    assert bonus == pytest.approx(PORTABILITY_FACTOR_MAX_BONUS, abs=1e-6)


def test_zero_success_rates_zero_bonus() -> None:
    assert (
        compute_portability(
            substrates_served=["claude", "gemini"],
            success_rate_per_substrate={"claude": 0.0, "gemini": 0.0},
        )
        == 0.0
    )


def test_diversity_factor_saturates_above_4() -> None:
    a = compute_portability(
        substrates_served=["a", "b", "c", "d"],
        success_rate_per_substrate=dict.fromkeys("abcd", 1.0),
    )
    b = compute_portability(
        substrates_served=["a", "b", "c", "d", "e", "f"],
        success_rate_per_substrate=dict.fromkeys("abcdef", 1.0),
    )
    # Both saturate at the cap.
    assert a == pytest.approx(b, abs=1e-6)


def test_negative_max_bonus_rejected() -> None:
    with pytest.raises(ValueError):
        compute_portability(
            substrates_served=["x"],
            success_rate_per_substrate={"x": 0.5},
            max_bonus=-0.1,
        )


def test_missing_rate_treated_as_zero() -> None:
    bonus = compute_portability(
        substrates_served=["a", "b"],
        success_rate_per_substrate={"a": 1.0},  # b missing → 0
    )
    expected = compute_portability(
        substrates_served=["a", "b"],
        success_rate_per_substrate={"a": 1.0, "b": 0.0},
    )
    assert bonus == pytest.approx(expected)
