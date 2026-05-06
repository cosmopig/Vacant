"""Heartbeat scheduler.

Per-state cadence and payload (dispatch §2 / THEORY_V5 §4.2 / D003):

| State        | Period                                | Payload                                      |
|--------------|---------------------------------------|----------------------------------------------|
| LOCAL        | `HEARTBEAT_BASE_PERIOD_S`             | `{liveness: true}`                           |
| ACTIVE       | `HEARTBEAT_BASE_PERIOD_S`             | `{liveness: true}`                           |
| HIBERNATING  | `HEARTBEAT_HIBERNATING_PERIOD_S`      | `{liveness: "dormant", last_active: ts}`     |
| STALE        | `HEARTBEAT_HIBERNATING_PERIOD_S`      | `{liveness: false, awaiting_revive: true}`   |
| SUNK         | `HEARTBEAT_SUNK_LIVENESS_PERIOD_S`    | `{liveness: false, key_in_custody: true}` ← load-bearing for lineage attribution (THEORY_V5 §4.2) |
| ARCHIVED     | scheduler does not run                | n/a                                          |

The SUNK payload is the load-bearing one: §4.2 explicitly notes that the
sunk heartbeat is **identity custody attestation, not liveness**, so
`liveness=false` and `key_in_custody=true` must both appear, and the entry
kind is `"HEARTBEAT_SUNK"` so consumers can distinguish at a glance.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from vacant.core.constants import (
    HEARTBEAT_BASE_PERIOD_S,
    HEARTBEAT_HIBERNATING_PERIOD_S,
    HEARTBEAT_SUNK_LIVENESS_PERIOD_S,
)
from vacant.core.crypto import SigningKey
from vacant.core.types import Logbook, LogEntry, VacantState
from vacant.runtime.errors import InvalidEventError

__all__ = [
    "HeartbeatPayload",
    "HeartbeatScheduler",
    "heartbeat_kind",
    "heartbeat_payload",
    "heartbeat_period_s",
]


HEARTBEAT_KIND_DEFAULT = "HEARTBEAT"
HEARTBEAT_KIND_SUNK = "HEARTBEAT_SUNK"


HeartbeatPayload = dict[str, Any]


def heartbeat_period_s(state: VacantState) -> int:
    """Return the cadence (seconds) for `state` heartbeats.

    Raises `InvalidEventError` for ARCHIVED — by spec, the scheduler does
    not run for archived vacants.
    """
    match state:
        case VacantState.LOCAL | VacantState.ACTIVE:
            return HEARTBEAT_BASE_PERIOD_S
        case VacantState.HIBERNATING | VacantState.STALE:
            return HEARTBEAT_HIBERNATING_PERIOD_S
        case VacantState.SUNK:
            return HEARTBEAT_SUNK_LIVENESS_PERIOD_S
        case VacantState.ARCHIVED:
            raise InvalidEventError("scheduler does not run for ARCHIVED vacants")


def heartbeat_kind(state: VacantState) -> str:
    """Log entry `kind` for the heartbeat. SUNK uses a distinct kind so
    downstream consumers can filter custody attestations from liveness pulses
    without re-inspecting the payload.
    """
    return HEARTBEAT_KIND_SUNK if state == VacantState.SUNK else HEARTBEAT_KIND_DEFAULT


def heartbeat_payload(
    state: VacantState,
    *,
    last_active: datetime | None = None,
    extra: dict[str, Any] | None = None,
) -> HeartbeatPayload:
    """State-specific payload for the next heartbeat entry."""
    payload: HeartbeatPayload
    match state:
        case VacantState.LOCAL | VacantState.ACTIVE:
            payload = {"liveness": True}
        case VacantState.HIBERNATING:
            payload = {
                "liveness": "dormant",
                "last_active": (last_active or datetime.now(UTC)).isoformat(),
            }
        case VacantState.STALE:
            payload = {"liveness": False, "awaiting_revive": True}
        case VacantState.SUNK:
            payload = {"liveness": False, "key_in_custody": True}
        case VacantState.ARCHIVED:
            raise InvalidEventError("ARCHIVED vacants do not emit heartbeats")
    if extra:
        payload = {**payload, **extra}
    return payload


class HeartbeatScheduler:
    """Async scheduler that signs and appends heartbeat entries to a logbook.

    Construction is dependency-injected: state is read via `state_provider`
    (a callable, since it can change between ticks), the signing key is
    pinned at construction, and the cadence is derived from the *current*
    state on each tick (so a transition from ACTIVE → HIBERNATING
    immediately stretches the next sleep interval).
    """

    def __init__(
        self,
        *,
        logbook: Logbook,
        signing_key: SigningKey,
        state_provider: Callable[[], VacantState],
        sleep: Callable[[float], Any] = asyncio.sleep,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        last_active_provider: Callable[[], datetime | None] = lambda: None,
    ) -> None:
        self._logbook = logbook
        self._signing_key = signing_key
        self._state_provider = state_provider
        self._sleep = sleep
        self._clock = clock
        self._last_active_provider = last_active_provider
        self._tick_count = 0

    @property
    def tick_count(self) -> int:
        return self._tick_count

    async def tick(self, *, extra: dict[str, Any] | None = None) -> LogEntry:
        """Append exactly one heartbeat entry for the current state.

        Raises `InvalidEventError` if the current state is ARCHIVED.
        """
        state = self._state_provider()
        if state == VacantState.ARCHIVED:
            raise InvalidEventError("HeartbeatScheduler.tick() called in ARCHIVED")
        payload = heartbeat_payload(state, last_active=self._last_active_provider(), extra=extra)
        kind = heartbeat_kind(state)
        entry = self._logbook.append(kind, payload, self._signing_key, ts=self._clock())
        self._tick_count += 1
        return entry

    async def run_until_archived(self, *, max_ticks: int | None = None) -> int:
        """Drive `tick()` continuously, sleeping `heartbeat_period_s(state)`
        between ticks, and stop when state becomes ARCHIVED (or `max_ticks`
        is reached). Returns the number of ticks emitted.
        """
        emitted = 0
        while True:
            state = self._state_provider()
            if state == VacantState.ARCHIVED:
                return emitted
            if max_ticks is not None and emitted >= max_ticks:
                return emitted
            await self.tick()
            emitted += 1
            next_state = self._state_provider()
            if next_state == VacantState.ARCHIVED:
                return emitted
            await self._sleep(heartbeat_period_s(next_state))
