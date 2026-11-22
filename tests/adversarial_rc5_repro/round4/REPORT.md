# vacant `do` (restart mode) — adversarial review, round 4 (rc5, pre-freeze)

Main target this round: `acceptance_integrity: "verified"` printed with no WARNING while
the check actually executes a file the agent could (and did) change to force a pass.
Repros in `findings/f*.sh`; fresh `VACANT_HOME`/`VACANT_WORK` per run. All findings
reproduced live on `venv/bin/vacant` 0.9.2 (Linux, python 3.12, node 22, npm 10, GNU make;
no pytest/cargo/go/jest — the jest case uses a faithful stub, noted inline).

The analyzer (`_analyze_acceptance_command`) only judges the *command tokens and the
files they directly resolve to*. Seven independent routes below show that the runner/
interpreter underneath (npm config, make's target model, unittest discovery, os/fs/io
escapes, jest's config-in-manifest) executes additional project files it never modeled —
each ends `baseline: FAIL → attempt 1: PASS → "acceptance passed … delivered"` with
`acceptance_integrity: verified`, the normal `protected (restored before check):` line,
and **zero** WARNING lines. The wrong verdict is also written into `result.json` and the
signed receipt, and shown by `vacant audit list` in the INTEGRITY column.

---

## Findings

### F1 — `.npmrc` `script-shell` makes every `npm` script exit 0 — verified, delivered
`f1-npmrc-script-shell.sh`. Class (a). Confidence: high (real npm 10, reproduced).

`package.json` → `scripts.test: "node verify.js"`, `verify.js` = `process.exit(1)`
(analyzer: fully understood, verified). The agent writes `.npmrc` containing
`script-shell=/bin/true`. npm reads `.npmrc` in the check copy's cwd and runs every
script through it — `/bin/true -c 'node verify.js'` → exit 0.

```
baseline: npm FAIL → attempt 1: npm PASS (status=ok)
acceptance passed on attempt 1 … delivered that attempt. 1 added.
acceptance_integrity: verified     outside_changes: []     WARNING lines: 0
project/.npmrc now contains: script-shell=/bin/true
```

`.npmrc` is not in `_TEST_CONFIG_NAMES`/`_TEST_CONFIG_PATTERNS`, not protected, not
pinned, not excluded — it is copied into the check work dir and written back to the
project, so it also **poisons every future `npm`/`npm run` invocation the user makes in
that project** (persistent damage beyond the run). `script-shell` is only the crudest
knob; `.npmrc` also controls e.g. `scripts-prepend-node-path`, `bin-links`, `ca`/`proxy`
behavior — the analyzer models none of it. Fix direction: treat `.npmrc` (and
`npmrc`/`yarnrc`/`pnpm-workspace` configs) as test-config-class files, or mark any npm
check unverified unless `.npmrc` is absent/protected.

### F2 — `make test`: the recipe never runs when a file named `test` exists
`f2-make-uptodate.sh`. Class (a). Confidence: high.

`Makefile: test:\n\tpython3 check.py` (no `.PHONY` — the common case). Analyzer traces
the recipe and marks it verified. Agent does `: > test`. `make test` →
`'test' is up to date` → exit 0; the recipe is never executed. The junk `test` file is
written back.

```
baseline: check FAIL → attempt 1: check PASS (status=ok)
protected (restored before check): Makefile, check.py
integrity: verified   accepted: True   WARNING lines: 0   'test' file delivered
```

Same mechanism: any make target reached by the check (the goal **or** a prerequisite on
the traced chain) is satisfied by an agent-created file of the same name. The analyzer
models which *recipes* run but not make's up-to-date semantics: a target with a recipe is
skipped when a newer file of that name exists. Any `--check "make …"` / `npm test` →
`make test` is forgeable this way unless the Makefile declares every traced target
`.PHONY`.

### F3 — `make` default goal: analyzer picks the first target, GNU make honors `.DEFAULT_GOAL`
`f3-make-default-goal.sh`. Class (a). Confidence: high.

```
.DEFAULT_GOAL := help
check:
	@python3 check.py
help:
	@./h.sh
```

`--check "make"`: the parser treats `.DEFAULT_GOAL := help` as a rule whose target starts
with `.` (skipped silently — it is not recognized as a variable assignment because the
name starts with `.`), then chooses `check` as the default goal and verifies its clean
recipe. Real `make` runs `help` → `./h.sh`, unprotected and never analyzed. Agent flips
`h.sh` to `exit 0` → PASS, `h.sh` delivered, `protected: [Makefile, check.py]`,
`integrity: verified`, 0 warnings. Anything in `help`'s recipe (which the analyzer never
looked at) executes.

