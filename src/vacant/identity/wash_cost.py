"""Whitewashing cost (P2 §3 / dispatch §3 / D004 §A).

The dispatch contract is:

```
inputs:  claimed_history_depth, attestation_count, substrate_diversity
output:  WashCost (network-cycles units; type-tagged)
properties:
  - monotonic non-decreasing in claimed_history_depth
  - increasing in false_claim_weight (parameterised so tests vary it)
```

The richer §3.4 economic formula (`c_stake / c_history_loss /
opportunity_cost`) is future work — see D004 §A. This module exposes the
narrower, testable contract; P3 / P4 can wrap it in an economic adapter.

Units: "network cycles" is a deliberately abstract unit. It is *not*
USD, *not* tokens, *not* Ethereum gas. Downstream consumers (P3) decide
how to weight it inside their reputation formulas; tests here only check
ordering invariants.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

from vacant.core.constants import WASH_COST_FALSE_CLAIM_WEIGHT_DEFAULT
from vacant.identity.errors import IdentityError

__all__ = [
    "WASH_COST_FALSE_CLAIM_WEIGHT_DEFAULT",
    "WashCost",
    "WashCostWeights",
    "compute_wash_cost",
]


WashCost = NewType("WashCost", float)
"""Type-tagged float in 'network cycles' units (D004 §A).

mypy treats `WashCost` and `float` as distinct types — passing a raw
`float` to a function expecting `WashCost` requires an explicit
`WashCost(...)` conversion."""


@dataclass(frozen=True)
class WashCostWeights:
    """Per-dimension unit costs.

    Defaults are chosen so that:
    - history (forging entries) dominates for typical attacker scenarios
      (per-entry cost is the largest of the three)
    - attestations are mid-cost (a real organisation must vouch)
    - substrate diversity is the smallest cost (claiming you run on more
      runtimes is cheap-talk; the network only believes it after seeing
      proofs handled elsewhere)

    All values are >= 0 and the dataclass enforces it.
    """

    history_unit_cost: float = 1.0
    attestation_unit_cost: float = 0.5
    substrate_unit_cost: float = 0.25

    def __post_init__(self) -> None:
        for name, value in (
            ("history_unit_cost", self.history_unit_cost),
            ("attestation_unit_cost", self.attestation_unit_cost),
            ("substrate_unit_cost", self.substrate_unit_cost),
        ):
            if value < 0:
                raise IdentityError(f"WashCostWeights.{name} must be >= 0, got {value}")


def compute_wash_cost(
    claimed_history_depth: int,
    attestation_count: int,
    substrate_diversity: int,
    *,
    false_claim_weight: float = WASH_COST_FALSE_CLAIM_WEIGHT_DEFAULT,
    weights: WashCostWeights | None = None,
) -> WashCost:
    """Cost (in network-cycles units) of standing up a fresh identity that
    claims `claimed_history_depth` past entries, `attestation_count` peer
    vouches, and operation across `substrate_diversity` substrates.

    Formula:

    ```
    cost = history_unit_cost   * claimed_history_depth * (1 + false_claim_weight)
         + attestation_unit_cost * attestation_count
         + substrate_unit_cost   * substrate_diversity
    ```

    Notes:
    - The `(1 + false_claim_weight)` factor on the history term encodes
      "claiming history you don't have is more expensive than claiming
      history you do". Tests vary `false_claim_weight` to verify the
      cost increases.
    - All three count inputs must be >= 0. Negative inputs raise
      `IdentityError`.
    - Output is `WashCost` (type-tagged float); callers can compare two
      `WashCost` values directly because `WashCost` is a `NewType` over
      `float`.
    """
    if claimed_history_depth < 0:
        raise IdentityError("claimed_history_depth must be >= 0")
    if attestation_count < 0:
        raise IdentityError("attestation_count must be >= 0")
    if substrate_diversity < 0:
        raise IdentityError("substrate_diversity must be >= 0")
    if false_claim_weight < 0:
        raise IdentityError("false_claim_weight must be >= 0")

    w = weights or WashCostWeights()
    cost = (
        w.history_unit_cost * claimed_history_depth * (1.0 + false_claim_weight)
        + w.attestation_unit_cost * attestation_count
        + w.substrate_unit_cost * substrate_diversity
    )
    return WashCost(cost)
