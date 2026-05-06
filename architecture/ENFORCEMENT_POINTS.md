# ENFORCEMENT_POINTS

For every load-bearing theory decision in `CLAUDE.md` §"Load-bearing
theory decisions", this document names the **single canonical
file:line** where the invariant is enforced in code, plus any
secondary callsites that *consume* the primary check (so a reviewer
walking the call graph can confirm the invariant is not silently
bypassed elsewhere).

If you are about to change one of these files, the rule of thumb is:
the *primary* enforcement point is the only place that decides; if you
change the policy you change it there. The *secondary* sites must keep
deferring to the primary — they are linked here so the next reviewer
can audit that property.

If you are adding a new load-bearing decision, add it to `CLAUDE.md`,
open an ADR, **and** extend this file.

---

## 1. Agent self-replication (D1-D5) is the primary birth path; Path A deprecated

Spec: `THEORY_V5.md` §3.6 / `CLAUDE.md` §Load-bearing decisions.

| Role | File:line | Note |
|---|---|---|
| **Primary** | `src/vacant/runtime/spawn.py:36-47` | `__all__` exposes only `spawn_clone_with_mutation` (D1), `spawn_subagent_bud` (D2), `spawn_capability_fork` (D3), `spawn_lineage_merge` (D4), `spawn_cross_substrate_respawn` (D5). Path A has no entry point. |
| Doc anchor | `src/vacant/runtime/spawn.py:12-13` | Module docstring: *"Path A (human-written vacant) is **deprecated** and intentionally absent (CLAUDE.md §Things to NOT do)."* |
| Secondary | `src/vacant/runtime/spawn.py:158-160` | `_ensure_parent_runnable` rejects spawns from non-LOCAL/ACTIVE parents → every birth requires a live D-path parent. |

## 2. Registry is per-vacant (halo), not central; calls go direct

Spec: `THEORY_V5.md` §7.1 / `CLAUDE.md`.

| Role | File:line | Note |
|---|---|---|
| **Primary** | `src/vacant/protocol/dispatch.py:128-130` | Docstring + behaviour: *"The registry is queried for discovery only; the call goes directly to `card.endpoint` via `transport`. No registry write endpoint is invoked from this path (D009 §C, dispatch acceptance)."* |
| Primary code | `src/vacant/protocol/dispatch.py:141-145` | `call_capability` resolves the halo via `aggregation_search`, then `call_local(target_card=…, transport=transport, …)` — `transport` is the caller-supplied direct HTTP client; no second-hop registry call. |
| Secondary | `src/vacant/registry/halo.py` | The halo aggregator only stores the per-vacant `capability_card`; there is no `route_request` / `proxy` endpoint. |
| Secondary | `src/vacant/registry/visibility.py:33-46` | `effective_visibility` is a discovery filter, not a routing decision. |

## 3. Sunk-state heartbeat is identity custody attestation, not liveness; Sunk cannot review

Spec: `THEORY_V5.md` §4.1 / §4.2.

| Role | File:line | Note |
|---|---|---|
| **Primary (review gate)** | `src/vacant/runtime/state_machine.py:104` | `_REVIEW_OK = frozenset({_S.LOCAL, _S.ACTIVE, _S.HIBERNATING})` — SUNK and ARCHIVED are excluded. |
| Primary (predicate) | `src/vacant/runtime/state_machine.py:108-113` | `can_review(state)` returns `False` for SUNK/ARCHIVED/STALE. |
| **Primary (custody payload)** | `src/vacant/runtime/heartbeat.py:96` | SUNK heartbeat emits `{"liveness": False, "key_in_custody": True}` — explicitly *not* liveness. |
| Secondary | `src/vacant/reputation/aggregator.py:225-228` | `record_review` calls `can_review(reviewer_ctx.state)`; SUNK reviewers raise `IneligibleReviewerError`. |

## 4. Lineage (parent_id chain), not individual vacants, is the subject of "infinite evolution"

Spec: `THEORY_V5.md` §4.3.

| Role | File:line | Note |
|---|---|---|
| **Primary (individual stall)** | `src/vacant/reputation/discount.py:47-65` | `compute_discount(stylo_distance)` — the per-vacant STYLO discount that bites self-evolution. |
| Primary (rolling drift) | `src/vacant/reputation/discount.py:113-150` | `RollingDriftWindow` + `apply_drift_discount` — accumulated drift is what stalls *individual* vacants. |
| **Primary (lineage reset)** | `src/vacant/reputation/cold_start.py:92` | `initial_prior(...)` — every D-path child gets a clean posterior + small birth boost; the parent's drift discount does NOT carry over. |
| Lineage anchor | `src/vacant/core/types.py:345` | `ResidentForm.parent_id: VacantId \| None` — the chain that "infinite evolution" actually evolves. |

## 5. Same-controller / same-substrate / same-stylo detection raises cost, doesn't prevent

Spec: `CLAUDE.md` / D015 §A.

