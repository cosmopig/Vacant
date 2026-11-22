# Adversarial Security Review: `vacant_network/adapters/restart.py`

- **Target**: [`vacant_network/adapters/restart.py`](vacant_network/adapters/restart.py) (zero-config restart mode of `vacant do`)
- **Regression test suite**: [`tests/test_adapters_restart_attacks.py`](tests/test_adapters_restart_attacks.py)
- **Verification command**:
  ```bash
  TMPDIR=$HOME/dev/ops/tmp_test PYTHONPATH=$PWD ~/dev/Vacant/.venv/bin/python -m pytest tests/test_adapters_restart_attacks.py -q
  ```
- **Result on current code**: **21 / 21 attack tests FAIL** (every claimed finding below is backed by a failing pytest test on the unmodified codebase; existing [`tests/test_adapters_restart.py`](tests/test_adapters_restart.py) remains 15 / 15 passing).

---

## Summary Table

| ID | Goal | Severity | Finding | Test | Fails on Current Code |
|---|---|---|---|---|---|
| A1 | (a) | **CRITICAL** | `_through_symlink` bypass via `shutil.copy2` into an existing project directory containing a same-named symlink | `test_a1_write_back_dir_replaced_by_file_must_not_follow_nested_symlink` | YES (`AssertionError`) |
| A2 | (a) | **HIGH** | In-place `shutil.copy2` overwrites hard-linked files outside the project | `test_a2_write_back_must_not_overwrite_hardlinked_file_outside_project` | YES (`AssertionError`) |
| B1 | (b) | **HIGH** | `COPY_SKIP` mismatch deletes regular files named `.git` (breaks git worktrees/submodules) | `test_b1_copy_skip_regular_file_like_git_worktree_must_not_be_deleted` | YES (`AssertionError`) |
| B2 | (b) | **HIGH** | `COPY_SKIP` mismatch lets an agent write a bogus `.git` file inside `project/.git/` | `test_b2_agent_creating_copy_skip_file_must_not_write_into_project_git_dir` | YES (`AssertionError`) |
| B3 | (b) | **HIGH** | `chmod 0o111` directory in workspace causes `_write_back` to delete untouched project files | `test_b3_chmod_111_dir_in_workspace_must_not_delete_project_files` | YES (`AssertionError`) |
| B4 | (b) | **MEDIUM** | Replacing a directory with a file writes a bogus `dir/dir` file inside the project directory | `test_b4_dir_replaced_by_file_must_not_corrupt_project_dir` | YES (`AssertionError`) |
| B5 | (b)/(d) | **HIGH** | Replacing a file with a directory crashes `_write_back` mid-loop, leaving `project` partially mutated | `test_b5_file_replaced_by_dir_must_not_crash_with_partial_write_back` | YES (`FileExistsError`) |
| C1 | (c) | **CRITICAL** | Forging the static `@@VACANT_RESULT@@` sentinel via `atexit` fakes acceptance PASS | `test_c1_forged_vacant_result_sentinel_must_not_pass_acceptance` | YES (`AssertionError`) |
| C2 | (c) | **CRITICAL** | Package shadowing (`sol_test/__init__.py`) bypasses `sol_test.py` with `tests_tampered == []` | `test_c2_package_shadowing_test_module_must_not_pass_acceptance` | YES (`AssertionError`) |
| C3 | (c) | **CRITICAL** | Shadowing stdlib `unittest` (`ws/unittest.py`) hijacks `_UNITTEST_RUNNER` via `sys.path[0] == ""` | `test_c3_shadowing_stdlib_unittest_in_workspace_must_not_pass_acceptance` | YES (`AssertionError`) |
| C4 | (c) | **CRITICAL** | Symlink asymmetry: `acceptance()` follows workspace symlinks while `_write_back()` skips them | `test_c4_symlinked_code_passes_acceptance_but_is_not_written_back` | YES (`AssertionError`) |
| C5 | (c) | **CRITICAL** | TOCTOU: `setsid()` background process mutates `ws` after `acceptance()` copies it and before `_write_back()` | `test_c5_detached_background_process_toctou_mutates_ws_after_acceptance` | YES (`AssertionError`) |
| D1 | (d) | **HIGH** | Per-directory `timeout_s` in `acceptance()` scales total time to `N * acc_t`, blowing past `budget_s` | `test_d1_per_directory_acceptance_timeout_exceeds_budget_by_multiples` | YES (`AssertionError`) |
| D2 | (d) | **HIGH** | `acc_t = max(5.0, ...)` floor pushes wall time far past small `budget_s` | `test_d2_acc_timeout_5s_floor_exceeds_small_budget` | YES (`AssertionError`) |
| D3 | (d) | **HIGH** | FIFO (named pipe) in workspace crashes `shutil.copytree` in `acceptance()`, delivering nothing | `test_d3_fifo_in_workspace_crashes_run_and_delivers_nothing` | YES (`shutil.Error`) |
| D4 | (d) | **HIGH** | Replacing a test file with a directory crashes `acceptance()` (`IsADirectoryError`), delivering nothing | `test_d4_test_replaced_by_directory_crashes_acceptance_and_delivers_nothing` | YES (`IsADirectoryError`) |
| D5 | (d) | **HIGH** | Replacing a test parent directory with a file crashes `acceptance()` (`FileExistsError`), delivering nothing | `test_d5_test_parent_dir_replaced_by_file_crashes_acceptance_and_delivers_nothing` | YES (`FileExistsError`) |
| D6 | (d) | **HIGH** | `chmod 0o444` on a tampered test file crashes `acceptance()` (`PermissionError`), delivering nothing | `test_d6_readonly_tampered_test_crashes_acceptance_and_delivers_nothing` | YES (`PermissionError`) |
| D7 | (d) | **HIGH** | `chmod 0o000` on any workspace file crashes `acceptance()` (`shutil.Error`), delivering nothing | `test_d7_chmod_000_file_in_workspace_crashes_acceptance_and_delivers_nothing` | YES (`shutil.Error`) |
| D8 | (d) | **HIGH** | Printing a malformed `@@VACANT_RESULT@@` payload crashes `acceptance()` (`JSONDecodeError`), delivering nothing | `test_d8_malformed_vacant_result_marker_crashes_acceptance_and_delivers_nothing` | YES (`JSONDecodeError`) |
| D9 | (d) | **MEDIUM** | `acceptance()` does not use `start_new_session=True` / `killpg`, leaking grandchild processes after timeout | `test_d9_acceptance_timeout_leaks_grandchild_process` | YES (`AssertionError`) |

