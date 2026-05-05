"""Logbook persistence interface (P1) + in-memory impl.

P1's `RuntimeLoop` is wired through this `LogbookStore` Protocol so P4 can
later swap in the SQLite-backed implementation without touching runtime
code. The in-memory impl provided here is enough for unit + integration
tests and the P7 demo dashboard.
"""

from __future__ import annotations

from typing import Protocol

from vacant.core.types import Logbook, VacantId

__all__ = ["InMemoryLogbookStore", "LogbookStore"]


class LogbookStore(Protocol):
    """Async key-value persistence over `(VacantId, Logbook)`."""

    async def load(self, vid: VacantId) -> Logbook | None: ...

    async def save(self, vid: VacantId, logbook: Logbook) -> None: ...

    async def has(self, vid: VacantId) -> bool: ...


class InMemoryLogbookStore:
    """Reference impl backed by a plain dict. Not thread-safe; intended for
    single-process tests and demos.
    """

    def __init__(self) -> None:
        self._data: dict[VacantId, Logbook] = {}

    async def load(self, vid: VacantId) -> Logbook | None:
        return self._data.get(vid)

    async def save(self, vid: VacantId, logbook: Logbook) -> None:
        self._data[vid] = logbook

    async def has(self, vid: VacantId) -> bool:
        return vid in self._data

    def __len__(self) -> int:
        return len(self._data)
