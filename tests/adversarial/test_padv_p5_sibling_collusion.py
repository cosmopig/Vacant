"""Padv P5 -- Sibling collusion ring (dispatch §"Sibling collusion ring").

Spec anchors:
- `architecture/components/P5_composite.md` §3.6 (internal evaluation
  signals + the structural limit in closed environments)
- `architecture/decisions/D012_p5_composite_reconciliation.md` §B,§D
- `architecture/decisions/D013_padv_p5_findings.md` §"Same-tree signal
  residual"
- `dispatch/Padv_review.md` §"P5 Composite attacks to consider"

The dispatch describes the attack: three siblings give each other
reviews to inflate before graduation. The dispatch's stated defense
is "same-tree signal applied as discount in P3". P5 itself does not
implement that signal; instead the graduation gate consumes a
`CollusionDetector` that any caller (typically P7 wiring P3) supplies.
This file tests:
1. The collusion gate trips when a detector reports same-tree-style
   signals above threshold.
2. A P3-less build (default detector returning zero) does NOT block
   sibling-collusion graduations -- this is the residual the spec
   acknowledges, captured in D013.
"""

from __future__ import annotations

import pytest

from vacant.composite import (
    ChildHandler,
    ChildManifest,
    ChildRecord,
    CollusionSignals,
    CompositeRuntime,
    CompositeStubDetector,
    GraduationCollusionError,
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


def _build_runtime_with_three_siblings():  # type: ignore[no-untyped-def]
    sk_p, p_id, p_form = _form_and_key(state=VacantState.ACTIVE)
    runtime = CompositeRuntime(parent_form=p_form, parent_signing_key=sk_p)
    siblings = []
    for _ in range(3):
        sk_c, c_id, c_form = _form_and_key()
        runtime.register_child(
            ChildRecord(
                manifest=_signed_manifest(p_id, c_id, sk_p, sk_c),
                child_form=c_form,
                child_signing_key=sk_c,
                handler=_noop_handler(),
            )
        )
        siblings.append((sk_c, c_id))
    return runtime, sk_p, p_id, siblings


# --- Attack 1: P3-backed detector reports high same-substrate signal ------
# Defense (D, write-time): GraduationService.graduate raises when the
# max signal strength on (parent, child) >= GRADUATION_COLLUSION_THRESHOLD.


class _SiblingFamilyDetector:
    """Detector emulating P3's same_detect: if parent and child share
    the same family (here, simulated by always returning high
    same_substrate strength for our test pair), the gate trips."""

    def __init__(self, target_pair: tuple[VacantId, VacantId], strength: float) -> None:
        self._target = target_pair
        self._strength = strength

    def signals_for(self, parent_id: VacantId, child_id: VacantId) -> CollusionSignals:
        if (parent_id, child_id) == self._target:
            return CollusionSignals(
                same_controller=0.0, same_substrate=self._strength, same_stylo=0.0
            )
        return CollusionSignals(same_controller=0.0, same_substrate=0.0, same_stylo=0.0)


@pytest.mark.asyncio
async def test_attack_high_same_substrate_signal_blocks_graduation() -> None:
    runtime, sk_p, p_id, siblings = _build_runtime_with_three_siblings()
    sk_c, c_id = siblings[0]
    detector = _SiblingFamilyDetector(target_pair=(p_id, c_id), strength=0.92)
    service = GraduationService(detector=detector)
    req = make_graduation_request(
        parent_id=p_id,
        parent_signing_key=sk_p,
        child_id=c_id,
        child_signing_key=sk_c,
        capability_text="research",
    )
    with pytest.raises(GraduationCollusionError):
        await service.graduate(runtime=runtime, request=req)


# --- Attack 2: collusion threshold is `>=` -- equal trips -----------------


@pytest.mark.asyncio
async def test_attack_signal_at_exact_threshold_trips() -> None:
    runtime, sk_p, p_id, siblings = _build_runtime_with_three_siblings()
    sk_c, c_id = siblings[1]
    detector = _SiblingFamilyDetector(target_pair=(p_id, c_id), strength=0.6)
    service = GraduationService(detector=detector, collusion_threshold=0.6)
    req = make_graduation_request(
        parent_id=p_id,
        parent_signing_key=sk_p,
        child_id=c_id,
        child_signing_key=sk_c,
        capability_text="x",
    )
    with pytest.raises(GraduationCollusionError):
        await service.graduate(runtime=runtime, request=req)


# --- Attack 3: only one of three signals high blocks graduation -----------
# Conservative composition (max-strength) means one high signal is
# enough; the other two being low does not let the collusion through.


@pytest.mark.asyncio
async def test_attack_max_strength_composition_blocks_on_one_high_signal() -> None:
    runtime, sk_p, p_id, siblings = _build_runtime_with_three_siblings()
    sk_c, c_id = siblings[2]

    class _OneHighDetector:
        def signals_for(self, parent_id: VacantId, child_id: VacantId) -> CollusionSignals:
            return CollusionSignals(
                same_controller=0.1,
                same_substrate=0.1,
                same_stylo=0.85,  # one signal is high
            )

    service = GraduationService(detector=_OneHighDetector())
    req = make_graduation_request(
        parent_id=p_id,
        parent_signing_key=sk_p,
        child_id=c_id,
        child_signing_key=sk_c,
        capability_text="x",
    )
    with pytest.raises(GraduationCollusionError):
        await service.graduate(runtime=runtime, request=req)


# --- Residual: P3-less build does not detect sibling collusion ------------
# When the detector is the default stub (returning zeros), the
# collusion gate never trips. This is the documented residual: the
# rate-limit + parent consent are the cost-raising layer, the spec's
# full defense (same-tree signal applied as discount) requires P3 to
# be wired. Captured in D013.


@pytest.mark.asyncio
async def test_residual_default_detector_does_not_block_sibling_graduation() -> None:
    runtime, sk_p, p_id, siblings = _build_runtime_with_three_siblings()
    sk_c, c_id = siblings[0]
    # Stub returning zero on every signal (the P3-less default).
    service = GraduationService(detector=CompositeStubDetector())
    req = make_graduation_request(
        parent_id=p_id,
        parent_signing_key=sk_p,
        child_id=c_id,
        child_signing_key=sk_c,
        capability_text="x",
    )
    # Graduation succeeds -- documented residual.
    outcome = await service.graduate(runtime=runtime, request=req)
    assert outcome.new_manifest.closed_by_default is False
    # Sanity: the rate limit + consent gates still hold (graduation
    # succeeded only because we provided dual signatures + were within
    # the rate limit).
