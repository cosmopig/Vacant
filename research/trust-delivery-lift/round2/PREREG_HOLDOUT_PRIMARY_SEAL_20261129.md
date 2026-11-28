# PRIMARY SEAL ADDENDUM — invoice holdout confirmatory (frozen 2026-11-29T00:10:00+08:00)

Supersedes nothing in the inferential contract; **narrows** what the confirmatory analysis claims.

## Primary endpoint (frozen)

- **Population:** `holdout_answerable_ids` **excluding** `pilot_excluded_tasks.json` (hold_000–hold_021).  
  **Unanswerable** holdout tasks are **out of scope** — no false-release / delivery claim there.
- **Outcome:** `oracle_whole_success` on the delivered `final` JSON per task×arm.
- **Contrast:** **VACANT** vs **MAJ3**.
- **Test:** exact **McNemar** two-sided, **α = 0.05** (library: `vacant_network.research.mcnemar_exact`).
- **Rows file (confirmatory):** `data/holdout_05b_confirmatory/rows.jsonl` only.

## Task order (truncation fairness)

- Task list = `tasks_r2.json` → `split.holdout_answerable_ids` minus pilot exclusion, **fixed generator order** (not re-shuffled at runtime). Harness `--seed` affects arm-internal RNG (BLIND/MAJ3 sampling) only, **not** task sequence.
- If the run stops before all planned task×arm rows exist (deadline / infra), primary analysis uses **n tasks actually completed** for **all four arms pairwise-present**; report **stopping reason** and **n reached** — no imputation.

## Secondary / exploratory (not primary)

- Gating utility grid, LPB3 logprob gate, draft-call floors, cost tables — **exploratory**; see gating quarantine notes in amendment + `COST_PARITY_AUDIT.md`.

## Pinned artifacts

| Artifact | Role |
|----------|------|
| `PREREG_HOLDOUT_AMENDMENT_20261128.md` | Checker fence, arms |
| `PREREG_HOLDOUT_ADDENDUM.md` | Original holdout arms |
| `checks.py` (SHA256 in manifest) | Visible/oracle checks |
| This file | Primary endpoint seal |

SHA256 of this file recorded in `data/holdout_05b_confirmatory/PRIMARY_SPEC_SHA256.json`.