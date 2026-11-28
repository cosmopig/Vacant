# PREREG ADDENDUM — invoice holdout confirmatory (frozen before row 3+)

**Frozen:** 2026-11-28T14:05:00Z (supervisor VAC-1; **2 rows** already on disk — **not used for analysis**)

**SHA256 (this file, bytes on disk):** record in `data/holdout_05b/PREREG_SHA256.json` at run start.

## CPU priority

1. **Invoice holdout** n=150 answerable — **confirmatory** small-model delivery test  
2. **Stop** partial 0.5B filing (exploratory floor only; **not** confirmatory)  
3. **1.5B filing** only if holdout completes with wall time remaining

## Arms (equal-cost logging)

| Arm | Calls (intent) |
|-----|----------------|
| `VACANT` | 1 + ≤4 field micro |
| `BLIND` | 2 full JSON |
| `MAJ3` | 3 full JSON |
| `LPB3` | 3 full JSON + logprob |

Every row logs `prompt_tokens`, `completion_tokens`, `cpu_seconds`, `n_calls`.

## Primary inferential comparison

**Pre-specified:** `VACANT` vs **`MAJ3`** McNemar exact (paired on `task_id`), answerable tasks only.

**Descriptive (not multiplicity-adjusted):** `VACANT` vs `BLIND`, `VACANT` vs `LPB3`; **equal-cost check:** report mean tokens & CPU per arm; flag if any baseline differs &gt;15% from VACANT mean (post-hoc descriptive only).

## Selective delivery 2×2 (invoice: all arms ship a candidate)

| Cell | Definition |
|------|------------|
| released-correct | `oracle_whole_success` |
| released-wrong | shipped ∧ ¬oracle |
| held-* | **0** for this harness (no withhold arm on holdout primary); ESCALATE rate **0** unless gating arm added |

Pre-gate **repair** = visible pass rate. Post-gate **risk** = wrong/oracle among shipped.

## Net utility grid (frozen, no tuning)

`U = (1[released_correct] - λ·1[released_wrong] - c·1[escalate]) / n`  
λ ∈ {1, 3, 10}, c ∈ {0, 0.5}. Compare arms at **same** coverage only descriptively.

## Filing relabel

All Filing offline/contract numbers on gold-evidence `page_text` = **leaky dev upper bound**, not confirmatory evidence.