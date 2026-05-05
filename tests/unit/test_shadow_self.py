"""Shadow-self embedding + drift tests."""

from __future__ import annotations

import pytest

from vacant.core.constants import STYLO_DRIFT_THRESHOLD
from vacant.core.crypto import SigningKey, VerifyKey
from vacant.core.types import Logbook
from vacant.runtime.shadow_self import (
    DRIFT_LOG_KIND,
    EMBEDDING_DIM,
    AnchorDistribution,
    compute_drift,
    compute_embedding,
    drift_log_entry,
    is_drifting,
)


def test_embedding_has_expected_dimensionality() -> None:
    v = compute_embedding([b"hello", b"world"])
    assert len(v) == EMBEDDING_DIM
    assert all(0.0 <= x <= 1.0 for x in v)


def test_embedding_is_deterministic() -> None:
    a = compute_embedding([b"abc", b"def"])
    b = compute_embedding([b"abc", b"def"])
    assert a == b


def test_embedding_changes_on_input_change() -> None:
    a = compute_embedding([b"abc", b"def"])
    b = compute_embedding([b"abc", b"deg"])
    assert a != b


def test_embedding_handles_empty_input() -> None:
    v = compute_embedding([])
    assert len(v) == EMBEDDING_DIM


def test_anchor_from_history_rejects_empty() -> None:
    with pytest.raises(ValueError):
        AnchorDistribution.from_history([])


def test_anchor_from_history_rejects_ragged_rows() -> None:
    with pytest.raises(ValueError):
        AnchorDistribution.from_history([[1.0, 2.0], [1.0]])


def test_anchor_rejects_negative_std() -> None:
    with pytest.raises(ValueError):
        AnchorDistribution(mean=(0.0,), std=(-1.0,))


def test_anchor_from_history_zero_variance_when_single_row() -> None:
    a = AnchorDistribution.from_history([[1.0, 2.0, 3.0]])
    assert a.mean == (1.0, 2.0, 3.0)
    assert a.std == (0.0, 0.0, 0.0)


def test_compute_drift_zero_at_mean() -> None:
    a = AnchorDistribution(mean=(0.0, 0.0), std=(1.0, 1.0))
    assert compute_drift([0.0, 0.0], a) == 0.0


def test_compute_drift_one_sigma_per_dim() -> None:
    a = AnchorDistribution(mean=(0.0, 0.0, 0.0, 0.0), std=(1.0, 1.0, 1.0, 1.0))
    # 4 dims, each one std from mean -> sqrt(4) = 2.0
    assert compute_drift([1.0, 1.0, 1.0, 1.0], a) == pytest.approx(2.0)


def test_compute_drift_dim_mismatch_raises() -> None:
    a = AnchorDistribution(mean=(0.0,), std=(1.0,))
    with pytest.raises(ValueError):
        compute_drift([0.0, 0.0], a)


def test_is_drifting_uses_default_threshold() -> None:
    assert is_drifting(STYLO_DRIFT_THRESHOLD - 0.01) is False
    assert is_drifting(STYLO_DRIFT_THRESHOLD) is True


def test_is_drifting_respects_custom_threshold() -> None:
    assert is_drifting(2.0, threshold=1.5) is True
    assert is_drifting(1.0, threshold=1.5) is False


def test_drift_does_not_fire_on_natural_variance() -> None:
    history = [
        [0.5, 0.5, 0.5, 0.5],
        [0.45, 0.55, 0.5, 0.52],
        [0.55, 0.5, 0.48, 0.5],
        [0.5, 0.45, 0.52, 0.48],
    ]
    a = AnchorDistribution.from_history(history)
    drift = compute_drift([0.5, 0.5, 0.5, 0.5], a)
    assert is_drifting(drift) is False


def test_drift_fires_on_far_outlier() -> None:
    history = [
        [0.5, 0.5, 0.5, 0.5],
        [0.5, 0.5, 0.5, 0.5],
        [0.5, 0.5, 0.5, 0.5],
        [0.5, 0.5, 0.5, 0.5],
    ]
    a = AnchorDistribution.from_history(history)
    drift = compute_drift([100.0, 100.0, 100.0, 100.0], a)
    assert is_drifting(drift) is True


def test_drift_log_entry_writes_drift_kind(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, vk = test_keypair
    a = AnchorDistribution(mean=(0.0,) * 4, std=(1.0,) * 4)
    embedding = [5.0, 5.0, 5.0, 5.0]
    drift = compute_drift(embedding, a)
    entry = drift_log_entry(
        logbook=fresh_logbook,
        signing_key=sk,
        drift=drift,
        embedding=embedding,
    )
    assert entry.kind == DRIFT_LOG_KIND
    assert entry.payload["drift"] == pytest.approx(drift)
    assert entry.payload["above_threshold"] is True
    assert fresh_logbook.verify_chain(vk) is True
