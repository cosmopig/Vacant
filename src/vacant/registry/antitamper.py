"""Six anti-tamper layers (dispatch §5):

1. **Signature verify** — every write checks the actor's Ed25519 signature
   against the canonical event bytes before insert.
2. **Sequence-number monotonicity** — per-vacant `actor_seq` strictly
   increases; out-of-order writes are rejected.
3. **Freshness window** — attestations carry a validity window; stale
   attestations fail at `submit_attestation` time and again at consume
   time.
4. **Merkle-root snapshots** — `seal_epoch()` builds a balanced Merkle
   tree over all unsealed event hashes and stores the root + the
   registry operator's signature on it.
5. **Anomaly counters** — rule-based windows over rep-jump, review
   bursts, spawn rates; surfaced as a `triggered` flag, not a hard block.
6. **Append-only audit log** — every signed write also lands in the
   event log; DELETE on `event` is rejected at the store layer.

These are pure functions (no I/O); the store wires them in before commit.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

from vacant.core.crypto import (
    SigningKey,
    VerifyKey,
    hash_blake2b,
    pubkey_from_bytes,
    sign,
    verify,
)
from vacant.registry.errors import (
    FreshnessError,
    SequenceMonotonicityError,
    SignatureRejected,
)

__all__ = [
    "MerkleProof",
    "build_merkle_root",
    "build_merkle_tree",
    "canonical_event_bytes",
    "check_attestation_freshness",
    "check_sequence_monotonic",
    "compute_event_hash",
    "merkle_inclusion_proof",
    "sign_epoch_root",
    "verify_event_signature",
    "verify_inclusion_proof",
]


# --- L1: signature verify ----------------------------------------------------


def canonical_event_bytes(
    *,
    event_type: str,
    actor_vacant_id: str,
    subject_vacant_id: str | None,
    payload_hash: bytes,
    idempotency_key: str,
    signed_by_pubkey: bytes,
    ts: int,
    actor_seq: int,
) -> bytes:
    """Canonical byte form of an event, used for both signing and the
    pre-image of `event_hash`. Matches P4 §3.1 hash-chain canonical rules
    (modulo BLAKE2b vs BLAKE3 — see D006 §A).
    """
    return b"\x1f".join(
        [
            event_type.encode("utf-8"),
            actor_vacant_id.encode("utf-8"),
            (subject_vacant_id or "").encode("utf-8"),
            payload_hash,
            idempotency_key.encode("utf-8"),
            signed_by_pubkey,
            ts.to_bytes(8, "big"),
            actor_seq.to_bytes(8, "big"),
        ]
    )


def verify_event_signature(
    *,
    pubkey_bytes: bytes,
    canonical_bytes: bytes,
    signature: bytes,
) -> None:
    """Raise `SignatureRejected` if `signature` doesn't verify."""
    try:
        vk = pubkey_from_bytes(pubkey_bytes)
    except Exception as exc:
        raise SignatureRejected(f"invalid pubkey: {exc}") from exc
    if not verify(vk, canonical_bytes, signature):
        raise SignatureRejected("event signature did not verify")


def compute_event_hash(
    *, prev_event_hash: bytes, canonical_bytes: bytes, signature: bytes
) -> bytes:
    """`event_hash = H(prev_event_hash || canonical_bytes || signature)`.

    Includes the signature so two events with identical canonical bytes
    but different actors (one impersonating the other) produce distinct
    hashes — defensive against an adversary who somehow forged a
    canonical-byte collision.
    """
    return hash_blake2b(prev_event_hash + canonical_bytes + signature)


# --- L2: sequence monotonicity -----------------------------------------------


def check_sequence_monotonic(*, last_seq: int, candidate_seq: int) -> None:
    """Strictly increasing per-vacant `actor_seq`. CONSTANTS.md says
    "Sequence-number monotonicity tolerance: 0 (strict)" — the candidate
    must be exactly `last_seq + 1`, not just `> last_seq`. This catches
    both reordering attacks and gap-introduction attacks.
    """
    expected = last_seq + 1
    if candidate_seq != expected:
        raise SequenceMonotonicityError(
            f"actor_seq must equal last_seq + 1 = {expected}, got {candidate_seq}"
        )


# --- L3: attestation freshness ----------------------------------------------


