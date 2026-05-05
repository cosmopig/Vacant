# P3 — Reputation

## Goal

Implement P3 Reputation: 5-dimensional Beta posterior, UCB exploration, STYLO-distance discount rollover, cold-start mechanism, same-* detection (controller / substrate / stylo), and portability_factor.

## Read first (in order)

1. `/CLAUDE.md`
2. `architecture/components/P3_reputation.md` — the spec
3. `architecture/research/T1_behavioral_fingerprint.md` — STYLO Vec16 + PROBE
4. `architecture/research/T5_same_controller.md` — same-controller detection methodology
5. `architecture/THEORY_V5.md` §3.6 (cold start), §4.1 (review eligibility), §4.3 (lineage as evolution subject), §6 (defense framing — cost-raising not preventing)

## Repo state at start

- P0, P1, P2, P4 merged.
- `src/vacant/reputation/` has only `__init__.py` and `errors.py`.

## Scope

### 1. Posterior — `src/vacant/reputation/posterior.py`

- `Beta(BaseModel)` — `alpha: float`, `beta: float`. Methods: `mean`, `variance`, `update(positive_weight, negative_weight)`.
- `Beta5D(BaseModel)` — five `Beta`s for `factual`, `logical`, `relevance`, `honesty`, `adoption`.
- Per-substrate: keyed by `(vacant_id, substrate_id)` so the same vacant on different LLMs has separate posteriors.
- Update rule: positive event → α += w; negative → β += w; w from reviewer's own reputation (recursive trust weighting). Recursion terminates at L0 root weights (defined in P2).

### 2. UCB — `src/vacant/reputation/ucb.py`

- `ucb_score(beta: Beta, total_calls: int, exploration_c: float = 2.0) -> float` — UCB1.
- `ucb_with_lineage_prior(beta, parent_beta, depth) -> float` — lineage members inherit a fraction of parent's posterior as prior; depth-aware decay.
- New vacants get an exploration bonus that decays with call count.

### 3. STYLO discount — `src/vacant/reputation/discount.py`

- `compute_discount(stylo_distance: float) -> float` — function that returns a multiplier in (0, 1] applied to old attestation weight when STYLO drift is large between epochs.
- `apply_discount(beta: Beta, discount: float) -> Beta` — shrinks effective sample size (α and β both scaled).
- This is the mechanism that bites self-evolution at the **individual-vacant level** — it's a feature, not a bug. **Lineage resets the clock** (§4.3) — a child vacant has its own clean posterior with optional inherited prior.

### 4. Cold start — `src/vacant/reputation/cold_start.py`

The §3.6 mechanism. Five components:

- **UCB exploration** — already in §2
- **Birth-path startup signals** — Path Zero / B / C / D have different starting weights; spec gives the values
- **Niche uniqueness bonus** — capability rarity bonus (rarer → higher initial visibility)
- **Low-stakes probes** — small-impact tasks routed to new vacants (define a "stake threshold" function)
- **Idle peer review** — older vacants, when idle, are scheduled to review newer (define an idle-detection signal)

### 5. Same-* detection — `src/vacant/reputation/same_detect.py`

Three lines, each returns a `SignalStrength` (float in [0,1]) + `suspected_cluster` (set of `VacantId`):

- **Same-controller** — timing/IP/ASN clustering per T5
- **Same-substrate** — shared LLM fingerprints
- **Same-stylo** — behavioral fingerprint similarity (consumes P1's `shadow_self` embedding)

**Frame as cost-raising, not preventing** — the output biases peer-review weight (reviews from suspected-collusion sets count for less), it does not block.

### 6. Portability factor — `src/vacant/reputation/portability.py`

- `compute_portability(vacant_id, substrates_served: list[str], success_rate_per_substrate: dict[str, float]) -> float`
- Returns a small reputation bonus for vacants successfully serving across multiple substrates (rewards ecological contribution).

### 7. Aggregator — `src/vacant/reputation/aggregator.py`

The public API surface that the registry queries. This is the `ReputationProtocol` that P4 is already importing as a stub:

- `get_reputation(vid: VacantId, substrate: str) -> Beta5D`
- `get_ranked(capability_query: str, n: int) -> list[tuple[VacantId, float]]` (UCB-scored)
- `record_review(reviewer: VacantId, target: VacantId, dimensions: dict[str, float], substrate: str) -> None`

**Reviewer eligibility check**: refuse reviews from vacants where `can_review(state) is False` (P1's state machine). Refuse to count reviews from suspected-collusion clusters above a threshold (downweight per same-* signal).

## Tests

- `tests/unit/test_posterior.py` — Bayesian update math; reviewer weighting recursion (terminates at L0 root weights)
- `tests/unit/test_ucb.py` — new vacants beat established when uncertainty is high; convergence — high-quality vacants dominate after N reviews
- `tests/unit/test_discount.py` — large STYLO drift halves effective sample size; small drift preserves it
- `tests/unit/test_cold_start.py` — simulation: 1 new vacant + 9 established; after 100 ticks the new vacant has had >0 calls
- `tests/unit/test_same_detect.py` — each line fires on a synthesized colluding pair; doesn't fire on independent pair
- `tests/property/test_reputation_invariants.py`:
  - posterior never negative
  - total weight monotonic until discount rollover
  - SUNK / ARCHIVED vacants' reviews are rejected
- `tests/integration/test_reputation_e2e.py` (`@pytest.mark.slow`) — 20-vacant network, 1000 calls, reputation distribution stabilizes with high-quality on top, low-quality below 0.3 mean across dimensions

Coverage target on `src/vacant/reputation/`: ≥90%.

## Acceptance

- Cold-start sim shows new vacants get traction within 100 ticks
- Same-* detection's three lines documented in PR description with rationale + attack model
- Reviews from SUNK/ARCHIVED vacants are rejected at the API surface (test it)
- All previous criteria hold

## Output

PR titled **"P3: reputation — Beta5D, UCB, STYLO discount, cold start, same-* detection"**.

## Out of scope

- Training a real STYLO model. Use a stub embedding (last-N-outputs hashed → 16-dim) and TODO-comment where the real model plugs in.
- Federated reputation aggregation (post-MVP)
