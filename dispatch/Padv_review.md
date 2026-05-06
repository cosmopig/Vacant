# Padv — Adversarial review pass

## When to run

After **any** PR that touches one of:

- `src/vacant/identity/` (P2)
- `src/vacant/reputation/` (P3)
- `src/vacant/registry/` (P4)
- `src/vacant/composite/graduation.py` (P5)
- `src/vacant/protocol/replay_protect.py` (P6)

These are the load-bearing security/integrity surfaces. The project went through 3 rounds of codex adversarial review with `no fatal issues remain`. **Do not regress that property.**

## Goal

Find at least **3 attacks** the changed code might enable, and add tests covering them. If you cannot find 3, you didn't try hard enough — re-read `architecture/THEORY_V5.md` §6 (defense framing) and `architecture/research/T5_same_controller.md`.

## How to run as a separate Claude Code session

1. Open a fresh Claude Code session against the repo
2. Paste this entire prompt
3. Add at the end:
   ```
   The PR to review is #<NUMBER>. Open a follow-up PR
   "Padv #<NUMBER>: adversarial review" with new tests.
   Do not merge the original PR until your follow-up is also approved.
   ```

## Read first

1. `/CLAUDE.md`
2. The PR diff (`gh pr diff <NUMBER>` or read the GitHub UI)
3. `architecture/THEORY_V5.md` §6 — the threat model and 38-attack matrix
4. `architecture/components/P*_*.md` for the spec the PR claims to implement
5. `architecture/research/T5_same_controller.md` (if reputation-related)
6. `architecture/research/T6_substrate_identity.md` (if substrate-related)

## Scope — what to attack

For each surface the PR touches, generate at least 3 distinct attacks. **Test, don't just describe.** Each attack becomes a `pytest` test that:

- Sets up the precondition the attacker needs
- Performs the attack steps
- Asserts the defense detects/raises/downweights/blocks (per the spec's "defense level" — P/D/C)

### Attack inventory by surface

#### P2 Identity attacks to consider

1. **Key rotation grindstone** — rotate keys in rapid succession to obscure history. Detection: rotation chain inspection should show monotonic timestamps + cumulative cost.
2. **L3 promotion via colluding L1s** — same controller signing as multiple L1 vouchers. Detection: same-controller signal must downweight.
3. **Wash cost evasion** — claim minimal history depth then quietly inflate via post-promotion writes. Detection: WashCost recomputation on each capability claim.
4. **Federation root impersonation** — present M signatures from N declared roots where ≥1 signature is forged. Detection: per-root signature verify.
5. **Attestation freshness exploit** — reuse expired peer attestation. Detection: freshness window enforced at consumer.
6. **Revocation race** — present an attestation that has been revoked but revocation hasn't propagated. Detection: revocation record check + Merkle snapshot freshness.

#### P3 Reputation attacks to consider

1. **Sybil ring** — N colluding vacants give each other 5-star reviews. Detection: same-controller / same-substrate / same-stylo signals.
2. **Dimension imbalance** — pump only F while leaving A low. Detection: dimension correlation alert > 0.6 fires.
3. **Sniping** — many high-quality reviews from one peer in short window targeting a competitor downward. Detection: per-target review rate limit (3/24h).
4. **Honesty laundering** — self-eval = 0.99 across the board. Detection: redteam_probe gap signal.
5. **Adoption stuffing** — fake adoption events. Detection: adoption events must trace to a verifiable callsite.
6. **STYLO discount evasion** — small drift each epoch to stay under threshold while accumulating change. Detection: cumulative drift over N epochs.
7. **Post-merger reputation poaching** — D4 lineage merge to absorb reputation from a high-rep parent without the merging vacant earning it. Detection: lineage-merge consent + post-merge cold-start period.

#### P4 Registry attacks to consider

1. **Halo replay** — replay an old halo with stale capability_card. Detection: sequence-number monotonicity + halo_version increments.
2. **Merkle snapshot forge** — submit a forged snapshot root. Detection: independent verifier MUST recompute from raw rows.
3. **Visibility downgrade** — flip an active vacant to LOCAL to evade discovery without recording it. Detection: state transitions are signed log entries.
4. **Audit log tamper** — DELETE on `audit_log`. Detection: SQLite TRIGGER preventing DELETE.
5. **Concurrent write race** — two writers, last-write-wins corruption. Detection: per-vacant sequence_no UNIQUE constraint + transaction.
6. **LOCAL leak** — query a LOCAL vacant from a non-owner identity. Detection: visibility check at RPC layer, not just at aggregation.

#### P5 Composite attacks to consider

1. **Tree-Only bypass** — closed child calls outside its tree by spoofing the call origin header. Detection: middleware verifies caller signature against tree manifest.
2. **Graduation laundering** — graduate a child immediately after its first review (insufficient evidence). Detection: rate limit + 3-layer check + min-review-count threshold.
3. **Sibling collusion ring** — three siblings give each other reviews to inflate before graduation. Detection: same-tree signal applied as discount in P3.
4. **Manifest tampering** — modify ChildManifest after parent signs but before child signs. Detection: both signatures cover the canonical-json of the same payload.

#### P6 Protocol attacks to consider

1. **Envelope replay across pairs** — replay an envelope from (A→B) as (A→C). Detection: per-pair sequence chain (target_id is in signed scope).
2. **Halo-to-direct call mismatch** — discovery returns vacant V's endpoint, but attacker MITMs the direct call. Detection: TLS pinning to endpoint key + envelope signature verifies against vacant's key, not endpoint.
3. **MCP bridge bypass** — call vacant's underlying substrate directly via the MCP server, skipping the runtime's logbook write. Detection: MCP server path forces logbook write before returning.
4. **Idempotency key collision** — replay with same idempotency_key on a different request body. Detection: server stores body hash next to key.

## Acceptance

PR titled **"Padv #<NUMBER>: adversarial review"** with:

- ≥3 new attack tests per affected module
- Each test references the spec section that defines the defense
- All tests **pass** (defense holds) — if any fail, fix the original code on the same branch and document the fix in PR description
- PR description summarizes findings: "Found N attacks; M had inadequate defense; fixed M; all attacks now caught."

If a defense genuinely cannot be implemented (e.g., requires a feature not in this MVP scope), open an ADR in `architecture/decisions/` documenting the residual risk and the cost-raising rationale (per Skalse 2022 framing — we don't claim impossibility-defeat).

## Out of scope

- Attacks on dependencies (pynacl, sqlmodel, fastapi) — assume those are correct
- DoS attacks — handled at deployment layer, not here
- Quantum-cryptography attacks — out of MVP scope
