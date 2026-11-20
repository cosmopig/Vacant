# NONPY_NOTES — Non-Python Support & Exercism JavaScript Bank for `ops/redo/redo.py`

Built in worktree `~/dev/wt/nonpy` (stdlib-only Python 3.11+; zero model calls run).

## 1. What Was Built

### A. Harness: `acceptance.kind = "command"` (`ops/redo/redo.py`)

- Added `kind: "command"` acceptance support alongside the existing `workspace_tests` path (which is kept byte-for-byte identical in behaviour):
  ```json
  "acceptance": {
    "kind": "command",
    "cmd": ["npm", "test", "--silent"],
    "timeout_s": 120,
    "protect": ["*.spec.js"]
  }
  ```
- **Semantics (mirroring `workspace_tests`)**:
  - Copies `final_ws` into an isolated temp directory while ignoring `SKIP_DIRS` (`.git`, `node_modules`, `__pycache__`, `.venv`, `.pytest_cache`, `.mypy_cache`).
  - Restores any top-level `SKIP_DIRS` symlinks present in `origin` (specifically `node_modules`) into the acceptance copy so offline test runners still resolve shared dependencies even if an agent deleted or replaced `node_modules`.
  - Restores every file in `origin` matching `protect` to its exact original bytes before running `cmd`; records any modified, deleted, or type-changed protected files in `tests_tampered`.
  - If `protect` is non-empty and matches zero files in `origin`, fails closed (`accept=False`, `status="no_tests_in_origin"`).
  - Runs `cmd` (list argv, no shell) in the acceptance copy with a clean environment (`_clean_env(tmp)`) and process-group timeout (`timeout_s`).
  - Exit code `0` => `accept=True`, `status="ok"`. Non-zero exit => `accept=False`, `status="ok"`. Timeout / spawn error => `accept=False`, `status="timeout"` / `"spawn_error"`.
  - `passed` / `run` are `None` by default, or parsed from Jest's final `Tests: ... N total` summary line when trivially present.
- **Grader**: With `"grader": {"visible_equals_grader": true}`, `grade()` reuses the pristine-spec acceptance outcome (`grader_kind = "visible_tests_pristine"`).
- **Preflight**:
  - For `kind == "command"`, `preflight` checks `shutil.which(cmd[0])`, checks that every task workspace contains files matching `protect`, and verifies the negative control fails cleanly (`accept=False`, `status="ok"`).
  - Added `--allow-uncommitted-plan` to `preflight` (matching `run`; default remains strict/committed-only).
- **Selftest**: Added 6 new `command`-kind checks to `python3 ops/redo/redo.py selftest` (32/32 total): stub failure + Jest count parsing, passing solution + `node_modules` symlink restoration after agent deletion, `*.spec.js` tamper restoration + `tests_tampered`, command timeout, non-Jest command `passed=None`/`run=None`, and full `cmd_run` A-vs-R3 flow with `visible_equals_grader=True`.

### B. Exercism JavaScript Task Bank (`~/dev/ops/ref/bm_tasks/exercism_js/`)

