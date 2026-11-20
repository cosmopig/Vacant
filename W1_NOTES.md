# W1 Notes: Multi-Kind Acceptance for `vacant do` Restart Mode

Target files:
- [`vacant_network/adapters/restart.py`](vacant_network/adapters/restart.py)
- [`vacant_network/adapters/cli.py`](vacant_network/adapters/cli.py)
- [`tests/test_adapters_restart_acceptance_kinds.py`](tests/test_adapters_restart_acceptance_kinds.py)

## Design

Before W1, zero-config restart mode (`vacant do` without a contract) always ran `unittest.TestLoader().loadTestsFromModule(...)` on `*_test.py` / `test_*.py`. Any pytest-style project (bare `def test_*` functions or `class Test*` not inheriting `unittest.TestCase`) collected 0 tests, returned `{accept: False, run: 0, passed: 0, status: "ok"}`, and burned all retry attempts.

W1 separates acceptance **selection** (`detect_acceptance` -> `AcceptanceSpec`) from **execution** (`acceptance`), while preserving the exact existing `unittest` path, delivery policy (`deliver_index`), and all security properties from [`REVIEW_restart_attacks.md`](REVIEW_restart_attacks.md).

### Detection order (fixed at task start from the original project)

1. **`check`** — explicit `--check "<shell command>"` CLI option (`vacant do ... --check "..."`).
   - Runs the shell command (`shell=True`) inside the evaluated snapshot copy (`work`), own session (`start_new_session=True`), `killpg` on exit/timeout, shared monotonic deadline, user's environment (`PWD` set to `work`).
   - Acceptance = exit code `0` (`passed=None`, `run=None`).
   - Protected files = any `*_test.py` / `test_*.py` found by `find_tests(project)` at task start; they are still restored to original bytes before running `--check`, tampered edits are recorded in `tests_tampered`, and they are never written back.
2. **Python test files** (`find_tests(project)` non-empty) — inspected statically via `ast.parse` on the original test files:
   - **`python_unittest`** — when no pytest-style tests are present (all tests are `unittest.TestCase` or dynamic `unittest`). Keeps the **exact** existing `_UNITTEST_RUNNER` script, per-directory execution, and counts. This is the only path the `ops/redo` measurements apply to.
   - **`python_pytest`** — when bare `def test_*` functions or non-`TestCase` `class Test*` test classes exist, and `pytest` is importable by the test interpreter under `python -I -B`. Runs an isolated `_PYTEST_RUNNER` script outside `work` via `python -I -B`, imports `pytest` before appending `work` to `sys.path`, passes explicit restored test file paths with `--import-mode=importlib -q -rN -p no:cacheprovider -o addopts=`, writes `--junitxml` to a private directory **outside** `work`, and reports its exit code over a nonce-tagged dedicated pipe (`w_fd`) followed by `os._exit(0)`. Counts are parsed from the external junitxml.
   - **`python_bare`** — fallback when pytest-style tests exist but `pytest` is not importable by the test interpreter. Runs an isolated stdlib `_BARE_RUNNER` script (`python -I -B`, nonce-tagged pipe, exact file loading) that executes `unittest.TestCase` tests, bare top-level `def test_*` functions, and simple non-`TestCase` `class Test*` methods (handling mixed unittest + bare projects). If a test imports `pytest` or requires fixture arguments, reports `runner_unavailable` rather than failing and retrying.
