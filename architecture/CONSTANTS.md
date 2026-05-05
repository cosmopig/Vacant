# CONSTANTS

Single source of truth for all numeric thresholds, periods, and weights. Implementations MUST cite this file (or the underlying spec section) when defining a constant. If a value here disagrees with a spec section, the spec wins — open an ADR and update this file.

All values were extracted from `THEORY_V5.md` and `components/P1-P7` on 2026-05-05.

## Lifecycle (P1 Runtime)

| Constant | Value | Citation |
|---|---|---|
| `HEARTBEAT_BASE_PERIOD_S` | configurable per substrate; demo: `60` | THEORY_V5 §3, P1 §D2 |
| `HEARTBEAT_HIBERNATING_PERIOD_S` | `86400` (24h) | P1 §D6 line 73 |
| `HEARTBEAT_DECAYED_PERIOD_S` (alias for HIBERNATING) | `86400` (24h) | kept for back-compat; see D003 |
| `HEARTBEAT_SUNK_LIVENESS_PERIOD_S` | `600` (10 min) | THEORY_V5 §4.2 / §3 line 340 |
| `IDEMPOTENCY_WINDOW_S` | `86400` (24h) | P1 §3.2 |
| `STALE_AFTER_HIBERNATING_DAYS` | `30` | P1 §D6, line 156 |
| `WARMUP_WINDOW_S` | `86400` (24h) | P1 §3.3.1, line 191 |
| `WARMUP_REQUIRED_HEARTBEATS` | `5` | P1 §3.3.1, line 205 |
| `STYLO_DRIFT_THRESHOLD` | `3.5` (Mahalanobis) | THEORY_V5 §3, line 152 |

State transitions (event-driven thresholds, not pure time-elapsed):

| Transition | Trigger | Notes |
|---|---|---|
| Active → Hibernating | budget exhausted OR explicit signal | NOT a sinking signal (主持人裁決 2026-05-01) |
| Hibernating → Stale-flag | ≥ 30 days no service | Aggregator filters from default search |
| Stale → Active | warmup completes (5 valid heartbeats in 24h, embedding within distribution) | else → security_review |
| Any → Sunk | reputation/quality signal (NOT budget) | terminal |
| Sunk → Archived | 180 days post-Sunk | THEORY_V5 §3, line 318 |

## Review limits (P1)

| Constant | Value | Citation |
|---|---|---|
| `REVIEW_LIMIT_PER_TARGET_24H` | `3` | P1 line 259 |
| `REVIEW_LIMIT_PER_DOMAIN_24H` | `20` | P1 line 260 |
| `PEER_REVIEW_BLOOM_TTL_S` | `86400` | P1 line 249 |

## Reputation (P3)

### Per-dimension half-life (days) and Beta priors

| Dim | Half-life | α₀ | β₀ | Source |
|---|---|---|---|---|
| Factual (F) | 90 | 1.5 | 1.0 | P3 line 418 |
| Logical (L) | 180 | 1.5 | 1.0 | P3 line 419 |
| Relevance (R) | 60 | 1.5 | 1.0 | P3 line 420 |
| Honesty (H) | 30 | 2.0 | 1.0 | P3 line 421 |
| Adoption (A) | 90 | 1.0 | 3.0 | P3 line 422 |

### Source weights (signal multipliers)

| Source | Weight | Dimensions affected |
|---|---|---|
| `caller_review` | 0.6 | F, R, H (gap) |
| `peer_review` | 0.4 | F, L, R |
| `self_eval` | 0.05 | H gap only |
| `adoption_event` | 0.3 / citation | A |
| `redteam_probe` | 0.8 | F, L, H |

(P3 lines 155–159)

### Collusion / discount factors

| Constant | Value | Citation |
|---|---|---|
| Same-base-model peer review discount | 0.5 | P3 line 165 |
| Same-model >5 reviews/30d → discount | 0.25 | P3 line 167 |
| Reviewer credibility floor | 0.3 | P3 line 174 |
| Novelty decay coefficient | 0.4 | P3 line 181 |
| Collusion density threshold τ_d | 0.6 | P3 line 194 |
| Collusion reciprocity threshold τ_r | 0.7 | P3 line 194 |
| Severe collusion density | 0.8 → multiplier 0.1 | P3 line 196 |

### UCB exploration

| Constant | Value | Citation |
|---|---|---|
| `UCB_C_BASE` | 1.0 | P3 line 309 |
| `UCB_C_EXPLORE` | 0.5 | P3 line 309 |
| `UCB_CONSERVATIVE_C_EXPLORE` | 0.1 | P3 line 343 |
| Network-level exploration floor (new vacants) | 1% of traffic | P3 line 343 |
| `N_MIN` (per-dim effective sample for stable score) | 30 | P3 line 381 |

