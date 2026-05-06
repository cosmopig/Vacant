"""Capability card serialization + halo_version forward-compat gate.

`serialize` / `deserialize` produce / consume canonical JSON for halo
emission. Both halt loudly via `UnsupportedHaloVersionError` when a
deserialized card carries a halo_version this build does not recognise
— this is the forward-compat hook for future halo schema upgrades.
"""

from __future__ import annotations

import json
from typing import Any

from vacant.core.constants import DEFAULT_HALO_VERSION
from vacant.core.types import CapabilityCard, SubstrateSpec, VacantId
from vacant.protocol.errors import (
    EnvelopeFormatError,
    UnsupportedHaloVersionError,
)

__all__ = [
    "MAX_SUPPORTED_HALO_VERSION",
    "MIN_SUPPORTED_HALO_VERSION",
    "deserialize",
    "serialize",
]


MIN_SUPPORTED_HALO_VERSION = DEFAULT_HALO_VERSION  # = 1
MAX_SUPPORTED_HALO_VERSION = DEFAULT_HALO_VERSION  # bumped when a new halo schema lands


def _to_dict(card: CapabilityCard) -> dict[str, Any]:
    return {
        "vacant_id": card.vacant_id.hex(),
        "capability_text": card.capability_text,
        "substrate_spec": {
            "allowed_substrates": list(card.substrate_spec.allowed_substrates),
            "policy": card.substrate_spec.policy,
        },
        "halo_version": card.halo_version,
        "endpoint": card.endpoint,
        "signature": card.signature.hex(),
    }


def serialize(card: CapabilityCard) -> bytes:
    """Canonical JSON bytes for `card`. Sorted keys + tight separators
    so the same card always serialises to identical bytes (cross-check
    against `card.signing_payload()` for signature stability)."""
    return json.dumps(
        _to_dict(card), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def deserialize(blob: bytes) -> CapabilityCard:
    """Inverse of `serialize`. Raises:

    - `UnsupportedHaloVersionError` if `halo_version` is outside the
      `[MIN, MAX]` supported range.
    - `EnvelopeFormatError` on shape / decode errors.
    """
    try:
        obj = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EnvelopeFormatError(f"capability card not valid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise EnvelopeFormatError("capability card must be a JSON object")
    try:
        version = int(obj.get("halo_version", DEFAULT_HALO_VERSION))
    except (ValueError, TypeError) as exc:
        raise EnvelopeFormatError(
            f"capability card halo_version must be int; got {obj.get('halo_version')!r}"
        ) from exc
    if not (MIN_SUPPORTED_HALO_VERSION <= version <= MAX_SUPPORTED_HALO_VERSION):
        raise UnsupportedHaloVersionError(
            f"halo_version {version} not in [{MIN_SUPPORTED_HALO_VERSION}, "
            f"{MAX_SUPPORTED_HALO_VERSION}]"
        )
    try:
        spec = obj.get("substrate_spec", {}) or {}
        substrate_spec = SubstrateSpec(
            allowed_substrates=list(spec.get("allowed_substrates", [])),
            policy=dict(spec.get("policy", {})),
        )
        return CapabilityCard(
            vacant_id=VacantId(pubkey_bytes=bytes.fromhex(obj["vacant_id"])),
            capability_text=str(obj["capability_text"]),
            substrate_spec=substrate_spec,
            halo_version=version,
            endpoint=obj.get("endpoint"),
            signature=bytes.fromhex(obj.get("signature", "")),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise EnvelopeFormatError(f"invalid capability card: {exc}") from exc
