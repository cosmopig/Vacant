"""Blinded peer review — THEORY_V5 §3.9 #4 Heisenberg-mitigation #4.

The unblinded peer-review path in `vacant.runtime.peer_review` writes
the reviewer's pubkey to the target's `reviews_received.jsonl` in
plaintext from the very first row. That makes immediate tit-for-tat
retaliation trivial: the moment Alice writes a low review of Bob,
Bob's grow loop can identify Alice and reciprocate.

V5 §3.9 #4 calls for the reviewer_id to be hashed initially and
revealed only after N rows accumulate, which structurally breaks the
immediate-reciprocity channel without weakening the long-term
audit trail.

This module provides the cryptographic primitives. The wire-level
hookup into `peer_review_tick` and `/reviews/ingest` is opt-in
(callers that want the protection construct their pipeline around
these primitives; the default unblinded path is untouched).

Protocol sketch:

    1. Reviewer R wants to submit a review of target T.
    2. R picks a fresh 32-byte nonce.
    3. R computes `commitment = BLAKE2b-256(R.pubkey || nonce || T.vid)`.
    4. R signs the review record where the `reviewer` field is
       replaced by `reviewer_commitment = commitment`, plus
       `commitment_scheme = "blake2b-pubkey-nonce-target-v1"`.
    5. R *separately* stores a sealed `RevealEnvelope` containing
       `{commitment, pubkey, nonce, signed_by_reviewer}` that they
       (or the batch operator) will release once N reviews of T
       have accumulated.
    6. After N reveals are released, every prior blinded record's
       reviewer can be linked back; the aggregator updates posteriors
       at that point.

Trade-offs (called out so callers know what they get):

- Replay-resistance: nonces are unique per review, so attackers can't
  observe an old commitment and re-bind it to a different reviewer.
- Forward secrecy: revealing the envelope does NOT compromise other
  reviewers in the same batch — each is independent.
- Honesty: a reviewer cannot lie about who they are at reveal time
  because BLAKE2b is preimage-resistant and the signature on the
  envelope ties (pubkey, nonce, commitment) together.
- Storage: blinded reviews and reveal envelopes are written separately
  so an inspector can audit "I have N blinded reviews; here are the N
  reveals that decode them."
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from vacant.core.crypto import (
    SigningKey,
    VerifyKey,
    hash_blake2b,
    pubkey_from_bytes,
    sign,
    verify,
)

__all__ = [
    "BLINDED_COMMITMENT_SCHEME",
    "BlindedReviewBatch",
    "RevealEnvelope",
    "commit_reviewer",
    "make_blinded_review_record",
    "make_reveal_envelope",
    "unblind_record",
    "verify_reveal",
]


BLINDED_COMMITMENT_SCHEME = "blake2b-pubkey-nonce-target-v1"


def _canonical_commitment_bytes(
    reviewer_pubkey: bytes, nonce: bytes, target_vid_hex: str
) -> bytes:
    """Bytes the commitment hashes over.

    Concrete byte layout (so older verifiers can re-derive without
    importing this module):
        b"v1|" + reviewer_pubkey (32) + b"|" + nonce (32) + b"|" + target_vid_hex (utf-8).
    """
    if len(reviewer_pubkey) != 32:
        raise ValueError(f"reviewer_pubkey must be 32 bytes, got {len(reviewer_pubkey)}")
    if len(nonce) != 32:
        raise ValueError(f"nonce must be 32 bytes, got {len(nonce)}")
    return (
        b"v1|"
        + bytes(reviewer_pubkey)
        + b"|"
        + bytes(nonce)
        + b"|"
        + target_vid_hex.encode("utf-8")
    )


def commit_reviewer(
    *,
    reviewer_pubkey: bytes,
    target_vid_hex: str,
    nonce: bytes | None = None,
) -> tuple[bytes, bytes]:
    """Produce `(commitment, nonce)`.

    If `nonce` is None we sample a fresh 32-byte cryptographic random
    value. The commitment is BLAKE2b-256 of
    `_canonical_commitment_bytes(...)`.
    """
    if nonce is None:
        nonce = os.urandom(32)
    payload = _canonical_commitment_bytes(reviewer_pubkey, nonce, target_vid_hex)
    return hash_blake2b(payload), nonce


@dataclass(frozen=True)
class RevealEnvelope:
    """Sealed reveal: maps a commitment back to the reviewer's pubkey.

    Until the operator releases this envelope, the matching blinded
    review's `reviewer_commitment` is computationally undetectable
    (BLAKE2b preimage-resistance). The `signature` field binds the
    triple `(commitment, reviewer_pubkey, nonce)` to the reviewer's
    private key — so a forged envelope claiming to map a commitment
    to a different reviewer must produce a valid signature *from the
    real reviewer's key*, which they don't have.
    """

    commitment_hex: str
    reviewer_pubkey_hex: str
    nonce_hex: str
    target_vid_hex: str
    scheme: str = BLINDED_COMMITMENT_SCHEME
    signature_hex: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "commitment_hex": self.commitment_hex,
            "reviewer_pubkey_hex": self.reviewer_pubkey_hex,
            "nonce_hex": self.nonce_hex,
            "target_vid_hex": self.target_vid_hex,
            "scheme": self.scheme,
            "signature_hex": self.signature_hex,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RevealEnvelope:
        return cls(
            commitment_hex=d["commitment_hex"],
            reviewer_pubkey_hex=d["reviewer_pubkey_hex"],
            nonce_hex=d["nonce_hex"],
            target_vid_hex=d["target_vid_hex"],
            scheme=d.get("scheme", BLINDED_COMMITMENT_SCHEME),
            signature_hex=d.get("signature_hex", ""),
        )


def make_reveal_envelope(
    *,
    reviewer_signing_key: SigningKey,
    nonce: bytes,
    commitment: bytes,
    target_vid_hex: str,
) -> RevealEnvelope:
    """Build + sign a `RevealEnvelope` for one blinded review.

    The signature covers `commitment || nonce || target_vid_hex || scheme`
    so a verifier can later check that the reviewer truly committed to
    this pair without trusting the storage layer.
    """
    reviewer_pubkey = bytes(reviewer_signing_key.verify_key)
    sign_payload = (
        commitment
        + b"|"
        + nonce
        + b"|"
        + target_vid_hex.encode("utf-8")
        + b"|"
        + BLINDED_COMMITMENT_SCHEME.encode("utf-8")
    )
    sig = sign(reviewer_signing_key, sign_payload)
    return RevealEnvelope(
        commitment_hex=commitment.hex(),
        reviewer_pubkey_hex=reviewer_pubkey.hex(),
        nonce_hex=nonce.hex(),
        target_vid_hex=target_vid_hex,
        scheme=BLINDED_COMMITMENT_SCHEME,
        signature_hex=sig.hex(),
    )


def verify_reveal(envelope: RevealEnvelope) -> bool:
    """Check that the reveal envelope is internally consistent + signed.

    Returns False on any malformed input rather than raising — callers
    that want a specific error message can branch on the False return.
    """
    if envelope.scheme != BLINDED_COMMITMENT_SCHEME:
        return False
    try:
        pubkey_bytes = bytes.fromhex(envelope.reviewer_pubkey_hex)
        nonce = bytes.fromhex(envelope.nonce_hex)
        commitment = bytes.fromhex(envelope.commitment_hex)
        sig = bytes.fromhex(envelope.signature_hex)
    except ValueError:
        return False
    if len(pubkey_bytes) != 32 or len(nonce) != 32 or len(commitment) != 32:
        return False
    # Re-derive commitment + verify it matches the stored one.
    try:
        recomputed = hash_blake2b(
            _canonical_commitment_bytes(pubkey_bytes, nonce, envelope.target_vid_hex)
        )
    except ValueError:
        return False
    if recomputed != commitment:
        return False
    try:
        vk: VerifyKey = pubkey_from_bytes(pubkey_bytes)
    except Exception:
        return False
    sign_payload = (
        commitment
        + b"|"
        + nonce
        + b"|"
        + envelope.target_vid_hex.encode("utf-8")
        + b"|"
        + envelope.scheme.encode("utf-8")
    )
    return verify(vk, sign_payload, sig)


def make_blinded_review_record(
    *,
    reviewer_signing_key: SigningKey,
    target_vid_hex: str,
    dimensions: dict[str, float],
    substrate: str,
    call_envelope_id_hex: str,
    claim: str,
    issued_at_iso: str,
    nonce: bytes | None = None,
) -> tuple[dict[str, Any], RevealEnvelope]:
    """Produce `(blinded_review_record, reveal_envelope)`.

    The blinded record has the same shape as the unblinded path's
    output (`runtime.peer_review._sign_review_record`) but with:
    - `reviewer_commitment` instead of `reviewer`
    - `commitment_scheme` field added
    - everything else identical

    The reveal envelope is what the batch operator releases after N
    blinded records have accumulated. Storage is the caller's choice
    (e.g., a separate `reveals_received.jsonl` or in-memory).
    """
    reviewer_pubkey = bytes(reviewer_signing_key.verify_key)
    commitment, used_nonce = commit_reviewer(
        reviewer_pubkey=reviewer_pubkey,
        target_vid_hex=target_vid_hex,
        nonce=nonce,
    )

    payload = {
        "reviewer_commitment": commitment.hex(),
        "commitment_scheme": BLINDED_COMMITMENT_SCHEME,
        "target": target_vid_hex,
        "dimensions": dimensions,
        "substrate": substrate,
        "call_envelope_id_hex": call_envelope_id_hex,
        "claim": claim,
        "issued_at": issued_at_iso,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload_hash = hash_blake2b(canonical.encode("utf-8"))
    signature = sign(reviewer_signing_key, payload_hash)
    record = {
        **payload,
        "payload_hash_hex": payload_hash.hex(),
        "signature_hex": signature.hex(),
    }

    envelope = make_reveal_envelope(
        reviewer_signing_key=reviewer_signing_key,
        nonce=used_nonce,
        commitment=commitment,
        target_vid_hex=target_vid_hex,
    )
    return record, envelope


def unblind_record(
    record: dict[str, Any], envelope: RevealEnvelope
) -> dict[str, Any] | None:
    """Map a blinded review record back to its plaintext-reviewer form.

    Returns the unblinded equivalent (with a `reviewer` field added,
    matching the unblinded path's shape) iff:
    - `record["commitment_scheme"] == BLINDED_COMMITMENT_SCHEME`
    - `record["reviewer_commitment"] == envelope.commitment_hex`
    - `record["target"] == envelope.target_vid_hex`
    - `verify_reveal(envelope)` passes
    - the record's own `signature_hex` verifies against the revealed
      reviewer pubkey (so a reveal can't be paired with someone
      else's record)

    Returns None otherwise — the caller decides whether to raise or
    drop the row.
    """
    if record.get("commitment_scheme") != BLINDED_COMMITMENT_SCHEME:
        return None
    if record.get("reviewer_commitment") != envelope.commitment_hex:
        return None
    if record.get("target") != envelope.target_vid_hex:
        return None
    if not verify_reveal(envelope):
        return None
    # Re-derive the canonical payload bytes (same fields the reviewer signed)
    # and verify the record's signature against the now-revealed pubkey.
    try:
        pubkey_bytes = bytes.fromhex(envelope.reviewer_pubkey_hex)
        record_sig = bytes.fromhex(record.get("signature_hex", ""))
        record_hash = bytes.fromhex(record.get("payload_hash_hex", ""))
    except ValueError:
        return None
    # Reconstruct the canonical commitment-bearing payload exactly.
    payload = {k: v for k, v in record.items() if k not in ("payload_hash_hex", "signature_hex")}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if hash_blake2b(canonical.encode("utf-8")) != record_hash:
        return None
    try:
        vk = pubkey_from_bytes(pubkey_bytes)
    except Exception:
        return None
    if not verify(vk, record_hash, record_sig):
        return None
    # All checks passed — emit the unblinded record.
    unblinded = {k: v for k, v in record.items() if k != "reviewer_commitment"}
    unblinded["reviewer"] = envelope.reviewer_pubkey_hex
    return unblinded


@dataclass
class BlindedReviewBatch:
    """Operator-side accumulator: buffer blinded reviews + their
    paired reveal envelopes; emit unblinded rows in a batch once
    `min_reveal_size` *distinct* reviewers have committed.

    Per V5 §3.9 #4: tit-for-tat retaliation is structurally broken
    because Bob (the target) cannot resolve Alice's commitment back
    to her pubkey until enough other reviewers have also committed —
    by which time the immediate retaliation window has closed.

    Threshold is by *distinct reviewer pubkey*, not by row count.
    Without that, a single attacker could submit `min_reveal_size`
    blinded reviews with different nonces and unblind themselves
    (the reveal envelopes ARE signed by the reviewer's real key, so
    the unblind step resolves all of them back to the attacker —
    defeating the protection).

    Poison-pill recovery: if one (record, envelope) pair fails
    `unblind_record`, `flush_reveals` drops *that pair* from the
    buffer (bumping `dropped_pairs_count`) and keeps the rest. Earlier
    behavior preserved the whole buffer indefinitely, which let a
    single bad submission stall the entire batch.

    **Layered Sybil defence (deliberate scope cut).** "Distinct
    pubkey" is a structural check, not a Sybil-resistance check.
    A determined attacker holding N independent keypairs can still
    fill the batch from their N keypairs alone and reach the
    distinct-reviewer threshold. That's NOT this primitive's job
    to defend against — V5's layered defence assigns Sybil-resistance
    to:

    - `same_controller` heuristic (V5 §3.5 / T5 three-layer pipeline)
    - `same_substrate` cluster cap (V5 §3.5)
    - same-stylo behaviour clustering (V5 §3.5)
    - cold-start prior discount (V5 §3.6)

    The aggregator applies those signals when it ingests the
    unblinded rows this batch emits. Blinding only defeats the
    *immediate-reciprocity* attack channel, which is a strictly
    weaker class than full-Sybil collusion.
    """

    min_reveal_size: int = 3
    """Number of *distinct reviewer pubkeys* to accumulate before
    reveal is allowed. V5 doesn't pin a number; 3 matches the
    unblinded path's spawn-trigger streak."""

    _pending: list[tuple[dict[str, Any], RevealEnvelope]] = field(default_factory=list)

    dropped_pairs_count: int = 0
    """Number of (record, envelope) pairs `flush_reveals` has dropped
    due to verification failure. An operator polling this counter can
    detect ongoing tampering attempts."""

    def add(self, record: dict[str, Any], envelope: RevealEnvelope) -> None:
        """Buffer one (blinded_record, reveal_envelope) pair."""
        if record.get("commitment_scheme") != BLINDED_COMMITMENT_SCHEME:
            raise ValueError(
                f"BlindedReviewBatch.add: record commitment_scheme is "
                f"{record.get('commitment_scheme')!r}, expected "
                f"{BLINDED_COMMITMENT_SCHEME!r}"
            )
        if record.get("reviewer_commitment") != envelope.commitment_hex:
            raise ValueError(
                "BlindedReviewBatch.add: record's reviewer_commitment "
                "does not match envelope's commitment_hex"
            )
        self._pending.append((record, envelope))

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def distinct_reviewers(self) -> int:
        """How many *distinct* reviewer pubkeys are committed in the
        current buffer. This is what `is_ready_to_reveal` checks
        against `min_reveal_size`."""
        return len({env.reviewer_pubkey_hex for _, env in self._pending})

    def is_ready_to_reveal(self) -> bool:
        return self.distinct_reviewers >= self.min_reveal_size

    def flush_reveals(self) -> list[dict[str, Any]]:
        """If the batch is ready, unblind every pending pair, drop
        any that fail verification, and clear the rest.

        Returns the unblinded rows. Drops bad pairs as a side effect
        and bumps `dropped_pairs_count`. An operator inspecting that
        counter can spot ongoing tampering without the batch ever
        deadlocking.
        """
        if not self.is_ready_to_reveal():
            return []
        unblinded: list[dict[str, Any]] = []
        for record, envelope in self._pending:
            row = unblind_record(record, envelope)
            if row is None:
                # Drop just this pair; do NOT stall the rest of the batch.
                self.dropped_pairs_count += 1
                continue
            unblinded.append(row)
        self._pending.clear()
        return unblinded
