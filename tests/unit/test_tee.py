"""B8 — L3 TEE attestation typed structure + verification stub."""

from __future__ import annotations

import pytest

from vacant.core.crypto import keygen
from vacant.core.types import CapabilityCard, Logbook, SubstrateSpec, VacantId
from vacant.identity import (
    L2Identity,
    L3TEEIdentity,
    LayerPromotionError,
    TEEAttestation,
    TEEVendor,
    TEEVerifierRegistry,
    issue_tee_attestation_mock,
    promote_to_l3_tee,
    verify_tee_attestation,
)


def _vid() -> tuple[VacantId, object]:
    sk, vk = keygen()
    return VacantId.from_verify_key(vk), sk


def _l2_for(vid: VacantId) -> L2Identity:
    """Build an L2 identity with a self-signed empty card. We don't go
    through the full L0→L1→L2 promotion chain because TEE promotion
    only consumes L2 — the chain machinery is tested elsewhere."""
    # Empty logbook is fine; promotion check is `card.vacant_id ==
    # vacant_id`, not log validation.
    return L2Identity(
        vacant_id=vid,
        logbook=Logbook(),
        capability_card=CapabilityCard(
            vacant_id=vid,
            capability_text="x",
            substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
        ),
    )


# --- TEEAttestation shape ----------------------------------------------------


def test_tee_attestation_rejects_short_measurement() -> None:
    vid, _ = _vid()
    with pytest.raises((ValueError, TypeError)):
        TEEAttestation(
            vacant_id=vid,
            vendor=TEEVendor.MOCK,
            measurement=b"too short",
            enclave_pubkey=b"\x00" * 32,
        )


def test_tee_attestation_rejects_short_pubkey() -> None:
    vid, _ = _vid()
    with pytest.raises((ValueError, TypeError)):
        TEEAttestation(
            vacant_id=vid,
            vendor=TEEVendor.MOCK,
            measurement=b"\x00" * 32,
            enclave_pubkey=b"\x00" * 16,
        )


# --- mock vendor round-trip --------------------------------------------------


def test_issue_and_verify_mock_attestation() -> None:
    vid, _vacant_sk = _vid()
    enclave_sk, enclave_vk = keygen()
    att = issue_tee_attestation_mock(
        vacant_id=vid,
        enclave_signing_key=enclave_sk,
        enclave_pubkey=bytes(enclave_vk),
        measurement=b"\xaa" * 32,
    )
    assert verify_tee_attestation(att) is True


def test_mock_attestation_fails_with_wrong_pubkey() -> None:
    vid, _ = _vid()
    enclave_sk, _enclave_vk = keygen()
    _wrong_sk, wrong_vk = keygen()
    att = issue_tee_attestation_mock(
        vacant_id=vid,
        enclave_signing_key=enclave_sk,
        enclave_pubkey=bytes(wrong_vk),  # mismatched
        measurement=b"\xaa" * 32,
    )
    assert verify_tee_attestation(att) is False


def test_mock_attestation_fails_outside_freshness_window() -> None:
    vid, _ = _vid()
    enclave_sk, enclave_vk = keygen()
    att = issue_tee_attestation_mock(
        vacant_id=vid,
        enclave_signing_key=enclave_sk,
        enclave_pubkey=bytes(enclave_vk),
        measurement=b"\xaa" * 32,
        valid_from_ms=1_000_000,
        valid_until_ms=2_000_000,
    )
    assert verify_tee_attestation(att, now_ms=500_000) is False  # too early
    assert verify_tee_attestation(att, now_ms=3_000_000) is False  # too late
    assert verify_tee_attestation(att, now_ms=1_500_000) is True  # in window


# --- promote_to_l3_tee gate --------------------------------------------------


def test_promote_to_l3_tee_happy_path() -> None:
    vid, _ = _vid()
    enclave_sk, enclave_vk = keygen()
    l2 = _l2_for(vid)
    att = issue_tee_attestation_mock(
        vacant_id=vid,
        enclave_signing_key=enclave_sk,
        enclave_pubkey=bytes(enclave_vk),
        measurement=b"\xaa" * 32,
    )
    l3 = promote_to_l3_tee(l2, att)
    assert isinstance(l3, L3TEEIdentity)
    assert l3.vacant_id == vid
    assert l3.tee_attestation is att


def test_promote_to_l3_tee_rejects_cross_vacant_attestation() -> None:
    vid_a, _ = _vid()
    vid_b, _ = _vid()
    enclave_sk, enclave_vk = keygen()
    l2 = _l2_for(vid_a)
    # Attestation for B, but presented for A's L2 — must fail.
    att = issue_tee_attestation_mock(
        vacant_id=vid_b,
        enclave_signing_key=enclave_sk,
        enclave_pubkey=bytes(enclave_vk),
        measurement=b"\xaa" * 32,
    )
    with pytest.raises(LayerPromotionError):
        promote_to_l3_tee(l2, att)


def test_promote_to_l3_tee_rejects_invalid_signature() -> None:
    vid, _ = _vid()
    _enclave_sk, enclave_vk = keygen()
    l2 = _l2_for(vid)
    # Build a TEE attestation with NO signature.
    att = TEEAttestation(
        vacant_id=vid,
        vendor=TEEVendor.MOCK,
        measurement=b"\xaa" * 32,
        enclave_pubkey=bytes(enclave_vk),
    )
    with pytest.raises(LayerPromotionError):
        promote_to_l3_tee(l2, att)


def test_promote_to_l3_tee_unknown_vendor_without_verifier_rejected() -> None:
    """SGX / SEV / etc. without an operator-supplied verifier must NOT
    silently pass — operators have to wire in their own. Default
    `TEEVerifierRegistry.empty()` returns False for everything that
    isn't MOCK."""
    vid, _ = _vid()
    _enclave_sk, enclave_vk = keygen()
    l2 = _l2_for(vid)
    att = TEEAttestation(
        vacant_id=vid,
        vendor=TEEVendor.SGX,
        measurement=b"\xaa" * 32,
        enclave_pubkey=bytes(enclave_vk),
        signature=b"\x00" * 64,
    )
    with pytest.raises(LayerPromotionError):
        promote_to_l3_tee(l2, att, verifiers=TEEVerifierRegistry.empty())


def test_promote_to_l3_tee_pluggable_verifier_accepts() -> None:
    """A custom verifier for SGX vendor can opt-in pass; demonstrates
    the registry hook works."""
    vid, _ = _vid()
    _enclave_sk, enclave_vk = keygen()
    l2 = _l2_for(vid)
    att = TEEAttestation(
        vacant_id=vid,
        vendor=TEEVendor.SGX,
        measurement=b"\xaa" * 32,
        enclave_pubkey=bytes(enclave_vk),
        signature=b"\x00" * 64,
    )
    registry = TEEVerifierRegistry(verifiers={TEEVendor.SGX: lambda _att: True})
    l3 = promote_to_l3_tee(l2, att, verifiers=registry)
    assert l3.tee_attestation.vendor is TEEVendor.SGX