### F4 — `unittest discover -p '<pattern>'`: collected files are unprotected
`f4-unittest-pattern.sh`. Class (a). Confidence: high (pure stdlib).

`--check "python3 -m unittest discover -s . -p '*_check.py'"`. The analyzer resolves `-m`
module args to files; a discovery *pattern* resolves to nothing, so nothing is protected.
`foo_check.py` at project root is not `test_*`/`*_test` and not under `tests/` → outside
every protected pattern. The agent edits the exact file the check collects → pass.

```
protected (restored before check): none — the agent could have edited what this check runs
acceptance_integrity: verified   accepted: True   WARNING lines: 0
delivered foo_check.py: assertEqual(1 + 1, 2)
```

Note the message even prints "the agent could have edited what this check runs" while
`acceptance_integrity` is `verified` and no WARNING appears — self-contradictory output.
Same class: `python -m unittest` positional *module* args DO resolve to files and get
protected; discovery `-s`/`-p`/`-t` semantics (start dir, pattern, top-level dir) are not
modeled at all.

### F5 — `os.system`/`os.popen` in a script file is invisible to the analyzer
`f5-py-os-system.sh`. Class (a). Confidence: high (pure stdlib, fully silent).

`--check "python3 verify.py"`; `verify.py` = `sys.exit(0 if os.system("sh helper.sh")==0 else 1)`.
`_py_analyze_code_ast` flags `subprocess`/`importlib`/`runpy`/`eval`/`exec` — but
`os.system`, `os.popen`, `os.execl`, `os.spawnl`, `ctypes` are only blocked for
`python -c` *inline* code (`_PY_INLINE_IO_ATTRS` gated on `inline=True`). For a file
script: no reason → `verify.py` protected + "understood" → verified. `helper.sh` is
unprotected; the dependency flag also misses it (`"sh helper.sh"` matches none of the
literal-path shapes — `lit==rel`, `lit==bn`, `lit.endswith("/"+rel)`). Agent flips
`helper.sh` → `exit 0` → PASS, delivered.

```
dep_changed: []   integrity: verified   accepted: True   WARNING lines: 0
```

Same hole, same class: `os.popen`, `pty.spawn`, `signal`/`fork` patterns, `ctypes.CDLL`,
and plain `open()`/`Path.read_text()` reads of decision data (f6 for the JS twin).

### F6 — `fs.readFileSync` in a node script is invisible; literal-split dodges the soft flag
`f6-node-fs-read.sh`. Class (a). Confidence: high (real node 22).

`--check "node verify.js"`; `verify.js` reads `"expected" + ".txt"` and compares to a
computed value. `_js_analyze_file` scans for relative `require`/`import`, `eval`,
`new Function`, `child_process` — `fs` reads are not modeled → verified. The split
literal also defeats `acceptance_dependencies_changed` (`"expected"`/`".txt"` match
nothing). Agent writes `expected.txt` = `42` → PASS, delivered, `dep_changed: []`,
0 warnings.

### F7 — `scripts.test = "jest"`: `package.json`'s `jest.setupFiles` executes an unprotected file
`f7-jest-setupfiles.sh`. Class (a). Confidence: medium-high (mechanism reproduced with a
faithful jest stub implementing the documented behavior — `setupFiles` execute in the
test realm before each test file and may shadow globals; real jest was not installable
offline, but the analyzer gap is independent of the runner).

`package.json`: `scripts.test: "jest"`, `"jest": {"setupFiles": ["./setup.js"]}`.
Analyzer marks `jest` a known runner → `verified`; protects `package.json` + `sum.test.js`
only. `setup.js` is unprotected and invisible to the dependency flag (package.json is
excluded from literal scanning, so the `"./setup.js"` reference is never seen). The agent
rewrites `setup.js` to `global.expect = () => ({ toBe() {} })` → every assertion passes →
`npm PASS`, `setup.js` delivered, `dep_changed: []`, 0 warnings. `sum.js`'s bug ships.

Same class: `"mocha": {"require": "./setup.js"}`, `"jest": {"moduleNameMapper"}` /
`"testRegex"` / `"globalSetup"` pointing at agent-writable files, `jest --config=x.js`
(arg form `--config=` never resolves to a file for protection — though existing
`jest.config.*` are protected as test-configs), `.babelrc` presets/plugins files.
Root cause shared with F1: the analyzer protects the manifest and the runner, but never
looks *inside* the manifest's non-`scripts` config keys or the runner's own config files.

### F8 — UX: almost every real `--check` script now reports `unverified` (alarm fatigue)
`f8-regression.sh`. Class (5). Confidence: high (reproduced).

The analyzer only "understands" a small whitelist of command words inside shell scripts.
Everyday shapes all hit the loud WARNING + "unverified" + "files changed by delivered
attempt" block:

