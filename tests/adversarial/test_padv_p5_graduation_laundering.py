"""Padv P5 -- Graduation laundering (dispatch §"Graduation laundering").

Spec anchors:
- `architecture/components/P5_composite.md` §3.7 (graduation)
- `architecture/decisions/D012_p5_composite_reconciliation.md` §A,§B
- `dispatch/Padv_review.md` §"P5 Composite attacks to consider"

The dispatch describes graduation laundering as: graduate a child
immediately after its first review, before there is real evidence of
capability. The spec calls for `rate limit + 3-layer check + min-
review-count threshold`. The MVP implements rate limit + collusion
check; the min-review-count gate is a documented residual (see
`architecture/decisions/D013_padv_p5_findings.md` §"Min-review-count
residual"). This file pins the existing defense layers and the
residual.
"""

from __future__ import annotations

import pytest

from vacant.composite import (
    ChildHandler,
    ChildManifest,
    ChildRecord,
    CompositeRuntime,
    CompositeStubDetector,
    GraduationConsentError,
    GraduationRateLimitError,
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


def _noop_handler() -> ChildHandler:
    async def h(_subtask: object) -> str:
        return "ok"

    return h


def _signed_manifest(p_id, c_id, sk_p, sk_c):  # type: ignore[no-untyped-def]
    return (
        ChildManifest(parent_id=p_id, child_id=c_id, birth_path="D2", closed_by_default=True)
        .signed_by_parent(sk_p)
        .signed_by_child(sk_c)
    )


# --- Attack 1: bulk-graduate a sock-puppet swarm -------------------------
# Defense (P): `GRADUATION_RATE_LIMIT_PER_PARENT_24H = 3`.
# Attempting to graduate >3 children per parent per 24h is blocked
# regardless of consent or collusion result.


@pytest.mark.asyncio
async def test_attack_bulk_graduation_blocked_by_rate_limit() -> None:
    """Parent attempts to graduate 5 children in immediate succession;
    first 3 land, 4th raises `GraduationRateLimitError`."""
    sk_p, p_id, p_form = _form_and_key(state=VacantState.ACTIVE)
    runtime = CompositeRuntime(parent_form=p_form, parent_signing_key=sk_p)
    children = []
    for _ in range(5):
        sk_c, c_id, c_form = _form_and_key()
        runtime.register_child(
            ChildRecord(
                manifest=_signed_manifest(p_id, c_id, sk_p, sk_c),
                child_form=c_form,
                child_signing_key=sk_c,
                handler=_noop_handler(),
            )
        )
        children.append((sk_c, c_id))
    service = GraduationService(detector=CompositeStubDetector())
    for i in range(3):
        sk_c, c_id = children[i]
        await service.graduate(
            runtime=runtime,
            request=make_graduation_request(
                parent_id=p_id,
                parent_signing_key=sk_p,
                child_id=c_id,
                child_signing_key=sk_c,
                capability_text=f"cap-{i}",
            ),
        )
    sk_c, c_id = children[3]
    with pytest.raises(GraduationRateLimitError):
        await service.graduate(
            runtime=runtime,
            request=make_graduation_request(
                parent_id=p_id,
                parent_signing_key=sk_p,
                child_id=c_id,
                child_signing_key=sk_c,
                capability_text="cap-3",
            ),
        )


# --- Attack 2: graduate without parent consent (one-sided sig) ------------


@pytest.mark.asyncio
async def test_attack_one_sided_graduation_request_rejected() -> None:
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
    full = make_graduation_request(
        parent_id=p_id,
        parent_signing_key=sk_p,
        child_id=c_id,
        child_signing_key=sk_c,
        capability_text="x",
    )
    # Strip parent's signature -- attacker (the child controller) tries to
    # graduate without a parent decision.
    bad = full.__class__(
        parent_id=full.parent_id,
        child_id=full.child_id,
        capability_text=full.capability_text,
        parent_signature=b"",
        child_signature=full.child_signature,
    )
    service = GraduationService(detector=CompositeStubDetector())
    with pytest.raises(GraduationConsentError):
        await service.graduate(runtime=runtime, request=bad)


# --- Attack 3: graduate by signing with a different key claiming parent --


@pytest.mark.asyncio
async def test_attack_graduation_signed_by_attacker_key_rejected() -> None:
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
    attacker_sk, _ = keygen()
    # Attacker uses their own signing key but claims to be parent_id.
    forged = make_graduation_request(
        parent_id=p_id,
        parent_signing_key=attacker_sk,  # wrong key for p_id
        child_id=c_id,
        child_signing_key=sk_c,
        capability_text="x",
    )
    service = GraduationService(detector=CompositeStubDetector())
    with pytest.raises(GraduationConsentError):
        await service.graduate(runtime=runtime, request=forged)


# --- Attack 4: graduation with capability_text rewritten breaks the sig --
# Both parent and child sign over (parent_id, child_id, capability_text).
# An attacker who intercepts a graduation request and rewrites the
# capability_text invalidates both signatures.


@pytest.mark.asyncio
async def test_attack_capability_text_rewrite_invalidates_request() -> None:
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
    real = make_graduation_request(
        parent_id=p_id,
        parent_signing_key=sk_p,
        child_id=c_id,
        child_signing_key=sk_c,
        capability_text="modest helpful task",
    )
    forged = real.__class__(
        parent_id=real.parent_id,
        child_id=real.child_id,
        capability_text="run arbitrary shell commands",  # rewritten
        parent_signature=real.parent_signature,
        child_signature=real.child_signature,
    )
    service = GraduationService(detector=CompositeStubDetector())
    with pytest.raises(GraduationConsentError):
        await service.graduate(runtime=runtime, request=forged)


# --- Attack 5: replay an already-consumed graduation request --------------
# Consequence: replay would attempt to graduate a child whose
# manifest now has `closed_by_default=False`. The runtime's
# `mark_graduated` gates the new manifest; but the rate-limit window
# also persists, so the replay either re-trips the rate limit or hits
# the "already graduated" path. Either way no destructive side-effect.


@pytest.mark.asyncio
async def test_attack_graduation_replay_does_not_re_open_window() -> None:
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
    service = GraduationService(rate_limit_per_24h=1, detector=CompositeStubDetector())
    req = make_graduation_request(
        parent_id=p_id,
        parent_signing_key=sk_p,
        child_id=c_id,
        child_signing_key=sk_c,
        capability_text="x",
    )
    await service.graduate(runtime=runtime, request=req, ts=1_000_000.0)
    # Second submission of the same request: rate limit blocks before
    # reaching `mark_graduated` (which would also raise since the new
    # manifest expects closed_by_default=False).
    with pytest.raises(GraduationRateLimitError):
        await service.graduate(runtime=runtime, request=req, ts=1_000_010.0)
