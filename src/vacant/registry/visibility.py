"""Halo visibility — the `registry_visibility` axis of THEORY_V5 §1.1's
three-axis ontology (registry_visibility x endpoint_reachability x
outbound_policy).

`Visibility.NONE` matches `VacantState.LOCAL` per CLAUDE.md §LOCAL: a
LOCAL vacant runs and signs but is not published to the public index.
The two concepts overlap at the discovery layer: `effective_visibility`
collapses the runtime state into the externally-observable visibility.
"""

from __future__ import annotations

from enum import StrEnum

from vacant.core.types import VacantState

__all__ = ["Visibility", "effective_visibility"]


class Visibility(StrEnum):
    """Discovery visibility for a halo record."""

    NONE = "NONE"
    """Not in any public index. Reachable only via owner/parent direct path."""

    RESTRICTED = "RESTRICTED"
    """Indexed but only revealed to authenticated callers (P5/P6 future)."""

    PUBLIC = "PUBLIC"
    """Default for ACTIVE-state vacants — fully discoverable."""


def effective_visibility(state: VacantState, registry_visibility: Visibility) -> Visibility:
    """Compute the discovery-layer visibility from runtime state + setting.

    LOCAL state forces `NONE` regardless of `registry_visibility` —
    CLAUDE.md §LOCAL is load-bearing: a LOCAL vacant must not appear in
    the public index even if its capability card was previously published.

    Sunk / Archived states keep their existing visibility (the halo is
    historically retained per THEORY_V5 §4.1) — but `is_runnable(state)`
    is False, so callers see the record but cannot make new calls.
    """
    if state == VacantState.LOCAL:
        return Visibility.NONE
    return registry_visibility
