"""Base error hierarchy for shared core types and crypto primitives."""

from __future__ import annotations


class CoreError(Exception):
    """Base class for all errors raised from `vacant.core`."""


class CryptoError(CoreError):
    """Crypto primitive failure (keygen / sign / verify / hash)."""


class SignatureVerificationError(CryptoError):
    """A signature did not verify against the supplied public key + message."""


class HashChainError(CoreError):
    """A logbook entry's hash chain pointer did not match the expected previous hash."""


class TypeIntegrityError(CoreError):
    """A core BaseModel failed an internal self-consistency check."""
