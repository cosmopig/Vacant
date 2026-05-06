"""Tree-Only outbound filter (P5 §2 D2 / dispatch §3).

A closed child can only call:
- its parent (the composite root), or
- a sibling within the same composite tree (mediated through the parent).

Cross-tree calls and direct external calls are rejected. The filter is
the structural enforcement of D1 (Closed children is a hard principle):
ACLs were rejected as too easy to bypass.

The orchestrator (`CompositeRuntime`) holds a list of `ChildManifest`s.
The tree itself is parent_id -> {child_id, ...}. `is_call_allowed`
takes the caller's manifest and a callee identity and returns True iff
the callee is the parent or a sibling registered under the same parent.

In production, every outbound socket from a closed-child runtime is
gated through `tree_only_filter` middleware -- given the (caller_id,
callee_id) pair, it raises `TreeOnlyViolationError` for non-tree calls.
"""

from __future__ import annotations

from collections.abc import Iterable

from vacant.composite.errors import TreeOnlyViolationError
from vacant.composite.manifest import ChildManifest
from vacant.core.types import VacantId

__all__ = [
    "is_call_allowed",
    "siblings_of",
    "tree_only_filter",
]


def siblings_of(child_id: VacantId, manifests: Iterable[ChildManifest]) -> set[VacantId]:
    """Return the set of *other* children sharing the same parent.

    Excludes the child itself."""
    by_parent: dict[VacantId, set[VacantId]] = {}
    for m in manifests:
        by_parent.setdefault(m.parent_id, set()).add(m.child_id)
    parent: VacantId | None = None
    for m in manifests:
        if m.child_id == child_id:
            parent = m.parent_id
            break
    if parent is None:
        return set()
    return by_parent.get(parent, set()) - {child_id}


def is_call_allowed(
    *,
    caller_manifest: ChildManifest,
    callee_id: VacantId,
    siblings: Iterable[VacantId] | None = None,
) -> bool:
    """True iff a closed child may call `callee_id`.

    Permitted callees:
    - `caller_manifest.parent_id` (the composite root).
    - any id in `siblings` (the orchestrator passes the precomputed
      sibling set; pass `None` to disable sibling calls entirely).

    A child whose `closed_by_default=False` is treated as graduated
    -- it can reach any callee, so this filter no-ops and returns True.
    """
    if not caller_manifest.closed_by_default:
        return True
    if callee_id == caller_manifest.parent_id:
        return True
    if siblings is not None and callee_id in set(siblings):
        return True
    return False


def tree_only_filter(
    *,
    caller_manifest: ChildManifest,
    callee_id: VacantId,
    siblings: Iterable[VacantId] | None = None,
) -> None:
    """Raise `TreeOnlyViolationError` if the call would breach Tree-Only.

    The orchestrator's outbound dispatch wires this in front of every
    network call from a closed-child runtime. A graduated child
    (`closed_by_default=False`) is unaffected."""
    if not is_call_allowed(
        caller_manifest=caller_manifest,
        callee_id=callee_id,
        siblings=siblings,
    ):
        raise TreeOnlyViolationError(
            f"closed child {caller_manifest.child_id.short()} cannot call "
            f"{callee_id.short()} (not parent / not sibling)"
        )
