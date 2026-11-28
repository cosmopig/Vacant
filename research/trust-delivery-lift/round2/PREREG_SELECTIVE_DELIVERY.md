# PREREG — selective delivery metrics (frozen 2026-11-28T14:05:00Z)

## 2×2 + ESCALATE (every arm)

- released-correct / released-wrong / held-correct / held-wrong  
- `escalate_rate` (contract aggregate ESCALATE when applicable; invoice holdout primary arms → 0)

## Coverage floor (consensus falsifier)

Consensus “win” **invalid** unless `coverage_auto_pass_eligible ≥ 5%` **and** uncontested false-release ≤ primary false-release + 2pp.

Blocking majority of correct rows without meeting coverage floor = **refuse gate**, not accountability win.

## Utility (no threshold tuning)

Fixed grid λ ∈ {1,3,10}, c ∈ {0,0.5} on invoice rows. No logprob threshold sweep.