def check_attestation_freshness(
    *,
    valid_from_ms: int,
    valid_until_ms: int | None,
    now_ms: int,
) -> None:
    """Raise `FreshnessError` if `now_ms` is outside `[valid_from, valid_until]`.

    `valid_until=None` means no expiry (per spec; aggregator may still
    apply a ceiling at consume time).
    """
    if now_ms < valid_from_ms:
        raise FreshnessError(
            f"attestation not yet valid (now={now_ms} < valid_from={valid_from_ms})"
        )
    if valid_until_ms is not None and now_ms > valid_until_ms:
        raise FreshnessError(f"attestation expired (now={now_ms} > valid_until={valid_until_ms})")


# --- L4: Merkle snapshots ----------------------------------------------------


def _pad_to_power_of_two(leaves: Sequence[bytes]) -> list[bytes]:
    """Right-pad with the last leaf to make tree balanced (RFC 6962 style)."""
    n = len(leaves)
    if n == 0:
        return []
    target = 1
    while target < n:
        target <<= 1
    if n == target:
        return list(leaves)
    return list(leaves) + [leaves[-1]] * (target - n)


def _node(left: bytes, right: bytes) -> bytes:
    return hash_blake2b(b"\x01" + left + right)


def _leaf(data: bytes) -> bytes:
    return hash_blake2b(b"\x00" + data)


def build_merkle_tree(leaves: Sequence[bytes]) -> list[list[bytes]]:
    """Build the full tree (list of levels, root last). Empty tree has root
    `H(b"\\x00")` to give a stable shape for empty epochs.
    """
    hashed = [_leaf(b) for b in leaves]
    if not hashed:
        return [[hash_blake2b(b"\x00")]]
    padded = _pad_to_power_of_two(hashed)
    levels = [padded]
    while len(levels[-1]) > 1:
        prev = levels[-1]
        nxt = [_node(prev[i], prev[i + 1]) for i in range(0, len(prev), 2)]
        levels.append(nxt)
    return levels


def build_merkle_root(leaves: Sequence[bytes]) -> bytes:
    """Convenience: just the root."""
    return build_merkle_tree(leaves)[-1][0]


@dataclass(frozen=True)
class MerkleProof:
    """Inclusion proof: sibling hashes from leaf up to (but excluding) root."""

    leaf_index: int
    leaf: bytes
    siblings: tuple[bytes, ...]
    """Each sibling tagged with its position: pairs of (is_right, hash)
    are encoded as the high-bit of the index — we reconstruct the side
    by walking the index bits."""


def merkle_inclusion_proof(leaves: Sequence[bytes], leaf_index: int) -> MerkleProof:
    if leaf_index < 0 or leaf_index >= len(leaves):
        raise IndexError(f"leaf_index {leaf_index} out of range for {len(leaves)} leaves")
    levels = build_merkle_tree(leaves)
    siblings: list[bytes] = []
    idx = leaf_index
    for level in levels[:-1]:
        sibling_idx = idx ^ 1
        siblings.append(level[sibling_idx])
        idx //= 2
    return MerkleProof(
        leaf_index=leaf_index,
        leaf=_leaf(leaves[leaf_index]),
        siblings=tuple(siblings),
    )


def verify_inclusion_proof(proof: MerkleProof, root: bytes) -> bool:
    """True iff `proof.leaf` is included in a tree with the given `root`."""
    h = proof.leaf
    idx = proof.leaf_index
    for sib in proof.siblings:
        if idx % 2 == 0:
            h = _node(h, sib)
        else:
            h = _node(sib, h)
        idx //= 2
    return h == root


def sign_epoch_root(*, root: bytes, signing_key: SigningKey) -> bytes:
    """Operator-key signature over an epoch root."""
    return sign(signing_key, b"vacant:registry:epoch:" + root)


def verify_epoch_signature(*, root: bytes, signature: bytes, operator_pubkey: VerifyKey) -> bool:
    return verify(operator_pubkey, b"vacant:registry:epoch:" + root, signature)


# --- L5: anomaly counters ----------------------------------------------------


@dataclass(frozen=True)
class AnomalyAssessment:
    metric: str
    value: float
    threshold: float
    triggered: bool


def assess_anomaly(*, metric: str, value: float, threshold: float) -> AnomalyAssessment:
    return AnomalyAssessment(
        metric=metric,
        value=value,
        threshold=threshold,
        triggered=value >= threshold,
    )


# --- L6: append-only audit log -----------------------------------------------
# Implemented at the store layer (no DELETE on `event`, `event_finalization`,
# `merkle_epoch`, `read_audit`). The store raises `AppendOnlyViolation`.

# Misc helpers for tests / external verifiers ---------------------------------


def sha256_hex(data: bytes) -> str:
    """For payload-hash ergonomics in test fixtures (BLAKE2b is canonical)."""
    return hashlib.sha256(data).hexdigest()
