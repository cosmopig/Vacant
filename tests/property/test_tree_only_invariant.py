"""Hypothesis property: a closed child's call only succeeds if the
target is in the same tree (parent or sibling)."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from vacant.composite import (
    ChildManifest,
    is_call_allowed,
    siblings_of,
)
from vacant.core.crypto import keygen
from vacant.core.types import VacantId


def _id() -> VacantId:
    _sk, vk = keygen()
    return VacantId.from_verify_key(vk)


def _manifest(parent: VacantId, child: VacantId, *, closed: bool = True) -> ChildManifest:
    return ChildManifest(
        parent_id=parent,
        child_id=child,
        birth_path="D2",
        closed_by_default=closed,
    )


@given(
    n_children=st.integers(min_value=1, max_value=6),
    n_other_targets=st.integers(min_value=1, max_value=6),
    caller_idx=st.integers(min_value=0, max_value=5),
    callee_choice=st.integers(min_value=0, max_value=20),
)
@settings(max_examples=200, deadline=None)
def test_closed_child_call_succeeds_iff_target_in_tree(
    n_children: int,
    n_other_targets: int,
    caller_idx: int,
    callee_choice: int,
) -> None:
    """For a randomly generated tree, a closed child's call to a
    randomly chosen target succeeds iff the target is the parent or a
    sibling. Cross-tree / external targets always fail."""
    parent = _id()
    children = [_id() for _ in range(n_children)]
    others = [_id() for _ in range(n_other_targets)]
    manifests = [_manifest(parent, c) for c in children]
    caller = children[caller_idx % n_children]
    caller_manifest = next(m for m in manifests if m.child_id == caller)
    siblings = siblings_of(caller, manifests)
    # Build the universe of possible callees: parent + all children + externals.
    universe: list[VacantId] = [parent, *children, *others]
    callee = universe[callee_choice % len(universe)]
    in_tree = (callee == parent) or (callee in siblings)
    if callee == caller:
        # Self-call: not in `siblings_of(caller)` (excluded), and not parent.
        assert in_tree is False
    allowed = is_call_allowed(
        caller_manifest=caller_manifest,
        callee_id=callee,
        siblings=siblings,
    )
    assert allowed == in_tree


@given(
    n_children=st.integers(min_value=1, max_value=6),
    callee_choice=st.integers(min_value=0, max_value=20),
)
@settings(max_examples=100, deadline=None)
def test_graduated_child_can_call_anyone(n_children: int, callee_choice: int) -> None:
    """Graduated child (`closed_by_default=False`) bypasses the gate --
    every callee is allowed."""
    parent = _id()
    children = [_id() for _ in range(n_children)]
    others = [_id() for _ in range(3)]
    caller = children[0]
    manifest = _manifest(parent, caller, closed=False)
    universe = [parent, *children, *others]
    callee = universe[callee_choice % len(universe)]
    assert is_call_allowed(caller_manifest=manifest, callee_id=callee) is True


@given(
    n_trees=st.integers(min_value=2, max_value=5),
    n_per_tree=st.integers(min_value=1, max_value=4),
    caller_tree=st.integers(min_value=0, max_value=4),
    target_tree=st.integers(min_value=0, max_value=4),
)
@settings(max_examples=100, deadline=None)
def test_cross_tree_calls_blocked(
    n_trees: int,
    n_per_tree: int,
    caller_tree: int,
    target_tree: int,
) -> None:
    """Multi-tree fuzz: a closed child of tree A cannot call a child of
    tree B (B != A)."""
    parents = [_id() for _ in range(n_trees)]
    trees: list[list[VacantId]] = [[_id() for _ in range(n_per_tree)] for _ in range(n_trees)]
    manifests: list[ChildManifest] = []
    for parent, kids in zip(parents, trees, strict=True):
        manifests.extend(_manifest(parent, k) for k in kids)
    caller_t = caller_tree % n_trees
    target_t = target_tree % n_trees
    caller = trees[caller_t][0]
    target = trees[target_t][0]
    caller_manifest = next(m for m in manifests if m.child_id == caller)
    siblings = siblings_of(caller, manifests)
    allowed = is_call_allowed(
        caller_manifest=caller_manifest,
        callee_id=target,
        siblings=siblings,
    )
    if caller_t == target_t:
        # Same tree -- target is either self (blocked) or sibling (allowed).
        assert allowed == (target != caller)
    else:
        # Different tree -- always blocked (target not parent, not sibling).
        assert allowed is False
