"""Registry-module error hierarchy. Concrete errors added by P4."""

from __future__ import annotations

from vacant.core.errors import CoreError


class RegistryError(CoreError):
    """Base class for `vacant.registry` errors."""
