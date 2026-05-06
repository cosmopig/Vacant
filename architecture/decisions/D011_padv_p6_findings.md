# D011 -- Padv-P6 Findings: envelope chain, halo MITM, MCP parity, idempotency residual

**Date:** 2026-05-06
**Author:** Padv-P6 (adversarial review of PR #8)
**Affected components:** `src/vacant/protocol/envelope.py`,
`src/vacant/protocol/dispatch.py`, `src/vacant/protocol/serve.py`,
`src/vacant/protocol/mcp_adapter.py`,
`src/vacant/protocol/replay_protect.py`,
`src/vacant/protocol/capability_card.py`

---

## Background

The Padv pass on `feat/p6-protocol` (PR #8) probed the four
dispatch-listed P6 attack surfaces:

1. Envelope replay across pairs.
2. Halo-to-direct call mismatch (MITM).
3. MCP bridge bypass.
4. Idempotency-key collision.

**No new defense gaps were found.** The existing P6 implementation
correctly defends 1, 2, and 3. Surface 4 is a documented residual:
the MVP does not implement an idempotency cache, but the per-pair
seq+chain replay protection covers the security-relevant subset of
the attack -- the unhandled case is "legitimate retry returns cached
response", which is a usability cost, not a security flaw. The fix
is queued as future work and a regression-guard test pins the current
behaviour.

## Finding 1 -- Envelope replay (CONFIRMED COVERED)

**Status:** Defense holds.

**Attack:** `dispatch/Padv_review.md` §"Envelope replay across pairs".
Capture envelope `(A -> B, seq=1)` and replay as `(A -> C, seq=1)`,
or replay against the same `(A -> B)` pair, or skip seq, or fork the
chain by submitting an arbitrary `prev_envelope_hash`.

**Defense layered (P, write-time):**

- The envelope's `signing_dict()` covers `(from, to, seq, ts, prev,
  idem, payload)`. Tampering any of these breaks the Ed25519 signature
  before any business logic runs.
- `serve.py` and `mcp_adapter.py` short-circuit with HTTP 421 / a
  structured error if `to_vacant_id != self_form.identity` (cross-pair
  forgery cannot succeed even before sig verification).
- `replay_protect.InMemoryReplayStore` / `SqliteReplayStore` enforce
  *strict* `+1` monotonicity AND `prev_envelope_hash == stored chain_tip`.
  A replay or skip raises `ReplayDetectedError`; a forged prev_hash
  raises `ChainForkError`.
- The replay store is per-pair, so advancing `(A -> B)` does not
  contaminate `(A -> C)`.

**Test coverage:** `tests/adversarial/test_padv_p6_envelope_replay.py`
-- `test_attack_cross_pair_replay_swap_to_breaks_signature`,
`test_attack_cross_pair_replay_at_serve_layer_returns_421`,
`test_attack_same_envelope_replayed_to_same_pair_rejected`,
`test_attack_serve_returns_409_on_replay`,
`test_attack_skip_seq_rejected`,
`test_attack_forged_prev_hash_rejected`,
`test_attack_tamper_seq_after_sign_breaks_signature`,
`test_attack_tamper_prev_hash_after_sign_breaks_signature`,
`test_attack_tamper_payload_after_sign_breaks_signature`,
`test_attack_separate_pairs_have_independent_seq_counters`.

## Finding 2 -- Halo-to-direct call MITM (CONFIRMED COVERED)

**Status:** Defense holds.

**Attack:** `dispatch/Padv_review.md` §"Halo-to-direct call mismatch".
The capability card discovered via the registry points to the victim's
endpoint URL, but at network time the request lands on an attacker-
controlled host. The attacker either:

- Returns a response signed by the attacker's own key (impersonating
  the victim).
- Substitutes their own `from_vacant_id` in the response.
- Publishes a forged capability card with a rewritten endpoint URL.

**Defense layered (P, write-time):**

- `CapabilityCard.signing_payload()` includes `endpoint`, so any
  rewrite of the endpoint after the victim signed the card breaks
  `card.verify()`. `dispatch.call_local` rejects any card that does
  not verify.
- `dispatch.call_local` verifies the response envelope under
  `target_card.vacant_id.verify_key()` -- not the URL host's TLS cert.
  A MITM has no access to the victim's signing key, so the response
  cannot be forged. (TLS pinning is a defense-in-depth nice-to-have,
  not the primary control.)
- The dispatcher does not POST any payload before the card check
  runs, so a fabricated card with no signature cannot trick a
  requester into leaking the request body to the attacker's URL.

**Test coverage:** `tests/adversarial/test_padv_p6_halo_mitm.py` --
`test_attack_endpoint_rewrite_after_sign_breaks_card_signature`,
`test_attack_mitm_response_signed_by_attacker_rejected`,
`test_attack_response_with_attacker_from_id_rejected`,
`test_attack_unsigned_capability_card_rejected`.

## Finding 3 -- MCP bridge parity with A2A (CONFIRMED COVERED)

**Status:** Defense holds.

**Attack:** `dispatch/Padv_review.md` §"MCP bridge bypass". An
MCP-aware client calls `tools/call name="vacant_call"` and tries
to skip the envelope-verify or replay-protect checks that
`/a2a/message/send` enforces.

**Defense layered (P, write-time):**

`VacantAsMCPServer.call_tool` runs the *same* sequence as
`serve.py`'s `/a2a/message/send`:

1. Parse the envelope from the JSON-RPC body.
2. Check `to_vacant_id == self_form.identity` (else structured error).
3. Check `can_be_called(self_form.runtime_state)` (rejects SUNK /
   ARCHIVED / HIBERNATING / STALE).
4. `request_env.verify_or_raise(...)` against the sender's pubkey.
5. `replay_store.check_and_advance(request_env)` against the *same*
   shared store the A2A path uses.
6. Dispatch to the behaviour callback.
7. Return a response envelope advanced on the `(self -> caller)`
   chain via `make_response_envelope`.

So an attacker cannot use MCP to issue `seq=1` and then A2A to issue
`seq=1` again on the same pair: both paths share the replay store.

**Test coverage:** `tests/adversarial/test_padv_p6_mcp_bypass.py` --
`test_attack_mcp_unsigned_envelope_rejected`,
`test_attack_mcp_replay_rejected_via_shared_replay_store`,
`test_attack_mcp_sunk_vacant_does_not_accept_calls`,
`test_attack_mcp_describe_does_not_leak_secrets`,
`test_attack_mcp_and_a2a_share_replay_state`,
`test_attack_mcp_misdirected_envelope_rejected`.

## Residual risk -- idempotency cache is future work

**Status:** Documented residual. Cost-raising defense (C). The
per-pair seq+chain is the structural mitigation.

**Attack:** `dispatch/Padv_review.md` §"Idempotency key collision".
A caller-supplied `idempotency_key` is intended (per spec) to be used
by the server to dedupe legitimate retries. If the server
caches by idem-key alone, an attacker who can guess or observe a key
could submit a *different body* with the same key and either receive
a stale cached response or corrupt the cache.

**Defense layered today:**

- `idempotency_key` is in the envelope's signed scope, so an attacker
  cannot rewrite an honest caller's key without invalidating the
  signature.
- Two envelopes with the same idem-key but different bodies have
  different `compute_hash()` values; a future idem-cache could detect
  the collision via body-hash comparison.
- The MVP server has no idempotency cache. The per-pair (sequence_no,
  chain_tip) check rejects *every* replayed envelope independent of
  idem-key, so the security surface "attacker reuses idem-key" is
  collapsed to "would the server return a stale response?" -- and the
  answer is no, because there's no cache to return from.

**What's left for future work:**

A server-side `(caller, idem_key) -> (body_hash, response_envelope)`
map keyed inside the replay store. With it, legitimate retries return
the cached response (usability) and same-key/different-body
collisions are rejected (the attack the dispatch describes).
P4's registry already has a `register:` idempotency layer
(`register_halo` / `register_event`) that we can lift the design from.

**Test coverage (regression guards):**
`tests/adversarial/test_padv_p6_idempotency.py` --
`test_attack_idempotency_key_tamper_breaks_signature`,
`test_attack_same_idem_different_body_distinct_envelope_hashes`,
`test_attack_same_idem_same_body_replay_caught_by_seq_chain`,
`test_attack_idem_key_reused_across_pairs_independent_state`,
`test_attack_jsonrpc_id_falls_back_to_envelope_hash_when_idem_empty`.

Plus `tests/adversarial/test_padv_p6_residual.py::test_residual_idempotency_cache_is_future_work`
pins the current absence of an idem-cache so a future PR has to
explicitly remove that pin when wiring the cache.

## Other residual -- MCP-client substrate trust model

**Status:** Acknowledged limitation. Cost-raising defense (C).

The `MCPClientSubstrate` is for vacant->external-tool calls (MCP
servers are not necessarily vacants). MCP has no signed-identity
concept, so substrate responses are trust-on-first-use. Vacants must
treat MCP-substrate output as untrusted text -- never as a
substitute for vacant attestation. The substrate's `proof` field
carries only `server_url`, NOT a vacant-signed key id, which makes
the trust model explicit.

`tests/adversarial/test_padv_p6_residual.py::test_residual_mcp_client_substrate_does_not_authenticate_server`
pins this as documented behaviour (a lying transport is not
detected, by design -- the consuming vacant is responsible for
treating tool output as such).

## Summary

- **Probed:** 4 dispatch-listed P6 attack surfaces.
- **Defense gaps fixed:** 0 -- the existing P6 implementation is
  layered and correct.
- **Residual risks (documented + regression-guarded):** 2.
  - Idempotency cache (future work, P3-style "lookup_idempotency"
    contract to be lifted from P4 registry).
  - MCP-client substrate trust model (acknowledged: MCP has no
    signed-identity layer; consuming vacants must treat output as
    external).
- **Tests added:** 25 attack tests across 5 files in
  `tests/adversarial/`, plus regression guards for the residuals.
- All tests pass on this branch.
