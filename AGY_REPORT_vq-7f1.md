# AGY Report — vq-7f1 (2026-11-28)

Branch: `agy/vq-7f1-fix`

## 1. Summary of Changes

### Defect 1: Selectable `b24` matching (`literal` default preserved)
Implemented the closed 3-item `b24` normalisation (remove `*`, remove backtick `` ` ``, remove `str.isspace()` runs adjacent to `(` or `)`) applied identically to page text and value on top of existing literal / numeric-boundary matching, threaded `matching: str = "literal" | "b24"` through public entry points, and added `VACANT_FLAG_MATCHING` resolution at outermost entry points only.

- `vacant_network/trace/locate.py:31-109` — added `MATCHING_MODES`, `DEFAULT_MATCHING` (`"literal"`), `validate_matching`, `resolve_matching` (reads `VACANT_FLAG_MATCHING` when explicit `matching is None`), `normalize_b24`, and `_normalize_b24_with_offsets`.
- `vacant_network/trace/locate.py:162-227` — extracted `_occurrence_spans_literal` preserving existing numeric boundary and literal logic verbatim; updated `occurrences(..., matching="literal")` and `contains(..., matching="literal")` to try literal first and fall back to `b24` normalised matching when `matching="b24"`, mapping matched spans back to original line/column offsets; corrected docstring.
- `vacant_network/trace/sources.py:96-106`, `302-420`, `479-612`, `785-832`, `933-995` — threaded `matching` through `plain_contains`, `_carriers`, `_still_there`, `value_status` (`_json_status`, `_line_status`, `_table_hits`, `_table_cell_status`, `_field_status`), and outermost entry points `provenance`, `check`, `candidates`, `snapshot`, `check_candidates` (which resolve `VACANT_FLAG_MATCHING` once via `L.resolve_matching(matching)` and pass explicit `matching=mode` downward).
- `vacant_network/trace/blame.py:473-478`, `518-577`, `819-821`, `900-917`, `961-988`, `1037-1095`, `1145-1187`, `1281-1353`, `1430-1433`, `1537-1565` — threaded `matching: str = "literal"` through `Blamer`, `rerun_flip`, `_blame_location`, `blame_location`, and `blame_results` (no env var read inside).
- `vacant_network/trace/stopcheck.py:42-63`, `86-110` — threaded `matching` through `_flag_blames` and resolved `matching` at `localize`.
- `vacant_network/trace/cli.py:46`, `407-430`, `572-605`, `690-720` — added `--matching {literal,b24}` to `vacant trace blame` and `vacant trace sources`, resolving via `L.resolve_matching(...)` at CLI entry.
- `tests/test_trace_locate_b24.py:1-338` — new regression and spec test suite (11 tests covering all requested categories, `known_deviation_b41`, 60-iteration property check, offset/line-col parity, 20/20 agreement with `ops/d2/expT_b36_spec_test.py` and `ops/d2/expT_feedback.py`, and outermost-only `VACANT_FLAG_MATCHING` behaviour).

### Defect 2: `egress.jsonl` body protection during session-end auto-GC
- **Status on HEAD**: **Already fixed on HEAD** (commits `c9b97e185` / `1bf3e0599`). No change to `vacant_network/retention.py` was required.
  - `vacant_network/retention.py:1000-1010` (`collect_project_blob_refs`) reads `<project>/egress.jsonl` for every project directory (both with and without `chain.ndjson`) and includes all valid 64-hex `sha256` entries in `expected_store_refs` / `all_shas`.
  - `vacant_network/retention.py:1324-1334` (`compact_trace`, default/auto GC path) adds all of `proj_refs["all_shas"]` to `keep_shas` and `structural_shas`, protecting them past the 60s `AUTO_GC_ORPHAN_GRACE_S` window and even under tight `VACANT_TRACE_BUDGET_BYTES`.
  - `vacant_network/adapters/hook.py:219-248`, `514-516` skips auto-GC entirely when `VACANT_HOOK_NO_GC` is truthy and otherwise spawns `python -m vacant_network gc --auto --json`.
- `tests/test_retention_egress_gc.py:1-207` — new regression suite (3 tests) executing the real `hook.handle("claude", "SessionEnd", ...)` -> `python3 -m vacant_network gc --auto --json` subprocess path against old (`>60s`) un-ingested `egress.jsonl` body objects (both chained and no-chain projects, under tight `VACANT_TRACE_BUDGET_BYTES=1024`), verifying old unreferenced orphans are still deleted, and verifying `VACANT_HOOK_NO_GC=1` skips GC entirely.

## 2. Test Commands and Exact Results

### 2a. `python3 -m pytest` (FAILED — environment lacks `pytest`)
Command run:
```bash
systemd-run --user --scope -q -p MemoryMax=2G python3 -m pytest tests/test_trace_locate_b24.py -x -q
```
Result: **exit 1** — `/usr/bin/python3: No module named pytest`.
This worktree has no `.venv`, system `/usr/bin/python3` does not have `pytest` installed (it does have `cryptography` and `jsonschema`), and accessing any other worktree/checkout `.venv` or the network is forbidden by the hard limits. Therefore real `pytest` was **not** run; please re-run `python -m pytest` inside the repo `.venv`.

### 2b. Experiment reference spec test (pure stdlib + `vacant_network`)
Command run:
```bash
systemd-run --user --scope -q -p MemoryMax=2G python3 ops/d2/expT_b36_spec_test.py --out /tmp/b36_check.json
```
Result: **exit 0** — **20/20 PASS** (`ALL PASS`).

### 2c. Direct execution via stdlib scratch runner under `/usr/bin/python3`
To verify the code and test logic offline without violating hard limits, each test file was executed one at a time via a stdlib-only pytest-shim script (`$RUNNER`, stored outside the worktree in the conversation scratch directory, loading `tests/conftest.py` isolation) wrapped in `systemd-run --user --scope -q -p MemoryMax=2G python3 "$RUNNER" -x <file>`:

| Test file | Result (stdlib runner, NOT real `pytest`) |
|---|---|
| `tests/test_trace_locate_b24.py` | 11 passed, 0 failed, 0 skipped (RC=0) |
| `tests/test_retention_egress_gc.py` | 3 passed, 0 failed, 0 skipped (RC=0) |
| `tests/test_retention.py` | 85 passed, 0 failed, 0 skipped (RC=0) |
| `tests/test_retention_cli_blame_verify.py` | 7 passed, 0 failed, 0 skipped (RC=0) |
| `tests/test_trace.py` | 3 passed, 0 failed, 0 skipped (RC=0) |
| `tests/test_trace_blame.py` | 34 passed, 0 failed, 0 skipped (RC=0) |
| `tests/test_trace_blame_coverage.py` | 9 passed, 0 failed, 0 skipped (RC=0) |
| `tests/test_trace_hardening.py` | 43 passed, 0 failed, 0 skipped (RC=0) |
| `tests/test_trace_capture.py` | 21 passed, 0 failed, 0 skipped (RC=0) |
| `tests/test_trace_sources.py` | 5 passed, 0 failed, 0 skipped (RC=0) |
| `tests/test_trace_sources_v4.py` | 12 passed, 0 failed, 0 skipped (RC=0) |
| `tests/test_record_hardening_gc.py` | 6 passed, 0 failed, 0 skipped (RC=0) |

## 3. Notes / Subtle Behaviours to Review

1. **Literal-first fallback in `b24`**: `locate.occurrences` and `locate.contains` try exact literal matching first and apply `normalize_b24` only when literal fails. This matches `ops/d2/expT_feedback.py` and guarantees `b24` never drops a pre-existing literal match (e.g. `"12"` in `"a*12"`, or `"*a*"` in `"*a*"`).
2. **Raw HTML branch in `sources.plain_contains`**: `plain_contains(raw, key, matching=mode)` checks `L.contains(raw, key, matching=mode) or L.contains(_plain(raw), key, matching=mode)`. This stays symmetric with existing literal `plain_contains` and agrees 20/20 with `ops/d2/expT_b36_spec_test.py`. By contrast, `ops/d2/expT_feedback.py` only applies `b24_norm` to `_plain(raw)`; thus an HTML page with a matching token only inside `<script>`/`<style>` that differs by `*`/`` ` ``/paren-whitespace would match under product `plain_contains(..., matching="b24")` just as it already does when matching literally in raw HTML.
3. **Outermost entry points for `VACANT_FLAG_MATCHING`**: `resolve_matching()` is called in `sources.{provenance,check,candidates,snapshot,check_candidates}`, `stopcheck.localize`, and `trace.cli.{cmd_sources,cmd_blame}`. Lower-level functions (`locate.{occurrences,contains}`, `sources.{plain_contains,value_status}`, `blame.{Blamer,blame_location,blame_results}`) never read the environment variable and default strictly to `"literal"`.
4. **No-chain `egress.jsonl` in `verify_trace_objects`**: While `compact_trace` protects `egress.jsonl` blobs even when a project directory has no `chain.ndjson` or `state.json` yet, `verify_trace_objects` (`retention.py:1091`) skips directories lacking both chain files and `state.json`. Left unchanged as out of scope for GC retention.

## 4. What Was NOT Done

- Did **not** execute real `pytest` (unavailable in `/usr/bin/python3`; other worktrees/checkouts and network were off-limits).
- Did **not** change the default `matching` mode (kept as `"literal"`).
- Did **not** modify `vacant_network/retention.py` (HEAD already passed the Defect 2 regression tests).
- Did **not** modify any prompt templates (KS-1) or frozen experiment files under `ops/d2/`.
- Did **not** push or rewrite git history.
