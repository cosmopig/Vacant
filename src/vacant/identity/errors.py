"""Identity-module error hierarchy. Concrete errors added by P2."""

from __future__ import annotations

from vacant.core.errors import CoreError


class IdentityError(CoreError):
    """Base class for `vacant.identity` errors."""
