# vacant `do` (restart mode) — adversarial review, round 2 (rc5)

Tool: `venv/bin/vacant do --cmd '<shell>' --prompt x [--check ...] [--protect ...]` on
throwaway projects under `projects/`; fresh `VACANT_HOME`/`VACANT_WORK` per run (as
siblings of the project, never inside it, except where a finding requires it).
Environment: Linux, node v22 + npm present, git present, python3.12; **pytest,
cargo, go not installed** — those paths are reasoned only.

Each finding has a self-contained repro `findings/<id>.sh`.

---

## Findings

### R1 — `VACANT_HOME` inside the project: private signing keys copied into the agent's workspace; `VACANT_WORK` inside the project: recursive copytree crash
`findings/e1-state-inside-project.sh`
- Class: escape + receipt-integrity (a); crash/UX (b). Confidence: high (reproduced).
- Restart mode's workspace copy is `shutil.copytree(project, ws, ignore=COPY_SKIP)`
  with **no exclusion for the state or work roots** — unlike the contract path's
  `_skip_dirs`, which exists precisely because "keys would be copied into the
  agent's workspace".
- (a) With `VACANT_HOME=<project>/.vacant` (the code's own comment calls
  state-inside-repo "CI 常見"), the second run copies
  `.vacant/intake/keys/{owner,approver,reviewer,verifier}/identity.key` into
  `attempt_1/w/`. Evidence:
  ```
  attempt_1/w/.vacant/intake/keys/verifier/identity.key   (and 3 more roles)
  ```
  The agent therefore holds the user's Ed25519 keys and a copy of the signed
  trace chain — it can sign arbitrary `restart_receipt`s, forge approvals, or
  modify the chain in ws and have the write-back deliver the forgery onto the
  real `chain.ndjson` (it still verifies: it's signed with the real key). The
  whole "signed receipt" claim collapses in this configuration.
- (b) With `VACANT_WORK` inside the project, `copytree` recurses into the run
  directory being created inside itself → `shutil.Error` / `Errno 36 File name
  too long` → bare traceback, exit 1, no receipt, no message.
- Why it matters: zero-config users with state inside the repo either crash or
  silently hand the agent root authority over the audit trail.

### R2 — B2 evasion: detached process with a scrubbed environment is invisible
`findings/e2-b2-env-i.sh`
- Class: escape. Confidence: high (reproduced).
- Detection greps `/proc/*/environ` for `VACANT_RUN_ID=<run_id>` — an env var the
  agent itself can read. `setsid env -i bash -c 'sleep 5; echo ESCAPED > $PROJ/late.txt'`
  spawns a detached writer whose environ never contains the marker.
- Observed: `detached_processes: []`, `outside_changes: []`, exit 0 — and
  `late_env_i.txt` appears in the project ~1s after vacant exits. (`env -u
  VACANT_RUN_ID setsid …` and `unset VACANT_RUN_ID` inside a shell are
  equivalent evasions.)
- Control: plain `setsid bash -c 'sleep 30'` (marker intact) IS detected —
  `detached: [1639183]` + `WARNING: detached process(es)…` — so the mechanism
  works exactly when the adversary cooperates.

### R3 — B2 blind spot: the marker is only in the AGENT's env — a detached process spawned during acceptance has none
`findings/e3-b2-check-spawned.sh`
- Class: escape. Confidence: high (reproduced).
- `impl.py` (unprotected) does `subprocess.Popen(["setsid","bash","-c","sleep 8; echo CHECKSIDE > proj/late.txt"])`
  at import time. During baseline/acceptance the test runner imports it and the
  setsid child spawns — `_run_external_command`/python runners use
  `dict(os.environ)`/`_clean_env`, neither contains `VACANT_RUN_ID`.
- Observed: accepted, exit 0, `detached_processes: []`, `outside_changes: []`;
  `late_check.txt` lands ~4s after the run ends.
- Why it matters: even an agent that keeps the marker honestly can hide a
  post-delivery writer in the code the check executes — the fix only
  instruments one of the two code-execution phases.

### R4 — B1 listing gaps: `.git` outside hooks/config, any dir named `node_modules`/`.venv`/`__pycache__`/`.pytest_cache`
`findings/e4-b1-listing-gaps.sh`
- Class: escape. Confidence: high (reproduced).
- `_project_lstat_listing` records `.git/config` and `.git/hooks/**` only, and
  skips `node_modules`, `.venv`, `__pycache__`, `.pytest_cache` **at any depth**.
- Observed `outside_changes` after agent ran: only the contrast file
  `plain_escape.txt` was reported. Invisible: `.git/refs/heads/pwned-branch`
  (planted), `refs/heads/hijacked` (real `git update-ref` — silently moves a
  branch the user will check out), `.git/HEAD.evil`, freshly created
  `node_modules/evilpkg/{index.js,package.json}` (a `require('evilpkg')` stub
  that persists — the project's own code will run it later),
  `sub/lib/node_modules/dep2/index.js`, `tools/.venv/.../evil.pth`.
- Why it matters: the claim is "writes inside `.git` outside hooks/config" and
  COPY_SKIP-named dirs are covered — they are not. `.git/refs`, `.git/HEAD`,
  `.git/index`, `.git/packed-refs`, `.git/info/exclude` are exactly the places
  that change what the user's next `git` command does, and a `.pth` file in any
  `.venv` executes code at interpreter startup — all invisible to the receipt.
- Note: detection is report-only anyway (R10/R11), but here it isn't even
  reported.

### R5 — A3 still open: `--check` wrappers defeat first-word manifest pinning
`findings/e5-a3-check-wrap.sh`
- Class: accepted-but-wrong. Confidence: high (reproduced, all 4 variants).
- `_check_command_protections` maps only the first command word and protects
  root manifests. Four reproduced escapes, each ending `EXIT=0`, "acceptance
  passed", poisoned manifest delivered:
  | check | result |
  |---|---|
  | `sh -c 'npm test'` | `package.json` unprotected → `scripts.test:"true"` delivered; dep.js still buggy |
  | `env sh -c 'npm test'` | same |
  | `npm --prefix sub test` | root package.json pinned but `sub/package.json` rewritten → delivered |
  | `cd sub && npm test` | cmd0=`cd` → nothing protected → `sub/package.json:"true"` delivered |
- Also reasoned (same mechanism): `make -C dir`, `pnpm --dir`, `cargo test
  --manifest-path`, `timeout 300 npm test`, `sudo npm test`, `eval 'npm test'`,
  `bash -c`, `python3 -c "import verify"`, `--check 'bash $V'` (indirection via
  env var), Makefile `include other.mk` (only the named Makefile is protected).
- Why it matters: `sh -c '…'` is *the* natural way to write a `--check`, and npm
  workspaces/`--prefix` are standard monorepo usage — the most common check
  spellings still route around the fix.

### R6 — A1/A2 flagging gaps: root fixtures, `data/` dirs, transitive and dynamic imports are all unflagged
`findings/e6-a1-unflagged-deps.sh`
- Class: accepted-but-wrong. Confidence: high (reproduced, all 4 variants).
- The rc5 mitigation is only a *warning list* (`acceptance_dependencies_changed`;
  delivery proceeds regardless), and even the list misses:
  | poisoned oracle | accepted | flag list |
  |---|---|---|
  | `expected.txt` at project root (test reads it) | True | `[]` |
  | `data/expected.txt` (dir not in `{fixtures,testdata,test_data,__fixtures__}`) | True | `[]` |
  | `helpers2.py` (test → helpers → helpers2; only direct imports scanned) | True | `[]` |
  | `oracle.py` (`importlib.import_module`, `__import__`, `exec` — not AST) | True | `[]` |
- Same unflagged classes: jest `__mocks__/`, `mock/`, `stubs/`, `golden/` dirs;
  files read via `open()`/`pathlib.read_text` (non-import) anywhere;
  `jest.mock('./x')`, template-literal ``require(`./x`)``, TS path aliases
  (`@/x`), `require(path.join(__dirname,'x'))`; Go/Cargo non-test sources.
- Separately: the flag is **noisy by design** — every run flags the module under
  test (`the check depends on these files…: calc.py` fires on the legitimate
  fix in the smoke test), so the useful signal drowns in per-run noise.
- Why it matters: the simplest round-1 A1 attack (a data file at the project
  root or in `data/`) is still completely invisible — the flag only fires when
  the poison is in one of four blessed directory names or a direct import edge.

### R7 — NEW BUG: `--check './verify.sh'` dies at baseline (exec bit stripped on protected restore)
`findings/e7-exec-bit-protected.sh`
- Class: UX (regression). Confidence: high (reproduced).
- `verify.sh` (0755) is auto-protected (token scan — the A4 fix works), but
  `_restore_test_file` rewrites protected files with `os.chmod(f, 0o600)` — the
  exec bit is lost in the acceptance copy. `./verify.sh` → `Permission denied`
  → exit 126 → `_baseline_env_reason` misclassifies it as an environment
  problem:
  ```
  baseline: acceptance cannot run in this environment: /bin/sh: 1: ./verify.sh: Permission denied
  stopped before running the agent (0 attempts); project unchanged.   EXIT=43
  ```
- Control `--check 'bash verify.sh'` works (baseline FAIL → agent runs →
  PASS → delivered). Only direct-exec checks break — `./test.sh`,
  `./run_checks`, `make`'s scripts are unaffected but any `*-protected`
  executable invoked directly is.
- Why it matters: a brand-new false "your environment is broken" refusal on the
  most natural check spelling; introduced by the rc5 restore path.

### R8 — NEW BUG: killing vacant mid-run leaves the project's node_modules read-only
`findings/e8-nm-readonly-on-kill.sh`
- Class: data-loss-adjacent/environment damage. Confidence: high (reproduced).
- `_nm_make_readonly` chmods the ORIGINAL project `node_modules` (and root dir)
  during each attempt + each acceptance; `_nm_restore_modes` is a `finally` —
  SIGTERM/SIGKILL/OOM never runs it.
- Observed after `kill -TERM` during attempt 1 (exit 143):
  ```
  755→555 node_modules; 755→555 dep/; 644→444 dep/index.js
  ```
  Permanent read-only node_modules; the user's next `npm install`/test fails.
- Same exposure: `node_modules` being a symlink to a shared dir → the outside
  target is chmod'ed too.

### R9 — C1 not fully fixed: a non-UTF-8 **prompt** still suppresses the signed receipt
`findings/e9-c1-surrogate-prompt.sh`
- Class: receipt-integrity. Confidence: high (reproduced).
- Filenames are sanitized (`_safe_path_str`), but `request_sha256 =
  sha256(prompt.encode("utf-8"))` inside `_record_receipt`'s try still raises
  `UnicodeEncodeError` on a surrogate-escaped argv string
  (`--prompt $'bad\xffprompt'`).
- Observed: run delivered, `EXIT=0`, `receipt: {'recorded': False,
  'error': "UnicodeEncodeError: … surrogates not allowed"}`;
  `audit list --strict` shows the run as `unsigned` (GAPS 2) — no verifiable
  record of a run that modified the project. Same effect class as round-1 C1
  through a different unsanitized input.

### R10 — B3 defeated by an absolute symlink inside node_modules; acceptance executes the poisoned file
`findings/e10-b3-symlink-write-through.sh`
- Class: accepted-but-wrong + escape. Confidence: high (reproduced).
- `project/node_modules/mypkg → /abs/project/pkgsrc/mypkg` (the standard
  `workspace:`-style link). `cp -a`/`copytree(symlinks=True)` preserves the
  absolute symlink in the agent's copy → the agent writes through
  `ws/node_modules/mypkg/index.js` into the ORIGINAL project.
- Observed: `node_modules_changed: []` (manifest only watches inside nm), the
  acceptance (`npm test` → `require('mypkg')` → orig symlink → poisoned
  pkgsrc) PASSES, `accepted: True`, exit 0; `outside_changes:
  ['pkgsrc/mypkg/index.js']` — reported but **never reverted**; the poisoned
  file remains.
- Why it matters: the fix's own docstring promise — "never give the agent a
  writable path into the original project" — fails for absolute symlinks,
  which are routine in monorepo layouts. And the run is still accepted.

### R11 — Acceptance tests the LIVE project for unchanged paths; the simplest direct write still wins end-to-end
`findings/e11-acceptance-live-files.sh`
- Class: accepted-but-wrong. Confidence: high (reproduced).
- The agent writes `impl.py` directly to `proj/` (absolute path, touches
  nothing in ws). `_populate_acceptance_work` copies "before" files from the
  LIVE project for every path the plan doesn't write → the acceptance runs
  the poisoned file.
- Observed: `python_unittest PASS`, `accepted: True`, `0 added, 0 modified,
  0 deleted`, exit 0; `outside_changes: ['impl.py']` — reported, kept, never
  reverted. The docstring claim "acceptance tests exactly the files that will
  be written back" is false — it tests live project state for the
  unchanged-in-ws set.
- Why it matters: round-1's simplest escape (one `echo` to the real project)
  still produces a PASS on tampered content with the file left tampered;
  "reported" ≠ "safe".

### R12 — Files under dirs named `node_modules`/`.venv`/`.git`/`__pycache__`/`.pytest_cache` are silently dropped from delivery
`findings/e15-copskip-silent-drop.sh`
- Class: accepted-but-wrong/UX. Confidence: high (reproduced).
- Agent creates `vendor/node_modules/lib.js` + `sub/.venv/f.txt` in its
  workspace. COPY_SKIP matches by *name at any depth* in `_scan_files`,
  `_snapshot_workspace`, `copytree`. The files never reach the snapshot → not
  `added`, not `skipped`, no message.
- Observed: `changed: {'added': [], 'modified': ['calc.py'], 'skipped': []}`;
  delivered project lacks both files; exit 0, "delivered that attempt". Part of
  the agent's output silently vanishes.

### R13 — B3 fix cost: full node_modules hashing ×4+ per attempt and a full copy per attempt
`findings/e12-nm-perf.sh`
- Class: slowdown. Confidence: measured at small scale, reasoned extrapolation.
- 36MB / 3000 files: `node_modules_hash_s: 0.815`, `copy_s: 0.115` on a 1.2s
  run. The manifest is rebuilt at start + after every attempt + before/after
  every acceptance + at end (≈4 hashes/attempt) and the agent copy is a full
  `cp` (no reflink on /tmp). For a realistic 300MB–1GB / 50–200k-file
  node_modules expect ~10–60s of hashing per attempt and a multi-second copy —
  meaningful wall-clock on every attempt, and it counts against `--timeout`.
- Also: `cp --reflink=auto` failure is silent fallback to `copytree` — no
  warning that the attempt just got much slower.

---

## What I tried that held up (confirmed fixed)

- **C1 filename case** (`findings/c1-fixed-checks.sh` a): `bad-\udcff-name.txt`
  delivered, `receipt: {'recorded': True, …}`, `non_utf8_paths: True`,
  `audit list --strict` → `verified yes`. Fixed.
- **B1 `.git/hooks`** (c1-fixed-checks b): planted `post-commit` → `changed in
  your project outside the delivered attempt: .git/hooks/post-commit` +
  `WARNING: .git/hooks was added or changed…`. Detected (report-only).
- **D3 concurrent file** (c1-fixed-checks c): mid-run `userfile.txt` →
  `appeared during run (not deleted)` — kept, reported. Fixed.
- **D3 conflict** (`findings/e16-d3-conflict.sh`): user's mid-run edit of
  `shared.py` → `conflict … kept your version` — file still `X=99`. Works.
- **D1** (c1-fixed-checks d): read-only project root → exit 43, clear message,
  no agent run.
- **D2** (c1-fixed-checks e): run from `proj/pkg` → `tests found in
  <parent>; run from there to check them` + `scanned: <subdir> (parent
  directories were not scanned)`. Honest now.
- **B3 same-size write + mtime restore** (`projects/e13-b3samesize`): sha256
  manifest catches it → `node_modules_modified`, run stops, nothing written
  back, exit 43, honest "reinstall node_modules" message.
- **B2 with marker intact** (`projects/e14-b2control`): `setsid bash -c
  'sleep 30'` → `detached_processes: [pid]` + WARNING. Detection works when
  the marker survives.
- **A3 base case**: `--check 'npm test'` pins + protects root package.json;
  `--check 'bash verify.sh'` auto-protects `verify.sh` (e7 control);
  `make` → Makefile variants mapped.
- **Exec preservation**: non-protected files keep exec bit in the acceptance
  copy (`preserve_exec` / snap modes 0700).
- **Delivery policy**: unchanged — first accepted attempt delivered; on all-fail
  the best-scoring (last for exit-code kinds); write-back happens on reject
  too (attempt N's diff); exit codes 0/40/43 as documented.

## What I could not test

- pytest acceptance (`python_pytest`), cargo, go — binaries absent.
- Non-Linux behavior (`/proc` scan is Linux-only by design).
- Write-back plan→apply TOCTOU under races (window is sub-ms; reasoned only:
  `dst_sha`/`live_sha` are read at plan time and not re-verified before
  `os.replace`, so a same-instant concurrent edit between plan and apply can
  still be overwritten).
- `env -u VACANT_RUN_ID setsid …` variant flaked in the repro (the `env -i`
  path proves the same point).
- Whether the agent, given the copied verifier key, can produce a *well-formed*
  forged receipt end-to-end (the key material and the canonicalization code
  are both inside the workspace copy — only the mechanics of running
  `vacant_network` from source stand in the way).

## Notes on delivery policy & exit codes (checked, unchanged)

- Delivered attempt = first `accept=True`, else max `passed` (ties → latest;
  exit-code kinds have `passed=None` → latest). Write-back of that attempt's
  diff happens even on reject (exit 40).
- Exit codes: 0 accepted or uncheckable; 40 not accepted; 43 for
  `baseline_error`, `agent_error`, `node_modules_changed`,
  `project_not_writable`. `outside_changes`, `appeared_during_run`,
  `conflicts`, `detached_processes`, `acceptance_dependencies_changed` are all
  report-only and never change the exit code — even when they describe
  detected tampering that the acceptance itself consumed (R10/R11).
