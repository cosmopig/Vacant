"""UCB scoring for vacant selection.

P3 §3.7 extends the standard UCB1 (DRF arXiv:2509.05764) to multi-dim +
uncertainty-aware:

```
mu_w = Sum w_d * mu_d
sigma_w = √(Sum w_d^2 * sigma_d^2)              # treats dims as independent
n_w = harmonic_mean(n_eff_d for w_d > 0.05)
explore = c_explore * √(log N / max(n_w, 1))
score = mu_w + c * sigma_w + explore
```

Lineage and UCB scoring are decoupled (D015 §B). `parent_id` is *caller-
side metadata* — useful for filtering ("show me descendants of root R")
or sort tie-breaks — but the parent's posterior MUST NOT bleed into the
child's UCB score. CLAUDE.md §Load-bearing theory decisions makes the
lineage-not-individuals-evolve invariant load-bearing: individuals do
not inherit reputation from their parent; new lineage members reset
the clock.

`lineage_prior_alpha` is kept as a public helper for research callers
that explicitly want a lineage-weighted Beta prior outside the UCB path
(e.g. seeding a research probe). It is *not* used by `ucb_score`,
`call_score`, or `ucb_with_lineage_prior`.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from statistics import harmonic_mean

from vacant.core.constants import (
    COLD_START_FLOORS_BY_LEVEL,
    N_MIN_FOR_STABLE_SCORE,
    REPUTATION_DIMS,
    S_REF_USDC,
    UCB_C_BASE,
    UCB_C_EXPLORE,
)
from vacant.reputation.posterior import Beta, Beta5D

__all__ = [
    "call_score",
    "cold_start_floor",
    "exploration_boost",
    "lineage_prior_alpha",
    "ucb_score",
    "ucb_with_lineage_prior",
]


def _normalise_weights(weights: Mapping[str, float]) -> dict[str, float]:
    """Return weights restricted to the canonical dim set, summing to 1.

    Missing dims default to 0; negative weights are rejected. If the
    supplied weights sum to 0, default to uniform.
    """
    out: dict[str, float] = {}
    for d in REPUTATION_DIMS:
        w = float(weights.get(d, 0.0))
        if w < 0:
            raise ValueError(f"weight for {d} must be >= 0; got {w}")
        out[d] = w
    total = sum(out.values())
    if total <= 0:
        return {d: 1.0 / len(REPUTATION_DIMS) for d in REPUTATION_DIMS}
    return {d: out[d] / total for d in REPUTATION_DIMS}


def ucb_score(
    rep: Beta5D,
    *,
    weights: Mapping[str, float] | None = None,
    n_global: int = 1,
    c_base: float = UCB_C_BASE,
    c_explore: float = UCB_C_EXPLORE,
    significant_weight: float = 0.05,
) -> float:
    """Multi-dim Bayesian UCB. P3 §3.7."""
    w = _normalise_weights(weights or {d: 0.2 for d in REPUTATION_DIMS})
    means = rep.means()
    vars_ = rep.variances()
    n_effs = rep.n_effs()

    mu_w = sum(w[d] * means[d] for d in REPUTATION_DIMS)
    sigma_w_sq = sum((w[d] ** 2) * vars_[d] for d in REPUTATION_DIMS)
    sigma_w = math.sqrt(sigma_w_sq)

    significant_dims = [d for d in REPUTATION_DIMS if w[d] > significant_weight]
    if not significant_dims:
        n_w = 1.0
    else:
        # `harmonic_mean` rejects 0 inputs -- clamp to a tiny positive floor so
        # cold-start (n_eff=0) doesn't hit ZeroDivisionError.
        clamped = [max(n_effs[d], 1e-6) for d in significant_dims]
        n_w = float(harmonic_mean(clamped))

    log_n = math.log(max(n_global, 2))  # log(1) is 0; UCB needs >= log(2)
    # Floor at 1e-3 (not 1.0) so cold-start vacants (n_eff ~ 0) get a
    # genuinely larger explore term than warmed-up vacants with n_eff < 1.
    # A 1.0 floor would lump all sub-1 n_eff values into the same bucket
    # and kill cold-start exploration differentiation.
    explore = c_explore * math.sqrt(log_n / max(n_w, 1e-3))

    return mu_w + c_base * sigma_w + explore


def lineage_prior_alpha(
    *,
    base_alpha: float,
    base_beta: float,
    parent_alpha: float,
    parent_beta: float,
    depth: int,
    inherit_fraction: float = 0.25,
    decay_lambda: float = 0.5,
) -> tuple[float, float]:
    """Lineage prior shaping (§4.3): blend parent posterior into child prior.

    `kappa(d) = inherit_fraction * exp(-decay_lambda * d)` shrinks with
    lineage depth so a long fork chain doesn't trivially inherit root.
    Returns the blended `(alpha, beta)` for the child's prior.
    """
    if depth < 0:
        raise ValueError(f"lineage depth must be >= 0; got {depth}")
    if not (0.0 <= inherit_fraction <= 1.0):
        raise ValueError(f"inherit_fraction must be in [0, 1]; got {inherit_fraction}")
    if decay_lambda < 0:
        raise ValueError(f"decay_lambda must be >= 0; got {decay_lambda}")
    kappa = inherit_fraction * math.exp(-decay_lambda * depth)
    return (base_alpha + kappa * parent_alpha, base_beta + kappa * parent_beta)


def ucb_with_lineage_prior(
    child_beta: Beta,
    parent_beta: Beta | None = None,
    *,
    n_global: int,
    depth: int = 0,
    c_explore: float = UCB_C_EXPLORE,
    inherit_fraction: float = 0.25,
    decay_lambda: float = 0.5,
) -> float:
    """Single-dim UCB on a *child* posterior. Parent posterior is ignored.

    D015 §B: lineage is caller-side metadata; individual vacants do not
    inherit reputation from their parent (CLAUDE.md §Load-bearing theory
    decisions). The parameters `parent_beta`, `depth`, `inherit_fraction`,
    `decay_lambda` are accepted for back-compatible call sites and for
    future caller-side filtering (`depth` may still be used to sort
    descendants), but they have no effect on the score.

    Use `lineage_prior_alpha(...)` directly if you genuinely need a
    lineage-weighted Beta prior outside the UCB pipeline.
    """
    _ = (parent_beta, depth, inherit_fraction, decay_lambda)  # documented no-ops
    s = child_beta.alpha + child_beta.beta
    mean = child_beta.alpha / s if s > 0 else 0.0
    n_w = max(child_beta.n_eff, 1e-6)
    log_n = math.log(max(n_global, 2))
    # Floor at 1e-3 (not 1.0) so cold-start vacants (n_eff ~ 0) get a
    # genuinely larger explore term than warmed-up vacants with n_eff < 1.
    explore = c_explore * math.sqrt(log_n / max(n_w, 1e-3))
    return mean + explore


def exploration_boost(
    *,
    n_eff: float,
    n_min: int = N_MIN_FOR_STABLE_SCORE,
    n_global: int,
    c_explore: float = UCB_C_EXPLORE,
) -> float:
    """Cold-start exploration bonus (§3.8 stage 2): boost UCB explore term
    while `n_eff < n_min`. Boost is `1 + (n_min - n_eff) / n_min`,
    multiplied into the explore term.
    """
    if n_eff >= n_min:
        return 0.0
    log_n = math.log(max(n_global, 2))
    boost = 1.0 + (n_min - n_eff) / n_min
    return c_explore * math.sqrt(log_n / max(n_eff, 1.0)) * boost


def cold_start_floor(attestation_level: str) -> float:
    """UCB lower bound by attestation level (§3.7 line 338)."""
    return COLD_START_FLOORS_BY_LEVEL.get(attestation_level, 0.0)


def call_score(
    rep: Beta5D,
    *,
    weights: Mapping[str, float] | None = None,
    n_global: int,
    stake_amount: float = 0.0,
    attestation_level: str = "L0",
    portability_bonus: float = 0.0,
    c_base: float = UCB_C_BASE,
    c_explore: float = UCB_C_EXPLORE,
) -> float:
    """Full call scoring (§3.7 + §3.8):

    `score = ucb(...) + stake_bonus + att_floor + portability_bonus`

    * `stake_bonus = 0.1 * log(1 + stake / S_REF)` -- affects exploration
      tolerance, not the mean (anti-Goodhart-against-stake §3.7).
    * `att_floor` from `cold_start_floor(attestation_level)`.
    * `portability_bonus` is supplied by `portability.py` (capped).
    """
    if stake_amount < 0:
        raise ValueError(f"stake_amount must be >= 0; got {stake_amount}")
    if portability_bonus < 0:
        raise ValueError(f"portability_bonus must be >= 0; got {portability_bonus}")
    base = ucb_score(
        rep,
        weights=weights,
        n_global=n_global,
        c_base=c_base,
        c_explore=c_explore,
    )
    stake_bonus = 0.1 * math.log(1.0 + stake_amount / S_REF_USDC)
    return base + stake_bonus + cold_start_floor(attestation_level) + portability_bonus
