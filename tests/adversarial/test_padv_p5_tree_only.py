"""Padv P5 -- Tree-Only bypass attempts (dispatch §"Tree-Only bypass").

Spec anchors:
- `architecture/components/P5_composite.md` §2 D2 (Tree-Only)
- `architecture/decisions/D012_p5_composite_reconciliation.md` §G
- `dispatch/Padv_review.md` §"P5 Composite attacks to consider"

Defense (P, write-time + structural): the tree is computed from the
parent's manifest list. A closed child can call only `parent_id` or a
sibling registered under the same parent. The `closed_by_default` flag
is in the manifest's signed scope, so an attacker cannot flip it
without invalidating both signatures.
"""

from __future__ import annotations

import pytest

from vacant.composite import (
    ChildHandler,
    ChildManifest,
    ChildRecord,
    CompositeRuntime,
    TreeOnlyViolationError,
    is_call_allowed,
    siblings_of,
    tree_only_filter,
)
from vacant.core.crypto import keygen
from vacant.core.types import (
    BehaviorBundle,
    Logbook,
    ResidentForm,
    SubstrateSpec,
    VacantId,
    VacantState,
)


def _id() -> VacantId:
    _sk, vk = keygen()
    return VacantId.from_verify_key(vk)


def _form_and_key():  # type: ignore[no-untyped-def]
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    return (
        sk,
        vid,
        ResidentForm(
            identity=vid,
            logbook=Logbook(),
            behavior_bundle=BehaviorBundle(system_prompt="x"),
            substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
            runtime_state=VacantState.LOCAL,
        ),
    )


def _signed_manifest(p_id, c_id, sk_p, sk_c, *, closed=True):  # type: ignore[no-untyped-def]
    return (
        ChildManifest(
            parent_id=p_id,
            child_id=c_id,
            birth_path="D2",
            closed_by_default=closed,
        )
        .signed_by_parent(sk_p)
        .signed_by_child(sk_c)
    )


def _noop_handler() -> ChildHandler:
    async def h(_subtask: object) -> str:
        return "ok"

    return h


# --- Attack 1: closed child calls direct external endpoint ----------------


def test_attack_closed_child_external_call_blocked() -> None:
    parent = _id()
    child = _id()
    external = _id()
    m = ChildManifest(parent_id=parent, child_id=child, birth_path="D2", closed_by_default=True)
    with pytest.raises(TreeOnlyViolationError):
        tree_only_filter(caller_manifest=m, callee_id=external)


# --- Attack 2: spoof closed_by_default via in-memory mutation -------------
# A pydantic frozen=True model rejects assignment, so this attack fails
# at the type-system layer.


def test_attack_in_memory_closed_flag_mutation_rejected() -> None:
    parent = _id()
    child = _id()
    m = ChildManifest(parent_id=parent, child_id=child, birth_path="D2", closed_by_default=True)
    with pytest.raises(Exception):  # noqa: B017 -- pydantic frozen-model error
        m.closed_by_default = False  # type: ignore[misc]


# --- Attack 3: cross-tree call (closed child of A calls child of B) -------


def test_attack_cross_tree_call_blocked_via_runtime() -> None:
    sk_pa, p_a_id, p_a_form = _form_and_key()
    sk_pb, p_b_id, _p_b_form = _form_and_key()
    sk_ca, c_a_id, c_a_form = _form_and_key()
    sk_cb, c_b_id, _c_b_form = _form_and_key()

    runtime_a = CompositeRuntime(parent_form=p_a_form, parent_signing_key=sk_pa)
    runtime_a.register_child(
        ChildRecord(
            manifest=_signed_manifest(p_a_id, c_a_id, sk_pa, sk_ca),
            child_form=c_a_form,
            child_signing_key=sk_ca,
            handler=_noop_handler(),
        )
    )

    # Child A calls child B (different tree). Blocked.
    with pytest.raises(TreeOnlyViolationError):
        runtime_a.outbound_call(caller_child_id=c_a_id, callee_id=c_b_id)
    # And calling parent B (a stranger composite) is also blocked.
    with pytest.raises(TreeOnlyViolationError):
        runtime_a.outbound_call(caller_child_id=c_a_id, callee_id=p_b_id)
    _ = (sk_pb, sk_cb)


