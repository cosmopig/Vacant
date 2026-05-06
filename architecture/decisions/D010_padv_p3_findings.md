# D010 -- Padv-P3 Findings: rate limit + cumulative drift + dim-imbalance alert

**Date:** 2026-05-06
**Author:** Padv-P3 (adversarial review of PR #7)
**Affected components:** `src/vacant/reputation/aggregator.py` /
`src/vacant/reputation/discount.py` / `src/vacant/core/constants.py`

---

## Background

The Padv pass on `feat/p3-reputation` (PR #7) probed seven P3 attack
surfaces (the seven dispatch-listed attacks). **3 real defense gaps**
were found and fixed; **3 residual risks** are documented with
regression-guard tests.

## Finding 1 -- Per-target review rate limit (FIXED)

**Status:** Defense gap. Fixed in this PR.

**Attack:** `dispatch/Padv_review.md` §"Sniping" -- a single peer
floods reviews against one target in a short window, dragging the
target's posterior down (or up). The original `Aggregator.record_review`
had no per-target rate limit; only novelty decay (per-(reviewer, target))
existed, which is bypassable by rotating reviewer identities.

**Defense (P, write-time):** enforce `REVIEW_LIMIT_PER_TARGET_24H = 3`
(CONSTANTS.md §Review limits / P1 line 259) over a 24h sliding window
in `Aggregator.record_review`. The 4th review against the same target
within the window raises `ReviewRateLimitError` regardless of who
submits it. The rate limit is per-target, not per-reviewer, so rotating
identities can't bypass it.

```python
async with self._lock:
    window = self._target_review_timestamps.setdefault(target, deque())
    cutoff = when - 86_400.0
    while window and window[0] <= cutoff:
        window.popleft()
    if len(window) >= self._review_limit_per_target_24h:
        raise ReviewRateLimitError(...)
    window.append(when)
```

`Aggregator(... review_limit_per_target_24h=N)` lets operators tune the
limit (e.g. demo orchestration with `10_000` for synthetic load tests).

**Test coverage:** `tests/adversarial/test_padv_p3_sniping.py` --
`test_attack_sniper_blocked_at_default_3_per_24h`,
`test_attack_sniping_via_distinct_reviewers_still_blocked`,
`test_attack_separate_targets_independent_quotas`,
`test_attack_window_evicts_after_24h`,
`test_attack_custom_limit_honoured`.

**Backwards compatibility:** existing P3 tests that did >3 reviews
against the same target in tight loops were updated to opt-out via
`review_limit_per_target_24h=10_000` -- those tests are exercising
discount/aggregation behaviour, not rate-limiting.

## Finding 2 -- Cumulative STYLO drift detector (FIXED)

**Status:** Defense gap. Fixed in this PR.

**Attack:** `dispatch/Padv_review.md` §"STYLO discount evasion" --
single-shot `compute_discount` is fooled by an attacker who keeps each
epoch's drift just below `STYLO_DRIFT_THRESHOLD = 3.5` while
accumulating change across many epochs. With per-epoch drift = 1.5
(below threshold), `compute_discount` returns ~0.85 -- almost no
evidence shed -- yet five such epochs cumulatively shift behaviour by
7.5 STYLO-distance units.

**Defense (D, detection):** add `CumulativeDriftTracker` to
`reputation/discount.py`. Rolling-window sum of per-epoch drifts; trips
when sum >= `STYLO_DRIFT_THRESHOLD * CUMULATIVE_DRIFT_THRESHOLD_MULTIPLIER`
(default `3.5 * 1.5 = 5.25` over a 5-epoch window). Constants pinned
in `core.constants`:

- `CUMULATIVE_DRIFT_WINDOW_EPOCHS = 5`
- `CUMULATIVE_DRIFT_THRESHOLD_MULTIPLIER = 1.5`

The tracker is per-(vacant, substrate); the policy layer (P1 / P7)
owns one per target it scores and consumes `is_tripped()` to enqueue
warmup ceremonies or apply harsher discounts. P3 itself doesn't
auto-block -- the cumulative trip is a signal that the policy layer
elevates to a per-vacant warmup decision.

**Test coverage:** `tests/adversarial/test_padv_p3_drift.py` --
`test_attack_single_shot_below_threshold_escapes_discount`,
`test_attack_cumulative_drift_tracker_trips_on_accumulated_small_drifts`,
`test_attack_cumulative_tracker_does_not_trip_on_natural_variance`,
`test_attack_cumulative_tracker_window_evicts_old_drifts`.

## Finding 3 -- Dimension-imbalance alert (FIXED)

**Status:** Defense gap. Fixed in this PR.

**Attack:** `dispatch/Padv_review.md` §"Dimension imbalance" -- pump
only `factual` while leaving `adoption` low. P3 §3.6 防線 4 calls for
a cross-dimension divergence check; CONSTANTS.md §Reputation has the
canonical threshold (`DIMENSION_CORRELATION_ALERT_THRESHOLD = 0.6`)
but no code consumed it.

**Defense (D, surface caveat):** add `dimension_imbalance_alert(rep)`
to `reputation/discount.py`. Returns True when `max - min` of the
five per-dim means exceeds the threshold (default 0.6). The
implementation is intentionally simple -- a full pairwise correlation
matrix is future work; max/min difference is a tight upper bound on
the spread the spec describes.

The alert is a **surface caveat** consumed by P5/P7 dashboard
rendering, not a write-time block. The detected imbalance is a signal
the UI should display next to the scalar score, per spec §3.6 防線 4
(forced disclosure).

**Test coverage:** `tests/adversarial/test_padv_p3_dimension_imbalance.py`
-- `test_attack_factual_only_pump_triggers_alert`,
`test_attack_balanced_high_does_not_trigger_alert`,
`test_attack_balanced_low_does_not_trigger_alert`,
`test_dimension_imbalance_alert_handles_fresh_prior` (cold-start
doesn't false-fire).

## Residual risk 1 -- Honesty laundering via `self_eval`

**Status:** Documented residual. Cost-raising defense (C). The base
weight (0.05) is the structural mitigation.

**Attack:** A vacant submits all-1.0 self-evaluations across H. P3 §3.5
specifies that `self_eval` should NOT directly write to H -- its only
role is feeding the gap calculation between self_claims and peer
consensus. The current `record_review` accepts `source="self_eval"`
and updates the dimensions submitted; the structural mitigation is
the tiny base weight (`SOURCE_BASE_WEIGHTS["self_eval"] = 0.05`,
~12x smaller than `peer_review = 0.4`).

The fully spec-compliant fix (separate honesty-aggregator pipeline that
*never* lets self_eval write directly) is future work. For MVP the
0.05 base weight + per-target rate limit + same-* signals are the
cost-raising defense.

**Test coverage (regression guard):**
`tests/adversarial/test_padv_p3_residual.py::test_self_eval_alone_cannot_dominate_honesty`
asserts that 3 self_eval reviews leave H much less changed than 3
peer_review reviews -- the structural rate gap is the defense.

## Residual risk 2 -- Adoption stuffing (callsite verification)

**Status:** Documented residual. Future work for P4 event-log
verification.

**Attack:** `dispatch/Padv_review.md` §"Adoption stuffing" -- a vacant
submits fake adoption events to inflate the A dimension. Per dispatch:
"adoption events must trace to a verifiable callsite". P3's
`record_review(source="adoption_event")` accepts the event without
verifying that a corresponding event exists in P4's event log.

The fully-wired defense requires:
1. P4 stores call events in the audit log.
2. P3's adoption-event accept path looks up the cited call_id and
   verifies it's a real event signed by both parties.

For P3 MVP the structural mitigations are: (a) base weight 0.3 / cite
(modest), (b) per-target 24h rate limit applies, (c) novelty decay on
repeat reviewer-target pairs.

**Test coverage (regression guard):**
`tests/adversarial/test_padv_p3_residual.py::test_adoption_stuffing_residual_documented`
pins the current behaviour (adoption events accepted) and the test
is marked to be replaced with a positive test once P4 callsite-trace
verification lands.

## Residual risk 3 -- Post-merger reputation poaching (D4 lineage merge)

**Status:** Documented residual. Depth-decay is the cost-raising
defense.

**Attack:** `dispatch/Padv_review.md` §"Post-merger reputation
poaching" -- a freshly-spawned D4 child gets a 25% inheritance
(`inherit_fraction=0.25`) of the parent's posterior at depth=0,
absorbing reputation without earning it.

**Existing defense:** `lineage_prior_alpha` decays inheritance with
`kappa = inherit_fraction * exp(-decay_lambda * depth)`. Depth-0
takes 25%; depth-3 takes <6%. The Beta5D system also enforces
`N_MIN_FOR_STABLE_SCORE = 30` and `N_SHOW_MIN_THRESHOLD = 10` --
`show_label` returns `INSUFFICIENT_DATA` until the merged child
accumulates its own evidence, so the inherited prior isn't displayed
as a scalar score.

A separate "post-merge cold-start period" (per dispatch's hint) is
future work -- the structural mitigation is the show-label gate.

**Test coverage:**
`tests/adversarial/test_padv_p3_residual.py::test_post_merger_depth_zero_child_inherits_capped_fraction`,
`test_post_merger_inheritance_decays_steeply_with_depth`,
`test_post_merger_low_n_eff_keeps_show_label_insufficient`.

## Summary

- **Found:** 30+ attack tests across 4 files (sybil, sniping, drift,
  dimension imbalance, residual regressions).
- **Defense gaps fixed:** 3
  - F1: per-target review rate limit (`REVIEW_LIMIT_PER_TARGET_24H = 3`).
  - F2: cumulative STYLO drift tracker (rolling-window detector).
  - F3: dimension-imbalance alert helper.
- **Residual risks (documented + regression-guarded):** 3
  - Honesty laundering -- structural mitigation via tiny self_eval weight.
  - Adoption stuffing -- P4 callsite-trace verification deferred.
  - Post-merger reputation poaching -- depth-decay + show-label gate.
- All tests pass on this branch.
