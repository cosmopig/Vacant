# D013 -- Padv-P5 Findings: manifest tamper, Tree-Only, graduation laundering, sibling collusion

**Date:** 2026-05-06
**Author:** Padv-P5 (adversarial review of PR #11)
**Affected components:** `src/vacant/composite/`

---

## Background

The Padv pass on `feat/p5-composite` (PR #11) probed the four
dispatch-listed P5 attack surfaces:

1. Tree-Only bypass.
2. Graduation laundering.
3. Sibling collusion ring.
4. ChildManifest tampering.

**No new defense gaps fixed.** The existing P5 implementation defends
1, 2 (with a documented residual on min-review-count), and 4. Surface
3 has a P5-internal residual: P5 ships a `CollusionDetector` Protocol
+ stub; the same-tree signal that the spec describes is implemented by
P3 and wired by callers (per D012 §D). Until P3 is wired, sibling
rings face only the rate-limit + parent-consent layers.

## Finding 1 -- Tree-Only bypass (CONFIRMED COVERED)

**Status:** Defense holds.

**Attack:** `dispatch/Padv_review.md` §"Tree-Only bypass". A closed
child claims to call its parent / sibling but really targets an
external endpoint, or tries to flip its own `closed_by_default` flag,
or claims to be a sibling of a different tree.

**Defense layered (P, write-time + structural):**

- The manifest's `closed_by_default` field is in the dual-signed
  payload (D012 §C). Flipping it post-sign breaks both signatures.
- `CompositeRuntime.outbound_call` derives the sibling set from the
  authoritative manifest registry it owns. A caller cannot inject a
  forged sibling list because the runtime never accepts one externally.
- Cross-tree calls fail because `siblings_of(caller, manifests)`
  groups by `parent_id` and the attacker's manifest declares a
  different parent.
- `register_child` rejects manifests whose `parent_id` differs from
  the composite's identity (so a forged "I am also your child"
  manifest signed by an attacker-controlled key cannot enter the
  runtime).

**Test coverage:** `tests/adversarial/test_padv_p5_tree_only.py` --
`test_attack_closed_child_external_call_blocked`,
`test_attack_in_memory_closed_flag_mutation_rejected`,
`test_attack_cross_tree_call_blocked_via_runtime`,
`test_attack_caller_cannot_inject_sibling_set_via_runtime`,
`test_attack_graduated_child_does_not_become_sibling_of_other_trees`,
`test_attack_self_parent_claim_blocked`.

## Finding 2 -- Graduation laundering (PARTIALLY COVERED + residual)

**Status:** Two of three layers (rate limit + 3-layer collusion) are
implemented. Min-review-count gate is a documented residual.

**Attack:** `dispatch/Padv_review.md` §"Graduation laundering".
Graduate a sock-puppet child immediately after its first review
without enough evidence; or flood the parent's quota with fake
graduations; or rewrite the capability text after the parent signs
the consent.

**Defenses present (P + D):**

- `GraduationService` enforces `GRADUATION_RATE_LIMIT_PER_PARENT_24H`
  (default 3) over a 24h sliding window per parent. The 4th attempt
  raises `GraduationRateLimitError`.
- `GraduationService.graduate(...)` requires a dual-signed
  `GraduationRequest` whose payload covers `(parent_id, child_id,
  capability_text)`. Rewriting any of those after signing
  invalidates both signatures, raising `GraduationConsentError`.
- The `CollusionDetector` runs after consent verifies; if any
  same-* signal >= `GRADUATION_COLLUSION_THRESHOLD` (default 0.6,
  conservative max-strength composition), `GraduationCollusionError`
  raises and the runtime is not mutated.

**Residual: min-review-count gate is future work**

The dispatch's third layer ("min-review-count threshold") is not
implemented. The closed environment's mini_rep signals (P5 §3.6) are
intentionally weak (no honesty dim, three-dim only, evaluator
non-independence acknowledged); using them as a hard-pass gate would
let an attacker drown the signal with cheap pipeline executions. The
MVP relies on the parent's consent as the load-bearing decision and
defers the mechanical floor to a future PR that pins:

- the minimum number of EXECUTE events needed,
- weighting by ground-truth-check pass rate,
- whether mini_rep alone or also peer signals from outside the tree
  must cross a threshold.

**Test coverage:**
`tests/adversarial/test_padv_p5_graduation_laundering.py` --
`test_attack_bulk_graduation_blocked_by_rate_limit`,
`test_attack_one_sided_graduation_request_rejected`,
`test_attack_graduation_signed_by_attacker_key_rejected`,
`test_attack_capability_text_rewrite_invalidates_request`,
`test_attack_graduation_replay_does_not_re_open_window`.

`tests/adversarial/test_padv_p5_residual.py::test_residual_zero_review_child_can_graduate_with_consent`
pins the current behaviour (parent consent is the load-bearing
gate); a future PR adding a min-review-count gate must update this
test or fail it explicitly so the change is reviewed.

## Finding 3 -- Sibling collusion ring (PARTIALLY COVERED + residual)

**Status:** Defense gate exists; the P5-side default detector returns
zero. Real signals require P3 to be wired (per D012 §D).

**Attack:** `dispatch/Padv_review.md` §"Sibling collusion ring".
Three siblings inside the same composite tree write reviews of each
other to inflate mini_rep, then graduate. The dispatch's stated
defense is "same-tree signal applied as discount in P3".

**Defense present (D, gate at graduation):**

`GraduationService` consumes a `CollusionDetector` injected at
construction time. A caller wiring P3's `same_detect` -- typically
the P7 demo orchestrator -- gets the full defense: high
same-substrate / same-controller / same-stylo on the (parent, child)
pair raises `GraduationCollusionError` regardless of consent +
rate-limit decisions.

**Residual: default detector returns zeros**

In a P3-less build (default `CompositeStubDetector`), the gate
trivially passes. This is intentional per D012 §D: P5 must not import
P3 directly, so the actual signal computation is the caller's
responsibility. The residual cost-raising layer in this configuration
is the rate limit + parent consent: a colluding ring still cannot
graduate more than `GRADUATION_RATE_LIMIT_PER_PARENT_24H = 3`
children per parent per day, and each graduation requires a freshly
signed parent consent.

**Test coverage:**
`tests/adversarial/test_padv_p5_sibling_collusion.py` --
`test_attack_high_same_substrate_signal_blocks_graduation`,
`test_attack_signal_at_exact_threshold_trips`,
`test_attack_max_strength_composition_blocks_on_one_high_signal`,
`test_residual_default_detector_does_not_block_sibling_graduation`.

## Finding 4 -- Manifest tampering (CONFIRMED COVERED)

**Status:** Defense holds.

**Attack:** `dispatch/Padv_review.md` §"Manifest tampering". Modify
`ChildManifest` fields after one party signs and before the other
signs, or splice signatures from one manifest onto another.

**Defense (P, write-time):**

Both `signature_parent` and `signature_child` cover the SAME canonical-
json bytes from `signing_dict()` -- which excludes only the two
signature fields. Tampering any of `parent_id`, `child_id`,
`birth_path`, `closed_by_default`, `tool_whitelist_inherited /
added / removed` after signing breaks both signatures (D012 §C).

A signature spliced from a manifest that signed a different payload
(different child_id, different birth_path, different tool list) fails
to verify against the new payload. A one-sided signature is rejected
by `verify_or_raise` with a typed `ManifestError`.

**Test coverage:**
`tests/adversarial/test_padv_p5_manifest_tamper.py` --
`test_attack_child_rewrites_payload_after_parent_signed`,
`test_attack_parent_rewrites_payload_after_child_signed`,
`test_attack_flipping_closed_by_default_breaks_signatures`,
`test_attack_sibling_signature_graft_rejected`,
`test_attack_tool_whitelist_tamper_breaks_signature`,
`test_attack_birth_path_tamper_breaks_signature`,
`test_attack_parent_id_tamper_breaks_signature`,
`test_attack_forged_manifest_with_attacker_parent_rejected_by_runtime`.

## Other residuals (regression-guarded)

- **Tree-Only as callsite gate (D012 §G):** `tree_only_filter` is a
  pure function called from `CompositeRuntime.outbound_call`. Wiring
  into the actual socket layer (so a closed-child runtime cannot
  bypass it by building its own `httpx.AsyncClient`) is P7 work.
  Pinned by `test_residual_tree_only_filter_is_a_function_not_network_middleware`.
- **No direct P4 import (D012 §E):** Pinned by
  `test_residual_graduation_module_does_not_import_registry`.
- **Concurrent delegation chain integrity:** `CompositeRuntime._lock`
  serialises parent-logbook writes. Pinned by
  `test_residual_concurrent_delegation_preserves_chain`.

## Summary

- **Probed:** 4 dispatch-listed P5 attack surfaces.
- **Defense gaps fixed:** 0 -- the P5 implementation defends the
  three structural surfaces (Tree-Only, manifest tamper, graduation
  consent). Two surfaces have residuals matching D012's stated
  layering decisions.
- **Residual risks (documented + regression-guarded):** 2.
  - Min-review-count graduation gate (graduation laundering) --
    parent consent is the load-bearing decision until a future PR
    pins the mechanical floor.
  - Same-tree collusion signal (sibling collusion ring) -- P3-less
    builds defer to the rate-limit + consent gates; full defense
    requires the caller to wire P3's `same_detect` per D012 §D.
- **Tests added:** 28 attack tests across 5 files in
  `tests/adversarial/`.
- All tests pass on this branch.
