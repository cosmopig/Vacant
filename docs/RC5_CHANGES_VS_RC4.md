# rc5 compared with rc4 / wheel 37005ec2 — what changed in `vacant do` restart mode

- rc4 is `652c50d36`. Its code is identical to the release candidate wheel `37005ec2aa91…`, which the running confirm2, confirm2c and atimeout batches measure.
- rc5 was first frozen at `83e84da29` (branch `redo/rc5`), then reopened once for the independent verification's P1/P5 items and refrozen. The final freeze commit is recorded in RELEASE_PREP. It came out of five rounds of adversarial review by Devin, written up in `tests/adversarial_rc5_repro/` (round 1 and round2–round5).
- The fixes were written by agy and reviewed by Claude. Every round reran the full test suite and the policy differential.

## The delivery policy did not change (evidence)

`tests/adversarial_rc5_repro/policy_diff_rc4_rc5.py` runs the same scenarios with the same scripted agent through rc4 and rc5 and compares:
- the exit code;
- `accepted` and `delivered_attempt`;
- each attempt's (accept, passed, run);
- the number of agent calls;
- a sha256 of every file in the project tree afterwards.

Result at the final freeze: **10/10 identical, plus 2/2 expected differences correct** (see P1 below). The 10 identical scenarios are:
- passes on the first attempt;
- fails, then passes on the second;
- never passes, so the best attempt is delivered;
- the agent edits the test file;
- the agent exits non-zero but the tests pass;
- a deletion in a subdirectory;
- a new module the tests import (`solution.py` does not exist at start);
- no tests;
- `--check`;
- npm.

The two expected differences are bug fixes:
- `py_stdlib_name_fixed`: rc4 rejected a correct fix; rc5 accepts it.
- `py_stdlib_name_broken`: rc4 accepted a broken module; rc5 rejects it.

Not covered by the differential: cargo and go (not installed on the test machine), and a real 600 s time-limit cut. pytest was exercised by the independent verification inside a project `.venv`.

## Behaviour changes, all outside a normal run
These only take effect when something abnormal happens: an escape, a concurrent edit, tampering, or an odd filename.

1. **node_modules.** The agent gets its own copy of `node_modules` (reflink when the filesystem supports it, otherwise a plain copy) instead of a symlink to the project's copy. Symlinks that point outside are replaced by real files in the copy. The original is checked with an lstat manifest (size, mtime, ctime, inode, mode, link target) at start, before each check and at the end. A change stops the run with exit 43 (as in rc4) and nothing is written back.
   This also changes the agent's environment in ordinary npm runs: it now works on a copy, which costs time to make (recorded as `copy_s`). The npm scenario in the differential is identical.
2. **The check is pinned more widely.** More files are kept fixed: restored to their start content before each check and never written back.
   - manifests reached by the check: `package.json`, Makefile, Cargo.toml, go.mod and others, including nested ones and npm `--prefix`;
   - files named in the check command or in a shell or Makefile check script;
   - `python -m` modules;
   - runner configs, including `.npmrc`, `.yarnrc*`, babel/swc/tsconfig, `.cargo/config*`, playwright/cypress/wdio/ava/nyc/nox configs, and files referenced from jest/mocha config keys in `package.json`;
   - files matched by `unittest discover` patterns.

   Agent-created files of these kinds are left out of the check copy and not written back. The same applies to new `__init__.py` files in test directories, and to new files that would shadow a module that already resolved at start (stdlib, an installed package, or an existing project module).
3. **The check runs against the start snapshot.** Before each check, the files the attempt did not touch are copied from the start snapshot, not from the live project. An agent writing directly into the real project therefore cannot make the check pass.
4. **Write-back against the start snapshot.**
   - Only files that existed at start and were deleted by the delivered attempt are deleted. Files that appear during the run are left alone and listed.
   - If a path changed in the project during the run AND the delivered attempt also changes it, **nothing is written back and the exit code is 43**. The message lists the conflicting paths and where the accepted attempt's files are kept. **This is a new exit-43 condition.**
   - Every file is re-checked just before it is replaced.
