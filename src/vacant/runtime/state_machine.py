"""Vacant lifecycle state machine.

Six states (`VacantState` from P0) by seven events (`Event` below): 42 cells.
The transition table is an explicit `dict[(state, event), state']`. Cells
absent from the table are *invalid* — applying them raises
`InvalidEventError` rather than silently no-op'ing, because at this layer a
misrouted event is a programming bug (the envelope-level checks in P6 §3.2
are responsible for rejecting requests before they reach this state machine).

Transitions are derived from:
- `architecture/components/P1_runtime.md` §3.8 (state machine diagram)
- `architecture/decisions/D001_hibernation_and_stale_revival.md` (warmup is
  collapsed into REVIVE_REQUESTED here; P1's full warmup ceremony is a
  later component concern, see follow-up note in PR description)
- `architecture/decisions/D003_p1_runtime_reconciliation.md` (`can_review`
  semantics for STALE)

Predicates exposed for downstream use:
- `can_review(state)` — used by P3 reputation
- `can_be_called(state)` / `is_runnable(state)` — LOCAL is fully runnable
  (CLAUDE.md §LOCAL); the only difference vs ACTIVE is registry visibility
- `requires_revive(state)` — STALE only

Sunk-heartbeat semantics (THEORY_V5 §4.2 / dispatch §1) are encoded in
`heartbeat_payload(state, ...)` in `runtime/heartbeat.py` — the state
machine itself doesn't know about payloads, just about transitions.
"""

from __future__ import annotations

from enum import StrEnum

from vacant.core.types import VacantState
from vacant.runtime.errors import InvalidEventError

__all__ = [
    "Event",
    "VacantStateMachine",
    "can_be_called",
    "can_review",
    "is_runnable",
    "requires_revive",
]


class Event(StrEnum):
    """Events the runtime feeds into the state machine."""

    TICK = "TICK"
    """Periodic housekeeping pulse."""
    HEARTBEAT = "HEARTBEAT"
    """A heartbeat attestation is being emitted."""
    CALL_RECEIVED = "CALL_RECEIVED"
    """An incoming A2A call is being accepted (passed §3.2 envelope checks)."""
    REVIEW_RECEIVED = "REVIEW_RECEIVED"
    """A peer/caller review landed in this vacant's logbook."""
    REVIVE_REQUESTED = "REVIVE_REQUESTED"
    """Owner / scheduler requests transition out of HIBERNATING or STALE."""
    ARCHIVE_REQUESTED = "ARCHIVE_REQUESTED"
    """Sunk vacant has aged past `ARCHIVED_AFTER_SUNK_DAYS`."""
    SPAWN_REQUESTED = "SPAWN_REQUESTED"
    """A spawn (D1-D5) ceremony is being initiated by the parent."""


_S = VacantState
_E = Event