3. **`npm`** — `package.json` with a non-empty `scripts.test` (excluding npm's default `"Error: no test specified"` placeholder) and `npm` on `PATH` -> `npm test` (exit code 0 = accept; `passed=None`, `run=None`).
4. **`cargo`** — `Cargo.toml` and `cargo` on `PATH` -> `cargo test` (exit code 0 = accept; `passed=None`, `run=None`).
5. **`go`** — `go.mod` and `go` on `PATH` -> `go test ./...` (exit code 0 = accept; `passed=None`, `run=None`).
6. **`none`** — nothing executable detected (or project markers found whose tools are absent from `PATH`). Runs once, delivers that attempt, and states clearly why nothing could be checked.

### Zero tests collected & runner unavailable

- If a runner collects 0 tests (`status="no_tests_collected"`) or cannot start due to non-candidate issues (`status="runner_unavailable"`, e.g. missing tool on `PATH`, `SyntaxError` in an original protected test file, pytest exit 3/4, or stdlib fallback encountering `import pytest` / fixture parameters), `accept` is `None`.
- On attempt 1, `run()` stops immediately without retrying, sets `res["accepted"] = None`, delivers attempt 1, and `summary()` explains clearly that nothing could be checked and why.
- Real failures/errors caused by candidate code (failing assertions, `SyntaxError`/`ImportError` in candidate modules, candidate crashing the runner with `os._exit(0)`, timeout) remain `accept=False` and trigger retries normally.

### Reporting & policy

- Both `summary(res)` and `result.json` (`acceptance.kind`, `acceptance.command`, `acceptance.protected`, `protected`) state the exact acceptance kind/command used and which files were protected/restored.
- `deliver_index` is unchanged: stop at the first accepted attempt; otherwise deliver the attempt with the most passed tests, ties going to the later attempt. For exit-code-only kinds (`check`, `npm`, `cargo`, `go`), `passed` is `None`, so when all attempts fail the tie rule delivers the latest attempt.

## Known Limits

- **Unmeasured**: the restart-mode numbers in `ops/redo` apply only to `python_unittest`. All newly added kinds (`check`, `python_pytest`, `python_bare`, `npm`, `cargo`, `go`) are unmeasured.
- **Not a sandbox**: the temporary workspace and snapshot copy run under the user's OS account. External commands (`--check`, `npm`, `cargo`, `go`) inherit the user's environment and privileges and can read/write anything the user can.
- **In-process Python execution**: in all Python paths (`python_unittest`, `python_pytest`, `python_bare`), candidate code still executes in the same Python process as the test framework, so in-process monkey-patching of `unittest`/`pytest` cannot be stopped here (use `vacant_network.checks.run_python_check` for two-process isolation).
- **Protected file scope**: only files matched by `find_tests` (`*_test.py` / `test_*.py`) are protected and restored before acceptance; auxiliary files such as `conftest.py`, `pyproject.toml`, `package.json`, or non-Python test files are not currently protected.
- **`COPY_SKIP` exclusions**: directories/files in `COPY_SKIP` (`.git`, `node_modules`, `__pycache__`, `.venv`, `.pytest_cache`) are not copied into the workspace or snapshot, which can affect `npm test` projects relying on a local `node_modules` tree.
- **Stdlib bare runner scope**: `python_bare` supports zero-argument bare `def test_*` functions (including `async def`), simple no-arg `class Test*` methods, and `unittest.TestCase`; it does not implement pytest fixtures, `parametrize`, or plugins (those report `runner_unavailable` if `pytest` is absent).

---

## RC2 Updates (Defect 1 & Defect 2)

Target files:
- [`vacant_network/adapters/restart.py`](vacant_network/adapters/restart.py)
- [`vacant_network/adapters/cli.py`](vacant_network/adapters/cli.py)
- [`tests/test_restart_rc2_protection.py`](tests/test_restart_rc2_protection.py)
- [`tests/test_restart_rc2_env.py`](tests/test_restart_rc2_env.py)

### Defect 1 — Protecting acceptance definitions & test files across ecosystems

**What changed:**
- **Pinned at start**: `detect_acceptance` pins the acceptance definition before the agent runs, including `package.json` `scripts.test` (`AcceptanceSpec.pinned_script`) and the full protected file set (`spec.protected`).
- **Cross-ecosystem protected files**: Before running acceptance, original bytes are restored (and agent edits are recorded in `tests_tampered` and never written back) for:
  - Test files across ecosystems: `*_test.py`, `test_*.py`, `*.test.*`, `*.spec.*`, `*_test.go`, and any regular file under `__tests__/**`, `tests/**`, or `test/**`.
  - Manifests defining the acceptance command: `package.json` (for `npm`), `Cargo.toml` (for `cargo`), and `go.mod` (for `go`).
- **Repeatable `--protect PATH/GLOB`**: `vacant do --check ... --protect <path-or-glob>` accepts exact paths, directory prefixes, and `**`-aware globs (rejecting paths escaping the project). Matched files are restored before acceptance and never written back with agent edits.
- **Honest unprotected warning**: When an executable acceptance has `protected == []`, `summary()` states plainly: `protected (restored before check): none — the agent could have edited what this check runs`. When protected files are modified by the agent, `summary()` lists them and notes they were checked against originals and not written back.

**What is still not protected:**
- Newly created files that did not exist at task start (e.g. an agent adding a new `jest.config.js`, `.mocharc`, `conftest.py`, or a new `*_test.go` with `init()`/`TestMain`).
- Non-test configuration files (`pyproject.toml`, `setup.cfg`, `tsconfig.json`, `vitest.config.*`, `babel.config.*`, etc.) or custom test runner scripts with non-standard names unless explicitly passed via `--protect`.
- Helper modules outside `tests/` / `test/` / `__tests__/` imported by tests (unless passed via `--protect`).
- In-process monkey-patching by candidate code executed in the same process as the test runner.

### Defect 2 — Project Python interpreter, `node_modules` reachability, and baseline pre-check

**What changed:**
- **Project Python interpreter (`resolve_python`)**: Python acceptance (`python_unittest`, `python_pytest`, `python_bare`) now resolves the interpreter in order:
  1. `$VIRTUAL_ENV/bin/python` (or `python3`)
  2. `<project>/.venv/bin/python` (or `python3`)
  3. `<project>/venv/bin/python` (or `python3`)
  4. `python3` / `python` from `PATH`
  5. `sys.executable` (last resort)
  Venv executable symlinks are never dereferenced so `pyvenv.cfg` remains active, and `<project>/.venv` is referenced in place without copying it into `ws` or `snap`. The resolved interpreter is recorded in `result.json`, the signed `restart_receipt`, and `summary()`.
- **Flags (`-B` kept, `-I` dropped)**:
  - `-B` (`PYTHONDONTWRITEBYTECODE=1`) is kept so acceptance never writes `.pyc` / `__pycache__` into the copy.
  - `-I` is dropped because `-I` implies `-E` (ignoring `PYTHONPATH` / wrapper-injected paths) and `-s` (hiding `pip install --user` site-packages). C3 shadowing resistance (`work/unittest.py`, `work/pytest.py`) is preserved without `-I` (and without requiring Python 3.11's `-P`, so older project venvs such as Python 3.10 also work) by running the runner script from a private empty directory outside `work`, stripping `""`, `"."`, the runner dir, and `cwd` from `sys.path` before importing `unittest`/`pytest`, filtering relative/`work` entries out of `PYTHONPATH`, and appending `work` only after framework imports succeed. Editable-install `sys.path` entries pointing at the original project root (or `src`) are redirected to the evaluated copy.
- **Acceptance-only `node_modules` reachability**: `node_modules` stays in `COPY_SKIP` and is never copied or symlinked into the agent workspace (`ws`) or snapshot (`snap`). During external acceptance (`npm`, `--check`, etc.) only, `work/node_modules` is symlinked to `<project>/node_modules` (along with `NODE_PATH` and `node_modules/.bin` on `PATH`) and unlinked immediately after acceptance finishes, before write-back.
  - *Trade-off*: the agent itself cannot write through a symlink in `ws` to `<project>/node_modules`, but candidate code executed *by* `npm test` / `--check` during acceptance runs under the user's OS account and could still write into `<project>/node_modules` through that symlink (consistent with restart mode not being an OS sandbox).
- **Baseline pre-check**: Before attempt 1, `run()` runs acceptance once on the untouched project copy and records `baseline` in `result.json` and the signed receipt.
  - If the baseline cannot run due to the environment (`load_error` / collection `ImportError`, `runner_unavailable` such as missing `pytest` or `npm`, or shell command-not-found exit 126/127), `run()` stops immediately with **0 agent attempts**, leaves the project untouched, reports `acceptance cannot run in this environment: <reason>` with the command and interpreter, and `vacant do` exits nonzero (`43`).
  - A baseline that runs and FAILS proceeds as before; a baseline that PASSES also proceeds as before (policy unchanged) and is noted in the delivery message.

**What is still not protected / known limits:**
- If a project's *own* broken source file causes a `SyntaxError` or `ImportError` during baseline test collection (`load_error`), the baseline pre-check treats it as an environment/collection error and stops with 0 attempts rather than trying to guess whether the missing symbol is a missing dependency or a file the user wanted the agent to create.
- A project using a non-standard virtualenv location (e.g. Poetry/Hatch/Conda outside `$VIRTUAL_ENV`, `.venv`, `venv`, and `PATH`) must activate it (`VIRTUAL_ENV`) or put its `bin/` on `PATH`.
- Acceptance-only `node_modules` symlink is not read-only at the OS level; malicious candidate code executed during `npm test` can still modify files the user's OS account can write.
