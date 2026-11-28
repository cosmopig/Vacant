# FENCE ADDENDUM — zombie `holdout_05b` contamination (frozen 2026-11-29T01:05:00+08:00)

**Frozen before any post-addendum read of confirmatory row outcomes.**

## Incident

- Broken-checker harness continued appending to `data/holdout_05b/` through **hold_095** while `holdout_05b_confirmatory/` was live → **CPU contention** + git exposure (`3240dc4a`, **2026-11-28T16:04Z**) **before** `PREREG_HOLDOUT_PRIMARY_SEAL_20261129.md` (**~16:10Z**).
- Per-task JSON in the old dir carries `unknown_field` on `vendor` (pre-amendment checker).

## Locked index

- **K = 95** — highest `hold_NNN` with any `data/holdout_05b/hold_NNN__*.json` artifact from the zombie writer (filesystem audit, **no row JSON reads**).

## Task sets (exact IDs in manifest JSON)

| Set | Definition | Role |
|-----|------------|------|
| `pilot_excluded` | hold_000–hold_021 | Exploratory only; never primary |
| `zombie_exposed` | hold_022–hold_K | Outcomes in git from broken checker; **not primary** |
| **`primary_confirmatory`** | hold_(K+1)–hold_149 (**hold_096–hold_149**, n=54) | **Sole primary** McNemar VACANT vs MAJ3 |
| `secondary_sensitivity` | hold_022–hold_149 (n=128) | Pre-registered **secondary**; same McNemar + VACANT vs BLIND; **contaminated / peeked** — label in REPORT |
| `contention_rerun_candidates` | hold_022–hold_K | May be **re-run** once under clean CPU rule below if wall-time allows; **do not** replace primary without new prereg |

## Primary endpoint (unchanged test, restricted IDs)

- Outcome: `oracle_whole_success` on **answerable** tasks in **`primary_confirmatory` only**.
- Test: exact McNemar two-sided **α=0.05**, **VACANT** vs **MAJ3**.
- Source rows: `data/holdout_05b_confirmatory/rows.jsonl` filtered to manifest IDs (confirmatory CPU treated as **tainted** for interpretation; primary is the least-exposed contiguous tail).

## Contention re-run rule (frozen)

- **Do not** restart `primary_confirmatory` tasks.
- **Optional** single re-run: `contention_rerun_candidates` only, sequential (no parallel `holdout_05b` harness), output → `data/holdout_05b_rerun_seed0/`; **exploratory** unless a future addendum promotes it.

## Disclosures required

- Zombie process, commit `3240dc4a`, seal ordering, VACANT **greedy-visible-pass** vs Maj3 vote-of-3 mechanism (see `MECHANISM_HONESTY.json`).

SHA256: `data/holdout_05b_confirmatory/FENCE_ADDENDUM_SHA256.json`