| Role | File:line | Note |
|---|---|---|
| **Primary** | `src/vacant/reputation/same_detect.py:258` | `discount_from_signals` returns `max(SAME_SIGNAL_DISCOUNT_FLOOR, 1.0 - max_strength)` — a flagged review is downweighted, never zeroed. |
| Constant | `architecture/CONSTANTS.md` (`SAME_SIGNAL_DISCOUNT_FLOOR = 0.1`) | `src/vacant/core/constants.py` exports the floor. |
| ADR | `architecture/decisions/D015_codex_review_2026_05_06.md` §A | The "no zero-out" decision pinned by D015. |
| Test pin | `tests/unit/test_same_detect.py::test_discount_from_signals_full_strength_respects_floor` | Regression: even `strength=1.0` hits the floor, not zero. |

## 6. Reputation is 5-dim Beta posterior, per-substrate, with STYLO discount, with portability_factor

Spec: `THEORY_V5.md` §3.

| Role | File:line | Note |
|---|---|---|
| **Primary (state shape)** | `src/vacant/reputation/posterior.py:71` | `class Beta` (single dim) + `class Beta5D` (`src/vacant/reputation/posterior.py:205`) — five-dimensional Beta posterior with time-decayed prior weight. |
| Primary (per-substrate keying) | `src/vacant/reputation/aggregator.py:206-211` | `record_review(reviewer, target, dimensions, substrate, …)` — every update is keyed by `(target, substrate)`; per-substrate posteriors are never merged. |
| Primary (portability) | `src/vacant/reputation/portability.py:30-36` | `compute_portability(...)` is a *separate* output; never folded back into raw reputation. |
| Primary (STYLO discount) | `src/vacant/reputation/discount.py:47-65` | See §4 above. |

## 7. Closed children + graduation: visibility flag, not entity upgrade — same keypair, same logbook

Spec: `THEORY_V5.md` §6 / P5_composite §4.

| Role | File:line | Note |
|---|---|---|
| **Primary (sealed-by-default)** | `src/vacant/runtime/spawn.py:215` | `spawn_subagent_bud` (D2) creates a child with `registry_visibility=NONE` → state `LOCAL`. |
| **Primary (graduation = flag flip)** | `src/vacant/composite/graduation.py:1-18` | Module docstring: *"Graduation — flip a closed child's `registry_visibility` from NONE to PUBLIC. The same keypair, the same logbook, just a visibility flag flip."* |
| Primary (gate) | `src/vacant/composite/graduation.py:188-240` | `GraduationService.graduate(...)` enforces dual-signature + rate limit + 3-layer collusion detection; on success the child's keypair and logbook are unchanged — only the manifest's visibility field flips. |
| Test pin | `tests/unit/test_graduation.py` | Asserts the keypair and logbook hash chain are preserved across graduation. |

## 8. No central LLM, no central judge — verification via signed logbooks + peer review + reputation

Spec: `CLAUDE.md` / `THEORY_V5.md` §3 (Skalse 2022 framing).

| Role | File:line | Note |
|---|---|---|
| **Primary (signed logbooks)** | `src/vacant/identity/attestation.py:134-146` | `verify_attestation(att)` is pure-cryptographic verification against the attester's public key — no oracle, no central authority. |
| Primary (peer review accepted) | `src/vacant/reputation/aggregator.py:201-228` | `record_review` runs the M-of-N reputation update with **only**: `can_review(reviewer.state)`, source weight, `same_signals` discount, posterior decay. There is no `if oracle.approve()`-style gate. |
| Primary (reviewer audit trail) | `src/vacant/reputation/aggregator.py:139-145` | `register_audit` requires every reviewer to sign a `REVIEW_EVENT` into their own logbook before the posterior moves — verification is via the reviewer's signature, not a third-party. |
| ADR | `architecture/decisions/D015_codex_review_2026_05_06.md` §D | Pins the "logbook-attested review" decision. |

## 9. LOCAL state ≠ broken vacant — fully functional, just not in the public index

Spec: `CLAUDE.md` §LOCAL / `THEORY_V5.md` §1.1.

| Role | File:line | Note |
|---|---|---|
| **Primary (runnable predicate)** | `src/vacant/runtime/state_machine.py:105` | `_RUNNABLE = frozenset({_S.LOCAL, _S.ACTIVE})` — LOCAL is in the runnable set. |
| Primary (review predicate) | `src/vacant/runtime/state_machine.py:104` | LOCAL is in `_REVIEW_OK` — LOCAL vacants emit reviews. |
| Primary (visibility forcing) | `src/vacant/registry/visibility.py:44-45` | `effective_visibility(state, …)` returns `Visibility.NONE` for LOCAL — not in the public index. |
| Doc anchor | `src/vacant/runtime/state_machine.py:121-125` | `is_runnable` docstring: *"LOCAL is runnable (CLAUDE.md §LOCAL: registry visibility=none, but everything else works)."* |

---

## How to keep this file honest

1. **Touching one of the file:line targets above** without updating this
   file is a review-blocker. CI does not auto-detect drift; the
   convention is: "if the line moves, update the table in the same PR."
2. **Adding a new load-bearing decision** to `CLAUDE.md` requires a
   new section here and an ADR.
3. **Removing a load-bearing decision** requires an ADR, a deletion
   here, and a `git grep` sweep for any test that pinned the old
   invariant.

The point of this file is that the next reviewer / defense committee /
codex round can read a single page and verify each invariant by jumping
to one source line. If that is not true, this file has rotted.
