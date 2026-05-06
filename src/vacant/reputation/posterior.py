"""Beta posterior + Beta5D -- five-dimensional reputation state.

Per P3 §3.1-§3.2 each reputation event updates a per-dimension Beta
posterior with time-decayed prior weight. The per-dimension half-life
is set in `core.constants.DIM_HALF_LIFE_DAYS`.

Update rule (§3.2):

```
gamma = exp(-ln(2) * Deltat / half_life_d)
alpha ← alpha0 + gamma * (alpha - alpha0)              # decay accumulated evidence, keep prior
beta ← beta0 + gamma * (beta - beta0)
n_eff ← gamma * n_eff
alpha ← alpha + w * s
beta ← beta + w * (1 - s)
n_eff ← n_eff + w
```

`s ∈ [0, 1]` is the signal's positive rate; `w` is the source-weighted
evidence contribution.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from vacant.core.constants import (
    BETA_BASE_PRIORS,
    DIM_HALF_LIFE_DAYS,
    REPUTATION_DIMS,
)
from vacant.reputation.errors import InvalidDimensionError, InvalidSignalError

__all__ = [
    "Beta",
    "Beta5D",
    "Dim",
    "decay_factor",
    "five_d_with_priors",
]


# Reputation dimension is just a string for forwards-compat with new dims.
Dim = str


def _check_dim(dim: str) -> None:
    if dim not in REPUTATION_DIMS:
        raise InvalidDimensionError(f"unknown reputation dim: {dim!r}")


def _ts_to_seconds(ts: float | int | datetime) -> float:
    if isinstance(ts, datetime):
        return ts.astimezone(UTC).timestamp()
    return float(ts)


def decay_factor(dt_seconds: float, half_life_days: float) -> float:
    """Exponential half-life decay factor: `exp(-ln(2) * Deltat_days / half_life_d)`."""
    if dt_seconds <= 0:
        return 1.0
    if half_life_days <= 0:
        return 0.0 if dt_seconds > 0 else 1.0
    days = dt_seconds / 86_400.0
    return math.exp(-math.log(2.0) * days / half_life_days)


class Beta(BaseModel):
    """Single-dimension Beta posterior with time-decay state."""

    model_config = ConfigDict(arbitrary_types_allowed=False)

    alpha: float = 1.0
    beta: float = 1.0
    alpha0: float = 1.0
    """Prior `alpha0` -- kept across decays so the prior never erodes."""
    beta0: float = 1.0
    """Prior `beta0`."""
    n_eff: float = 0.0
    """Effective sample size = alpha + beta - alpha0 - beta0 (post-decay). Tracks how
    much *evidence* the posterior carries beyond the prior."""
    last_update_ts: float = 0.0
    """Unix-epoch seconds. Used to compute decay against the current time."""
    half_life_days: float = 90.0

    @field_validator("alpha", "beta", "alpha0", "beta0", "n_eff", "half_life_days")
    @classmethod
    def _non_negative(cls, v: float) -> float:
        if v < 0:
            raise InvalidSignalError(f"Beta value must be >= 0, got {v}")
        return v

    @property
    def mean(self) -> float:
        s = self.alpha + self.beta
        return self.alpha / s if s > 0 else 0.0

    @property
    def variance(self) -> float:
        s = self.alpha + self.beta
        if s <= 0:
            return 0.0
        return (self.alpha * self.beta) / ((s * s) * (s + 1.0))

    def decayed(self, *, now_ts: float | datetime) -> Beta:
        """Return a *new* `Beta` with alpha, beta, n_eff decayed to `now_ts`.

        The prior never decays -- only the accumulated evidence above the
        prior shrinks (P3 §3.2). Identity if `now_ts <= last_update_ts`.
        """
        target = _ts_to_seconds(now_ts)
        dt = target - self.last_update_ts
        if dt <= 0:
            return self
        gamma = decay_factor(dt, self.half_life_days)
        new_alpha = self.alpha0 + gamma * (self.alpha - self.alpha0)
        new_beta = self.beta0 + gamma * (self.beta - self.beta0)
        new_n_eff = gamma * self.n_eff
        return self.model_copy(
            update={
                "alpha": new_alpha,
                "beta": new_beta,
                "n_eff": new_n_eff,
                "last_update_ts": target,
            }
        )

    def update(
        self,
        *,
        positive_weight: float,
        negative_weight: float,
        now_ts: float | datetime,
    ) -> Beta:
        """Decay to `now_ts` then apply a weighted positive/negative pulse.

        `positive_weight` and `negative_weight` are the `w * s` and
        `w * (1 - s)` terms from §3.2. Both must be >= 0; the caller has
        already factored `s ∈ [0, 1]` into them.
        """
        if positive_weight < 0 or negative_weight < 0:
            raise InvalidSignalError(
                f"update weights must be >= 0; got pos={positive_weight}, neg={negative_weight}"
            )
        decayed = self.decayed(now_ts=now_ts)
        return decayed.model_copy(
            update={
                "alpha": decayed.alpha + positive_weight,
                "beta": decayed.beta + negative_weight,
                "n_eff": decayed.n_eff + positive_weight + negative_weight,
            }
        )

    def update_with_signal(self, *, signal: float, weight: float, now_ts: float | datetime) -> Beta:
        """Convenience wrapper: split `(signal, weight)` into pos/neg pulses.

        `signal` is the positive rate ∈ [0, 1]; `weight` >= 0 is the
        source-weighted evidence contribution.
        """
        if not (0.0 <= signal <= 1.0):
            raise InvalidSignalError(f"signal must be in [0, 1], got {signal}")
        if weight < 0:
            raise InvalidSignalError(f"weight must be >= 0, got {weight}")
        return self.update(
            positive_weight=weight * signal,
            negative_weight=weight * (1.0 - signal),
            now_ts=now_ts,
        )


def _make_dim_beta(dim: Dim, *, now_ts: float = 0.0) -> Beta:
    _check_dim(dim)
    a, b = BETA_BASE_PRIORS[dim]
    half_life = float(DIM_HALF_LIFE_DAYS[dim])
    return Beta(
        alpha=a,
        beta=b,
        alpha0=a,
        beta0=b,
        n_eff=0.0,
        last_update_ts=now_ts,
        half_life_days=half_life,
    )


def five_d_with_priors(*, now_ts: float | datetime = 0.0) -> Beta5D:
    """Construct a `Beta5D` with the canonical base priors.

    Cold-start adjustments (L1 attestation, stake, vouchers, sibling
    inheritance) are applied separately in `cold_start.py`.
    """
    target = _ts_to_seconds(now_ts)
    return Beta5D(
        factual=_make_dim_beta("factual", now_ts=target),
        logical=_make_dim_beta("logical", now_ts=target),
        relevance=_make_dim_beta("relevance", now_ts=target),
        honesty=_make_dim_beta("honesty", now_ts=target),
        adoption=_make_dim_beta("adoption", now_ts=target),
    )


class Beta5D(BaseModel):
    """Five-dimensional reputation state for one (vacant, substrate) pair."""

    factual: Beta = Field(default_factory=lambda: _make_dim_beta("factual"))
    logical: Beta = Field(default_factory=lambda: _make_dim_beta("logical"))
    relevance: Beta = Field(default_factory=lambda: _make_dim_beta("relevance"))
    honesty: Beta = Field(default_factory=lambda: _make_dim_beta("honesty"))
    adoption: Beta = Field(default_factory=lambda: _make_dim_beta("adoption"))

    def get(self, dim: Dim) -> Beta:
        _check_dim(dim)
        return getattr(self, dim)  # type: ignore[no-any-return]

    def with_dim(self, dim: Dim, beta: Beta) -> Beta5D:
        _check_dim(dim)
        return self.model_copy(update={dim: beta})

    def means(self) -> dict[str, float]:
        return {dim: self.get(dim).mean for dim in REPUTATION_DIMS}

    def variances(self) -> dict[str, float]:
        return {dim: self.get(dim).variance for dim in REPUTATION_DIMS}

    def n_effs(self) -> dict[str, float]:
        return {dim: self.get(dim).n_eff for dim in REPUTATION_DIMS}

    def decayed(self, *, now_ts: float | datetime) -> Beta5D:
        return Beta5D(
            factual=self.factual.decayed(now_ts=now_ts),
            logical=self.logical.decayed(now_ts=now_ts),
            relevance=self.relevance.decayed(now_ts=now_ts),
            honesty=self.honesty.decayed(now_ts=now_ts),
            adoption=self.adoption.decayed(now_ts=now_ts),
        )

    def update_dim(
        self,
        dim: Dim,
        *,
        signal: float,
        weight: float,
        now_ts: float | datetime,
    ) -> Beta5D:
        beta = self.get(dim).update_with_signal(signal=signal, weight=weight, now_ts=now_ts)
        return self.with_dim(dim, beta)
