# Filing-Evidence offline typed audit (zero model cost)

**Dataset:** `pramana-research/filing-evidence` ([HF](https://huggingface.co/datasets/pramana-research/filing-evidence), Apache-2.0)  
**Answers:** bundled `qwen3.5-9b` setup `C1` (`answers.jsonl`, 1000 rows)  
**Questions:** `questions.jsonl` (gold: `shown_value`, `scale`, `unit`, `period`)

## Procedure

1. Quote pass: `failed_check is null` (same gate as the dataset’s quote check).
2. Oracle labels from release: `value_matches_gold` (not used at runtime).
3. **Typed check (runtime-visible only):** cited `span` on synthetic page text from gold evidence + header “(in millions)”; value must match a number in `span`; header scale must not contradict answer `scale`.

## Stop rule (preregistered)

Ineffective if typed check catches **&lt;30%** of quote-pass-but-wrong **or** wrongly rejects **&gt;5%** of quote-pass-and-correct.

## Result

| Quantity | Value |
|----------|------:|
| Quote pass (total) | 825 |
| Quote pass, value wrong | 101 |
| Quote pass, value correct | 724 |
| Typed catches (among wrong) | 75 (**74.3%**) |
| Typed false reject (among correct) | 35 (**4.8%**) |
| False-reject 95% CI (bootstrap / Wilson) | **[3.3%, 6.5%]** / **[3.5%, 6.6%]** — sits at the 5% limit |
| Missed pass-but-wrong | **26** — all categorized `wrong_column_or_value_in_span` (value appears in span but wrong column) |
| False-reject categories | 19 `span_missing_from_evidence_page` (evidence-only page stub), 16 `checker_scale_heuristic` |
| **Label** | **Checker validity** on released **qwen3.5-9b C1** answers — not small-model delivery |
| Stop rule | **Pass** — online CPU arms (0.5B/1.5B) may proceed under `PREREG_ROUND2.md` |

Detail: `data/offline_audit_detail.json` (reproduce `offline_audit_detail.py`).

Machine-readable: `data/offline_typed_audit_qwen_c1.json`  
Reproduce: `python offline_audit.py --questions data/questions.jsonl --answers data/qwen_c1_answers.jsonl --out data/offline_typed_audit_qwen_c1.json`