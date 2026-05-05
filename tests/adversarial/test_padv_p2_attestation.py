"""Padv P2 — adversarial tests for `vacant.identity.attestation`.

Spec anchors:
- `architecture/components/P2_identity.md` §3.5 (peer attestation,
  WoT)
- `architecture/CONSTANTS.md` §Identity (freshness window, min vouchers)
- `dispatch/Padv_review.md` §"Attestation freshness exploit",
  §"Revocation race"
"""

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

# --- Attack 1: attester impersonation ----------------------------------------
# Defense (P): the signing payload includes `attester.pubkey_bytes`, and
# `verify_attestation` validates the signature under
# `att.attester.verify_key()`. An attacker constructing an attestation
# whose `attester` field names a victim, but signing with the attacker's
# own key, fails verification.


def test_attack_attester_impersonation_fails_verify() -> None:
    _victim_sk, victim_vk = keygen()
    attacker_sk, _ = keygen()
    _, attestee_vk = keygen()

    victim_id = VacantId.from_verify_key(victim_vk)
    attestee_id = VacantId.from_verify_key(attestee_vk)

    # Manually construct an unsigned attestation claiming attester=victim,
    # then sign with attacker_sk.
    now = datetime.now(UTC)
    unsigned = PeerAttestation(
        attester=victim_id,
        attestee=attestee_id,
        claim="trust-me",
        issued_at=now,
        expires_at=now + timedelta(days=30),
    )
    from vacant.core.crypto import sign

    forged = unsigned.model_copy(
        update={"signature": sign(attacker_sk, unsigned.signing_payload())}
    )
    assert verify_attestation(forged) is False


# --- Attack 2: expires_at extension -----------------------------------------
# Defense (P): `expires_at` is part of the signing payload. Modifying it
# after issuance (to slide the window forward) breaks the signature.


def test_attack_extending_expires_at_breaks_signature() -> None:
    sk, vk = keygen()
    _, peer_vk = keygen()
    long_ago = datetime.now(UTC) - timedelta(days=400)
    expired = issue_attestation(
        attester=VacantId.from_verify_key(vk),
        attestee=VacantId.from_verify_key(peer_vk),
        claim="x",
        attester_signing_key=sk,
        issued_at=long_ago,
        expires_at=long_ago + timedelta(days=1),
    )
    # Attacker tries to extend the window without re-signing.
    extended = expired.model_copy(update={"expires_at": datetime.now(UTC) + timedelta(days=30)})
    assert verify_attestation(extended) is False


# --- Attack 3: revocation impersonation -------------------------------------
# Defense (P): `revoke_attestation` defensively verifies that the supplied
# signing key actually matches `att.attester`'s pubkey. An attacker who
# tries to revoke someone else's attestation with their own key gets a
# `AttestationError`.


def test_attack_third_party_revocation_rejected() -> None:
    issuer_sk, issuer_vk = keygen()
    attacker_sk, _ = keygen()
    _, attestee_vk = keygen()

    att = issue_attestation(
        attester=VacantId.from_verify_key(issuer_vk),
        attestee=VacantId.from_verify_key(attestee_vk),
        claim="x",
        attester_signing_key=issuer_sk,
    )
    with pytest.raises(AttestationError):
        revoke_attestation(att, attacker_sk)


# --- Attack 4: forged revocation token ---------------------------------------
# Defense (P): `is_revoked` re-verifies each revocation token's signature
# before accepting it as valid. A token with a tampered `attester` field
# (claiming someone else issued the revocation) doesn't verify.


def test_attack_forged_revocation_token_ignored() -> None:
    issuer_sk, issuer_vk = keygen()
    _, attestee_vk = keygen()
    att = issue_attestation(
        attester=VacantId.from_verify_key(issuer_vk),
        attestee=VacantId.from_verify_key(attestee_vk),
        claim="x",
        attester_signing_key=issuer_sk,
    )
    legit = revoke_attestation(att, issuer_sk)

    # Attacker swaps the attester in the revocation record.
    other_id = VacantId.from_verify_key(keygen()[1])
    forged = legit.model_copy(update={"attester": other_id})
    assert is_revoked(att, [forged]) is False


# --- Attack 5: revocation pointed at a different attestation ----------------
# Defense (P): `is_revoked` matches by `attestation_fingerprint`. A
# revocation for attestation X does not invalidate attestation Y.


def test_attack_revocation_for_other_attestation_does_not_apply() -> None:
    sk, vk = keygen()
    _, attestee_vk = keygen()
    att_x = issue_attestation(
        attester=VacantId.from_verify_key(vk),
        attestee=VacantId.from_verify_key(attestee_vk),
        claim="X",
        attester_signing_key=sk,
    )
    att_y = issue_attestation(
        attester=VacantId.from_verify_key(vk),
        attestee=VacantId.from_verify_key(attestee_vk),
        claim="Y",
        attester_signing_key=sk,
    )
    rev_for_x = revoke_attestation(att_x, sk)
    assert is_revoked(att_y, [rev_for_x]) is False
    assert is_revoked(att_x, [rev_for_x]) is True


# --- Attack 6: tampering the attestee field after issue ----------------------
# Defense (P): the signing payload includes `attestee.pubkey_bytes`.
# Re-pointing an attestation at a different attestee breaks the signature.


def test_attack_tampering_attestee_after_issue_breaks_signature() -> None:
    sk, vk = keygen()
    _, victim_vk = keygen()
    _, hijacker_vk = keygen()
    legit = issue_attestation(
        attester=VacantId.from_verify_key(vk),
        attestee=VacantId.from_verify_key(victim_vk),
        claim="x",
        attester_signing_key=sk,
    )
    hijacked = legit.model_copy(update={"attestee": VacantId.from_verify_key(hijacker_vk)})
    assert verify_attestation(hijacked) is False


# --- Attack 7: not-yet-valid attestation cannot be backdated -----------------
# Defense (P): `verify_attestation` requires `now >= issued_at`. An
# attacker pre-issuing an attestation for the future cannot use it now.


def test_attack_future_dated_attestation_rejected() -> None:
    sk, vk = keygen()
    _, peer_vk = keygen()
    far_future = datetime.now(UTC) + timedelta(days=365)
    att = issue_attestation(
        attester=VacantId.from_verify_key(vk),
        attestee=VacantId.from_verify_key(peer_vk),
        claim="x",
        attester_signing_key=sk,
        issued_at=far_future,
        expires_at=far_future + timedelta(days=30),
    )
    assert verify_attestation(att) is False
