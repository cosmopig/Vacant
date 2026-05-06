"""Tree-Only outbound filter tests."""

from __future__ import annotations

import pytest

from vacant.composite import (
    ChildManifest,
    TreeOnlyViolationError,
    is_call_allowed,
    siblings_of,
    tree_only_filter,
)
from vacant.core.crypto import keygen
from vacant.core.types import VacantId


def _id():  # type: ignore[no-untyped-def]
    _sk, vk = keygen()
    return VacantId.from_verify_key(vk)


def _manifest(parent_id, child_id, *, closed=True):  # type: ignore[no-untyped-def]
    return ChildManifest(
        parent_id=parent_id,
        child_id=child_id,
        birth_path="D2",
        closed_by_default=closed,
    )


def test_closed_child_can_call_parent() -> None:
    parent = _id()
    child = _id()
    m = _manifest(parent, child)
    assert is_call_allowed(caller_manifest=m, callee_id=parent) is True
    tree_only_filter(caller_manifest=m, callee_id=parent)


def test_closed_child_can_call_sibling_in_same_tree() -> None:
    parent = _id()
    child_a = _id()
    child_b = _id()
    m_a = _manifest(parent, child_a)
    m_b = _manifest(parent, child_b)
    siblings = siblings_of(child_a, [m_a, m_b])
    assert child_b in siblings
    assert is_call_allowed(caller_manifest=m_a, callee_id=child_b, siblings=siblings) is True


def test_closed_child_blocked_from_external_call() -> None:
    parent = _id()
    child = _id()
    external = _id()
    m = _manifest(parent, child)
    with pytest.raises(TreeOnlyViolationError):
        tree_only_filter(caller_manifest=m, callee_id=external)


def test_closed_child_blocked_from_cross_tree_call() -> None:
    parent_a = _id()
    parent_b = _id()
    child_a = _id()
    child_b = _id()
    m_a = _manifest(parent_a, child_a)
    m_b = _manifest(parent_b, child_b)
    # Cross-tree: child_a tries to call child_b under a different parent.
    siblings_a = siblings_of(child_a, [m_a])
    assert child_b not in siblings_a
    with pytest.raises(TreeOnlyViolationError):
        tree_only_filter(caller_manifest=m_a, callee_id=child_b, siblings=siblings_a)
    _ = m_b


def test_graduated_child_bypasses_filter() -> None:
    """closed_by_default=False (post-graduation) -> filter no-ops."""
    parent = _id()
    child = _id()
    external = _id()
    m = _manifest(parent, child, closed=False)
    # Graduated child can reach an external target -- the filter must NOT raise.
    tree_only_filter(caller_manifest=m, callee_id=external)
    assert is_call_allowed(caller_manifest=m, callee_id=external) is True


def test_siblings_of_excludes_self() -> None:
    parent = _id()
    a = _id()
    b = _id()
    c = _id()
    manifests = [_manifest(parent, a), _manifest(parent, b), _manifest(parent, c)]
    s = siblings_of(a, manifests)
    assert s == {b, c}
    assert a not in s


def test_siblings_of_returns_empty_for_unknown_child() -> None:
    parent = _id()
    a = _id()
    unknown = _id()
    manifests = [_manifest(parent, a)]
    assert siblings_of(unknown, manifests) == set()


def test_filter_disabled_siblings_blocks_sibling_call() -> None:
    """Pass `siblings=None` to disable sibling calls entirely (parent only)."""
    parent = _id()
    a = _id()
    b = _id()
    m_a = _manifest(parent, a)
    with pytest.raises(TreeOnlyViolationError):
        tree_only_filter(caller_manifest=m_a, callee_id=b, siblings=None)
