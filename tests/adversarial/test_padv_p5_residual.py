"""Padv P5 -- regression guards for documented residual risks.

Spec anchors:
- `architecture/decisions/D013_padv_p5_findings.md` (residual risks)
- `dispatch/Padv_review.md` §"P5 Composite attacks to consider"
"""

from __future__ import annotations

import pytest

from vacant.composite import (
    ChildHandler,
    ChildManifest,
    ChildRecord,
    CompositeRuntime,
    CompositeStubDetector,
    GraduationService,
    make_graduation_request,
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


def _form_and_key(state: VacantState = VacantState.LOCAL):  # type: ignore[no-untyped-def]
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    bundle = BehaviorBundle(system_prompt="x")
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
        ChildManifest(parent_id=p_id, child_id=c_id, birth_path="D2", closed_by_default=True)
        .signed_by_parent(sk_p)
        .signed_by_child(sk_c)
    )


def _noop_handler() -> ChildHandler:
    async def h(_subtask: object) -> str:
        return "ok"

    return h


# --- Residual 1: no min-review-count gate (D013 §"Min-review-count") ------
# The dispatch describes graduation laundering's defense as "rate
# limit + 3-layer check + min-review-count threshold". P5 implements
# the first two; the min-review-count gate is future work because the
# closed environment's mini_rep signals (P5 §3.6) are intentionally
# weak and using them as a hard gate would let an attacker drown the
# signal in noise. The MVP relies on rate limit + collusion check +
# parent consent as cost-raising layers.


@pytest.mark.asyncio
async def test_residual_zero_review_child_can_graduate_with_consent() -> None:
    """Pin: a child with no recorded reviews can still graduate as
    long as parent consents and the rate limit + collusion gates pass.
    A future PR will add a min-review-count gate; until then, the
    parent's consent is the load-bearing decision."""
    sk_p, p_id, p_form = _form_and_key(state=VacantState.ACTIVE)
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
    # Child has only a "genesis" entry (no reviews, no executions).
    assert len(c_form.logbook.entries) == 1
    service = GraduationService(detector=CompositeStubDetector())
    req = make_graduation_request(
        parent_id=p_id,
        parent_signing_key=sk_p,
        child_id=c_id,
        child_signing_key=sk_c,
        capability_text="x",
    )
    outcome = await service.graduate(runtime=runtime, request=req)
    assert outcome.new_manifest.closed_by_default is False


def test_residual_graduation_service_does_not_implement_min_reviews() -> None:
    """Regression guard: GraduationService has no `min_reviews` knob.
    A future PR adding one should fail this test, prompting a re-read
    of D013 + the addition of a positive test for the new gate."""
    import inspect

    sig = inspect.signature(GraduationService.__init__)
    assert "min_reviews" not in sig.parameters
    assert "min_review_count" not in sig.parameters


# --- Residual 2: same-tree signal requires P3 wiring ----------------------
# `vacant.composite.collusion` defines a `CollusionDetector` Protocol;
# the default stub returns 0 on every signal. P3-backed callers
# (typically P7 demo orchestration) inject a detector that *does*
# compute same-substrate / same-stylo / same-controller signals
# against the parent-child pair. Until P3 is wired, sibling-collusion
# rings only face the rate-limit + parent-consent gates.


def test_residual_default_detector_returns_zero_signals() -> None:
    from vacant.composite import default_detector

    detector = default_detector()
    # The signal pair (any, any) returns zeros under the default detector.
    sk1, vk1 = keygen()
    sk2, vk2 = keygen()
    a = VacantId.from_verify_key(vk1)
    b = VacantId.from_verify_key(vk2)
    sigs = detector.signals_for(a, b)
    assert sigs.same_controller == 0.0
    assert sigs.same_substrate == 0.0
    assert sigs.same_stylo == 0.0
    _ = (sk1, sk2)


# --- Residual 3: tree_only_filter is a callsite gate, not network MW -----
# D012 §G pins this as P7 follow-up. The filter exists, the
# orchestrator's `outbound_call` calls it; wiring into the actual
# socket layer (so a closed child runtime cannot bypass it by
# constructing its own httpx.AsyncClient) is future work.


def test_residual_tree_only_filter_is_a_function_not_network_middleware() -> None:
    """Pin: tree_only_filter is exposed as a function callers wire into
    their dispatch surface. Production wiring (gating every outbound
    httpx.AsyncClient socket from a closed child runtime) is P7
    follow-up per D012 §G."""
    from vacant.composite import tree_only_filter

    # The filter is a module-level function, not a class with state or
    # a network adapter.
    assert callable(tree_only_filter)
    # It also has no notion of HTTP / sockets / TLS in its parameters --
    # it's purely a (caller_manifest, callee_id, siblings) gate.
    import inspect

    params = set(inspect.signature(tree_only_filter).parameters)
    assert params == {"caller_manifest", "callee_id", "siblings"}


# --- Residual 4: graduation does not publish to P4 -----------------------
# D012 §E pins this: GraduationService returns a CapabilityCard, the
# caller wires `publish_halo`. A regression that adds direct registry
# I/O inside P5 should fail this test.


def test_residual_graduation_module_does_not_import_registry() -> None:
    import vacant.composite.graduation as grad_mod

    src = grad_mod.__file__
    with open(src, encoding="utf-8") as f:
        text = f.read()
    # Cite-anchored guard: we explicitly want NO `from vacant.registry`
    # import in P5's graduation module (D012 §E).
    assert "from vacant.registry" not in text
    assert "import vacant.registry" not in text


# --- Residual 5: composite parent's logbook chain integrity --------------
# Sanity regression: dual-write to both parent + child logbooks must
# preserve BLAKE2b chain integrity even with concurrent delegations.


@pytest.mark.asyncio
async def test_residual_concurrent_delegation_preserves_chain() -> None:
    """Two awaited delegations in sequence keep the parent chain valid.
    The orchestrator's `self._lock` serialises parent-logbook writes."""
    import asyncio

    sk_p, p_id, p_form = _form_and_key(state=VacantState.ACTIVE)
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
    # Issue 5 concurrent delegations to the same child.
    await asyncio.gather(*(runtime.delegate(child_id=c_id, subtask={"i": i}) for i in range(5)))
    assert p_form.logbook.verify_chain(p_id.verify_key()) is True
    assert c_form.logbook.verify_chain(c_id.verify_key()) is True
