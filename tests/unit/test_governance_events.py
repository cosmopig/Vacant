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
    MigrationEventStore,
    MigrationRaceError,
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


def test_migration_event_store_first_write_wins() -> None:
    """V5 §8.1 A14: atomic migration_event. Two concurrent writers
    submitting events for the same vacant collide at the store's
    PK level — the loser raises `MigrationRaceError` and must abort
    or retry. This is the actual atomic claim the spec rests on; the
    UUID-uniqueness of `MigrationEvent.new()` alone doesn't deliver it."""
    sk, vid = _vid_pair()
    store = MigrationEventStore()

    winner = MigrationEvent.new(
        vacant_id=vid, from_endpoint="a", to_endpoint="b", signing_key=sk
    )
    store.record(winner)

    # Concurrent loser: different concurrency_uuid (so PK doesn't collide
    # directly), but same vacant_id — the store still rejects.
    loser = MigrationEvent.new(
        vacant_id=vid, from_endpoint="a", to_endpoint="c", signing_key=sk
    )
    with pytest.raises(MigrationRaceError, match="already has an in-flight migration"):
        store.record(loser)

    # The winner is what the store reports.
    assert store.get(vid) == winner


def test_migration_event_store_duplicate_pk_rejected() -> None:
    """An attempt to record the exact same event twice (same PK)
    is also rejected — defends against accidental retry-without-clear."""
    sk, vid = _vid_pair()
    store = MigrationEventStore()
    ev = MigrationEvent.new(
        vacant_id=vid, from_endpoint="a", to_endpoint="b", signing_key=sk
    )
    store.record(ev)
    store.clear(vid)
    # After clear, re-recording the SAME event still hits PK uniqueness.
    with pytest.raises(MigrationRaceError, match="duplicate PK"):
        store.record(ev)


def test_migration_event_store_clear_allows_new_migration() -> None:
    """Once an in-flight migration is finalised (`store.clear`), a
    fresh migration for the same vacant succeeds. Models the
    "migration committed, next one can start" lifecycle."""
    sk, vid = _vid_pair()
    store = MigrationEventStore()
    first = MigrationEvent.new(
        vacant_id=vid, from_endpoint="a", to_endpoint="b", signing_key=sk
    )
    store.record(first)
    store.clear(vid)
    second = MigrationEvent.new(
        vacant_id=vid, from_endpoint="b", to_endpoint="c", signing_key=sk
    )
    store.record(second)
    assert store.get(vid) == second


def test_migration_event_store_rejects_unsigned_event() -> None:
    """Store refuses to record an event whose Ed25519 signature
    doesn't verify under the claimed vacant_id."""
    sk, vid = _vid_pair()
    store = MigrationEventStore()
    forged = MigrationEvent(
        vacant_id=vid,
        from_endpoint="a",
        to_endpoint="b",
        concurrency_uuid="00000000-0000-4000-8000-000000000000",
        issued_at_ms=1,
        signature=bytes(64),
    )
    with pytest.raises(MigrationRaceError, match="signature did not verify"):
        store.record(forged)


def test_migration_event_store_rejects_zero_seen_pks_max() -> None:
    """`seen_pks_max <= 0` would silently disable replay protection
    (every insert is immediately evicted) — reject at construction."""
    with pytest.raises(ValueError, match="must be >= 1"):
        MigrationEventStore(seen_pks_max=0)
    with pytest.raises(ValueError, match="must be >= 1"):
        MigrationEventStore(seen_pks_max=-1)


def test_migration_event_store_seen_pks_bounded_with_fifo_eviction() -> None:
    """`seen_pks_max` bounds the replay-rejection cache; FIFO
    eviction once full so a long-running store doesn't leak memory.
    The oldest evicted PKs are no longer replay-rejected — that's
    the documented trade-off."""
    sk, vid = _vid_pair()
    # Tight cap so we can exercise eviction in a small loop.
    store = MigrationEventStore(seen_pks_max=3)
    events = []
    for _ in range(5):
        ev = MigrationEvent.new(
            vacant_id=vid, from_endpoint="a", to_endpoint="b", signing_key=sk
        )
        store.record(ev)
        store.clear(vid)
        events.append(ev)
    # Cache holds only the last 3 PKs.
    assert len(store._seen_pks) == 3
    # The two oldest events have been evicted — re-recording them
    # is allowed again. Newer events are still replay-rejected.
    store.record(events[0])  # evicted, OK
    store.clear(vid)
    with pytest.raises(MigrationRaceError, match="duplicate PK"):
        store.record(events[-1])  # still in cache, rejected


def test_migration_event_store_thread_safe_under_concurrent_record() -> None:
    """Two threads racing to record for the same vacant: exactly one
    succeeds, the other raises `MigrationRaceError`. The internal
    `threading.Lock` is what makes this deterministic; without it,
    both threads could race past the in-flight check."""
    import threading as _t

    sk, vid = _vid_pair()
    store = MigrationEventStore()
    results: list[str] = []

    def attempt(label: str) -> None:
        ev = MigrationEvent.new(
            vacant_id=vid, from_endpoint=label, to_endpoint="b", signing_key=sk
        )
        try:
            store.record(ev)
            results.append(f"{label}:ok")
        except MigrationRaceError:
            results.append(f"{label}:race")

    t1 = _t.Thread(target=attempt, args=("a",))
    t2 = _t.Thread(target=attempt, args=("b",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    # Exactly one winner; exactly one race-loser.
    assert sorted([r.split(":")[1] for r in results]) == ["ok", "race"]


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
