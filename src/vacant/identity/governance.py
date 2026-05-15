"""Governance + custody-transfer events (THEORY_V5 §8.1 A14, A29, A36, A39).

The v5 attack matrix marks these four entries as covered by named
mechanisms, but until this module they had no implementation. This
file closes that gap by providing the data types and pure-function
predicates the spec promises. Integration into the registry write
path and the aggregator's `caller_review` weighting is a follow-up
ticket — the types here are ready to be consumed, but no live code
path currently invokes them.

What this module provides (per V5 §8.1):

- `MigrationEvent` (A14) — atomic migration record. The
  `concurrency_uuid` field gives a registry a first-write-wins
  primary key: two concurrent migration submissions with the same
  vacant_id but different concurrency_uuid collide at the DB level,
  matching V5's "原子 migration_event + concurrent uuid 偵測"
  promise. Defence level **P** (prevents).

- `ControllerTransferEvent` (A29) — signed handover event from
  the old controller to the new one. `recently_transferred(now, ...)`
  is the predicate the spec calls out by name. Defence level **D**.

- `GovernanceChangeEvent` (A36) — same shape as the controller
  transfer but tagged for legal/corporate governance changes (e.g.,
  acquisitions where the keypair stays unchanged but the beneficial
  controller changes). Defence level **D**.

- `AttestorDiversity` (A39) — a small primitive that scores a set
  of attestor IDs by their Shannon entropy and labels low-entropy
  configurations as "captured-risk". Defence level **C**. Multi-source
  cross-check is left as a registry-side concern.

All four are pure-function / pure-data; no I/O, no global state.
Tests in `tests/unit/test_governance_events.py`.
"""

from __future__ import annotations

import math
import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

from vacant.core.crypto import SigningKey, sign, verify
from vacant.core.types import VacantId

__all__ = [
    "AttestorDiversity",
    "ControllerTransferEvent",
    "GovernanceChangeEvent",
    "MigrationEvent",
    "MigrationEventStore",
    "MigrationRaceError",
    "score_attestor_set",
]


class MigrationRaceError(Exception):
    """Raised by `MigrationEventStore.record` on a duplicate
    `(vacant_id, concurrency_uuid)` insert. The semantics match
    V5 §8.1 A14's "first-write-wins" claim — the loser MUST treat
    this exception as an indication that another migration won the
    race and act accordingly (abort, retry with a fresh event, etc.).
    """


# --- A14: atomic migration event ----------------------------------------


@dataclass(frozen=True)
class MigrationEvent:
    """A single atomic migration declaration.

    V5 §8.1 A14 defence: `原子 migration_event + concurrent uuid 偵測`.
    Two concurrent migrations of the same vacant generate distinct
    `concurrency_uuid`s; a registry using `(vacant_id, concurrency_uuid)`
    as a composite PK rejects the second insert at the DB level — that
    is the "atomic" claim. The race becomes "exactly one writer wins";
    losers can detect their loss and retry / abort cleanly.

    The signing key MUST be the migrating vacant's own private key —
    signature binds the (vacant_id, from_endpoint, to_endpoint,
    concurrency_uuid, issued_at_ms) tuple.
    """

    vacant_id: VacantId
    from_endpoint: str
    to_endpoint: str
    concurrency_uuid: str
    issued_at_ms: int
    signature: bytes = b""

    @classmethod
    def new(
        cls,
        *,
        vacant_id: VacantId,
        from_endpoint: str,
        to_endpoint: str,
        signing_key: SigningKey,
        issued_at_ms: int | None = None,
    ) -> MigrationEvent:
        """Construct + sign a fresh migration event. `concurrency_uuid`
        is a random UUIDv4 — two callers racing on the same vacant
        will never collide on this field, so the registry's
        first-write-wins PK rules them mutually exclusive."""
        if issued_at_ms is None:
            issued_at_ms = int(time.time() * 1000)
        cu = str(uuid.uuid4())
        payload = _migration_payload_bytes(
            vacant_id=vacant_id,
            from_endpoint=from_endpoint,
            to_endpoint=to_endpoint,
            concurrency_uuid=cu,
            issued_at_ms=issued_at_ms,
        )
        sig = sign(signing_key, payload)
        return cls(
            vacant_id=vacant_id,
            from_endpoint=from_endpoint,
            to_endpoint=to_endpoint,
            concurrency_uuid=cu,
            issued_at_ms=issued_at_ms,
            signature=sig,
        )

    def verify(self) -> bool:
        if not self.signature:
            return False
        payload = _migration_payload_bytes(
            vacant_id=self.vacant_id,
            from_endpoint=self.from_endpoint,
            to_endpoint=self.to_endpoint,
            concurrency_uuid=self.concurrency_uuid,
            issued_at_ms=self.issued_at_ms,
        )
        return verify(self.vacant_id.verify_key(), payload, self.signature)


