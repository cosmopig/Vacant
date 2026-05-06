"""ChildManifest dual-signature tests."""

from __future__ import annotations

import pytest

from vacant.composite import ChildManifest, ManifestError, ensure_birth_path
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
