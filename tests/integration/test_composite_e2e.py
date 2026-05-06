"""End-to-end composite scenario: parent + 3 D2 children handle a
composite query; one child graduates; post-graduation it answers a
direct external call."""

from __future__ import annotations

import pytest

from vacant.composite import (
    AGGREGATE_KIND,
    DELEGATE_KIND,
    EXECUTE_KIND,
    GRADUATED_KIND,
    ChildManifest,
    ChildRecord,
    CompositeRuntime,
    CompositeStubDetector,
    GraduationService,
    TreeOnlyViolationError,
    make_graduation_request,
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

pytestmark = pytest.mark.slow


def _form_and_key(state: VacantState = VacantState.LOCAL):  # type: ignore[no-untyped-def]
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    bundle = BehaviorBundle(system_prompt="x", tool_whitelist=["text"])
    spec = SubstrateSpec(allowed_substrates=["mock"])
    lb = Logbook()
    lb.append("genesis", {}, sk)
    return (
        sk,
        vid,
        ResidentForm(
            identity=vid,
            logbook=lb,
            behavior_bundle=bundle,
            substrate_spec=spec,
            runtime_state=state,
        ),
    )


def _signed_manifest(p_id, c_id, sk_p, sk_c):  # type: ignore[no-untyped-def]
    return (
        ChildManifest(
            parent_id=p_id,
            child_id=c_id,
            birth_path="D2",
            closed_by_default=True,
            tool_whitelist_inherited=["text"],
        )
        .signed_by_parent(sk_p)
        .signed_by_child(sk_c)
    )


@pytest.mark.asyncio
async def test_parent_with_three_children_aggregates_and_one_graduates() -> None:
    """End-to-end: 1 composite parent + 3 closed children answer a
    multi-step query. Then one child graduates and accepts a direct
    external call without going through the parent."""
    sk_p, p_id, p_form = _form_and_key(VacantState.ACTIVE)
    runtime = CompositeRuntime(parent_form=p_form, parent_signing_key=sk_p)

    children = []
    for capability in ("research", "writing", "review"):
        sk_c, c_id, c_form = _form_and_key()

        async def handler(subtask, _cap=capability):  # type: ignore[no-untyped-def]
            return {"capability": _cap, "input": subtask}

        runtime.register_child(
            ChildRecord(
                manifest=_signed_manifest(p_id, c_id, sk_p, sk_c),
                child_form=c_form,
                child_signing_key=sk_c,
                handler=handler,
            )
        )
        children.append((sk_c, c_id, c_form, capability))

    # 1. Run a composite query: delegate to all three, aggregate.
    plan = [(c_id, {"kind": "subtask", "text": f"do {cap}"}) for _, c_id, _, cap in children]
    results = await runtime.delegate_many(plan)
    aggregated = runtime.aggregate(results)
    assert len(aggregated) == 3
    capabilities = {r["capability"] for r in aggregated}
    assert capabilities == {"research", "writing", "review"}

    # 2. Parent's logbook: 3 DELEGATEs + 1 AGGREGATE on top of the genesis entry.
    parent_kinds = [e.kind for e in p_form.logbook.entries]
    assert parent_kinds.count(DELEGATE_KIND) == 3
    assert parent_kinds.count(AGGREGATE_KIND) == 1
    # Each child's logbook: 1 EXECUTE entry on top of genesis.
    for _sk_c, _c_id, c_form, _cap in children:
        kinds = [e.kind for e in c_form.logbook.entries]
        assert kinds.count(EXECUTE_KIND) == 1

    # 3. Closed children cannot call external. Pick child[0] and try to
    # call something outside the tree.
    sk_c, c_id, c_form, _cap = children[0]
    sibling_ids = [other_c_id for _sk, other_c_id, _, _ in children if other_c_id != c_id]
    # Sibling call: allowed.
    tree_only_filter(
        caller_manifest=runtime.manifest_for(c_id),
        callee_id=sibling_ids[0],
        siblings=sibling_ids,
    )
    # External call: blocked.
    _ext_sk, ext_vk = keygen()
    external = VacantId.from_verify_key(ext_vk)
    with pytest.raises(TreeOnlyViolationError):
        runtime.outbound_call(caller_child_id=c_id, callee_id=external)

    # 4. Graduate child[2] (review).
    sk_c, c_id, c_form, _cap = children[2]
    service = GraduationService(detector=CompositeStubDetector())
    request = make_graduation_request(
        parent_id=p_id,
        parent_signing_key=sk_p,
        child_id=c_id,
        child_signing_key=sk_c,
        capability_text="review",
    )
    outcome = await service.graduate(runtime=runtime, request=request)
    assert outcome.new_manifest.closed_by_default is False
    assert outcome.child_card.verify() is True
    # Same identity, same logbook (extended).
    assert outcome.child_card.vacant_id == c_id
    grad_kinds = [e.kind for e in c_form.logbook.entries]
    assert grad_kinds.count(GRADUATED_KIND) == 1

    # 5. Post-graduation: child[2] can be reached by an outsider directly,
    #    bypassing the tree-only filter.
    runtime.outbound_call(caller_child_id=c_id, callee_id=external)  # no raise

    # 6. Other children remain closed; they still raise on external calls.
    sk_c, other_c_id, _, _ = children[0]
    with pytest.raises(TreeOnlyViolationError):
        runtime.outbound_call(caller_child_id=other_c_id, callee_id=external)


@pytest.mark.asyncio
async def test_parent_logbook_chain_remains_intact_through_composite_run() -> None:
    """The parent's logbook hash chain must verify after delegation +
    aggregation + graduation. This is the load-bearing audit
    invariant."""
    sk_p, p_id, p_form = _form_and_key(VacantState.ACTIVE)
    runtime = CompositeRuntime(parent_form=p_form, parent_signing_key=sk_p)
    sk_c, c_id, c_form = _form_and_key()

    async def handler(subtask: object) -> str:
        return "ok"

    runtime.register_child(
        ChildRecord(
            manifest=_signed_manifest(p_id, c_id, sk_p, sk_c),
            child_form=c_form,
            child_signing_key=sk_c,
            handler=handler,
        )
    )
    results = await runtime.delegate_many([(c_id, {"x": 1}), (c_id, {"x": 2})])
    runtime.aggregate(results)

    service = GraduationService(detector=CompositeStubDetector())
    req = make_graduation_request(
        parent_id=p_id,
        parent_signing_key=sk_p,
        child_id=c_id,
        child_signing_key=sk_c,
        capability_text="x",
    )
    await service.graduate(runtime=runtime, request=req)

    assert p_form.logbook.verify_chain(p_id.verify_key()) is True
    assert c_form.logbook.verify_chain(c_id.verify_key()) is True
