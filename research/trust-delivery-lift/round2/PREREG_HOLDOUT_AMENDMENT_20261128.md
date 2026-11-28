# AMENDMENT — holdout confirmatory resume (frozen 2026-11-28T15:02:00Z)

## Checker fix (vacant.contract not involved; invoice checks.py)

- **Bug:** `vendor` field fell through to `unknown_field` → **100% visible fail** while oracle could pass.
- **Fix:** `check_field` handles `vendor` with provenance (dev gold self-test passes 170 tasks).
- **Checker version:** `invoice.visible_checker/2` (record SHA256 of `checks.py` in manifest).

## Contamination fence

- **pilot_excluded:** `hold_000` … `hold_021` (22 tasks, rows 0–87). **Exploratory only.** Never in confirmatory McNemar.
- **Confirmatory:** remaining **~128** `holdout_answerable_ids` not yet run after resume.

## Arms & primary (unchanged)

`BLIND`, `VACANT`, `MAJ3`, `LPB3`. Primary inferential: **VACANT vs MAJ3** exact McNemar.

## Cost accounting (per arm, cold)

Each arm records **its own** call list; no cross-arm draft sharing.  
Per row also logs **`draft_oracle`** / **`draft_visible`** from **call 1 only** (zero-repair floor).

## Gating secondary (exploratory, same amendment — zero extra model calls)

| Arm | Ship iff |
|-----|----------|
| VACANT | `visible_all_pass` |
| BLIND | 2/2 draft JSON strings identical |
| MAJ3 | 3/3 identical |
| LPB3 | `mean_logprob >= LPB3_LOGPROB_TAU` |

**`LPB3_LOGPROB_TAU = -12.5`** fixed from **dev** LPB3 sample medians (`ops` note: dev JSON lacks logprob in row → use frozen constant from dev run 2026-11-28, not tuned on holdout).

Utility grid λ∈{1,3,10}, c∈{0,0.5} on **gated ship** decisions with true per-arm costs.

## Dropped (logged)

No post-hoc non-inferiority / “same accuracy lower cost” from exploratory interim.

## Resume rule

**No interim outcome peeking** until confirmatory n complete or deadline.