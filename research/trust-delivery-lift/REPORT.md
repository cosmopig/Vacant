# trust-delivery-lift 結果報告

**分支：** `research/trust-delivery-lift`  
**模型（依回合）：** Qwen2.5-0.5B-Instruct CPU（invoice holdout）；Qwen2.5-1.5B filing exploratory  
**截止目標：** 2026-11-29 12:00 Asia/Taipei  

## English abstract

**Headline:** Pre-registered **primary** (fenced **untouched tail** n=**54**, hold_096–hold_149): **McNemar VACANT vs MAJ3 p=1.0** — **no 0.5B invoice delivery lift** over majority vote; mechanism was **greedy-1 vs vote-of-3** (**repair trigger 0%**, all VACANT `n_calls=1`). **Value shown:** release-safety semantics + replayable rows, not accuracy.

**Contamination (disclosed):** Zombie harness kept writing `data/holdout_05b/` through **hold_095** during confirmatory; commit **`3240dc4a`** (**16:04Z**) predates primary seal (**~16:10Z**). **Sole primary** = tasks never in old-dir footprint: see `PREREG_HOLDOUT_FENCE_ADDENDUM_20261129.md`. **Secondary (contaminated):** hold_022–hold_149 sensitivity only.

**Pilot 1 (n=12):** null. **Filing 9b:** leaky dev upper bound. **1.5B filing subset:** complete exploratory (220×6 rows). **Judgment relocation** + contract replay 100%; independent contract authors **not** external.

---

## Where judgment lives

| Locus | Who decides | What | Residual risk (honest) |
|-------|-------------|------|-------------------------|
| **Acceptance contract** | Requester / benchmark operator (before any model run) | Field types, units, tolerances (`0.001`/`0.5`), opcode set, `owner_escalate` | Wrong or incomplete clauses → false release or false reject; **not** fixed by re-tuning after seeing errors |
| **VACANT runtime** | Nobody (executor only) | `PASS` / `FAIL` / `ESCALATE` per clause + spans + `executor_sha256` | Cannot resolve semantics; **must not** pick accounting definitions |
| **ESCALATE queue** | Named reviewer (`contract_owner@requester` in contract JSON) | Multi-column period disputes, items outside contract | Until resolved, delivery withheld (`TYPED_REFUSE` arm) |
| **Held-out oracle** | Experiment runner only (post hoc) | Whether value matches HF gold | Never visible to model or acceptance during run |
| **Page context stub** | Harness limitation | Evidence-line text, not full HTML | Provenance clause incomplete → **35–36 false rejects classified as contract incompleteness**, not tuned away |

**Owner objection addressed:** We do **not** claim “typed check = trusted taste.” We claim: **given a byte-stable contract file**, any party re-running `contract/executor.py` gets **identical** clause verdicts (`third_party_reproducibility` = **100%** on 2000 re-runs).

---

## 1. Pilot 1 — org-profile JSON (complete)

| 臂 | 完整交付 (confirmatory n=12) | Wilson 95% |
|----|------------------------------|------------|
| BLIND | 1/12 (8.3%) | [1.5%, 35.4%] |
| EVR | 1/12 (8.3%) | [1.5%, 35.4%] |

Δ = **0 pp**；預註冊 ≥5 pp 門檻 **未達成**。

## 2. P0 — extraction controls (complete)

`validate_controls.py`: **15/15** must-match/must-differ（scale/sign/currency/percent/sets）。  
Round-2 invoice oracle uses `typed_equal` for money/currency.

## 3. Filing-Evidence — checker validity (qwen3.5-9b C1)

**Label:** validates **contract executor** on released large-model answers — **not** 0.5B/1.5B delivery.

| Metric | Value |
|--------|------:|
| Quote pass, value wrong | 101 |
| Contract catch (primary profile) | 75/101 (**74.3%**) |
| Quote pass, value correct | 724 |
| False reject | 36 (**4.97%**; bootstrap 95% CI **[3.3%, 6.5%]**) |
| Missed wrong (in span, wrong column) | **26** (`wrong_column_or_value_in_span`) |
| False-reject tags (incompleteness) | 19 `span_not_in_page_text`, 16 `scale_mismatch` |

Stop rule (≥30% catch, ≤5% false reject): **borderline pass** (CI touches 5%).

