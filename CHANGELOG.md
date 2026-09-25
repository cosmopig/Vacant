# Changelog

## Unreleased

**Accountable trace: who did what, which step put the wrong value in, and the problem is raised
instead of drowned.** Decision: `decisions/DECISION_20260924_ACCOUNTABLE_TRACE.md`.

- New `vacant_network.trace`: every tool call of pi, Claude Code, OpenCode and Codex is recorded
  into one signed chain per project (actor incl. sub-agents, tool, input, output, and the files the
  step changed — from Vacant's own before/after view of the workspace, so shell writes count);
  changes no step explains are recorded as accountability gaps, never blamed on anyone.
- When a check fails: locate (file, line, value) → the step that introduced it → re-run the same
  check on the rebuilt before/after states (`provable`) → where the value came from (input,
  sub-agent reply, command output, a script the agent wrote, a web page, the task message).
  Two layers (fact / inference), five grades, seven fault classes.
- The end-of-turn feedback now names the location, the expected value and the step where the value
  first appeared, with no actor in it (`feedback_ks1_clean`, executable). When the agent will not be
  asked to continue, open issues go to the human (Claude Code `systemMessage`, a report under
  `$VACANT_HOME/trace/`, `vacant trace report`). `vacant flag` lets a person point at a wrong place.
- Consequences are events and reputation is replayed from them: only `provable` findings touch an
  actor (no slash; `vacant flag --dismiss` reverses exactly), input faults are tallied on the source,
  gaps on the platform integration. Routing is advice to the human and `vacant do --agent auto`.
- `vacant do --feedback-mode localized|generic|none` and `ops/accountability/r536/` (bank, runner,
  analysis) for the preregistered real-model experiment (draft, awaiting sign-off).
- Evidence (L-fake, four real agents × six planted faults, one of them a sub-agent that computes
  the wrong value which the main agent copies, one a wrong web page fetched with `curl`): 24/24 attributions, the sub-agent case pointing at
  the sub-agent's own step on all four agents, `ops/accountability/evidence_20260924/`. pi has no
  built-in sub-agents; a pi process started by an extension during a tool call is now recognised
  as a sub-agent of that session (it was treated as a second main agent and asked, at its own
  turn end, for the parent's deliverable). A value that came from `curl`/`wget` output is traced to the
  URL as an outside source (it was blamed on the agent as "the command produced it").
- While a background sub-agent is still working (Claude Code's default), the end-of-turn check waits:
  it used to push the main agent to redo the sub-agent's work. `SubagentStart` is now installed for
  Claude Code and Codex. End to end: 25/25, including Claude's background sub-agent.
- A human flag (`vacant flag file:line "what is wrong"`) on something no check covers now has an
  end-to-end run on all four agents: it reaches the agent at the next session's turn end even though
  the contract passes, it points at the step that wrote the line, and it resolves once the line
  changes. The note is shown as the owner's words, not as a check's. End to end: 29/29.
- Parallel delegation: a delegation call that finished first used to take a sibling sub-agent's
  in-flight write as its own; a delegation call never writes files itself, so a file version that a
  real step wrote is credited to that step. End to end on all four agents: 33/33.
- Review of the last two changes (8 findings, `ops/accountability/review_defer_credit/FINDINGS.md`):
  a session end now clears sub-agents that never reported; a deferred check voids the session's
  earlier outcome; at most 3 consecutive deferrals; a turn end settles only the actor's own steps;
  delegated writes are credited only to a later step with the identical before/after change;
  flags reach the agent only with a valid owner signature (a sub-agent could inject text as the owner).
- Interactive use: the feedback-round cap now applies per request the person types, not per session.
  In a multi-turn TUI session a question asked first could use up the rounds, and the wrong value
  written after the next request then got no located feedback (reproduced as a negative control in
  Claude Code's TUI). Messages the person did not type (a background sub-agent's result, a parent's
  task for a sub-agent, Vacant's own feedback echoed back) do not reset it. OpenCode's plugin does not
  see prompts, so there the cap still resets only on a pass.
- New `ops/accountability/e2e_tui.py`: the four agents' real TUIs driven in tmux like a person would
  (type, Enter, exit). 16/16 attributions, feedback reaching the model, feedback on the person's screen
  and acceptance after the fix, including a multi-turn case. OpenCode's interactive TUI does get
  pre-delivery feedback (written earlier, first measured now); `opencode run` still does not.
  `e2e_trace.py --via-do` runs the same faults through `vacant do`: 25/25, OpenCode included.
- The scripted mock model accepts only the experiment's fake keys (anything else is refused with 401
  and never logged), so a passing run shows no other credential on the machine was used; it also
  plays multi-turn scripts (`turns`).
- Large projects: a scan inside a hook stops at 8 s (hooks are killed at 30 s); a first look that
  does not fit moves to the background and the steps before it are recorded as not observed;
  states of projects with 1000+ files are stored as deltas (0.9 KB per step instead of 4.9 MB at
  40k files); re-runs rebuild only the deliverable, the same files the intake's verifiers see.
  Measured with the real hook entry point: 40k files → first Pre 5.7–8.2 s, later hooks p95 0.6 s,
  Stop with tracing 1.9 s (`ops/accountability/evidence_20260924/perf/`). Above 50k files the
  per-step scan is off and the trace says so. An adversarial review of this change found 8
  issues, all fixed (`ops/accountability/review_scale/FINDINGS.md`): a step that started before the
  first look and ended after it now leaves a gap instead of letting a later editor be blamed;
  unreadable stored states make the trace say "not observed" instead of blaming anyone.

**The intake is real, and it plugs into pi, Claude Code, OpenCode and Codex without looking at
model traffic.** Decision: `decisions/DECISION_20260924_UNIVERSAL_INTAKE.md`.

- New `vacant_network.intake`: versioned task contracts (`vacant contract init|lock|validate`),
  content-addressed quarantine, per-claim verifiers with four outcomes (PASS / FAIL / UNKNOWN /
  CONFLICT), a written decision policy (accept / reject / hold / escalate), signed human reviews,
  bound single-use approvals, a recipient gate (`dir:` and `git:` destinations) that re-checks
  everything and reads the destination back, a per-task signed ledger in which every event —
  including infrastructure failures — stays in the denominator, and an HTTP intake whose
  submitters cannot supply the verdict. Exit codes 40–45 (the `vacant run` / gateshim 20–26
  meanings are unchanged).
- New `vacant_network.adapters`: `vacant do <agent>` (isolated workspace + headless run + intake),
  `vacant install` / `vacant uninstall` (hooks + an Agent Skill in each agent's own config,
  key-level and reversible), `vacant hook <agent> <event>` (one policy, four native formats).
- Per-run hooks never touch the user's files and never replace their settings: OpenCode's plugin is
  merged into `OPENCODE_CONFIG_CONTENT` (not `OPENCODE_CONFIG_DIR`, which also hides the global
  `AGENTS.md`; an unparseable user value means no injection rather than a replaced value), and
  its end-of-session submission runs in the awaited `dispose()`. When the persistent install is
  present, `vacant do` does not inject a second copy (pi, OpenCode and Codex hooks are additive,
  so the stop check would otherwise run twice per turn).
- **Adversarial review, same day** (five lenses, 60 findings, each reproduced or refuted against
  the code; decision §十一). Fixed with a regression test each:
  - *Recipient:* releases follow only an **owner-locked contract** (`vacant contract lock` now
    signs the contract hash and release policy with a new `owner` key; a second contract with the
    same task id and a weaker policy is refused); the already-published path re-checks the lock
    and decision; approvals bind the *resolved* destination; spent nonces and withdrawals are
    remembered in the signed ledger too; the recipient notices a truncated ledger it has seen;
    git destinations find the task's last release (not just the branch tip) and read back with
    `ls-tree -z`; hand-made quarantine manifests with `../` paths are refused before any write;
    `/published` serves only what the signed ledger shows as released and not withdrawn, never
    follows symlinks, and re-hashes every file.
  - *Verifiers:* sandboxed checks run hermetically (no login-shell profile, no Python user site,
    HOME outside the deliverable; `vrun`'s `bash -lc` behaviour is unchanged); `command` gets its
    documented environment inside the sandbox; NaN/inf and decimal commas are unreadable instead of
    matching anything; `Subtotal` is not `total`; citations checked only against the deliverable's
    own files are not independent evidence; JSON NaN, `format` and draft-07 keywords are enforced;
    malformed params are `UNKNOWN`, not the deliverable's fault; hidden claims stay hidden in every
    output; reviews bind the contract hash; the scaffold forbids `.env` at any depth.
  - *Adapters:* the shell rule compares path components and real write targets (it no longer
    blocks `pytest tests` or every write under `~/.vacant-work`); Codex/OpenCode `apply_patch`
    payloads are read in their real shapes; `/clear`, resume and reload do not submit; unfixable
    holds are not pushed back to the agent; the session cannot run `vacant review|approve|release|
    withdraw|keys|contract lock`; `CLAUDE_CONFIG_DIR` is honoured; Codex trust keys cover a
    symlinked `~/.codex`; installs write through symlinks and keep file modes; re-installing keeps
    the first backup; failed undo steps are kept for retry; a damaged end marker is refused
    instead of deleting to end of file; `vacant do codex` no longer makes Codex append a
    `[projects]` entry to the user's config on every run; pi/OpenCode hooks no longer block the
    event loop; `vacant uninstall` also removes a 0.8.0 model-channel install.
  - *Accounting:* interrupting `vacant do` kills the agent's process group and records
    `infra_void`; escape detection covers `.git` config/hooks/refs, `__pycache__` and empty
    directories; `vacant do` retries only on a required FAIL; a later rejected candidate no
    longer hides a live release in `task status`/`report`; withdrawing a never-released task is
    a no-op; an unreadable ledger is its own row in the report; release-stage failures are
    `infra_void` (exit 43).
- **Changed:** `vacant install` / `vacant uninstall` now install the universal hooks + skill. The
  previous behaviour (resident model-channel proxy) is `vacant possess install` or
  `vacant install --observe-model`.
- **Fixed (P0):** acceptance counted results *received* instead of checks *declared*; a suite whose
  second check killed the process (even with exit 0) was reported all-pass. The trusted parent now
  derives the declared case list from the test file's syntax before any candidate code runs, the
  driver prints an end marker, and missing / duplicate / unknown cases, non-zero exit or a missing
  end marker all fail. `return False` and async checks no longer pass.
- **Fixed:** `vacant on` crashed with `NameError: os`; agents spawned by `vacant run` inherited a
  stale `PWD` (OpenCode wrote into the launch directory instead of the workspace).
- **Wording:** `"tamper_proof": true` → `false` / `"tamper_evident": true`; "the gate stops the
  delivery" → the gate decides refusal; `suitespec`'s "2+2=5" boundary now separates requirement
  authority from factual authority.

## 0.8.0 — 2026-09-19

**Breaking: the import package is renamed `vacant` → `vacant_network`. Every
`import vacant` / `from vacant.… import …` in your code must be changed.** There is
**no compatibility shim**, deliberately — a shim would reinstate the very collision this
release exists to remove (see below). Pin `0.7.0` if you cannot change your imports yet.

```python
- from vacant.logbook import Logbook          # 0.7.0 and earlier
+ from vacant_network.logbook import Logbook  # 0.8.0
```

### Why — `pip install vacant` was silently replacing our code

PyPI's `vacant` (alltuner/vacant, a Rust-backed authoritative-DNS tool; 0.4.15 as measured
2026-09-19) shipped **the same top-level directory name `vacant/`** we did. pip overwrites
file by file, so installing both produced, with **zero error messages in all four install
orders** (measured 2026-09-19 against real wheels):

```
pip list       → both listed; vacant-network 0.7.0 still "installed"
import vacant  → AttributeError: module 'vacant' has no attribute '__version__'
vacant --help  → their DNS tool's interface
```

Adding a second console script was tried first and **measured not to work**: both scripts
did `from vacant.cli import main`, so their `vacant/cli.py` shadowed ours either way. A
second command name only helps *after* the import package is renamed — which is what this
release does.

### What this fixes, and what it does not

| | up to 0.7.0 | from 0.8.0 |
|---|---|---|
| `import` | shared `vacant/` directory; pip overwrites file by file | **fixed** — `vacant_network/`, no shared module |
| the `vacant` command | whichever package is installed second wins | **not fixed, not fixable** — identical console-script names are the same file path |

Two escape hatches are added for the half that cannot be fixed:

- **`vacant-network`** — a second console script, same entry point. It imports
  `vacant_network.cli`, which the other package cannot shadow.
- **`python -m vacant_network`** — new `vacant_network/__main__.py`; bypasses `bin/`
  entirely.

`vacant` remains the primary command name.

### Not renamed (deliberate)

These are **not** the package name and changing them would break stored data or rewrite
records of runs that already happened:

- Wire/format strings: `vacant.facts/1`, `vacant.delegation.context`,
  `vacant.delegation.receipt`, the `vacant` field in `summary.json`.
- The config filename `vacant.toml`; the arm name `"vacant"`; the task-generator seed
  `"vacant"`; the CLI `prog=` string; the MCP server name.
- `runs/**` and `decisions/**` — archived drivers and pre-registration documents still
  read `vacant.*`. Rewriting them would make the record describe a command that was never
  issued (same discipline as the frozen `--decision` paths). `runs/INDEX.md` says so
  explicitly. Three files pinned by `docs/paper_2026-09-14/source_manifest.json`
  (`docs/VACANT_COMPLETE_2026-09-12.md`, `docs/JOURNEY_2026-09-13.md`,
  `docs/HMIX_ARCHITECTURE_2026-09-11.md`) are untouched for the same reason.
- **108 archived data files** (`.json`/`.jsonl`/`.log`/`.txt` under `ops/gain/replay/**`,
  `ops/gain/r53*/bank*`, `ops/gain/r530/smoke9/`, `ops/exhibit/twin/twin_pack.json`) keep
  `vacant/…` verbatim. Two reasons, both hard:
  1. Their `file_sha256` maps record **which source bytes produced that run**. Renaming a
     key would claim we hashed `vacant_network/checks.py` on 2026-09-06, when that path
     did not exist.
  2. Fields such as `ruler` (`vacant/vrun/acceptance.py::run_suite(…)`) sit **inside
     signed receipt payloads**. Editing them breaks signature verification — including in
     `examples/twin_viewer.html` and `examples/receipt_viewer_multiparty.html`, which
     re-verify those chains in the browser in front of an audience. The viewers' embedded
     data blobs are therefore byte-identical; only their source comments were renamed
     (`ops/gain/replay/build_multiparty_viewer.py --check` still reports OK).

  Consequence, stated rather than hidden: those files name a path that no longer exists in
  the tree. That is the same trade as the frozen `--decision` paths.

### Fixed — one version string no longer means two different codebases

Before this release the three "version" sources disagreed: the newest git tag was
`v0.6.0`, PyPI had `0.7.0`, and `vacant/__init__.py` also said `0.7.0` while HEAD had
moved on — so `0.7.0` named two different sets of bytes (recorded in
`docs/INSTALL_LOG_20260919.md` §11 and README's "you may hit this" table).

- `tests/test_version_discipline.py` — `__version__`, the newest `CHANGELOG.md` heading
  and the version `pyproject.toml` resolves must agree. Fail-closed.
- `.github/workflows/publish.yml` — a release-triggered publish now **refuses to build**
  unless the release tag is exactly `v$__version__`.
- **Still true, and not measured away**: PyPI's newest `vacant-network` is `0.7.0` until
  0.8.0 is actually published. The tag `v0.8.0` is cut locally and is **not pushed**. And
  **we still cannot say which commit PyPI's 0.7.0 was built from** — there is no build
  record; that is "not measured", not "measured to be none".

## 0.7.0 — 2026-09-18

**Breaking: this is not an upgrade of 0.6.0, it is a different codebase.**
Anything that imported `vacant.core`, `vacant.protocol`, `vacant.runtime`, `vacant.mvp`,
`vacant.client` or `vacant.composite` will not work. Those modules are gone. Pin `0.6.0`
if you depend on them.

### Added — `vacant run`: a receiving desk for any agent's delivery

- **`vacant run -- <any agent command>`** wraps an agent process. It records the workspace
  tree hash, spawns the agent, waits for it to **exit**, runs the client's visible acceptance
  suite against a **frozen snapshot**, signs a receipt chain, and makes the **exit code reflect
  the verdict — not what the agent said about itself**. `VACANT=0` passes bytes through
  untouched (request bodies are byte-identical to an unwrapped run, proven by
  `ops/vacantrun/selftest.py`) while still recording every call verbatim.

- **`--retry resample|revise` (V1)** — when acceptance fails, run the agent again.
  `resample` resets the workspace and withholds the failure text; `revise` keeps the workspace
  and hands the failure text back. Every attempt signs its own `ws_attempt`; the closing
  verdict signs `ws_verdict`. **No protocol is touched and no model utterance is fabricated**:
  a retry is a new process, not an injected message.

- **`--feedback-into file|prompt|both` (V2)** — deliver the failure text by **appending it to
  the next spawn's prompt** instead of writing a file the model may never read. The placeholder
  `{VACANT_FEEDBACK}` must sit at the **end** of its argument, so attempt 1 is byte-identical
  to an unwrapped run and later attempts are a byte-exact prefix plus the feedback — which also
  keeps the provider's prefix cache warm. **What this buys is that the feedback is present in
  the model's input. It does not make the model act on it**; the only thing that is enforced is
  that work which fails acceptance is not delivered.

- **`vacant demo gate`** — zero setup, zero model endpoint, zero API key, zero network.
  A stub agent declares success, the client's acceptance says otherwise, delivery is refused
  (exit 20), and the receipt is verifiable — with the verifier's own negative control run first.

- **Agent compatibility, measured rather than assumed** (`docs/AGENT_COMPAT.md`).
  Claude Code 2.1.276 and OpenCode 1.18.31 attach through a single environment variable;
  Codex 0.153.2 (API key) and pi 0.85.1 attach through their config files.
  **Codex under `codex login` cannot be attached at all** — its model channel is a hard-coded
  `wss://` endpoint, so verbatim recording does not hold on that path. **Hermes is untested**
  (not installed on any machine we have). The only evidence that an agent is actually mediated
  is `requests_seen`, not the fact that an environment variable was set.

- **CI now has the seven required status checks** it has always declared, including a
  `pip install`-from-wheel smoke test that runs `vacant demo gate` **from outside the
  repository** — because running it inside the repo imports the source tree, not the package.

### Packaging

- Distribution renamed to **`vacant-network`** on PyPI. The import name is still `vacant`.
  (`vacant` on PyPI belongs to an unrelated DNS tool by another author; the repository's
  own `pyproject.toml` previously declared that name and could never have been published.)
- Runtime dependencies cut from a declared `fastapi` / `anthropic` / `streamlit` /
  `sqlmodel` / `alembic` set — 63 packages on a clean install — to the three that are
  actually imported: `cryptography`, `mcp`, `jsonschema`. A clean install is now 30 packages.
- `jsonschema` promoted from "used if present" to a declared dependency. The previous
  fallback (`vacant/checks.py::_mini_validate`) is **looser** than the real validator, so
  the same `json_schema` check could return different verdicts on two machines. A system
  whose claim is that verdicts can be recomputed cannot have its criterion drift with the
  environment.
- `requires-python`, classifiers, `project.urls`, SPDX license metadata and a
  `py3-none-any` wheel + sdist that pass `twine check`.
- Version has a single source of truth: `vacant.__version__`, read by setuptools.
- **`vacant demo gate` and `vacant run -- <cmd>` no longer need a clone.** Their judgement
  layer used to live in `ops/`, which is deliberately not in the wheel, so `pip install
  vacant-network` gave you a library and a message telling you to clone. Fixed by **moving
  and inverting the dependency**, not by copying: the implementation now lives in
  `vacant/vrun/` (`acceptance`, `sandbox`, `wshash`, `receipts`, `verify_receipts`,
  `launcher`, `retry`, `wireproxy`, `envmap`, `demo`), and `ops/gain/r530/*`,
  `ops/gain/replay/verify_run_receipts.py` and `ops/vacantrun/*` are re-exports that alias
  `sys.modules` to it. The old import paths and the old script paths keep working and
  resolve to **the same module object**, so there is still exactly one ruler — a second
  copy is what `vacant/suitegauge.py` and `conform_failure_detail` both forbid in writing.
  `tests/test_vrun_reexport.py` is the executable guard (identity by `is`, no `ops.*`
  dependency inside the package, `packages` actually lists `vacant.vrun`).
  The top-level `ops` package is still kept out of the wheel on purpose: `ops` on PyPI is
  Juju's package, and the collision would silently overwrite files.
  `ops/vacantrun/envmap.py` has no re-export — it moved outright, because a list whose
  failure mode is "that path was not mediated and there is no error message" must have
  exactly one home.

### Verified — the wheel itself, installed, from outside the repository (2026-09-18)

"No clone needed" was written down before anyone had installed the wheel. It is now
measured. The measurement has to happen **outside a repo checkout**: inside one,
`import vacant` finds the source tree rather than the installed package, so a check run
there cannot tell a working wheel from a broken one.

- `python -m build` produces `vacant_network-0.7.0-py3-none-any.whl` and the sdist;
  `twine check` PASSED on both. The wheel's `top_level.txt` is `vacant` alone, and its 71
  entries include the ten `vacant/vrun/*` modules and `vacant/web/app.{html,css,js}`.
- Fresh venv (Python 3.13) with **only** that wheel installed, working directory outside
  the repository: `vacant demo gate` plays the whole first screen — the gate refuses the
  delivery (`visible_fail`), the inner `vacant run` subprocess exits `20`, the two-entry
  Ed25519 chain verifies (`verdict=OK`) and the verifier's own negative control passes
  first. `vacant run -- <cmd>` in the same venv: `20` on refusal, `0` on `visible_pass`,
  and `VACANT=0` passes the agent's own exit code through.
- Receipts written by the installed wheel were then re-verified by
  `ops/gain/replay/verify_run_receipts.py` from a repo checkout: `run 3　鏈 2　entries 4　
  驗過 4　失敗 0　壞鏈 0 … 總判：OK`. One ruler, two install shapes.
- **The name collision was measured, not assumed.** Juju's `ops` (3.8.2) and
  `vacant-network` 0.7.0 were installed into one venv in both orders. Both import,
  `ops.CharmBase` and `ops.model.Model` still resolve, `vacant demo gate` still runs, and
  the intersection of the two distributions' `RECORD` file lists is **empty** — neither
  package overwrites a file of the other. All 61 modules of the wheel import cleanly in
  that venv too, so nothing inside `vacant` accidentally resolves to Juju's `ops`.
- **And the counterfactual was measured as well**, because the reason for keeping a
  top-level `ops` out of the wheel has to be the real failure mode: a throwaway wheel that
  *does* ship a top-level `ops` was installed on top of Juju's. pip printed
  `Successfully installed`, no warning, and afterwards `ops/__init__.py` belonged to the
  new package (`ops.CharmBase` gone) while `pip` still reported `ops 3.8.2` as installed.
  Silent overwrite, exactly as the READMEs say.
- Installing from the **sdist** works too, and so does Python **3.11**, the declared
  minimum (`vacant demo gate` end to end, gate refuses, chain OK, on 3.11.13 and 3.13.1).

### Fixed — two defects that only bit at call time

- `vacant/peerexec.py::sandbox_probe` and `vacant/suitegauge.py::default_runner` imported
  `ops.gain.gain_run` inside the function body. `ops/` is not part of the distribution, so
  importing `vacant` succeeded and **calling** these raised a bare
  `ModuleNotFoundError: No module named 'ops'`. They now raise
  `vacant.suitegauge.OpsRunnerUnavailable` with a message that names the two supported
  injection points (`gauge_suite(runner=...)`, `Executor.new(probe=...)`) and the
  `CheckRunner` signature. **The acceptance criterion was not copied into the library** —
  a second copy is exactly the drift both docstrings forbid, and the experiment's sandbox
  import allow-list is not a policy the library should assert on a user's behalf.
- The build no longer warns about `vacant/web`, and the dashboard assets are confirmed
  present in the wheel.

### Fixed — three blockers found by a clean-room verification (2026-09-18)

An external agent was given the wheel and the READMEs only — no source — and ran 0.7.0 on
Ubuntu. Three defects, all of the same shape: **the failure looks exactly like a normal
output.**

- **`vacant bench` reported a comparison it had never measured.** With every model call
  failing (endpoint down), all calls were silently counted as wrong answers and rendered as
  "plain 0%, vacant 0%, +0%", exit 0. That violates the project's own `infra_void` rule
  (09 §3.5; already enforced by `vacant/vrun/acceptance.py` and by `vacant record check`):
  **a cell that was not measured is not a cell that measured zero.** `bench` now separates
  right / wrong / **not measured**, refuses to print any comparison number when either arm
  has zero measured cells (exit 2, with the endpoint, the per-arm denominators and the first
  error verbatim), and prints the `infra_void` count separately when the failure is partial.
  `Vacant.bench` gained `plain_void` / `vacant_void` / `plain_measured` / `vacant_measured` /
  `paired_measured` / `infra_void` / `first_error`; the three rates are `None`, not `0.0`,
  when their denominator is zero. `SolveResult` gained `ok_calls` / `failed_calls` /
  `first_error` and the `infra_void` / `measured` properties.
- **Our own banned terminology appeared in our own CLI output.** `llms.txt` says "do not
  describe Vacant as a trust layer" and the `AGENTS.md` facts block carries a `never_use`
  list, yet `vacant demo`
  printed 「信任性質」/「信任層淨貢獻」, `vacant init` printed 「信任庫」and `vacant up`
  printed 「信任機制」. Every user-visible string is now accountability-phrased. **Only
  strings changed**: `trust_dir`, `trust_card`, `trust_on`, the `--trust` flag and the
  `trust/` directory name are API surface and are untouched (the path is still spelled
  `trust/` in the output, now glossed as "金鑰與究責紀錄"). The `never_use` list itself was
  incomplete — it listed only the two English phrasings — so 「信任」／「信任層」 were added
  to it, together with the scope (output and prose, never identifiers) and the test that
  now enforces it. The MCP tool docstrings in
  `vacant/mcp_server.py` were deliberately **not** touched — that text enters an agent's
  prompt, so editing it changes behaviour and breaks comparability with existing runs.
- **Three "follow the docs and it breaks" gaps**, one of which disguised itself as a
  refusal: `select_by_quorum`'s `drafts` is `Sequence[tuple[str, str]]` and the order was
  documented nowhere. Passing `(worker_id, code)` is not a type error — every "draft" fails
  the suite, the panel agrees unanimously, and you get `refused=True` with three chains that
  all verify, which is indistinguishable from the mechanism correctly rejecting bad work.
  `select_by_quorum` now applies a cheap **heuristic** shape check and raises
  `peerexec.DraftOrderError`; the heuristic has false negatives and says so, in the
  docstring, in the exception text and in a test that pins one. `SuiteSpec` mappings require
  `"v": 1` and the old message (`bad_version:None`) named neither the field nor its legal
  value; `Executor.attest` requires `task["entry_point"]` and reported
  `entry_point_unbound` even when the `SuiteSpec` passed in did declare one. Both messages
  now say what to fix. `SuiteSpecError` was split into `.code` (machine-readable — this is
  what goes on the chain and into `Selection.refusal_reason`, and it is **byte-for-byte
  unchanged**) and `.hint` (human-readable, `str(exc)` only).

### Documentation

- `README.md` / `README.en.md` / `README.ja.md` rewritten: a short human part
  (one sentence, a 30-second quickstart, current results with their denominators) followed
  by a large machine-facing part.
- New `AGENTS.md` — the integration contract for coding agents: API surface with
  signatures, the four deployment shapes and which of them are actually binding,
  falsifiable invariants, honest boundaries, common mistakes, and a stable
  machine-readable facts block.
- New `llms.txt` following the llmstxt.org convention.
- **The outward positioning was corrected.** Vacant used to be described as a layer that
  wraps an agent. It is not: as a library or an MCP tool it is *voluntary*. The accurate
  description, now the first line of all three READMEs, is a **receiving desk** — a delivery
  without a verifiable receipt is not accepted. Enforcement is at acceptance time, and that
  check cannot be routed around; making Vacant a machine's single exit is the deployment
  layer's job. In reference-monitor terms (Saltzer & Schroeder 1975) it is tamper-proof and
  small enough to verify, and does **not** satisfy complete mediation.
- **Three boundaries that had never been written down are now written down**: the chain gives
  integrity but not completeness (a truncated tail verifies — a truncation/omission attack,
  Ma & Tsudik 2009; `vacant/checkpoint.py:144-155` has the same hole; signing the entry count
  into each entry does not help, because `seq` already is the count); the acceptance gate
  still admitted 14.8% false deliveries in R532; and the reconciliation in
  `ops/gain/replay/verify_run_receipts.py` is same-origin, so it catches bugs and not malice.
- **A coverage gap in our own audit was found, published, and then closed.** We had claimed
  R532 was "V/GT 43/43 CLEAN". It was false: `ops/gain/harness_vgt_audit.py:746` is
  `if arm not in VARIANTS: continue` and `ops/gain/harness_arms.py:65` sets
  `VARIANTS = ("HPI", "HOC", "HMIX")`, so the classical seven arms — `OFF` and `CONFORM`
  included — had never been scanned. The fix includes **changing the default to a full
  audit**: a green light obtained by forgetting to pass a flag is exactly the condition that
  let the hole exist. The retroactive sweep completed 2026-09-18 and is recorded in
  `ops/gain/vgt_retro_audit_20260918.json` (scope v3 = ten arms, per-arm fail-closed):
  **179 archived runs, 165 CLEAN / 10 UNVERIFIABLE / 4 VIOLATION, 3,486,403 needles
  checked**, with the four cited batches CLEAN on every arm (R460 6/6, R460R 30/30, R529
  37/37, R532 43/43), including **R532's 1,122 `CONFORM` records audited dynamically for the
  first time**. The 10 UNVERIFIABLE are aborted runs with preflight only and no audit target
  — an honest verdict, neither clean nor dirty. The 4 VIOLATION are all in R530 under
  `hidden_file_in_workspace` and, on inspection, are the model's own same-named test files;
  whether to tighten that rule is **unresolved**. Boundaries that travel with these numbers:
  `CLEAN` covers only the literal repr of `hidden \ visible` in harness-authored prompt text
  (semantic paraphrase is not detected), the bank is inferred rather than recorded for runs
  predating R529, and `analyze_r529.py`'s `vgt_gate()` / `analyze_r532.py`'s `gates_post()`
  still read the HMIX-only `vgt_v2_<block>.json`, so the gates have **not** all caught up.
  Full text in `AGENTS.md` §7 H-0.
- `vacant/__init__.py`'s summary line no longer says "強制信任" (mandatory trust). It said
  two wrong things at once: the project's terminology is *accountability*, not trust, and
  "mandatory" is more optimistic than `vacant/controller.py:7-8`, which states that the
  guarantee covers only the subprocess the controller spawns itself.

### Not changed

No experiment code. The acceptance sandbox, the chain format, the gauge, the arbiter and
every recorded run are byte-for-byte what they were. The clean-room fixes above changed
runtime behaviour in exactly two places, both of them refusals that used to be silent:
`vacant bench` now exits non-zero instead of printing an unmeasured comparison, and
`select_by_quorum` raises on a reversed `drafts` argument. Every wire-facing string
(`refusal_reason`, `SuiteSpecError.code`, attestation payloads) is unchanged.
