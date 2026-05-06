"""`RegistryBackend` Protocol — the seam for swapping central → federated/DHT.

Acceptance criterion (dispatch §"Acceptance"): "Architected so the swap
from central → federated/DHT is local to one module (a `RegistryBackend`
Protocol)". This module declares the contract; `central.py` (mid-PR
class wired into `store.py`) implements it for SQLite. Federated and DHT
backends are post-MVP.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from vacant.registry.models import (
    Attestation,
    Event,
    MerkleEpoch,
    Vacant,
)

__all__ = ["RegistryBackend"]


class RegistryBackend(Protocol):
    """Storage contract every backend implementation honours.

    Methods are async; return types use SQLModel rows directly so the
    aggregation layer can index them without a translation step. A
    federated backend would implement the same interface using cross-shard
    reads + witness-verified writes (post-MVP).
    """

    async def init_schema(self) -> None: ...

    async def insert_vacant(self, vacant: Vacant) -> None: ...

    async def get_vacant(self, vacant_id: str) -> Vacant | None: ...

    async def update_vacant_status(self, vacant_id: str, status: str) -> None: ...

    async def update_vacant_visibility(self, vacant_id: str, visibility: str) -> None: ...

    async def insert_event(self, event: Event) -> int: ...

    """Append an event; returns the assigned `seq`."""

    async def latest_event_for_actor(self, actor_vacant_id: str) -> Event | None: ...

    async def latest_event_overall(self) -> Event | None: ...

    async def insert_attestation(self, attestation: Attestation) -> None: ...

    async def list_attestations(self, vacant_id: str) -> Sequence[Attestation]: ...

    async def insert_merkle_epoch(self, epoch: MerkleEpoch) -> int: ...

    async def get_merkle_epoch(self, epoch_id: int) -> MerkleEpoch | None: ...

    async def latest_merkle_epoch(self) -> MerkleEpoch | None: ...

    async def list_unsealed_events(self) -> Sequence[Event]: ...

    async def assign_events_to_epoch(self, seqs: Sequence[int], epoch_id: int) -> None: ...

    async def lookup_idempotency(self, idempotency_key: str) -> Event | None: ...

    async def list_descendants(self, vacant_id: str, *, max_depth: int = 8) -> Sequence[Vacant]: ...

    async def list_ancestors(self, vacant_id: str, *, max_depth: int = 8) -> Sequence[Vacant]: ...

    async def search_capability(
        self,
        *,
        capability: str | None,
        family: str | None,
        status: str | None,
        visibility: str | None,
        limit: int,
    ) -> Sequence[Vacant]: ...