@dataclass
class MigrationEventStore:
    """In-memory store that gives `MigrationEvent` the first-write-wins
    semantics V5 §8.1 A14 promises.

    Three invariants:

    1. **PK uniqueness (replay protection)**: every
       `(vacant_id_hex, concurrency_uuid)` ever observed remains in
       the `_seen_pks` set permanently; re-submitting the same event
       after `clear()` still raises `MigrationRaceError`.
    2. **At-most-one-in-flight per vacant (race protection)**: while a
       migration for `vacant_id` is in-flight, a second event for
       the same `vacant_id` (different concurrency_uuid) is rejected.
       The loser learns deterministically that another writer won.
    3. **Lifecycle clear**: `clear(vacant_id)` releases the in-flight
       slot (registry calls this once the migration is finalised /
       aborted) but does NOT clear the seen-PK history — old PKs
       remain replay-rejected for the lifetime of the store.

    This is the in-memory reference implementation. Production should
    swap in a SQLAlchemy-backed store with the same PK and the same
    seen-set semantic so the DB wins the race.
    """

    _seen_pks: set[tuple[str, str]] = field(default_factory=set)
    """Permanent record of every (vacant_id, concurrency_uuid) ever
    accepted. Used for replay rejection regardless of in-flight state."""

    _by_vacant: dict[str, MigrationEvent] = field(default_factory=dict)
    """In-flight events keyed by vacant_id. Cleared by `clear()` once
    the migration is finalised."""

    def record(self, event: MigrationEvent) -> None:
        """Atomically register a migration. Raises
        `MigrationRaceError` if either (a) the
        `(vacant_id, concurrency_uuid)` has *ever* been seen by this
        store (replay protection — see `_seen_pks`), or (b) another
        in-flight migration for the same `vacant_id` exists
        (race-loser case — V5 §8.1 A14)."""
        if not event.verify():
            raise MigrationRaceError(
                f"MigrationEventStore.record: event signature did not verify "
                f"for vacant_id={event.vacant_id.short()}"
            )
        key = (event.vacant_id.hex(), event.concurrency_uuid)
        if key in self._seen_pks:
            raise MigrationRaceError(
                f"MigrationEventStore.record: duplicate PK "
                f"({event.vacant_id.short()}, {event.concurrency_uuid})"
            )
        existing_for_vid = self._by_vacant.get(event.vacant_id.hex())
        if existing_for_vid is not None:
            raise MigrationRaceError(
                f"MigrationEventStore.record: vacant {event.vacant_id.short()} "
                f"already has an in-flight migration "
                f"(concurrency_uuid={existing_for_vid.concurrency_uuid}); "
                f"loser must abort or wait for current to resolve"
            )
        self._seen_pks.add(key)
        self._by_vacant[event.vacant_id.hex()] = event

    def get(self, vacant_id: VacantId) -> MigrationEvent | None:
        """Return the currently in-flight migration for `vacant_id`,
        or None when no migration is in-flight."""
        return self._by_vacant.get(vacant_id.hex())

    def clear(self, vacant_id: VacantId) -> None:
        """Release the in-flight slot for `vacant_id`. Called by the
        registry once the migration is finalised (or aborted).
        Idempotent. Does NOT clear `_seen_pks` — old PKs remain
        replay-rejected permanently."""
        self._by_vacant.pop(vacant_id.hex(), None)


def _migration_payload_bytes(
    *,
    vacant_id: VacantId,
    from_endpoint: str,
    to_endpoint: str,
    concurrency_uuid: str,
    issued_at_ms: int,
) -> bytes:
    return (
        b"vacant:migration:v1|"
        + vacant_id.hex().encode("utf-8")
        + b"|"
        + from_endpoint.encode("utf-8")
        + b"|"
        + to_endpoint.encode("utf-8")
        + b"|"
        + concurrency_uuid.encode("utf-8")
        + b"|"
        + str(issued_at_ms).encode("utf-8")
    )


# --- A29 + A36: controller / governance transfer ------------------------


_TRANSFER_KINDS = ("controller_transfer", "governance_change")


@dataclass(frozen=True, kw_only=True)
class _BaseTransferEvent:
    """Shared shape for A29 / A36. Two distinct kinds so consumers
    (the aggregator's caller_review weight or a Layer 9 metric) can
    treat them differently if they want."""

    vacant_id: VacantId
    kind: Literal["controller_transfer", "governance_change"]
    from_controller_id: str
    to_controller_id: str
    issued_at_ms: int
    signature: bytes = b""

    def signing_payload(self) -> bytes:
        return (
            b"vacant:transfer:v1|"
            + self.kind.encode("utf-8")
            + b"|"
            + self.vacant_id.hex().encode("utf-8")
            + b"|"
            + self.from_controller_id.encode("utf-8")
            + b"|"
            + self.to_controller_id.encode("utf-8")
            + b"|"
            + str(self.issued_at_ms).encode("utf-8")
        )

    def verify(self) -> bool:
        if not self.signature:
            return False
        return verify(
            self.vacant_id.verify_key(),
            self.signing_payload(),
            self.signature,
        )