---

## Detailed Findings

### Category (a): Write, overwrite, or delete OUTSIDE the project or workspace

#### A1 — CRITICAL: `_through_symlink` bypass via `shutil.copy2` into an existing project directory
- **Affected code**: `restart.py:170-182` (`_write_back`)
- **Root cause & reproduction**:
  1. The user's project contains a real directory `project/sub/` with a pre-existing symlink `project/sub/sub -> /outside/outside_precious.txt`.
  2. The agent (operating strictly inside `ws`) removes `ws/sub` and creates a regular file `ws/sub` containing `"OVERWRITTEN\n"`.
  3. `_write_back` checks `_through_symlink(project, "sub")`, which returns `False` because `project/sub` is a real directory, not a symlink.
  4. Line 182 executes `shutil.copy2(ws / "sub", project / "sub")`. Because `os.path.isdir(dst)` is `True`, Python's `shutil.copy2` silently redirects the target to `project/sub/sub` — following the unchecked symlink and overwriting `/outside/outside_precious.txt` outside the project.
- **Test**: `tests/test_adapters_restart_attacks.py::test_a1_write_back_dir_replaced_by_file_must_not_follow_nested_symlink`
- **Fails on current code**: **YES**
  ```
  FAILED tests/test_adapters_restart_attacks.py::test_a1_write_back_dir_replaced_by_file_must_not_follow_nested_symlink
  AssertionError: assert 'OVERWRITTEN\n' == 'precious\n'
  ```
- **Suggested fix**:
  Never pass an existing directory to `shutil.copy2` (and prefer `shutil.copyfile` / atomic temp-file + `os.replace` over `shutil.copy2(src, dst)`). Explicitly check `dst.is_dir() and not dst.is_symlink()` before writing: either reject/skip directory-vs-file collisions or safely remove empty directories only after verifying no protected files or symlinks are affected. Also open destination files with `O_NOFOLLOW` or write to a temporary file in `dst.parent` (using `O_CREAT | O_EXCL | O_NOFOLLOW`) and `os.replace()` into `dst`.

#### A2 — HIGH: In-place `shutil.copy2` overwrites hard-linked files outside the project
- **Affected code**: `restart.py:182` (`_write_back`)
- **Root cause & reproduction**:
  1. The user's project has a file `project/shared.txt` that is hard-linked (`st_nlink > 1`) to `outside_hardlink.txt` outside the project (common with deduplicated datasets, backup snapshots, or package caches).
  2. `shutil.copytree` breaks the hard link when creating `ws/shared.txt`, so the agent edits an independent copy in `ws`.
  3. `_write_back` calls `shutil.copy2(ws / "shared.txt", project / "shared.txt")`, which opens `project/shared.txt` in `"wb"` mode and truncates/overwrites the existing inode in-place — clobbering `outside_hardlink.txt` outside the project.
- **Test**: `tests/test_adapters_restart_attacks.py::test_a2_write_back_must_not_overwrite_hardlinked_file_outside_project`
- **Fails on current code**: **YES**
  ```
  FAILED tests/test_adapters_restart_attacks.py::test_a2_write_back_must_not_overwrite_hardlinked_file_outside_project
  AssertionError: assert 'agent edit\n' == 'precious\n'
  ```
- **Suggested fix**:
  Write new contents to a sibling temporary file in `dst.parent` (`tempfile.NamedTemporaryFile(dir=dst.parent, delete=False)`) and atomically swap it into place with `os.replace(tmp_dst, dst)`. This preserves the external hard link untouched (and also avoids `PermissionError` on read-only destination files and avoids partial writes on crash).

---

### Category (b): Delete or corrupt files in the user's project not legitimately changed

#### B1 — HIGH: `COPY_SKIP` mismatch deletes regular files named `.git` (breaks git worktrees & submodules)
- **Affected code**: `restart.py:73` (`_files`) vs `restart.py:215` (`run`)
- **Root cause & reproduction**:
  1. `run()` copies `project -> ws` with `shutil.copytree(..., ignore=shutil.ignore_patterns(*COPY_SKIP))`, which skips **both directories and regular files** named `.git`, `node_modules`, `__pycache__`, `.venv`, `.pytest_cache`.
  2. `_files()` only filters `dns` (directories): `dns[:] = sorted(d for d in dns if d not in COPY_SKIP)`. It does **not** filter `fns` (regular files).
  3. In every git worktree and git submodule, `project/.git` is a **regular file** (`gitdir: ...`). `copytree` omits it from `ws`, `_files(project)` includes `".git"` in `before`, `_files(ws)` omits it from `after`, and `_write_back` unconditionally calls `(project / ".git").unlink()` — even when a completely benign agent never touched `.git`.
- **Test**: `tests/test_adapters_restart_attacks.py::test_b1_copy_skip_regular_file_like_git_worktree_must_not_be_deleted`
- **Fails on current code**: **YES**
  ```
  FAILED tests/test_adapters_restart_attacks.py::test_b1_copy_skip_regular_file_like_git_worktree_must_not_be_deleted
  AssertionError: .git worktree file was deleted by _write_back
  ```
- **Suggested fix**:
  Filter `fns` in `_files()` with the exact same rule: `if fn in COPY_SKIP: continue` (and keep `COPY_SKIP` filtering identical between `copytree` and `_files`).

#### B2 — HIGH: `COPY_SKIP` mismatch lets an agent inject a file inside `project/.git/`
- **Affected code**: `restart.py:73-77` (`_files`), `restart.py:182` (`_write_back`)
- **Root cause & reproduction**:
  1. In a normal git repository, `project/.git` is a directory skipped by `copytree` and `_files(project)`.
  2. Because `_files(ws)` does not skip regular files matching `COPY_SKIP`, an agent creating a regular file `ws/.git` puts `".git"` into `after`.
  3. `_write_back` calls `shutil.copy2(ws / ".git", project / ".git")`, which writes a bogus file `project/.git/.git` inside the user's `.git/` directory (and in a git worktree where `project/.git` is a file, overwrites `project/.git` with attacker-controlled `gitdir:` content).
- **Test**: `tests/test_adapters_restart_attacks.py::test_b2_agent_creating_copy_skip_file_must_not_write_into_project_git_dir`
- **Fails on current code**: **YES**
  ```
  FAILED tests/test_adapters_restart_attacks.py::test_b2_agent_creating_copy_skip_file_must_not_write_into_project_git_dir
  AssertionError: assert not True
  ```
