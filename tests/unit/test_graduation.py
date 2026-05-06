"""Graduation flow tests (parent consent + rate limit + collusion gate)."""

from __future__ import annotations

import pytest

from vacant.composite import (
    GRADUATED_KIND,
    ChildHandler,
    ChildManifest,
    ChildRecord,
    CollusionSignals,
    CompositeRuntime,
    CompositeStubDetector,
    GraduationCollusionError,
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

# --- fixtures --------------------------------------------------------------


def _form_and_key(*, state: VacantState = VacantState.LOCAL):  # type: ignore[no-untyped-def]
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


def _signed_manifest(parent_id, child_id, sk_p, sk_c):  # type: ignore[no-untyped-def]
    return (
        ChildManifest(
            parent_id=parent_id,
            child_id=child_id,
            birth_path="D2",
            closed_by_default=True,
        )
        .signed_by_parent(sk_p)
        .signed_by_child(sk_c)
    )


async def _noop(_subtask: object) -> str:
    return "ok"


def _build_runtime_with_child():  # type: ignore[no-untyped-def]
    sk_p, p_id, p_form = _form_and_key(state=VacantState.ACTIVE)
    sk_c, c_id, c_form = _form_and_key()
    runtime = CompositeRuntime(parent_form=p_form, parent_signing_key=sk_p)
    manifest = _signed_manifest(p_id, c_id, sk_p, sk_c)
    record: ChildRecord = ChildRecord(
        manifest=manifest,
        child_form=c_form,
        child_signing_key=sk_c,
        handler=_noop_handler(),
    )
    runtime.register_child(record)
    return runtime, sk_p, p_id, p_form, sk_c, c_id, c_form


def _noop_handler() -> ChildHandler:
    async def handler(_subtask: object) -> str:
        return "ok"

    return handler


# --- happy path ------------------------------------------------------------


@pytest.mark.asyncio
async def test_graduate_all_three_conditions_met() -> None:
    runtime, sk_p, p_id, p_form, sk_c, c_id, c_form = _build_runtime_with_child()
    service = GraduationService(detector=CompositeStubDetector())
    req = make_graduation_request(
        parent_id=p_id,
        parent_signing_key=sk_p,
        child_id=c_id,
        child_signing_key=sk_c,
        capability_text="independent reasoning",
    )
    outcome = await service.graduate(runtime=runtime, request=req)
    # Manifest flipped, both sigs verify.
    assert outcome.new_manifest.closed_by_default is False
    assert outcome.new_manifest.verify() is True
    # Capability card signed by child's key.
    assert outcome.child_card.verify() is True
    assert outcome.child_card.capability_text == "independent reasoning"
    # IDENTITY PRESERVED: same keypair, same VacantId.
    assert outcome.child_card.vacant_id == c_id
    # Both logbooks have a GRADUATED entry.
    assert any(e.kind == GRADUATED_KIND for e in p_form.logbook.entries)
    assert any(e.kind == GRADUATED_KIND for e in c_form.logbook.entries)
    # Runtime now records the graduated manifest.
    assert runtime.manifest_for(c_id).closed_by_default is False


@pytest.mark.asyncio
async def test_graduation_preserves_logbook_continuity() -> None:
    """Post-graduation logbook is an EXTENSION of pre's, not a fork."""
    runtime, sk_p, p_id, _p_form, sk_c, c_id, c_form = _build_runtime_with_child()
    pre_entries = list(c_form.logbook.entries)
    pre_chain_ok = c_form.logbook.verify_chain(c_id.verify_key())
    assert pre_chain_ok

    service = GraduationService(detector=CompositeStubDetector())
    req = make_graduation_request(
        parent_id=p_id,
        parent_signing_key=sk_p,
        child_id=c_id,
        child_signing_key=sk_c,
        capability_text="x",
    )
    await service.graduate(runtime=runtime, request=req)

    # Post-graduation: pre-entries are still the prefix, chain still verifies.
    assert c_form.logbook.entries[: len(pre_entries)] == pre_entries
    assert len(c_form.logbook.entries) > len(pre_entries)
    assert c_form.logbook.verify_chain(c_id.verify_key()) is True


# --- failure modes ---------------------------------------------------------


@pytest.mark.asyncio
async def test_graduation_rejected_when_parent_consent_missing() -> None:
    """Parent signature missing -> request.verify() False -> consent error."""
    runtime, sk_p, p_id, p_form, sk_c, c_id, c_form = _build_runtime_with_child()
    req = make_graduation_request(
        parent_id=p_id,
        parent_signing_key=sk_p,
        child_id=c_id,
        child_signing_key=sk_c,
        capability_text="x",
    )
    # Strip parent's signature.
    bad = req.__class__(
        parent_id=req.parent_id,
        child_id=req.child_id,
        capability_text=req.capability_text,
        parent_signature=b"",
        child_signature=req.child_signature,
    )
    service = GraduationService()
    with pytest.raises(GraduationConsentError):
        await service.graduate(runtime=runtime, request=bad)
    # Runtime untouched.
    assert runtime.manifest_for(c_id).closed_by_default is True
    _ = (p_form, c_form)


@pytest.mark.asyncio
async def test_graduation_rejected_when_consent_signed_by_wrong_party() -> None:
    runtime, sk_p, p_id, p_form, sk_c, c_id, c_form = _build_runtime_with_child()
    other_sk, _other_vk = keygen()
    # Build request signed by `other_sk` instead of parent.
    req = make_graduation_request(
        parent_id=p_id,
        parent_signing_key=other_sk,  # wrong key
        child_id=c_id,
        child_signing_key=sk_c,
        capability_text="x",
    )
    service = GraduationService()
    with pytest.raises(GraduationConsentError):
        await service.graduate(runtime=runtime, request=req)
    _ = (sk_p, p_form, c_form)


@pytest.mark.asyncio
async def test_graduation_rate_limit_exceeded_blocks_fourth_graduation() -> None:
    """The default rate limit is 3 graduations per parent per 24h.
    A 4th attempt is blocked even if all other gates pass."""
    sk_p, p_id, p_form = _form_and_key(state=VacantState.ACTIVE)
    runtime = CompositeRuntime(parent_form=p_form, parent_signing_key=sk_p)
    children = []
    for _ in range(4):
        sk_c, c_id, c_form = _form_and_key()
        manifest = _signed_manifest(p_id, c_id, sk_p, sk_c)
        runtime.register_child(
            ChildRecord(
                manifest=manifest,
                child_form=c_form,
                child_signing_key=sk_c,
                handler=_noop_handler(),
            )
        )
        children.append((sk_c, c_id))
    service = GraduationService(rate_limit_per_24h=3, detector=CompositeStubDetector())
    for i in range(3):
        sk_c, c_id = children[i]
        req = make_graduation_request(
            parent_id=p_id,
            parent_signing_key=sk_p,
            child_id=c_id,
            child_signing_key=sk_c,
            capability_text=f"cap-{i}",
        )
        await service.graduate(runtime=runtime, request=req)
    # 4th: blocked.
    sk_c, c_id = children[3]
    req = make_graduation_request(
        parent_id=p_id,
        parent_signing_key=sk_p,
        child_id=c_id,
        child_signing_key=sk_c,
        capability_text="cap-3",
    )
    with pytest.raises(GraduationRateLimitError):
        await service.graduate(runtime=runtime, request=req)


@pytest.mark.asyncio
async def test_graduation_rate_limit_window_evicts_after_24h() -> None:
    sk_p, p_id, p_form = _form_and_key(state=VacantState.ACTIVE)
    runtime = CompositeRuntime(parent_form=p_form, parent_signing_key=sk_p)
    children = []
    for _ in range(2):
        sk_c, c_id, c_form = _form_and_key()
        manifest = _signed_manifest(p_id, c_id, sk_p, sk_c)
        runtime.register_child(
            ChildRecord(
                manifest=manifest,
                child_form=c_form,
                child_signing_key=sk_c,
                handler=_noop_handler(),
            )
        )
        children.append((sk_c, c_id))
    service = GraduationService(rate_limit_per_24h=1, detector=CompositeStubDetector())
    base = 1_000_000.0
    sk_c, c_id = children[0]
    req = make_graduation_request(
        parent_id=p_id,
        parent_signing_key=sk_p,
        child_id=c_id,
        child_signing_key=sk_c,
        capability_text="cap-0",
    )
    await service.graduate(runtime=runtime, request=req, ts=base)
    # 2nd graduation 25h later -- old slot evicted, accepted.
    sk_c, c_id = children[1]
    req = make_graduation_request(
        parent_id=p_id,
        parent_signing_key=sk_p,
        child_id=c_id,
        child_signing_key=sk_c,
        capability_text="cap-1",
    )
    await service.graduate(runtime=runtime, request=req, ts=base + 25 * 3600)


@pytest.mark.asyncio
async def test_graduation_blocked_by_high_collusion_signal() -> None:
    runtime, sk_p, p_id, p_form, sk_c, c_id, c_form = _build_runtime_with_child()
    high_signal_detector = CompositeStubDetector(same_substrate=0.95)
    service = GraduationService(detector=high_signal_detector)
    req = make_graduation_request(
        parent_id=p_id,
        parent_signing_key=sk_p,
        child_id=c_id,
        child_signing_key=sk_c,
        capability_text="x",
    )
    with pytest.raises(GraduationCollusionError):
        await service.graduate(runtime=runtime, request=req)
    # Manifest unchanged.
    assert runtime.manifest_for(c_id).closed_by_default is True
    _ = (p_form, c_form)


@pytest.mark.asyncio
async def test_graduation_collusion_signals_max_composition() -> None:
    """The detector returns three signals; the gate trips on the highest
    one (conservative composition)."""
    runtime, sk_p, p_id, _p_form, sk_c, c_id, _c_form = _build_runtime_with_child()
    # All three below threshold individually, none above.
    just_below = CompositeStubDetector(
        same_controller=0.5,
        same_substrate=0.55,
        same_stylo=0.5,
    )
    service = GraduationService(detector=just_below, collusion_threshold=0.6)
    req = make_graduation_request(
        parent_id=p_id,
        parent_signing_key=sk_p,
        child_id=c_id,
        child_signing_key=sk_c,
        capability_text="ok",
    )
    outcome = await service.graduate(runtime=runtime, request=req)
    assert outcome.collusion_signals.same_substrate == pytest.approx(0.55)


@pytest.mark.asyncio
async def test_graduation_does_not_change_keypair() -> None:
    """Identity preservation: the child's VacantId after graduation is
    bytes-identical to before."""
    runtime, sk_p, p_id, _p_form, sk_c, c_id, c_form = _build_runtime_with_child()
    pre_pubkey = c_form.identity.pubkey_bytes
    service = GraduationService(detector=CompositeStubDetector())
    req = make_graduation_request(
        parent_id=p_id,
        parent_signing_key=sk_p,
        child_id=c_id,
        child_signing_key=sk_c,
        capability_text="x",
    )
    outcome = await service.graduate(runtime=runtime, request=req)
    assert outcome.new_manifest.child_id.pubkey_bytes == pre_pubkey
    assert outcome.child_card.vacant_id.pubkey_bytes == pre_pubkey
    # And the child form's identity is unchanged.
    assert c_form.identity == c_id


# --- service-level invariants ---------------------------------------------


def test_graduation_service_rejects_bad_construction() -> None:
    with pytest.raises(ValueError):
        GraduationService(rate_limit_per_24h=0)
    with pytest.raises(ValueError):
        GraduationService(collusion_threshold=1.5)
    with pytest.raises(ValueError):
        GraduationService(collusion_threshold=-0.1)


def test_collusion_signals_validates_range() -> None:
    with pytest.raises(ValueError):
        CollusionSignals(same_controller=1.1, same_substrate=0.0, same_stylo=0.0)
    with pytest.raises(ValueError):
        CollusionSignals(same_controller=-0.1, same_substrate=0.0, same_stylo=0.0)
