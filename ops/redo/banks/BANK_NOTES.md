# BANK_NOTES — `exercism_py_unused`

## Summary

Built a new, previously unused 40-task Python bank for `ops/redo/redo.py` from `exercism/python` using a pre-fixed, deterministic selection rule with zero model runs.

- **Bank directory:** `~/dev/ops/ref/bm_tasks/exercism_py_unused` (40 tasks, 161 files total)
- **Source clone:** `~/dev/ops/ref/src/exercism-python` (`https://github.com/exercism/python`)
- **Pinned source commit SHA:** `479f11b44b02337b0413e805b948491c2179615a`
- **Manifest:** `ops/redo/banks/exercism_py_unused.json`
- **Builder / verifier script:** `ops/redo/banks/build_exercism_py_unused.py`

## Selection Pipeline Counts

Executed with Python 3.12.3 (stdlib only, 120s per-exercise validation timeout):

| Stage | Count | Notes |
|---|---:|---|
| Practice exercises under `exercises/practice/*` | 142 | Total directories |
| Excluded — overlap with `polyglot_py` (Rule 1) | 34 | All 34 `pg_*` tasks matched 1-to-1 after stripping `pg_` and mapping `_` to `-` |
| Non-polyglot candidates | 108 | All 108 had `.meta/example.py`, `*_test.py`, stub `.py`, and `.docs/instructions.md` |
| Excluded — missing required files (Rule 1) | 0 | — |
| Excluded — non-stdlib imports or external network/file I/O (Rule 2) | 0 | All imports across tests, helpers, and examples are pure Python stdlib or local exercise modules |
| Excluded — validation (a) `example.py` failed `unittest` (Rule 3a) | 0 | Note: `parallel-letter-frequency` takes ~31.0s due to `sleep()` calls in `.meta/example.py`, so it passes within the 120s timeout (matching `redo.py`'s default `acceptance.timeout_s`) |
| Excluded — validation (b) original stub passed all tests (Rule 3b) | 2 | `ledger` (11 tests OK) and `markdown` (17 tests OK) — both are refactoring exercises whose starter stubs already implement the spec |
| Eligible after validation | 106 | Full ordered list recorded in `ordered_eligible` in the manifest |
| Selected (first 40 by `sha256(slug + ":redo-unused-2026-11-20")`) | 40 | `ex_all_your_base` (rank 1) through `ex_clock` (rank 40) |

### Task Format & Edge Cases

- Every task directory `ex_<slug_with_underscores>/` mirrors `~/dev/ops/ref/bm_tasks/polyglot_py/pg_wordy/`:
  - `instruction.txt`: single line (`Read goal.md and contract.md in this directory and do what they say. Use your tools to write the file.`)
  - `workspace/goal.md`: `.docs/instructions.md`, plus `.docs/instructions.append.md` appended directly if present
  - `workspace/contract.md`: identical template wording to `polyglot_py` (target solution filename, skeleton extracted from stub, stdlib-only rule, preserve names, test filename(s) and `pytest`/`unittest` commands)
  - `workspace/<x>_test.py`: exact byte copy of the exercise test file
- **Helper test file (`ex_error_handling`, rank 7):** Like `pg_paasio` in `polyglot_py`, `error-handling` includes `test_utils.py` (an in-memory `FileLike` mock imported by `error_handling_test.py`). `workspace/test_utils.py` is copied unchanged and referenced in `contract.md` (`The tests for this task are in \`error_handling_test.py\` and \`test_utils.py\`.`), matching `pg_paasio`.
- **No reference solutions leaked:** Verified `example.py` does not appear anywhere in `~/dev/ops/ref/bm_tasks/exercism_py_unused`.
- **Skipped tests check:** Among the 106 eligible exercises, only `alphametics` (hash `b8622192...`, outside the top 40) has a `@unittest.skip("extra-credit")` test. None of the 40 chosen tasks have skipped tests.

## Verification Results

1. **Manifest hash verification:**
   ```bash
   python3 ops/redo/banks/build_exercism_py_unused.py --check
   ```
   Result: `CHECK_OK: 161/161 files match manifest hashes in /home/user1/dev/ops/ref/bm_tasks/exercism_py_unused (tasks=40, commit=479f11b44b02)`

2. **`ops/redo/redo.py` `acceptance()` verification across all 40 chosen tasks:**
   - Pristine `workspace/` (no solution file): `40/40` rejected (`accept=False`)
   - Temp copy with `.meta/example.py` as `<module>.py`: `40/40` accepted (`accept=True`, `status=ok`, `run > 0`, `passed == run`, `tests_tampered == []`)
   - Temp copy with original stub as `<module>.py`: `40/40` rejected (`accept=False`)

3. **`ops/redo/redo.py preflight` verification:**
   - Inspected `ops/redo/redo.py`:
     - `preflight` **accepts** `--bank <path>` (`ops/redo/redo.py:1249-1252`).
     - `preflight` does **not** accept `--allow-uncommitted-plan` (that flag is only registered for the `run` subcommand at `ops/redo/redo.py:1253-1258`).
   - Ran `preflight` against a temporary copy of `ops/redo/plans/smoke2_pi_gemma12b.json` with `"tasks": ["ex_all_your_base", "ex_robot_simulator"]`:
     ```bash
     python3 ops/redo/redo.py preflight \
       --bank ~/dev/ops/ref/bm_tasks/exercism_py_unused \
       --plan <tmp_copy_of_smoke2_pi_gemma12b.json>
     ```
   - Observed output (exit code `1`):
     ```text
     OK    題庫 /home/user1/dev/ops/ref/bm_tasks/exercism_py_unused（2 題都有 workspace/）
     OK    每一題的工作區都有測試檔（驗收訊號的來源）
     OK    2 題沒有 scorer.py／hidden：用「原件測試」當評分（visible_equals_grader）
     OK    負控制：ex_all_your_base 原封不動的工作區被驗收擋下（status=ok）
     OK    agent 指令 pi → /home/user1/.local/bin/pi
     OK    agent 設定來源 /home/user1/.pi/agent（複製 ['models.json']）
     OK    provider lms1004nothink 在 /home/user1/.pi/agent/models.json 裡
     FAIL  計畫檔還沒 commit

     計畫 smoke2_pi_gemma12b sha256 8d3638596ce971517b227e77940e9c0affb8f9a3c04ced027bf8c7b9dd26b2aa
     VERDICT: PREFLIGHT_FAIL
     ```
   - All 7 bank/test/grader/negative-control/agent/provider checks passed. The single `FAIL` (`計畫檔還沒 commit`) is expected for an uncommitted temporary plan because `preflight` enforces the git clean check (`cmd_preflight`, `ops/redo/redo.py:1040-1041`) without an override flag.

## How to Point a Redo Plan at `exercism_py_unused`

In `ops/redo/redo.py`, `resolve_bank(plan, override)` (`ops/redo/redo.py:172-185`) checks bank candidates in priority order and returns the first existing directory where every task in `plan["tasks"]` has a `<bank>/<task>/workspace/` subdirectory:

1. `--bank <path>` CLI argument (supported by both `preflight` and `run`)
2. `REDO_BANK` environment variable
3. `plan["bank"]`
4. `plan["bank_candidates"]` (in list order)

To create a committed plan targeting this bank:

1. Set `"bank": "~/dev/ops/ref/bm_tasks/exercism_py_unused"` (and update `"bank_candidates"` if desired).
2. Set `"tasks"` to task IDs from `chosen_tasks` in `ops/redo/banks/exercism_py_unused.json` (e.g., `["ex_all_your_base", "ex_robot_simulator", ...]`).
3. Keep `"grader": {"visible_equals_grader": true, ...}` (this bank has visible workspace tests and no separate `scorer.py`/`hidden/`, same as `polyglot_py`).
4. Commit the plan file before running `python3 ops/redo/redo.py preflight --plan <plan.json>` and `python3 ops/redo/redo.py run --plan <plan.json> --root <out_dir>`.

---

## `exercism_py_hard` (`difficulty >= 4`, all eligible)

Added alongside `exercism_py_unused` (without modifying `exercism_py_unused` or its manifest) to avoid baseline ceiling effects on easy exercises while relying strictly on pre-existing external metadata (`config.json` `exercises.practice[].difficulty`, zero model results used).

- **Bank directory:** `~/dev/ops/ref/bm_tasks/exercism_py_hard` (26 tasks, 104 files total, prefix `ex_<slug_with_underscores>`)
- **Manifest:** `ops/redo/banks/exercism_py_hard.json`
- **Source clone & commit:** `~/dev/ops/ref/src/exercism-python` @ `479f11b44b02337b0413e805b948491c2179615a`

### Selection Rule

Same eligibility and isolated `unittest` validation rules as `exercism_py_unused` (not in `polyglot_py`, required files, stdlib/local-only imports and no external network/file I/O, `(a)` `.meta/example.py` passes `unittest` with >0 tests and `(b)` starter stub fails), **plus** `difficulty >= 4` from `exercism-python/config.json` (`exercises.practice[].difficulty`). Order all surviving slugs ascending by `sha256(slug + ':redo-pyhard-2026-11-21')` and take **all** eligible exercises (`--take-all`).

### Counts & Exclusions

| Stage | Count | Notes |
|---|---:|---|
| Practice exercises under `exercises/practice/*` | 142 | Total directories |
| Excluded — overlap with `polyglot_py` (Rule 1) | 34 | Same 34 `pg_*` tasks |
| Non-polyglot candidates | 108 | — |
| Excluded — `difficulty < 4` (Rule 1, `min_difficulty=4`) | 80 | Pre-existing `config.json` difficulty 1–3 |
| Candidates with `difficulty >= 4` | 28 | — |
| Excluded — required files / stdlib & I/O / validation (a) | 0 | — |
| Excluded — validation (b) original stub passed all tests | 2 | `ledger` (difficulty 4, 11 tests OK) and `markdown` (difficulty 4, 17 tests OK) — upstream refactoring exercises |
| Eligible & selected (`--take-all`) | 26 | 104 bank files total; `ex_satellite` (rank 1) through `ex_complex_numbers` (rank 26) |

- Note: `ex_alphametics` (rank 2, difficulty 6) contains one upstream `@unittest.skip("extra-credit")` test.

### Difficulty Histogram (26 selected)

| Difficulty | Count |
|---|---:|
| 4 | 16 |
| 5 | 6 |
| 6 | 3 |
| 7 | 1 |

### Overlap with `exercism_py_unused` (10 slugs)

`all-your-base`, `binary-search-tree`, `change`, `flower-field`, `rational-numbers`, `satellite`, `swift-scheduling`, `tournament`, `trinary`, `word-search`

### Build & Verify Commands

```bash
python3 ops/redo/banks/build_exercism_py_unused.py \
  --bank-id exercism_py_hard --min-difficulty 4 \
  --salt ':redo-pyhard-2026-11-21' --take-all \
  --out ~/dev/ops/ref/bm_tasks/exercism_py_hard \
  --manifest ops/redo/banks/exercism_py_hard.json \
  --overlap-manifest ops/redo/banks/exercism_py_unused.json \
  --workers 3

python3 ops/redo/banks/build_exercism_py_unused.py --check \
  --out ~/dev/ops/ref/bm_tasks/exercism_py_hard \
  --manifest ops/redo/banks/exercism_py_hard.json
```
