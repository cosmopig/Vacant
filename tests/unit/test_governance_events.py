"""A14 / A29 / A36 / A39 — governance + custody-transfer events."""

from __future__ import annotations

import math

import pytest

from vacant.core.crypto import SigningKey, keygen
from vacant.core.types import VacantId
from vacant.identity.governance import (
    AttestorDiversity,
    ControllerTransferEvent,
    GovernanceChangeEvent,
    MigrationEvent,
    recently_transferred,
    score_attestor_set,
)


def _vid_pair() -> tuple[SigningKey, VacantId]:
    sk, vk = keygen()
    return sk, VacantId.from_verify_key(vk)


# --- A14 MigrationEvent ---------------------------------------------------


def test_migration_event_signed_and_verified() -> None:
    sk, vid = _vid_pair()
    ev = MigrationEvent.new(
        vacant_id=vid,
        from_endpoint="https://old.example.com",
        to_endpoint="https://new.example.com",
        signing_key=sk,
    )
    assert ev.verify() is True
    # UUID is a real UUID4.
    import uuid as _uuid

    assert _uuid.UUID(ev.concurrency_uuid).version == 4


def test_migration_event_signature_tied_to_concurrency_uuid() -> None:
    """Tampering the concurrency_uuid must invalidate the signature
    so a race-loser can't re-publish under a different uuid."""
    sk, vid = _vid_pair()
    ev = MigrationEvent.new(
        vacant_id=vid, from_endpoint="a", to_endpoint="b", signing_key=sk
    )
    tampered = MigrationEvent(
        vacant_id=ev.vacant_id,
        from_endpoint=ev.from_endpoint,
        to_endpoint=ev.to_endpoint,
        concurrency_uuid="00000000-0000-4000-8000-000000000000",
        issued_at_ms=ev.issued_at_ms,
        signature=ev.signature,
    )
    assert tampered.verify() is False


def test_migration_event_concurrent_writers_get_distinct_uuids() -> None:
    """Two simultaneous migrations of the same vacant produce distinct
    `concurrency_uuid`s, which is the primary-key collision V5 §8.1 A14
    relies on."""
    sk, vid = _vid_pair()
    ev1 = MigrationEvent.new(vacant_id=vid, from_endpoint="a", to_endpoint="b", signing_key=sk)
    ev2 = MigrationEvent.new(vacant_id=vid, from_endpoint="a", to_endpoint="c", signing_key=sk)
    assert ev1.concurrency_uuid != ev2.concurrency_uuid


# --- A29 ControllerTransferEvent / A36 GovernanceChangeEvent ----------------


def test_controller_transfer_signed_and_verified() -> None:
    sk, vid = _vid_pair()
    ev = ControllerTransferEvent.new(
        vacant_id=vid,
        from_controller_id="alice@example.com",
        to_controller_id="bob@example.com",
        signing_key=sk,
    )
    assert ev.kind == "controller_transfer"
    assert ev.verify() is True


def test_governance_change_signed_and_verified() -> None:
    sk, vid = _vid_pair()
    ev = GovernanceChangeEvent.new(
        vacant_id=vid,
        from_controller_id="oldcorp.example",
        to_controller_id="newcorp.example",
        signing_key=sk,
    )
    assert ev.kind == "governance_change"
    assert ev.verify() is True


def test_transfer_events_with_wrong_signature_dont_verify() -> None:
    sk1, vid1 = _vid_pair()
    sk2, vid2 = _vid_pair()
    # Sign with sk2 but claim it's vid1's event.
    bad = ControllerTransferEvent(
        vacant_id=vid1,
        from_controller_id="a",
        to_controller_id="b",
        issued_at_ms=1,
    )
    bad = ControllerTransferEvent(
        vacant_id=vid1,
        from_controller_id="a",
        to_controller_id="b",
        issued_at_ms=1,
        signature=bytes(64),
    )
    assert bad.verify() is False


def test_recently_transferred_within_30_days_is_true() -> None:
    sk, vid = _vid_pair()
    now_ms = 1_700_000_000_000
    fresh = ControllerTransferEvent.new(
        vacant_id=vid,
        from_controller_id="a",
        to_controller_id="b",
        signing_key=sk,
        issued_at_ms=now_ms - 5 * 24 * 60 * 60 * 1000,  # 5 days ago
    )
    assert recently_transferred([fresh], now_ms=now_ms) is True


def test_recently_transferred_outside_window_is_false() -> None:
    sk, vid = _vid_pair()
    now_ms = 1_700_000_000_000
    stale = GovernanceChangeEvent.new(
        vacant_id=vid,
        from_controller_id="a",
        to_controller_id="b",
        signing_key=sk,
        issued_at_ms=now_ms - 60 * 24 * 60 * 60 * 1000,  # 60 days ago
    )
    assert recently_transferred([stale], now_ms=now_ms) is False


def test_recently_transferred_empty_iterable_is_false() -> None:
    assert recently_transferred([]) is False


# --- A39 AttestorDiversity ------------------------------------------------


def test_attestor_diversity_zero_for_single_source() -> None:
    div = AttestorDiversity(attestor_ids=("attestor-x", "attestor-x", "attestor-x"))
    assert div.score() == 0.0
    assert div.is_captured() is True


def test_attestor_diversity_max_for_uniform_distribution() -> None:
    div = AttestorDiversity(
        attestor_ids=("a", "b", "c", "d"),
    )
    # 4 equal → entropy = log2(4) = 2.
    assert div.score() == pytest.approx(2.0, abs=1e-9)
    assert div.is_captured(min_entropy_bits=1.5) is False


def test_attestor_diversity_partial_capture_flagged() -> None:
    # 90% one source + 10% another → entropy ~0.469, below 1.0 threshold.
    div = AttestorDiversity(
        attestor_ids=tuple(["primary"] * 9 + ["secondary"] * 1),
    )
    assert div.score() < 1.0
    assert div.is_captured(min_entropy_bits=1.0) is True


def test_score_attestor_set_standalone() -> None:
    """Free-standing helper used by callers who don't want the dataclass."""
    score = score_attestor_set(["a", "b"])
    # 2 equal → log2(2) = 1.
    assert score == pytest.approx(1.0)
