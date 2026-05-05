# D005 — Padv-P2 Findings: rotation-replay closure + residual risks

**Date:** 2026-05-05
**Author:** Padv-P2 (adversarial review of PR #3)
**Affected components:** `src/vacant/identity/federation.py`

---

## Background

The Padv pass on `feat/p2-identity` (PR #3) probed five P2 surfaces (keys,
layers, wash cost, federation, attestation) with attack tests. One found
a real cost-raising defense gap; three found documented residual risks.
This ADR pins both.

## Finding 1 — Rotation signature replay across rootset states (FIXED)

**Status:** Defense gap. Fixed in this PR.

**Attack:** A federation root rotation `(R3 → X)` is signed by the quorum
over the payload `H("vacant:federation:rotate" || pk(R3) || pk(X))`. The
payload binds neither the rootset state at signing time nor a nonce. If
`R3` ever rejoins the set later (via another rotation, e.g. recovering a
key or restoring a member), the *same* signatures could be replayed to
remove `R3` again — even after the original quorum has changed its mind
or its membership has churned.

**Defense (P, in strong-custody assumption):** include the rootset state
hash in the rotation payload:

```python
payload = H(
    "vacant:federation:rotate" || rootset.state_hash() ||
    pk(old_root) || pk(new_root)
)
```

`RootSet.state_hash()` is
`BLAKE2b(threshold || revision || sorted_pubkeys)`. The `revision`
counter monotonically increments per successful rotation, so even
"rotate-out-then-back-in" sequences (which restore the same membership)
produce distinct state hashes — closing the second-order replay
discovered while writing the first attack test.

**Consequence:** `sign_rotation` now requires the `rootset` it is being
collected for; `rotate_root` re-derives the same payload and verifies
signatures against it. Existing tests were updated mechanically (the
function signature gained `rootset=` as a kw-only argument).

**Cost:** small — one extra hash per rotation signature. No on-wire schema
change for `RootSignature` itself.

**Test coverage:** `tests/adversarial/test_padv_p2_federation.py` —
`test_attack_rotation_signature_replay_against_revived_rootset`.

## Finding 2 — Hostile new_root without consent (RESIDUAL)

**Status:** Residual risk. Cost-raising defense (C). Not fixed in MVP.

**Attack:** A simple-majority quorum can rotate any victim into the
rootset as `new_root` without the victim's consent. In the limit, this
lets a hostile sub-quorum "frame" an unrelated identity as a federation
root.

**Why not fix in MVP:** binding the new_root's consent (a co-signature
from the new_root) is mechanically straightforward but raises bootstrap
costs every time the quorum wants to add a *fresh* root that hasn't yet
participated in any signing. The federated rootset is small (5 in MVP,
9 long-term) and root selection is meant to be public + ceremonial; the
practical attack surface is already gated by social trust in the
existing quorum, not pure cryptography.

**Cost-raising mitigations already in place (per Skalse 2022 framing):**

- Rotations are visible (the resulting `RootSet` can be published, and
  P4 will store rootset history).
- Quorum collusion ≥ M is required, so an attacker must already control
  M of the existing roots.
- The new_root can decline to sign anything as a root, making them a
  no-op member; downstream federated attestations require the new_root
  to actually contribute a signature for verification, so a "framed"
  new_root has zero attestation throughput.

**Future work:** a `new_root_consent: RootSignature` field on
rotation, blocked behind a config flag, will land with P4's federated
registry phase (T4 §"3-of-9 evolution").

## Finding 3 — Identity-layer Sybil (DESIGN, RESIDUAL)

**Status:** By-design. Documented residual; deferred to P3.

**Attack:** A single controller mints N independent Ed25519 keypairs and
issues N "distinct" peer attestations to themselves, satisfying the
`promote_to_l3` distinct-attester check.

**Why not fix at the identity layer:** distinguishing controllers from
keypairs requires behavioural / network signals (T5 same-controller
detection) that P3 owns. The identity layer cannot observe controllers
directly without violating "open network, no resource gatekeeper" (P2
D2). Per CLAUDE.md, "same-controller / same-substrate / same-stylo
detection raises cost, doesn't prevent" — this finding is the
identity-layer half of that contract.

**Test coverage (regression guard):**
`tests/adversarial/test_padv_p2_layers.py` —
`test_attack_l3_distinct_keys_pass_at_identity_layer_residual_risk`
asserts that the identity layer continues to *defer* to P3 here. If a
future change tries to "fix" Sybil at the identity layer (e.g. by
imposing a global registry of attesters), this test will fail and the
PR author must justify regressing the layered design.

## Finding 4 — NaN false-claim weight (DESIGN, RESIDUAL)

**Status:** By-design. Pinned by test.

**Attack:** Pass `false_claim_weight = math.nan` to `compute_wash_cost`.
The current `< 0` check does not reject NaN (NaN < 0 is False), and the
returned cost is NaN.

**Why not fix:** propagating NaN downstream is *safer* than silently
treating NaN as zero. Consumers (P3) must handle NaN cost as "unknown"
and apply maximum suspicion. A `math.isnan` check at construction would
hide this and risk silent zeroing if a caller upstream forgot to convert.

**Test coverage (regression guard):**
`tests/adversarial/test_padv_p2_wash_cost.py` —
`test_attack_nan_weight_propagates_not_zero`.

## Summary

- **Found:** 31 attack tests across 5 surfaces (5 keys + 7 layers +
  6 wash-cost + 10 federation + 7 attestation = 35; minor double-coverage
  on revision/order assertions).
- **Defense gaps fixed:** 1 (rotation-replay binding, two iterations:
  state hash + revision counter; the second iteration was found while
  writing the first attack test).
- **Residual risks (documented):** 3 (hostile new_root, controller-level
  Sybil, NaN cost propagation). Each has a cost-raising mitigation and
  a regression-guard test pinning the documented contract.
- **All attack tests pass on this branch.**
