"""Padv P5 -- ChildManifest dual-signature tamper (dispatch §"Manifest tampering").

Spec anchors:
- `architecture/components/P5_composite.md` §3.1 (manifest)
- `architecture/decisions/D012_p5_composite_reconciliation.md` §C
- `dispatch/Padv_review.md` §"P5 Composite attacks to consider"

Defense (P, write-time): both `signature_parent` and `signature_child`
cover the same canonical-json payload. Any post-sign field rewrite
invalidates both signatures; a one-sided signature is rejected by
`verify_or_raise`.
"""

from __future__ import annotations

import pytest

from vacant.composite import ChildManifest, ManifestError
from vacant.core.crypto import keygen
from vacant.core.types import VacantId


def _ids():  # type: ignore[no-untyped-def]
    sk_p, vk_p = keygen()
    sk_c, vk_c = keygen()
    return (
        sk_p,
        VacantId.from_verify_key(vk_p),
        sk_c,
        VacantId.from_verify_key(vk_c),
    )


def _draft(parent_id: VacantId, child_id: VacantId) -> ChildManifest:
    return ChildManifest(
        parent_id=parent_id,
        child_id=child_id,
        birth_path="D2",
        closed_by_default=True,
        tool_whitelist_inherited=["text"],
    )


# --- Attack 1: parent signs first, child rewrites payload before signing --
# Defense: child's signing_payload() recomputes from current fields,
# so child signs the rewritten payload while parent's signature is over
# the original. Parent's sig fails `verify` against the rewritten state.


def test_attack_child_rewrites_payload_after_parent_signed() -> None:
    """An attacker who controls the child but not the parent tries to
    expand the tool whitelist after the parent signs. The tampered
    manifest cannot get the child's signature *and* keep the parent's
    valid: the parent's signature breaks."""
    sk_p, p_id, sk_c, c_id = _ids()
    after_parent = _draft(p_id, c_id).signed_by_parent(sk_p)
    rewritten = after_parent.model_copy(update={"tool_whitelist_added": ["root", "shell"]})
    fully_signed = rewritten.signed_by_child(sk_c)
    # Parent's signature is over the original payload; verify fails.
    assert fully_signed.verify() is False
    with pytest.raises(ManifestError, match="parent signature"):
        fully_signed.verify_or_raise()


# --- Attack 2: child signs first, parent rewrites payload before signing --
# Symmetric to Attack 1.


def test_attack_parent_rewrites_payload_after_child_signed() -> None:
    sk_p, p_id, sk_c, c_id = _ids()
    after_child = _draft(p_id, c_id).signed_by_child(sk_c)
    rewritten = after_child.model_copy(
        update={"closed_by_default": False}  # try to graduate without dual consent
    )
    fully_signed = rewritten.signed_by_parent(sk_p)
    assert fully_signed.verify() is False
    with pytest.raises(ManifestError, match="child signature"):
        fully_signed.verify_or_raise()


# --- Attack 3: closed_by_default flag is in signed scope ------------------
# An attacker who acquires a dual-signed manifest cannot flip
# closed_by_default to False (which would graduate the child without
# the proper flow): the flag is in the signing payload.


def test_attack_flipping_closed_by_default_breaks_signatures() -> None:
    sk_p, p_id, sk_c, c_id = _ids()
    m = _draft(p_id, c_id).signed_by_parent(sk_p).signed_by_child(sk_c)
    assert m.closed_by_default is True
    flipped = m.model_copy(update={"closed_by_default": False})
    assert flipped.verify() is False


# --- Attack 4: swap signatures from a sibling manifest --------------------
# Attack: take signature_parent and signature_child from a *different*
# manifest the parent signed (e.g. for sibling X) and graft them onto
# a forged manifest for sibling Y. The signatures are over X's payload;
# verification against Y's payload fails for both keys.


def test_attack_sibling_signature_graft_rejected() -> None:
    sk_p, p_id, sk_c_a, c_a_id = _ids()
    _sk_p2, _p2_id, sk_c_b, c_b_id = _ids()  # different child id
    # Parent signs sibling A's manifest.
    m_a = _draft(p_id, c_a_id).signed_by_parent(sk_p).signed_by_child(sk_c_a)
    # Forge a manifest for sibling B but graft A's signatures on.
    forged = ChildManifest(
        parent_id=p_id,
        child_id=c_b_id,
        birth_path="D2",
        closed_by_default=True,
        tool_whitelist_inherited=["text"],
        signature_parent=m_a.signature_parent,
        signature_child=m_a.signature_child,
    )
    assert forged.verify() is False
    _ = sk_c_b


