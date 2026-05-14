"""Best-effort write replication for federated registries (technical.html
§Roadmap "Federated").

The read side (`FederatedRegistryBackend`) already exists: M-of-N quorum
reads over independent peers. The write side is intentionally
out-of-scope for the central MVP because robust cross-peer write
replication needs either consensus (Raft / Paxos) or BFT (PBFT / Tendermint).
This module fills the gap with a pragmatic *best-effort gossip* layer:

- Each registry has its own primary `RegistryStore` (the canonical write
  path stays unchanged).
- `GossipReplicator` periodically (or on demand) pulls signed events
  from peer registries that the local peer is missing, validates them
  against the **same anti-tamper L1+L2 invariants** the local primary
  enforces (signature, monotonic actor_seq), and re-submits them via a
  `Sequence[RegistryStore]`-typed local sink.
- Anti-tamper guarantees come for free: a forged event won't replicate
  because `RegistryStore.submit_event` rejects bad signatures; a
  reordered event won't replicate because per-actor sequence is strict.

Convergence model:
- Eventually consistent: once two peers can talk, they end up with the
  same prefix per actor.
- Adversary-tolerant: a malicious peer can only feed us events that
  validate under the legit actor's pubkey. They can't make us accept a
  forged history.
- Forks within a single actor's chain still surface — the second
  conflicting event for the same `(actor, actor_seq)` triggers
  `SequenceMonotonicityError` on the loser side. The operator inspects
  the divergence.

This is deliberately *not* Byzantine consensus. We aim for what
technical.html actually claims (multi-replica auditability), not full
total-order broadcast.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field

from vacant.registry.errors import (
    IdempotencyConflict,
    RegistryError,
    SequenceMonotonicityError,
    SignatureRejected,
)
from vacant.registry.models import Event
from vacant.registry.store import RegistryStore, SignedEventDraft

__all__ = [
    "GossipReplicator",
    "GossipStats",
    "event_to_draft",
]


@dataclass
class GossipStats:
    """Per-tick replication outcome counts. Surfaced for dashboards /
    metrics so the operator can see how converged peers are.

    Attributes:
        peers_contacted: How many peer backends were polled in this tick.
        events_replicated: Events successfully `submit_event`d into the
            local store.
        events_skipped_duplicate: Idempotency hits — the local store
            already had this event. Normal in steady state.
        events_skipped_sequence: Per-actor sequence already advanced
            past this candidate's `actor_seq`. Either the peer is
            behind or we already replicated this from a different peer.
        events_rejected_signature: A peer tried to feed us an event
            whose signature doesn't validate. Strong signal the peer is
            malicious or has bit-rotted data. Counted but not surfaced
            as an exception (we want to keep gossiping).
        peer_errors: Peers that raised when we polled them (network
            outage, schema mismatch, etc.). Counted; tick continues.
    """

    peers_contacted: int = 0
    events_replicated: int = 0
    events_skipped_duplicate: int = 0
    events_skipped_sequence: int = 0
    events_rejected_signature: int = 0
    peer_errors: int = 0

    def merge(self, other: GossipStats) -> GossipStats:
        return GossipStats(
            peers_contacted=self.peers_contacted + other.peers_contacted,
            events_replicated=self.events_replicated + other.events_replicated,
            events_skipped_duplicate=self.events_skipped_duplicate + other.events_skipped_duplicate,
            events_skipped_sequence=self.events_skipped_sequence + other.events_skipped_sequence,
            events_rejected_signature=(
                self.events_rejected_signature + other.events_rejected_signature
            ),
            peer_errors=self.peer_errors + other.peer_errors,
        )


def event_to_draft(event: Event) -> SignedEventDraft:
    """Convert a persisted `Event` row back into a `SignedEventDraft`.

    Used to feed a remote peer's events into the local store via the
    standard `submit_event` path — so they pass the same anti-tamper
    checks as a freshly-written event. The chain hash is recomputed by
    the local store; we don't have to (and shouldn't) trust the remote
    peer's `event_hash`.
    """
    import json

    try:
        payload = json.loads(event.payload_json)
    except json.JSONDecodeError as exc:
        raise RegistryError(f"event seq={event.seq} has unparseable payload_json: {exc}") from exc
    if not isinstance(payload, dict):
        raise RegistryError(
            f"event seq={event.seq} payload_json is not a dict: {type(payload).__name__}"
        )
    return SignedEventDraft(
        event_type=event.event_type,
        actor_vacant_id=event.actor_vacant_id,
        subject_vacant_id=event.subject_vacant_id,
        payload=payload,
        idempotency_key=event.idempotency_key,
        signed_by_pubkey=event.signed_by_pubkey,
        signature=event.signature,
        actor_seq=event.actor_seq,
        ts=event.ts,
    )


class GossipReplicator:
    """Pull-based gossip replicator over a set of `RegistryStore` peers.

    Usage:
        local = RegistryStore(local_engine)
        peers = [RegistryStore(e1), RegistryStore(e2), ...]
        gossip = GossipReplicator(local=local, peers=peers)
        stats = await gossip.replicate_tick()

    A single `replicate_tick()` polls every peer once, asks for events
    newer than what we've already seen from that peer's view, and
    submits each via `local.submit_event`. The local store's L1+L2
    defenses do the actual security work — the gossip layer just hauls
    bytes.

    To run continuously, schedule a tick (e.g. via
    `asyncio.create_task(gossip.run_forever(interval_s=60))`).
    """

    def __init__(
        self,
        *,
        local: RegistryStore,
        peers: Sequence[RegistryStore],
        max_events_per_peer_per_tick: int = 500,
    ) -> None:
        if max_events_per_peer_per_tick < 1:
            raise ValueError(
                f"max_events_per_peer_per_tick must be >= 1, got {max_events_per_peer_per_tick}"
            )
        self._local = local
        self._peers: tuple[RegistryStore, ...] = tuple(peers)
        self._max_per_tick = max_events_per_peer_per_tick
        # Per-peer high-water marks: `seq` value last attempted from that
        # peer. We re-poll from this seq onward each tick. Updated on
        # success OR refusal (so we don't loop on a known-bad event).
        self._peer_high_water: list[int] = [0] * len(self._peers)
        self._stop = asyncio.Event()

    @property
    def peer_count(self) -> int:
        return len(self._peers)

    async def replicate_tick(self) -> GossipStats:
        """One round of polling every peer. Returns aggregate stats."""
        total = GossipStats()
        for idx, peer in enumerate(self._peers):
            total = total.merge(await self._replicate_from(idx, peer))
        total.peers_contacted = len(self._peers)
        return total

    async def _replicate_from(self, peer_index: int, peer: RegistryStore) -> GossipStats:
        """Pull missing events from one peer."""
        stats = GossipStats()
        from_seq = self._peer_high_water[peer_index]
        try:
            events = await self._fetch_events(peer, from_seq=from_seq)
        except Exception:
            stats.peer_errors = 1
            return stats

        for ev in events:
            if ev.seq is None:
                continue
            try:
                draft = event_to_draft(ev)
            except RegistryError:
                # Malformed payload from peer — skip and advance HWM so
                # we don't loop on this row.
                self._peer_high_water[peer_index] = ev.seq
                continue
            try:
                await self._local.submit_event(draft)
                stats.events_replicated += 1
            except IdempotencyConflict:
                stats.events_skipped_duplicate += 1
            except SequenceMonotonicityError:
                stats.events_skipped_sequence += 1
            except SignatureRejected:
                stats.events_rejected_signature += 1
            self._peer_high_water[peer_index] = ev.seq
        return stats

    async def _fetch_events(self, peer: RegistryStore, *, from_seq: int) -> Sequence[Event]:
        """Fetch ordered events from `peer` strictly after `from_seq`.

        Implemented over `RegistryStore.list_events_for_vacant` would
        require knowing every vacant; instead we go through the raw
        session for a simple paginated `seq > from_seq` cursor. Limited
        to `_max_per_tick` to avoid one peer monopolising a tick.
        """
        from sqlmodel import select

        rows: list[Event] = []
        async with peer._sessionmaker() as s:
            stmt = (
                select(Event)
                .where(Event.seq > from_seq)  # type: ignore[operator]
                .order_by(Event.seq)  # type: ignore[arg-type]
                .limit(self._max_per_tick)
            )
            res = await s.execute(stmt)
            rows.extend(res.scalars().all())
        return rows

    async def run_forever(self, *, interval_s: float = 60.0) -> None:
        """Run `replicate_tick` on a loop until `stop()` is called.

        Designed to live in a `asyncio.create_task(...)` background. The
        `stop()` event short-circuits the sleep so shutdown is prompt.
        """
        while not self._stop.is_set():
            await self.replicate_tick()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval_s)
            except TimeoutError:
                continue

    def stop(self) -> None:
        """Signal `run_forever` to exit after its current tick."""
        self._stop.set()


# silence "unused import" when running tools that exercise __all__ only
_ = field
