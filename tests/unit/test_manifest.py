"""ChildManifest dual-signature tests."""

from __future__ import annotations

import pytest

from vacant.composite import (
    ChildManifest,
    ManifestError,
    OutboundPolicy,
    Reachability,
    ensure_birth_path,
)
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


def _draft(*, parent_id, child_id, **kw):  # type: ignore[no-untyped-def]
    fields = {
        "tool_whitelist_inherited": ["pen", "ruler"],
        "tool_whitelist_added": ["calculator"],
        "tool_whitelist_removed": ["scissors"],
    }
    fields.update(kw)
    return ChildManifest(
        parent_id=parent_id,
        child_id=child_id,
        birth_path="D2",
        closed_by_default=True,
        **fields,
    )


def test_manifest_signed_by_both_verifies() -> None:
    sk_p, p_id, sk_c, c_id = _ids()
    m = _draft(parent_id=p_id, child_id=c_id)
    m = m.signed_by_parent(sk_p).signed_by_child(sk_c)
    assert m.verify() is True
    m.verify_or_raise()


def test_manifest_missing_parent_signature_rejected() -> None:
    _sk_p, p_id, sk_c, c_id = _ids()
    m = _draft(parent_id=p_id, child_id=c_id).signed_by_child(sk_c)
    assert m.verify() is False
    with pytest.raises(ManifestError, match="parent signature"):
        m.verify_or_raise()


def test_manifest_missing_child_signature_rejected() -> None:
    sk_p, p_id, _sk_c, c_id = _ids()
    m = _draft(parent_id=p_id, child_id=c_id).signed_by_parent(sk_p)
    assert m.verify() is False
    with pytest.raises(ManifestError, match="child signature"):
        m.verify_or_raise()


def test_manifest_tampered_after_dual_sign_breaks_verify() -> None:
    """Both signatures cover the canonical-json of the same payload, so
    a post-signing field rewrite invalidates both signatures."""
    sk_p, p_id, sk_c, c_id = _ids()
    m = _draft(parent_id=p_id, child_id=c_id).signed_by_parent(sk_p).signed_by_child(sk_c)
    tampered = m.model_copy(update={"tool_whitelist_added": ["pen", "calculator", "knife"]})
    assert tampered.verify() is False


def test_manifest_signing_payload_canonicalises_tool_lists() -> None:
    """Sorted tool lists -- order-independent payload canonicalisation."""
    _sk_p, p_id, _sk_c, c_id = _ids()
    a = _draft(
        parent_id=p_id,
        child_id=c_id,
        tool_whitelist_inherited=["pen", "ruler"],
    )
    b = _draft(
        parent_id=p_id,
        child_id=c_id,
        tool_whitelist_inherited=["ruler", "pen"],
    )
    assert a.signing_payload() == b.signing_payload()


def test_manifest_swapped_signatures_rejected() -> None:
    """Swap parent's sig into child's slot (and vice versa). Both sigs
    fail under the wrong pubkey."""
    sk_p, p_id, sk_c, c_id = _ids()
    m = _draft(parent_id=p_id, child_id=c_id).signed_by_parent(sk_p).signed_by_child(sk_c)
    swapped = m.model_copy(
        update={
            "signature_parent": m.signature_child,
            "signature_child": m.signature_parent,
        }
    )
    assert swapped.verify() is False


def test_manifest_dual_sign_independent() -> None:
    """A draft can be parent-signed and child-signed in either order
    and produce the same final manifest."""
    sk_p, p_id, sk_c, c_id = _ids()
    a = _draft(parent_id=p_id, child_id=c_id).signed_by_parent(sk_p).signed_by_child(sk_c)
    b = _draft(parent_id=p_id, child_id=c_id).signed_by_child(sk_c).signed_by_parent(sk_p)
    assert a == b


def test_manifest_birth_path_validated() -> None:
    _sk_p, p_id, _sk_c, c_id = _ids()
    with pytest.raises(Exception):  # noqa: B017 (pydantic ValidationError)
        ChildManifest(
            parent_id=p_id,
            child_id=c_id,
            birth_path="D9",  # type: ignore[arg-type]
            closed_by_default=True,
        )
    assert ensure_birth_path("D2") == "D2"
    with pytest.raises(ManifestError):
        ensure_birth_path("X1")


def test_manifest_default_closed_by_default_is_true() -> None:
    _sk_p, p_id, _sk_c, c_id = _ids()
    m = ChildManifest(parent_id=p_id, child_id=c_id, birth_path="D2")
    assert m.closed_by_default is True


# --- THEORY_V5 §5.1 three-axis ontology ---------------------------------


def test_manifest_default_axes_match_self_grown_config() -> None:
    """A D2 subagent-bud with no axis overrides should match the V5
    canonical self-grown configuration: NONE visibility (encoded by
    closed_by_default=True) + PARENT_ONLY reachability + NO_EXTERNAL
    outbound."""
    _sk_p, p_id, _sk_c, c_id = _ids()
    m = ChildManifest(parent_id=p_id, child_id=c_id, birth_path="D2")
    assert m.closed_by_default is True
    assert m.endpoint_reachability == Reachability.PARENT_ONLY
    assert m.outbound_policy == OutboundPolicy.NO_EXTERNAL


def test_manifest_signing_payload_changes_when_axes_change() -> None:
    """Both signatures cover the axis fields, so tampering with them
    after signing must invalidate the manifest."""
    sk_p, p_id, sk_c, c_id = _ids()
    base = _draft(parent_id=p_id, child_id=c_id)
    signed = base.signed_by_parent(sk_p).signed_by_child(sk_c)
    assert signed.verify() is True
    # Recreate with a different reachability axis but keep the old sigs.
    tampered = signed.model_copy(
        update={"endpoint_reachability": Reachability.PUBLIC_A2A}
    )
    assert tampered.verify() is False


def test_manifest_broker_config_round_trips() -> None:
    """The 'broker' configuration of V5 §5.2 must be expressible as
    a dual-signed manifest end-to-end."""
    sk_p, p_id, sk_c, c_id = _ids()
    m = ChildManifest(
        parent_id=p_id,
        child_id=c_id,
        birth_path="D2",
        closed_by_default=False,  # unlisted, not NONE
        endpoint_reachability=Reachability.PARENT_BRIDGED,
        outbound_policy=OutboundPolicy.PARENT_PERMITTED,
    )
    signed = m.signed_by_parent(sk_p).signed_by_child(sk_c)
    signed.verify_or_raise()
    sd = signed.signing_dict()
    assert sd["endpoint_reachability"] == "parent-bridged"
    assert sd["outbound_policy"] == "parent-permitted"


def test_manifest_public_resident_least_privilege_outbound_no_external() -> None:
    """V5 §5.2 explicitly: a graduated vacant can still choose
    NO_EXTERNAL outbound (least privilege) — outbound is independent
    of the visibility/reachability axes."""
    sk_p, p_id, sk_c, c_id = _ids()
    m = ChildManifest(
        parent_id=p_id,
        child_id=c_id,
        birth_path="D2",
        closed_by_default=False,  # graduated
        endpoint_reachability=Reachability.PUBLIC_A2A,
        outbound_policy=OutboundPolicy.NO_EXTERNAL,  # still no outbound
    )
    signed = m.signed_by_parent(sk_p).signed_by_child(sk_c)
    assert signed.verify() is True