@dataclass(frozen=True, kw_only=True)
class ControllerTransferEvent(_BaseTransferEvent):
    """A29 — a signed handover from the old controller to the new one.
    The keypair is unchanged across the transfer; what changed is the
    real-world entity holding it. V5 §8.1 marks this **D** (detect),
    with `recently_transferred` as the consumer-facing flag.
    """

    kind: Literal["controller_transfer", "governance_change"] = "controller_transfer"

    @classmethod
    def new(
        cls,
        *,
        vacant_id: VacantId,
        from_controller_id: str,
        to_controller_id: str,
        signing_key: SigningKey,
        issued_at_ms: int | None = None,
    ) -> ControllerTransferEvent:
        if issued_at_ms is None:
            issued_at_ms = int(time.time() * 1000)
        partial = cls(
            vacant_id=vacant_id,
            from_controller_id=from_controller_id,
            to_controller_id=to_controller_id,
            issued_at_ms=issued_at_ms,
        )
        return cls(
            vacant_id=vacant_id,
            from_controller_id=from_controller_id,
            to_controller_id=to_controller_id,
            issued_at_ms=issued_at_ms,
            signature=sign(signing_key, partial.signing_payload()),
        )


@dataclass(frozen=True, kw_only=True)
class GovernanceChangeEvent(_BaseTransferEvent):
    """A36 — same shape as ControllerTransferEvent but tagged for
    beneficial-control / corporate governance changes where the
    Ed25519 keypair stays unchanged. V5 §8.1 marks this **D** with
    a `recent_governance_change` flag.

    A self-declared GovernanceChangeEvent is only as honest as its
    signer; V5 §H10 acknowledges this is a residual risk. The
    primitive is a structural slot that downstream third-party
    attestation (future) can plug into.
    """

    kind: Literal["controller_transfer", "governance_change"] = "governance_change"

    @classmethod
    def new(
        cls,
        *,
        vacant_id: VacantId,
        from_controller_id: str,
        to_controller_id: str,
        signing_key: SigningKey,
        issued_at_ms: int | None = None,
    ) -> GovernanceChangeEvent:
        if issued_at_ms is None:
            issued_at_ms = int(time.time() * 1000)
        partial = cls(
            vacant_id=vacant_id,
            from_controller_id=from_controller_id,
            to_controller_id=to_controller_id,
            issued_at_ms=issued_at_ms,
        )
        return cls(
            vacant_id=vacant_id,
            from_controller_id=from_controller_id,
            to_controller_id=to_controller_id,
            issued_at_ms=issued_at_ms,
            signature=sign(signing_key, partial.signing_payload()),
        )


def recently_transferred(
    events: Iterable[_BaseTransferEvent],
    *,
    now_ms: int | None = None,
    window_ms: int = 30 * 24 * 60 * 60 * 1000,
) -> bool:
    """True iff any event in `events` was issued within `window_ms`
    of `now_ms`. V5 §8.1 mentions a `recently_transferred` flag /
    `recent_governance_change` flag; this is the shared predicate.
    Default window: 30 days (per A30's documented "短期濫用 30 天"
    semantic in V5 §8.1)."""
    if now_ms is None:
        now_ms = int(time.time() * 1000)
    cutoff = now_ms - window_ms
    return any(ev.issued_at_ms >= cutoff for ev in events)


# --- A39: attestor diversity --------------------------------------------


@dataclass(frozen=True)
class AttestorDiversity:
    """V5 §8.1 A39 — `attestor diversity + attestor reputation +
    cross-check 多源`. The defence is **C** (raises cost).

    `score()` returns the Shannon entropy of the attestor set. The
    `is_captured()` predicate flags low-entropy configurations
    (single source dominates) as captured-risk; the registry can
    use this signal to downweight cross-checks that lean on too few
    independent attestors.

    Multi-source cross-check itself (comparing what multiple
    attestors said about the same target) is a registry-side
    concern; this type only scores the *set composition*.
    """

    attestor_ids: tuple[str, ...]

    def score(self) -> float:
        """Shannon entropy (bits) of the attestor ID distribution.
        0 for empty or single-source; log2(N) for N uniformly-
        distributed attestors."""
        return score_attestor_set(self.attestor_ids)

    def is_captured(self, *, min_entropy_bits: float = 1.0) -> bool:
        """Default threshold 1.0 bit ≈ "at least two roughly-equal
        attestors". Below that, treat as captured."""
        return self.score() < min_entropy_bits


def score_attestor_set(attestor_ids: Iterable[str]) -> float:
    """Free-standing Shannon entropy helper for callers that don't
    want to instantiate `AttestorDiversity`."""
    counts: dict[str, int] = {}
    for aid in attestor_ids:
        counts[aid] = counts.get(aid, 0) + 1
    if not counts:
        return 0.0
    total = sum(counts.values())
    return float(
        -sum((c / total) * math.log2(c / total) for c in counts.values() if c > 0)
    )
