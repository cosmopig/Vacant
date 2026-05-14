"""Reputation aggregator -- the public API surface that the registry queries.

Implements P4's `vacant.registry.aggregation.ReputationOracle` Protocol
(via `score(vacant_id, dimensions)`), plus the richer dispatch §7 API:

- `get_reputation(vid, substrate) -> Beta5D`
- `get_ranked(capability_query, n) -> list[(VacantId, score)]`
- `record_review(reviewer, target, dimensions, substrate) -> None`

`record_review` enforces the dispatch's reviewer-eligibility check:
reviews from `SUNK / ARCHIVED / STALE` vacants are rejected at the API
surface (P1 `can_review`), and reviews from suspected-collusion sets
are downweighted via the `same-*` detector signals.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from vacant.core.constants import (
    NOVELTY_DECAY_COEFFICIENT,
    REPUTATION_DIMS,
    REVIEW_LIMIT_PER_TARGET_24H,
    REVIEWER_CREDIBILITY_FLOOR,
    SAME_BASE_MODEL_DISCOUNT,
    SAME_MODEL_HEAVY_DISCOUNT,
    SOURCE_BASE_WEIGHTS,
)
from vacant.core.crypto import SigningKey
from vacant.core.types import Logbook, VacantId, VacantState
from vacant.reputation.adoption import AdoptionEvent, AdoptionLedger
from vacant.reputation.cold_start import birth_path_bonus  # noqa: F401  re-export
from vacant.reputation.discount import apply_discount_5d
from vacant.reputation.errors import (
    ChainTamperError,
    IneligibleReviewerError,
    InvalidDimensionError,
    InvalidSignalError,
    MissingAuditKeyError,
    ReviewRateLimitError,
)
from vacant.reputation.posterior import Beta5D, five_d_with_priors
from vacant.reputation.same_detect import (
    SameDetectSignal,
    discount_from_signals,
)
from vacant.reputation.ucb import call_score as ucb_call_score
from vacant.runtime.state_machine import can_review

__all__ = [
    "Aggregator",
    "ReviewRecord",
    "VacantContext",
]


@dataclass
class VacantContext:
    """Per-vacant metadata the aggregator tracks alongside its posterior.

    Sourced from P4's `vacant` table when wired in. Held here so unit
    tests can run without a registry.
    """

    vacant_id: VacantId
    base_model_family: str = "unknown"
    state: VacantState = VacantState.ACTIVE
    capability_text: str = ""
    attestation_level: str = "L0"
    stake_amount: float = 0.0


@dataclass
class ReviewRecord:
    """One review event submitted to `record_review`."""

    reviewer: VacantId
    target: VacantId
    dimensions: dict[str, float]
    substrate: str
    source: str = "peer_review"
    ts: float = field(default_factory=lambda: time.time())
    same_signals: tuple[SameDetectSignal, ...] = ()


class Aggregator:
    """In-memory reputation aggregator. Persists state externally via P4.

    Construction: pass a registry of `VacantContext` keyed by `VacantId`.
    Tests typically build this fresh per-case; the demo dashboard
    constructs one and seeds from the registry's `vacant` table.
    """

    def __init__(
        self,
        contexts: dict[VacantId, VacantContext] | None = None,
        *,
        review_limit_per_target_24h: int | None = None,
        logbooks: dict[VacantId, Logbook] | None = None,
        signing_keys: dict[VacantId, SigningKey] | None = None,
    ) -> None:
        self._contexts: dict[VacantId, VacantContext] = dict(contexts or {})
        # Audit trail (D015 §D). The aggregator runs in one of two modes:
        #
        #   audit-aware  — `_logbooks` is non-empty (constructor seeded
        #                  or `register_audit` was called). Every
        #                  `record_review` requires the reviewer to be
        #                  registered; missing registration raises
        #                  `MissingAuditKeyError` (Pfix3 B4 fail-closed).
        #                  README's "record_review first appends signed
        #                  REVIEW_EVENT" claim holds in this mode.
        #
        #   no-audit     — `_logbooks` is empty and stays empty. Used by
        #                  unit tests + offline tooling that don't care
        #                  about D015 §D. Mutation is permitted without
        #                  any audit append.
        #
        # The discriminant is `_audit_mode_active` below. Once a logbook
        # has been registered (either via constructor or `register_audit`)
        # the aggregator is locked into audit-aware mode for the rest of
        # its life — a partial fixture cannot bypass the gate.
        #
        # ONE-WAY LATCH: `_audit_mode_active` is intentionally never
        # cleared back to False. Manually flipping it (e.g., in a test)
        # silently re-introduces the silent-skip behaviour Pfix3 B4
        # explicitly removed; do not do that. If a future use case
        # genuinely needs to "drop audit mode" mid-life, build a fresh
        # Aggregator instead.
        self._logbooks: dict[VacantId, Logbook] = dict(logbooks or {})
        self._signing_keys: dict[VacantId, SigningKey] = dict(signing_keys or {})
        self._audit_mode_active: bool = bool(self._logbooks)
        # Per (vacant, substrate) Beta5D.
        self._posteriors: dict[tuple[VacantId, str], Beta5D] = {}
        # Per (reviewer, target) review-count for novelty discount.
        self._review_counts: dict[tuple[VacantId, VacantId], int] = {}
        # Per (reviewer, target) sliding-window review timestamps for the
        # per-(reviewer,target) rate limit. Spec P1 line 259: "每 24h 對同一
        # target_did 的 review 上限: 3" — reviewer-side spam cap, not absolute
        # cap. Padv-P3 D010 §1 sniping defense (single peer flooding one
        # target) is satisfied because it's the (reviewer,target) pair that's
        # capped; popular targets can still receive many reviews from many
        # distinct reviewers.
        self._target_review_timestamps: dict[tuple[VacantId, VacantId], deque[float]] = {}
        self._review_limit_per_target_24h = (
            review_limit_per_target_24h
            if review_limit_per_target_24h is not None
            else REVIEW_LIMIT_PER_TARGET_24H
        )
        # Adoption ledger: downstream vacants attesting they used a source
        # vacant's response. Drives the `adoption` posterior dimension
        # (technical.html §Reputation row 5). Indexed in-memory; persistence
        # is the registry's job (post-MVP).
        self._adoption_ledger = AdoptionLedger()
        self._lock = asyncio.Lock()

    # --- public registry-side API ------------------------------------------

    def add_context(self, ctx: VacantContext) -> None:
        """Register a vacant + its metadata."""
        self._contexts[ctx.vacant_id] = ctx

    def register_audit(self, vid: VacantId, *, logbook: Logbook, signing_key: SigningKey) -> None:
        """Attach a `Logbook` + `SigningKey` for `vid`. Registering ANY
        reviewer flips the aggregator into audit-aware mode for the rest
        of its lifetime: subsequent `record_review` calls require the
        reviewer to be registered, otherwise `MissingAuditKeyError`."""
        self._logbooks[vid] = logbook
        self._signing_keys[vid] = signing_key
        self._audit_mode_active = True

    def _audit_enabled_for(self, reviewer: VacantId) -> bool:
        return reviewer in self._logbooks and reviewer in self._signing_keys

    def get_context(self, vid: VacantId) -> VacantContext:
        try:
            return self._contexts[vid]
        except KeyError as exc:
            raise InvalidSignalError(f"unknown vacant {vid}") from exc

    async def get_reputation(self, vid: VacantId, substrate: str) -> Beta5D:
        """Return the per-substrate Beta5D, building a cold-start prior if absent."""
        key = (vid, substrate)
        async with self._lock:
            rep = self._posteriors.get(key)
            if rep is None:
                rep = five_d_with_priors(now_ts=time.time())
                self._posteriors[key] = rep
        return rep

    async def get_ranked(
        self,
        capability_query: str,
        n: int,
        *,
        substrate: str = "default",
        weights: Mapping[str, float] | None = None,
    ) -> list[tuple[VacantId, float]]:
        """UCB-scored top-N candidates for a capability query.

        Filters to `is_runnable` vacants whose `capability_text` contains
        the query as a substring (cheap MVP search; P4's aggregation
        layer does the real index lookup).
        """
        async with self._lock:
            n_global = max(1, len(self._contexts))
            scored: list[tuple[VacantId, float]] = []
            for vid, ctx in self._contexts.items():
                if ctx.state not in (VacantState.ACTIVE, VacantState.LOCAL):
                    continue
                if capability_query and capability_query not in ctx.capability_text:
                    continue
                rep = self._posteriors.get((vid, substrate))
                if rep is None:
                    rep = five_d_with_priors(now_ts=time.time())
                score = ucb_call_score(
                    rep,
                    weights=weights,
                    n_global=n_global,
                    stake_amount=ctx.stake_amount,
                    attestation_level=ctx.attestation_level,
                )
                scored.append((vid, score))
        scored.sort(key=lambda p: p[1], reverse=True)
        return scored[:n]

    async def record_review(
        self,
        reviewer: VacantId,
        target: VacantId,
        dimensions: Mapping[str, float],
        substrate: str,
        *,
        source: str = "peer_review",
        same_signals: Sequence[SameDetectSignal] = (),
        ts: float | None = None,
    ) -> None:
        """Apply a review to the target's posterior. Raises
        `IneligibleReviewerError` if reviewer's runtime state forbids
        new reviews (P1 §4.1) and `InvalidDimensionError` for unknown
        dims.
        """
        if reviewer not in self._contexts:
            raise InvalidSignalError(f"unknown reviewer {reviewer}")
        if target not in self._contexts:
            raise InvalidSignalError(f"unknown target {target}")
        if reviewer == target:
            raise InvalidSignalError("reviewer == target (self-review)")

        reviewer_ctx = self._contexts[reviewer]
        if not can_review(reviewer_ctx.state):
            raise IneligibleReviewerError(
                f"reviewer {reviewer} state {reviewer_ctx.state.value} cannot review"
            )

        if source not in SOURCE_BASE_WEIGHTS:
            raise InvalidSignalError(f"unknown source {source!r}")
        for d in dimensions:
            if d not in REPUTATION_DIMS:
                raise InvalidDimensionError(f"unknown dim {d!r}")
        for d, s in dimensions.items():
            if not (0.0 <= float(s) <= 1.0):
                raise InvalidSignalError(f"dim {d} signal must be in [0, 1]; got {s}")

        target_ctx = self._contexts[target]
        when = ts if ts is not None else time.time()

        # --- Audit gate (Pfix3 B4) -----------------------------------------
        # Once any reviewer is registered the aggregator is in audit-aware
        # mode and every record_review must have audit covered for the
        # reviewer. This makes the README claim ("first appends signed
        # REVIEW_EVENT") honest in production. Tests that don't construct
        # with logbooks stay in no-audit mode and skip the append.
        if self._audit_mode_active and not self._audit_enabled_for(reviewer):
            raise MissingAuditKeyError(
                f"reviewer {reviewer} has no logbook/signing_key registered "
                "but the aggregator is in audit-aware mode (D015 §D); "
                "call `register_audit(reviewer, logbook=..., signing_key=...)` "
                "before record_review"
            )

        # --- Atomic mutation under a single lock ---------------------------
        # Order: rate-limit → tentative window append → signed REVIEW_EVENT
        # append (rollback window on failure) → composition → posterior
        # update. Holding the lock for the whole sequence guarantees that
        # an exception at any step leaves the aggregator's observable
        # state (window, logbook, posterior) coherent.
        pair = (reviewer, target)
        async with self._lock:
            # L2: per-(reviewer, target) rate limit (Padv-P3 D010 §1).
            # Spec P1 line 259: "每 24h 對同一 target_did 的 review 上限: 3"
            window = self._target_review_timestamps.setdefault(pair, deque())
            cutoff = when - 86_400.0
            while window and window[0] <= cutoff:
                window.popleft()
            if len(window) >= self._review_limit_per_target_24h:
                raise ReviewRateLimitError(
                    f"reviewer {reviewer} → target {target}: {len(window)} "
                    f"reviews in past 24h (limit {self._review_limit_per_target_24h})"
                )
            window.append(when)

            # D015 §D audit append. Failure rolls back the window
            # timestamp so retry isn't penalised by a phantom slot.
            if self._audit_enabled_for(reviewer):
                try:
                    self._append_signed_review_event(
                        reviewer=reviewer,
                        target=target,
                        dimensions=dimensions,
                        substrate=substrate,
                        source=source,
                        when=when,
                    )
                except Exception:
                    window.pop()  # remove the tentative timestamp we just appended
                    raise

            # Weight composition (§3.4).
            base_weight = SOURCE_BASE_WEIGHTS[source]
            same_model_w = 1.0
            if reviewer_ctx.base_model_family == target_ctx.base_model_family:
                same_model_w *= SAME_BASE_MODEL_DISCOUNT

            # Novelty (§3.4.3).
            self._review_counts.setdefault(pair, 0)
            self._review_counts[pair] += 1
            k = self._review_counts[pair]
            novelty = 1.0 / (1.0 + NOVELTY_DECAY_COEFFICIENT * max(0, k - 1))
            if reviewer_ctx.base_model_family == target_ctx.base_model_family and k > 5:
                same_model_w = SAME_MODEL_HEAVY_DISCOUNT

            reviewer_rep = self._posteriors.get((reviewer, substrate))
            sig_discount = discount_from_signals(same_signals)
            composed = base_weight * same_model_w * novelty * sig_discount

            # Apply per-dim posterior update (§3.4.2 reviewer credibility).
            key = (target, substrate)
            rep = self._posteriors.get(key) or five_d_with_priors(now_ts=when)
            for d, s in dimensions.items():
                cred = REVIEWER_CREDIBILITY_FLOOR
                if reviewer_rep is not None:
                    cred = (
                        REVIEWER_CREDIBILITY_FLOOR
                        + (1.0 - REVIEWER_CREDIBILITY_FLOOR) * reviewer_rep.get(d).mean
                    )
                w = composed * cred
                rep = rep.update_dim(d, signal=float(s), weight=w, now_ts=when)
            self._posteriors[key] = rep

    # --- adoption signal (technical.html §Reputation row 5) --------------

    async def record_adoption(
        self,
        event: AdoptionEvent,
        *,
        same_signals: Sequence[SameDetectSignal] = (),
    ) -> None:
        """Record a downstream → source adoption signal.

        Validation:
        - `event.source_vid` and `event.downstream_vid` must both be in
          `_contexts` (we only score vacants we know about).
        - The ledger enforces 24-72h window + dedup + self-adoption
          rejection (`AdoptionLedger.attest`); any failure surfaces as
          `AdoptionLedgerError`.

        Effect: the source vacant's `adoption` Beta posterior on
        `event.substrate` is updated with signal=1.0 (adoption is binary
        — they used it or they didn't) at weight
        `SOURCE_BASE_WEIGHTS["adoption_event"] * sig_discount`, where
        `sig_discount` reflects `same_*` collusion detection on the
        downstream → source pair (so a Sybil-suspect downstream
        contributes less than an independent one).
        """
        if event.source_vid not in self._contexts:
            raise InvalidSignalError(f"unknown adoption source {event.source_vid}")
        if event.downstream_vid not in self._contexts:
            raise InvalidSignalError(f"unknown adoption downstream {event.downstream_vid}")

        async with self._lock:
            # Window + dedup + self-adoption. Raises AdoptionLedgerError;
            # we let it propagate so the caller knows the signal was rejected.
            self._adoption_ledger.attest(event)

            base_weight = SOURCE_BASE_WEIGHTS["adoption_event"]
            sig_discount = discount_from_signals(same_signals)
            composed = base_weight * sig_discount

            key = (event.source_vid, event.substrate)
            rep = self._posteriors.get(key) or five_d_with_priors(now_ts=event.adoption_ts)
            rep = rep.update_dim("adoption", signal=1.0, weight=composed, now_ts=event.adoption_ts)
            self._posteriors[key] = rep

    def adoption_count(self, source_vid: VacantId, *, substrate: str | None = None) -> int:
        """How many distinct downstream vacants have adopted this source.

        Read surface for dashboards / metrics that want to display the
        "N vacants are building on this" signal without going through
        the full posterior. The dedup is by downstream identity, so the
        return value is the size of the unique-downstream set.
        """
        return len(self._adoption_ledger.distinct_downstreams(source_vid, substrate=substrate))

    # --- ReputationOracle protocol (P4 plug-in) ---------------------------

    async def score(self, vacant_id: str, dimensions: Sequence[str]) -> float:
        """Implements `vacant.registry.aggregation.ReputationOracle.score`.

        `vacant_id` is the hex form (P4's storage convention). We map it
        back to a `VacantId` against our context registry.
        """
        # Locate by hex.
        ctx = next(
            (c for c in self._contexts.values() if c.vacant_id.hex() == vacant_id),
            None,
        )
        if ctx is None:
            return 0.0
        async with self._lock:
            rep = self._posteriors.get((ctx.vacant_id, "default"))
        if rep is None:
            return 0.0
        if not dimensions:
            dims = REPUTATION_DIMS
        else:
            dims = tuple(d for d in dimensions if d in REPUTATION_DIMS)
            if not dims:
                return 0.0
        means = rep.means()
        return sum(means[d] for d in dims) / len(dims)

    # --- audit helpers (D015 §D) ------------------------------------------

    def _append_signed_review_event(
        self,
        *,
        reviewer: VacantId,
        target: VacantId,
        dimensions: Mapping[str, float],
        substrate: str,
        source: str,
        when: float,
    ) -> None:
        """Append a signed REVIEW_EVENT entry to the reviewer's logbook,
        verifying the chain before and after. Raises `ChainTamperError`
        if verification fails (and rolls the new entry back so the
        logbook stays valid for the next caller)."""
        logbook = self._logbooks[reviewer]
        signing_key = self._signing_keys[reviewer]
        pubkey = reviewer.verify_key()
        if not logbook.verify_chain(pubkey):
            raise ChainTamperError(
                f"reviewer {reviewer} logbook fails verify_chain — "
                "refusing to record review (D015 §D)"
            )
        payload = {
            "kind": "REVIEW_EVENT",
            "target": target.hex(),
            "dimensions": {d: float(s) for d, s in dimensions.items()},
            "substrate": substrate,
            "source": source,
            "ts": when,
        }
        logbook.append("REVIEW_EVENT", payload, signing_key)
        if not logbook.verify_chain(pubkey):
            # Roll back; the post-append verification failed.
            logbook.entries.pop()
            raise ChainTamperError(
                f"REVIEW_EVENT append produced an invalid chain for {reviewer} — "
                "rolling back (D015 §D)"
            )

    # --- maintenance -------------------------------------------------------

    async def apply_drift_discount(self, vid: VacantId, *, substrate: str, discount: float) -> None:
        """Apply a STYLO-distance discount to a (vacant, substrate)
        posterior. Called by P1 / shadow-self when drift is detected.
        """
        async with self._lock:
            key = (vid, substrate)
            rep = self._posteriors.get(key)
            if rep is None:
                return
            self._posteriors[key] = apply_discount_5d(rep, discount)
