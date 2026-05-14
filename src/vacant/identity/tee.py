"""TEE-anchored L3 identity attestation (technical.html §Identity: L0-L3
Layering, L3 = TEE).

The standard L3 promotion (`identity.layers.promote_to_l3`) collects
peer attestations until `MIN_VOUCHERS_FOR_L3_PROMOTION` distinct peers
vouch. This module adds a second L3 path: a *Trusted Execution
Environment* attestation. A TEE provider (Intel SGX, AMD SEV, AWS
Nitro, Apple Secure Enclave, etc.) signs a measurement of the code +
hardware that holds the vacant's signing key, plus the pubkey itself,
binding the keypair to a specific isolated environment.

What this module gives you:

- `TEEAttestation` — a typed, signed envelope carrying:
  - `vendor` (sgx / sev / nitro / apple / mock)
  - `measurement` (32-byte hash of the enclave's code/firmware)
  - `enclave_pubkey` (the TEE-attesting key — distinct from the
    vacant's keypair)
  - `signature` (vendor signature over the canonical signing payload)
- `verify_tee_attestation(...)` — pluggable verifier:
  - For `mock`: Ed25519 verification against `enclave_pubkey`.
  - For real vendors: returns `False` unless the operator supplies a
    `VerifierRegistry` mapping `vendor → verifier_callable`.
- `L3TEEIdentity` — `L2Identity` + a verified `TEEAttestation`. Distinct
  type from `L3Identity` so mypy can enforce policy decisions like
  "this code path only accepts TEE-anchored vacants".
- `promote_to_l3_tee(l2, attestation, *, verifiers=...)` — the
  promotion gate.

Design constraints:

- **Vendor-specific verifiers are pluggable, not hardcoded.** We don't
  ship real Intel SGX quote verification because that pulls in massive
  vendor SDKs; operators wire their own.
- **The mock vendor is for tests + dev.** It does a plain Ed25519
  verification — sufficient to prove the type wiring is correct.
- **TEE attestation does NOT replace peer attestations.** It augments
  them: a malicious TEE provider is still possible, just expensive.
  Real deployments combine both paths.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from vacant.core.crypto import SigningKey, VerifyKey, hash_blake2b, pubkey_from_bytes, sign, verify
from vacant.core.types import CapabilityCard, Logbook, VacantId
from vacant.identity.errors import LayerPromotionError
from vacant.identity.layers import L2Identity, vacant_id_did_key

__all__ = [
    "MOCK_TEE_VENDOR",
    "L3TEEIdentity",
    "TEEAttestation",
    "TEEVendor",
    "TEEVerifierRegistry",
    "issue_tee_attestation_mock",
    "promote_to_l3_tee",
    "verify_tee_attestation",
]


class TEEVendor(StrEnum):
    """Known TEE attestation providers.

    `MOCK` exists for tests + offline dev; real deployments stick to
    the vendor-specific values. The enum is `str`-typed so attestations
    serialise cleanly to JSON without an enum-encoding step.
    """

    MOCK = "mock"
    SGX = "sgx"
    SEV = "sev"
    NITRO = "nitro"
    APPLE_SE = "apple_se"


MOCK_TEE_VENDOR = TEEVendor.MOCK
"""Convenience alias for the mock vendor used in unit tests."""


class TEEAttestation(BaseModel):
    """A signed TEE attestation binding `vacant_id` to a measured enclave.

    Attributes:
        vacant_id: The vacant being attested.
        vendor: Which TEE provider issued the attestation.
        measurement: 32-byte hash of the enclave's code/firmware. For
            SGX this would be MRENCLAVE; for SEV the launch measurement;
            for the mock vendor any 32 bytes.
        enclave_pubkey: The TEE's attestation key (raw 32-byte Ed25519
            pubkey). Distinct from `vacant_id`'s own pubkey — the TEE
            vouches that it generated the vacant's key inside the
            measured enclave.
        valid_from_ms / valid_until_ms: Optional freshness window in
            ms-since-epoch.
        signature: Ed25519 signature by `enclave_pubkey` over
            `signing_payload()`. For real vendors this would be a
            full quote / SEV report; for the mock vendor a plain
            Ed25519 sig.

    The signing payload is domain-separated with `vacant:tee:l3:` so a
    sig collected for a TEE attestation cannot be replayed against a
    different envelope shape with the same fields.
    """

    model_config = ConfigDict(frozen=True)

    vacant_id: VacantId
    vendor: TEEVendor
    measurement: bytes = Field(min_length=32, max_length=32)
    enclave_pubkey: bytes = Field(min_length=32, max_length=32)
    valid_from_ms: int = 0
    valid_until_ms: int | None = None
    signature: bytes = b""

    def signing_payload(self) -> bytes:
        """Canonical bytes the vendor signs.

        Includes every field except `signature` so a verifier can
        recompute the exact bytes and check the signature.
        """
        return hash_blake2b(
            b"vacant:tee:l3"
            + b"\x1f"
            + self.vacant_id.pubkey_bytes
            + b"\x1f"
            + self.vendor.value.encode("utf-8")
            + b"\x1f"
            + self.measurement
            + b"\x1f"
            + self.enclave_pubkey
            + b"\x1f"
            + str(self.valid_from_ms).encode("utf-8")
            + b"\x1f"
            + str(self.valid_until_ms if self.valid_until_ms is not None else "").encode("utf-8")
        )


TEEVerifier = Callable[[TEEAttestation], bool]
"""Vendor-specific verifier function. Returns True iff the attestation
is genuine for that vendor."""


@dataclass(frozen=True)
class TEEVerifierRegistry:
    """Operator-supplied mapping `vendor → verifier`.

    `verify_tee_attestation` consults this registry first; the built-in
    `MOCK` verifier (Ed25519 over `signing_payload()`) is appended as
    a fallback so tests work without configuring anything.
    """

    verifiers: dict[TEEVendor, TEEVerifier]

    def get(self, vendor: TEEVendor) -> TEEVerifier | None:
        return self.verifiers.get(vendor)

    @classmethod
    def empty(cls) -> TEEVerifierRegistry:
        return cls(verifiers={})


def _verify_mock(att: TEEAttestation) -> bool:
    """Built-in verifier for `TEEVendor.MOCK` — plain Ed25519.

    Sufficient to exercise the type wiring; production should use a
    real vendor verifier from `TEEVerifierRegistry`.
    """
    try:
        vk: VerifyKey = pubkey_from_bytes(att.enclave_pubkey)
    except Exception:
        return False
    if not att.signature:
        return False
    return verify(vk, att.signing_payload(), att.signature)


def verify_tee_attestation(
    att: TEEAttestation,
    *,
    registry: TEEVerifierRegistry | None = None,
    now_ms: int | None = None,
) -> bool:
    """Verify `att` against the appropriate vendor verifier.

    Routing:
    1. If `registry` has a verifier for `att.vendor`, use it.
    2. Else, if `att.vendor == MOCK`, use `_verify_mock`.
    3. Else, return False — we don't ship hardcoded vendor SDKs.

    Freshness window is checked here too: an attestation outside
    `[valid_from_ms, valid_until_ms]` fails regardless of signature.
    """
    if now_ms is not None:
        if now_ms < att.valid_from_ms:
            return False
        if att.valid_until_ms is not None and now_ms > att.valid_until_ms:
            return False
    if registry is not None:
        v = registry.get(att.vendor)
        if v is not None:
            return v(att)
    if att.vendor is TEEVendor.MOCK:
        return _verify_mock(att)
    return False


def issue_tee_attestation_mock(
    *,
    vacant_id: VacantId,
    enclave_signing_key: SigningKey,
    enclave_pubkey: bytes,
    measurement: bytes,
    valid_from_ms: int = 0,
    valid_until_ms: int | None = None,
) -> TEEAttestation:
    """Helper for tests + scenarios: produce a signed `TEEAttestation`
    in the `MOCK` vendor space.

    A real vendor would have its own attestation issuance flow (SGX
    quote generation, SEV report fetch, etc.); the mock vendor uses
    Ed25519 so we can exercise the type wiring without a real TEE.
    """
    base = TEEAttestation(
        vacant_id=vacant_id,
        vendor=TEEVendor.MOCK,
        measurement=measurement,
        enclave_pubkey=enclave_pubkey,
        valid_from_ms=valid_from_ms,
        valid_until_ms=valid_until_ms,
        signature=b"",
    )
    sig = sign(enclave_signing_key, base.signing_payload())
    return base.model_copy(update={"signature": sig})


@dataclass(frozen=True)
class L3TEEIdentity:
    """`L2` + a verified `TEEAttestation`.

    Distinct from `L3Identity` (peer-attestation L3) so functions that
    require a TEE-anchored vacant (e.g. high-stakes routing) can ask
    for `L3TEEIdentity` at the type level rather than runtime-checking.
    Both L3 paths can coexist for the same vacant.
    """

    vacant_id: VacantId
    logbook: Logbook
    capability_card: CapabilityCard
    tee_attestation: TEEAttestation

    def did(self) -> str:
        return vacant_id_did_key(self.vacant_id)


def promote_to_l3_tee(
    l2: L2Identity,
    attestation: TEEAttestation,
    *,
    verifiers: TEEVerifierRegistry | None = None,
    now_ms: int | None = None,
) -> L3TEEIdentity:
    """Promote `l2` to L3 via TEE attestation.

    Validates:
    - `attestation.vacant_id == l2.vacant_id` (no cross-vacant
      attestation injection)
    - `verify_tee_attestation(attestation)` returns True

    Raises `LayerPromotionError` with a precise message on failure.
    """
    if attestation.vacant_id != l2.vacant_id:
        raise LayerPromotionError(
            f"L2 → L3-TEE: attestation.vacant_id {attestation.vacant_id} "
            f"does not match L2 vacant_id {l2.vacant_id}"
        )
    if not verify_tee_attestation(attestation, registry=verifiers, now_ms=now_ms):
        raise LayerPromotionError(
            f"L2 → L3-TEE: TEE attestation for vendor {attestation.vendor.value} "
            "did not verify (signature/freshness/vendor)"
        )
    return L3TEEIdentity(
        vacant_id=l2.vacant_id,
        logbook=l2.logbook,
        capability_card=l2.capability_card,
        tee_attestation=attestation,
    )
