"""Protocol-module error hierarchy. Concrete errors added by P6."""

from __future__ import annotations

from vacant.core.errors import CoreError


class ProtocolError(CoreError):
    """Base class for `vacant.protocol` errors."""