_TRANSITIONS: dict[tuple[VacantState, Event], VacantState] = {
    # --- LOCAL ---------------------------------------------------------------
    (_S.LOCAL, _E.TICK): _S.LOCAL,
    (_S.LOCAL, _E.HEARTBEAT): _S.LOCAL,
    (_S.LOCAL, _E.CALL_RECEIVED): _S.LOCAL,
    (_S.LOCAL, _E.REVIEW_RECEIVED): _S.LOCAL,
    (_S.LOCAL, _E.SPAWN_REQUESTED): _S.LOCAL,
    # --- ACTIVE --------------------------------------------------------------
    (_S.ACTIVE, _E.TICK): _S.ACTIVE,
    (_S.ACTIVE, _E.HEARTBEAT): _S.ACTIVE,
    (_S.ACTIVE, _E.CALL_RECEIVED): _S.ACTIVE,
    (_S.ACTIVE, _E.REVIEW_RECEIVED): _S.ACTIVE,
    (_S.ACTIVE, _E.SPAWN_REQUESTED): _S.ACTIVE,
    # --- HIBERNATING ---------------------------------------------------------
    (_S.HIBERNATING, _E.TICK): _S.HIBERNATING,
    (_S.HIBERNATING, _E.HEARTBEAT): _S.HIBERNATING,
    (_S.HIBERNATING, _E.REVIEW_RECEIVED): _S.HIBERNATING,
    (_S.HIBERNATING, _E.REVIVE_REQUESTED): _S.ACTIVE,
    # CALL_RECEIVED / SPAWN_REQUESTED / ARCHIVE_REQUESTED → invalid
    # --- STALE ---------------------------------------------------------------
    (_S.STALE, _E.TICK): _S.STALE,
    (_S.STALE, _E.HEARTBEAT): _S.STALE,
    (_S.STALE, _E.REVIEW_RECEIVED): _S.STALE,
    (_S.STALE, _E.REVIVE_REQUESTED): _S.ACTIVE,
    # --- SUNK ----------------------------------------------------------------
    (_S.SUNK, _E.TICK): _S.SUNK,
    (_S.SUNK, _E.HEARTBEAT): _S.SUNK,  # custody attestation, not liveness
    (_S.SUNK, _E.REVIEW_RECEIVED): _S.SUNK,  # late reviews persist (§4.1)
    (_S.SUNK, _E.ARCHIVE_REQUESTED): _S.ARCHIVED,
    # --- ARCHIVED ------------------------------------------------------------
    (_S.ARCHIVED, _E.TICK): _S.ARCHIVED,
    # HEARTBEAT in ARCHIVED is invalid — scheduler must not run (dispatch §2)
}


_REVIEW_OK: frozenset[VacantState] = frozenset({_S.LOCAL, _S.ACTIVE, _S.HIBERNATING})
_RUNNABLE: frozenset[VacantState] = frozenset({_S.LOCAL, _S.ACTIVE})


def can_review(state: VacantState) -> bool:
    """True iff a vacant in `state` may emit new peer/caller reviews.

    False for STALE, SUNK, ARCHIVED (THEORY_V5 §4.1; D003 §A).
    """
    return state in _REVIEW_OK


def can_be_called(state: VacantState) -> bool:
    """True iff this vacant accepts new A2A calls."""
    return state in _RUNNABLE


def is_runnable(state: VacantState) -> bool:
    """True iff the runtime should serve traffic. LOCAL is runnable
    (CLAUDE.md §LOCAL: registry visibility=none, but everything else works).
    """
    return state in _RUNNABLE


def requires_revive(state: VacantState) -> bool:
    """True iff the vacant is frozen pending a REVIVE_REQUESTED event."""
    return state == _S.STALE


class VacantStateMachine:
    """Stateful wrapper around the transition table.

    Constructed with a starting state; `apply(event)` mutates `state` in
    place and returns the new state. Use `peek(state, event)` if you want
    to evaluate a transition without mutating.
    """

    __slots__ = ("_state",)

    def __init__(self, initial: VacantState = VacantState.LOCAL) -> None:
        self._state = initial

    @property
    def state(self) -> VacantState:
        return self._state

    @classmethod
    def transitions(cls) -> dict[tuple[VacantState, Event], VacantState]:
        """A copy of the transition table; useful for exhaustive tests."""
        return dict(_TRANSITIONS)

    @classmethod
    def peek(cls, state: VacantState, event: Event) -> VacantState:
        """Pure transition lookup. Raises `InvalidEventError` if undefined."""
        try:
            return _TRANSITIONS[(state, event)]
        except KeyError as exc:
            raise InvalidEventError(
                f"event {event.value} is not valid in state {state.value}"
            ) from exc

    def apply(self, event: Event) -> VacantState:
        """Apply `event`, mutate `self.state`, return the new state."""
        new_state = self.peek(self._state, event)
        self._state = new_state
        return new_state

    def can_review(self) -> bool:
        return can_review(self._state)

    def can_be_called(self) -> bool:
        return can_be_called(self._state)

    def is_runnable(self) -> bool:
        return is_runnable(self._state)

    def requires_revive(self) -> bool:
        return requires_revive(self._state)
