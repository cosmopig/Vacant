"""Federation root set + M-of-N attestations (T4 / dispatch §4 / D004 §C / D016).

`RootSet` carries `(threshold, roots, revision)` where `threshold` is the
number of distinct root signatures required to validate a
`FederatedAttestation`. MVP defaults are 2-of-5 (CONSTANTS.md); the
long-term target is 3-of-9.

`RootSetHistory` is the append-only chain of revisions: every successful
`rotate_root` produces a new revision that is appended without
discarding the previous one. This lets the network verify
`FederatedAttestation`s issued *before* a rotation against the rootset
that was active at issuance time, without needing the verifier to
remember which rootset was current at which moment (D016).

Each `FederatedAttestation` records `issued_under_revision`, the
revision it was signed against. `signing_payload()` mixes this revision
into the digest so a signature collected for revision `R` cannot be
replayed against an attestation envelope claiming a different revision.

`verify_federated(att, history_or_rootset)` looks up the revision in the
history and verifies under that historical rootset. The caller may also
pass a single `RootSet` (the verification still demands
`rootset.revision == att.issued_under_revision`); this is the
backward-compatible path used by tests that operate on a single
revision.
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
    "RootSetHistory",
    "RootSignature",
    "build_federated_attestation",
    "default_mvp_rootset",
    "issue_root_signature",
    "rotate_root",
    "sign_rotation",
    "verify_federated",
]


@dataclass(frozen=True)
class RootSet:
    """An (M, N) root set for federated attestations.

    `revision` is a monotonic counter incremented by every successful
    rotation. It exists so that "rotate-out-then-back-in" sequences
    (which return to the same membership) still produce a distinct
    state hash and therefore reject replayed rotation signatures
    (D005 §1). It is also the key under which a `RootSetHistory`
    indexes this revision (D016).
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


# --- RootSet history (D016) --------------------------------------------------


@dataclass(frozen=True)
class RootSetHistory:
    """Append-only chain of `RootSet` revisions.

    `revisions[i].revision == i` for every `i`. This lets a verifier
    look up the rootset that was active at any past revision in O(1)
    and confirms that the chain has no gaps. The head
    (`revisions[-1]`) is the *current* rootset; older entries are kept
    so `FederatedAttestation`s issued before a rotation remain
    verifiable (D016).

    Construct via `RootSetHistory.from_initial(rootset)` (revision 0)
    and grow via `extend(new_rootset)` or the convenience
    `apply_rotation(...)` wrapper around `rotate_root`.
    """

    revisions: tuple[RootSet, ...]

    def __post_init__(self) -> None:
        if not self.revisions:
            raise FederationError("RootSetHistory must contain at least one revision")
        for i, rs in enumerate(self.revisions):
            if rs.revision != i:
                raise FederationError(
                    f"RootSetHistory: revision[{i}].revision = {rs.revision}, expected {i}"
                )

    @classmethod
    def from_initial(cls, rootset: RootSet) -> RootSetHistory:
        """Build a history with a single revision (the initial rootset).

        The rootset's `revision` field must be 0 (a fresh history starts
        at revision 0). Use `apply_rotation` / `extend` to grow it.
        """
        if rootset.revision != 0:
            raise FederationError(
                f"RootSetHistory.from_initial: rootset.revision must be 0, got {rootset.revision}"
            )
        return cls(revisions=(rootset,))

    @property
    def current(self) -> RootSet:
        return self.revisions[-1]

    @property
    def current_revision(self) -> int:
        return self.current.revision

    def at(self, revision: int) -> RootSet:
        """Return the rootset that was active at `revision`. Raises
        `FederationError` if the revision is not in the history."""
        if revision < 0 or revision >= len(self.revisions):
            raise FederationError(
                f"RootSetHistory has no revision {revision} "
                f"(history covers 0..{len(self.revisions) - 1})"
            )
        return self.revisions[revision]

    def extend(self, new_rootset: RootSet) -> RootSetHistory:
        """Append a new revision. The new rootset's `revision` must be
        exactly `current_revision + 1` (the rotation chain is dense)."""
        expected = self.current_revision + 1
        if new_rootset.revision != expected:
            raise FederationError(
                f"RootSetHistory.extend: new revision must be {expected}, "
                f"got {new_rootset.revision}"
            )
        return RootSetHistory(revisions=(*self.revisions, new_rootset))

    def apply_rotation(
        self,
        *,
        old_root: VacantId,
        new_root: VacantId,
        signatures: list[RootSignature],
    ) -> RootSetHistory:
        """Convenience wrapper: apply `rotate_root` to the current
        revision and append the result to the history."""
        new_rs = rotate_root(
            self.current, old_root=old_root, new_root=new_root, signatures=signatures
        )
        return self.extend(new_rs)


