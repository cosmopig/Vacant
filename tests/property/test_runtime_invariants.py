"""Property tests for runtime invariants:

- SUNK → ACTIVE only via REVIVE (and not at all in this state machine; SUNK
  has no path to ACTIVE — once sunk, the only outbound is ARCHIVE_REQUESTED
  → ARCHIVED).
- SUNK can_review() always False (THEORY_V5 §4.1).
- Logbook only grows.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from vacant.core.crypto import keygen
from vacant.core.types import Logbook, VacantState
from vacant.runtime.errors import InvalidEventError
from vacant.runtime.state_machine import (
    Event,
    VacantStateMachine,
    can_review,
)

_EVENTS = list(Event)
_STATES = list(VacantState)


@given(events=st.lists(st.sampled_from(_EVENTS), min_size=0, max_size=20))
@settings(max_examples=200, deadline=None)
def test_random_event_sequences_never_produce_invalid_state(events: list[Event]) -> None:
    sm = VacantStateMachine()
    for e in events:
        try:
            new = sm.apply(e)
        except InvalidEventError:
            continue
        assert new in _STATES


@given(events=st.lists(st.sampled_from(_EVENTS), min_size=0, max_size=30))
@settings(max_examples=200, deadline=None)
def test_sunk_never_returns_to_active(events: list[Event]) -> None:
    sm = VacantStateMachine(VacantState.SUNK)
    for e in events:
        try:
            sm.apply(e)
        except InvalidEventError:
            continue
        assert sm.state != VacantState.ACTIVE
        assert sm.state != VacantState.LOCAL


def test_sunk_cannot_review() -> None:
    """can_review(SUNK) is False, deterministically (THEORY_V5 §4.1)."""
    assert can_review(VacantState.SUNK) is False


@given(
    kinds=st.lists(
        st.text(min_size=1, max_size=8).filter(lambda s: s.strip()),
        min_size=1,
        max_size=10,
    ),
)
@settings(max_examples=50, deadline=None)
def test_logbook_only_grows(kinds: list[str]) -> None:
    sk, _vk = keygen()
    lb = Logbook()
    prev_len = 0
    for k in kinds:
        lb.append(k, {}, sk)
        assert len(lb.entries) == prev_len + 1
        prev_len += 1


@given(start=st.sampled_from(_STATES))
@settings(max_examples=20, deadline=None)
def test_revive_only_lifts_hibernating_or_stale(start: VacantState) -> None:
    """REVIVE_REQUESTED transitions to ACTIVE iff start ∈ {HIBERNATING, STALE}."""
    sm = VacantStateMachine(start)
    if start in {VacantState.HIBERNATING, VacantState.STALE}:
        assert sm.apply(Event.REVIVE_REQUESTED) == VacantState.ACTIVE
    else:
        try:
            new = sm.apply(Event.REVIVE_REQUESTED)
            # If it didn't raise, it must have been a no-op (impossible per table).
            assert new == start
        except InvalidEventError:
            pass


@given(
    starts=st.lists(st.sampled_from(_STATES), min_size=1, max_size=5),
    events=st.lists(st.sampled_from(_EVENTS), min_size=0, max_size=10),
)
@settings(max_examples=100, deadline=None)
def test_archived_is_absorbing(starts: list[VacantState], events: list[Event]) -> None:
    """Once ARCHIVED, no event sequence escapes."""
    sm = VacantStateMachine(VacantState.ARCHIVED)
    for e in events:
        try:
            sm.apply(e)
        except InvalidEventError:
            continue
    assert sm.state == VacantState.ARCHIVED
    _ = starts
