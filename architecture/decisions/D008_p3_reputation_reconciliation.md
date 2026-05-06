# D008 -- P3 Reputation Spec Reconciliation

**Date:** 2026-05-06
**Author:** P3 implementation session
**Affected components:** P3 Reputation / `core/constants.py` / `architecture/CONSTANTS.md`

---

## Background

Several spec ambiguities surfaced while implementing
`dispatch/P3_reputation.md`. This ADR pins the resolved interpretation.

### Issue A -- Beta prior values: spec §3.2 vs CONSTANTS.md vs §3.10 worked example

Three sources disagree:

| Source | F | L | R | H | A |
|---|---|---|---|---|---|
| `components/P3_reputation.md` §3.2 (table) | (1, 1) | (1, 1) | (1, 1) | (2, 1) | (1, 3) |
| `architecture/CONSTANTS.md` §Reputation | (1.5, 1.0) | (1.5, 1.0) | (1.5, 1.0) | (2.0, 1.0) | (1.0, 3.0) |
| `components/P3_reputation.md` §3.10 worked example | (1.5, 1.0) | (1.5, 1.0) | (1.5, 1.0) | (2.0, 1.0) | (1.0, 3.0) |

The worked example in §3.10 uses 1.5 because it explicitly shows
"`L1 attestation` → 全維 +0.5alpha" being already applied (§3.8 cold-start
prior). The base prior in §3.2 is **1.0** -- the 1.5 in CONSTANTS.md is
the worked example's *L1-attestation-applied* value being mistakenly
imported as the base.

### Issue B -- `dispatch §4` "five components" vs `spec §3.8` "three stages"

The dispatch enumerates five cold-start components:

1. UCB exploration (already in §2)
2. Birth-path startup signals (D1-D5 from THEORY_V5 §3.6)
3. Niche uniqueness bonus
4. Low-stakes probes
5. Idle peer review

The component spec §3.8 has three stages: prior, exploration bonus,
"INSUFFICIENT_DATA" label. The dispatch is the immediate task contract;
the spec covers a superset.

### Issue C -- Same-* detection signal output type

The dispatch §5 says each detector returns a `SignalStrength` (float in
[0,1]) + `suspected_cluster` (set of `VacantId`). The spec §3.4.4
describes a Louvain-based graph detector with discount multipliers.
These can coexist: the dispatch's output is the public API; the spec
describes one possible internal mechanism.

### Issue D -- `ReputationProtocol` shape vs P4's `ReputationOracle`

P4 already imports `ReputationOracle` Protocol with method
`async score(vacant_id: str, dimensions: Sequence[str]) -> float`. The
dispatch's `Aggregator` API has `get_reputation(VacantId, str) -> Beta5D`,
`get_ranked(...)`, `record_review(...)`. These overlap; the
`Aggregator` should also satisfy `ReputationOracle` so P4 can use it.

## Decision

### A. Base prior is `(1.0, 1.0)` for F/L/R; `(2.0, 1.0)` for H; `(1.0, 3.0)` for A

`core/constants.py` exports the base priors as a per-dimension dict:

```python
BETA_BASE_PRIORS: Final[dict[str, tuple[float, float]]] = {
    "factual":   (1.0, 1.0),
    "logical":   (1.0, 1.0),
    "relevance": (1.0, 1.0),
    "honesty":   (2.0, 1.0),
    "adoption":  (1.0, 3.0),
}
```

`CONSTANTS.md` is updated to reflect the spec -- the 1.5 column was a
copy-paste artefact from the §3.10 worked example.

The L1-attestation `+0.5alpha` (spec §3.8) is applied separately in
`cold_start.py` so the bonus is auditable rather than baked into the
prior.

### B. Five components implemented, three are central + two are policy hooks

The five dispatch-listed components map to:

| # | Component | Implementation |
|---|---|---|
| 1 | UCB exploration | `ucb.py::ucb_score` (already in §2) |
| 2 | Birth-path startup signals | `cold_start.py::birth_path_bonus` -- table indexed by `BirthPath` enum (Path Zero / B / C / D1-D5); maps to a tuple of `(alpha, beta)` boosts |
| 3 | Niche uniqueness bonus | `cold_start.py::niche_bonus` -- accepts a `capability_supply` int (count of vacants offering this capability); rarer → larger bonus |
| 4 | Low-stakes probes | `cold_start.py::is_eligible_for_low_stakes_probe` -- returns `True` for vacants with `n_eff < N_min` and not-yet-Sunk |
| 5 | Idle peer review | `cold_start.py::should_idle_review_target` -- returns `True` if reviewer has been idle >= `IDLE_REVIEW_THRESHOLD_S` and target has `n_eff < N_min` |

Components 4 and 5 are policy hooks -- they don't directly mutate
reputation; they signal to P1 (idle-time scheduler) and P4 (probe
caller-routing). The dispatch acceptance ("cold-start sim shows new
vacants get traction within 100 ticks") is satisfied by component 1
(UCB exploration boost) + component 2 (birth-path alpha-boost).

### C. Same-* detection ships dispatch's API; internal mechanism per T5 §3.5 MVP

Each detector returns a `SameDetectSignal` dataclass:

```python
@dataclass(frozen=True)
class SameDetectSignal:
    strength: float                  # in [0, 1]
    suspected_cluster: frozenset[VacantId]
    rationale: str                   # human-readable for caveats
```

Layer-0 declared link (controller_id / parent_id) → strength = 1.0.
Layer-1 temporal correlation (heartbeat cross-correlation) → strength
proportional to correlation. Layer-2 behavioural similarity → strength
proportional to cosine. Output is a single `SameDetectSignal` per
detector; the aggregator caps weight via `1 - max(detector.strength)`.

### D. `Aggregator` satisfies P4's `ReputationOracle` Protocol

`reputation/aggregator.py::Aggregator` exposes:

```python
async def score(self, vacant_id: str, dimensions: Sequence[str]) -> float
async def get_reputation(self, vid: VacantId, substrate: str) -> Beta5D
async def get_ranked(self, capability_query: str, n: int) -> list[tuple[VacantId, float]]
async def record_review(...) -> None
```

The first method matches `vacant.registry.aggregation.ReputationOracle`
so the registry can plug it in directly without an adapter.

### E. Reviewer eligibility uses P1's `can_review`

The P1 state-machine predicate `vacant.runtime.state_machine.can_review`
(already merged) is the source of truth: reviews from
`SUNK / ARCHIVED / STALE` vacants are rejected at the aggregator's API
surface (`record_review`), per dispatch acceptance criterion.

## Consequences

- One canonical prior table (D008 §A) used by both `cold_start.py` and
  the worked example.
- The five cold-start components are all implemented; components 4 and
  5 are explicit policy hooks for downstream consumers.
- Same-* detection has a uniform `SameDetectSignal` output type that
  the aggregator can compose without per-line special casing.
- P4's `Aggregator` import works without adapters.