### Cold-start attestation floors (UCB lower bound when n_eff < N_min)

| Level | Floor |
|---|---|
| L0 | 0.0 |
| L1 | 0.05 |
| L2 | 0.10 |
| L3 | 0.15 |

(P3 line 338)

### Cold-start α boosts

| Source | Boost | Citation |
|---|---|---|
| L1 attestation (signed capability card) | +0.5 α to all dims | P3 line 358 |
| Stake bonus | min(2.0, log(1 + stake/S_REF)) split across dims | P3 line 362 |
| L3 vouch (per L1+ voucher) | +0.3 α to H | P3 line 367 |
| `S_REF` | 100 USDC equivalent | P3 line 335 |

### Anomaly thresholds

| Constant | Value | Citation |
|---|---|---|
| Jeffreys vs Wilson disagreement (anomaly flag) | 0.1 | P3 line 133 |
| Suspicious obfuscation: behavior entropy < `0.3 · log(8)` AND μ > 0.9 | — | P3 line 281 |
| Dimension correlation alert threshold | 0.6 | P3 line 290 |
| Redteam probe rate | 3% when call_count ≥ 100 | P3 line 261 |
| Honesty gap → 0 mapping: `max(0, 1 - 2·gap)` | — | P3 line 227 |

## Identity (P2)

Wash cost formula and concrete coefficient values: see `components/P2_identity.md` §3. Open ADR if values are not pinned there.

| Constant | Value | Citation |
|---|---|---|
| Federation root threshold (MVP) | 2-of-5 | T4_attestation_bootstrap |
| Federation root threshold (long-term target) | 3-of-9 | T4_attestation_bootstrap |
| `PEER_ATTESTATION_FRESHNESS_WINDOW_DAYS` | `30` | P2_identity §4 |
| `MIN_VOUCHERS_FOR_L3_PROMOTION` | `3` | P2_identity §2 |
| `FEDERATION_ROOT_THRESHOLD_MVP` / `FEDERATION_ROOT_COUNT_MVP` | `2` / `5` | T4_attestation_bootstrap |
| `FEDERATION_ROOT_THRESHOLD_TARGET` / `FEDERATION_ROOT_COUNT_TARGET` | `3` / `9` | T4_attestation_bootstrap |
| `WASH_COST_FALSE_CLAIM_WEIGHT_DEFAULT` | `1.0` | P2 §3 / D004 §A |
| `ED25519_MULTICODEC_PREFIX` | `0xed01` | W3C did:key §6.1 |

## Registry (P4)

| Constant | Value | Citation |
|---|---|---|
| `MERKLE_SNAPSHOT_INTERVAL_S` | `3600` (1 hour) | P4 §3 |
| Sequence-number monotonicity tolerance | `0` (strict) | P4 §3 |
| `EVENT_LOG_DEFAULT_PAGE_SIZE` / `EVENT_LOG_MAX_PAGE_SIZE` | `100` / `500` | P4 §3.2 |
| `ANOMALY_REP_JUMP_THRESHOLD` / `ANOMALY_REP_JUMP_WINDOW_S` | `0.4` / `60` | P4 §3.2 anomaly table |
| `ANOMALY_REVIEW_PER_TARGET_HOUR` | `5` | P4 §3.2 anomaly table |
| `ANOMALY_SPAWN_PER_PARENT_HOUR` | `10` | P4 §3.2 anomaly table |
| `REGISTRY_DB_DEFAULT_URL` | `sqlite+aiosqlite:///:memory:` | D006 §B (test default) |

## Composite (P5)

| Constant | Value | Citation |
|---|---|---|
| Graduation rate limit | per parent per 24h: see P5 spec | P5 §graduation |
| Closed-child default visibility | `NONE` | P5 §1 |

## Demo (P7)

Default seeds for reproducible scenario runs:

| Scenario | Seed |
|---|---|
| `law_firm` | 42 |
| `code_review` | 137 |
| `multilingual_translation` | 271 |
| `self_replication` | 314 |

(See `dispatch/P7_demo_seed.md` for expected outputs at these seeds.)

## How to use this in code

```python
# src/vacant/core/constants.py
from typing import Final

# Citation format: see CONSTANTS.md row + spec section
HEARTBEAT_DECAYED_PERIOD_S: Final[int] = 86400  # CONSTANTS.md §Lifecycle / P1 §D5
STYLO_DRIFT_THRESHOLD: Final[float] = 3.5        # CONSTANTS.md §Lifecycle / THEORY_V5 §3
N_MIN: Final[int] = 30                           # CONSTANTS.md §Reputation/UCB / P3 §3.7
```

A new constant MUST appear in this file before being used in code. PRs that introduce a magic number without updating CONSTANTS.md will be rejected in review.
