"""Substrate-module error hierarchy."""

from __future__ import annotations

from vacant.core.errors import CoreError


class SubstrateError(CoreError):
    """Base class for `vacant.substrate` errors (backend / inference failures)."""
