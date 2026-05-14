"""Federated `RegistryBackend` (technical.html §Roadmap: "Federated").

The central-MVP `RegistryStore` (`store.py`) trusts a single SQLite
database. A federated deployment runs N peer registries that each
maintain their own copy of the event log; reads are accepted only when
≥ M peers agree on the data being returned.

This module wires that pattern onto the existing `RegistryBackend`
Protocol — every reader operation becomes an M-of-N quorum query
across the configured peers. It is intentionally *read-only* (writes
remain the operator's responsibility on each peer's primary store;
cross-peer write replication is post-MVP).

Three building blocks:

1. `FederatedRegistryBackend(peers, threshold)` — implements the read
   half of `RegistryBackend.Protocol` by fan-out + quorum-of-M.
2. `QuorumDisagreement` — raised when fewer than `threshold` peers
   agree on the returned shape. Surfaces the discrepancy so the
   operator can investigate (one of the peers is lying or out of date).
3. `RecordHash` — deterministic content hash for the rows the
   federated layer queries; "agreement" means same hash from M peers.

Why a separate backend rather than burying federation inside
`RegistryStore`? The CLAUDE.md acceptance criterion is explicit:
"Architected so the swap from central → federated/DHT is local to one
module". This module is exactly that swap; the rest of the system
keeps treating the registry as a single object.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from vacant.core.crypto import hash_blake2b
from vacant.registry.backend import RegistryBackend
from vacant.registry.errors import RegistryError
from vacant.registry.models import (
    Attestation,
    Event,
    MerkleEpoch,
    Vacant,
)

__all__ = [
    "FederatedRegistryBackend",
    "QuorumDisagreement",
    "record_hash",
]


class QuorumDisagreement(RegistryError):
    """Raised when fewer than `threshold` peers returned the same answer.

    The exception carries the per-peer result hashes so an operator can
    diagnose which peer is divergent. It is intentionally typed under
    `RegistryError` (not `RegistryWriteError`) because federation
    failures don't imply a write-integrity violation on any specific
    peer — they imply *inconsistency* between peers.
    """

    def __init__(self, message: str, *, observed: dict[bytes, int] | None = None) -> None:
        super().__init__(message)
        self.observed = observed or {}


# --- canonicalisation --------------------------------------------------------


def _vacant_hash(v: Vacant | None) -> bytes:
    """Deterministic hash for a `Vacant` row.

    `None` produces a sentinel hash so "peer A says it exists, peer B
    says it doesn't" is just another disagreement — handled uniformly
    by `_quorum_or_raise`.
    """
    if v is None:
        return b"\x00" * 32
    blob = b"\x1f".join(
        [
            v.vacant_id.encode("utf-8"),
            v.public_key,
            v.capability_card_hash,
            v.capability_card_sig,
            v.status.encode("utf-8"),
            v.visibility.encode("utf-8"),
            str(v.latest_event_seq).encode("utf-8"),
        ]
    )
    return hash_blake2b(blob)


def _event_hash(e: Event | None) -> bytes:
    if e is None:
        return b"\x00" * 32
    # The event's own `event_hash` is already a chain-bound digest;
    # using it directly means two peers agree iff they hold the same
    # event row.
    return e.event_hash


def _epoch_hash(epoch: MerkleEpoch | None) -> bytes:
    if epoch is None:
        return b"\x00" * 32
    # Bind to the operator signature so a divergent peer (e.g. a
    # malicious one re-signing the same root with a different key)
    # produces a distinct hash.
    return hash_blake2b(
        b"epoch"
        + b"\x1f"
        + (str(epoch.epoch_id or 0)).encode("utf-8")
        + b"\x1f"
        + epoch.root_hash
        + b"\x1f"
        + epoch.registry_signature
    )


def _attestation_hash(a: Attestation) -> bytes:
    return hash_blake2b(
        a.attestation_id.encode("utf-8")
        + b"\x1f"
        + a.attester_pubkey
        + b"\x1f"
        + a.attester_signature
        + b"\x1f"
        + a.payload_hash
    )


def _sequence_hash(items: Sequence[Any], item_hash: Any) -> bytes:
    """Hash a sequence by combining per-item digests in order.

    Order matters for events (the chain order is load-bearing); for
    lineage queries the backends should return parents/descendants in a
    stable order, but if they don't, two peers returning the same
    underlying set in different orders will disagree — which is the
    safe behaviour (better to surface "ordering ambiguous" than to
    accept).
    """
    h = b""
    for it in items:
        h = hash_blake2b(h + item_hash(it))
    return h


def record_hash(obj: Any) -> bytes:
    """Public entry point: canonical hash for federation diffing.

    Dispatches on type so callers can pre-compute a hash for any of the
    federated read shapes without importing the private helpers.
    Unknown types fall back to `repr` hashing — defensive against
    backend authors adding new return shapes without updating this
    file (the test will catch the missing case via disagreement).
    """
    if obj is None:
        return b"\x00" * 32
    if isinstance(obj, Vacant):
        return _vacant_hash(obj)
    if isinstance(obj, Event):
        return _event_hash(obj)
    if isinstance(obj, MerkleEpoch):
        return _epoch_hash(obj)
    if isinstance(obj, Attestation):
        return _attestation_hash(obj)
    if isinstance(obj, (list, tuple)):

        def _dispatch(x: Any) -> bytes:
            return record_hash(x)

        return _sequence_hash(obj, _dispatch)
    return hash_blake2b(repr(obj).encode("utf-8"))


# --- quorum core -------------------------------------------------------------


@dataclass(frozen=True)
class _PeerOutcome:
    """One peer's response to a fan-out query."""

    peer_index: int
    value: Any
    hash: bytes
    error: BaseException | None


