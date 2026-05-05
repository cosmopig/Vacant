"""L0-L3 layered identity (P2 §2 / dispatch §2).

Distinct frozen Pydantic types — *not* a class hierarchy — so that a
function annotated `f(x: L3Identity)` rejects an `L1Identity` at type-check
time. Promotion is one-way and explicit:

```
L0Identity → L1Identity → L2Identity → L3Identity
            (logbook)    (cap card)    (>= N peer attestations)
```

Each promotion verifies the relevant invariants and raises
`LayerPromotionError` with a precise message on failure. There is no
implicit downgrade — once you have an `L2Identity`, the corresponding
logbook is known-good, and callers can rely on that without re-checking.

The `did:key` textual form (§3.1) is exposed via `vacant_id_did_key` so
downstream code that emits attestations / capability cards can produce
the W3C `did:key:z…` string without re-implementing multibase encoding.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from vacant.core.constants import (
    ED25519_MULTICODEC_PREFIX,
    MIN_VOUCHERS_FOR_L3_PROMOTION,
)
from vacant.core.types import CapabilityCard, Logbook, VacantId
from vacant.identity.errors import LayerPromotionError

if TYPE_CHECKING:
    from vacant.identity.attestation import PeerAttestation

__all__ = [
    "L0Identity",
    "L1Identity",
    "L2Identity",
    "L3Identity",
    "promote_to_l1",
    "promote_to_l2",
    "promote_to_l3",
    "vacant_id_did_key",
]


def vacant_id_did_key(vid: VacantId) -> str:
    """Return the `did:key:z…` form of `vid` (W3C did:key §6.1).

    Encoding: multibase58btc(`0xed01` || pubkey_bytes), prefixed `did:key:`.
    Uses standard Bitcoin Base58 with the `z` multibase prefix.
    """
    payload = ED25519_MULTICODEC_PREFIX + vid.pubkey_bytes
    return f"did:key:z{_b58encode(payload)}"


# Bitcoin Base58 alphabet (Satoshi 2009; Wikipedia "Base58Check encoding").
_B58_ALPHABET: Final[str] = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _b58encode(data: bytes) -> str:
    n = int.from_bytes(data, "big")
    out: list[str] = []
    while n > 0:
        n, r = divmod(n, 58)
        out.append(_B58_ALPHABET[r])
    # Preserve leading zero bytes as leading '1's (per Base58Check).
    leading = len(data) - len(data.lstrip(b"\x00"))
    return "1" * leading + "".join(reversed(out))


# --- Layer types -------------------------------------------------------------


@dataclass(frozen=True)
class L0Identity:
    """Just a `VacantId` — the bare keypair, no logbook checked yet."""

    vacant_id: VacantId

    def did(self) -> str:
        return vacant_id_did_key(self.vacant_id)


@dataclass(frozen=True)
class L1Identity:
    """`L0` + a logbook whose hash chain + signatures verify against `vacant_id`."""

    vacant_id: VacantId
    logbook: Logbook

    def did(self) -> str:
        return vacant_id_did_key(self.vacant_id)


@dataclass(frozen=True)
class L2Identity:
    """`L1` + a `CapabilityCard` whose `vacant_id` matches and whose
    signature verifies against the same key.
    """

    vacant_id: VacantId
    logbook: Logbook
    capability_card: CapabilityCard

    def did(self) -> str:
        return vacant_id_did_key(self.vacant_id)


@dataclass(frozen=True)
class L3Identity:
    """`L2` + at least `MIN_VOUCHERS_FOR_L3_PROMOTION` peer attestations.

    Attestations are stored as a tuple so the type stays hashable / frozen;
    the actual `PeerAttestation` model lives in `identity.attestation`.
    """

    vacant_id: VacantId
    logbook: Logbook
    capability_card: CapabilityCard
    attestations: tuple[object, ...]
    """Tuple of `PeerAttestation` (kept as `object` to avoid an import cycle;
    `promote_to_l3` validates the concrete type at runtime)."""

    def did(self) -> str:
        return vacant_id_did_key(self.vacant_id)


# --- Promotions --------------------------------------------------------------


def promote_to_l1(l0: L0Identity, logbook: Logbook) -> L1Identity:
    """Verify the logbook chain + signatures against `l0.vacant_id` and
    return an `L1Identity`. Raises `LayerPromotionError` on failure.
    """
    pubkey = l0.vacant_id.verify_key()
    if not logbook.verify_chain(pubkey):
        raise LayerPromotionError(
            f"L0 → L1: logbook chain does not verify against {l0.vacant_id.short()}"
        )
    return L1Identity(vacant_id=l0.vacant_id, logbook=logbook)


def promote_to_l2(l1: L1Identity, capability_card: CapabilityCard) -> L2Identity:
    """Verify the capability card belongs to the L1 identity and is
    self-signed; return an `L2Identity`.
    """
    if capability_card.vacant_id != l1.vacant_id:
        raise LayerPromotionError(
            f"L1 → L2: capability_card.vacant_id {capability_card.vacant_id} "
            f"does not match L1 vacant_id {l1.vacant_id}"
        )
    if not capability_card.verify():
        raise LayerPromotionError("L1 → L2: capability_card signature does not verify")
    return L2Identity(
        vacant_id=l1.vacant_id,
        logbook=l1.logbook,
        capability_card=capability_card,
    )


def promote_to_l3(
    l2: L2Identity,
    attestations: object,
    *,
    min_vouchers: int = MIN_VOUCHERS_FOR_L3_PROMOTION,
) -> L3Identity:
    """Verify enough peer attestations name this vacant and return `L3`.

    `attestations` is taken as `object` to avoid an import cycle with
    `identity.attestation`; `_validate_attestations` checks the concrete
    type at runtime. Each attestation is verified for: (a) `attestee` ==
    `l2.vacant_id`, (b) signature against `attester` pubkey, (c) freshness
    window (not expired). Distinct attesters are required — N copies from
    one attester count as one.
    """
    valid = _validate_attestations(attestations, attestee=l2.vacant_id)
    distinct_attesters = {a.attester for a in valid}
    if len(distinct_attesters) < min_vouchers:
        raise LayerPromotionError(
            f"L2 → L3: have {len(distinct_attesters)} distinct valid attesters, need {min_vouchers}"
        )
    return L3Identity(
        vacant_id=l2.vacant_id,
        logbook=l2.logbook,
        capability_card=l2.capability_card,
        attestations=tuple(valid),
    )


def _validate_attestations(
    attestations: object,
    *,
    attestee: VacantId,
) -> list[PeerAttestation]:
    """Runtime validator for the `object`-typed attestations parameter."""
    from vacant.identity.attestation import (
        PeerAttestation as _PeerAttestation,
    )
    from vacant.identity.attestation import (
        verify_attestation,
    )

    if not isinstance(attestations, list | tuple):
        raise LayerPromotionError(
            "L2 → L3: attestations must be a list or tuple of PeerAttestation"
        )
    valid: list[PeerAttestation] = []
    for i, item in enumerate(attestations):
        if not isinstance(item, _PeerAttestation):
            raise LayerPromotionError(f"L2 → L3: attestations[{i}] is not a PeerAttestation")
        if item.attestee != attestee:
            raise LayerPromotionError(f"L2 → L3: attestations[{i}].attestee != {attestee}")
        if not verify_attestation(item):
            raise LayerPromotionError(
                f"L2 → L3: attestations[{i}] failed signature/freshness check"
            )
        valid.append(item)
    return valid


# Re-export for callers that want the multibase encoder directly (tests).
b58encode = _b58encode
