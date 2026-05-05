# D004 — P2 Identity Spec Reconciliation

**Date:** 2026-05-05
**Author:** P2 implementation session
**Affected components:** P2 Identity / `core/constants.py` / `architecture/CONSTANTS.md`

---

## Background

`dispatch/P2_identity.md` and `architecture/components/P2_identity.md` differ
on a few points; this ADR pins the resolved interpretation for the P2 PR.

### Issue A — wash cost inputs

`components/P2_identity.md` §3.4 frames wash cost in terms of an economic
formula:

```
WashCost(t) = c_attest(t) + c_stake(t) + c_history_loss + opportunity_cost(T_ramp)
```

`dispatch/P2_identity.md` §3 frames wash cost over a *much narrower* set of
inputs that this code can actually compute:

```
inputs:  claimed_history_depth, attestation_count, substrate_diversity
output:  WashCost (network-cycles units; type-tagged)
properties: monotonic in claimed_history_depth;
            increasing in false_claim_weight (parameterised)
```

The component spec's `c_stake / c_history_loss / opportunity_cost(T_ramp)`
are economic / behavioural quantities the runtime cannot evaluate on its
own — they need P3 (reputation), P4 (registry traffic stats), and a
real-money escrow oracle (which the MVP does not have).

### Issue B — `vacant_id` digest scheme

`components/P2_identity.md` §3.1 sketches `vacant_id = multibase58btc(blake3(pk)[:24])`.
P0's `VacantId` already wraps the raw 32-byte Ed25519 public key directly
(blake2b is the canonical hash; blake3 is not a dep). The dispatch §1 asks
P2 to *manage* keypair lifecycle — not to redefine `VacantId`.

### Issue C — federation rootset thresholds

`research/T4_attestation_bootstrap.md` and `architecture/CONSTANTS.md`
agree on **2-of-5** for MVP and **3-of-9** as the long-term target. The
component spec also mentions Sigstore's 3-of-5; that's a different
network's parameters and not normative for Vacant.

### Issue D — `PeerAttestation` freshness window

The dispatch §5 names `expires_at` on `PeerAttestation` but doesn't pin a
default. `architecture/CONSTANTS.md` already carries
`Peer attestation freshness window | 30 days (default) | P2_identity §4`.

## Decision

### A. Wash cost ships the dispatch's narrow formula

`identity/wash_cost.py` implements the dispatch §3 contract verbatim:

```python
def compute_wash_cost(
    claimed_history_depth: int,
    attestation_count: int,
    substrate_diversity: int,
    *,
    false_claim_weight: float = WASH_COST_FALSE_CLAIM_WEIGHT_DEFAULT,
    weights: WashCostWeights | None = None,
) -> WashCost: ...
```

with these properties tested:

- monotonic non-decreasing in `claimed_history_depth`
- monotonic non-decreasing in `attestation_count`
- monotonic non-decreasing in `substrate_diversity`
- monotonic non-decreasing in `false_claim_weight` whenever
  `claimed_history_depth >= 1` (the false-claim cost is "what you would
  pay to fabricate this much history")

Concrete unit costs (`history_unit_cost`, `attestation_unit_cost`,
`substrate_unit_cost`) live in `WashCostWeights` with documented
defaults; tests vary `false_claim_weight` to verify the dispatch's
"increasing with false-claim weight" property.

The richer §3.4 economic formula (`c_stake / c_history_loss /
opportunity_cost`) is left as future work and noted in the docstring.
P3 will plug economic inputs into a wrapper later; this PR's API does
not preclude that wrapper.

### B. `VacantId` is unchanged; `vacant_id_did_key` is added

`VacantId` keeps its P0 byte-wrapper semantics. A pure helper
`vacant_id_did_key(vid: VacantId) -> str` returns the
`did:key:z<multibase58btc(0xed01 || pubkey)>` string for the dispatch's
use cases (Capability Card, attestation envelopes). The encoding follows
W3C `did:key` §6.1 with the Ed25519 multicodec prefix `0xed01`.

This avoids touching P0's serialisation (which P0 / P1 tests already
depend on) while still exposing the textual form §3.1 needs.

### C. RootSet defaults to 2-of-5

`identity/federation.py` constructs a default `RootSet(threshold=2,
roots=...)`. The class accepts any (M, N) where `1 <= M <= N`, so the
3-of-9 evolution is a config change, not a code change. Constants
`FEDERATION_ROOT_THRESHOLD_MVP = 2`, `FEDERATION_ROOT_COUNT_MVP = 5`,
`FEDERATION_ROOT_THRESHOLD_TARGET = 3`, `FEDERATION_ROOT_COUNT_TARGET = 9`
are added to `core/constants.py` and `architecture/CONSTANTS.md`.

### D. `PeerAttestation` defaults to a 30-day freshness window

`identity/attestation.py` defaults `expires_at = issued_at +
PEER_ATTESTATION_FRESHNESS_WINDOW_DAYS` (= 30 days, already in
CONSTANTS.md). Callers can override per-attestation; verification rejects
attestations whose `expires_at < now()` regardless of signature validity.

`PEER_ATTESTATION_FRESHNESS_WINDOW_DAYS = 30` is mirrored into
`core/constants.py`.

## Consequences

- The wash cost API the runtime can call is concrete and has the
  monotonicity property the dispatch acceptance criteria require, while
  the richer economic framing in §3.4 stays accessible as future work.
- `VacantId` keeps its P0 contract; the `did:key` textual form is a
  one-liner helper for callers that need it.
- The federation rootset is parameterised, so the T4 evolution path
  (2-of-5 → 3-of-9) is a config edit.
- Identity-adjacent constants live in one place (`core/constants.py`)
  and are mirrored into `architecture/CONSTANTS.md` per CLAUDE.md.
