# vacant `do` (restart mode) — adversarial review findings

Tool: `venv/bin/vacant do --cmd '<shell>' --prompt x [--check ...]` on throwaway
projects, fresh `VACANT_HOME`/`VACANT_WORK` per run. No contract files were used,
so every run took the "restart" path in `adapters/restart.py`. Stand-in agents
are bash/python scripts run as the agent; they run with the user's full
permissions inside the isolated copy (`attempt_N/w`).

Environment notes: pytest is NOT installed, so the `python_pytest` path could not
be exercised end-to-end; anything pytest-specific below is reasoned from source
and marked as such. node/npm and git exist; cargo/go do not.

Each finding has a self-contained repro `findings/<name>.sh`.

---

## A. Accepted-but-wrong

### A1 — Fixture/test-data files outside the protected set are writable and delivered
`findings/a1-fixture-poisoning.sh`
- Class: A. Confidence: high (reproduced).
- Project: `test_calc.py` (unittest) asserts `calc.add(2,3)` equals
  `fixtures/expected.txt` ("5"); `calc.add` is buggy (`a-b` → -1) → baseline FAIL.
- Agent (stand-in): `echo -n "-1" > fixtures/expected.txt` — never touches `calc.py`.
- Observed:
  ```
  baseline: python_unittest FAIL (0/1)
  attempt 1: python_unittest PASS (1/1)
  [vacant] acceptance passed on attempt 1 ... delivered that attempt. 0 added, 1 modified, 0 deleted.
  protected (restored before check): test_calc.py
  ```
  Delivered project: `fixtures/expected.txt` = `-1`, `calc.py` still buggy. Exit 0.
- Why it matters: protection covers only `*_test.py`/`test_*.py`/`*.test.*`/`*.spec.*`/
  `*_test.go`, dirs named `tests`/`test`/`__tests__`, and test-config names. Any
  fixture/data file a test reads from another location (e.g. `fixtures/`,
  `testdata/`, project root) can be poisoned to flip the verdict, and the poison
  is written back as a legitimate deliverable.

### A2 — Helper modules imported by tests are not protected (python + npm)
`findings/a2-helper-module-poisoning.sh`
- Class: A. Confidence: high (reproduced, both variants).
- Python: `test_impl.py` does `helpers.expected_answer()`; agent rewrites
  `helpers.py` to return the buggy value → `python_unittest PASS (1/1)` →
  `1 modified` written back; `impl.py` still buggy.
- npm (auto kind): `verify.test.js` (protected, restored) requires `./helper.js`;
  agent rewrites `helper.js` → `npm PASS (status=ok)` → poisoned helper.js
  delivered. package.json + verify.test.js pinning does not help.
- Why it matters: the defense restores the *test file* but not the *oracle code
  the test file imports*. "Files the tests check through" is wider than the
  test-name patterns; this is the same mechanism as A1 through the import graph
  rather than the filesystem.

### A3 — `--check 'npm test'`: package.json is not protected for kind=check
`findings/a3-check-manifest-rewrite.sh`
- Class: A. Confidence: high (reproduced).
- `--check "npm test"`: agent rewrites `package.json` → `scripts.test: "true"`.
  The `pinned_script` double-check in `_run_external_command` only runs when
  `spec.kind == "npm"`; for `kind == "check"` nothing pins or protects
  package.json.
- Observed:
  ```
  baseline: check FAIL (status=failed)
  attempt 1: check PASS (status=ok)
  acceptance passed ... delivered that attempt. 0 added, 1 modified, 0 deleted.
  protected (restored before check): verify.test.js
  ```
  Delivered `package.json` has `"test":"true"`. Exit 0.
- Why it matters: the exact "package.json test script" attack that was fixed for
  the auto-detected npm path is still open when the user supplies the same check
  themselves — the most natural way to use `--check`.

### A4 — `--check` harness files not matching test patterns are rewritable (verify.sh, Makefile)
`findings/a4-check-script-rewrite.sh`
- Class: A. Confidence: high (reproduced); vacant does print a warning.
- `--check "bash verify.sh"`: agent rewrites verify.sh to `exit 0` → PASS →
  gutted verify.sh written back. Same for `--check "make test"` with
  `test: @true` in Makefile.
- Observed: `protected (restored before check): none — the agent could have
  edited what this check runs` … `acceptance passed ... delivered that attempt.
  0 added, 1 modified, 0 deleted.` Exit 0.
