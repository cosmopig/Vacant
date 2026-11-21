# vacant `do` (restart mode) — adversarial review, round 3 / final (rc5)

Scope this round: only (a) accepted-but-wrong with **no** warning, (b) silent damage to
user files not listed in message/receipt, (c) receipt failure (missing / forged /
altered-but-verifying). Repros in `findings/r*.sh`; fresh `VACANT_HOME`/`VACANT_WORK`
per run. All findings **reproduced live** on `venv/bin/vacant` 0.9.2 (Linux, node 22,
npm 10, git, make; no pytest/cargo/go).

---

## Findings

### F1 — npm acceptance pins *which script*, not *which file it runs* — 5 variants, all silent
Classes: (a). Confidence: high (all reproduced, exit 0, no warning).

The common mechanism: rc5 protects **manifests and test-named files**, but nothing that
pins the *files the pinned command actually resolves to*. Each variant ends:
`baseline: FAIL → attempt 1: PASS → "acceptance passed … delivered"` with the poisoned
file written back and **zero** warning lines.

| repro | variant | poisoned file | result |
|---|---|---|---|
| `r1-npm-script-target.sh` | auto `npm` kind, `scripts.test: "node verify.js"` | `verify.js` (not `*.test.*` → unprotected, unflagged) | `verify.js → process.exit(0)` delivered; dep.js still buggy |
| `r9-npm-workspace-subpkg.sh` | auto `npm` kind + workspaces, `scripts.test: "npm --prefix sub test"` | `sub/package.json` (only root `package.json` is protected/pinned for kind=npm) | `sub/package.json → "test":"true"` delivered; `sub/real.test.js` was protected but never ran |
| `r3-check-if-npm.sh` | `--check 'if true; then npm test; fi'`, `( npm test )`, `echo … \| xargs npm test` | `package.json` — `if/then`, subshell parens, `xargs` are not in the cmd-word unwrap table → npm not detected → manifest neither protected nor pinned | `package.json → "test":"true"` delivered, 3/3 |
| `r3b-check-make-npm.sh` | `--check 'make test'`, recipe `npm test` | `package.json` — `make` maps to Makefile/*.mk only | `package.json → "test":"true"` delivered |
| `r2-check-module-m.sh` | `--check 'python3 -m verify'` | `verify.py` — a `-m MODULE` token is not a file path → not protected | `verify.py → sys.exit(0)` delivered |

Why nothing warns: the only mitigations are (i) file protection (restored before check)
and (ii) `acceptance_dependencies_changed` — which is computed only from literals /
imports / fixture-dir membership of **protected** files. A manifest's script target,
a `-m` module name, or a manifest reached through a recipe are all outside that model.
`package.json` is explicitly excluded from literal scanning, so even the flag can't see
`sub/package.json` through the pinned root script.

Also reasoned (same code path, no binaries here to demo): `--check 'mvn test'` →
`pom.xml`, `gradle test` → `build.gradle`, `rake test` → `Rakefile`, `composer test` →
`composer.json`, `mix test` → `mix.exs`, `python3 -c '…'` / `node -e '…'` inline code
referencing project files — none of these cmd words or tokens map to a manifest/file in
`_CHECK_MANIFEST_BY_CMD`, so the harness stays unprotected.

### F2 — Unquoted file references in a protected `.sh` check are invisible to the flagger
`r7-check-created-harness.sh` (variant B). Class: (a). Confidence: high.

`--check 'bash verify.sh'`: `verify.sh` is protected and restored — but it runs
`diff -q - expected.txt` with `expected.txt` **unquoted**. `_extract_string_literals`
only collects *quoted* literals, and `expected.txt` sits at the project root (not a
fixture dir). The agent writes `41` into `expected.txt` → diff passes → PASS →
`expected.txt` delivered; message shows `protected: test_keep.py, verify.sh` and no
dependency flag. This is round-1 A1's mechanism still open through the unquoted-literal
gap (`. ./helper.sh`, `source cfg`, `diff expected.txt …`, `cat $f`-free unquoted args
all miss the flag).

### F3 — `.git/objects/**` writes and deletions are invisible; repository damaged silently
`r4-git-objects.sh`. Class: (b). Confidence: high.

`_project_lstat_listing` covers all of `.git` **except** `.git/objects/` (deliberate
skip). The agent — via a plain absolute-path write during its attempt — planted
`.git/objects/info/alternates` (points git's object lookup at a foreign dir),
`.git/objects/info/grafts`, `.git/objects/pack/pack-evil.pack`, and **deleted a real
loose object**. Result:

```
[vacant] acceptance passed on attempt 1 … delivered that attempt. 0 added, 1 modified, 0 deleted.
outside_changes: []          receipt recorded: True          EXIT=0
git fsck: missing blob 336a6c…   error: unable to normalize alternate object path
```

The message and the signed receipt report *nothing* — `objects/info/*` files change what
every future `git` command resolves (and `grafts` rewrites visible history), a dropped
loose object corrupts the repo, and a planted pack injects objects. None of it is
listed, reverted, or counted.

### F4 — Agent suppresses its signed receipt by chmod'ing `$VACANT_HOME`; run still exits 0 silently
`r5-receipt-chmod.sh`. Class: (c). Confidence: high.

`_record_receipt` is fail-open (`except Exception → {"recorded": False}`), and
`summary()` never mentions the receipt. The agent `chmod -R 0500 $VACANT_HOME` during
its attempt → append fails with `PermissionError` →

```
[vacant] acceptance passed on attempt 1 … delivered that attempt. 0 added, 1 modified, 0 deleted.
EXIT=0      receipt: {'recorded': False, 'error': 'PermissionError … trace'}
audit list --strict → restart:… accepted 0 unsigned 2 gaps   STRICT_EXIT=0
```

A run that modified the project has **no signed receipt**, and `--strict` still exits 0
(strict only fails on bad signatures; unsigned records need `--require-signed`). The
message gives no indication the audit trail is missing.

### F5 — The verifier key is readable by the agent → forged `restart_receipt`s verify under `--strict`
`r6-receipt-forge.sh`. Class: (c). Confidence: high.

The signature only proves the *key* signed — and the key is
`$VACANT_HOME/intake/keys/verifier/identity.key`, world-readable by any process running
as the user, including the agent. After a **rejected** run (exit 40) the demo calls
`Recorder(project).append("restart_receipt", {…accepted: true…})` with the venv's own
`vacant_network`:

```
restart:restart-FORGED  restart  generic  1 accepted  0 yes  1 gap   STRICT_EXIT=0
restart:restart-…e0eecf restart  generic  1 rejected  0 yes  0 gaps
```

The forged "accepted" receipt is chain-linked and signature-**verified**. (The R1 fix
only stopped *copying* keys into the workspace — the agent reads them directly; and any
user process can do this without ever running the agent.)

---

## Attacks tried that held (confirmed fixed / refused)

- `--check 'bash verify.sh'` with a **missing** verify.sh → baseline 127 →
  `baseline_error`, exit 43, nothing run (`r7` variant A). Correct.
- `--check './verify.sh'` exec bit preserved on protected restore → baseline runs,
  reject → exit 40 (round-2 R7 fixed).
- Legit unittest fix accepted (exit 0, file fixed); no-tests project → honest
  "nothing checked" (exit 0); agent flips test assert → restored → exit 40, original
  intact.
- Round-2-listed behaviors re-verified structurally: `sh -c`/`env`/`timeout`/`cd`/
  `eval`/`sudo`/`nohup`/`time`/`exec`/`command`/`setsid` unwrapping works — the F1
  variants all route through keywords/tools that remain unmapped (`if`, `( )`, `xargs`,
  `find -exec`, `make`'s recipe internals, `-m` module names).
- `.git` outside `objects/` (refs, HEAD, packed-refs, hooks, config, index) is in the
  lstat listing now; `outside_changes` would list them. `objects/` is the hole.

## Could not test (time/tooling)

- pytest acceptance (`python_pytest`), cargo, go — binaries absent.
- Detached-process escape past the final reap pass (the 5-pass/0.03 s window + post-
  delivery writes): timing-sensitive; the docstring already admits late writes aren't
  recorded, and any detected detached PID is warned — left as a residual race, not
  demonstrated.
- Plan→apply TOCTOU on paths *not* covered by the live-sha re-check (e.g. a directory
  swapped between `_plan_write_back` and `_apply_write_plan` mid-apply): sub-ms window,
  reasoned only.
- Whether `audit list --strict` would flag a forged receipt that *also* has a matching
  doctored `result.json` (gap fields are warnings, not signature failures — likely still
  verifies).
- Non-Linux platform behavior.

## Regression check (`r8-regression.sh`)

Legit fix → accept; `./verify.sh` exec check → reject 40; no-tests → honest exit 0;
test tamper → reject 40. Ordinary use is intact — no new crashes or wrong refusals seen.
