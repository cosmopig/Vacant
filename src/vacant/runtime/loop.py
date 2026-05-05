"""Async lifecycle loop wiring state machine + heartbeat + store.

P1's `RuntimeLoop` is the *minimal* per-vacant runtime: it accepts
`Event`s, drives the state machine, persists logbook deltas through a
`LogbookStore`, and (optionally) runs a `HeartbeatScheduler` in the
background. Higher-level concerns — A2A endpoint, peer review pipeline,
budget bookkeeping — are intentionally *not* in this loop; they belong to
P3 / P4 / P6 and consume the events/logbook this loop produces.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from vacant.core.crypto import SigningKey
from vacant.core.types import LogEntry, ResidentForm, VacantState
from vacant.runtime.heartbeat import HeartbeatScheduler
from vacant.runtime.state_machine import Event, VacantStateMachine
from vacant.runtime.store import LogbookStore

__all__ = ["RuntimeLoop"]


class RuntimeLoop:
    """Per-vacant lifecycle loop.

    The loop is constructed *around* an existing `ResidentForm`; identity
    creation lives in P2. The `signing_key` is held in memory for as long
    as the loop runs (`vacant.identity` will later wrap this in a real
    custody boundary; see THEORY_V5 §0.1).
    """

    def __init__(
        self,
        *,
        form: ResidentForm,
        signing_key: SigningKey,
        store: LogbookStore,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._form = form
        self._signing_key = signing_key
        self._store = store
        self._clock = clock
        self._sm = VacantStateMachine(form.runtime_state)
        self._last_active: datetime | None = (
            clock() if form.runtime_state in {VacantState.ACTIVE, VacantState.LOCAL} else None
        )

    # --- read-only properties ------------------------------------------------

    @property
    def form(self) -> ResidentForm:
        return self._form

    @property
    def state(self) -> VacantState:
        return self._sm.state

    @property
    def state_machine(self) -> VacantStateMachine:
        return self._sm

    # --- public API ----------------------------------------------------------

    async def submit(self, event: Event) -> VacantState:
        """Apply `event`, persist the resulting logbook, return the new state."""
        new_state = self._sm.apply(event)
        if new_state in {VacantState.ACTIVE, VacantState.LOCAL}:
            self._last_active = self._clock()
        self._form = self._form.model_copy(update={"runtime_state": new_state})
        await self._store.save(self._form.identity, self._form.logbook)
        return new_state

    async def append_log(self, kind: str, payload: dict[str, Any]) -> LogEntry:
        """Append a free-form entry to the logbook and persist."""
        entry = self._form.logbook.append(kind, payload, self._signing_key, ts=self._clock())
        await self._store.save(self._form.identity, self._form.logbook)
        return entry

    def heartbeat_scheduler(
        self,
        *,
        sleep: Callable[[float], Any] = asyncio.sleep,
    ) -> HeartbeatScheduler:
        """Build a `HeartbeatScheduler` bound to this loop's logbook + state."""
        return HeartbeatScheduler(
            logbook=self._form.logbook,
            signing_key=self._signing_key,
            state_provider=lambda: self._sm.state,
            sleep=sleep,
            clock=self._clock,
            last_active_provider=lambda: self._last_active,
        )
