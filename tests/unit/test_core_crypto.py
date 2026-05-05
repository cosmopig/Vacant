"""Unit tests for `vacant.core.crypto`."""

from __future__ import annotations

import pytest

from vacant.core.constants import ED25519_SIGNATURE_BYTES, HASH_DIGEST_BYTES
from vacant.core.crypto import (
    SigningKey,
    VerifyKey,
    hash_blake2b,
    hex_decode,
    hex_encode,
    keygen,
    pubkey_from_bytes,
    sign,
    verify,
    verify_or_raise,
)
from vacant.core.errors import CryptoError, SignatureVerificationError


def test_keygen_returns_distinct_pair() -> None:
    sk1, vk1 = keygen()
    _sk2, vk2 = keygen()
    assert isinstance(sk1, SigningKey)
    assert isinstance(vk1, VerifyKey)
    assert bytes(vk1) != bytes(vk2)


def test_sign_verify_roundtrip(test_keypair: tuple[SigningKey, VerifyKey]) -> None:
    sk, vk = test_keypair
    msg = b"vacant test message"
    sig = sign(sk, msg)
    assert len(sig) == ED25519_SIGNATURE_BYTES
    assert verify(vk, msg, sig) is True


def test_verify_rejects_wrong_message(test_keypair: tuple[SigningKey, VerifyKey]) -> None:
    sk, vk = test_keypair
    sig = sign(sk, b"original")
    assert verify(vk, b"tampered", sig) is False


def test_verify_rejects_wrong_pubkey(test_keypair: tuple[SigningKey, VerifyKey]) -> None:
    sk, _vk = test_keypair
    _sk2, vk2 = keygen()
    sig = sign(sk, b"hello")
    assert verify(vk2, b"hello", sig) is False


def test_verify_rejects_wrong_length_sig(test_keypair: tuple[SigningKey, VerifyKey]) -> None:
    _sk, vk = test_keypair
    assert verify(vk, b"hello", b"too short") is False


def test_verify_or_raise_raises_on_bad_sig(
    test_keypair: tuple[SigningKey, VerifyKey],
) -> None:
    _sk, vk = test_keypair
    with pytest.raises(SignatureVerificationError):
        verify_or_raise(vk, b"x", b"\x00" * ED25519_SIGNATURE_BYTES)


def test_sign_rejects_non_bytes(test_keypair: tuple[SigningKey, VerifyKey]) -> None:
    sk, _vk = test_keypair
    with pytest.raises(CryptoError):
        sign(sk, "not bytes")  # type: ignore[arg-type]


def test_hash_blake2b_is_deterministic() -> None:
    a = hash_blake2b(b"abc")
    b = hash_blake2b(b"abc")
    assert a == b
    assert len(a) == HASH_DIGEST_BYTES


def test_hash_blake2b_changes_on_input_change() -> None:
    assert hash_blake2b(b"abc") != hash_blake2b(b"abd")


def test_hex_encode_decode_roundtrip() -> None:
    data = b"\x00\x01\xfe\xff hello"
    assert hex_decode(hex_encode(data)) == data


def test_hex_decode_rejects_garbage() -> None:
    with pytest.raises(CryptoError):
        hex_decode("zz")


def test_pubkey_from_bytes_rejects_wrong_length() -> None:
    with pytest.raises(CryptoError):
        pubkey_from_bytes(b"too short")


def test_pubkey_from_bytes_roundtrip(test_keypair: tuple[SigningKey, VerifyKey]) -> None:
    _sk, vk = test_keypair
    vk2 = pubkey_from_bytes(bytes(vk))
    assert bytes(vk2) == bytes(vk)