- **Source clone**: `~/dev/ops/ref/src/exercism-javascript` (`https://github.com/exercism/javascript`), commit `70364d04ee58ae548fb2a14603d1dc1d46ddc8c1`.
- **Builder & verifier**: `ops/redo/banks/build_exercism_js.py` (stdlib-only Python 3.11+, supports `--check`).
- **Manifest**: `ops/redo/banks/exercism_js.json` (source SHA, fixed rule, exclusions + reasons, ordered 34 slugs, per-task validation counts, and SHA-256 / symlink targets of all 306 bank entries).
- **Pre-registered selection rule** (fixed before any model run):
  1. Scan `exercises/practice/*` (139 exercises). Require `.meta/config.json`, `.meta/proof.ci.js`, single `*.spec.js`, single starter stub `.js`, and `.docs/instructions.md`.
  2. Exclude exercises requiring npm dependencies beyond root `package.json` `devDependencies` (jest/babel toolchain) or network APIs.
  3. Enable Exercism CI test markers in `*.spec.js` (`\bx(test|it)\(` -> `test(`, `\bxdescribe\(` -> `describe(`), matching upstream `scripts/helpers.mjs` without altering `test.skip`/`describe.skip`.
  4. Validate offline via `npm test --silent` using repo `babel.config.js`, `jest.config.js`, and the shared `node_modules` cache:
     - (a) `.meta/proof.ci.js` passes (`rc == 0`, `passed > 0`, `failed == 0`);
     - (b) starter stub `.js` fails at least one test (`rc != 0`).
  5. Order the 137 survivors ascending by `sha256(slug + ":redo-js-2026-11-20")` and take the first 34.
- **Exclusions (2/139)**:
  - `ledger`: stub unexpectedly passed spec (`rc=0`) — upstream refactoring exercise whose starter file is already a working implementation.
  - `markdown`: stub unexpectedly passed spec (`rc=0`) — upstream refactoring exercise.
- **Workspace layout** (`~/dev/ops/ref/bm_tasks/exercism_js/js_<slug>/`, mirroring `polyglot_py/pg_wordy`):
  - `instruction.txt`: identical single line (`Read goal.md and contract.md in this directory and do what they say. Use your tools to write the file.`).
  - `workspace/goal.md`: `.docs/instructions.md` (+ `.docs/instructions.append.md` when present).
  - `workspace/contract.md`: JS-adapted contract with solution filename, full starter stub as skeleton, no new npm packages rule, tests-are-correct rule, and `npm test` / `npm test --silent` instructions.
  - `workspace/<slug>.js`: starter stub (never `.meta/proof.ci.js`). Having the starter stub in place lets `preflight` and agents run Jest/Babel end-to-end against real failing tests rather than failing at `MODULE_NOT_FOUND`.
  - `workspace/<slug>.spec.js`: CI-enabled Jest spec.
  - `workspace/package.json`: minimal offline manifest with `"scripts": {"test": "jest"}` (replaces upstream `"corepack pnpm jest"` so no corepack/pnpm/network calls occur).
  - `workspace/babel.config.js` and `workspace/jest.config.js`: exact copies from repo root.
  - `workspace/node_modules`: symlink to `~/dev/ops/ref/cache/exercism_js/node_modules`.
- **Why `node_modules` symlink instead of `NODE_PATH`**:
  - `npm test` automatically prepends `./node_modules/.bin` to `PATH`, so `"test": "jest"` works offline with zero wrapper scripts or extra environment variables.
  - Jest (`babel-jest`, `@jest/globals`) and Babel (`@exercism/babel-preset-javascript`, `core-js`) resolve presets/transformers reliably from `cwd/node_modules`, whereas `NODE_PATH` does not reliably cover Jest/Babel preset resolution or `.bin` discovery.
  - `redo.py` already excludes `node_modules` from `snapshot()` and `_archive()`, keeping logs/archives tiny, while `_acceptance_command()` restores `origin/node_modules` symlink into the acceptance copy.
  - Disk cost is O(1): one shared install for all 34 tasks.

### C. Smoke Plan (`ops/redo/plans/smoke2_pi_gemma12b_js.json`)

- Copied from `ops/redo/plans/smoke2_pi_gemma12b.json`, targeting `~/dev/ops/ref/bm_tasks/exercism_js`, the first two ordered tasks (`js_food-chain`, `js_high-scores`), `acceptance.kind = "command"` with `["npm", "test", "--silent"]` and `protect = ["*.spec.js"]`, and `visible_equals_grader = true`. Not executed against any model.

## 2. Exact Versions

