# P2 — Identity

## Goal

Implement P2 Identity: multi-layer identity (L0–L3), wash cost, federation/attestation hooks. P2 owns Ed25519 keypair management above the primitives P0 placed in `core/crypto.py`.

## Read first (in order)

1. `/CLAUDE.md`
2. `architecture/components/P2_identity.md`
3. `architecture/research/P2_identity_research.md`
4. `architecture/research/T4_attestation_bootstrap.md` (federation root strategy)
5. `architecture/THEORY_V5.md` §2 (identity), §6 (defense framing — wash cost cited there)

## Repo state at start

- P0 merged. (P1 may or may not be merged — independent of this work.)
- `src/vacant/identity/` exists but only has `__init__.py` and `errors.py`.

## Scope

### 1. Key lifecycle — `src/vacant/identity/keys.py`

- `KeyVault(ABC)` interface: `store(key_id, signing_key)`, `load(key_id)`, `delete(key_id)`. Real HSM/secure-enclave is a TODO comment, not implementation.
- `FileVault(KeyVault)` — encrypted-at-rest file storage; key passed via env or argument (never logged).
- `InMemoryVault(KeyVault)` — for tests.
- `rotate_key(old_signing_key, logbook) -> tuple[new_signing_key, LogEntry]` — emits a `KEY_ROTATION` entry with `old_pubkey_hash` and signature from the OLD key proving custody, plus signature from the NEW key proving the rotation. Both must be verifiable later.
- `revoke_key(signing_key, logbook, reason) -> LogEntry` — terminal; this vacant cannot sign new entries after.

### 2. Layered identity — `src/vacant/identity/layers.py`

Use `typing.NewType` or distinct Pydantic types so misuse is a type error:

- `L0Identity` — raw VacantId (just a key)
- `L1Identity` — VacantId + verified Logbook
- `L2Identity` — L1 + signed CapabilityCard
- `L3Identity` — L2 + ≥N peer attestations (N from spec; default 3)

Promotion functions: `promote_to_l1(vid, logbook) -> L1Identity | None`, etc. Each verifies all required invariants before returning.

A function expecting `L3Identity` must reject `L1Identity` at type-check time. Include a `mypy reveal_type` test demonstrating this.

### 3. Wash cost — `src/vacant/identity/wash_cost.py`

Implement the cost calculation per `P2_identity.md` §3. Inputs:

- `claimed_history_depth: int` — how many log entries the new identity claims to inherit
- `attestation_count: int` — how many peers have signed it
- `substrate_diversity: int` — number of distinct substrate IDs it claims to operate on

Output: `WashCost` (network-cycles units; type-tagged).

Function: `compute_wash_cost(...) -> WashCost`.

The cost must be **monotonic** in `claimed_history_depth` and increasing with false-claim weight (parameterize so tests can vary).

### 4. Federation — `src/vacant/identity/federation.py`

- `RootSet` — M-of-N attestation roots per T4 (start: 2-of-5, evolves to 3-of-9; expressed as config).
- `FederatedAttestation` envelope (signed by ≥M roots).
- `verify_federated(attestation, rootset) -> bool` — accepts iff M valid signatures from N declared roots.
- `rotate_root(rootset, old_root, new_root, signatures) -> RootSet` — handles key rotation across the root set.

### 5. Peer attestation — `src/vacant/identity/attestation.py`

- `PeerAttestation(BaseModel)` — `attester: VacantId`, `attestee: VacantId`, `claim: str` (capability or trait), `signature: bytes`, `issued_at: datetime`, `expires_at: datetime`.
- `verify_attestation(att, attester_pubkey) -> bool` — signature + freshness window.
- `revoke_attestation(att, attester_signing_key) -> RevocationRecord` — signed revocation that any holder of `att` can present to invalidate it.

### 6. Tests

- `tests/unit/test_keys.py` — keygen, sign roundtrip, rotation chain integrity (rotation event references `old_key_hash`), revocation terminal.
- `tests/unit/test_layers.py` — promotion paths; type-level safety (mypy reveal_type).
- `tests/unit/test_wash_cost.py` — monotonicity property; cost increases with false-claim weight.
- `tests/property/test_attestation_chain.py` — hypothesis: chain of N peer attestations with one tampered link is always rejected.
- `tests/integration/test_federation_bootstrap.py` (`@pytest.mark.slow`) — 2-of-5 rootset issues attestation; verifier accepts; with 1 root invalid still verifies; with 2 roots invalid fails; rotation preserves verifiability of pre-rotation attestations.

Coverage target on `src/vacant/identity/`: ≥90%.

## Acceptance

- Type system catches L0–L3 misuse at type-check time (PR description includes a `mypy` snippet showing the rejected misuse).
- `compute_wash_cost` matches the formula in `P2_identity.md` §3 within rounding.
- All previous criteria hold.

## Output

PR titled **"P2: identity — keys, layers, wash cost, federation"**.

## Out of scope

- Storing identity claims in the registry table (P4)
- Reputation impact of wash cost (P3 consumes the cost value)
- Real HSM integration
