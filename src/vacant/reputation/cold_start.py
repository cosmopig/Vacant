"""Cold-start mechanism (P3 §3.8 + dispatch §4).

Five components, per dispatch:

1. UCB exploration -- implemented in `ucb.py` (`exploration_boost`).
2. Birth-path startup signals -- `birth_path_bonus` enum table.
3. Niche uniqueness bonus -- `niche_bonus` from capability-supply count.
4. Low-stakes probes -- `is_eligible_for_low_stakes_probe` policy hook.
5. Idle peer review -- `should_idle_review_target` policy hook.

Stage 1 (initial prior, §3.8) is `initial_prior(...)`: takes attestation
level / stake / vouchers / sibling and returns a `Beta5D`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from vacant.core.constants import (
    BETA_BASE_PRIORS,
    DIM_HALF_LIFE_DAYS,
    IDLE_REVIEW_THRESHOLD_S,
    L1_ATTESTATION_ALPHA_BOOST,
    L3_VOUCH_ALPHA_BOOST,
    N_MIN_FOR_STABLE_SCORE,
    N_SHOW_MIN_THRESHOLD,
    REPUTATION_DIMS,
    S_REF_USDC,
)
from vacant.reputation.posterior import Beta, Beta5D, five_d_with_priors

__all__ = [
    "BirthPath",
    "ColdStartCaveats",
    "InsufficientDataLabel",
    "birth_path_bonus",
    "initial_prior",
    "is_eligible_for_low_stakes_probe",
    "niche_bonus",
    "should_idle_review_target",
    "show_label",
]


class BirthPath(StrEnum):
    """Birth-path enumeration (THEORY_V5 §3.6).

    - PATH_ZERO: human-built infrastructure (one-time).
    - PATH_B: subagent graduation (legacy; permanent transitional path).
    - PATH_C: client-mediated spawn (transitional; folds into D5 long-term).
    - D1..D5: agent self-replication paths (THEORY_V5 §3.6 D-series).
    """

    PATH_ZERO = "PATH_ZERO"
    PATH_B = "PATH_B"
    PATH_C = "PATH_C"
    D1 = "D1"
    D2 = "D2"
    D3 = "D3"
    D4 = "D4"
    D5 = "D5"


# Birth-path startup signals (D008 §B). Maps to `(alpha_boost_F_L_R, alpha_boost_H)`.
# Path Zero / B / C are heritage paths and get a small "bootstrap" alpha boost
# in F/L/R, recognising the developer's real-world stakes. D-series paths
# inherit the parent's reputation via `lineage_prior_alpha` instead, so the
# direct boost here is small (lineage is the heavier signal).
_BIRTH_PATH_BOOSTS: dict[BirthPath, tuple[float, float]] = {
    BirthPath.PATH_ZERO: (0.5, 0.5),
    BirthPath.PATH_B: (0.3, 0.2),
    BirthPath.PATH_C: (0.2, 0.1),
    BirthPath.D1: (0.0, 0.0),
    BirthPath.D2: (0.0, 0.0),
    BirthPath.D3: (0.0, 0.0),
    BirthPath.D4: (0.1, 0.1),
    BirthPath.D5: (0.0, 0.0),
}


def birth_path_bonus(path: BirthPath) -> tuple[float, float]:
    """Return `(alpha_boost for F/L/R each, alpha_boost for H)` per birth path.

    D-series paths return small boosts because lineage prior shaping
    (see `ucb.lineage_prior_alpha`) carries the parent-reputation signal.
    """
    return _BIRTH_PATH_BOOSTS[path]


def initial_prior(
    *,
    attestation_level: str = "L0",
    stake_amount: float = 0.0,
    n_l1_plus_vouchers: int = 0,
    sibling: Beta5D | None = None,
    birth_path: BirthPath | None = None,
    now_ts: float = 0.0,
) -> Beta5D:
    """Build a cold-start `Beta5D` per P3 §3.8 stage 1.

    Composition order:

    1. Base priors (CONSTANTS.md §Reputation, see D008 §A).
    2. L1 attestation: +`L1_ATTESTATION_ALPHA_BOOST` to F/L/R alpha
       (skipped for L0).
    3. Stake bonus: `min(2.0, log(1 + stake/S_REF))` split half-each
       across F/L/R.
    4. L3 vouches: `+L3_VOUCH_ALPHA_BOOST * n_l1_plus_vouchers` to H alpha.
    5. Sibling inheritance under same owner: `alpha/4`, `beta/4` blended in
       (capped, decayed evidence).
    6. Birth-path boost: per `birth_path_bonus` table.
    """
    rep = five_d_with_priors(now_ts=now_ts)

    # 2. L1 attestation
    if attestation_level in ("L1", "L2", "L3"):
        for d in ("factual", "logical", "relevance"):
            beta = rep.get(d)
            rep = rep.with_dim(
                d,
                beta.model_copy(
                    update={
                        "alpha": beta.alpha + L1_ATTESTATION_ALPHA_BOOST,
                        "alpha0": beta.alpha0 + L1_ATTESTATION_ALPHA_BOOST,
                    }
                ),
            )

    # 3. Stake
    if stake_amount > 0:
        bonus = min(2.0, math.log(1.0 + stake_amount / S_REF_USDC))
        per_dim = bonus / 2.0
        for d in ("factual", "logical", "relevance"):
            beta = rep.get(d)
            rep = rep.with_dim(
                d,
                beta.model_copy(
                    update={
                        "alpha": beta.alpha + per_dim,
                        "alpha0": beta.alpha0 + per_dim,
                    }
                ),
            )

    # 4. L3 vouches → H alpha
    if n_l1_plus_vouchers > 0:
        boost = L3_VOUCH_ALPHA_BOOST * n_l1_plus_vouchers
        h = rep.honesty
        rep = rep.with_dim(
            "honesty",
            h.model_copy(update={"alpha": h.alpha + boost, "alpha0": h.alpha0 + boost}),
        )

    # 5. Sibling inheritance (capped via /4)
    if sibling is not None:
        new_dims: dict[str, Beta] = {}
        for d in REPUTATION_DIMS:
            child = rep.get(d)
            sib = sibling.get(d)
            inherited_alpha = sib.alpha / 4.0
            inherited_beta = sib.beta / 4.0
            new_dims[d] = child.model_copy(
                update={
                    "alpha": child.alpha + inherited_alpha,
                    "beta": child.beta + inherited_beta,
                    # The inherited evidence is decayed-state, so it
                    # contributes to n_eff (not the prior).
                    "n_eff": child.n_eff + inherited_alpha + inherited_beta,
                }
            )
        rep = Beta5D(**new_dims)

    # 6. Birth-path boost
    if birth_path is not None:
        flr_boost, h_boost = birth_path_bonus(birth_path)
        if flr_boost > 0:
            for d in ("factual", "logical", "relevance"):
                beta = rep.get(d)
                rep = rep.with_dim(
                    d,
                    beta.model_copy(
                        update={
                            "alpha": beta.alpha + flr_boost,
                            "alpha0": beta.alpha0 + flr_boost,
                        }
                    ),
                )
        if h_boost > 0:
            beta = rep.honesty
            rep = rep.with_dim(
                "honesty",
                beta.model_copy(
                    update={
                        "alpha": beta.alpha + h_boost,
                        "alpha0": beta.alpha0 + h_boost,
                    }
                ),
            )

    return rep


def niche_bonus(
    *,
    capability_supply: int,
    saturation_supply: int = 10,
    max_bonus: float = 0.10,
) -> float:
    """Niche uniqueness bonus: rarer capability → larger bonus.

    `capability_supply` is the count of vacants currently offering this
    capability. The bonus is `max_bonus * (1 - supply / saturation)`,
    floored at 0.

    Intuition: a niche with 1 supplier should get the full `max_bonus`;
    once 10+ vacants compete on the same capability, the bonus is 0.
    """
    if capability_supply < 0:
        raise ValueError(f"capability_supply must be >= 0; got {capability_supply}")
    if saturation_supply <= 0:
        raise ValueError(f"saturation_supply must be > 0; got {saturation_supply}")
    if max_bonus < 0:
        raise ValueError(f"max_bonus must be >= 0; got {max_bonus}")
    if capability_supply >= saturation_supply:
        return 0.0
    fraction_filled = capability_supply / saturation_supply
    return max_bonus * (1.0 - fraction_filled)


def is_eligible_for_low_stakes_probe(rep: Beta5D, *, n_min: int = N_MIN_FOR_STABLE_SCORE) -> bool:
    """Policy hook: caller-side proxy routes a small fraction of low-stakes
    requests to vacants that have not yet crossed `n_min`. Reactivated by
    P4 / P7 caller routing.
    """
    return any(rep.get(d).n_eff < n_min for d in REPUTATION_DIMS)


def should_idle_review_target(
    *,
    reviewer_idle_seconds: float,
    target_n_eff_min: float,
    n_min: int = N_MIN_FOR_STABLE_SCORE,
    idle_threshold_s: int = IDLE_REVIEW_THRESHOLD_S,
) -> bool:
    """Policy hook: an idle reviewer should peer-review a target with
    `n_eff < n_min`. P1 idle-time scheduler consumes this.
    """
    return reviewer_idle_seconds >= idle_threshold_s and target_n_eff_min < n_min


# --- INSUFFICIENT_DATA label (§3.8 stage 3) ---------------------------------


@dataclass(frozen=True)
class ColdStartCaveats:
    """Caveats accompanying a reputation read for new vacants."""

    insufficient_data: bool
    n_eff_min: float
    partial_dims: tuple[str, ...]
    """Dims whose `n_eff` is below `N_SHOW`."""


@dataclass(frozen=True)
class InsufficientDataLabel:
    """Surface-level marker returned to UI clients when `n_eff` is low."""

    show_scalar: bool
    label: str
    caveats: ColdStartCaveats


def show_label(rep: Beta5D, *, n_show: int = N_SHOW_MIN_THRESHOLD) -> InsufficientDataLabel:
    """Return whether to show a scalar reputation or `INSUFFICIENT_DATA`.

    `n_show=10` per CONSTANTS.md / D008 §A: if any dim is below this,
    callers must not render a scalar score; show the caveat instead.
    """
    n_effs = rep.n_effs()
    partials = tuple(d for d, n in n_effs.items() if n < n_show)
    insufficient = bool(partials)
    return InsufficientDataLabel(
        show_scalar=not insufficient,
        label="INSUFFICIENT_DATA" if insufficient else "OK",
        caveats=ColdStartCaveats(
            insufficient_data=insufficient,
            n_eff_min=min(n_effs.values()) if n_effs else 0.0,
            partial_dims=partials,
        ),
    )


# Silence unused-import warning while keeping the constant accessible from
# this module (other components use it through us).
_ = (DIM_HALF_LIFE_DAYS, BETA_BASE_PRIORS)
