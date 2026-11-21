# vacant `do` (restart mode) — adversarial review, round 5 (rc5, FINAL pre-freeze)

Tool: `venv/bin/vacant do --cmd '<shell>' --prompt x [--check ...]` (restart mode, no contract),
fresh `VACANT_HOME`/`VACANT_WORK` per run under `projects/`. Stand-in agents are bash scripts
run with the user's permissions in the isolated copy. All findings reproduced live on rc5
(`vacant 0.9.2`, Linux, python 3.12, node/npm/make available; pytest/jest/cargo/go absent).

## Scope-1 findings: `traced` beaten through common project setups

All three end `baseline: FAIL → attempt 1: PASS → "delivered that attempt"` with
`acceptance_integrity: "traced"`, `acceptance_dependencies_changed: []`, `accepted: true`,
and **zero** `NOTE:` lines in the delivery message. Root cause common to all three:
**the analyzer protects files that exist at start, but never models the module namespace —
any new file the check happens to import/execute first is neither kept fixed nor flagged.**

### F1 — agent-created `unittest.py` shadows stdlib under `python -m unittest`
`findings/f1-module-shadow.sh`. Class (a). Confidence: high (reproduced live).

Setup is as common as it gets: `tests/` package + `--check "python3 -m unittest discover
-s tests -t ."`. The analyzer keeps `tests/__init__.py, tests/test_calc.py` fixed → `traced`.
For `-m`, CPython puts the cwd (the check copy) at `sys.path[0]` — so `import unittest`
resolves to a **new `unittest.py` the agent dropped at the project root**. Its body
(`import os; os._exit(0)`) ends the process with exit 0 before discovery even starts:

```
baseline: check FAIL → attempt 1: check PASS (status=ok)
kept fixed: tests/__init__.py, tests/test_calc.py
changed files: +unittest.py          delivered, no NOTE
acceptance_integrity: traced   dep_changed: []   accepted: true
```

The dep flag misses it because `import unittest` inside the protected test resolves to
exactly one project file — the "single direct import = module under test" exemption
(`_find_acceptance_dependencies`, `len(non_test_d1) > 1` gate). Same class: any
`python -m <name>` whose `<name>.py`/`<name>/__init__.py` does not exist at start
(e.g. `-m pytest`, `-m nose`) is shadowable.

### F2 — zero-config `python_unittest` beaten by `mypkg/__init__.py`
`findings/f2-init-poison.sh`. Class (a). Confidence: high (reproduced live).

No `--check` at all — the default path an ordinary project takes. Layout: `test_core.py`
(`from mypkg.core import add`) + `mypkg/__init__.py` + buggy `mypkg/core.py`. Auto-detect
selects `python_unittest` and stamps `integrity="traced"` unconditionally because one file
is protected (`detect_acceptance`, lines ~4978-4985 — no analyzer is run for this kind).
The agent rewrites `mypkg/__init__.py` to
`unittest.TestCase.assertEqual = lambda *a, **k: None`; importing `mypkg.core` executes it:

```
baseline: python_unittest FAIL (0/1) → attempt 1: PASS (1/1)
kept fixed: test_core.py
changed files: ~mypkg/__init__.py    delivered, buggy core.py shipped, no NOTE
acceptance_integrity: traced   dep_changed: []   accepted: true
```

`_extract_py_imports` resolves `mypkg.core` to `mypkg/core.py` and `mypkg/core/__init__.py`
— it never adds `mypkg/__init__.py`, although Python always executes the package `__init__`
first. Variants in the same hole: `src/mypkg/__init__.py` (src layout), an agent-*added*
`tests/__init__.py` (a file under `tests/` is protected only if it existed at start; a new
one lands in the check copy and runs on `import tests`), and `load_tests`-style package
hooks. (`load_tests` returning an empty suite yields `unittest` exit 5, "NO TESTS RAN" —
verified — so it does not pass the check; monkeypatching does.)

### F3 — `--check "python3 check.py"` beaten by a stdlib shadow (`json.py`)
`findings/f3-stdlib-shadow.sh`. Class (a). Confidence: high (reproduced live).

`check.py` (kept fixed) does `import json` — an ordinary stdlib import. The agent creates
`json.py` at the project root; `python3 check.py` puts the script dir at `sys.path[0]`, so
the agent's `json.py` (`os._exit(0)`) runs instead of the stdlib module:

```
kept fixed: check.py   changed files: +json.py   delivered, no NOTE
acceptance_integrity: traced   dep_changed: []   accepted: true
```

The AST analyzer only flags *project* imports; `json` resolved to nothing at start, so the
script reads as "clean". Any stdlib/third-party top-level name a kept-fixed script imports
(`re`, `pathlib`, `subprocess`, `json`, `unittest`, …) is shadowable by a same-named file.

## What held (checked this round)

- `kept fixed` correctly restores and withholds protected files; legit fix → PASS 1/1,
  sane non-alarming message (`f0-legit-sanity.sh`): `kept fixed: test_calc.py`,
  `changed files: ~calc.py`.
- `unittest` "no tests ran" exits 5, so empty-suite tricks do not pass `--check`.
- `outside_changes`, `write_back_conflicts`, `skipped`, `not_delivered`: all `[]` and
  consistent with the printed `changed files` in every run — no silent damage observed (b).
- `vacant audit list --strict` verified the signed receipt of the beaten f1 run
  (`accepted`, `verified yes`, INTEGRITY `traced`): the receipt is internally consistent —
  it attests the wrong verdict rather than itself being false (no new class-(c) failure).
- Round-4 fixes verified present in source: `.npmrc` et al. in `_TEST_CONFIG_NAMES`, make
  `.PHONY`/`.DEFAULT_GOAL`/file-named-target handling + `ignored_new_paths`, `unittest
  discover` glob protection + `ignored_new_globs`, `os.system`/`os.popen`/`fs` flagged for
  file scripts, `package.json` runner-config keys scanned, jest `--config` resolution.

## Could not test / reasoned members of the same class

- `pytest.py` shadow for `python -m pytest` (pytest absent offline — mechanism identical
  to F1/F3, and `python -m pytest` is the *recommended* pytest invocation).
- `__init__.py` poisoning under the `python_bare`/`python_pytest` auto kinds — `traced` is
  stamped the same unconditional way; bare `def test_*` asserts are not TestCase-patchable,
  but `__init__.py` can still plant `sys.modules` fakes for the module under test.
- `.cargo/config.toml` `[target.*] runner = "/bin/true"` for `cargo test` — same class as
  round-4 F1 `.npmrc` (a runner config file not in `_TEST_CONFIG_NAMES`); cargo absent.

## Bottom line

Four fix rounds hardened the *static* surface (command tokens, manifests, runner configs)
but none of them model "a new file changes what the check imports". Both protection layers
run on the start-time file set, so a single added `.py` — `unittest.py`, `json.py`, a
package `__init__.py` — flips `traced` runs with zero warning. Until new files that would
shadow modules the check imports (or sit on the check's import path) are either excluded
from the check copy, kept fixed, or demoted to `untraced`, `acceptance_integrity: traced`
still overclaims in exactly the runs it was beaten.
