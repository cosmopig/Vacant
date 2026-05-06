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
    """Build the canonical byte form of a registry event.

    The same byte string is fed to both `sign()` (when the actor
    creates the event) and `verify()` (when the registry accepts it).
    It is also the pre-image of `event_hash`. Matches P4 §3.1 hash-
    chain canonical rules (modulo BLAKE2b vs BLAKE3 — see D006 §A).

    Args:
        event_type: Event kind (e.g. `"halo_publish"`, `"review"`).
        actor_vacant_id: Hex of the vacant submitting the event.
        subject_vacant_id: Optional hex of the vacant the event is
            *about* (e.g. the target of a review). Empty string when
            absent.
        payload_hash: BLAKE2b of the event-specific payload.
        idempotency_key: Caller-supplied identifier for de-dup.
        signed_by_pubkey: Raw 32-byte Ed25519 pubkey expected to have
            signed the event.
        ts: Unix timestamp in seconds (or epoch-resolution of choice).
        actor_seq: Strictly-increasing per-actor sequence number.

    Returns:
        Bytes with the eight fields joined by the `0x1f` separator,
        suitable for signing or verification.
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
    """Verify an event signature, raising on any failure.

    Args:
        pubkey_bytes: Raw 32-byte Ed25519 pubkey to verify under.
        canonical_bytes: Output of `canonical_event_bytes(...)`.
        signature: Ed25519 signature claimed by the actor.

    Raises:
        SignatureRejected: If `pubkey_bytes` is malformed, or the
            signature does not validate over `canonical_bytes`.
    """
    try:
        vk = pubkey_from_bytes(pubkey_bytes)
    except Exception as exc:
        raise SignatureRejected(f"invalid pubkey: {exc}") from exc
    if not verify(vk, canonical_bytes, signature):
        raise SignatureRejected("event signature did not verify")


def compute_event_hash(
    *, prev_event_hash: bytes, canonical_bytes: bytes, signature: bytes
) -> bytes:
    """Compute the hash that links one event to the next in the chain.

    The signature is mixed in so two events with identical canonical
    bytes but distinct actors (one impersonating the other) cannot
    collide — defensive against an adversary who somehow forged a
    canonical-byte collision.

    Args:
        prev_event_hash: Hash of the previous event in the chain.
        canonical_bytes: Output of `canonical_event_bytes(...)`.
        signature: Actor's Ed25519 signature over `canonical_bytes`.

    Returns:
        `BLAKE2b(prev || canonical || signature)`. Stored on the event
        row and used as `prev_event_hash` for the next insert.
    """
    return hash_blake2b(prev_event_hash + canonical_bytes + signature)


# --- L2: sequence monotonicity -----------------------------------------------


def check_sequence_monotonic(*, last_seq: int, candidate_seq: int) -> None:
    """Enforce strict-by-one monotonicity for a per-actor sequence number.

    `CONSTANTS.md` pins "Sequence-number monotonicity tolerance: 0
    (strict)" — the candidate must be **exactly** `last_seq + 1`, not
    just `> last_seq`. The strict form catches both reordering attacks
    (where a stale event is replayed) and gap-introduction attacks
    (where a malicious actor bumps the sequence to skip auditable
    history).

    Args:
        last_seq: Highest `actor_seq` already accepted for this actor.
            Use `0` for a fresh actor (their first event must claim
            `actor_seq=1`).
        candidate_seq: The `actor_seq` claimed by the inbound event.

    Raises:
        SequenceMonotonicityError: If `candidate_seq != last_seq + 1`.
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
    """Reject attestations that are outside their validity window.

    Args:
        valid_from_ms: Earliest moment the attestation should be
            accepted, in milliseconds since epoch.
        valid_until_ms: Latest moment, or `None` for no upstream
            ceiling. The aggregator may still apply its own ceiling at
            consume time.
        now_ms: Wall-clock timestamp the registry will compare
            against.

    Raises:
        FreshnessError: If `now_ms < valid_from_ms` ("not yet valid")
            or, when `valid_until_ms` is set, `now_ms > valid_until_ms`
            ("expired").
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
    """Build the full Merkle tree as a list of levels.

    Args:
        leaves: Pre-image bytes for each leaf. Order is significant —
            inclusion proofs index into this order.

    Returns:
        A list of levels, leaves first, root last (so the root is at
        `tree[-1][0]`). For an empty input the tree is
        `[[BLAKE2b(b"\\x00")]]` so empty epochs still have a stable
        root shape.
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
    """Build only the root (convenience wrapper).

    Args:
        leaves: Pre-image bytes for each leaf, in deterministic order.

    Returns:
        The 32-byte root hash. For empty input, a stable empty-epoch
        root.
    """
    return build_merkle_tree(leaves)[-1][0]


