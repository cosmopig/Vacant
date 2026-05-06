# D007 — Padv-P4 Findings: actor-impersonation closure + chain/index verifiers

**Date:** 2026-05-06
**Author:** Padv-P4 (adversarial review of PR #5)
**Affected components:** `src/vacant/registry/store.py`

---

## Background

The Padv pass on `feat/p4-registry` (PR #5) probed five P4 surfaces (event
chain, halo, visibility, anti-tamper, concurrency) with 24 attack tests.
**Two real defense gaps** were found and fixed; **one residual risk** is
documented with a regression-guard test.

## Finding 1 — Cross-actor identity impersonation (FIXED)

**Status:** Defense gap. Fixed in this PR.

**Attack:** `submit_event` verifies `signature` against `signed_by_pubkey`,
and the canonical bytes commit to both `actor_vacant_id` and
`signed_by_pubkey`. But the original code did not check that
`signed_by_pubkey` matches the **registered public key** for
`actor_vacant_id`. So an attacker with their own legitimately-registered
vacant could submit events whose `actor_vacant_id` named the **victim**,
as long as `signed_by_pubkey = attacker_pubkey` and the signature
verified under that key. The event would be filed under the victim's id
in the log, even though it was signed by the attacker.

Concretely, after `victim` registers, an `attacker`-controlled key can
submit:

```python
# canonical bytes commit to actor=victim_id, signer=attacker_pk;
# signature verifies under attacker_pk; event is filed as `from victim`.
SignedEventDraft(
    actor_vacant_id=victim_id,           # claim victim's identity
    signed_by_pubkey=attacker_pubkey,    # attacker's actual key
    signature=sign(attacker_sk, ...),    # signed by attacker
    ...
)
```

The signature verified, the canonical bytes were consistent, the chain
extended cleanly — and the registry's audit log carried a forged event
under the victim's name.

**Defense (P, in strong-custody assumption):** add a registered-actor
binding check in `submit_event`:

```python
actor = await self.get_vacant(draft.actor_vacant_id)
if actor is None:
    raise SignatureRejected("actor not registered")
if actor.public_key != draft.signed_by_pubkey:
    raise SignatureRejected(
        "signed_by_pubkey does not match registered key for actor"
    )
```

The vacant row is inserted *before* its first register event by
`publish_halo`, so this check is satisfied for legitimate flows.
Subsequent events fail unless `signed_by_pubkey` matches the same
registered public key. Cross-actor impersonation is blocked at write
time.

**Cost:** one extra row read per `submit_event`; trivially small.

**Test coverage:** `tests/adversarial/test_padv_p4_chain.py` —
`test_attack_cross_actor_impersonation_rejected`,
`test_attack_unregistered_actor_rejected`.

## Finding 2 — Index drift from event log (FIXED via verifier)

**Status:** Defense gap (verification-side). Fixed in this PR by adding
the verifier.

**Attack:** The `vacant.visibility` column is a *cache* that the
aggregation layer reads from. `publish_halo` updates it via
`update_vacant_visibility` and emits a signed `register` event. But an
attacker with direct SQL write access could `UPDATE vacant SET
visibility = 'NONE'` without emitting an event, hiding the vacant from
public discovery. The aggregation index would silently drift from the
audit chain.

**Defense (D, detection-only):** ship a `verify_vacant_index_consistent`
helper that recomputes the visibility from the latest signed `register`
event in the chain and compares it to the indexed column. Returns False
on mismatch. External auditors run this periodically; the chain is the
source of truth, the column is an indexed projection of it.

The chain itself remains tamper-evident via the existing signatures + the
new `verify_event_chain` helper (see Finding 3 below). So an attacker
who tampers the column without re-signing the chain is detectable both
at index-consistency time and at chain-verification time.

**Why detection rather than prevention:** SQL-direct writes are out of
scope for the application layer. The application can sign every legitimate
write through the store API; it cannot prevent a controller from running
arbitrary SQL. The defense framing is "the chain is verifiable, the
index is computable from it" — direct writes are detectable, not
preventable. Matches THEORY_V5 §0.1 strong-custody assumption: in demo
custody, controller-level writes are out-of-band; in strong custody
(TEE-isolated DB), they aren't possible at all.

**Test coverage:** `tests/adversarial/test_padv_p4_visibility.py` —
`test_attack_silent_visibility_downgrade_detected`,
`test_attack_silent_visibility_upgrade_detected`,
`test_attack_visibility_transition_via_publish_is_logged`.

## Finding 3 — In-place row tampering (UPDATE) detection (FIXED via verifier)

**Status:** Defense gap (verification-side). Fixed in this PR by adding
the verifier.

**Attack:** The `before_flush` listener catches DELETE on append-only
tables. UPDATE was not addressed. An attacker with SQL write access
could `UPDATE event SET payload_json = '...'` for any row; the stored
`payload_hash`, `signature`, and `event_hash` would be unchanged,
making the row internally inconsistent.

**Defense (D, detection-only):** add `verify_event_chain()` that walks
the event log in seq order and re-derives:

1. `payload_hash` from `payload_json` and compares to stored
2. canonical bytes from stored fields
3. signature verification under stored `signed_by_pubkey`
4. `event_hash` from `prev_event_hash || canonical || signature` and
   compares to stored
5. `prev_event_hash` for entry n+1 against `event_hash` for entry n

Any tamper at any field is caught at one of these checkpoints. Tests
exercise `payload_json` UPDATE, `signature` UPDATE, `event_hash`
UPDATE, and `prev_event_hash` splice — all detected.

UPDATE rejection at write time was considered (a `before_flush` listener
that raises on `session.dirty` for append-only tables) but is brittle:
SQLAlchemy's session model uses UPDATE for cache eviction and ID
attachment after INSERT. A blanket UPDATE rejection breaks normal flows.
The verifier route is cleaner and matches what an external auditor
would do anyway.

**Test coverage:** `tests/adversarial/test_padv_p4_chain.py` —
`test_attack_payload_json_tamper_detected_by_verify_chain`,
`test_attack_signature_tamper_detected_by_verify_chain`,
`test_attack_event_hash_tamper_detected`,
`test_attack_prev_event_hash_splice_detected`.

## Residual risk — `aggregation.search_capability(include_local=True)`

**Status:** Documented residual. Cost-raising defense (C). Not fixed
in MVP.

The python API `search_capability` accepts `include_local=True` to
return NONE-visibility halos — used by owner/parent direct paths. The
RPC endpoint `/v1/query_capability` does NOT expose this parameter, so
external HTTP clients cannot smuggle it. But python-API consumers
running inside the same trust boundary as the registry could pass it
without authentication.

For MVP we treat this as a python-API affordance: callers within the
registry's trust boundary (P5 composite parents, P7 demo orchestrator)
have authority to look up their own subgraph. The RPC layer is the
trust boundary; it doesn't expose the bypass.

**Test coverage (regression guard):**
`tests/adversarial/test_padv_p4_visibility.py` —
`test_attack_query_capability_rpc_does_not_expose_include_local` pins
the RPC contract: the endpoint never returns LOCAL halos to anonymous
or stranger callers, even with smuggled query parameters.

## Summary

- **Found:** 24 attack tests across 4 surfaces (chain integrity,
  visibility, anti-tamper, concurrency).
- **Defense gaps fixed:** 2.
  - F1: cross-actor impersonation (write-time check + tests).
  - F2/F3: in-place tamper + index drift (verifiers + tests).
- **Residual risks (documented):** 1.
  - python-API `include_local=True` bypass (not exposed via RPC).
- **All 24 attack tests pass on this branch.**