# --- Attack 4: forged sibling -- claim id that's not in the parent's tree -
# A closed child cannot reach an arbitrary VacantId by *claiming* it's a
# sibling: `siblings_of(caller, manifests)` derives the sibling set from
# the parent's manifest list. Attacker-supplied "siblings" parameter
# would only matter at the call site; the runtime computes it from the
# authoritative manifest registry.


def test_attack_caller_cannot_inject_sibling_set_via_runtime() -> None:
    sk_p, p_id, p_form = _form_and_key()
    sk_c, c_id, c_form = _form_and_key()
    runtime = CompositeRuntime(parent_form=p_form, parent_signing_key=sk_p)
    runtime.register_child(
        ChildRecord(
            manifest=_signed_manifest(p_id, c_id, sk_p, sk_c),
            child_form=c_form,
            child_signing_key=sk_c,
            handler=_noop_handler(),
        )
    )
    # Attacker can't pass a "siblings" hint to runtime.outbound_call --
    # the runtime computes it internally from the manifest registry.
    forged_target = _id()
    with pytest.raises(TreeOnlyViolationError):
        runtime.outbound_call(caller_child_id=c_id, callee_id=forged_target)
    # And a child id that was never registered raises (not silently passes).
    forged_caller = _id()
    from vacant.composite import CompositeError

    with pytest.raises(CompositeError, match="unknown child"):
        runtime.outbound_call(caller_child_id=forged_caller, callee_id=p_id)


# --- Attack 5: graduated child should NOT bypass another tree's filter ----
# Defense (graduated) -- `closed_by_default=False` lets the child reach
# external targets, but the bypass is only with respect to its OWN
# manifest. A graduated child of tree A is not magically a sibling of
# tree B's children; it's just an ACTIVE vacant on the public network.


def test_attack_graduated_child_does_not_become_sibling_of_other_trees() -> None:
    parent_a = _id()
    parent_b = _id()
    grad_in_a = _id()  # graduated child of A
    closed_in_b = _id()
    # Graduated child's manifest (A side).
    m_grad = ChildManifest(
        parent_id=parent_a,
        child_id=grad_in_a,
        birth_path="D2",
        closed_by_default=False,
    )
    # Closed child of B's manifest.
    m_b = ChildManifest(
        parent_id=parent_b,
        child_id=closed_in_b,
        birth_path="D2",
        closed_by_default=True,
    )
    # Graduated child can reach anything (filter no-ops): true by design.
    assert is_call_allowed(caller_manifest=m_grad, callee_id=closed_in_b) is True
    # But B's closed child cannot reach the graduated child of A.
    siblings_b = siblings_of(closed_in_b, [m_b])
    assert is_call_allowed(caller_manifest=m_b, callee_id=grad_in_a, siblings=siblings_b) is False


# --- Attack 6: registered child cannot call external by claiming it is
# its own parent. Defense: `parent_id` must match exactly.


def test_attack_self_parent_claim_blocked() -> None:
    sk_p, p_id, p_form = _form_and_key()
    sk_c, c_id, c_form = _form_and_key()
    runtime = CompositeRuntime(parent_form=p_form, parent_signing_key=sk_p)
    runtime.register_child(
        ChildRecord(
            manifest=_signed_manifest(p_id, c_id, sk_p, sk_c),
            child_form=c_form,
            child_signing_key=sk_c,
            handler=_noop_handler(),
        )
    )
    # Calling the child's OWN id (treating self as parent) is blocked --
    # `is_call_allowed` only allows callee == manifest.parent_id, never == child_id.
    with pytest.raises(TreeOnlyViolationError):
        runtime.outbound_call(caller_child_id=c_id, callee_id=c_id)
