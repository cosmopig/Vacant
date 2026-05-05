"""Padv P2 — adversarial tests for `vacant.identity.wash_cost`.

Spec anchors:
- `architecture/components/P2_identity.md` §3.4 (cost formula),
  D003 D4 (cost ≥ 2·gain framing)
- `dispatch/Padv_review.md` §"Wash cost evasion"
"""

from __future__ import annotations

import math

import pytest

from vacant.identity.errors import IdentityError
from vacant.identity.wash_cost import WashCostWeights, compute_wash_cost

# --- Attack 1: false_claim_weight evasion (claim weight = 0) -----------------
# Defense (C): even at `false_claim_weight = 0` the per-history-entry cost
# remains positive (history term: w_h * depth * (1 + 0) = w_h * depth).
# Attackers who set the weight to zero in their cost-modelling still pay
# for every claimed entry. The "false claim" multiplier *amplifies* the
# per-entry cost; setting it to zero only flattens that amplification.


def test_attack_zero_false_claim_weight_still_grows_with_depth() -> None:
    a = compute_wash_cost(0, 0, 0, false_claim_weight=0.0)
    b = compute_wash_cost(100, 0, 0, false_claim_weight=0.0)
    assert b > a
    assert b > 99.0  # default w_h = 1.0, so 100 entries cost >= 100


# --- Attack 2: negative false_claim_weight rejected --------------------------
# Defense (P): negative weights are validated at the API boundary.


def test_attack_negative_false_claim_weight_rejected() -> None:
    with pytest.raises(IdentityError):
        compute_wash_cost(10, 0, 0, false_claim_weight=-0.5)


# --- Attack 3: NaN / infinity weight rejected at construction ---------------
# Defense (P): `WashCostWeights.__post_init__` rejects negative; we
# additionally verify that NaN doesn't survive (NaN < 0 is False, so we
# accept NaN today — document that as residual). For now this test
# pins behaviour: NaN inputs propagate to NaN cost (which surfaces
# downstream rather than silently zeroing).


def test_attack_nan_weight_propagates_not_zero() -> None:
    # Padv finding: NaN is *not* rejected by current code (NaN < 0 is False).
    # The current behaviour is to propagate NaN rather than silently
    # short-circuit; downstream consumers (P3) must treat NaN cost as
    # "unknown" and fall back to maximum suspicion. This test pins that
    # contract so a future "silently treat NaN as 0" change would fail.
    cost = compute_wash_cost(10, 0, 0, false_claim_weight=math.nan)
    assert math.isnan(cost)


# --- Attack 4: extreme depth doesn't overflow -------------------------------
# Defense (P): float arithmetic; very large but finite inputs yield finite
# float costs (well below sys.float_info.max for reasonable inputs).


def test_attack_extreme_depth_remains_finite() -> None:
    cost = compute_wash_cost(10**9, 0, 0, false_claim_weight=10.0)
    assert math.isfinite(cost)
    assert cost > 0


# --- Attack 5: claim cheap weights but inputs still gated -------------------
# Defense (P): even with all-zero weights, negative INPUTS are rejected.


def test_attack_all_zero_weights_does_not_unblock_negative_inputs() -> None:
    weights = WashCostWeights(0.0, 0.0, 0.0)
    with pytest.raises(IdentityError):
        compute_wash_cost(-1, 0, 0, weights=weights)


# --- Attack 6: false_claim_weight only multiplies HISTORY term --------------
# Defense (P): per spec, the false-claim multiplier applies to history
# only — claiming many attestations or substrates is not amplified by
# false_claim_weight (those have other defenses elsewhere). This test
# pins that contract.


def test_attack_false_claim_weight_only_amplifies_history_term() -> None:
    base = compute_wash_cost(0, 50, 50, false_claim_weight=0.0)
    cranked = compute_wash_cost(0, 50, 50, false_claim_weight=10.0)
    assert base == cranked
