"""Exhaustive `(state, event) → state'` coverage for `VacantStateMachine`."""

from __future__ import annotations

import pytest

from vacant.core.types import VacantState
from vacant.runtime.errors import InvalidEventError
from vacant.runtime.state_machine import (
    Event,
    VacantStateMachine,
    can_be_called,
    can_review,
    is_runnable,
    requires_revive,
)

# --- transition table -----------------------------------------------------

_VALID: dict[tuple[VacantState, Event], VacantState] = VacantStateMachine.transitions()


def test_table_covers_expected_size() -> None:
    # Hand-counted in state_machine.py: LOCAL/ACTIVE 5 each, HIBERNATING 4,
    # STALE 4, SUNK 4, ARCHIVED 1 = 23 valid cells out of 6*7=42.
    assert len(_VALID) == 23


@pytest.mark.parametrize(
    ("state", "event"),
    sorted(
        ((s, e) for s in VacantState for e in Event),
        key=lambda p: (p[0].value, p[1].value),
    ),
)
def test_every_state_event_pair_is_classified(state: VacantState, event: Event) -> None:
    """Either the table maps to a `VacantState`, or `peek` raises."""
    if (state, event) in _VALID:
        assert VacantStateMachine.peek(state, event) == _VALID[(state, event)]
    else:
        with pytest.raises(InvalidEventError):
            VacantStateMachine.peek(state, event)


def test_apply_mutates_state() -> None:
    sm = VacantStateMachine(VacantState.HIBERNATING)
    assert sm.state == VacantState.HIBERNATING
    new = sm.apply(Event.REVIVE_REQUESTED)
    assert new == VacantState.ACTIVE
    assert sm.state == VacantState.ACTIVE


def test_apply_invalid_raises_and_does_not_mutate() -> None:
    sm = VacantStateMachine(VacantState.SUNK)
    with pytest.raises(InvalidEventError):
        sm.apply(Event.CALL_RECEIVED)
    assert sm.state == VacantState.SUNK


def test_revive_lifts_hibernating_to_active() -> None:
    assert (
        VacantStateMachine.peek(VacantState.HIBERNATING, Event.REVIVE_REQUESTED)
        == VacantState.ACTIVE
    )


def test_revive_lifts_stale_to_active() -> None:
    assert VacantStateMachine.peek(VacantState.STALE, Event.REVIVE_REQUESTED) == VacantState.ACTIVE


def test_revive_in_active_is_invalid() -> None:
    with pytest.raises(InvalidEventError):
        VacantStateMachine.peek(VacantState.ACTIVE, Event.REVIVE_REQUESTED)


def test_archive_only_from_sunk() -> None:
    assert (
        VacantStateMachine.peek(VacantState.SUNK, Event.ARCHIVE_REQUESTED) == VacantState.ARCHIVED
    )
    for s in (
        VacantState.LOCAL,
        VacantState.ACTIVE,
        VacantState.HIBERNATING,
        VacantState.STALE,
        VacantState.ARCHIVED,
    ):
        with pytest.raises(InvalidEventError):
            VacantStateMachine.peek(s, Event.ARCHIVE_REQUESTED)


def test_call_only_in_runnable_states() -> None:
    for s in (VacantState.LOCAL, VacantState.ACTIVE):
        assert VacantStateMachine.peek(s, Event.CALL_RECEIVED) == s
    for s in (
        VacantState.HIBERNATING,
        VacantState.STALE,
        VacantState.SUNK,
        VacantState.ARCHIVED,
    ):
        with pytest.raises(InvalidEventError):
            VacantStateMachine.peek(s, Event.CALL_RECEIVED)


def test_heartbeat_invalid_only_in_archived() -> None:
    for s in VacantState:
        if s == VacantState.ARCHIVED:
            with pytest.raises(InvalidEventError):
                VacantStateMachine.peek(s, Event.HEARTBEAT)
        else:
            assert VacantStateMachine.peek(s, Event.HEARTBEAT) == s


def test_archived_is_terminal() -> None:
    """No event can leave ARCHIVED except TICK no-op."""
    for e in Event:
        if e == Event.TICK:
            assert VacantStateMachine.peek(VacantState.ARCHIVED, e) == VacantState.ARCHIVED
        else:
            with pytest.raises(InvalidEventError):
                VacantStateMachine.peek(VacantState.ARCHIVED, e)


# --- predicates ----------------------------------------------------------


def test_can_review_matches_theory_v5_section_4_1() -> None:
    assert can_review(VacantState.LOCAL) is True
    assert can_review(VacantState.ACTIVE) is True
    assert can_review(VacantState.HIBERNATING) is True
    assert can_review(VacantState.STALE) is False
    assert can_review(VacantState.SUNK) is False
    assert can_review(VacantState.ARCHIVED) is False


def test_can_be_called_matches_dispatch() -> None:
    assert can_be_called(VacantState.LOCAL) is True
    assert can_be_called(VacantState.ACTIVE) is True
    for s in (
        VacantState.HIBERNATING,
        VacantState.STALE,
        VacantState.SUNK,
        VacantState.ARCHIVED,
    ):
        assert can_be_called(s) is False


def test_is_runnable_matches_can_be_called() -> None:
    for s in VacantState:
        assert is_runnable(s) == can_be_called(s)


def test_requires_revive_only_for_stale() -> None:
    for s in VacantState:
        assert requires_revive(s) == (s == VacantState.STALE)


def test_state_machine_predicates_proxy_to_module_funcs() -> None:
    sm = VacantStateMachine(VacantState.STALE)
    assert sm.requires_revive() is True
    assert sm.can_review() is False
    assert sm.can_be_called() is False
    assert sm.is_runnable() is False
