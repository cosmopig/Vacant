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
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from vacant.core.constants import (
    NOVELTY_DECAY_COEFFICIENT,
    REPUTATION_DIMS,
    REVIEWER_CREDIBILITY_FLOOR,
    SAME_BASE_MODEL_DISCOUNT,
    SAME_MODEL_HEAVY_DISCOUNT,
    SOURCE_BASE_WEIGHTS,
)
from vacant.core.types import VacantId, VacantState
from vacant.reputation.cold_start import birth_path_bonus  # noqa: F401  re-export
from vacant.reputation.discount import apply_discount_5d
from vacant.reputation.errors import (
    IneligibleReviewerError,
    InvalidDimensionError,
    InvalidSignalError,
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
    ) -> None:
        self._contexts: dict[VacantId, VacantContext] = dict(contexts or {})
        # Per (vacant, substrate) Beta5D.
        self._posteriors: dict[tuple[VacantId, str], Beta5D] = {}
        # Per (reviewer, target) review-count for novelty discount.
        self._review_counts: dict[tuple[VacantId, VacantId], int] = {}
        self._lock = asyncio.Lock()

    # --- public registry-side API ------------------------------------------

    def add_context(self, ctx: VacantContext) -> None:
        """Register a vacant + its metadata."""
        self._contexts[ctx.vacant_id] = ctx

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

        # --- weight composition (§3.4) -------------------------------------
        base_weight = SOURCE_BASE_WEIGHTS[source]

        # Same-base-model discount (§3.4.1).
        same_model_w = 1.0
        if reviewer_ctx.base_model_family == target_ctx.base_model_family:
            same_model_w *= SAME_BASE_MODEL_DISCOUNT

        # Novelty (§3.4.3).
        async with self._lock:
            self._review_counts.setdefault((reviewer, target), 0)
            self._review_counts[(reviewer, target)] += 1
            k = self._review_counts[(reviewer, target)]
        novelty = 1.0 / (1.0 + NOVELTY_DECAY_COEFFICIENT * max(0, k - 1))
        # If this is the 6th+ same-model repeat, escalate the discount.
        if reviewer_ctx.base_model_family == target_ctx.base_model_family and k > 5:
            same_model_w = SAME_MODEL_HEAVY_DISCOUNT

        # Reviewer credibility (§3.4.2): `cred = floor + (1-floor) * mu`.
        # Recursive trust weighting terminates here at the floor -- even
        # an L0 reviewer counts for `REVIEWER_CREDIBILITY_FLOOR`.
        async with self._lock:
            reviewer_rep = self._posteriors.get((reviewer, substrate))
        # If this review touches multiple dims, take the per-dim mean as
        # the credibility multiplier per dim.

        # Same-* signals (§3.4.4 / dispatch §5).
        sig_discount = discount_from_signals(same_signals)

        composed = base_weight * same_model_w * novelty * sig_discount

        # --- apply per-dim --------------------------------------------------
        async with self._lock:
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
