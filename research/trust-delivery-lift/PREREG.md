# PREREG — trust-delivery-lift (2026-11-28)

Frozen before confirmatory batch (`confirm_ids`, 12 tasks).

## Question

On structured source-grounded extraction with a **local small instruct model** (Qwen2.5-0.5B on CPU), does **EVR** (evidence-located visible failures + one equal-budget repair call) improve **whole-deliverable success** vs the best cheap baseline at **two calls per task**?

## Tasks

- Bank: `research/trust-delivery-lift/tasks_bank.json`, sha256 recorded in `data/manifest_pilot.json` at pilot freeze.
- **Pilot** (mechanism screen): `pilot_ids` — 12 distinct org profiles; not used for confirmatory claim.
- **Confirmatory**: `confirm_ids` — 12 held-out profiles; one row per task×arm.

## Equal cost

Every arm: **call1** weak prompt + **call2** arm-specific follow-up. Token totals counted per row.

## Arms

| Arm | Call2 semantics |
|-----|-----------------|
| KEEP | Re-output / minimal polish (placebo second call) |
| BLIND | Full rewrite |
| BLANKS | Fill only empty keys |
| EVR | Fix fields failing **visible** checks with cited source spans |
| RAND | Repair 1–2 fields chosen uniformly from visible failures |

Pilot picks baseline = max `whole_success_rate` among KEEP, BLIND, BLANKS, RAND (frozen before confirmatory).

## Primary comparison (confirmatory)

**EVR** vs frozen baseline on `confirm_ids`:

- Primary metric: **whole_success_final** (all required fields hidden-correct).
- Net harm: `right_to_wrong`, `wrong_to_right` per task vs shared call1 draft.
- Success threshold for mechanistic claim: EVR rate exceeds baseline by **≥5pp** with Wilson 95% CI lower bound **> baseline point estimate** (exploratory if n=12 fails this).

## Scorer

- `scorer.py` typed fields; hidden gold only at grade time.
- Visible checks: presence + parseable type (no gold).
- Synthetic must-equal / must-differ suite must pass (`--selftest-scorer`).

## Stopping

Single confirmatory pass (no optional stopping). Pilot may abort EVR if wrong→right = 0 on ≥10/12 pilot tasks.

## SHA256 at freeze

Filled in `data/PREREG_SHA256.json` when confirmatory starts.