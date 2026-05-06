"""Substrate-module error hierarchy."""

from __future__ import annotations

from vacant.core.errors import CoreError


class SubstrateError(CoreError):
    """Base class for `vacant.substrate` errors (backend / inference failures)."""


class SubstrateUnavailableError(SubstrateError):
    """The substrate backend cannot be reached (missing SDK, missing API
    key, no network)."""


class SubstrateRateLimitError(SubstrateError):
    """The substrate backend rejected with rate-limit; retries exhausted."""
