# 0.9.2 (rc5): known limits of `vacant do` restart mode

These are written down rather than fixed, under the convergence rule agreed on 2026-11-21. Only three classes were must-fix:
- accepted-but-wrong with no warning on a kept-fixed (`traced`) check, **through a file outside the code under test** (a test, config, check script, manifest, runner config, shadowing file or package init);
- silent damage to user files;
- receipt failure.

The code under test itself is outside that class: see the section "The code under test runs inside the check", which can be `traced` with no warning and are listed here as structural. Everything else is listed here. Each item links its repro script under `tests/adversarial_rc5_repro/`, where one exists.

## Structural (cannot be fixed without OS-level isolation)

1. **Receipts can be forged by a process running as the same user.** The signing key is a file that any process running as you can read, including the agent. Receipts protect against tampering after the fact: change one record and every later hash stops matching. They do NOT protect against a same-user process forging a new, valid-looking receipt. Repro: `round3/r6-receipt-forge.sh`. Ideas: key isolation (a separate account, an OS keystore or a hardware key) and anchoring the chain head outside the machine. Not planned for 0.9.2.
2. **Not a sandbox.** The agent runs with your permissions and can write anywhere you can.
   - rc5 lists changes it detects in your project outside the delivered attempt: lstat listing of the project, all of `.git` including `objects/`, nested `node_modules`/`.venv`.
   - It refuses to deliver when such changes overlap the delivery, and the check always runs against the start snapshot.
   - It does not revert changes outside the delivery, and it sees nothing outside the project directory. Repro: `b1-direct-escape.sh`, `round2/e4-b1-listing-gaps.sh`.
3. **Detached processes.** On Linux, detached descendants are caught by a subreaper and killed after each attempt, after each check and at the end. A write that lands in the moment after the final pass is still not recorded. On other platforms this layer does not exist. Repro: `b2-detached-process-escape.sh`, `round2/e2-b2-env-i.sh`.

## The code under test runs inside the check (structural)

4. **The code under test can tamper with the test framework in the check's own process.** It runs in the same process as the check. Examples: a line at the end of a module that replaces `unittest.TestCase.assertEqual`, or code that patches pytest's `TestReport`. Such a run can be `traced`, show no NOTE, and pass. Separating the check and the code under test into different processes would change what is measured, so it is not done in 0.9.2. The README's "what it does not do" says this.
5. **The only module a test imports directly is treated as the code under test**, so it does not trigger the dependency NOTE, even when it is really a helper that re-exports the expected answers. Package `__init__.py` files and new files shadowing an existing module are NOT exempt.
6. **"accepted-but-wrong = 0" in all batches** uses the task's pristine visible tests as the grader (`grader_kinds = visible_tests_pristine`). It means nobody got a pass by tampering with the tests. It does not mean the answers are correct beyond those tests.

## What `traced` means and does not mean

7. **`traced` only means the analyzer traced every project file the check executes and kept all of them fixed.** It does not mean:
   - the check is correct;
   - nothing else influences it, e.g. data files read at runtime with computed paths, dynamic imports, environment variables, or network.

   Dynamic imports (`importlib`, `__import__`, `exec`, `eval`, `runpy`) in kept-fixed tests or check scripts make the run `untraced`, with the reason `dynamic-import`. Paths computed at runtime in the code under test are not traced. Repro: `round4/f6-node-fs-read.sh` (untraced), `round2/e6-a1-unflagged-deps.sh` (the `dynimport` case, now untraced).
8. **Most real-world check scripts come out `untraced`.** Examples: shell redirection, unknown commands such as `diff` or `grep`, `bash -c`, or a check script that imports the module under test. In that case the message carries only a short tag. The NOTE line appears only when a changed file is concretely detected among the check's inputs. An untraced check can be beaten through the untraced inputs; that is what untraced says. Repro: `round4/f8-regression.sh`.
9. **The NOTE about the check's dependencies is a best-effort list.**
   - It covers: literal file names in kept-fixed test files, imports up to depth 2, package `__init__.py` chains, and fixture/data directory names.
   - It does not cover: names computed at runtime, imports deeper than 2, or literals split across strings.

## Time limits and slow backends

10. **Each attempt is capped at 600 s by default (1800 s total).** A task that needs one longer run is cut off, and restarting hits the same cap. This is much more frequent on slow backends. Measured on Colab L4 (vLLM, jobs 6): mean model turn 24–50 s versus 5–12 s on local 3090s; 26–80% of inner attempts cut, versus 6–36% locally.
   - The message reports every cut. When all attempts were cut, it says to raise `--attempt-timeout` / `--timeout`.
   - A pre-registered comparison of 900 s vs 600 s (atimeout) decides whether the default changes. Analysis: `ops/redo/analysis/turn_latency.py` on the nonpy branch.

## Not tested live

11. cargo, go, maven/gradle, playwright/cypress/wdio/ava/nyc/nox were not installed on the review machine. Their protection paths are covered by unit tests and stand-in commands only. pytest was tested live by the independent verification, with pytest installed in a project `.venv` (repro `verify_rc5/u_d2`).
12. The non-Linux paths (no subreaper, `detached_processes: null`) were tested only by faking `sys.platform`.
13. Plan→apply races narrower than a re-check, such as a directory swapped mid-apply, are reasoned about only.

## Cost

14. npm projects: the agent gets its own copy of `node_modules` (reflink when the filesystem supports it, otherwise a full copy). The message warns when it falls back to a full copy. The copy time is recorded as `copy_s`. On a 36 MB / 3000-file `node_modules`: copy 0.14 s, manifest 0.04 s.

## Fixed after the first freeze (for the record)

- **P1.** A project module named like a stdlib module (`queue.py`, `statistics.py`) was shadowed by the stdlib during the check in rc4 and early rc5: correct fixes were judged FAIL, and broken modules could be judged PASS. The runners now put the project dir first. No measured task was affected (0 of 206 Python task modules collide with a stdlib name). Repro: `verify_rc5/u_d`, `u_d2`, `mine_m1`, `m10_from_attacks.sh.txt`.
- **P5.** Unreadable project files crashed with a traceback; now the run stops before the agent starts (exit 43, with a message and a receipt).
- **N1.** On the unittest path, tests in a `tests/` package that import a module at the project root were judged FAIL even when the fix was correct. Import resolution now matches `python3 -m unittest` run at the project root. The `src/` layout still needs PYTHONPATH, as it would outside Vacant. No measured batch was affected: all are flat.
- **N2.** Dynamic imports inside helper modules the tests import, up to depth 2, now make the run `untraced`. Previously only the kept-fixed files themselves were scanned.
