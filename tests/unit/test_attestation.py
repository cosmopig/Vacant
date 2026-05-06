"""PeerAttestation issue/verify/revoke unit tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from vacant.core.crypto import keygen
from vacant.core.types import VacantId
from vacant.identity.attestation import (
    PeerAttestation,
    is_revoked,
    issue_attestation,
    revoke_attestation,
    verify_attestation,
)
from vacant.identity.errors import AttestationError


def _two_vacants() -> tuple[tuple[VacantId, object], tuple[VacantId, object]]:
    sk_a, vk_a = keygen()
    sk_b, vk_b = keygen()
    return (VacantId.from_verify_key(vk_a), sk_a), (VacantId.from_verify_key(vk_b), sk_b)


def test_issue_and_verify_round_trip() -> None:
    (a_id, a_sk), (b_id, _b_sk) = _two_vacants()
    att = issue_attestation(
        attester=a_id, attestee=b_id, claim="not-sock-puppet", attester_signing_key=a_sk
    )
    assert verify_attestation(att) is True


def test_verify_rejects_tampered_claim() -> None:
    (a_id, a_sk), (b_id, _) = _two_vacants()
    att = issue_attestation(
        attester=a_id, attestee=b_id, claim="trustworthy", attester_signing_key=a_sk
    )
    tampered = att.model_copy(update={"claim": "evil"})
    assert verify_attestation(tampered) is False


def test_verify_rejects_expired_attestation() -> None:
    (a_id, a_sk), (b_id, _) = _two_vacants()
    long_ago = datetime.now(UTC) - timedelta(days=400)
    att = issue_attestation(
        attester=a_id,
        attestee=b_id,
        claim="x",
        attester_signing_key=a_sk,
        issued_at=long_ago,
        expires_at=long_ago + timedelta(days=1),
    )
    assert verify_attestation(att) is False


def test_verify_rejects_not_yet_valid_attestation() -> None:
    (a_id, a_sk), (b_id, _) = _two_vacants()
    future = datetime.now(UTC) + timedelta(days=10)
    att = issue_attestation(
        attester=a_id,
        attestee=b_id,
        claim="x",
        attester_signing_key=a_sk,
        issued_at=future,
        expires_at=future + timedelta(days=1),
    )
    # `now` defaults to the wall clock, which precedes `future`.
    assert verify_attestation(att) is False


def test_issue_rejects_self_attestation() -> None:
    (a_id, a_sk), _ = _two_vacants()
    with pytest.raises(AttestationError):
        issue_attestation(attester=a_id, attestee=a_id, claim="x", attester_signing_key=a_sk)


def test_issue_rejects_empty_claim() -> None:
    (a_id, a_sk), (b_id, _) = _two_vacants()
    with pytest.raises(AttestationError):
        issue_attestation(attester=a_id, attestee=b_id, claim="   ", attester_signing_key=a_sk)


def test_issue_rejects_inverted_window() -> None:
    (a_id, a_sk), (b_id, _) = _two_vacants()
    now = datetime.now(UTC)
    with pytest.raises(AttestationError):
        issue_attestation(
            attester=a_id,
            attestee=b_id,
            claim="x",
            attester_signing_key=a_sk,
            issued_at=now,
            expires_at=now - timedelta(seconds=1),
        )


def test_unsigned_attestation_does_not_verify() -> None:
    (a_id, _), (b_id, _) = _two_vacants()
    now = datetime.now(UTC)
    raw = PeerAttestation(
        attester=a_id,
        attestee=b_id,
        claim="x",
        issued_at=now,
        expires_at=now + timedelta(days=1),
    )
    assert verify_attestation(raw) is False


def test_revoke_round_trip() -> None:
    (a_id, a_sk), (b_id, _) = _two_vacants()
    att = issue_attestation(attester=a_id, attestee=b_id, claim="x", attester_signing_key=a_sk)
    record = revoke_attestation(att, a_sk)
    assert record.verify() is True
    assert is_revoked(att, [record]) is True


def test_revoke_with_wrong_key_raises() -> None:
    (a_id, _), (b_id, _) = _two_vacants()
    _other_sk, _other_vk = keygen()
    foreign_sk = keygen()[0]
    att = PeerAttestation(
        attester=a_id,
        attestee=b_id,
        claim="x",
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    with pytest.raises(AttestationError):
        revoke_attestation(att, foreign_sk)


def test_is_revoked_ignores_unrelated_revocations() -> None:
    (a_id, a_sk), (b_id, _) = _two_vacants()
    att1 = issue_attestation(attester=a_id, attestee=b_id, claim="x", attester_signing_key=a_sk)
    att2 = issue_attestation(attester=a_id, attestee=b_id, claim="y", attester_signing_key=a_sk)
    rec_for_att2 = revoke_attestation(att2, a_sk)
    assert is_revoked(att1, [rec_for_att2]) is False


def test_is_revoked_rejects_invalid_revocation_record() -> None:
    (a_id, a_sk), (b_id, _) = _two_vacants()
    att = issue_attestation(attester=a_id, attestee=b_id, claim="x", attester_signing_key=a_sk)
    rec = revoke_attestation(att, a_sk)
    bad = rec.model_copy(update={"signature": b"\x00" * 64})
    assert is_revoked(att, [bad]) is False
