"""Federation root set + M-of-N attestations (T4 / dispatch §4 / D004 §C).

`RootSet` carries `(threshold, roots)` where `threshold` is the number of
distinct root signatures required to validate a `FederatedAttestation`.
MVP defaults are 2-of-5 (CONSTANTS.md); the long-term target is 3-of-9.

`rotate_root(...)` performs a single (old → new) swap. Pre-rotation
attestations remain verifiable as long as the *signing* roots from the
attestation are still members of the current set OR have a documented
rotation history. For the MVP we keep rotation point-in-time: an
attestation made before a rotation verifies against the rootset of that
moment, so callers verifying historical attestations should use the
rootset that was active when the attestation was issued. The integration
test exercises this contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from pydantic import BaseModel, ConfigDict, Field

from vacant.core.constants import (
    FEDERATION_ROOT_COUNT_MVP,
    FEDERATION_ROOT_THRESHOLD_MVP,
)
from vacant.core.crypto import SigningKey, hash_blake2b, sign, verify
from vacant.core.types import VacantId
from vacant.identity.errors import FederationError

__all__ = [
    "FederatedAttestation",
    "RootSet",
    "RootSignature",
    "default_mvp_rootset",
    "issue_root_signature",
    "rotate_root",
    "verify_federated",
]


@dataclass(frozen=True)
class RootSet:
    """An (M, N) root set for federated attestations.

    `revision` is a monotonic counter incremented by every successful
    rotation. It exists solely to make the state hash strictly
    increasing so that "rotate-out-then-back-in" sequences (which
    return to the same membership) still produce a distinct state hash
    and therefore reject replayed rotation signatures (D005 §1).
    """

    threshold: int
    roots: tuple[VacantId, ...] = field(default_factory=tuple)
    revision: int = 0

    def __post_init__(self) -> None:
        if self.threshold < 1:
            raise FederationError(f"RootSet.threshold must be >= 1, got {self.threshold}")
        if len(self.roots) < self.threshold:
            raise FederationError(f"RootSet has {len(self.roots)} roots, need >= {self.threshold}")
        if len(set(self.roots)) != len(self.roots):
            raise FederationError("RootSet contains duplicate roots")
        if self.revision < 0:
            raise FederationError(f"RootSet.revision must be >= 0, got {self.revision}")

    @property
    def n(self) -> int:
        return len(self.roots)

    def contains(self, vid: VacantId) -> bool:
        return vid in self.roots

    def state_hash(self) -> bytes:
        """BLAKE2b digest binding rotation signatures to *this* rootset state.

        Without this binding, a quorum's rotation signature for `(old, new)`
        could be replayed against any future rootset that still contains
        `old` and lacks `new` — including a state arrived at by re-adding
        `old` after a previous rotation removed it (Padv-P2 finding D005
        §1). Including threshold + sorted pubkeys + monotonic `revision`
        makes signatures single-state even across rotate-out-then-back-in
        sequences.
        """
        return hash_blake2b(
            b"vacant:rootset:state"
            + b"\x1f"
            + str(self.threshold).encode("utf-8")
            + b"\x1f"
            + str(self.revision).encode("utf-8")
            + b"\x1f"
            + b"\x1f".join(sorted(r.pubkey_bytes for r in self.roots))
        )


def default_mvp_rootset(*, vacant_ids: list[VacantId] | None = None) -> RootSet:
    """Build a 2-of-5 rootset. If `vacant_ids` is given, use them
    (must have at least `FEDERATION_ROOT_COUNT_MVP` entries). Otherwise
    raise — we don't synthesise root identities silently.
    """
    if vacant_ids is None:
        raise FederationError("default_mvp_rootset() requires explicit vacant_ids")
    if len(vacant_ids) < FEDERATION_ROOT_COUNT_MVP:
        raise FederationError(
            f"need >= {FEDERATION_ROOT_COUNT_MVP} vacant_ids for MVP rootset, got {len(vacant_ids)}"
        )
    return RootSet(
        threshold=FEDERATION_ROOT_THRESHOLD_MVP,
        roots=tuple(vacant_ids[:FEDERATION_ROOT_COUNT_MVP]),
    )


# --- Attestation envelope ----------------------------------------------------


class RootSignature(BaseModel):
    """One root's contribution to a federated attestation."""

    model_config = ConfigDict(frozen=True)

    root: VacantId
    signature: bytes


