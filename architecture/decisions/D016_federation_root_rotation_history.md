# D016 — Federation root rotation history

**Date:** 2026-05-06
**Author:** Pfix2 Group A8 (codex round 2 finding F12)
**Affected components:** `src/vacant/identity/federation.py`

---

## Background

`src/vacant/identity/federation.py` ships M-of-N federated attestations.
The original implementation was *point-in-time*: `verify_federated(att,
rootset)` validated `att`'s signatures against whatever single
`RootSet` the caller passed in. After a `rotate_root(...)` call,
attestations issued under the previous rootset became un-verifiable
unless the verifier independently remembered which rootset was active
when the attestation was issued.

Codex round 2 (`dispatch/Pfix2_codex_round2.md` finding F12) flagged
this as a usability and correctness gap:

- Real verifiers do not maintain a separate timeline of "which rootset
  was current at which moment."
- Without rotation history, every rotation silently retires a quorum's
  cosignatures from the past 30 days.
- The attestation envelope did not record which rootset the signatures
  were issued against, so once the rotation happened there was no
  programmatic way to recover the right rootset.

This ADR pins the data model that closes the gap.

## Why this comes after D015

D015 closed the codex round-1 findings on reputation, registry, and
demo. F12 was originally classed as a usability item; round 2's
adversarial pass elevated it to a correctness blocker because:

- A leaked old-revision root key combined with an attacker-supplied
  envelope would otherwise be indistinguishable from a legitimate
  pre-rotation attestation.
- Operators would, in practice, "verify against the current rootset
  only," silently dropping every pre-rotation attestation rather than
  walking history they did not have.

Either failure mode breaks the federated layer's integrity claim.

## Decision

### §A — `RootSet` retains a monotonic `revision`

`RootSet.revision: int` (already present in D005's
rotation-replay-resistant state hash) is now load-bearing for
historical lookup. Every successful rotation increments `revision` by
exactly one.

### §B — `RootSetHistory` is the canonical chain

```python
@dataclass(frozen=True)
class RootSetHistory:
    revisions: tuple[RootSet, ...]   # revisions[i].revision == i
```

Invariants enforced at construction:

- non-empty
- dense: `revisions[i].revision == i` for every `i`

Operations:

- `RootSetHistory.from_initial(rootset)` — start a fresh history at
  revision 0
- `history.current` — head (the active rootset)
- `history.at(revision)` — O(1) lookup of the rootset that was active
  at any past revision; raises `FederationError` if the revision is
  not in the chain
- `history.extend(new_rootset)` — append the next revision (must equal
  `current_revision + 1`)
- `history.apply_rotation(old_root=, new_root=, signatures=)` —
  ergonomic wrapper that calls `rotate_root` against `current` and
  appends the result

### §C — `FederatedAttestation` records its issuance revision

```python
class FederatedAttestation(BaseModel):
    subject: VacantId
    claim: str
    signatures: list[RootSignature]
    issued_under_revision: int = 0     # NEW
```

`signing_payload()` now mixes `issued_under_revision` into the digest:

```
hash_blake2b(subject || 0x1f || claim || 0x1f || str(revision))
```

This binds each `RootSignature` to a single revision: a signature
collected for revision `R` will not validate inside an envelope that
claims a different revision.

The default of `0` is the back-compat path for tests and existing
callers that operate against a single (initial) rootset; the digest
binding still applies — you simply stay at revision 0 for the entire
conversation.

### §D — `verify_federated` accepts `RootSet | RootSetHistory`

```python
def verify_federated(
    attestation: FederatedAttestation,
    rootset_or_history: RootSet | RootSetHistory,
) -> bool: ...
```

Behaviour:

- `RootSetHistory`: look up `history.at(att.issued_under_revision)`;
  if the revision is not in the history, return `False`. Otherwise
  apply the existing M-of-N quorum check against the resolved
  rootset.
- `RootSet`: additionally require `rootset.revision ==
  att.issued_under_revision` before running the quorum check. This
  preserves the back-compat one-rootset-per-call shape used by
  existing tests, but the revision-binding still holds — passing a
  revision-1 rootset against a revision-0 envelope returns `False`.

### §E — `build_federated_attestation` is the canonical constructor

```python
def build_federated_attestation(
    *, history, subject, claim, signatures
) -> FederatedAttestation: ...
```

Tags the attestation with `history.current_revision`. Use this instead
of constructing `FederatedAttestation(...)` directly whenever the live
history is available — it removes the foot-gun where a caller hand-
tags an envelope with a stale revision.

## Threat model

### What this defeats

- **Pre-rotation attestation loss:** verifiers no longer need to
  remember the active rootset at issuance time; the envelope tells
  them, and the history resolves it.
- **Stale-signature replay into a fresh envelope:** signatures are
  bound to a revision via the digest. Re-tagging a revision-0
  signature inside a revision-1 envelope produces a digest mismatch
  and verification fails.
- **Cross-revision moveup:** a signature collected for the current
  revision cannot be moved into a prior-revision envelope (same
  digest-binding mechanism).

### What this does NOT defeat

- **Compromised current root:** if an attacker controls a quorum of
  current-revision keys, they can issue legitimate attestations under
  the current revision. This is by design — that scenario is the
  `RootSet` membership question, not the rotation-history question.
- **Long-tail leak of pre-rotation keys:** if an attacker leaks
  enough pre-rotation keys to reach quorum at revision `R-k` (for
  some `k > 0`), they can mint historical-looking attestations.
  Defending against this is the role of revocation / time-bounded
  trust windows, which are explicitly out of scope for D016 — the
  ADR pins the *data model*, not policy on stale-revision trust.

## Migration

- Existing `FederatedAttestation`-using code keeps working: the new
  field defaults to `0` and the existing single-rootset
  `verify_federated` path is preserved (with the added revision-match
  check).
- `tests/unit/test_federation.py`,
  `tests/integration/test_federation_bootstrap.py`,
  `tests/adversarial/test_padv_p2_federation.py` all continue to
  pass without modification.
- `tests/integration/test_federation_rotation_history.py` is the new
  regression suite (12 tests covering pre-rotation verification,
  stale-revision rejection, history invariants, and the back-compat
  single-rootset path).

## References

- `dispatch/Pfix2_codex_round2.md` §A8 (the dispatch slot for this fix)
- `architecture/components/P2_identity.md` §3.5 (federated attestation)
- `architecture/research/T4_attestation_bootstrap.md` (M-of-N evolution)
- `architecture/decisions/D004_p2_identity_reconciliation.md` §C (the
  initial federation roadmap)
- `architecture/decisions/D005_padv_p2_findings.md` §1
  (rotation-replay defense — the predecessor of the `state_hash`
  binding that D016 sits next to)
