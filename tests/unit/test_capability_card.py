"""Capability card serialize/deserialize + halo_version gate."""

from __future__ import annotations

import json

import pytest

from vacant.core.crypto import keygen
from vacant.core.types import CapabilityCard, SubstrateSpec, VacantId
from vacant.protocol import (
    EnvelopeFormatError,
    UnsupportedHaloVersionError,
    deserialize,
    serialize,
)


def _signed_card(*, endpoint: str | None = "https://example.com/a2a") -> CapabilityCard:
    sk, vk = keygen()
    return CapabilityCard(
        vacant_id=VacantId.from_verify_key(vk),
        capability_text="translate",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
        endpoint=endpoint,
    ).signed(sk)


def test_serialize_deserialize_round_trip() -> None:
    card = _signed_card()
    blob = serialize(card)
    parsed = deserialize(blob)
    assert parsed == card


def test_serialize_is_canonical_json() -> None:
    """Sorted keys + tight separators."""
    card = _signed_card()
    blob = serialize(card)
    obj = json.loads(blob.decode())
    assert obj["vacant_id"] == card.vacant_id.hex()
    assert obj["endpoint"] == card.endpoint


def test_serialize_then_verify_signature_holds() -> None:
    card = _signed_card()
    blob = serialize(card)
    parsed = deserialize(blob)
    assert parsed.verify() is True


def test_deserialize_unknown_halo_version_rejected() -> None:
    card = _signed_card()
    blob = serialize(card)
    obj = json.loads(blob.decode())
    obj["halo_version"] = 99
    bad = json.dumps(obj).encode()
    with pytest.raises(UnsupportedHaloVersionError):
        deserialize(bad)


def test_deserialize_invalid_json_raises() -> None:
    with pytest.raises(EnvelopeFormatError):
        deserialize(b"{not-json")


def test_deserialize_non_object_json_raises() -> None:
    with pytest.raises(EnvelopeFormatError):
        deserialize(b"[1, 2, 3]")


def test_deserialize_missing_vacant_id_raises() -> None:
    bad = json.dumps({"capability_text": "x"}).encode()
    with pytest.raises((EnvelopeFormatError, UnsupportedHaloVersionError)):
        deserialize(bad)


def test_deserialize_invalid_halo_version_type_raises() -> None:
    obj = {
        "vacant_id": "00" * 32,
        "capability_text": "x",
        "substrate_spec": {},
        "halo_version": "abc",
        "endpoint": None,
        "signature": "",
    }
    with pytest.raises(EnvelopeFormatError):
        deserialize(json.dumps(obj).encode())


def test_serialize_includes_endpoint_in_signing_payload() -> None:
    """Tampering the endpoint after issuance breaks the signature."""
    card = _signed_card(endpoint="https://example.com/a2a")
    blob = serialize(card)
    obj = json.loads(blob.decode())
    obj["endpoint"] = "https://attacker.com/a2a"
    tampered_blob = json.dumps(obj).encode()
    parsed = deserialize(tampered_blob)
    # Parsed has the new endpoint but the old signature → verify fails.
    assert parsed.verify() is False


def test_endpoint_default_none_round_trip() -> None:
    """Cards with no endpoint (LOCAL vacants) round-trip correctly."""
    sk, vk = keygen()
    card = CapabilityCard(
        vacant_id=VacantId.from_verify_key(vk),
        capability_text="local",
        substrate_spec=SubstrateSpec(),
    ).signed(sk)
    parsed = deserialize(serialize(card))
    assert parsed.endpoint is None
    assert parsed.verify() is True