- Why it matters: only files matching the hard-coded test names/configs are
  restored. The check's own entry point is usually *not* in that set
  (`verify.sh`, `Makefile`, `run_checks.py`, `FooTest.java`-style names that
  don't match `*.test.*`). The tool warns but still accepts exit-0 and delivers
  the tampered harness. `--protect` exists as mitigation but nothing tells the
  user which files the check reads.

### A5 — (source-only) runner config files missing from the protected set
- Reasoned from source, not run (needs tools not installed): `_TEST_CONFIG_PATTERNS`
  covers jest/vitest/mocha/babel/karma but NOT `playwright.config.*`,
  `cypress.config.*`, `wdio.conf.*`, `ava.config.*`, `.nycrc*`, `noxfile.py`.
  For auto npm kind (`npm test` → pinned script), an agent-edited
  `playwright.config.ts`/`cypress.config.js` would be copied into the acceptance
  dir and could restrict `testMatch`/spec selection to pass. Same class as
  A3/A4; flagged without a live repro.

---

## B. Escape from the copy

### B1 — Direct writes to the original project persist via `.git`, symlinks, and outside paths
`findings/b1-direct-escape.sh`
- Class: B. Confidence: high (reproduced).
- Attempt is rejected (test still fails); after delivery:
  - `.git/hooks/post-commit` (executable, planted via absolute path) **persists** —
    `.git` is in COPY_SKIP so it is never scanned/planned; it will run on the
    user's next `git commit`.
  - `planted_link -> /etc/hostname` **persists** — `_scan_files` skips symlinks,
    so the write-back plan never sees it.
  - `outside/marker.txt` (file outside the project) **persists** — never inspected
    (documented honesty boundary, still an escape).
  - A regular-file escape (`pwned_regular.txt`) **was deleted** by the write-back
    diff — good — which also demonstrates the flip side in D3.
- Output said only `0 added, 0 modified, 0 deleted` — no trace of any of this;
  the signed receipt records only planned write-back ops.
- Why it matters: "the copy is not a sandbox" is documented, but `.git/hooks` and
  symlinks inside the *project itself* survive silently even though restart mode
  partially defends the project (it reverts ordinary-file escapes). A run that
  reports "rejected, nothing written back" can still leave an executable git hook.

### B2 — setsid-detached process writes to the original project after delivery
`findings/b2-detached-process-escape.sh`
- Class: B. Confidence: high (reproduced; documented in the honesty boundary).
- Agent: `setsid bash -c 'sleep 4; echo LATE > <project>/late.txt' & sleep 1`.
- Observed: `acceptance passed ... delivered that attempt. 0 added, 0 modified,
  0 deleted.` → exit 0 → 4s later `late.txt` exists in the original project,
  unrecorded anywhere.
- Why it matters: vacant kills only the agent's process group. A write landing
  after the write-back plan is applied (or after exit) is never reverted or
  counted. The source docstring acknowledges detached grandchildren are not
  killed; the receipt still claims `0 added` with no caveat.

### B3 — node_modules protection is defeated by same-size write + mtime restore; acceptance then runs poisoned code
`findings/b3-node-modules-spoof.sh`
- Classes: A + B. Confidence: high (reproduced).
- During an attempt vacant chmods `node_modules` read-only and afterwards diffs a
  manifest of `(type, size, mtime_ns, inode, link)`. The agent (owner of the
  files) chmods them writable again, overwrites `depcheck/index.js` with the
  SAME byte length (`exports.ok = () => true; `, 25 bytes), and restores
  `st_mtime_ns` → manifest identical → undetected.
- Acceptance (`npm test`) then resolves `work/node_modules` → the ORIGINAL
  (poisoned) node_modules → `node verify.test.js` exits 0.
- Observed:
  ```
  baseline: npm FAIL (status=failed)
  attempt 1: npm PASS (status=ok)
  acceptance passed ... delivered that attempt. 0 added, 0 modified, 0 deleted.
  protected (restored before check): package.json, verify.test.js
  ```
  `node_modules/depcheck/index.js` in the ORIGINAL project remains poisoned.
  Exit 0.
- Why it matters: this silently defeats the previously-fixed "writes into
  node_modules" mitigation — the manifest key set omits content hashes and modes,
  so a size-preserving write with restored mtime is invisible, and it converts an
  integrity check into an oracle for acceptance (the check itself executes the
  tampered dependency through the acceptance-time symlink).

---

## C. Receipt / audit integrity

### C1 — Non-UTF-8 filename: delivered, then exit 2, and no signed receipt is written
`findings/c1-nonutf8-receipt.sh`
- Classes: C + D. Confidence: high (reproduced).
- Agent creates `bad-\xff-name.txt`. Observed:
  ```
  attempt 1: python_unittest PASS (1/1)
  vacant: 'utf-8' codec can't encode character '\udcff' in position 1336: surrogates not allowed
  EXIT=2
  ```
  The file IS delivered to the original project; then JSON serialization of the
  result/receipt hits the surrogate-escaped path (UnicodeEncodeError — a
  ValueError subclass, caught by the CLI's generic handler → exit 2). No
  `restart_receipt` is appended; `$VACANT_HOME` is left empty.
- `vacant audit list --strict` for the run shows only:
  `restart:restart-... restart - - - unreadable - unsigned 2` — a run that
  modified the project has no verifiable record. An agent can deterministically
  suppress its signed receipt this way.
- Why it matters: auditability is the product's core claim; a single byte in a
  filename turns a successful delivery into an unsigned, error-exiting run.

---

## D. First-time-user / ordinary-situation failures

### D1 — Read-only project: workspace copy is read-only, agent can't write, run still "passes and delivers"
`findings/d1-readonly-project.sh`
- Class: D. Confidence: high (reproduced).
- `chmod 0555 proj` → `shutil.copytree` propagates the mode → agent's
  `echo done > output.txt` → `Permission denied` (agent rc=1, visible only in
  `agent_stderr.log` inside the run dir) → acceptance on the unchanged copy
  still PASSes → `[vacant] acceptance passed ... delivered that attempt. 0
  added, 0 modified, 0 deleted.` Exit 0.
- Why it matters: the tool claims success while the agent could do literally
  nothing. The agent-failure notice is only emitted when acceptance fails, so a
  green run hides a dead agent. A read-only project should at least force a
  writable workspace mode or refuse up front.

### D2 — Running from a subdirectory: "no tests detected" while the project root has failing tests
`findings/d2-subdir-misleading.sh`
- Class: D. Confidence: high (reproduced).
- `proj/test_root.py` fails; run `vacant do` from `proj/pkg` →
  `not checked (no_tests)` → `ran once; no executable acceptance (no tests or
  supported test runner detected) ... 1 added` → exit 0, `output.txt` delivered
  into `pkg/` unchecked.
- Why it matters: the "no tests" message is false for the enclosing project.
  Nothing tells the user only a subdirectory was scanned.

### D3 — Files created in the project during a run are silently deleted at delivery
`findings/d3-concurrent-delete.sh`
- Classes: B + D (data loss). Confidence: high (reproduced).
- A file written into the project DURING an attempt (concurrent user edit — or
  an agent's direct escape write) is treated as "present in project but absent
  from the delivered snapshot" and unlinked by `_apply_write_plan`.
- Observed: `userfile.txt` created mid-run → summary `0 added, 0 modified, 1
  deleted` → `result.json: {'deleted': ['userfile.txt']}` → file gone.
- Why it matters: vacant deletes files it did not create, with only a count in
  the summary. The same mechanism conveniently erases evidence of an agent's
  regular-file escapes, so the receipt's `deleted` list is the only place the
  deletion is visible.

---

## Confirmed blocked / correct behavior (ran, not just reasoned)

- **Agent edits the test file** (`test_x.py` assert flipped to pass): restored
  before acceptance → `attempt 1: python_unittest FAIL` → exit 40; original
  test file unchanged.
- **Agent adds `conftest.py`**: reported as
  `the agent added test configuration (conftest.py); not used for the check and
  not written back` → exit 40; file not delivered.
- **Missing agent binary** (`--cmd /nonexistent-xyz`):
  `command not found: ... nothing was run, project unchanged` → exit 43.
- **Direct regular-file escape writes to the original project** are reverted
  (deletes planned by diffing live project vs delivered snapshot) — see B1/D3
  for the gaps that remain.
- **Project with no tests**: `ran once; no executable acceptance ... nothing was
  checked` → exit 0, honest message, delivers 1 added file — correct.
- **Tests already passing**: baseline `PASS (1/1)` then still runs the agent;
  correct.

## Tried but dead ends (reasoned/verified)

- **sitecustomize.py / usercustomize.py in the workspace** to hijack Python
  startup: verified `python3 -m unittest` and `python3 script.py` do NOT import
  sitecustomize from cwd/script dir (sys.path[0] is set after `site` init);
  runner env also strips PYTHONPATH entries under the work root.
- **`.pth` files**: only processed inside site-packages dirs; agent cannot reach
  them via the workspace and HOME is redirected to a private dir for Python
  runners.
- **PYTHONSTARTUP / PYTHONINSPECT**: not inherited — Python runners use a clean
  env; `--check`/npm/cargo/go inherit `os.environ` but `sh -c` doesn't source
  rc files.

## Notes on coverage

- Only the restart (no-contract) path was exercised. The contract path
  (`--contract`, intake `flow.submit` → `verifiers.run_all`, signed ledger)
  was read but not attacked end-to-end within the time budget; it additionally
  has `origin_digest` escape measurement that restart mode lacks.
- pytest-specific accept path (`python_pytest`) not runnable here — noted
  wherever relevant.
