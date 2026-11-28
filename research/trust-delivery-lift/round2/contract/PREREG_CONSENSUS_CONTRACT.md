# PREREG — consensus contract (frozen before consensus metrics)

**Frozen:** 2026-11-28T13:46:00Z

## Blind authors (exactly three, scripted, no model)

| id | Compiler |
|----|----------|
| `A_primary` | `compile_contract_primary` |
| `B_independent` | `compile_contract_independent` |
| `C_question_only` | `compile_contract_question_only` |

## Consensus rule (structural only)

For each opcode type `op` appearing in any author’s clause list:

1. **Inclusion consensus:** `op` is in the consensus contract **iff** ≥2 authors include an clause with that `op`.
2. **Parameter consensus:** For numeric/string params in the opcode schema (`tolerance_relative`, `tolerance_floor`, `unit`, `distinct_numbers_escalate_above`, `required_fields`), consensus value = the value agreed by **≥2 authors**; if no agreement → **omit op** (treated as ESCALATE-at-runtime via `missing_consensus_clause`).

## Runtime on non-consensus tasks

Any required check with no consensus opcode → aggregate **ESCALATE** (not PASS).

## Metrics (on qwen3.5-9b C1 first — checker validity)

Compare **primary** vs **consensus**:

- Catch rate among quote-pass-value-wrong
- False reject among quote-pass-value-correct  
- False-release among aggregate PASS

**Falsifier (pre-committed):** consensus catch &lt; primary catch − **10 pp**, OR consensus false-release &gt; primary false-release + **2 pp** → report **lift absent under consensus**.

## Not allowed

- Tuning authors after seeing metrics
- Adding a fourth author to rescue agreement