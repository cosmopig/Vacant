"""Composite-module error hierarchy. Concrete errors added by P5."""

from __future__ import annotations

from vacant.core.errors import CoreError


class CompositeError(CoreError):
    """Base class for `vacant.composite` errors."""