class FederatedAttestation(BaseModel):
    """An attestation cosigned by ≥ M roots from a `RootSet`."""

    model_config = ConfigDict(frozen=True)

    subject: VacantId
    """The vacant the attestation is *about*."""

    claim: str
    """Free-form claim string, hashed into the signing payload."""

    signatures: list[RootSignature] = Field(default_factory=list)

    def signing_payload(self) -> bytes:
        return hash_blake2b(self.subject.pubkey_bytes + b"\x1f" + self.claim.encode("utf-8"))


def issue_root_signature(
    *,
    root: VacantId,
    root_signing_key: SigningKey,
    subject: VacantId,
    claim: str,
) -> RootSignature:
    """Helper: produce a single root's contribution to an attestation."""
    payload = FederatedAttestation(subject=subject, claim=claim, signatures=[]).signing_payload()
    sig = sign(root_signing_key, payload)
    return RootSignature(root=root, signature=sig)


def verify_federated(attestation: FederatedAttestation, rootset: RootSet) -> bool:
    """True iff ≥ `rootset.threshold` *distinct* signatures from
    `rootset.roots` validly cover `attestation.signing_payload()`.

    Signatures from non-members or duplicate signatures from the same
    member do not count.
    """
    payload = attestation.signing_payload()
    seen: set[VacantId] = set()
    for rs in attestation.signatures:
        if rs.root in seen:
            continue
        if not rootset.contains(rs.root):
            continue
        if verify(rs.root.verify_key(), payload, rs.signature):
            seen.add(rs.root)
        if len(seen) >= rootset.threshold:
            return True
    return False


# --- Rotation ----------------------------------------------------------------


def _rotation_payload(rootset: RootSet, old_root: VacantId, new_root: VacantId) -> bytes:
    """Canonical bytes signed during a rotation. Bound to the *current*
    rootset state so signatures cannot replay against a future state that
    happens to satisfy the same `(old_root, new_root)` precondition
    (Padv-P2 finding D005)."""
    return hash_blake2b(
        b"vacant:federation:rotate"
        + b"\x1f"
        + rootset.state_hash()
        + b"\x1f"
        + old_root.pubkey_bytes
        + b"\x1f"
        + new_root.pubkey_bytes
    )


def rotate_root(
    rootset: RootSet,
    *,
    old_root: VacantId,
    new_root: VacantId,
    signatures: list[RootSignature],
) -> RootSet:
    """Swap `old_root` for `new_root` in `rootset`.

    The rotation must itself be authorised by ≥ `rootset.threshold` valid
    signatures from the *current* rootset over the rotation payload
    (`state_hash || old_root || new_root`). Callers are responsible for
    collecting those signatures from the current quorum.

    Constraints:
    - `old_root` must be in `rootset`
    - `new_root` must NOT already be in `rootset` (rotation is a swap, not a duplicate)
    - rotation signatures must reach quorum under the *current* rootset
    - rotation signatures are bound to the current rootset state hash and
      cannot be replayed against a different rootset (Padv-P2 / D005).
    """
    if not rootset.contains(old_root):
        raise FederationError(f"rotate_root: {old_root} is not in the current rootset")
    if rootset.contains(new_root):
        raise FederationError(f"rotate_root: {new_root} is already in the rootset")

    payload = _rotation_payload(rootset, old_root, new_root)
    seen: set[VacantId] = set()
    for rs in signatures:
        if rs.root in seen or not rootset.contains(rs.root):
            continue
        if verify(rs.root.verify_key(), payload, rs.signature):
            seen.add(rs.root)
    if len(seen) < rootset.threshold:
        raise FederationError(
            f"rotate_root: only {len(seen)} valid quorum signatures, need {rootset.threshold}"
        )
    new_roots = tuple(new_root if r == old_root else r for r in rootset.roots)
    return replace(rootset, roots=new_roots, revision=rootset.revision + 1)


def sign_rotation(
    *,
    rootset: RootSet,
    root: VacantId,
    root_signing_key: SigningKey,
    old_root: VacantId,
    new_root: VacantId,
) -> RootSignature:
    """Helper: build a single root's signature on a rotation request.

    Includes `rootset` so the signature is bound to a specific rootset
    state — a quorum's rotation signature is single-use against the
    rootset it was collected for (Padv-P2 / D005).
    """
    payload = _rotation_payload(rootset, old_root, new_root)
    sig = sign(root_signing_key, payload)
    return RootSignature(root=root, signature=sig)