- **Suggested fix**:
  Skip `fn in COPY_SKIP` in `_files()` (same fix as B1) and reject writing any path component in `COPY_SKIP` during `_write_back()`.

#### B3 — HIGH: `chmod 0o111` directory in workspace causes `_write_back` to delete untouched project files
- **Affected code**: `restart.py:72` (`_files`), `restart.py:183-188` (`_write_back`)
- **Root cause & reproduction**:
  1. In no-tests mode (documented policy #4), `acceptance()` is skipped.
  2. `project` contains `data/keep.txt`. The agent runs `os.chmod("data", 0o111)` (execute-only, not readable) in `ws` without deleting `data/keep.txt`.
  3. `_files(ws)` calls `os.walk(ws)` with default `onerror=None`, silently ignoring `PermissionError` when listing `ws/data` — so `data/keep.txt` vanishes from `after`.
  4. `_through_symlink(ws, "data/keep.txt")` calls `lstat()` through the `0o111` directory, which succeeds (only `+x` is needed for traversal) and returns `False`.
  5. `_write_back` deletes `project/data/keep.txt`.
- **Test**: `tests/test_adapters_restart_attacks.py::test_b3_chmod_111_dir_in_workspace_must_not_delete_project_files`
- **Fails on current code**: **YES**
  ```
  FAILED tests/test_adapters_restart_attacks.py::test_b3_chmod_111_dir_in_workspace_must_not_delete_project_files
  AssertionError: data/keep.txt was deleted despite still existing in ws
  ```
- **Suggested fix**:
  Pass an `onerror` callback to `os.walk` in `_files()` that records any unreadable directory prefix (or normalize workspace directory permissions to user-readable `0o700` before walking/copying), and never treat files under an unreadable workspace directory as deleted (skip them and record in `changed["skipped"]`).

#### B4 — MEDIUM: Directory replaced by regular file writes a bogus `dir/dir` file into the project
- **Affected code**: `restart.py:170-189` (`_write_back`)
- **Root cause & reproduction**:
  1. `project/sub/` is a directory containing `keep.txt`.
  2. The agent replaces `ws/sub/` with a regular file `ws/sub`.
  3. `_write_back` calls `shutil.copy2(ws / "sub", project / "sub")` while `project/sub` is still a directory, creating `project/sub/sub` and recording `"added": ["sub"]`, then deletes `project/sub/keep.txt`. `project/sub` remains a directory with a stray `sub/sub` file (and if `project/sub/sub` was a protected test file, it would be overwritten; if `project/sub/sub` was a normal pre-existing file, Loop 2 immediately deletes it, silently losing the agent's new file).
- **Test**: `tests/test_adapters_restart_attacks.py::test_b4_dir_replaced_by_file_must_not_corrupt_project_dir`
- **Fails on current code**: **YES**
  ```
  FAILED tests/test_adapters_restart_attacks.py::test_b4_dir_replaced_by_file_must_not_corrupt_project_dir
  AssertionError: assert not True
  ```
- **Suggested fix**:
  Run deletions before additions, prune newly-empty directories (only if no protected/untracked/symlinked files remain inside them), and before copying any file verify `not dst.is_dir()` (skipping and recording in `changed["skipped"]` if a non-empty or protected directory still occupies `dst`).

#### B5 — HIGH: File replaced by directory crashes `_write_back` mid-loop, leaving `project` partially mutated
- **Affected code**: `restart.py:170-189` (`_write_back`)
- **Root cause & reproduction**:
  1. `project` contains `a.txt`, `m.txt`, `z.txt`, `sol.py`.
  2. The agent modifies `a.txt`, `z.txt`, `sol.py`, and replaces regular file `m.txt` with directory `m.txt/child.txt`.
  3. `_write_back` processes additions/modifications (`sorted(after - protected)`) **before** deletions (`before - after - protected`).
  4. `project/a.txt` is overwritten, then `m.txt/child.txt` calls `dst.parent.mkdir(parents=True, exist_ok=True)` while `project/m.txt` is still a regular file, raising an unhandled `FileExistsError`. `sol.py`, `z.txt`, and all deletions are aborted, no `result.json` is written, and `project` is left half-written.
- **Test**: `tests/test_adapters_restart_attacks.py::test_b5_file_replaced_by_dir_must_not_crash_with_partial_write_back`
- **Fails on current code**: **YES**
  ```
  FAILED tests/test_adapters_restart_attacks.py::test_b5_file_replaced_by_dir_must_not_crash_with_partial_write_back
  FileExistsError: [Errno 17] File exists: '.../proj/m.txt'
  ```
- **Suggested fix**:
  Perform deletions (`before - after - protected`) **before** creating new parent directories and writing additions/modifications, and pre-validate all path-type conflicts (including conflicts with `protected` files like `sol_test.py/evil.py`) before mutating `project`.

---

### Category (c): Make `acceptance` report PASS when original tests would NOT pass on delivered code

#### C1 — CRITICAL: Forging the static `@@VACANT_RESULT@@` sentinel via `atexit`
- **Affected code**: `restart.py:66` (`_UNITTEST_RUNNER`), `restart.py:96` (`_clean_env`), `restart.py:144-146` (`acceptance`)
- **Root cause & reproduction**:
  1. `_UNITTEST_RUNNER` runs untrusted candidate code in the same Python process and emits a hardcoded, un-authenticated marker `\n@@VACANT_RESULT@@<json>` to `stdout`.
  2. `acceptance()` extracts the **last** occurrence via `out.rsplit("@@VACANT_RESULT@@", 1)[1]`.
  3. `_clean_env()` sets `HOME` to the `vacant-acc-*` temp directory, making it trivial for candidate code to detect acceptance execution.
  4. Broken `sol.py` (`def f(x): return x`) registers an `atexit` handler (only when `"vacant-acc-"` is in `HOME`) that prints `\n@@VACANT_RESULT@@{"run": 2, "failures": 0, ...}` after the real runner output. `acceptance()` parses the forged line and returns `accept: True`, while real tests fail 0/2 on the delivered project.
- **Test**: `tests/test_adapters_restart_attacks.py::test_c1_forged_vacant_result_sentinel_must_not_pass_acceptance`
- **Fails on current code**: **YES**
  ```
  FAILED tests/test_adapters_restart_attacks.py::test_c1_forged_vacant_result_sentinel_must_not_pass_acceptance
  AssertionError: assert True is False
  ```
- **Suggested fix**:
  1. Pass a per-run random nonce (`secrets.token_hex(16)`) or dedicated result pipe/fd (`pass_fds=(w_fd,)` closed in candidate or written to a parent-held pipe outside stdout) rather than a static stdout sentinel, and check `cp.returncode == 0` and that the marker appears **once**.
  2. Note: because candidate code runs in-process with `unittest` (unlike `vacant_network.checks.run_python_check`'s two-process RPC), in-process monkey-patching of `unittest` remains possible unless candidate execution is separated or the honest boundary explicitly notes that `restart.py` cannot defend against adversarial test-framework tampering in-process (still, fixing the static sentinel, `HOME` giveaway, and C2/C3/C4/C5 eliminates trivial bypasses).

#### C2 — CRITICAL: Package shadowing (`sol_test/__init__.py`) bypasses `sol_test.py` with `tests_tampered == []`
- **Affected code**: `restart.py:54` (`_UNITTEST_RUNNER`), `restart.py:111-139` (`acceptance`)
- **Root cause & reproduction**:
  1. `acceptance()` restores `sol_test.py` and runs `unittest.TestLoader().loadTestsFromName("sol_test")`.
  2. The agent leaves `sol_test.py` untouched, writes broken `sol.py`, and creates package `sol_test/__init__.py` containing a trivial passing `TestCase`.
  3. In Python's import system, a package directory `sol_test/` takes precedence over module file `sol_test.py`. `loadTestsFromName("sol_test")` imports `sol_test/__init__.py` instead of the restored `sol_test.py` and returns `accept: True`, `tests_tampered == []`.
- **Test**: `tests/test_adapters_restart_attacks.py::test_c2_package_shadowing_test_module_must_not_pass_acceptance`
- **Fails on current code**: **YES**
  ```
  FAILED tests/test_adapters_restart_attacks.py::test_c2_package_shadowing_test_module_must_not_pass_acceptance
  AssertionError: assert True is False
  ```
- **Suggested fix**:
  Load each original test file **by explicit filesystem path** using `importlib.util.spec_from_file_location(mod_name, exact_file_path)` (and `unittest.TestLoader().loadTestsFromModule(mod)`) instead of `loadTestsFromName(mod)`.

#### C3 — CRITICAL: Shadowing stdlib `unittest` (`ws/unittest.py`) hijacks `_UNITTEST_RUNNER`
- **Affected code**: `restart.py:48-49` (`_UNITTEST_RUNNER`), `restart.py:138` (`acceptance`)
- **Root cause & reproduction**:
  1. `acceptance()` launches `[sys.executable, "-B", "-c", _UNITTEST_RUNNER, *mods]` with `cwd = work / d`.
  2. Without `-P` / `-I`, Python's `-c` mode prepends `""` (current working directory) to `sys.path[0]` **before** line 48's `import json, sys, traceback, unittest`.
  3. Creating `unittest.py` (or `json.py` / `traceback.py`) in `ws` shadows the standard library module inside `_UNITTEST_RUNNER`. The fake `unittest.py` returns a stub `TestResult(testsRun=2, failures=[])` during acceptance while delegating to real `unittest` otherwise. `acceptance()` reports `accept: True` on broken `sol.py`.
- **Test**: `tests/test_adapters_restart_attacks.py::test_c3_shadowing_stdlib_unittest_in_workspace_must_not_pass_acceptance`
- **Fails on current code**: **YES**
  ```
  FAILED tests/test_adapters_restart_attacks.py::test_c3_shadowing_stdlib_unittest_in_workspace_must_not_pass_acceptance
  AssertionError: assert True is False
  ```
- **Suggested fix**:
  Pass `-P` (`PYTHONSAFEPATH=1`, available in Python >= 3.11, which is the repo's minimum Python version) to `sys.executable`, import all stdlib modules (`json`, `sys`, `traceback`, `unittest`, `importlib.util`) **before** adding `work / d` to `sys.path` (and append rather than insert ahead of stdlib, or insert after stdlib paths).

#### C4 — CRITICAL: Symlink asymmetry — `acceptance()` follows workspace symlinks while `_write_back()` skips them
- **Affected code**: `restart.py:110` (`acceptance`), `restart.py:76` (`_files`), `restart.py:184` (`_write_back`)
- **Root cause & reproduction**:
  1. `acceptance()` copies `ws -> work` with `symlinks=True` and executes Python inside `work`, where Python **follows** symlinks.
  2. `_write_back()` uses `_files(ws)` (which ignores symlinks) and skips deletion when `_through_symlink(ws, rel)` is `True`.
  3. Purely inside `ws` (no external files), the agent writes `GOOD` to `ws/_good_impl.py`, removes `ws/sol.py`, and creates relative symlink `ws/sol.py -> _good_impl.py`.
  4. `acceptance()` imports `work/sol.py` -> `_good_impl.py` and returns `accept: True` (`tests_tampered == []`).
  5. `_write_back()` skips `sol.py`, leaving `project/sol.py` untouched as `raise NotImplementedError`. Running the original tests on the delivered project fails 0/2 (`ERROR: NotImplementedError`).
  6. *(Variant)*: Symlinking `ws/unittest.py -> ../fake_unittest.py` leaves `changed["skipped"] == []` and zero extra files in `project` while writing `BAD` to `project/sol.py`.
- **Test**: `tests/test_adapters_restart_attacks.py::test_c4_symlinked_code_passes_acceptance_but_is_not_written_back`
- **Fails on current code**: **YES**
  ```
  FAILED tests/test_adapters_restart_attacks.py::test_c4_symlinked_code_passes_acceptance_but_is_not_written_back
  AssertionError: acceptance reported PASS but delivered project fails original tests: run=2 fail=0 err=2
  ```
- **Suggested fix**:
  **Test the exact tree that would be delivered**: build `work` for `acceptance()` by applying the same `_write_back` rules onto a fresh copy of `project` (i.e., start from `project` with symlinks/protected/skipped rules applied, NOT a raw `copytree(ws, work, symlinks=True)`). Any symlink that `_write_back` refuses to write back will then also be absent in `acceptance()`, eliminating the asymmetry completely.

#### C5 — CRITICAL: TOCTOU between `acceptance()` and `_write_back()` via surviving `setsid()` background process
- **Affected code**: `restart.py:219-238` (`run`), `run.py:289,322` (`run_agent`)
- **Root cause & reproduction**:
  1. `run_agent()` kills `proc`'s process group via `_kill_group(proc)` (`os.killpg`), which cannot reach a child that called `start_new_session=True` (`os.setsid()`).
  2. `acceptance()` copies `ws -> tmp/w` and runs tests on `tmp/w`, while `_write_back()` later reads from the **live, mutable `ws` directory** (not the tested snapshot, and with no content-hash check).
  3. The agent writes passing `sol.py` and spawns a `setsid()` background worker. Once `acceptance()` is running in `tmp/w`, the worker overwrites `ws/sol.py` with pure `BAD` (`def f(x): return x`).
  4. `acceptance()` returns `accept: True` (`tests_tampered == []`, `changed["skipped"] == []`), and `_write_back()` delivers pure `BAD` to `project/sol.py` with zero trace of the exploit remaining in `project`.
  5. *(Note)*: Even without a background process, `sol.py` running inside `acceptance()` itself knows `ws` (from the agent's `os.getcwd()`) and can directly overwrite `ws/sol.py` during test execution before `_write_back()` runs.
- **Test**: `tests/test_adapters_restart_attacks.py::test_c5_detached_background_process_toctou_mutates_ws_after_acceptance`
- **Fails on current code**: **YES**
  ```
  FAILED tests/test_adapters_restart_attacks.py::test_c5_detached_background_process_toctou_mutates_ws_after_acceptance
  AssertionError: acceptance reported PASS but delivered sol.py is: def f(x): return x
  ```
- **Suggested fix**:
  Before running `acceptance()`, capture an immutable snapshot (or `{rel: bytes}` / content hashes in a fresh `mkdtemp` directory with `0o700` permissions) of the candidate files from `ws`, run `acceptance()` on a copy of that snapshot, and have `_write_back()` deliver **from that exact verified snapshot** (never re-reading mutable `ws` after `acceptance()`).

---

### Category (d): Exceed `budget_s` by a lot, hang, or crash delivering nothing

#### D1 — HIGH: Per-directory `timeout_s` in `acceptance()` exceeds `budget_s` by `N × acc_t`
- **Affected code**: `restart.py:136-140` (`acceptance`)
- **Root cause & reproduction**:
  1. `acceptance()` groups tests by directory (`by_dir`) and runs `subprocess.run(..., timeout=timeout_s)` in a loop, passing the **full `timeout_s` to every directory** instead of tracking a single shared monotonic deadline.
  2. With 4 test directories (`d0`..`d3`) and `budget_s = 3.0`, an agent writes `sol.py` that sleeps `2.0s` on import (under `acc_t = 5.0`, so `TimeoutExpired` is never triggered).
  3. All 4 directories run sequentially for `8.2s` on a `3.0s` budget (> 2.7× budget). Under production defaults (`budget_s = 1800`, `ACC_TIMEOUT_S = 120`) on a repo with 20 test directories, a single `acceptance()` call can run for ~40 minutes (2,400s), exceeding the entire 30-minute `budget_s`.
- **Test**: `tests/test_adapters_restart_attacks.py::test_d1_per_directory_acceptance_timeout_exceeds_budget_by_multiples`
- **Fails on current code**: **YES**
  ```
  FAILED tests/test_adapters_restart_attacks.py::test_d1_per_directory_acceptance_timeout_exceeds_budget_by_multiples
  AssertionError: exceeded budget_s=3.0 by 5.2s
  ```
- **Suggested fix**:
  Compute `deadline = time.monotonic() + timeout_s` once at the start of `acceptance()`, and before each directory compute `left = deadline - time.monotonic()`; if `left <= 0`, return `status="timeout"`, otherwise pass `timeout=left`.

#### D2 — HIGH: `acc_t = max(5.0, ...)` floor pushes wall time far past `budget_s`
- **Affected code**: `restart.py:225` (`run`)
- **Root cause & reproduction**:
  1. Line 225 computes `acc_t = max(5.0, min(ACC_TIMEOUT_S, budget_s - (time.monotonic() - t0)))`.
  2. When `budget_s = 2.0`, attempt 1 runs for `~1.8s` (`budget_s - reserve`), leaving `0.2s` of budget — yet `acc_t` is clamped UP to `5.0s`.
  3. A slow `sol.py` causes `acceptance()` to run for the full `5.0s`, resulting in `total_wall_s = 6.8s` (> 3.4× `budget_s`).
- **Test**: `tests/test_adapters_restart_attacks.py::test_d2_acc_timeout_5s_floor_exceeds_small_budget`
- **Fails on current code**: **YES**
  ```
  FAILED tests/test_adapters_restart_attacks.py::test_d2_acc_timeout_5s_floor_exceeds_small_budget
  AssertionError: exceeded budget_s=2.0: total_wall_s=6.8
  ```
- **Suggested fix**:
  Cap `acc_t` by `max(0.5, min(ACC_TIMEOUT_S, budget_s - elapsed))` (or scale the floor with `budget_s`, e.g., `min(5.0, budget_s * 0.25)`), and compute `reserve` so that attempt 1 also respects small `budget_s` values (e.g., `reserve = min(ACC_TIMEOUT_S, max(budget_s * 0.2, 0.5))` without forcing `remaining >= 1.0` above `budget_s`).

#### D3 — HIGH: FIFO (named pipe) in workspace crashes `shutil.copytree` in `acceptance()`, delivering nothing
- **Affected code**: `restart.py:110` (`acceptance`)
- **Root cause & reproduction**:
  1. Attempt 1 achieves `HALF` (1/2 passing). Attempt 2 creates a FIFO (`os.mkfifo("pipe")`) in `ws`.
  2. `acceptance()` calls `shutil.copytree(ws, work, symlinks=True, ...)` which raises unhandled `shutil.Error` (`SpecialFileError: ... is a named pipe`).
  3. `run()` crashes completely; attempt 1's `HALF` is never delivered and no `result.json` is written. (Unix domain sockets trigger the same crash.)
- **Test**: `tests/test_adapters_restart_attacks.py::test_d3_fifo_in_workspace_crashes_run_and_delivers_nothing`
- **Fails on current code**: **YES**
  ```
  FAILED tests/test_adapters_restart_attacks.py::test_d3_fifo_in_workspace_crashes_run_and_delivers_nothing
  shutil.Error: [('.../attempt_2/w/pipe', '.../w/pipe', '`.../attempt_2/w/pipe` is a named pipe')]
  ```
- **Suggested fix**:
  Replace raw `shutil.copytree` with a defensive copier that only copies regular files and directories (skipping FIFOs, sockets, device nodes, and optionally symlinks — see C4), and catch copy/preparation `OSError`/`shutil.Error` inside `acceptance()` so a broken attempt returns `{"accept": False, "status": "copy_error", ...}` instead of crashing `run()`.

#### D4 — HIGH: Replacing a test file with a directory crashes `acceptance()` (`IsADirectoryError`)
- **Affected code**: `restart.py:126-129` (`acceptance`)
- **Root cause & reproduction**:
  1. Attempt 1 passes 1/2 (`HALF`). Attempt 2 unlinks `sol_test.py` and runs `os.mkdir("sol_test.py")`.
  2. In `acceptance()`, `_through_symlink(work, "sol_test.py")` is `False`, `not f.is_file()` is `True`, and `f.write_bytes(want)` raises unhandled `IsADirectoryError`. Nothing is delivered.
- **Test**: `tests/test_adapters_restart_attacks.py::test_d4_test_replaced_by_directory_crashes_acceptance_and_delivers_nothing`
- **Fails on current code**: **YES**
  ```
  FAILED tests/test_adapters_restart_attacks.py::test_d4_test_replaced_by_directory_crashes_acceptance_and_delivers_nothing
  IsADirectoryError: [Errno 21] Is a directory: '.../w/sol_test.py'
  ```
- **Suggested fix**:
  When restoring each original test file `f = work / rel`, if `f.is_dir() and not f.is_symlink()`, remove it with `shutil.rmtree(f)` before writing `want` (and handle any non-regular file at `f` by unlinking it first).

#### D5 — HIGH: Replacing a test parent directory with a regular file crashes `acceptance()` (`FileExistsError`)
- **Affected code**: `restart.py:128` (`acceptance`)
- **Root cause & reproduction**:
  1. Project has `tests/sol_test.py`. Attempt 1 passes 1/2 (`HALF`). Attempt 2 deletes `tests/` and creates a regular file `tests`.
  2. `acceptance()` calls `f.parent.mkdir(parents=True, exist_ok=True)`, which raises unhandled `FileExistsError` because `work/tests` is a regular file. Nothing is delivered.
- **Test**: `tests/test_adapters_restart_attacks.py::test_d5_test_parent_dir_replaced_by_file_crashes_acceptance_and_delivers_nothing`
- **Fails on current code**: **YES**
  ```
  FAILED tests/test_adapters_restart_attacks.py::test_d5_test_parent_dir_replaced_by_file_crashes_acceptance_and_delivers_nothing
  FileExistsError: [Errno 17] File exists: '.../w/tests'
  ```
- **Suggested fix**:
  Walk every parent component `p` of `rel` (just like the symlink branch does): if `p.is_symlink()` or (`p.exists()` and `not p.is_dir()`), `p.unlink()` it before `p.mkdir(exist_ok=True)`.

#### D6 — HIGH: `chmod 0o444` on a tampered test file crashes `acceptance()` (`PermissionError`)
- **Affected code**: `restart.py:110,129` (`acceptance`)
- **Root cause & reproduction**:
  1. Attempt 1 passes 1/2 (`HALF`). Attempt 2 modifies `sol_test.py` and runs `os.chmod("sol_test.py", 0o444)`.
  2. `shutil.copytree` preserves `0o444` via `copy2`. Line 129 calls `f.write_bytes(want)`, raising unhandled `PermissionError`. Nothing is delivered. (Similarly, `chmod 0o555` on a test's parent directory crashes `unlink`/`write_bytes` and leaves undeletable `vacant-acc-*` directories behind in `TMPDIR` because `shutil.rmtree(..., ignore_errors=True)` fails silently.)
- **Test**: `tests/test_adapters_restart_attacks.py::test_d6_readonly_tampered_test_crashes_acceptance_and_delivers_nothing`
- **Fails on current code**: **YES**
  ```
  FAILED tests/test_adapters_restart_attacks.py::test_d6_readonly_tampered_test_crashes_acceptance_and_delivers_nothing
  PermissionError: [Errno 13] Permission denied: '.../w/sol_test.py'
  ```
- **Suggested fix**:
  Before modifying or unlinking paths inside `work` (and in the `finally` cleanup of `tmp`), ensure user write/exec bits (`0o700` on directories, `0o600` on files, or unlink+create fresh files instead of opening read-only files in-place).

#### D7 — HIGH: `chmod 0o000` on any workspace file crashes `acceptance()` (`shutil.Error`)
- **Affected code**: `restart.py:110` (`acceptance`)
- **Root cause & reproduction**:
  1. Attempt 1 passes 1/2 (`HALF`). Attempt 2 creates `secret.txt` and runs `os.chmod("secret.txt", 0o000)`.
  2. `shutil.copytree(ws, work, ...)` fails to open `ws/secret.txt` and raises unhandled `shutil.Error` (`PermissionError`). Attempt 1 is never delivered.
- **Test**: `tests/test_adapters_restart_attacks.py::test_d7_chmod_000_file_in_workspace_crashes_acceptance_and_delivers_nothing`
- **Fails on current code**: **YES**
  ```
  FAILED tests/test_adapters_restart_attacks.py::test_d7_chmod_000_file_in_workspace_crashes_acceptance_and_delivers_nothing
  shutil.Error: [('.../attempt_2/w/secret.txt', '.../w/secret.txt', "[Errno 13] Permission denied: '.../attempt_2/w/secret.txt'")]
  ```
- **Suggested fix**:
  Wrap workspace copying in a helper that handles `PermissionError` (skipping unreadable files or restoring owner read bits on workspace copies if appropriate) and catch unexpected copy errors inside `acceptance()` so a single broken attempt returns `accept: False` rather than aborting `run()`.

#### D8 — HIGH: Printing a malformed `@@VACANT_RESULT@@` payload crashes `acceptance()` (`JSONDecodeError` / `IndexError` / `KeyError`)
- **Affected code**: `restart.py:146-151` (`acceptance`)
- **Root cause & reproduction**:
  1. Attempt 1 passes 1/2 (`HALF`). Attempt 2 writes `sol.py` that prints `\n@@VACANT_RESULT@@not-json\n` (or `\n@@VACANT_RESULT@@\n` -> `IndexError`, or `\n@@VACANT_RESULT@@{}\n` -> `KeyError`) and calls `os._exit(0)`.
  2. Line 146 executes `json.loads(out.rsplit("@@VACANT_RESULT@@", 1)[1].strip().splitlines()[0])` without error handling, raising unhandled `json.JSONDecodeError`. `run()` crashes and attempt 1 is never delivered.
- **Test**: `tests/test_adapters_restart_attacks.py::test_d8_malformed_vacant_result_marker_crashes_acceptance_and_delivers_nothing`
- **Fails on current code**: **YES**
  ```
  FAILED tests/test_adapters_restart_attacks.py::test_d8_malformed_vacant_result_marker_crashes_acceptance_and_delivers_nothing
  json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
  ```
- **Suggested fix**:
  Wrap result parsing and schema validation (checking `isinstance(r, dict)` and expected integer types for all counter fields) in `try ... except (ValueError, IndexError, KeyError, TypeError): return {**base, "status": "runner_bad_output", ...}` — and move the result channel off stdout onto a dedicated pipe/fd or random-nonce sentinel (see C1).

#### D9 — MEDIUM: `acceptance()` does not isolate process groups, leaking grandchild processes after timeout
- **Affected code**: `restart.py:138-143` (`acceptance`)
- **Root cause & reproduction**:
  1. Unlike `run_agent()` (which uses `start_new_session=True` and `_kill_group`), `acceptance()` calls `subprocess.run(..., capture_output=True, timeout=timeout_s)` in the caller's own process group.
  2. If candidate code spawns a child process that inherits `stdout`/`stderr` and sleeps, `subprocess.run` blocks for the full `timeout_s` (even if the test runner exits immediately), kills only the direct child on `TimeoutExpired`, and leaves the grandchild running as an orphan after `acceptance()` and `run()` return.
- **Test**: `tests/test_adapters_restart_attacks.py::test_d9_acceptance_timeout_leaks_grandchild_process`
- **Fails on current code**: **YES**
  ```
  FAILED tests/test_adapters_restart_attacks.py::test_d9_acceptance_timeout_leaks_grandchild_process
  AssertionError: grandchild pid ... leaked alive after acceptance() timed out
  ```
- **Suggested fix**:
  Launch the unittest runner via `subprocess.Popen(..., start_new_session=True)` (matching `run_agent`), wait with the shared deadline, and call `os.killpg(proc.pid, signal.SIGKILL)` in a `finally` block so any spawned subprocesses in the test runner's process group are terminated cleanly.

---

## Vectors Tested and Found NOT Exploitable

The following attack vectors were empirically tested against the current `vacant_network/adapters/restart.py` and confirmed **not** exploitable:

1. **Direct test-file symlink to an outside file (`ws/sol_test.py -> outside.txt`)** — `_through_symlink(work, rel)` detects the symlink, unlinks it inside `work`, and writes `want` to a fresh file. `outside.txt` is untouched.
2. **Relative symlink on a test file escaping `ws` (`ws/sol_test.py -> ../../../../outside.txt`)** — `_through_symlink()` checks `p.is_symlink()` regardless of relative vs absolute target; `outside.txt` is untouched.
3. **Test parent directory replaced by symlink (`ws/tests -> outside_dir`)** — `_through_symlink()` triggers the parent-unwrapping loop (`p.unlink(); p.mkdir(exist_ok=True)`), so `outside_dir` is untouched.
4. **Hard link on a test file in `ws` (`os.link(outside, "sol_test.py")`)** — Because `acceptance()` runs on a `shutil.copytree(ws, work)` copy (which creates new inodes for regular files), restoring `work/sol_test.py` writes to `work`'s new inode, not `outside`.
5. **Symlink loops (`a -> b`, `b -> a`), broken/dangling symlinks (`broken -> /nonexistent`), and symlinks to `/` (`rootlink -> /`)** — `shutil.copytree(..., symlinks=True)` recreates symlinks without traversing them, `_files()` uses `os.walk(followlinks=False)` and skips symlinks, and `shutil.rmtree()` does not follow symlinks. No hang, infinite recursion, or crash.
6. **Pre-existing file symlink in `project` (`project/link.txt -> outside.txt`) overwritten by agent creating regular file `ws/link.txt`** — `_through_symlink(project, "link.txt")` checks the final path component too, so `_write_back` skips `"link.txt"` and `outside.txt` is untouched.
7. **Workspace directory replaced by symlink to trigger project file deletion (`ws/data -> elsewhere`)** — `_through_symlink(ws, "data/keep.txt")` returns `True`, so `_write_back` skips deletion and preserves `project/data/keep.txt`.
8. **Deleting files through a project symlink (`project/link -> outside_dir`)** — `_files(project)` does not descend into symlinked directories (`followlinks=False`) and `_through_symlink(project, rel)` guards `unlink()`.
9. **Candidate raising `SystemExit(0)` inside a test (without forging `@@VACANT_RESULT@@`)** — `unittest` catches it as a test error (`accepted=False`), and `os._exit(0)` alone yields `status="runner_no_output"`, `accepted=False`.
10. **Agent ignoring `SIGTERM` (`signal.signal(SIGTERM, SIG_IGN)`) and sleeping past `attempt_timeout_s`** — `run_agent()` terminates the agent's process group with uncatchable `SIGKILL` (`os.killpg(proc.pid, signal.SIGKILL)`), stopping on schedule.
11. **Grandchild holding stdout/stderr open in `acceptance()` hanging forever past `timeout_s`** — On Python 3.12 (POSIX), `subprocess.run(..., capture_output=True, timeout=...)` does time out at `timeout_s` instead of hanging indefinitely (though it still consumes the full `timeout_s` and leaks the orphan grandchild — see D9).

---

## Additional Operational Note (Not Claimed as a Failing Test)

- **Sparse-file disk/RAM amplification**: Creating a 50 MB sparse file in `ws` (`f.truncate(50 * 1024 * 1024)`, 0 allocated blocks on disk) is materialized into 50 MB of real disk blocks by `shutil.copytree` in `acceptance()`, materialized again by `shutil.copy2` in `_write_back()`, and loaded wholly into RAM by `dst.read_bytes() == src.read_bytes()` (`restart.py:176`). No test was added for multi-GB expansion to avoid stressing the test runner's disk/RAM, but comparing files in chunks (or via streaming sha256) and enforcing a workspace copy size cap / timeout would close this DoS vector as well.


---

## Fix log

All 21 findings (A1–A2, B1–B5, C1–C5, D1–D9) were fixed in [`vacant_network/adapters/restart.py`](vacant_network/adapters/restart.py) using Python stdlib only (`vacant_network/adapters/run.py` already uses `start_new_session=True` + `_kill_group(proc)` and required no modification). Policy (`deliver_index` / `_policy_deliver`) and existing behavior remain unchanged; `誠實邊界` in `restart.py`'s module docstring was updated to describe the exact post-fix boundaries.

| ID | Fix in `vacant_network/adapters/restart.py` |
|---|---|
| **A1** | Replaced `shutil.copy2(src, dst)` with `_plan_write_back` + `_can_remove_dir` + `_atomic_write_from_file` (`mkstemp` in `dst.parent` + `os.replace`, which never redirects into an existing directory). Directories containing symlinks (or protected/`COPY_SKIP`/unreadable/non-deleted entries) cannot be removed, so the conflicting file write is skipped and reported in `changed["skipped"]`. |
| **A2** | Replaced in-place `shutil.copy2` with `_atomic_write_from_file` (`tempfile.mkstemp` + chunked copy + `os.replace`), atomically replacing the directory entry with a new inode so external hard links remain untouched. |
| **B1** | Updated `_scan_files` / `_files` and `_snapshot_workspace` to filter **both** directories and regular files against `COPY_SKIP`, and added `_has_copy_skip` guards in `_plan_write_back`, so regular files named `.git` (e.g., git worktrees/submodules) are never deleted. |
| **B2** | Same `COPY_SKIP` filtering in `_snapshot_workspace` and `_has_copy_skip` guards in `_plan_write_back` ensure agent-created regular files matching `COPY_SKIP` (such as `ws/.git`) are ignored and never written into `project/.git/`. |
| **B3** | `_snapshot_workspace` uses `os.scandir` with explicit `OSError` handling to record unreadable workspace directories (`unreadable_dirs`) and unreadable files (`unreadable_files`). `_plan_write_back` skips deleting any `project` path whose prefix matches `unreadable_dirs` / `unreadable_files` / `symlinks` / `special_files` (reporting them in `changed["skipped"]`). |
| **B4** | `_plan_write_back` + `_can_remove_dir` + `_apply_write_plan` execute deletions first, then `rmdir` deepest-first only directories proven to contain nothing outside the scheduled deletion set, then atomically place the replacing regular file via `os.replace`. |
| **B5** | `_plan_write_back` pre-validates all parent-path conflicts against the scheduled deletion set (skipping conflicts with protected or un-deleted files), and `_apply_write_plan` performs deletions before directory creation and file writes with full rollback on any unexpected error so `project` is never left partially mutated. |
| **C1** | Removed the static stdout `@@VACANT_RESULT@@` sentinel and `vacant-acc-` `HOME` prefix. `acceptance()` passes a dedicated result pipe (`w_fd` via `pass_fds`, immediately marked non-inheritable via `os.set_inheritable(w_fd, False)`) and a per-run random `secrets.token_hex(16)` nonce over stdin (which is then redirected to `/dev/null`), writes the nonce-tagged JSON once, closes `w_fd`, and exits via `os._exit(0)` (bypassing candidate `atexit` handlers). |
| **C2** | `_UNITTEST_RUNNER` loads each restored original test file by exact filesystem path via `importlib.util.spec_from_file_location` + `unittest.TestLoader().loadTestsFromModule`, preventing package directories like `sol_test/__init__.py` from shadowing `sol_test.py`. |
| **C3** | `acceptance()` writes `_UNITTEST_RUNNER` to an isolated script outside `work` and runs `[sys.executable, "-I", "-B", str(runner_script)]` (no `""` or user site on `sys.path`), imports all stdlib modules before appending `cwd` to the end of `sys.path`, so workspace modules like `ws/unittest.py` cannot shadow stdlib. |
| **C4** | `_snapshot_workspace` refuses all symlinks, and `_populate_acceptance_work` builds the acceptance tree from the exact post-write-back regular-file set (excluding skipped snapshot writes, preserving skipped project files, and containing zero symlinks) plus restored `originals`, eliminating any asymmetry between accepted and delivered trees. |
| **C5** | Immediately after `run_agent` exits and kills the agent's process group, `run()` captures a single private `0o700` snapshot (`_snapshot_workspace`, using `O_RDONLY | O_NOFOLLOW | O_NONBLOCK` and computing streaming sha256 digests). `acceptance()` evaluates a copy of that snapshot and `_write_back()` verifies hashes and delivers from that same snapshot rather than re-reading mutable `ws`. |
| **D1** | `acceptance()` computes one shared monotonic `deadline = time.monotonic() + max(0.0, timeout_s)` across all test directories in `by_dir`, passing only the remaining time to each subprocess and returning `status="timeout"` once `deadline` expires. |
| **D2** | Removed the `max(5.0, ...)` floor on `acc_t` (now `max(0.0, min(ACC_TIMEOUT_S, budget_s - elapsed))`) and capped the attempt-1 `remaining` floor by `min(0.1, budget_s)` so small budgets are respected. |
| **D3** | Replaced `shutil.copytree` in `acceptance()` with `_snapshot_workspace`, which checks `stat.S_ISREG` and opens with `O_NOFOLLOW | O_NONBLOCK` to skip FIFOs, sockets, and device nodes without crashing. |
| **D4** | `_restore_test_file` checks `lstat()` on the target test path and removes conflicting directories via `_rmtree_force` before writing the original test bytes. |
| **D5** | `_restore_test_file` walks every parent component of each test file and unlinks any non-directory (file or symlink) occupying a parent path before creating the directory. |
| **D6** | `_snapshot_workspace` stores snapshot copies with `0o600` permissions, `_restore_test_file` enforces `0o700` on parent dirs and unlinks existing test files before writing, and `_rmtree_force` restores owner `0o700`/`0o600` permissions before removing temp directories. |
| **D7** | `_snapshot_workspace` catches `OSError` / `PermissionError` on unreadable workspace files (recording them in `unreadable_files`), and `acceptance()` / `run()` wrap per-attempt evaluation in fail-safe `except Exception` handlers returning `status="acceptance_error"` instead of aborting `run()`. |
| **D8** | Result transport moved off stdout to the dedicated `w_fd` pipe, and `_parse_runner_output` validates UTF-8 decoding, exact 2-line format, constant-time nonce match (`hmac.compare_digest`), JSON parsing, and strict integer/string schema checks, returning `runner_no_output` / `runner_bad_output` without raising. |
| **D9** | `acceptance()` launches the runner via `subprocess.Popen(..., start_new_session=True)` and unconditionally calls `_kill_group_and_wait(proc)` (`os.killpg(proc.pid, signal.SIGKILL)` + brief wait until `killpg(pid, 0)` raises `OSError`) in a `finally` block, preventing leaked grandchild processes. |
