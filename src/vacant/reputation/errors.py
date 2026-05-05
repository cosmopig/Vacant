"""Reputation-module error hierarchy. Concrete errors added by P3."""

from __future__ import annotations

from vacant.core.errors import CoreError


class ReputationError(CoreError):
    """Base class for `vacant.reputation` errors."""
