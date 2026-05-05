"""Runtime-module error hierarchy. Concrete errors added by P1."""

from __future__ import annotations

from vacant.core.errors import CoreError


class RuntimeError_(CoreError):
    """Base class for `vacant.runtime` errors.

    Suffix `_` avoids shadowing the built-in `RuntimeError`.
    """
