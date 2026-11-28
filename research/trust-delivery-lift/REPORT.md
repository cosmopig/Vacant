# trust-delivery-lift 結果報告

**分支：** `research/trust-delivery-lift`  
**模型（依回合）：** Qwen2.5-0.5B-Instruct CPU（invoice holdout 進行中）  
**截止目標：** 2026-11-29 12:00 Asia/Taipei  

## English abstract

**Pilot 1 (n=12):** null. **Confirmatory (complete):** **n=128** answerable tasks (`hold_022`–`hold_149`), **512** rows, `stopping_reason=confirmatory_complete`. **Primary (frozen):** exact McNemar **VACANT vs MAJ3** on `oracle_whole_success` — **b=0, c=1, p=1.0** (null; one discordant pair). Oracle rates: VACANT **96/128 (75.0%)**, MAJ3 **95/128 (74.2%)**, BLIND **95/128**, LPB3 **96/128**. **Not** a delivery lift claim. **Exploratory:** VACANT **P(oracle fail | visible pass)=32/128=25%** (Goodhart on visible gate); gating utility in `summary.json` (LPB3 gate metrics **invalid** pre-quarantine rows). **Costs** unequal: VACANT ~**3.1 s / 281 tok / 1.0 calls** vs BLIND ~**7.0 s / 568 tok / 2** vs Maj/LPB ~**11.6 s / ~858 tok / 3** — see `COST_PARITY_AUDIT.md`. **1.5B filing** online subset **running** (exploratory). Filing 9b remains **leaky dev upper bound** only. **Filing (9b / partial 0.5B):** **leaky dev upper bound only** — not evidence. **Accountability = honest coverage:** uncontested auto-PASS **20%** coverage, **0%** false-release on that slice (9b); **53.9%** contested → ESCALATE; consensus refuse-gate **invalid** as a win without coverage floor. **Scripted “independent” contract authors are us — not external authorship.** **Verdict:** judgment relocated + reproducible execution; **delivery lift TBD** from holdout McNemar.

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

## 4. Filing online — small models (stopped; exploratory partial only)

**Supervisor order:** holdout confirmatory first; **0.5B filing run stopped** (~1100+/1320 rows exploratory, **not** labeled confirmatory). **1.5B** only if holdout completes with time left.

- **Pre-registered subset:** `subset_prereg_seed42.json` — **20 filings, 220 questions** (seed 42).  
- **0.5B (CPU, solo tmux):** `data/online_05b_seed42/` — **6 arms** × 220Q (append-only `rows.jsonl`). **Interim (~32% rows):** ~71 Q/arm; **0/6** filings with zero-wrong deliveries so far (0.5B capacity); see `online_05b_seed42_interim_summary.json` (updates as run continues).  
- **1.5B:** tmux `filing-15b` — started after holdout gate (**exploratory**; not confirmatory delivery evidence).  
- **Metric:** filing-level **zero-wrong** (`recompute_filing.py`); costs per arm in summary JSON.

## 5. Invoice Round 2 — confirmatory primary + exploratory

**Population (primary):** answerable confirmatory tasks only (`pilot_excluded` hold_000–021 **excluded**; holdout_unanswerable **not evaluated** — no false-release claim there). Spec: `PREREG_HOLDOUT_PRIMARY_SEAL_20261129.md` + `data/holdout_05b_confirmatory/PRIMARY_SPEC_SHA256.json`.

| Arm | n | oracle success | Wilson 95% CI | visible pass | mean CPU-s | mean tokens | mean calls |
|-----|---|----------------|---------------|--------------|------------|-------------|------------|
| VACANT | 128 | 96 (75.0%) | [66.8%, 81.7%] | 100% | 3.09 | 281 | 1.0 |
| MAJ3 | 128 | 95 (74.2%) | [66.0%, 81.0%] | 99.2% | 11.59 | 858 | 3.0 |
| BLIND | 128 | 95 (74.2%) | [66.0%, 81.0%] | 99.2% | 7.01 | 568 | 2.0 |
| LPB3 | 128 | 96 (75.0%) | [66.8%, 81.7%] | 100% | 11.74 | 859 | 3.0 |

**Primary McNemar (VACANT vs MAJ3):** discordant **1** (VACANT + only), **p=1.0** two-sided — **no evidence** of difference at this n.

**Exploratory gating** (`gating_exploratory` in `data/holdout_05b_confirmatory/summary.json`): VACANT coverage 100% with **silent failure 25%** when shipping on visible pass; BLIND/MAJ3 agreement gates lower coverage (~90%/80%) with similar silent-failure rates. **LPB3** row-level gated stats computed under **invalid τ** — quarantined; do not cite.

**Draft-call floor (1-call):** `draft_oracle_rate` matches final oracle for VACANT/BLIND/LPB3 at **75%** on this slice — field-lock repair moves **≤1** task over Maj3 here.

### What the primary null implies (pre-registered; not a lift claim)

On **Qwen2.5-0.5B**, **128 answerable invoice tasks**, the **field-locked VACANT repair loop does not improve whole-deliverable accuracy** vs **equal-budget Maj3** (McNemar **p=1.0**; one discordant pair). VACANT is **not cheaper in calls than a fair comparison story** would require — it is cheaper in **wall time/tokens** because it often stops after **one greedy JSON + micro passes** while Maj3 always runs **three full samples**.

**Demonstrated value at this scale is not “better answers.”** It is: (1) **release-safety semantics** — a frozen visible contract decides what may ship (exploratory false-release among visible-pass deliveries **32/128 = 25%** on this bank — see anatomy below); (2) **replayable row records** (`final`, costs, per-field visible detail) for accountability after the fact, not McNemar lift.

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

**Holdout confirmatory (0.5B invoice):** **未建立** VACANT vs MAJ3 delivery lift (McNemar null). Mechanism still shows **unequal cost** and **visible-pass ⊉ oracle** (25% silent failure under VACANT gate). **不能**宣稱「問責改善 whole-deliverable 交付」 on this bank at 0.5B; **能**宣稱 primary endpoint **pre-registered and honestly null** at n=128.

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