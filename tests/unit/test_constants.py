"""Sanity checks on the constants module."""

from __future__ import annotations

from vacant.core import constants as C


def test_constants_have_expected_values() -> None:
    assert C.STALE_AFTER_HIBERNATING_DAYS == 30
    assert C.ARCHIVED_AFTER_SUNK_DAYS == 180
    assert C.STYLO_DRIFT_THRESHOLD == 3.5
    assert C.HEARTBEAT_BASE_PERIOD_S == 60
    assert C.HEARTBEAT_DECAYED_PERIOD_S == 86_400
    assert C.HEARTBEAT_SUNK_LIVENESS_PERIOD_S == 600
    assert C.WARMUP_REQUIRED_HEARTBEATS == 5
    assert C.WARMUP_WINDOW_S == 86_400
    assert C.IDEMPOTENCY_WINDOW_S == 86_400
    assert C.DEFAULT_HALO_VERSION == 1


def test_crypto_size_constants() -> None:
    assert C.HASH_DIGEST_BYTES == 32
    assert C.ED25519_PUBLIC_KEY_BYTES == 32
    assert C.ED25519_SIGNATURE_BYTES == 64