- **Python**: `Python 3.12.3` (stdlib only, 3.11+ compatible)
- **Node.js**: `v22.23.2` (`/home/user1/.local/bin/node`)
- **npm**: `10.9.8` (`/home/user1/.local/bin/npm`)
- **Source repo**: `exercism/javascript` @ `70364d04ee58ae548fb2a14603d1dc1d46ddc8c1`
- **Shared `node_modules` cache** (`~/dev/ops/ref/cache/exercism_js/node_modules`), installed once via `npm install --no-audit --no-fund` from repo root `devDependencies`:
  - `@exercism/babel-preset-javascript`: `0.5.1`
  - `@exercism/eslint-config-javascript`: `0.8.1`
  - `@jest/globals`: `30.5.2`
  - `@types/node`: `24.19.2`
  - `@types/shelljs`: `0.8.17`
  - `babel-jest`: `30.5.2`
  - `core-js`: `3.46.0`
  - `diff`: `8.0.4`
  - `eslint`: `9.39.5`
  - `expect`: `29.7.0`
  - `globals`: `16.5.0`
  - `jest`: `30.5.2`
  - `prettier`: `3.10.1`
  - `shelljs`: `0.10.0`

## 3. How to Run

All commands run from the `~/dev/wt/nonpy` repo root:

```bash
# 1. Verify harness (Python workspace_tests + command acceptance) — 0 model calls
python3 ops/redo/redo.py selftest

# 2. Verify JS task bank + manifest integrity — 0 model calls
python3 ops/redo/banks/build_exercism_js.py --check

# 3. Rebuild JS task bank from ~/dev/ops/ref/src/exercism-javascript (optional)
python3 ops/redo/banks/build_exercism_js.py

# 4. Preflight the JS smoke plan (add --allow-uncommitted-plan before committing)
python3 ops/redo/redo.py preflight \
  --plan ops/redo/plans/smoke2_pi_gemma12b_js.json \
  --allow-uncommitted-plan

# 5. Run a committed plan (example; do not run until ready to call the model)
# ROOT=~/dev/ops/redo_runs/smoke2_js
# python3 ops/redo/redo.py run --plan ops/redo/plans/smoke2_pi_gemma12b_js.json --root "$ROOT"
```

## 4. Known Limits

1. **Protected file scope**: The smoke plan sets `"protect": ["*.spec.js"]` per spec. That prevents test-file tampering, but does not by itself restore `package.json`, `babel.config.js`, or `jest.config.js` if an adversarial agent rewrote `"scripts.test"` in `package.json` to `true`. Production JS plans that want to close that path can set `"protect": ["*.spec.js", "package.json", "babel.config.js", "jest.config.js"]` without harness changes.
2. **Host-machine symlink path**: `workspace/node_modules` points to the absolute path `/home/user1/dev/ops/ref/cache/exercism_js/node_modules`. Moving the bank to another machine requires either populating that cache path or re-running `build_exercism_js.py --cache <path> --bank <path>`.
3. **Not a sandbox**: As in `redo.py`'s existing honest boundary, both the agent and `npm test` execute as the current OS user; the temporary workspace is not a container or network namespace.
4. **Upstream `test.skip` preserved**: Consistent with upstream `exercism/javascript` CI (`scripts/helpers.mjs`), `xtest`/`xdescribe` are enabled while `test.skip`/`describe.skip` are kept skipped. Among the 34 chosen tasks, `js_reverse-string` has 7 active tests and 2 upstream-skipped tests (`ref_passed=7, ref_total=9`).
5. **Stub load-time throw**: In `js_simple-cipher`, the starter stub throws inside `constructor()` which is invoked during `describe()` setup, so Jest exits non-zero before running individual tests (`stub_failed=None, stub_total=0`); the reference passes 12/12.
6. **Visible tests equal grader**: `visible_equals_grader` is `true` for this bank (`grader_kind = "visible_tests_pristine"`). There are no separate hidden test suites; acceptance measures passing the full pristine `*.spec.js`.
