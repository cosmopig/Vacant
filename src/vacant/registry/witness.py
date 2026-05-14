"""Federated witness cosignatures on Merkle epoch roots (decentralised trust
layer / technical.html row 4 "N-of-M attestation").

Where the central operator's signature on `MerkleEpoch.registry_signature`
trusts a *single* key, the witness layer collects independent Ed25519
signatures from peer registries (or any trusted observer) over the same
epoch root. An external verifier accepts the registry's history only if
≥ M cosignatures from a known peer set validate — turning the central MVP
registry into a federated multi-signer log without touching the central
store's schema beyond the existing `EpochWitness` table.

This is the concrete federated-backend complement to:
- `RegistryBackend` Protocol (the storage seam, `backend.py`)
- N-of-M federated attestations on identities (`identity/federation.py`)

The flow is:
1. Operator seals an epoch → `MerkleEpoch` row + `registry_signature`.
2. Operator distributes the *epoch witness statement*
   (`build_witness_statement`) to a quorum of peer registries.
3. Each peer that independently observed the same event log signs the
   statement with their witness key and returns a cosignature.
4. Operator persists each cosignature via `record_witness_cosignature`
   → `EpochWitness` rows.
5. Verifiers fetch the epoch + all `EpochWitness` rows and call
   `verify_witness_quorum(...)`.

The statement is bound to `root_hash + epoch_id + first_seq + last_seq +
tree_size + sealed_at`, so a witness cannot have their signature
replayed against a different epoch.

The `WitnessRootSet` mirrors `identity.federation.RootSet` (M-of-N
threshold semantics) but operates on registry-witness keys rather than
identity-root keys. They're kept separate so a compromise of an
identity root does not also compromise the transparency log, and vice
versa.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from vacant.core.crypto import (
    SigningKey,
    VerifyKey,
    hash_blake2b,
    pubkey_from_bytes,
    sign,
    verify,
)
from vacant.registry.errors import RegistryError
from vacant.registry.models import EpochWitness, MerkleEpoch

__all__ = [
    "WitnessCosignature",
    "WitnessError",
    "WitnessRootSet",
    "build_witness_statement",
    "issue_witness_cosignature",
    "verify_witness_cosignature",
    "verify_witness_quorum",
]


class WitnessError(RegistryError):
    """Raised when a witness cosignature is malformed or the quorum
    cannot be satisfied."""


@dataclass(frozen=True)
class WitnessRootSet:
    """M-of-N set of witness public keys.

    Witnesses sign with Ed25519. `threshold` is the number of distinct
    valid cosignatures required for `verify_witness_quorum` to succeed.

    Construction validates:
    - `1 ≤ threshold ≤ len(keys)`
    - no duplicate keys (a single witness cannot count twice toward quorum)
    """

    threshold: int
    keys: tuple[bytes, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.threshold < 1:
            raise WitnessError(f"WitnessRootSet.threshold must be >= 1, got {self.threshold}")
        if len(self.keys) < self.threshold:
            raise WitnessError(
                f"WitnessRootSet has {len(self.keys)} keys, need >= {self.threshold}"
            )
        if any(len(k) != 32 for k in self.keys):
            raise WitnessError("WitnessRootSet keys must be 32-byte Ed25519 pubkeys")
        if len(set(self.keys)) != len(self.keys):
            raise WitnessError("WitnessRootSet contains duplicate keys")

    def contains(self, pubkey: bytes) -> bool:
        return pubkey in self.keys


@dataclass(frozen=True)
class WitnessCosignature:
    """A single witness's contribution to a federated epoch quorum.

    `witness_id` is a human-readable label (e.g. the witness operator's
    domain name), kept as a tag for operator UIs; quorum verification
    only consults `witness_pubkey` + `signature`.
    """

    witness_id: str
    witness_pubkey: bytes
    signature: bytes


def build_witness_statement(epoch: MerkleEpoch) -> bytes:
    """Canonical bytes a witness signs to attest to an epoch.

    The statement binds the witness's signature to:
    - `epoch_id` (distinguishes adjacent epochs with similar shapes)
    - `first_seq` / `last_seq` / `tree_size` (cross-checks witness
      observed the same event log range)
    - `root_hash` (the actual Merkle commitment)
    - `sealed_at` (rejects re-anchor attempts under a forged timestamp)

    The fields are joined with the `0x1f` ASCII unit separator, then
    BLAKE2b-hashed under a domain-separation prefix so a witness
    signature cannot be replayed against a non-epoch payload.

    Args:
        epoch: The sealed `MerkleEpoch` row to be witnessed. `epoch_id`
            must be assigned (i.e. the epoch must have been persisted).

    Returns:
        The 32-byte BLAKE2b digest that witnesses sign over.

    Raises:
        WitnessError: If `epoch.epoch_id is None`.
    """
    if epoch.epoch_id is None:
        raise WitnessError("cannot witness an epoch with no epoch_id (was it persisted?)")
    return hash_blake2b(
        b"vacant:registry:epoch:witness"
        + b"\x1f"
        + int(epoch.epoch_id).to_bytes(8, "big")
        + b"\x1f"
        + int(epoch.first_seq).to_bytes(8, "big")
        + b"\x1f"
        + int(epoch.last_seq).to_bytes(8, "big")
        + b"\x1f"
        + int(epoch.tree_size).to_bytes(8, "big")
        + b"\x1f"
        + epoch.root_hash
        + b"\x1f"
        + int(epoch.sealed_at).to_bytes(8, "big")
    )


def issue_witness_cosignature(
    *,
    epoch: MerkleEpoch,
    witness_id: str,
    witness_signing_key: SigningKey,
    witness_pubkey: bytes,
) -> WitnessCosignature:
    """Helper for a witness operator: produce a cosignature on `epoch`.

    The witness is responsible for verifying that the epoch they're
    about to sign reflects the event-log range *they* independently
    observed; this function does not re-derive the Merkle root from
    primary data. (A witness backend would do that before calling us.)

    Args:
        epoch: The sealed epoch to cosign.
        witness_id: Witness operator label (free-form, e.g. domain name).
        witness_signing_key: Witness's Ed25519 private key.
        witness_pubkey: Raw 32-byte pubkey corresponding to
            `witness_signing_key`; we record this on the cosignature so
            verifiers can look up the witness in their `WitnessRootSet`
            without an extra round-trip.

    Returns:
        A `WitnessCosignature` ready to hand back to the registry.
    """
    statement = build_witness_statement(epoch)
    sig = sign(witness_signing_key, statement)
    return WitnessCosignature(
        witness_id=witness_id,
        witness_pubkey=witness_pubkey,
        signature=sig,
    )


def verify_witness_cosignature(
    *,
    epoch: MerkleEpoch,
    cosignature: WitnessCosignature,
) -> bool:
    """True iff `cosignature.signature` is a valid Ed25519 sig from
    `cosignature.witness_pubkey` over `build_witness_statement(epoch)`.

    Used internally by `verify_witness_quorum`; exposed because the RPC
    layer may want to validate a cosignature on arrival before
    persisting it to `EpochWitness`.
    """
    try:
        vk: VerifyKey = pubkey_from_bytes(cosignature.witness_pubkey)
    except Exception:
        return False
    return verify(vk, build_witness_statement(epoch), cosignature.signature)


def verify_witness_quorum(
    *,
    epoch: MerkleEpoch,
    cosignatures: Sequence[WitnessCosignature | EpochWitness],
    rootset: WitnessRootSet,
) -> bool:
    """True iff `cosignatures` contain ≥ `rootset.threshold` *distinct*
    valid signatures from witnesses in `rootset`.

    Args:
        epoch: The epoch being verified.
        cosignatures: Either `WitnessCosignature` dataclasses (in-memory
            path used by tests / RPC) or `EpochWitness` rows (DB path);
            both carry `witness_pubkey + signature` so we accept either.
        rootset: The witness root set against which to count distinct
            valid signers.

    Returns:
        `True` once `rootset.threshold` distinct keys from `rootset` have
        each validated; `False` otherwise. Signatures from keys not in
        `rootset` are silently ignored — a verifier who wants strict
        membership can pre-filter.

    Notes:
        Cross-witness signature replay is the failure mode this guards
        against. Each cosignature must verify against `cosignature.
        witness_pubkey`, and the same `witness_pubkey` only counts once
        toward quorum regardless of how many times it appears in the
        input.
    """
    statement = build_witness_statement(epoch)
    distinct: set[bytes] = set()
    for cos in cosignatures:
        pubkey = cos.witness_pubkey
        # `WitnessCosignature.signature` vs `EpochWitness.cosignature` —
        # accept either so callers can pass DB rows directly.
        sig = getattr(cos, "signature", None) or getattr(cos, "cosignature", None)
        if sig is None:
            continue
        if pubkey in distinct:
            continue
        if not rootset.contains(pubkey):
            continue
        try:
            vk = pubkey_from_bytes(pubkey)
        except Exception:  # noqa: S112 — malformed pubkey: drop this signer silently, the verifier ignores it
            continue
        if verify(vk, statement, sig):
            distinct.add(pubkey)
        if len(distinct) >= rootset.threshold:
            return True
    return False
