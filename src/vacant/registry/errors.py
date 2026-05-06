"""Error hierarchy for `vacant.registry`."""

from __future__ import annotations

from vacant.core.errors import CoreError


class RegistryError(CoreError):
    """Base class for `vacant.registry` errors."""


class RegistryWriteError(RegistryError):
    """A write violated an anti-tamper invariant before commit."""


class SignatureRejected(RegistryWriteError):
    """A submitted envelope's signature did not verify (anti-tamper L1)."""


class SequenceMonotonicityError(RegistryWriteError):
    """A submitted event's per-vacant sequence is not strictly greater than
    the last one (anti-tamper L2).
    """


class FreshnessError(RegistryWriteError):
    """An attestation is outside its freshness window (anti-tamper L3)."""


class IdempotencyConflict(RegistryWriteError):
    """The same `idempotency_key` was used with a *different* canonical
    payload hash (P4 §2.6 double-spend protection)."""


class VisibilityViolation(RegistryError):
    """A read attempt crossed a visibility boundary (e.g. stranger
    requesting a LOCAL vacant's halo)."""


class NotFoundError(RegistryError):
    """The requested record does not exist."""


class AppendOnlyViolation(RegistryWriteError):
    """A DELETE was attempted against an append-only table (anti-tamper L6)."""
