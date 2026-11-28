# CRITIQUE_LOG — `research/trust-delivery-lift`

Record of external (Gemini) critiques and responses.

| Time (UTC) | Critique | Response |
|------------|----------|----------|
| 2026-11-28 13:20 | *(awaiting first relay)* | Initial push: typed scorer + synthetic controls; equal 2-call arms; pilot v1 complete. Documented known design gap (non-paired call1 per arm) before v2 fix. |
| 2026-11-28 13:35 | *(self-review / expected)* Speed over scale; 0.5B only | Confirmed no 7–9B; Colab notebook uses 0.5B CPU path only. |
| 2026-11-28 13:35 | *(self-review)* Pairing & visible grader | v2 `freeze_drafts.py`, visible currency/city/source-digit checks; confirmatory held-out null. |
| 2026-11-28 21:23 | **Gemini** (upload `ideas-20261128-2123`): (1) n=12 no power—need n≥120–200; (2) 8% Pass@1 floor—not accountability; (3) separate visible vs oracle 2×2; no credit for abstention; (4) 0.5B in-context editing paralysis—use harness merge not full JSON rewrite; (5) BLIND weak baseline—use Maj@3/logprob Bo3 matched CPU+tokens | **Pilot 1 kept as honest null.** Round 2: `PREREG_ROUND2.md`, invoice 8-field bank, field-locked VACANT + STITCH, Maj3/LPB3 baselines, n≥150 holdout, gating secondary Rank 4. |
| 2026-11-28 ~17:30 UTC | **User + GAP_MAP** (`GAP_MAP_94bb.md`, `LINKS_5e63.md`): P0 typed extraction controls; round-2 primary = field-lock + **BLIND** as key baseline (Maj/BoN not contribution); Filing-Evidence offline typed audit + stop rule; binding avoid list §4; milestone ~06:00 Taipei = P0 + one real result | **Done:** `validate_controls.py` → 15/15 controls; **Filing offline** on HF qwen3.5-9b C1: catch **74.3%** on quote-pass-wrong (n=101), false reject **4.8%** (n=724), stop rule **pass** → online filing arms allowed. `PREREG_ROUND2.md` rewritten. Maj3 demoted to non-contribution baseline in prereg. |

### PRE-RUN self-critique (standing rule) — contract / zero-discretion reframe — 2026-11-28 ~21:37 UTC

**Strongest objection (owner):** Renaming “typed check” to “contract” still hides **requester judgment** (which clauses exist, tolerances, when to ESCALATE). If those choices are made **after** seeing false rejects, accountability is theater and trust does not transfer.

**Confounds:** (1) Filing **primary** contract still reads `gold.unit/scale/period` from `questions.jsonl`—benchmark answer-key fields, not a separately authored legal doc. (2) **Independent** compiler was not yet truly blind (could leak gold). (3) `frozen_at=now()` mutates hashes across runs. (4) “100% reproducibility” is same-process replay, not a hostile third party with only contract bytes. (5) Evidence page stub ≠ full filing HTML—provenance clause may be **incomplete by construction**, making false rejects look like “incompleteness” without fixing delivery.

**Judgment-laden / post-hoc risk:** Tolerances `0.001 / 0.5`, multi-column ESCALATE threshold `>2`, and which ops are in scope were tuned on qwen3.5-9b C1 offline curves—**forbidden** unless frozen before that audit and never changed after.

**What would falsify the reframe:** (a) **Independent vs primary** delivery decisions agree &lt;90% on held tasks → lift is not contract-stable. (b) **False-release rate** among contract `PASS` deliveries is high vs oracle → gates do not reduce wrong shipment. (c) **ESCALATE** rate ~0 while humans would dispute definitions → semantic gap still decided silently somewhere. (d) After freezing, **changing only** `distinct_numbers_escalate_above` moves false-reject/catch materially → still discretionary tuning.

