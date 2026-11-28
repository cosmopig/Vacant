# CRITIQUE_LOG — `research/trust-delivery-lift`

Record of external (Gemini) critiques and responses.

**Timezone:** Rows through 2026-11-28 ~13:35 are **UTC** (VM). Rows marked **~21:xx** were mis-labeled UTC — they are **Asia/Taipei** local on commit day (≈ UTC+8).

| Time | Critique | Response |
|------------|----------|----------|
| 2026-11-28 13:20 | *(awaiting first relay)* | Initial push: typed scorer + synthetic controls; equal 2-call arms; pilot v1 complete. Documented known design gap (non-paired call1 per arm) before v2 fix. |
| 2026-11-28 13:35 | *(self-review / expected)* Speed over scale; 0.5B only | Confirmed no 7–9B; Colab notebook uses 0.5B CPU path only. |
| 2026-11-28 13:35 | *(self-review)* Pairing & visible grader | v2 `freeze_drafts.py`, visible currency/city/source-digit checks; confirmatory held-out null. |
| 2026-11-28 21:23 Asia/Taipei | **Gemini** (upload `ideas-20261128-2123`): (1) n=12 no power—need n≥120–200; (2) 8% Pass@1 floor—not accountability; (3) separate visible vs oracle 2×2; no credit for abstention; (4) 0.5B in-context editing paralysis—use harness merge not full JSON rewrite; (5) BLIND weak baseline—use Maj@3/logprob Bo3 matched CPU+tokens | **Pilot 1 kept as honest null.** Round 2: `PREREG_ROUND2.md`, invoice 8-field bank, field-locked VACANT + STITCH, Maj3/LPB3 baselines, n≥150 holdout, gating secondary Rank 4. |
| 2026-11-28 17:30 Asia/Taipei | **User + GAP_MAP** (`GAP_MAP_94bb.md`, `LINKS_5e63.md`): P0 typed extraction controls; round-2 primary = field-lock + **BLIND** as key baseline (Maj/BoN not contribution); Filing-Evidence offline typed audit + stop rule; binding avoid list §4; milestone ~06:00 Taipei = P0 + one real result | **Done:** `validate_controls.py` → 15/15 controls; **Filing offline** on HF qwen3.5-9b C1: catch **74.3%** on quote-pass-wrong (n=101), false reject **4.8%** (n=724), stop rule **pass** → online filing arms allowed. `PREREG_ROUND2.md` rewritten. Maj3 demoted to non-contribution baseline in prereg. |

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

### PRE-RUN — uncontested vs contested split — 2026-11-28 ~13:55 UTC

**Objection (owner + self):** Consensus blocking **524/724** correct rows is a **non-shippable “refuse everything” gate**; **100% catch** on wrong rows is **trivial** when almost nothing PASSes. **521** `multi_column_escalate` disagreements dominate — not proof of smart gating.

**Confound:** Uncontested region defined by **three scripted authors**, not human panels. “Auto-decided” may be tiny coverage.

**Post-hoc risk:** Picking coincident-primary-consensus to rescue shipping **after** seeing block rate — **forbidden**.

**Falsifier:** On **uncontested-only** auto-PASS, false-release **≥ primary false-release** OR coverage **&lt;5%** → “honest coverage” claim fails.

**Verdict:** Pre-register `PREREG_COVERAGE_SPLIT.md` **now**; metrics on qwen9b first, then small-model arms **without** changing thresholds.

| 2026-11-28 ~13:55 UTC | **Consensus refuse gate critique** | Logged above; split analysis prereg + script before reading 0.5B filing outcomes beyond interim counts.

| 2026-11-28 21:50 Asia/Taipei | **Consensus contract metrics (post-prereg)** | **Opcode agree 3/3:** provenance, value_in_span. **2/3:** multi_column_escalate, scale, unit — **521** primary PASS → consensus ESCALATE. **Param split:** status_found_fields on **all** tasks (different required field lists). Consensus catch **100%** vs primary **74%** on quote-pass-wrong but **524/724** correct rows blocked vs **36** (**35→36** after contract-backed executor). False-release PASS: primary **3.6%**, consensus **0%**. **Lift under consensus ≠ shippable lift** — honesty trade, not falsifier triggered on catch drop. |

### PRE-RUN — Supervisor VAC-1 (2026-11-28 22:05 Asia/Taipei) — before acting

