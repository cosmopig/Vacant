# PREREG — acceptance contracts (frozen before contract metrics / online arms)

**Frozen:** 2026-11-28T13:37:00Z (UTC) — no clause/tolerance edits after this file without new prereg row.

## Executor

- Package: `round2/contract/executor.py`
- Version id: `vacant.contract.executor/1`
- Verdicts per clause: `PASS` | `FAIL` | `ESCALATE` only
- Aggregate: any `FAIL` → `FAIL`; else any `ESCALATE` → `ESCALATE`; else `PASS`

## Opcodes (closed set)

| op | Deterministic rule |
|----|-------------------|
| `status_found_fields` | If status `not_found` → FAIL unless `allow_not_found`; else required keys present |
| `provenance_span_substr` | `span` substring of `page_text` |
| `value_in_span_numbers` | `value` within `tolerance_relative=0.001`, `tolerance_floor=0.5` of a number token in `span` |
| `scale_header_consistency` | If answer declares `scale`, incompatible with header phrase in `page_text` → FAIL |
| `unit_if_declared` | If answer declares `unit`, must equal contract `unit` |
| `multi_column_escalate` | If `distinct_numbers_escalate_above=2` exceeded in `span` → **ESCALATE** (never pick column) |

## Profiles

- **primary:** C1–C5 (no multi_column_escalate) — documents incompleteness for multi-column errors
- **independent:** R1–R6 — compiled from question text + form only; includes `multi_column_escalate`

## Judgment relocation (not eliminated)

- **Requester:** clause set, tolerances, `owner_escalate`, declared unit (primary: from benchmark task metadata shipped with question)
- **VACANT:** execute opcodes only
- **Named reviewer:** resolve `ESCALATE` items only

## Falsification targets (pre-committed)

- Independent vs primary same delivery decision: require ≥90% on qwen C1 replay
- False-release among `PASS`: report rate; do not tune tolerances to minimize
- Re-run agreement on frozen contract files: 100%