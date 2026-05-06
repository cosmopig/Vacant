"""HeartbeatScheduler + per-state cadence/payload tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from vacant.core.constants import (
    HEARTBEAT_BASE_PERIOD_S,
    HEARTBEAT_HIBERNATING_PERIOD_S,
    HEARTBEAT_SUNK_LIVENESS_PERIOD_S,
)
from vacant.core.crypto import SigningKey, VerifyKey
from vacant.core.types import Logbook, VacantState
from vacant.runtime.errors import InvalidEventError
from vacant.runtime.heartbeat import (
    HEARTBEAT_KIND_DEFAULT,
    HEARTBEAT_KIND_SUNK,
    HeartbeatScheduler,
    heartbeat_kind,
    heartbeat_payload,
    heartbeat_period_s,
)


def test_period_active_and_local_are_base() -> None:
    assert heartbeat_period_s(VacantState.ACTIVE) == HEARTBEAT_BASE_PERIOD_S
    assert heartbeat_period_s(VacantState.LOCAL) == HEARTBEAT_BASE_PERIOD_S


def test_period_hibernating_and_stale_are_24h() -> None:
    assert heartbeat_period_s(VacantState.HIBERNATING) == HEARTBEAT_HIBERNATING_PERIOD_S
    assert heartbeat_period_s(VacantState.STALE) == HEARTBEAT_HIBERNATING_PERIOD_S


def test_period_sunk_is_10_min() -> None:
    assert heartbeat_period_s(VacantState.SUNK) == HEARTBEAT_SUNK_LIVENESS_PERIOD_S
    # Cross-check the actual seconds — load-bearing for THEORY_V5 §4.2.
    assert HEARTBEAT_SUNK_LIVENESS_PERIOD_S == 600


def test_period_archived_raises() -> None:
    with pytest.raises(InvalidEventError):
        heartbeat_period_s(VacantState.ARCHIVED)


def test_kind_sunk_distinguished() -> None:
    assert heartbeat_kind(VacantState.SUNK) == HEARTBEAT_KIND_SUNK
    for s in (
        VacantState.LOCAL,
        VacantState.ACTIVE,
        VacantState.HIBERNATING,
        VacantState.STALE,
    ):
        assert heartbeat_kind(s) == HEARTBEAT_KIND_DEFAULT


def test_payload_active_marks_liveness_true() -> None:
    p = heartbeat_payload(VacantState.ACTIVE)
    assert p == {"liveness": True}


def test_payload_hibernating_includes_last_active() -> None:
    last = datetime(2026, 1, 1, tzinfo=UTC)
    p = heartbeat_payload(VacantState.HIBERNATING, last_active=last)
    assert p["liveness"] == "dormant"
    assert p["last_active"] == last.isoformat()


def test_payload_stale_marks_awaiting_revive() -> None:
    p = heartbeat_payload(VacantState.STALE)
    assert p == {"liveness": False, "awaiting_revive": True}


def test_payload_sunk_is_custody_attestation() -> None:
    p = heartbeat_payload(VacantState.SUNK)
    # THEORY_V5 §4.2: sunk heartbeat = identity custody attestation
    assert p["liveness"] is False
    assert p["key_in_custody"] is True


def test_payload_archived_raises() -> None:
    with pytest.raises(InvalidEventError):
        heartbeat_payload(VacantState.ARCHIVED)


def test_payload_extra_merges_in() -> None:
    p = heartbeat_payload(VacantState.ACTIVE, extra={"tick_seq": 7})
    assert p["tick_seq"] == 7
    assert p["liveness"] is True


# --- scheduler -----------------------------------------------------------


@pytest.mark.asyncio
async def test_scheduler_tick_appends_signed_entry(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, vk = test_keypair
    state = VacantState.ACTIVE
    sched = HeartbeatScheduler(
        logbook=fresh_logbook,
        signing_key=sk,
        state_provider=lambda: state,
    )
    entry = await sched.tick()
    assert entry.kind == HEARTBEAT_KIND_DEFAULT
    assert entry.payload == {"liveness": True}
    assert fresh_logbook.verify_chain(vk) is True
    assert sched.tick_count == 1


@pytest.mark.asyncio
async def test_scheduler_sunk_tick_carries_custody_payload(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, vk = test_keypair
    sched = HeartbeatScheduler(
        logbook=fresh_logbook,
        signing_key=sk,
        state_provider=lambda: VacantState.SUNK,
    )
    entry = await sched.tick()
    assert entry.kind == HEARTBEAT_KIND_SUNK
    assert entry.payload["liveness"] is False
    assert entry.payload["key_in_custody"] is True
    assert fresh_logbook.verify_chain(vk) is True


@pytest.mark.asyncio
async def test_scheduler_archived_raises(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, _vk = test_keypair
    sched = HeartbeatScheduler(
        logbook=fresh_logbook,
        signing_key=sk,
        state_provider=lambda: VacantState.ARCHIVED,
    )
    with pytest.raises(InvalidEventError):
        await sched.tick()


@pytest.mark.asyncio
async def test_run_until_archived_emits_max_ticks_then_stops(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, _vk = test_keypair
    sleeps: list[float] = []

    async def fake_sleep(s: float) -> None:
        sleeps.append(s)

    sched = HeartbeatScheduler(
        logbook=fresh_logbook,
        signing_key=sk,
        state_provider=lambda: VacantState.ACTIVE,
        sleep=fake_sleep,
    )
    emitted = await sched.run_until_archived(max_ticks=3)
    assert emitted == 3
    assert len(fresh_logbook.entries) == 3
    assert all(s == HEARTBEAT_BASE_PERIOD_S for s in sleeps[:2])


@pytest.mark.asyncio
async def test_run_until_archived_stops_when_state_archives(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, _vk = test_keypair
    state: VacantState = VacantState.ACTIVE

    async def fake_sleep(s: float) -> None:
        nonlocal state
        # After the first tick, flip to ARCHIVED so the next loop bails.
        state = VacantState.ARCHIVED

    sched = HeartbeatScheduler(
        logbook=fresh_logbook,
        signing_key=sk,
        state_provider=lambda: state,
        sleep=fake_sleep,
    )
    emitted = await sched.run_until_archived()
    assert emitted == 1


@pytest.mark.asyncio
async def test_run_until_archived_handles_already_archived(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, _vk = test_keypair
    sched = HeartbeatScheduler(
        logbook=fresh_logbook,
        signing_key=sk,
        state_provider=lambda: VacantState.ARCHIVED,
    )
    emitted = await sched.run_until_archived()
    assert emitted == 0


@pytest.mark.asyncio
async def test_scheduler_uses_clock_for_timestamps(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, _vk = test_keypair
    fixed = datetime(2026, 5, 5, 12, 0, 0, tzinfo=UTC)
    sched = HeartbeatScheduler(
        logbook=fresh_logbook,
        signing_key=sk,
        state_provider=lambda: VacantState.ACTIVE,
        clock=lambda: fixed,
    )
    entry = await sched.tick()
    assert entry.ts == fixed


@pytest.mark.asyncio
async def test_scheduler_extra_payload_merges_in(
    test_keypair: tuple[SigningKey, VerifyKey], fresh_logbook: Logbook
) -> None:
    sk, _vk = test_keypair
    sched = HeartbeatScheduler(
        logbook=fresh_logbook,
        signing_key=sk,
        state_provider=lambda: VacantState.ACTIVE,
    )
    extra: dict[str, Any] = {"tick_seq": 42}
    entry = await sched.tick(extra=extra)
    assert entry.payload["tick_seq"] == 42