# --- Attack 5: change tool_whitelist sets after dual sign breaks sig ------


def test_attack_tool_whitelist_tamper_breaks_signature() -> None:
    sk_p, p_id, sk_c, c_id = _ids()
    m = (
        ChildManifest(
            parent_id=p_id,
            child_id=c_id,
            birth_path="D2",
            closed_by_default=True,
            tool_whitelist_inherited=["text"],
            tool_whitelist_added=["calculator"],
            tool_whitelist_removed=["scissors"],
        )
        .signed_by_parent(sk_p)
        .signed_by_child(sk_c)
    )
    for field in ("tool_whitelist_inherited", "tool_whitelist_added", "tool_whitelist_removed"):
        bad = m.model_copy(update={field: ["root"]})
        assert bad.verify() is False, f"tamper of {field} not detected"


# --- Attack 6: change birth_path or parent_id breaks signature ------------


def test_attack_birth_path_tamper_breaks_signature() -> None:
    sk_p, p_id, sk_c, c_id = _ids()
    m = _draft(p_id, c_id).signed_by_parent(sk_p).signed_by_child(sk_c)
    bad = m.model_copy(update={"birth_path": "D4"})
    assert bad.verify() is False


def test_attack_parent_id_tamper_breaks_signature() -> None:
    sk_p, p_id, sk_c, c_id = _ids()
    _sk_other, vk_other = keygen()
    other_p = VacantId.from_verify_key(vk_other)
    m = _draft(p_id, c_id).signed_by_parent(sk_p).signed_by_child(sk_c)
    bad = m.model_copy(update={"parent_id": other_p})
    # Now `parent_id`'s pubkey doesn't match the signing key that signed
    # it, so verify fails (the original signature was made with sk_p
    # which doesn't correspond to `other_p`'s verify_key).
    assert bad.verify() is False


# --- Attack 7: forge an entire manifest with attacker keys ----------------
# The attacker generates a brand-new (parent, child) pair with their
# own keys, signs both ends, and tries to inject this as a "child" of
# the real composite parent. Defense: CompositeRuntime.register_child
# rejects manifests whose parent_id != composite's identity.


def test_attack_forged_manifest_with_attacker_parent_rejected_by_runtime() -> None:
    from vacant.composite import (
        ChildRecord,
        CompositeRuntime,
    )
    from vacant.core.types import (
        BehaviorBundle,
        Logbook,
        ResidentForm,
        SubstrateSpec,
        VacantState,
    )

    # Real composite parent.
    real_sk_p, real_vk_p = keygen()
    real_p_id = VacantId.from_verify_key(real_vk_p)
    real_p_form = ResidentForm(
        identity=real_p_id,
        logbook=Logbook(),
        behavior_bundle=BehaviorBundle(system_prompt="x"),
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
        runtime_state=VacantState.ACTIVE,
    )
    runtime = CompositeRuntime(parent_form=real_p_form, parent_signing_key=real_sk_p)

    # Attacker forges (parent, child) with their own keys.
    attacker_sk_p, attacker_vk_p = keygen()
    attacker_p_id = VacantId.from_verify_key(attacker_vk_p)
    sk_c, vk_c = keygen()
    c_id = VacantId.from_verify_key(vk_c)
    forged = (
        ChildManifest(
            parent_id=attacker_p_id,  # NOT real_p_id
            child_id=c_id,
            birth_path="D2",
            closed_by_default=True,
        )
        .signed_by_parent(attacker_sk_p)
        .signed_by_child(sk_c)
    )
    # Forged manifest verifies cryptographically (attacker has both keys).
    assert forged.verify() is True
    # But the runtime rejects it: parent_id doesn't match this composite.
    c_form = ResidentForm(
        identity=c_id,
        logbook=Logbook(),
        behavior_bundle=BehaviorBundle(system_prompt="x"),
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
        runtime_state=VacantState.LOCAL,
    )

    async def _h(_: object) -> str:
        return "ok"

    with pytest.raises(ManifestError, match="parent_id"):
        runtime.register_child(
            ChildRecord(
                manifest=forged,
                child_form=c_form,
                child_signing_key=sk_c,
                handler=_h,
            )
        )
