# D015 — codex review findings 2026-05-06

**Date:** 2026-05-06
**Author:** codex-review-fix pass
**Affected components:** `src/vacant/reputation/`, `src/vacant/registry/`,
`src/vacant/protocol/`, `src/vacant/mvp/`

---

## Background

A 2026-05-06 codex adversarial pass against the spec surfaced 5 major
findings that, left as-is, would have silently regressed three load-bearing
theory decisions from `CLAUDE.md`:

1. *Same-controller / same-substrate / same-stylo detection raises cost,
   doesn't prevent.*
2. *Lineage (parent_id chain), not individual vacants, is the subject of
   "infinite evolution."*
3. *Reputation comes from auditable history (signed logbooks).*

Plus two interface / demo gaps that broke the registry → dispatch path
and faked the same-controller demo.

This ADR pins the design decisions; the matching code changes ship in
the same PR.

## §A — `discount_from_signals` floor (F1)

**Decision:** `discount_from_signals(...)` returns at least
`SAME_SIGNAL_DISCOUNT_FLOOR` (= 0.1) when any signal fires. A
`strength=1.0` `SameDetectSignal` no longer zeroes the reviewer's weight.

**Rationale:**

- `CLAUDE.md` §Load-bearing theory decisions: "Same-controller /
  same-substrate / same-stylo detection raises cost, doesn't prevent."
- Allowing `discount → 0` converts detection into a unilateral mute:
  a single false-positive same-* signal would silence the reviewer's
  contribution entirely. That is the "preventing" framing we explicitly
  disclaim.
- Keeping a residual floor preserves the cost-raising semantics: the
  flagged review still counts (downweighted), so a wrongly-flagged
  honest reviewer is not erased.

**Tests:** `tests/unit/test_same_detect.py::test_discount_from_signals_full_strength_respects_floor`,
`...::test_discount_from_signals_floor_holds_for_any_signal_combination`.

## §B — UCB no longer mixes parent posterior into child score (F2)

**Decision:** `ucb_with_lineage_prior` no longer blends the parent's
posterior into the child's UCB score. The parent argument is kept as a
*caller-side metadata* hook (lineage filtering / sort tie-break) but
the score itself is computed only from the child's own posterior.

`lineage_prior_alpha` remains exported as a low-level helper for any
caller that wants to compute a lineage-weighted prior *outside* the
UCB pipeline (e.g. a future cold-start research probe), but
`ucb_with_lineage_prior`, `call_score`, `ucb_score` and the aggregator
do not use it.

**Rationale:**

- `CLAUDE.md` §Load-bearing theory decisions: "Lineage (parent_id chain),
  not individual vacants, is the subject of 'infinite evolution.'
  Individual vacants accumulate STYLO-distance discount rollover that
  bites self-evolution; new lineage members reset the clock."
- A child inheriting parent posterior in its UCB score *is* individual-
  level reputation inheritance — exactly the regression the lineage
  invariant disallows. It would let a high-reputation parent fork
  children that auto-rank above genuinely better but unrelated vacants.
- Lineage as caller-side metadata (e.g. "filter to descendants of root
  R", "show ancestry chip in the dashboard") preserves the auditing /
  attribution role of `parent_id` without leaking reputation across
  identities.

**Tests:** `tests/unit/test_ucb.py::test_ucb_with_lineage_prior_does_not_inherit_parent_score`,
`...::test_lineage_prior_alpha_helper_still_decays`.

## §C — `HaloMatch` carries the signed `CapabilityCard` (F3)

**Decision:** `HaloMatch` (the result of registry
`search_capability` / `rank_by_reputation`) is extended with a
`capability_card: CapabilityCard` field carrying the **signed** card
(including `endpoint`). `dispatch._match_to_card` reads this directly;
no rehydration / extra round-trip is needed.

**Rationale:**

- The previous interface broke at the seam: the registry returned a
  `HaloMatch` without an endpoint, but `dispatch.call_capability` needs
  `card.endpoint` to POST. The dispatch had a heuristic
  `_match_to_card` that only worked for unit-test stubs.
- Option (B) (rehydrate via `vacant_id`) doubles RTTs and reintroduces
  registry-as-mediator, against §7.1 trust-anchor-not-trust-origin.
- Option (A) (carry the signed card) keeps the registry as an index
  layer: the caller can verify the card independently — exactly the
  "trust the halo signature, not the registry" property the spec wants.

**Tests:** `tests/integration/test_dispatch_via_registry.py` exercises
the full path "registry lookup → HaloMatch → dispatch → A2A call"
with a mock HTTP transport but real `HaloMatch → CapabilityCard` flow.

## §D — `record_review` writes a signed REVIEW_EVENT (F4)

**Decision:** `Aggregator.record_review` requires a reviewer signing
key. It appends a signed `REVIEW_EVENT` `LogEntry` to the reviewer's
logbook *before* mutating the posterior. The logbook chain is verified
post-append; if verification fails, the posterior update is rolled back
and `ChainTamperError` is raised.

The new `Aggregator(...)` constructor carries `logbooks:
dict[VacantId, Logbook]` and `signing_keys: dict[VacantId, SigningKey]`
maps so the audit trail is attached to the same logbook that everything
else in the system already verifies.

**Rationale:**

- The thesis claim is "reputation is grounded in auditable history."
  Direct posterior mutation without a signed event is the exact gap
  that would let an adversary post-hoc fabricate a reputation history.
- The audit trail lives in the *reviewer's* logbook (not a separate
  ledger) so the existing `Logbook.verify_chain` / `verify_or_raise`
  pipeline transparently covers it.

**Tests:** `tests/unit/test_aggregator.py` adds:

- `test_record_review_appends_signed_review_event`
- `test_record_review_with_tampered_logbook_rejects_and_does_not_update_posterior`

## §E — `code_review` demo runs a real `same_controller` detector (F5)

**Decision:** the `code_review` scenario constructs a colluding pair
(reviewer-3 / reviewer-4) with a shared declared `controller_id` plus
correlated heartbeat timing, runs the `same_controller(...)` detector,
and feeds *its actual output* into the aggregator. Hardcoded
`SameDetectSignal(strength=1.0)` is removed.

The detector is also evaluated against:

- The *seeded colluding pair* — TP rate ≥ 0.8.
- A non-colluding control pair — FP rate ≤ 0.1.

The MVP dashboard's adversarial page reads these signals from the
scenario result instead of synthesizing them at render time.

**Rationale:**

- A demo that hardcodes the signal does not demonstrate the detector;
  it demonstrates the aggregator's response to a hand-supplied number.
- The seeded scenario gives the dashboard a reproducible TP/FP rate to
  display, which is the actual numeric claim of the cost-raising
  framing.

**Tests:** `tests/integration/test_mvp_full.py` (scenario-level metric
assertions) plus existing scenario hardness in
`tests/unit/test_same_detect.py`.

## Migration / non-decisions

- `lineage_prior_alpha` remains exported (back-compat for any research
  callers); only `ucb_with_lineage_prior` semantics change.
- `record_review`'s old positional/keyword shape is preserved; the
  signing key + logbook are passed via the constructor, so callers that
  don't supply them get a `MissingAuditKeyError` *only when they call
  `record_review`*. Read paths (`get_reputation`, `score`, `get_ranked`)
  remain unaffected.

## Status

Accepted 2026-05-06. Review-test coverage tracked in the PR description.