**Survival conditions (proceed only if enforced):** Freeze opcode set + tolerances in `round2/contract/PREREG_CONTRACT.md` **before** any new metrics; hash **excludes** timestamps; `freeze_contracts.py` writes bytes **before** online harness reads them; independent author uses **question string + form only** (no `gold` JSON); report **35 false rejects** as **documented incompleteness** (no clause narrowing post hoc); third-party check = **re-run `executor.py` on frozen contract files** (agreement must be 100%); online small-model results labeled **separate** from 9b checker validity.

**Verdict:** **Proceed** with implementation under the survival conditions above; **do not** claim “zero judgment” globally—claim **judgment relocation** to requester + named `owner_escalate`, executor fixed.

| 2026-11-28 ~21:38 UTC | **Owner** (standing rule): critique before contract experiment | **Logged above.** Code changes: frozen hashes, independent blind compiler, `PREREG_CONTRACT.md`, metrics + REPORT “Where judgment lives”. |
| 2026-11-28 ~21:40 UTC | **Self-falsification (contract metrics on qwen C1)** | Independent vs primary same delivery decision **47.9%** (≪90% survival rule) → **cannot** claim delivery lift is stable across blind contract authors; primary **ESCALATE 0%** (multi-column disputes not surfaced on primary profile). False-release among contract PASS **3.6%** (26/721). Re-run agreement **100%**. Report as **judgment relocation evidence + contract-author sensitivity**, not “solved trust.” |

### PRE-RUN — consensus contract + CPU subset — 2026-11-28 ~21:45 UTC

**Objection:** “Consensus” can smuggle judgment if authors are not truly blind or if we pick the threshold ≥2 **after** seeing 52% disagreement.

**Confounds:** (1) Only **three** scripted authors—not human requesters. (2) Consensus measured on **opcode sets**, but param drift (tolerance) might still differ. (3) Subset **random seed** chosen after seeing slow run—must fix seed **before** restarting harness. (4) Killing dev tmux mid-write could corrupt rows—checkpoint append-only OK.

**Post-hoc risk:** Dropping clauses that hurt catch rate on qwen9b—**forbidden**; consensus rule is structural only.

**Falsifier:** Under consensus, **catch on quote-pass-wrong** falls below primary catch by **>10 pp** OR **false-release** rises **>2 pp** → consensus “lift story” dead—report plain null.

**Survival:** `PREREG_CONSENSUS_CONTRACT.md` + seed **42** + three author IDs frozen **now**; metrics on qwen C1 only before small-model arms complete.

**Verdict:** Proceed.

### PRE-RUN — overnight CPU filing subset — 2026-11-28 ~21:46 UTC

**Objection:** Shrinking n to finish = power failure; Colab fallback = different stack.

**Falsifier:** If 0.5B filing zero-wrong rate CI overlaps all arms → no mechanism story anyway.

**Survival:** Pre-registered **220 questions / 20 filings** (`subset_prereg_seed42.json`); same arms; label subset on every row.

**Verdict:** Proceed; kill competing dev harness.

| 2026-11-28 ~21:50 UTC | **Consensus contract metrics (post-prereg)** | **Opcode agree 3/3:** provenance, value_in_span. **2/3:** multi_column_escalate, scale, unit — **521** primary PASS → consensus ESCALATE. **Param split:** status_found_fields on **all** tasks (different required field lists). Consensus catch **100%** vs primary **74%** on quote-pass-wrong but **524/724** correct rows blocked vs **36**. False-release PASS: primary **3.6%**, consensus **0%**. **Lift under consensus ≠ shippable lift** — honesty trade, not falsifier triggered on catch drop. |

## Anticipated critic targets (pre-buttress)

## Anticipated critic targets (pre-buttress)

1. **Non-paired drafts in pilot v1** — Fixed in v2: `freeze_drafts.py` + `harness.py --drafts`.
2. **Visible grader too weak (EVR starved)** — Added currency-required visible rule, hq_city comma rule, digit-in-source check (no gold).
3. **Scale / big models** — Scope locked to Qwen2.5-0.5B CPU only; Colab notebook deferred / 0.5B only.