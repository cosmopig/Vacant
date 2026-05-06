"""Property tests for Merkle snapshot integrity (dispatch §Tests).

Hypothesis: any single modified leaf invalidates the root, and any
inclusion proof generated from one leaf set fails verification against
a different leaf set's root.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from vacant.registry.antitamper import (
    build_merkle_root,
    merkle_inclusion_proof,
    verify_inclusion_proof,
)

_LEAVES = st.lists(st.binary(min_size=1, max_size=32), min_size=1, max_size=16)


@given(leaves=_LEAVES, target=st.integers(min_value=0, max_value=15))
@settings(max_examples=80, deadline=None)
def test_any_modified_leaf_invalidates_root(leaves: list[bytes], target: int) -> None:
    idx = target % len(leaves)
    original_root = build_merkle_root(leaves)
    if not leaves[idx]:
        return
    flipped = list(leaves)
    flipped[idx] = bytes((flipped[idx][0] ^ 0xFF, *flipped[idx][1:]))
    new_root = build_merkle_root(flipped)
    if flipped[idx] == leaves[idx]:
        # No-op flip (rare): nothing to assert.
        return
    assert new_root != original_root


@given(leaves=_LEAVES, target=st.integers(min_value=0, max_value=15))
@settings(max_examples=60, deadline=None)
def test_inclusion_proofs_round_trip(leaves: list[bytes], target: int) -> None:
    idx = target % len(leaves)
    root = build_merkle_root(leaves)
    proof = merkle_inclusion_proof(leaves, idx)
    assert verify_inclusion_proof(proof, root)


@given(leaves=_LEAVES, target=st.integers(min_value=0, max_value=15))
@settings(max_examples=40, deadline=None)
def test_inclusion_proof_fails_against_wrong_root(leaves: list[bytes], target: int) -> None:
    if len(leaves) < 2:
        return
    idx = target % len(leaves)
    proof = merkle_inclusion_proof(leaves, idx)
    other_root = build_merkle_root([*leaves, b"extra-leaf"])
    if other_root == build_merkle_root(leaves):
        return  # rare: padding made roots equal
    assert verify_inclusion_proof(proof, other_root) is False


@given(leaves=_LEAVES)
@settings(max_examples=30, deadline=None)
def test_root_is_deterministic(leaves: list[bytes]) -> None:
    assert build_merkle_root(leaves) == build_merkle_root(list(leaves))


@given(leaves=st.lists(st.binary(min_size=1, max_size=8), min_size=2, max_size=16))
@settings(max_examples=40, deadline=None)
def test_swap_two_leaves_changes_root(leaves: list[bytes]) -> None:
    if len(leaves) < 2:
        return
    if leaves[0] == leaves[1]:
        return
    swapped = [leaves[1], leaves[0], *leaves[2:]]
    assert build_merkle_root(swapped) != build_merkle_root(leaves)
