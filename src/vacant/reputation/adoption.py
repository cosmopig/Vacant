"""Adoption-signal indexer (technical.html §Reputation row 5).

When a downstream vacant *uses* an upstream response — cites it, builds
on it, returns a verified result derived from it — that's an adoption
signal: an implicit endorsement that's harder to forge than a
self-reported review.

This module is the indexing + windowing layer:

- `AdoptionLedger` records `(source_vid, downstream_vid, source_call_id,
  ts)` tuples and exposes range queries over the 24-72h window
  (`ADOPTION_SIGNAL_MIN_WINDOW_S` / `ADOPTION_SIGNAL_MAX_WINDOW_S`,
  CONSTANTS.md / D008 §A).
- `AdoptionEvent` is the dataclass shape the aggregator consumes.
- The aggregator's `record_adoption(event)` calls `AdoptionLedger.attest`
  before forwarding the signal as a posterior update on the `adoption`
  dimension with `SOURCE_BASE_WEIGHTS["adoption_event"]` weight.

Windowing matters: a downstream vacant that pings the registry *seconds*
after the source response was issued is suspicious (likely the same
controller; no time to actually use the result); a signal that arrives
*weeks* later is too stale to be evidence of fresh adoption. The window
caps both sides.

Anti-Sybil: same downstream cannot adopt the same source `(source_vid,
source_call_id)` twice — `attest` raises `AdoptionLedgerError` on
duplicates. Multiple downstreams can independently adopt the same source.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from vacant.core.constants import (
    ADOPTION_SIGNAL_MAX_WINDOW_S,
    ADOPTION_SIGNAL_MIN_WINDOW_S,
)
from vacant.core.types import VacantId
from vacant.reputation.errors import ReputationError

__all__ = [
    "AdoptionEvent",
    "AdoptionLedger",
    "AdoptionLedgerError",
]


class AdoptionLedgerError(ReputationError):
    """An adoption attestation failed validation.

    Distinct cases:
    - signal outside the 24-72h window
    - duplicate `(source, source_call_id, downstream)` tuple
    - self-adoption (`source == downstream`)
    """


@dataclass(frozen=True)
class AdoptionEvent:
    """A single downstream → upstream adoption signal.

    Attributes:
        source_vid: The upstream vacant whose response is being adopted.
        downstream_vid: The vacant that consumed the response.
        source_call_id: Stable identifier of the source response
            (e.g. the source vacant's envelope idempotency_key). Acts
            as the dedup key for "same downstream can't adopt the same
            response twice".
        source_ts: When the source response was issued (used to evaluate
            the window).
        adoption_ts: When the downstream registered adoption.
        substrate: Which substrate the upstream answer was served on;
            adoption signals are per-substrate (a model that works for
            English may not work for code).
    """

    source_vid: VacantId
    downstream_vid: VacantId
    source_call_id: str
    source_ts: float
    adoption_ts: float
    substrate: str = "default"

    def latency_s(self) -> float:
        """Time between source response and adoption signal, in seconds."""
        return self.adoption_ts - self.source_ts

    def is_within_window(self) -> bool:
        """True iff `latency_s()` falls inside [24h, 72h]."""
        return ADOPTION_SIGNAL_MIN_WINDOW_S <= self.latency_s() <= ADOPTION_SIGNAL_MAX_WINDOW_S


@dataclass
class AdoptionLedger:
    """In-memory store of adoption events with windowed read access.

    Dedup is keyed on `(source_vid, source_call_id, downstream_vid)`:
    a downstream can only adopt a given source response once. The
    ledger is intentionally additive — adoption signals are not
    revocable (technical.html: "history preserved permanently"), so
    the only error path is duplicate-rejection at insertion time.
    """

    _events: list[AdoptionEvent] = field(default_factory=list)
    _seen: set[tuple[bytes, str, bytes]] = field(default_factory=set)

    def attest(self, event: AdoptionEvent) -> None:
        """Record `event`, enforcing self-adoption + window + dedup.

        Raises `AdoptionLedgerError` if:
        - `event.source_vid == event.downstream_vid` (self-adoption is
          meaningless; equivalent to a self-review which the aggregator
          already rejects)
        - `event.is_within_window()` is False (24-72h window)
        - the `(source_vid, source_call_id, downstream_vid)` triple
          was already recorded
        """
        if event.source_vid == event.downstream_vid:
            raise AdoptionLedgerError(
                f"self-adoption: source==downstream=={event.source_vid.short()}"
            )
        if not event.is_within_window():
            raise AdoptionLedgerError(
                f"adoption latency {event.latency_s():.1f}s outside window "
                f"[{ADOPTION_SIGNAL_MIN_WINDOW_S}, {ADOPTION_SIGNAL_MAX_WINDOW_S}]"
            )
        key = (
            event.source_vid.pubkey_bytes,
            event.source_call_id,
            event.downstream_vid.pubkey_bytes,
        )
        if key in self._seen:
            raise AdoptionLedgerError(
                f"duplicate adoption: downstream {event.downstream_vid.short()} "
                f"already adopted {event.source_vid.short()}/{event.source_call_id}"
            )
        self._seen.add(key)
        self._events.append(event)

    def for_source(
        self, source_vid: VacantId, *, substrate: str | None = None
    ) -> Iterator[AdoptionEvent]:
        """Yield all events whose `source_vid` matches `source_vid`.

        When `substrate` is given, restrict to events on that substrate.
        Returned in insertion order; callers that need time-bucketed
        analytics can re-sort by `adoption_ts`.
        """
        for ev in self._events:
            if ev.source_vid != source_vid:
                continue
            if substrate is not None and ev.substrate != substrate:
                continue
            yield ev

    def distinct_downstreams(
        self, source_vid: VacantId, *, substrate: str | None = None
    ) -> set[VacantId]:
        """How many *distinct* downstream vacants have adopted this source.

        Used by the aggregator to compute the adoption posterior
        update: each distinct downstream contributes one signal (this
        is the Sybil-resistance lever — adoption from N distinct
        identities ≠ same identity adopting N times).
        """
        return {ev.downstream_vid for ev in self.for_source(source_vid, substrate=substrate)}

    def total_events(self) -> int:
        """Total number of accepted adoption events (across all sources)."""
        return len(self._events)

    def __len__(self) -> int:
        return self.total_events()

    def __iter__(self) -> Iterator[AdoptionEvent]:
        return iter(self._events)

    def extend(self, events: Iterable[AdoptionEvent]) -> None:
        """Batch-insert events; each goes through `attest()` so the same
        validation runs. Stops at the first failure (events accepted up
        to that point are kept; the rest are dropped). Used for replay
        from a persistent log."""
        for ev in events:
            self.attest(ev)