@dataclass(frozen=True)
class MerkleProof:
    """Inclusion proof: sibling hashes from leaf up to (but excluding) root.

    The position of each sibling (left vs right) is reconstructed by
    walking the bits of `leaf_index` rather than tagging each sibling
    explicitly — saves a byte per level and matches RFC 6962.

    Attributes:
        leaf_index: Position of the leaf in the original sequence.
        leaf: The hashed leaf (`BLAKE2b(b"\\x00" || preimage)`).
        siblings: Hashes of the sibling at each level, leaf side
            up. Length equals `log2(padded_n)`.
    """

    leaf_index: int
    leaf: bytes
    siblings: tuple[bytes, ...]


def merkle_inclusion_proof(leaves: Sequence[bytes], leaf_index: int) -> MerkleProof:
    """Build an inclusion proof for the leaf at `leaf_index`.

    Args:
        leaves: The full leaf sequence the tree was built over.
        leaf_index: Index into `leaves`.

    Returns:
        A `MerkleProof` whose `verify_inclusion_proof(...)` will
        succeed against the root of the same tree.

    Raises:
        IndexError: If `leaf_index` is out of range.
    """
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
    """Verify that `proof.leaf` is included in a tree with `root`.

    Args:
        proof: The proof returned by `merkle_inclusion_proof`.
        root: The expected Merkle root.

    Returns:
        `True` iff folding `proof.leaf` upward with `proof.siblings`
        (using `proof.leaf_index` to decide left/right at each level)
        yields `root`.
    """
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
    """Operator-key signature over an epoch root.

    Args:
        root: The epoch's Merkle root.
        signing_key: The registry operator's private key.

    Returns:
        Ed25519 signature over `b"vacant:registry:epoch:" || root`.
        The domain-separation prefix prevents the signature from being
        replayed against a non-epoch payload that happens to start
        with these bytes.
    """
    return sign(signing_key, b"vacant:registry:epoch:" + root)


def verify_epoch_signature(*, root: bytes, signature: bytes, operator_pubkey: VerifyKey) -> bool:
    """Verify a previously-signed epoch root.

    Args:
        root: The epoch's Merkle root.
        signature: Output of `sign_epoch_root`.
        operator_pubkey: The expected operator verify-key.

    Returns:
        `True` iff `signature` validates over the domain-separated
        epoch payload.
    """
    return verify(operator_pubkey, b"vacant:registry:epoch:" + root, signature)


# --- L5: anomaly counters ----------------------------------------------------


@dataclass(frozen=True)
class AnomalyAssessment:
    """Outcome of evaluating one anomaly counter against its threshold.

    Attributes:
        metric: Counter name (e.g. `"rep_jump_24h"`).
        value: Measured value.
        threshold: Threshold from the operator's configuration.
        triggered: `True` iff `value >= threshold`. Surfaced to the
            operator as a flag, **not** as a hard reject — anomaly
            counters are detection signals, not authorisation gates.
    """

    metric: str
    value: float
    threshold: float
    triggered: bool


def assess_anomaly(*, metric: str, value: float, threshold: float) -> AnomalyAssessment:
    """Compare `value` to `threshold` and package as an `AnomalyAssessment`.

    Args:
        metric: Counter name.
        value: Measured value.
        threshold: Threshold to compare against.

    Returns:
        An `AnomalyAssessment` with `triggered=True` iff
        `value >= threshold`.
    """
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
    """SHA-256 hex digest helper for test-fixture ergonomics.

    BLAKE2b is the canonical hash everywhere in the registry; this
    helper exists only because some fixtures predate the BLAKE2b
    canonicalisation and retain SHA-256 inputs.

    Args:
        data: Bytes to digest.

    Returns:
        Lowercase 64-character hex digest.
    """
    return hashlib.sha256(data).hexdigest()
