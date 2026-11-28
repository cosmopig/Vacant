# PREREG — Round 2 (GAP_MAP pivot) — frozen before holdout / filing online

**Branch:** `research/trust-delivery-lift`  
**Pilot 1:** honest null (`../REPORT.md` § Pilot 1, n=12).  
**Binding avoids:** GAP_MAP §4 — no plain retry-on-fail as main story, no self-judging, signed logs as research product, untrained advisor hints, history-trust routing, per-field averages as headline.

## P0 (prerequisite, no model calls)

**Must-match / must-differ control suite** for extraction typing: scale (3M vs 3B), sign, currency, period/column, unit, required sets.

- Code: `typed_value.py` + `validate_controls.py` + legacy `../scorer.py` controls
- Artifact: `data/control_extraction_results.json` (must pass before any round-2 scorer run counts)

## Rank 1 — Field-locked repair (invoice bank; gap 2)

**Claim under test:** lock fields that pass runtime checks; re-ask only failing/missing fields; **harness merges** patches (not full-document rewrite). Untested at ≤1.5B on whole-deliverable in literature (GAP_MAP gap 2).

**Primary baseline (matched cost):** `BLIND` — blind full resample / second independent draft at matched token+CPU budget.  
**Allowed baselines, not our contribution:** `MAJ3`, `BEST_OF_N`, `LPB3`, `ONE`.

Task bank: `generate_bank.py` → `tasks_r2.json` (≥150 answerable holdout, template clusters).  
Visible checks: `checks.py` (no gold). Oracle: exact normalized 8-field match post-run.

Arms (2-call parity where applicable; shared call-1 draft file when frozen):

| Arm | Role |
|-----|------|
| `BLIND` | **Primary baseline** — 2× full JSON, oracle pick is hidden; deliver second sample |
| `VACANT` | Lock passing fields; micro-prompt per failing field; harness merge |
| `STITCH` | 3× samples; zero-prompt per-field first check-passing stitch |
| `MAJ3` | Baseline only — per-field majority, no checks |

**McNemar:** `VACANT` vs `BLIND` on holdout; clustered by `template_id`.

## Rank 1b — Filing-Evidence flagship (gap 1; if P0 + offline stop rule pass)

**Dataset:** [pramana-research/filing-evidence](https://huggingface.co/datasets/pramana-research/filing-evidence) (Apache-2.0; ~1k questions, 90 filings; gold carries value/scale/unit/period). Paper: [Show Your Work arXiv:2611.24990](https://arxiv.org/abs/2611.24990).

### (a) Offline typed audit (zero model cost) — **DONE before online**

On model answers with `failed_check is null` (quote check passed):

- **Typed check:** value in cited span; header scale vs answer scale; no gold at runtime (`filing/typed_filing_check.py`).
- **Stop rule:** ineffective if catch &lt;30% among quote-pass-but-value-wrong **or** false reject &gt;5% among quote-pass-and-value-correct.
- **First result (qwen3.5-9b C1):** `filing/data/offline_typed_audit_qwen_c1.json` — catch **74.3%** (75/101), false reject **4.8%** (35/724) → **proceed** to bounded online CPU arms.

### (b) Online CPU (if stop rule passes)

Models: **Qwen2.5-0.5B** and **1.5B** on ~20 filings (~220 questions), ≤2 calls/question, shared first answer across arms:

| Arm | Description |
|-----|-------------|
| A `PLAIN` | deliver first answer |
| B `QUOTE_RETRY` | original quote check + retry (dataset-style; baseline, not contribution) |
| C `BLIND` | blind resample; deliver second |
| D `TYPED_REASK` | typed fail → targeted re-ask listing alternatives |
| E `TYPED_REFUSE` | typed fail → not certified / no delivery |

**Main metric:** share of filings with **zero wrong** delivered answers; bootstrap CIs over whole filings.  
**No-model rule baseline:** header scale + latest table column (`rule_baseline.py`).

## Secondary (gating)

Unchanged intent: `GATE_*` on invoice bank only if Rank 1 holdout completes.

## SHA256

`data/r2/PREREG_SHA256.json` updated at holdout freeze (invoice). Filing offline prereg pinned by commit hash + answer file sha256 in audit JSON.