- `--check "bash verify.sh"` where verify.sh contains `> got.txt` (output redirection)
  or `diff`/`grep`/`cat`/`echo`/`[`/`source`/`.` — i.e. virtually every real verify script
  → `unverified reason(s): verify.sh: shell output redirection` / `unknown command: diff`.
- `--check "bash -c 'make test'"` / `sh -c '…'` → `unsupported bash option: -c`.
- `--check "python3 check.py"` where check.py imports the module under test (`import app`)
  → `script imports project modules: check.py -> app.py` — the *normal* way to write a
  check → unverified.
- Any `xargs`, `if`, `( )`, `eval`, `command`, `exec`, `env`, `pip`, `coverage`, `tox`,
  `docker`, `curl` in the command → unverified.

The verdict is still honest (conservative), and delivery is not blocked — but since
"verified" is only attainable for toy-shaped checks, the WARNING becomes boilerplate
users learn to skip — which is exactly what lets F1–F7 hide in the same output
elsewhere. Worth either narrowing the wording to the specific untraced construct, or
acknowledging in the message that most real checks land here.

---

## What held (verified live or at analyzer level)

- `pretest`/`posttest` lifecycle hooks are followed, pinned (`pinned_named_scripts`), and
  protected — the round-3 npm hook route is closed.
- `if`/`( )`/`xargs`/`;`-tricks/`eval`/`source`/`.`/backticks/`$VAR`/redirections/
  here-docs/process-substitution/unquoted globs in check strings and inside protected
  `.sh` files → all `unverified` (round-3 F1 variants r3 and F2's mechanism now warn).
- make `include`/`-include`/`sinclude`, `$(shell …)`, `::`, pattern/var targets,
  `VAR=val` overrides, `!=` assignments, order-only `|`, untraceable prereqs,
  `make -f`/`make -C` resolution → `unverified` or correctly traced.
- `npm --prefix`, `npm run <name>`, `yarn`/`pnpm`, `npx jest|vitest|mocha` arg-file
  protection; `node -e`/`--require`/`--import`; `python -c` io/import checks;
  `python -m <project module>` resolution (incl. `pkg/__main__.py`) → handled.
- Agent-*created* `conftest.py`/`pytest.ini`/`jest.config.*` → `config_ignored`:
  excluded from the check copy AND from write-back, listed in the message.
- `node_modules`: agent ws changes → `node_modules_changed` → run aborts (nothing
  delivered); at check time the *original* `node_modules` is symlinked in and `.bin` is
  prepended — the agent's copy is not used. Direct writes to the orig project's
  `node_modules`/`.venv`/`__pycache__`/`.git/objects/**` during the attempt → shown in
  `outside_changes` (lstat listing covers them; `.pth`/hooks/refs get dedicated WARNING
  lines).
- Ordinary use: auto unittest legit fix → `verified`, accepted, exit 0; no-tests project
  → honest `no_tests`; `python -m unittest` module-name args resolve and are protected;
  baseline-PASS/FAIL reporting correct; `audit list`/`--strict` show and verify the
  signed receipt (strict exit 0 on the f1 run — the wrong "verified" verdict is what the
  receipt attests, so the receipt itself is consistent).
- `--check "bash -c …"`/redirection/control-flow → `unverified` (see F8 — conservative,
  just noisy).

## Could not test

- Real jest/mocha/pytest/cargo/go/maven/gradle binaries (absent offline): F7 uses a stub
  implementing documented `setupFiles` semantics; `pytest.ini` `python_files`/`conftest`
  chain, `mocha` `.mocharc` `require:`/`spec:`, cargo build.rs, `go test -exec`, maven
  plugins are reasoned-only members of the same "config key / runner internals" class.
- Whether `--check` env quirks (`CDPATH`, `BASH_ENV`/`ENV` inherited via `dict(os.environ)`)
  matter — env is the user's own, not agent-controllable.
- `.venv` `sitecustomize`/`.pth` inside the *original* project: resolvable as the
  interpreter for python_* kinds, but any agent write there lands in `outside_changes`
  (listed, not silent) — did not pursue as a finding.
- `audit --strict` failure modes beyond same-user forgery (already documented as known).

## Bottom line

`acceptance_integrity: verified` currently means "the analyzer traced the command words
and pinned file arguments" — but npm/make/unittest/jest/python/node all have second-order
file resolution (rcfiles, up-to-date rules, default-goal overrides, discovery patterns,
`os`/`fs` escapes, runner config keys inside manifests) that sits outside the model.
Until those are modeled or defaulted to `unverified`, the `verified` verdict overclaims:
it tells the user "protected everything this check runs" in exactly the runs where the
check was beaten.