**Objection:** Pivoting CPU to holdout after peeking at 0.5B filing interim is post-hoc; adding MAJ3 now could be tuned to beat BLIND; relabeling Filing without re-run is cheap exit.

**Confounds:** 2 holdout rows already exist; Filing numbers still in git.

**Falsifier:** Holdout VACANT vs MAJ3 null with honest costs → no delivery lift claim.

**Survival:** Freeze `PREREG_HOLDOUT_ADDENDUM.md` + SHA256 **before** reading row 3+; stop filing; relabel Filing **leaky dev upper bound**; scripted “independent authors” labeled honestly.

**Verdict:** Act per ranked list.

| 2026-11-28 22:05 Asia/Taipei | **Supervisor VAC-1 (hourly)** | **(1)** Stop 0.5B filing (floor 0/6); **holdout first** BLIND/VACANT/**MAJ3**/**LPB3** n=150. **(2)** Equal-cost logging; McNemar VACANT vs MAJ3 frozen. **(3)** Filing = **leaky dev upper bound** (gold-evidence page stub). **(4)** 2×2 + U grid prereg; consensus needs coverage floor. **(5)** Timezone fix; scripted authors honest; 35→36 noted. |

### PRE-RUN — Supervisor VAC-1 (2026-11-28 23:00 Asia/Taipei) — visible checker pause

**Objection:** Resuming holdout before fixing checker repeats false V− on oracle-correct rows; any amendment after seeing 22-task interim risks tuning MAJ3/τ to interim discordance.

**Confounds:** Rows 0–87 run under `unknown_field` on `vendor`; VACANT **n_calls≈2** is mostly **early visible-all-fail** stopping micro-repair, not cross-arm draft cache (each arm calls `lm.generate` independently).

**Falsifier:** After `checks.py` fix, dev gold **170/170** visible+oracle pass — if holdout confirmatory still shows **100% V−**, checker still broken.

**Survival:** Fence **hold_000–hold_021** as `pilot_excluded`; hashed `PREREG_HOLDOUT_AMENDMENT_20261128.md` + `checks.py` SHA256; resume only `holdout_05b_confirmatory/` with `--exclude-ids`; no peeking until confirmatory complete; exploratory interim logged (BLIND/VACANT 14/22 oracle, MAJ3 13/22, 1 VACANT–MAJ3 discordant); dropped post-hoc cost non-inferiority.

**Verdict:** Fix checker on dev tests only; push amendment; resume confirmatory uninterrupted.

| 2026-11-28 23:00 Asia/Taipei | **Supervisor VAC-1 (hourly)** | **Pause holdout** — `vendor` → `unknown_field`; fence 22 tasks; amendment + cost/draft logging + gating secondary exploratory; no post-hoc Pareto claim. |

### PRE-RUN — overnight watch + recompute + 1.5B (2026-11-28 23:01 Asia/Taipei)

**Objection:** Polling tmux then running `recompute_r2.py` mid-flight breaks “no peek”; starting 1.5B before holdout gate wastes CPU; interim at 10:30 without fixed n invites threshold shopping on partial McNemar.

**Confounds:** Confirmatory may finish **after** 10:30 Taipei (~5 h at ~40 s/row); 1.5B filing same contract stack as stopped 0.5B — still not confirmatory delivery evidence.

**Falsifier:** If confirmatory completes with oracle rates flat vs BLIND → primary null stands even with full n.

**Survival:** Peek only **row counts** until 512 rows OR clock **≥11:30 Taipei** (interim stop **10:30** if rate projects miss); recompute **only** `holdout_05b_confirmatory/rows.jsonl`; 1.5B **after** holdout gate; REPORT labels exploratory gating + any partial confirmatory with **stopping reason**; no post-hoc Pareto.

**Verdict:** Proceed with count-only polling; batch analysis at gate.

| 2026-11-28 23:47 Asia/Taipei | **Owner** (push cadence) | Commit locally during long runs; **push ≤1 / ~3h** + final REPORT before 12:00 Taipei — reduce PR email noise. |

## Anticipated critic targets (pre-buttress)

1. **Non-paired drafts in pilot v1** — Fixed in v2: `freeze_drafts.py` + `harness.py --drafts`.
2. **Visible grader too weak (EVR starved)** — Added currency-required visible rule, hq_city comma rule, digit-in-source check (no gold).
3. **Scale / big models** — Scope locked to Qwen2.5-0.5B CPU only; Colab notebook deferred / 0.5B only.