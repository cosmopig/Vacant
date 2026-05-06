# D012 -- P5 Composite reconciliation

**Date:** 2026-05-06
**Author:** P5 implementation pass
**Affected components:** `src/vacant/composite/`, `src/vacant/core/constants.py`,
`architecture/CONSTANTS.md`

---

## Background

The P5 component spec (`architecture/components/P5_composite.md`) and the
P5 dispatch (`dispatch/P5_composite.md`) leave several thresholds and
shapes unspecified:

- the per-parent graduation rate-limit value,
- the threshold above which a `same_*` collusion signal blocks
  graduation,
- the canonical signing payload for `ChildManifest` (the dispatch
  pins both signatures cover the same payload but does not pin the
  encoding),
- whether P5 should depend directly on P3 reputation.

This ADR pins those decisions for the implementation in PR
`feat/p5-composite`.

## §A -- Graduation rate limit defaults to 3 / parent / 24h

**Decision:** `GRADUATION_RATE_LIMIT_PER_PARENT_24H = 3`. Sliding 24h
window per parent, enforced inside `GraduationService`.

**Rationale:**

- Mirrors the `REVIEW_LIMIT_PER_TARGET_24H = 3` pattern (P1 line 259):
  small N per day, sufficient for any honest parent's promotion
  cadence in a demo setting.
- Tunable per-service via `GraduationService(rate_limit_per_24h=N)`
  for the P7 demo (which spawns and graduates many sub-vacants in
  tight loops).
- Matches the spec's intent ("a finite, parent-consented operation,
  not an escape hatch") without over-constraining: bursts of three
  graduations in a day are unusual but legitimate (e.g. graduating a
  sibling group after they hit a maturity milestone together).

## §B -- Collusion threshold is 0.6 max-strength

**Decision:** `GRADUATION_COLLUSION_THRESHOLD = 0.6`. The graduation
gate trips when *any* of the three same-* signals on (parent, child)
is at or above this value.

**Rationale:**

- Same value as `DIMENSION_CORRELATION_ALERT_THRESHOLD = 0.6`
  (P3 §3.6 / CONSTANTS.md §Anomaly thresholds), so the two collusion
  signals share a calibration anchor.
- Conservative composition (`max(...)`) rather than weighted sum: a
  single high signal is enough evidence of sock-puppet behaviour to
  block this graduation. Same framing as `discount_from_signals`
  in P3 (max-strength composition).
- The gate is cost-raising, not preventive (CLAUDE.md §Same-* detection):
  the attacker can keep trying after burning more identity capital.

## §C -- ChildManifest signing payload canonicalisation

**Decision:** Both `signature_parent` and `signature_child` cover the
SAME canonical-json bytes produced by `ChildManifest.signing_payload()`,
which serialises `signing_dict()` with `sort_keys=True,
separators=(",", ":")`. The three tool-whitelist lists are sorted
inside `signing_dict()` so reordering does not produce a different
payload.

**Rationale:**

- Matches the dispatch's "both signatures cover the canonical-json of
  the same payload" requirement.
- Mirrors the rest of the codebase's canonicalisation rule (P0
  `LogEntry.signing_payload` and P6 `VacantEnvelope.signing_payload`
  use the same encoder).
- Excluded fields: only `signature_parent` and `signature_child`. Every
  other field -- including `closed_by_default` -- is in scope so an
  attacker cannot rewrite the closed flag after both signatures land.

## §D -- P5 does not import P3

**Decision:** `vacant.composite` defines a `CollusionDetector` Protocol
and ships a `CompositeStubDetector` (zeroes by default). The P3
`same_detect` signals are wired by the call site -- typically the P7
demo orchestrator -- by passing a P3-backed detector to
`GraduationService(detector=...)`.

**Rationale:**

- The dispatch explicitly says "If P3 isn't merged yet, define a
  `CollusionProtocol` and use a stub" -- this ADR pins the protocol
  shape (`signals_for(parent, child) -> CollusionSignals`).
- Keeps P5 testable without a reputation engine, and lets P3-less
  builds run graduation flows that defer to parent consent + rate
  limit (the "C" cost-raising layer).
- The trust model is unchanged: a P3-less build claims weaker collusion
  defences but does NOT claim P3 is a hard dependency.

## §E -- Graduation produces a CapabilityCard but does not publish

**Decision:** `GraduationService.graduate(...)` returns a
`GraduationOutcome` carrying a freshly signed `CapabilityCard`. The
caller (typically P7 orchestrator) is responsible for invoking
`vacant.registry.halo.publish_halo` with that card. P5 does NOT import
P4.

**Rationale:**

- Keeps the layering clean: P5 owns the composite-internal authorisation
  logic; P4 owns registry I/O. This mirrors how P3 (reputation
  recording) doesn't import P4 either.
- Lets the P7 demo orchestrate publish + collusion check + rate-limit
  in one place with full visibility.
- Avoids a circular dep risk if registry hooks ever need composite
  state.

## §F -- Identity preservation through graduation

**Decision:** Graduation flips the manifest's `closed_by_default` from
True to False, mints a `CapabilityCard` signed by the *same* child
keypair, and appends a `COMPOSITE_GRADUATED` entry to *both* logbooks.
The child's `VacantId` (Ed25519 pubkey bytes) is unchanged; the
child's logbook is extended, not forked.

**Rationale:**

- Mandated by CLAUDE.md ("Closed children + graduation: composite
  parents' children are closed by default, can graduate to public via
  parent consent + rate limit + 3-layer collusion detection. Same
  keypair / same logbook through graduation -- it's a visibility
  flag, not an entity upgrade").
- Regression-guarded by
  `tests/unit/test_graduation.py::test_graduation_does_not_change_keypair`
  and `test_graduation_preserves_logbook_continuity`.

## §G -- Tree-Only enforcement is a callsite gate, not a network filter

**Decision:** The Tree-Only invariant (P5 §2 D2) is enforced by
`tree_only_filter(caller_manifest, callee_id, siblings)` -- called at
every outbound socket from a closed-child runtime via
`CompositeRuntime.outbound_call`. A graduated child
(`closed_by_default=False`) bypasses the filter.

**Rationale:**

- The dispatch describes this as "outbound HTTP from a closed-child
  runtime is gated through `tree_only_filter` middleware". For MVP we
  expose the filter as a function callers wire into their dispatch
  surface; integrating into the actual P6 dispatch path is a follow-up
  once the P7 demo defines what a "closed child runtime" socket looks
  like end-to-end.
- The property test `test_closed_child_call_succeeds_iff_target_in_tree`
  pins the invariant with hypothesis fuzz: any closed-child call
  succeeds iff the callee is parent or sibling.

## Constants added

- `GRADUATION_RATE_LIMIT_PER_PARENT_24H = 3` (CONSTANTS.md §Composite)
- `GRADUATION_COLLUSION_THRESHOLD = 0.6` (CONSTANTS.md §Composite)

Both pinned via the new D012 §A and §B citations in CONSTANTS.md.