5. **Detached processes are killed.** On Linux, a subreaper catches descendants that detach. They are killed after each attempt, after each check and at the end, and recorded with their pid and command line. On other platforms this layer does not exist, and the message says so.
6. **Upfront refusal.** If the project directory is not writable, the run stops before the agent runs (exit 43). The agent's copy is always writable.
7. **State and work roots** (`VACANT_HOME`, `VACANT_WORK`) are never copied into the agent's workspace, even when they sit inside the project. This keeps the signing keys out of the workspace and stops the recursive-copy crash.
8. **Receipts and audit.**
   - Every string is byte-safe, so non-UTF-8 file names or prompts no longer suppress the receipt.
   - Before writing the receipt, permissions on Vacant's own state are repaired. If it still fails, the message starts with a WARNING.
   - `vacant audit list --strict` now fails on restart runs that have no signed receipt.
   - New fields: `acceptance_integrity` (traced/untraced) with reasons; `outside_changes`, `appeared_during_run` and `write_back_conflicts`; `detached_processes`; `acceptance_dependencies_changed`; `not_delivered`; `time_limit_s` per attempt; and timing fields.
9. **Messages state facts only.**
   - `kept fixed (restored to their start content before each check): …` replaces "protected".
   - Untraced checks get a short tag on the acceptance line.
   - A `NOTE:` line appears only when the delivered attempt changed a file the check reads or runs that was not kept fixed.
   - Each time an attempt was cut at its time limit, the message says so, and suggests raising the limit when every attempt was cut.
   - Changes made to the project outside the delivered attempt are listed, with prominent lines for `.git/hooks`, refs, `.pth` files and `.git/objects`.
10. **Mode bits.** Restored files keep their mode bits, so `./verify.sh` stays executable. The original `node_modules` is no longer chmod-ed, so killing Vacant can no longer leave it read-only. Both were regressions introduced inside rc5 and fixed before the freeze.

## P1: a project module named like a stdlib module (fixed when the freeze was reopened)
- In rc4 (`37005ec2`) and in rc5 up to `83e84da29`, the isolated Python runners appended the project dir to `sys.path`, so it came after the stdlib.
- Effect: a project's own `queue.py` or `statistics.py` was shadowed by the stdlib module of the same name during the check. A correct fix was judged FAIL, and a broken module could be judged PASS.
- The runners now put the project dir first, which is what `python -m unittest` / `pytest` do in the project. New files that would shadow a name that already resolved at start are still left out (rc5e).
- **Effect on measured batches: none.** The modules of all 206 Python tasks used with rc1+ wheels were checked against `sys.stdlib_module_names`:
  - polyglot_py: 34;
  - exercism_py_unused: 40;
  - exercism_py_hard: 26;
  - exercism_py_pool: 106.

  None collides. The JS batches use relative imports and are not affected.

Also changed when the freeze was reopened:
- **P5:** unreadable project files now stop the run before the agent starts, with exit 43, a message and a receipt, instead of a traceback.
- Dynamic imports in kept-fixed files make the run `untraced`.
- `vacant audit list` / `show` mark a write-back conflict run as "accepted, not written back (conflict)".
- Shadowing files get their own wording.

## The measured path: zero-config `python_unittest`
- The confirm and unused40 batches measured this path. rc5 changes it only in abnormal cases: shadow files and new test-directory `__init__.py` are left out of the check; a changed package `__init__.py` prints a NOTE; the check runs against the start snapshot.
- A normal run of this path is covered by the differential and is identical.
- In every batch run so far, the native arm and the product arm both have **accepted_but_wrong = 0** and per-attempt `signal.accept_fail = 0`. The batches are confirm1, confirm1c, unused40, hardpy26, W3-5 (screen and confirm), redo1_pi, redo1_opencode, the screen16 runs, and confirm2 partial. Source: each batch's REPORT.json. The grader is the task's pristine visible tests (`grader_kinds = visible_tests_pristine`). So the 0 means "nobody got a pass by tampering with the tests". It does NOT mean "the answers are correct beyond the tests".