### 52% disagreement — opcode decomposition (key owner finding)

Three blind compilers (`A_primary`, `B_independent`, `C_question_only`). **Agreement on delivery PASS/hold: 47.9%** (primary vs independent). **Primary vs consensus: 47.9%** delivery match.

| Opcode | Authors including (of 1000 tasks) | Consensus? |
|--------|-----------------------------------|------------|
| `provenance_span_substr` | **3/3** | yes |
| `value_in_span_numbers` | **3/3** | yes |
| `multi_column_escalate` | **2/3** | yes (drives **521×** `consensus_escalate_vs_primary_pass`) |
| `scale_header_consistency` | **2/3** | yes (125 tasks param split on `required_fields`) |
| `status_found_fields` | **2/3** | included but **param split on all 1000** (different required field lists) |
| `unit_if_declared` | **2/3** | param split on 125 |

**Consensus contract (pre-registered `PREREG_CONSENSUS_CONTRACT.md`):** on qwen9b replay, catch on quote-pass-wrong **100%** vs primary **74%**, but **524/724** correct rows fail consensus (ESCALATE/FAIL) vs **36** under primary — **refuse gate**; 100% catch is **trivial** at that block rate. Dominant pattern: `PASS|ESCALATE|ESCALATE` (**521** tasks).

### Honest coverage split (`PREREG_COVERAGE_SPLIT.md`, before small-model analysis)

| Metric | qwen9b C1 |
|--------|------------|
| Uncontested (3 authors same verdict) | **46.1%** |
| Auto-ship eligible (unanimous PASS) | **20.0%** (200/1000) |
| Contested → human ESCALATE | **53.9%** |
| False-release on uncontested auto-PASS | **0/200 (0%)** |
| Contested pattern top | `PASS\|ESCALATE\|ESCALATE` × 521 |

**Claim candidate:** On the **uncontested** region, auto-PASS is **trustworthy** (0% false-release here); **contested** volume is **explicitly not auto-shipped** — accountability as **coverage disclosure**, not maximal catch.

### Contract metrics (`contract_metrics_qwen_c1.json`)

| Metric | Value |
|--------|------:|
| Re-run agreement | **100%** |
| False-release among contract `PASS` | 26/721 (**3.6%**) |
| ESCALATE rate (primary) | **0%** (no `multi_column_escalate` opcode on primary — **known incompleteness**) |
| Independent vs primary same delivery decision | **47.9%** (**fails** pre-registered ≥90% survival) |

**Interpretation:** Judgment relocation works for **replay**; **contract authoring is not interchangeable** without changing ship/hold rates. Primary profile **silently** ships on multi-number spans; independent profile **ESCALATEs** → divergence.

## 4. Filing online — exploratory (0.5B partial vs 1.5B complete)

**Label:** exploratory only; **not** confirmatory. Subset: `subset_prereg_seed42.json` — **20 filings, 220 questions** (seed 42).

| Model | Rows | Status |
|-------|------|--------|
| 0.5B | 1188 / 1320 | stopped early (supervisor holdout priority) |
| 1.5B | **1320 / 1320** | complete |

**Per-arm delivered correct/wrong + filing-clustered bootstrap** (`filing/recompute_filing_compare.py` → `data/filing_05b_vs_15b_exploratory.json`):

| Arm | 1.5B released correct / wrong | false-release \|delivered | zero-wrong filing rate (95% CI) |
|-----|------------------------------|---------------------------|----------------------------------|
| PLAIN | 71 / 76 | 51.7% | 0% [0,0] |
| TYPED_REFUSE | 37 / 23 | **38.3%** | **33%** [11%, 56%] |
| RULE | 60 / 149 | 71.3% | 0% [0,0] |

**Gate false-release (RULE + TYPED_REFUSE combined, exploratory):** **0.5B 68.3%** (138/202 delivered wrong) vs **1.5B 63.9%** (172/269) — **modest drop**, not removal. **TYPED_REFUSE** alone improves at 1.5B: false-release **46.7% → 38.3%**; zero-wrong filing rate **50% → 33%** point with wide CIs (partial 0.5B n≈198/arm).

**Does the gate’s false-release fall at 1.5B?** **Somewhat on TYPED_REFUSE deliveries**, but **still high**; model capacity does not make incomplete span contracts safe.

