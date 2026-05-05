"""Peer attestations: signed vouches one vacant gives another.

`PeerAttestation` is the L3 building block (`identity/layers.py`). Each
attestation is a frozen Pydantic model carrying an Ed25519 signature over
a canonical byte payload of `(attester, attestee, claim, issued_at,
expires_at)`. Verification checks signature *and* freshness; the
freshness window defaults to `PEER_ATTESTATION_FRESHNESS_WINDOW_DAYS`
(D004 §D, CONSTANTS.md §Identity).

Revocation: `revoke_attestation(att, attester_signing_key)` returns a
`RevocationRecord` carrying a signed revocation token. Holders can
present this token to a verifier; `is_revoked(att, revocations)` returns
True iff the attester signed an explicit revocation for that
attestation. We do not silently downgrade — the check is explicit so the
caller knows whether they trusted a revoked claim.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Final

from pydantic import BaseModel, ConfigDict

from vacant.core.constants import PEER_ATTESTATION_FRESHNESS_WINDOW_DAYS
from vacant.core.crypto import SigningKey, hash_blake2b, sign, verify
from vacant.core.types import VacantId
from vacant.identity.errors import AttestationError

__all__ = [
    "ATTESTATION_REVOCATION_INTENT",
    "PeerAttestation",
    "RevocationRecord",
    "is_revoked",
    "issue_attestation",
    "revoke_attestation",
    "verify_attestation",
]


ATTESTATION_REVOCATION_INTENT: Final[str] = "vacant:attestation:revocation"


def _attestation_payload(
    *,
    attester: VacantId,
    attestee: VacantId,
    claim: str,
    issued_at: datetime,
    expires_at: datetime,
) -> bytes:
    """Canonical byte form of the attestation. Used both for signing and as
    the revocation target hash."""
    parts = [
        attester.pubkey_bytes,
        attestee.pubkey_bytes,
        claim.encode("utf-8"),
        _utc_iso(issued_at).encode("utf-8"),
        _utc_iso(expires_at).encode("utf-8"),
    ]
    return b"\x1f".join(parts)


def _utc_iso(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC).isoformat()


class PeerAttestation(BaseModel):
    """One vacant's signed claim about another."""

    model_config = ConfigDict(frozen=True)

    attester: VacantId
    attestee: VacantId
    claim: str
    issued_at: datetime
    expires_at: datetime
    signature: bytes = b""

    def signing_payload(self) -> bytes:
        return _attestation_payload(
            attester=self.attester,
            attestee=self.attestee,
            claim=self.claim,
            issued_at=self.issued_at,
            expires_at=self.expires_at,
        )

    def fingerprint(self) -> bytes:
        """BLAKE2b digest of the signing payload — names the attestation
        in revocation records.
        """
        return hash_blake2b(self.signing_payload())


def issue_attestation(
    *,
    attester: VacantId,
    attestee: VacantId,
    claim: str,
    attester_signing_key: SigningKey,
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> PeerAttestation:
    """Construct and sign a fresh `PeerAttestation`.

    Defaults:
    - `issued_at` = now UTC
    - `expires_at` = `issued_at + PEER_ATTESTATION_FRESHNESS_WINDOW_DAYS`
    """
    if not claim.strip():
        raise AttestationError("issue_attestation: claim must be non-empty")
    if attester == attestee:
        raise AttestationError("issue_attestation: attester == attestee (self-attest)")
    issued = (issued_at or datetime.now(UTC)).astimezone(UTC)
    expires = (
        expires_at or issued + timedelta(days=PEER_ATTESTATION_FRESHNESS_WINDOW_DAYS)
    ).astimezone(UTC)
    if expires <= issued:
        raise AttestationError("issue_attestation: expires_at must be after issued_at")
    unsigned = PeerAttestation(
        attester=attester,
        attestee=attestee,
        claim=claim,
        issued_at=issued,
        expires_at=expires,
    )
    sig = sign(attester_signing_key, unsigned.signing_payload())
    return unsigned.model_copy(update={"signature": sig})


def verify_attestation(att: PeerAttestation, *, now: datetime | None = None) -> bool:
    """True iff:
    - `att.signature` verifies against `att.attester`'s pubkey
    - `now ∈ [issued_at, expires_at]`
    """
    if not att.signature:
        return False
    current = (now or datetime.now(UTC)).astimezone(UTC)
    issued = att.issued_at.astimezone(UTC)
    expires = att.expires_at.astimezone(UTC)
    if current < issued or current > expires:
        return False
    return verify(att.attester.verify_key(), att.signing_payload(), att.signature)


# --- Revocation --------------------------------------------------------------


class RevocationRecord(BaseModel):
    """Signed revocation token for one attestation."""

    model_config = ConfigDict(frozen=True)

    attestation_fingerprint: bytes
    attester: VacantId
    revoked_at: datetime
    signature: bytes = b""

    def signing_payload(self) -> bytes:
        return b"\x1f".join(
            [
                ATTESTATION_REVOCATION_INTENT.encode("utf-8"),
                self.attestation_fingerprint,
                self.attester.pubkey_bytes,
                _utc_iso(self.revoked_at).encode("utf-8"),
            ]
        )

    def verify(self) -> bool:
        if not self.signature:
            return False
        return verify(
            self.attester.verify_key(),
            self.signing_payload(),
            self.signature,
        )


def revoke_attestation(
    att: PeerAttestation,
    attester_signing_key: SigningKey,
    *,
    revoked_at: datetime | None = None,
) -> RevocationRecord:
    """Build a signed revocation token for `att`.

    The signing key must correspond to `att.attester` (only the original
    attester can revoke their own claim — verified by the signature).
    """
    when = (revoked_at or datetime.now(UTC)).astimezone(UTC)
    unsigned = RevocationRecord(
        attestation_fingerprint=att.fingerprint(),
        attester=att.attester,
        revoked_at=when,
    )
    sig = sign(attester_signing_key, unsigned.signing_payload())
    record = unsigned.model_copy(update={"signature": sig})
    if not record.verify():
        # Defensive: the caller passed a key that doesn't match `att.attester`.
        raise AttestationError("revoke_attestation: signing key does not match attester pubkey")
    return record


def is_revoked(att: PeerAttestation, revocations: list[RevocationRecord]) -> bool:
    """True iff `revocations` contains a *valid* revocation naming `att`."""
    fp = att.fingerprint()
    for r in revocations:
        if r.attestation_fingerprint == fp and r.attester == att.attester and r.verify():
            return True
    return False