# --- Attestation envelope ----------------------------------------------------


class RootSignature(BaseModel):
    """One root's contribution to a federated attestation."""

    model_config = ConfigDict(frozen=True)

    root: VacantId
    signature: bytes


class FederatedAttestation(BaseModel):
    """An attestation cosigned by ≥ M roots from a `RootSet`.

    `issued_under_revision` records which `RootSetHistory` revision the
    signatures were collected against. The signing payload mixes the
    revision in so a signature collected for revision `R` cannot be
    moved into an envelope claiming a different revision (D016). Older
    callers that operate on a single rootset may rely on the default
    of 0; verifiers will demand `rootset.revision == 0` to accept such
    attestations.
    """

    model_config = ConfigDict(frozen=True)

    subject: VacantId
    """The vacant the attestation is *about*."""

    claim: str
    """Free-form claim string, hashed into the signing payload."""

    signatures: list[RootSignature] = Field(default_factory=list)

    issued_under_revision: int = 0
    """Revision of the `RootSetHistory` the signatures were issued under."""

    def signing_payload(self) -> bytes:
        return hash_blake2b(
            self.subject.pubkey_bytes
            + b"\x1f"
            + self.claim.encode("utf-8")
            + b"\x1f"
            + str(self.issued_under_revision).encode("utf-8")
        )


def issue_root_signature(
    *,
    root: VacantId,
    root_signing_key: SigningKey,
    subject: VacantId,
    claim: str,
    issued_under_revision: int = 0,
) -> RootSignature:
    """Helper: produce a single root's contribution to an attestation.

    The signing payload includes `issued_under_revision`, so a signature
    collected for one revision will not validate inside an envelope
    that claims a different revision (D016).
    """
    payload = FederatedAttestation(
        subject=subject,
        claim=claim,
        signatures=[],
        issued_under_revision=issued_under_revision,
    ).signing_payload()
    sig = sign(root_signing_key, payload)
    return RootSignature(root=root, signature=sig)


def build_federated_attestation(
    *,
    history: RootSetHistory,
    subject: VacantId,
    claim: str,
    signatures: list[RootSignature],
) -> FederatedAttestation:
    """Construct a `FederatedAttestation` tagged with the *current*
    revision of `history`.

    Use this instead of constructing `FederatedAttestation` directly
    whenever you have the live history available — it prevents a caller
    from accidentally tagging a fresh attestation with a stale revision
    and is the ergonomic counterpart to `RootSetHistory.apply_rotation`
    (D016).

    Signatures must already be collected via `issue_root_signature(...,
    issued_under_revision=history.current_revision)`. The resulting
    attestation will fail `verify_federated` if signers used the wrong
    revision in their payload — which is the point: a stale-revision
    issuance is detectable at verification time.
    """
    return FederatedAttestation(
        subject=subject,
        claim=claim,
        signatures=signatures,
        issued_under_revision=history.current_revision,
    )


def verify_federated(
    attestation: FederatedAttestation,
    rootset_or_history: RootSet | RootSetHistory,
) -> bool:
    """True iff ≥ `rootset.threshold` *distinct* signatures from the
    rootset that was active at `attestation.issued_under_revision`
    validly cover `attestation.signing_payload()`.

    When given a `RootSetHistory`, the function looks up the rootset
    active at the attestation's revision (D016). When given a single
    `RootSet`, the function additionally requires
    `rootset.revision == attestation.issued_under_revision`; this is
    the back-compat path for callers that already know they are
    operating against a single revision.
    """
    if isinstance(rootset_or_history, RootSetHistory):
        try:
            rootset = rootset_or_history.at(attestation.issued_under_revision)
        except FederationError:
            return False
    else:
        rootset = rootset_or_history
        if rootset.revision != attestation.issued_under_revision:
            return False

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
