# PREREG — Round 2 (field-locked repair) — frozen before any holdout run

**Branch:** `research/trust-delivery-lift`  
**Pilot 1:** preserved under `../data/` + `../REPORT.md` § Pilot 1 (honest null, n=12).

## Primary hypothesis (Rank 1)

On **6–8 field invoice/order extraction** with **runtime acceptance checks** (no oracle leakage), **VACANT field-locked repair** (harness merges per-field micro-prompts only when a field passes checks) improves **held-out whole-deliverable exact match** vs **equal token & CPU-second** baselines on **Qwen2.5-0.5B** or **1.5B** (chosen by dev Pass@1 ∈ [15%, 40%]).

## Task bank

- Generator: `generate_bank.py` → `tasks_r2.json`
- **dev_ids:** 20 (calibration only)
- **holdout_ids:** ≥150 answerable (`answerable=true`)
- **gating_ids:** holdout includes **25%** `answerable=false` (corrupted/contradictory); primary metrics use answerable subset only; secondary uses full mix.
- **Clusters:** `template_id` ∈ {T1..T5}; McNemar clustered by template in `recompute_r2.py`.

## Runtime checks (visible; no gold)

Per field + global: JSON schema keys, ISO-4217 in allowlist from doc, ISO-8601 dates, `due_date >= invoice_date`, `|subtotal + tax - total| <= 0.01`, **provenance substring** of normalized value in source text, `order_id` alnum length 6–16.

## Held-out oracle

Exact normalized match on all 8 fields (only after run).

## Arms (primary; matched budget)

All arms track `prompt_tokens`, `completion_tokens`, `cpu_seconds`.

| Arm | Description |
|-----|-------------|
| `ONE` | 1× full JSON @ greedy |
| `MAJ3` | 3× full JSON @ T=0.7; **per-field majority** (no checks) |
| `LPB3` | 3× full JSON @ T=0.7; pick **entire JSON** with highest mean token logprob |
| `VACANT` | 1× full JSON; lock passing fields; ≤`MAX_FIELD_RETRIES` micro-prompts per failing field; **harness patch** only if field check passes |
| `STITCH` | 3× full JSON @ T=0.7; **zero-prompt** per-field first check-passing value across samples (deterministic order sample 0→2) |

**Budget parity rule:** `VACANT` field micro-calls capped so mean total tokens/task ≤ mean(`MAJ3`) + 10% (reported; no post-hoc trim).

**Frozen baseline for McNemar:** `MAJ3` if whole-success rate highest among `ONE`,`MAJ3`,`LPB3` on dev; else `LPB3`.

## Success metrics

- Whole-deliverable oracle success rate (all answerable holdout tasks in denominator; failures/timeouts count).
- Paired `wrong→right` / `right→wrong` vs frozen baseline per task.
- **McNemar exact** (primary: `VACANT` vs frozen baseline).
- **2×2** per arm: visible all-fields-pass × oracle whole-success (logged per row).

## Secondary (gating utility; same tasks)

| Arm | Calls |
|-----|-------|
| `GATE_VACANT` | 1× + reject if any visible check fails |
| `GATE_LOGPROB` | 1× + ship if mean logprob ≥ τ (τ from dev to match ~VACANT coverage) |
| `GATE_SC2` | 2× @ T=0.7; ship if identical JSON string |
| `GATE_SV` | 2×; call2 yes/no self-verify |

Metrics: SFR = P(wrong|shipped), AURC on risk–coverage, U(λ) for λ∈{1,2,5}, at matched coverage vs `GATE_VACANT`.

## Stopping

One holdout pass per arm; no optional stopping.

## SHA256

Recorded in `data/r2/PREREG_SHA256.json` at freeze (before holdout).