async def _gather_peer(peer: RegistryBackend, index: int, coro_factory: Any) -> _PeerOutcome:
    """Run `coro_factory(peer)` and wrap the result/exception.

    The coro is built lazily per-peer so peers running on independent
    event loops / connection pools don't share state. Exceptions are
    captured (not raised) so a single peer outage doesn't take down
    the whole quorum read.
    """
    try:
        value = await coro_factory(peer)
        return _PeerOutcome(peer_index=index, value=value, hash=record_hash(value), error=None)
    except BaseException as exc:
        return _PeerOutcome(peer_index=index, value=None, hash=b"\xff" * 32, error=exc)


def _quorum_pick(outcomes: Sequence[_PeerOutcome], threshold: int) -> Any:
    """Return the value held by ≥ `threshold` peers (by content hash).

    Raises `QuorumDisagreement` with the observed distribution if no
    such majority exists. Errors are folded into the count under their
    sentinel hash, so an error from a peer counts as "no answer" rather
    than silently dropping that peer from the denominator.
    """
    counts: Counter[bytes] = Counter()
    by_hash: dict[bytes, Any] = {}
    for out in outcomes:
        counts[out.hash] += 1
        # Prefer the *first* non-error value we see for a given hash so
        # the returned object isn't None when one peer errored on a
        # value the others returned successfully.
        if out.hash not in by_hash and out.error is None:
            by_hash[out.hash] = out.value
    if not counts:
        raise QuorumDisagreement("no peers responded", observed=dict(counts))
    top_hash, top_count = counts.most_common(1)[0]
    if top_count < threshold:
        raise QuorumDisagreement(
            f"quorum not reached: top group has {top_count} peers, need {threshold} "
            f"(out of {len(outcomes)} peers); hash distribution: {dict(counts)}",
            observed=dict(counts),
        )
    return by_hash.get(top_hash)


# --- federated backend -------------------------------------------------------