## 5. Invoice Round 2 — fenced primary + contamination

### Disclosure (2026-11-29 01:00 Taipei)

- Stopped all writers to `data/holdout_05b/` (zombie ran **hold_022–hold_095** in old dir with **broken checker**; artifacts leaked in **`3240dc4a`** before fence addendum).
- **K=95**; **primary_confirmatory** = **hold_096–hold_149** (n=**54**) only — `FENCE_MANIFEST.json`.
- Confirmatory **CPU-s treated as tainted** where dual harness overlapped; primary is least-exposed contiguous tail in fixed bank order.

### Primary (sole inferential)

| Arm | n tasks | oracle success | McNemar vs MAJ3 |
|-----|---------|----------------|-----------------|
| VACANT | 54 | 40 (74.1%) | **b=0, c=1, p=1.0** |
| MAJ3 | 54 | 39 (72.2%) | — |

Source: `summary_fenced.json` · Spec: `PREREG_HOLDOUT_FENCE_ADDENDUM_20261129.md`.

### Mechanism honesty (VACANT)

| Metric | Primary tail (n=54) | Note |
|--------|---------------------|------|
| Repair trigger rate (`n_calls>1`) | **0%** | Greedy draft passes **visible** → no micro-repair |
| `n_calls` histogram | **100% at 1** | Compare **1-shot** vs Maj3 **×3 full JSON**, not repair loop |
| Draft oracle rate | 74.1% | Floor = final oracle rate here (no conditional repair gain) |

### Secondary (contaminated / sensitivity — not primary)

128 tasks hold_022–hold_149 McNemar VACANT vs MAJ3 / BLIND in `summary_fenced.json` — **peeked + CPU contention**; cite only as sensitivity.

**Population scope:** **answerable** invoices only; unanswerable holdout **not** evaluated for false-release claims.

**Exploratory gating** (`gating_exploratory` in `data/holdout_05b_confirmatory/summary.json`): VACANT coverage 100% with **silent failure 25%** when shipping on visible pass; BLIND/MAJ3 agreement gates lower coverage (~90%/80%) with similar silent-failure rates. **LPB3** row-level gated stats computed under **invalid τ** — quarantined; do not cite.

**Draft-call floor (1-call):** `draft_oracle_rate` matches final oracle for VACANT/BLIND/LPB3 at **75%** on this slice — field-lock repair moves **≤1** task over Maj3 here.

### What the primary null implies (pre-registered; not a lift claim)

On **Qwen2.5-0.5B**, **fenced primary n=54** (hold_096–hold_149), the test was **not a repair loop**: **repair never fired** (`n_calls=1` on every VACANT row). The comparison is **greedy single decode vs vote-of-3**, with **identical** McNemar vs Maj3 (**p=1.0**). The **binding constraint exposed here is contract incompleteness** (visible `vendor` = provenance-only), **not** failure of micro-repair.

**Demonstrated value at this scale is not “better answers.”** It is: (1) **release-safety semantics** — ship rules frozen before the run; (2) **replayable receipts**; (3) honest reporting when the visible contract **cannot** encode truth (exploratory **25%** false-release if shipping on visible pass on the wider secondary slice — all **vendor** oracle errors).

### Exploratory — VACANT failure anatomy (confirmatory)

Source: `data/holdout_05b_confirmatory/FAILURE_ANATOMY_VACANT_EXPLORATORY.json` (`audit_vacant_failure_anatomy.py`).

| Bucket | n (of 32 oracle fails) | Meaning |
|--------|------------------------|---------|
| **A — visible pass, oracle fail (Goodhart / incomplete contract)** | **32 (100%)** | Visible gate would ship; oracle wrong. **All 32** mismatches on **`vendor`** only: visible clause checks **provenance in source text + length**, **not** identity to gold vendor string. |
| **B — visible fail, still oracle fail (unrepaired)** | **0** | No delivery left with failing visible checks — not a “stuck repair” story on this confirmatory slice. |

**Clause map (invoice visible contract):** failures are **not** spread across `currency` / `arith_mismatch` / dates on this slice; they concentrate on **`vendor`** because that is the only oracle error the visible contract does not catch. **Contract incompleteness:** visible spec does not encode “correct vendor entity,” only “vendor string appears in document.”

