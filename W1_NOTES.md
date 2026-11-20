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