class FederatedRegistryBackend:
    """M-of-N read-only `RegistryBackend` over `peers`.

    All read methods fan out to every peer in parallel and accept the
    first value held by ≥ `threshold` peers. Write methods raise
    `RegistryError` — federated writes need a different protocol
    (Byzantine consensus, gossip, etc.) and are deliberately out of
    scope for the MVP swap.

    Construction:
        peers: sequence of N independent `RegistryBackend`s (typically
            `RegistryStore` instances pointing at different replica DBs,
            but anything implementing the Protocol works — including
            HTTP-mediated clients).
        threshold: minimum number of peers that must return the same
            content for a read to succeed. Constraint:
            `1 ≤ threshold ≤ len(peers)`.

    Why both `len >= threshold` *and* threshold ≥ 1? Because a 0-threshold
    federated read would silently accept any divergence; we surface the
    misconfig as a `ValueError` at construction time.
    """

    def __init__(
        self,
        peers: Sequence[RegistryBackend],
        *,
        threshold: int,
    ) -> None:
        if threshold < 1:
            raise ValueError(f"threshold must be >= 1, got {threshold}")
        if len(peers) < threshold:
            raise ValueError(f"need >= {threshold} peers for an M-of-N quorum, got {len(peers)}")
        self._peers: tuple[RegistryBackend, ...] = tuple(peers)
        self._threshold = threshold

    @property
    def peer_count(self) -> int:
        return len(self._peers)

    @property
    def threshold(self) -> int:
        return self._threshold

    async def _quorum_read(self, coro_factory: Any) -> Any:
        """Fan out `coro_factory(peer)` across all peers, return the
        quorum value. Common path for every read method below.
        """
        outcomes = await asyncio.gather(
            *(_gather_peer(p, i, coro_factory) for i, p in enumerate(self._peers))
        )
        return _quorum_pick(outcomes, self._threshold)

    # --- writes (rejected) ---------------------------------------------------

    async def init_schema(self) -> None:
        """Schema init is per-peer; the federated layer doesn't own a
        schema of its own."""
        for p in self._peers:
            await p.init_schema()

    def _reject_write(self, method: str) -> None:
        raise RegistryError(
            f"FederatedRegistryBackend.{method} is read-only; "
            "perform writes against each peer's primary backend"
        )

    async def insert_vacant(self, vacant: Vacant) -> None:
        self._reject_write("insert_vacant")

    async def update_vacant_status(self, vacant_id: str, status: str) -> None:
        self._reject_write("update_vacant_status")

    async def update_vacant_visibility(self, vacant_id: str, visibility: str) -> None:
        self._reject_write("update_vacant_visibility")

    async def insert_event(self, event: Event) -> int:
        self._reject_write("insert_event")
        return 0  # unreachable; keeps mypy happy on the Protocol shape

    async def insert_attestation(self, attestation: Attestation) -> None:
        self._reject_write("insert_attestation")

    async def insert_merkle_epoch(self, epoch: MerkleEpoch) -> int:
        self._reject_write("insert_merkle_epoch")
        return 0

    async def assign_events_to_epoch(self, seqs: Sequence[int], epoch_id: int) -> None:
        self._reject_write("assign_events_to_epoch")

    # --- reads (quorum) ------------------------------------------------------

    async def get_vacant(self, vacant_id: str) -> Vacant | None:
        async def _go(p: RegistryBackend) -> Vacant | None:
            return await p.get_vacant(vacant_id)

        return await self._quorum_read(_go)  # type: ignore[no-any-return]

    async def latest_event_for_actor(self, actor_vacant_id: str) -> Event | None:
        async def _go(p: RegistryBackend) -> Event | None:
            return await p.latest_event_for_actor(actor_vacant_id)

        return await self._quorum_read(_go)  # type: ignore[no-any-return]

    async def latest_event_overall(self) -> Event | None:
        async def _go(p: RegistryBackend) -> Event | None:
            return await p.latest_event_overall()

        return await self._quorum_read(_go)  # type: ignore[no-any-return]

    async def list_attestations(self, vacant_id: str) -> Sequence[Attestation]:
        async def _go(p: RegistryBackend) -> Sequence[Attestation]:
            return await p.list_attestations(vacant_id)

        return await self._quorum_read(_go)  # type: ignore[no-any-return]

    async def get_merkle_epoch(self, epoch_id: int) -> MerkleEpoch | None:
        async def _go(p: RegistryBackend) -> MerkleEpoch | None:
            return await p.get_merkle_epoch(epoch_id)

        return await self._quorum_read(_go)  # type: ignore[no-any-return]

    async def latest_merkle_epoch(self) -> MerkleEpoch | None:
        async def _go(p: RegistryBackend) -> MerkleEpoch | None:
            return await p.latest_merkle_epoch()

        return await self._quorum_read(_go)  # type: ignore[no-any-return]

    async def list_unsealed_events(self) -> Sequence[Event]:
        async def _go(p: RegistryBackend) -> Sequence[Event]:
            return await p.list_unsealed_events()

        return await self._quorum_read(_go)  # type: ignore[no-any-return]

    async def lookup_idempotency(self, idempotency_key: str) -> Event | None:
        async def _go(p: RegistryBackend) -> Event | None:
            return await p.lookup_idempotency(idempotency_key)

        return await self._quorum_read(_go)  # type: ignore[no-any-return]

    async def list_descendants(self, vacant_id: str, *, max_depth: int = 8) -> Sequence[Vacant]:
        async def _go(p: RegistryBackend) -> Sequence[Vacant]:
            return await p.list_descendants(vacant_id, max_depth=max_depth)

        return await self._quorum_read(_go)  # type: ignore[no-any-return]

    async def list_ancestors(self, vacant_id: str, *, max_depth: int = 8) -> Sequence[Vacant]:
        async def _go(p: RegistryBackend) -> Sequence[Vacant]:
            return await p.list_ancestors(vacant_id, max_depth=max_depth)

        return await self._quorum_read(_go)  # type: ignore[no-any-return]

    async def search_capability(
        self,
        *,
        capability: str | None,
        family: str | None,
        status: str | None,
        visibility: str | None,
        limit: int,
    ) -> Sequence[Vacant]:
        async def _go(p: RegistryBackend) -> Sequence[Vacant]:
            return await p.search_capability(
                capability=capability,
                family=family,
                status=status,
                visibility=visibility,
                limit=limit,
            )

        return await self._quorum_read(_go)  # type: ignore[no-any-return]
