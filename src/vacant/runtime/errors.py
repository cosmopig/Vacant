"""Error hierarchy for `vacant.runtime`."""

from __future__ import annotations

from vacant.core.errors import CoreError


class RuntimeError_(CoreError):
    """Base class for `vacant.runtime` errors.

    Suffix `_` avoids shadowing the built-in `RuntimeError`.
    """


class InvalidEventError(RuntimeError_):
    """An `Event` was applied to a `VacantState` that does not accept it.

    Example: `CALL_RECEIVED` while in `SUNK`. The state machine does not
    silently no-op these — they signal a programming bug or a request that
    should have been rejected upstream (P6 envelope checks, §3.2).
    """


class SpawnError(RuntimeError_):
    """A spawn (D1-D5) operation could not satisfy its preconditions."""


class ConsentError(SpawnError):
    """A multi-parent spawn (D4) was missing or had an invalid parent consent."""
