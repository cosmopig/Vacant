# Security Policy

## Project status

Vacant is an undergraduate capstone project (2026), not a battle-tested production system. Treat any deployment beyond local demo as an experimental research artifact. The threat model is documented in [`architecture/THEORY_V5.md`](architecture/THEORY_V5.md) §6 (38-attack matrix, P/D/C defense levels).

## Reporting a vulnerability

**Do not** open a public issue for security-sensitive findings. Instead:

1. Email the maintainer at `cosmo20050801@gmail.com` with subject prefix `[VACANT-SEC]`.
2. Include: reproduction steps, affected commit hash, your assessment of impact, suggested fix if any.
3. Allow up to 72 hours for an initial response. Capstone-project bandwidth — not a corporate SOC.
4. Coordinated disclosure preferred: maintainer will work with you on a timeline before any public discussion.

For non-sensitive defense gaps (an attack scenario the design doesn't yet cover but is interesting to discuss publicly), open an issue using the **Defense gap** template.

## Scope of "security relevance"

In Vacant's threat model, the following are explicitly in scope:

- **Identity layer** (`src/vacant/identity/`): keypair custody, wash-cost evasion, attestation forgery, federation root rotation correctness.
- **Reputation layer** (`src/vacant/reputation/`): Sybil rings, dimension imbalance attacks, sniping, honesty laundering, STYLO discount evasion.
- **Registry layer** (`src/vacant/registry/`): halo replay, Merkle snapshot forgery, audit log tampering, visibility downgrade, concurrent-write race.
- **Composite layer** (`src/vacant/composite/`): Tree-Only bypass, graduation laundering, sibling collusion ring, manifest tampering.
- **Protocol layer** (`src/vacant/protocol/`): envelope replay across pairs, MITM via halo–direct call mismatch, MCP bridge bypass, idempotency-key collisions.

These are tracked in `tests/adversarial/` with at least 3 attack tests per surface. New attack vectors are gladly accepted as adversarial-review PRs (see [`dispatch/Padv_review.md`](dispatch/Padv_review.md)).

## Out of scope

The following are explicitly **not** in scope (consistent with the spec's "honestly stated limitations"):

- DoS attacks at the transport layer (handled by deployment, not by Vacant itself).
- Quantum-cryptography attacks (Ed25519 will need a post-quantum migration; out of MVP scope).
- Bugs in `pynacl`, `cryptography`, `sqlmodel`, `fastapi`, `httpx`, or any other dependency. Report those upstream.
- Attacks that require breaking the foundational `Key Custody / Controller Autonomy` assumption (THEORY_V5 §0.1). Vacant's correctness chain begins from "the keypair holder controls their own actions"; defending the *physical* keypair is the operator's responsibility.

## Honest residual risk

The spec marks 13 honest open questions (`H1`–`H13` in THEORY_V5). These are *known* limitations the project doesn't claim to fully solve, only to honestly disclose. Examples:

- Reputation gaming under Skalse 2022 impossibility (no proxy reward is fully un-game-able; Vacant's claim is *cost-raising*, not *prevention*).
- Same-* detection covers cost-raising scenarios but adaptive evasion is acknowledged.
- Federation root rotation history (currently being addressed in PR `feat/a8-federation-rotation`).

If you find a gap *not* listed in H1–H13 or `architecture/decisions/D###_*.md`, that's a finding worth reporting.

## Supported versions

Pre-1.0. Only `main` is supported. Once the capstone defense passes and the project receives a 1.0 tag, this section will be updated with a real support window.

| Version | Status |
|---|---|
| `main` | Active |
| pre-1.0 tags | Not supported |

## What we will and won't do

**Will**:
- Acknowledge reports within 72 hours.
- Assess severity using the spec's defense-level taxonomy (P / D / C).
- Coordinate disclosure with the reporter.
- Credit reporter in `CHANGELOG.md` (unless they prefer anonymity).

**Won't**:
- Pay bug bounties (capstone-project budget = 0).
- Embargo a finding that's already public elsewhere.
- Delete or rewrite git history to "hide" a finding (transparency over comfort).