**Release-safety (exploratory):** if policy = ship iff `visible_all_pass`, **false-release rate = 25%** here — the mechanism **monitors form, not truth** at 0.5B on this task bank.

## 6. Verdict paragraph（可否說「問責改善交付」？）

**Pilot 1 + 目前證據：不能**在 0.5B／短文 JSON 上宣稱可測的 whole-deliverable lift。  

**可以說的（有邊界）：**

1. **Vacant 路徑** = 先把驗收寫進 **可雜湊的 requester contract**，執行層 **零裁量**（僅 PASS/FAIL/ESCALATE），第三方重跑 **100% 一致**。  
2. **Filing 線**上，同一份契約對 9b 輸出有 **~74%** 錯誤攔截力，但 **~5%** 誤拒 + **條款不完整**（欄位/期間）與 **stub 頁面** 仍在。  
3. **獨立契約作者測試失敗**（48% 一致）→ 任何「lift」都 **綁在特定凍結條款**，不能泛化成「契約」概念。  
4. **ESCALATE** 須由具名負責人處理語意爭議；primary 合約目前 **ESCALATE 率 0%** = 語意風險仍可能被當 PASS 出貨（false release 3.6%）。

**Holdout (0.5B invoice, fenced n=54):** **未建立** delivery lift; measured **greedy vs vote-3** with **incomplete vendor clause**, not repair. **能**宣稱 pre-registered primary **honestly null** after contamination fence.

---

## Synthesis and next experiment

**Synthesis.** One story ties the lines: **frozen acceptance contracts** buy **replayable release decisions**, not **accuracy** at 0.5B on these banks. Invoices: visible spec is **incomplete** → **pass-but-wrong** dominates; repair path **never ran**. Filing: typed gate **withholds** some deliveries but **false-release among what ships** stays high unless the model is stronger—and even **1.5B** only **shifts** error rates.

**Parallel intervention probe (box-side, exploratory; not re-run in this repo):** on a **44-item** slice at 0.5B, **contract-compiled decoding** moved **correct 5→17** but **pass-but-wrong 4→27** (incompleteness / wrong constraint surface). **Token mean-logprob** for pass-but-wrong: **AUROC ~0.56–0.60** (weak ranker). **Dual-decode agreement gate:** precision **~69%** vs **~56%** baseline — **matches self-consistency**, not independent evidence.

**Next experiment (pre-registered shape, not launched here):**

1. **Tighten clauses** that caused pass-but-wrong (invoice: vendor **identity** not just provenance; filing: column/period opcodes already in contract executor).  
2. **Measure repair only when visible fails** — force a spec where greedy draft does **not** all-pass, or score **conditional repair gain** on that subset.  
3. **Do not** treat logprob or dual-decode agreement as oracle; use only as **exploratory** withhold signals with reported AUROC / precision.  
4. **Holdout discipline:** single writer, fenced IDs, no dual harness.

---

## 7. 重現

```bash
cd research/trust-delivery-lift
# Pilot 1
../../.venv/bin/python harness.py --split confirm_ids --arms BLIND,EVR --drafts data/confirm/drafts.jsonl --out data/confirm

# P0 + contract
cd round2
../../.venv/bin/python validate_controls.py
../../.venv/bin/python -m contract.freeze_contracts --questions filing/data/questions.jsonl --subset filing/data/subset_20filings.json --out filing/data/contracts_frozen
PYTHONPATH=. ../../.venv/bin/python contract/metrics.py

# Filing offline audit
cd filing
../../.venv/bin/python offline_audit.py --questions data/questions.jsonl --answers data/qwen_c1_answers.jsonl --out data/offline_typed_audit_qwen_c1.json
../../.venv/bin/python offline_audit_detail.py

# Round 2 holdout (running)
cd ..
../../.venv/bin/python harness_r2.py --split holdout_answerable_ids --arms BLIND,VACANT --out data/holdout_05b
../../.venv/bin/python recompute_r2.py --rows data/holdout_05b/rows.jsonl --mcnemar BLIND VACANT --out data/holdout_05b/summary.json
```

設計與反駁紀錄：`CRITIQUE_LOG.md` · 合約凍結：`round2/contract/PREREG_CONTRACT.md`