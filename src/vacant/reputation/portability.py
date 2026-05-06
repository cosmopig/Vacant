"""Portability factor (dispatch §6 / P3 §"resilience-as-independent-metric").

THEORY_V5 §3.1 split portability *out* of raw reputation: it became an
independent `resilience_score`. The dispatch §6 still asks for a small
**call_score bonus** rewarding ecological contribution -- vacants that
serve across multiple substrates with high success.

Implementation:

```
raw = sum(success_rate_per_substrate)
diversity = log(1 + n_substrates)
portability = clip(raw * diversity_norm, 0, MAX_BONUS)
```

The bonus is capped at `PORTABILITY_FACTOR_MAX_BONUS` so it can't
dominate the UCB call_score (anti-Goodhart-against-portability).
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from vacant.core.constants import PORTABILITY_FACTOR_MAX_BONUS

__all__ = ["compute_portability"]


def compute_portability(
    *,
    substrates_served: list[str],
    success_rate_per_substrate: Mapping[str, float],
    max_bonus: float = PORTABILITY_FACTOR_MAX_BONUS,
) -> float:
    """Return a portability bonus in `[0, max_bonus]`.

    - `substrates_served` is the list of substrates this vacant has
      executed on.
    - `success_rate_per_substrate` is the per-substrate success rate
      ∈ [0, 1].
    - Bonus is `max_bonus * diversity_factor * success_factor`, where:
        - `diversity_factor` saturates at 1.0 once `n_substrates >= 4`
          (log curve with reference 4).
        - `success_factor = mean(success_rates over served substrates)`.
    """
    if max_bonus < 0:
        raise ValueError(f"max_bonus must be >= 0; got {max_bonus}")
    if not substrates_served:
        return 0.0
    n = len(substrates_served)
    diversity_factor = min(1.0, math.log(1.0 + n) / math.log(1.0 + 4.0))
    rates = [
        max(0.0, min(1.0, float(success_rate_per_substrate.get(s, 0.0)))) for s in substrates_served
    ]
    success_factor = sum(rates) / n if rates else 0.0
    return max_bonus * diversity_factor * success_factor
