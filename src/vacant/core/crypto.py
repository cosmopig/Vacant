"""Pure crypto primitives used across the vacant stack.

Pure functions, no module-level mutable state, no global RNG. Ed25519 via
PyNaCl is the canonical implementation (CLAUDE.md §Tech stack). BLAKE2b-256
is the canonical hash (matches `LogEntry.prev_hash` and CapabilityCard
signing payloads).
"""

from __future__ import annotations

import hashlib

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

from vacant.core.constants import (
    ED25519_PUBLIC_KEY_BYTES,
    ED25519_SIGNATURE_BYTES,
    HASH_DIGEST_BYTES,
)
from vacant.core.errors import CryptoError, SignatureVerificationError

__all__ = [
    "SigningKey",
    "VerifyKey",
    "hash_blake2b",
    "hex_decode",
    "hex_encode",
    "keygen",
    "sign",
    "verify",
]


def keygen() -> tuple[SigningKey, VerifyKey]:
    """Generate a fresh Ed25519 keypair using the OS CSPRNG."""
    sk = SigningKey.generate()
    return sk, sk.verify_key


def sign(key: SigningKey, msg: bytes) -> bytes:
    """Detached Ed25519 signature over `msg` (returns 64 raw bytes)."""
    if not isinstance(msg, bytes | bytearray):
        raise CryptoError("sign(): msg must be bytes")
    sig: bytes = key.sign(bytes(msg)).signature
    return sig


def verify(pubkey: VerifyKey, msg: bytes, sig: bytes) -> bool:
    """True iff `sig` is a valid Ed25519 signature over `msg` for `pubkey`.

    Returns False on any malformed input rather than raising; callers that
    want to surface tampering as an exception should raise
    `SignatureVerificationError` themselves on the False branch.
    """
    if len(sig) != ED25519_SIGNATURE_BYTES:
        return False
    try:
        pubkey.verify(bytes(msg), bytes(sig))
    except BadSignatureError:
        return False
    except Exception:
        return False
    return True


def verify_or_raise(pubkey: VerifyKey, msg: bytes, sig: bytes) -> None:
    """Like `verify` but raises `SignatureVerificationError` on failure."""
    if not verify(pubkey, msg, sig):
        raise SignatureVerificationError("Ed25519 signature did not verify")


def hash_blake2b(data: bytes) -> bytes:
    """BLAKE2b digest truncated to `HASH_DIGEST_BYTES` (32 bytes)."""
    return hashlib.blake2b(bytes(data), digest_size=HASH_DIGEST_BYTES).digest()


def hex_encode(b: bytes) -> str:
    """Lowercase hex encode."""
    return bytes(b).hex()


def hex_decode(s: str) -> bytes:
    """Inverse of `hex_encode`. Raises `CryptoError` on malformed input."""
    try:
        return bytes.fromhex(s)
    except ValueError as exc:
        raise CryptoError(f"hex_decode(): not valid hex: {exc}") from exc


def pubkey_from_bytes(data: bytes) -> VerifyKey:
    """Construct a `VerifyKey` from raw 32-byte public-key material."""
    if len(data) != ED25519_PUBLIC_KEY_BYTES:
        raise CryptoError(
            f"pubkey_from_bytes(): expected {ED25519_PUBLIC_KEY_BYTES} bytes, got {len(data)}"
        )
    return VerifyKey(bytes(data))
