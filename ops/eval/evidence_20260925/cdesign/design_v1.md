# Zero-config Vacant (arm C), product-grade — implementation design

Label `design`, 2026-09-25. Repo `/home/user/Vacant` @ b8b78304 (branch claude/vacant-verification-redesign-jv7eou). Design only; no repo edits. Files: `/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/cdesign/design/{DESIGN.md,AGENT_TEXTS.md,WORK_PACKAGES.md}`. Everything below was checked against the current code by reading it (`trace/{capture,recorder,blame,locate,feedback,stopcheck,finalize,tools}.py`, `adapters/{hook,hookpolicy,agents,install,run,cli}.py`, `intake/policy.py`), the arch notes, the decision (§4, §6.4, §6.5, §8, human decisions), the install audit, the acceptance spec, and the item lists of the concurrent xpath fixes.

## 0. What the product must do (產品原則)

The person installs once (`pipx install vacant-network`, `vacant install`) and keeps opening their usual agent. With no contract, no env var, no config edit, every task's result is checked at "agent says done" against the recorded steps of that task (materials named in the request opened? each specific number/date sourced or derived? a claim of testing backed by a run that passed after the last edit? a failed step ignored?), the unjustified parts are sent back to be redone before the person sees the result (bounded rounds), and the person then sees a short note (Checked / Fixed / Unverified). Vacant breaking never changes what the agent delivers (fail open). Contracts stay the optional hard-check layer on top.

## 1. Where the current code stops, and the smallest cut that opens it

| today (verified by reading; the Stop gate also by running the hook in the install audit) | gate | consequence |
|---|---|---|
| `adapters/hook.py::handle` line 279: Stop check only `and contract is not None` | contract | no contract ⇒ bare allow, whatever the final message claims |
| `trace/capture.py::workspace_for`: trace only with contract or `VACANT_TRACE=1` | env | zero-config installs record one events.jsonl line per hook, nothing else |
| `hook.handle`: `new_request(...)` and `_spawn_finalize(...)` only under contract | contract | no round reset, no session-end pass without a contract |
| `hookpolicy._rounds_file(session, contract)` keyed on contract path | contract | contract-less projects would share one "nocontract" bucket |
| `adapters/run.py` (`vacant do`) typed on `Contract` throughout | contract | not a zero-config path either (left as is; not on the critical path) |
| `vacant install` writes SKILL.md for every agent | — | the skill enters the model's system prompt/tool list: C's first request ≠ A's (G11) |

Everything downstream already works with `contract=None`: `blame.blame_location` (value → introducing step → origin among what the actor observed), `locate.occurrences/contains` (numeric-aware; `365,950` = `365950`, so a computed total printed by a command is "sourced" with no new machinery), `feedback` (line cap, KS-1 per line, finding ids, still-open/resolved), `stopcheck.localize` (finding events, report, feedback_state.json), `hookpolicy` round cap + `new_request`, `finalize`, `Trace.materialize`, `vrun/sandbox.py hermetic=True`. One gap in the primitives: `Blamer._referenced_files` does not see paths inside interpreter code (`open('materials/x.csv')`), so the "opened?" matcher must be evidence.py's own (decision §6.4).

So zero-config = a new finding source (evidence over the chain) plugged into the same Stop plumbing, plus a mode switch, contract-less tracing, final-text capture, a review renderer, a delivery note and the display channels. ≈ 2,900 lines + ≈ 230 tests.

## 2. Modules

```
vacant_network/adapters/mode.py           NEW   VACANT_MODE resolution (env > install.json > default)
vacant_network/adapters/zeroconfig.py     NEW   zero-config Stop/session-end entry called from hook.py: subprocess watchdog, fail-open, errors.jsonl, note plumbing
vacant_network/adapters/hook.py           EDIT  ≤ 20 lines: route to zeroconfig when no contract; new_request/defer without contract; pass final text
vacant_network/adapters/hookpolicy.py     EDIT  _rounds_file/new_request accept a workspace scope; decide_stop_zero(); ZERO_MAX_ROUNDS = 2
vacant_network/adapters/install.py        EDIT  manifest schema 2: {"mode","skill","installed_at"}
vacant_network/adapters/cli.py            EDIT  install: no SKILL.md by default (--skill), ≤10 lines, prints data dir; uninstall: data dir + removal command, --purge; thin subparsers for --help
vacant_network/adapters/agents.py         EDIT  pi extension: forward final text, show note; OpenCode plugin: fetch final text, show note; install fns: skill optional
vacant_network/trace/capture.py           EDIT  workspace_for(): project root when mode != off; record final_message at stop; prompt_source: new headers
vacant_network/trace/recorder.py          EDIT  EVENT_TYPES += "final_message"; Recorder.final_message()
vacant_network/trace/evidence.py          NEW   the deterministic evidence pass (pure over the chain)
vacant_network/trace/evidence_rules.json  NEW   exemptions, runners, failure/success patterns, limits (data, not code)
vacant_network/trace/derive.py            NEW   derived-value recognition (aggregates, group-by, ratios, dates)
vacant_network/trace/xlsxread.py          NEW   stdlib zipfile+XML reader for .xlsx cell values (R5)
vacant_network/trace/projectchecks.py     NEW   auto-discovered checks on materialized before/after copies
vacant_network/trace/review.py            NEW   agent-facing text: constants (KS-1 at import), per-kind templates, substitute line, path guard
vacant_network/trace/delivery.py          NEW   delivery note (delivery.md/json + ≤6-line screen text)
vacant_network/trace/stopcheck.py         EDIT  localize_evidence() twin of localize(); `zero` CLI entry
vacant_network/trace/finalize.py          EDIT  zero mode: `--zero <workspace> <platform> <session>`
ops/intake/mock_model.py                  EDIT  header mark, x_fix_when, x_fix_rounds, x_read, full feedback text
ops/usersim/run.py (+ gen_fixtures --big) NEW   the simulated-user harness (accept spec §5)
ops/zeroeval/replay_evidence.py           NEW   offline false-positive replay over recorded chains
```

Nothing is written into any task workspace. All state stays under `$VACANT_HOME` (`~/.vacant`): `adapters/install.json`, `intake/hooks/{events,errors}.jsonl`, `intake/hooks/rounds_*.json`, `trace/projects/<key>/{chain.ndjson, head.json, state.json, perf.jsonl, feedback_state.json, evidence_<n>.json, report.md, report.json, delivery.md, delivery.json}`, `tmp/projcheck-*` (removed after use).

## 3. Mode switch and its default after install

`VACANT_MODE ∈ {off, observe, persona, evidence}`, resolved by `adapters/mode.py::current_mode()`: (1) env `VACANT_MODE` if set and valid (benchmark arms and tests; the product never needs it); (2) else `install.json["mode"]` (written by `vacant install` as `"evidence"`); (3) else `"evidence"` (schema-1 manifests, per-run injected hooks): the default is evidence, `off` is only ever explicit; (4) `VACANT_TRACE=0` forces `off` (archived runs and tests rely on it); `VACANT_TRACE=1` keeps its old meaning (trace `cwd`).

- `off`: today's behaviour (contract path only).
- `observe`: trace + evidence.json + delivery.md written, no text ever injected, nothing on screen.
- `persona`: benchmark arm B (kept for later; the human decided B is not run now). Same wrapper, same rounds, header+persona+footer only, no evidence lines; byte-identical to `evidence` minus the evidence block.
- `evidence`: the product. Default.

`vacant install` writes `install.json` schema 2: `{"schema": 2, "mode": "evidence", "skill": false, "installed_at": "<iso>", "agents": {...}}`. Re-running is idempotent and does not change a mode the person set. No `vacant mode` verb is added: one setting, one default; `VACANT_MODE=off` in the shell is the expert off-switch, documented in the README troubleshooting table.

## 4. Tracing without a contract

`capture.workspace_for(cwd, contract)` becomes:

```
if VACANT_TRACE == "0": return None
if contract is not None: ws = contract.base_dir
elif VACANT_TRACE == "1" and cwd: ws = cwd
elif current_mode() != "off" and cwd: ws = project_root(cwd)
else: return None
return ws if _traceable(ws) else None
```

`project_root(cwd)`: the nearest ancestor of `cwd` (inclusive) holding a `.git` entry (dir or file), walking up but stopping before `$HOME` and `/`; none ⇒ `cwd`. No subprocess; one stat per ancestor. The `_traceable` exclusions stay (`/`, `$HOME` and its parents, `$VACANT_HOME`, `$VACANT_WORK`). N2b (agent opened in `$HOME`) is not traced and creates no project entry. `HOOK_SCAN_S` = 8 s first-look-to-background and the 50k-file cutoff stay; a project with scanning disabled yields `UNOBSERVED` blames ⇒ never a pushback.

`hook.handle` changes (tiny; group "sources" owns this file concurrently): `_person_prompt` → `new_request(session, scope)` whenever a workspace exists; `_defer_for_subagents` runs with `contract=None`; `elif ev.kind == "stop" and contract is None and mode != off:` → `zeroconfig.stop(agent, ev, payload)`; terminal `session_end` without contract → `zeroconfig.session_end` spawns `trace.finalize --zero` in the background (the `opencode run` route and late edits); the Stop payload's final text (`last_assistant_message` for Claude/Codex, `final_text` from the pi/OpenCode bridges) goes into `capture.observe(..., final_text=...)`, which records a `final_message` event (`{actor, session, text_blob, observed_by:"agent_hook"}`) before the evidence pass.

Round-budget key without a contract: `_rounds_file(session_id, scope)`, scope = contract path (as today) or `ws:<resolved workspace>`; `new_request(session_id, scope)` likewise. One request = the person's typed prompt (`capture.classify_prompt(...)[0] == "user"`, the single source of truth, including the concurrent fixes: scheduled prompts, teammate envelopes, `vacant do` retry text, feedback headers).

## 5. At "agent says done": the deterministic evidence pass (`trace/evidence.py`)

Pure function `evidence_pass(trace: Trace, *, session_key, rules, now_index) -> EvidenceResult`. It reads only the chain and blobs, so it replays offline on any recorded trace (`ops/zeroeval/replay_evidence.py`) with zero model calls — that is how the false-positive rate is measured before any claim.

### 5.1 Window, deliverables, materials

- **Window** = chain events after the last `prompt` event with `source == "user"` for this session (sub-agent steps of the same root session included). No user prompt recorded ⇒ from the session's first step (`window_basis: "session_start"`, a coverage remark in the note). Vacant's own review prompts (`source == "vacant_feedback"`) never start a window, so round 2 sees draft + fix together.
- **Deliverables** = files written by window steps (`Trace.transitions` of kind `step`; gap transitions are listed under coverage, not checked), still present in the latest index, minus `rules.skip_dirs` (`.git node_modules __pycache__ .venv .pytest_cache .mypy_cache dist build .cache target`), minus files > 2 MB, minus non-UTF-8 files except `.xlsx` (read via `xlsxread`). Type by extension: `document` (`md txt rst adoc tex html csv tsv`), `code` (everything else, incl. `.json .yaml .toml`), `sheet` (`.xlsx`).
- **Given materials** (R7): tokens of the person's prompt(s) in the window, stripped of punctuation, matched against the window-start index as (a) exact relative path, (b) path relative to the hook `cwd`, (c) unique basename with extension, (d) a directory name (token equal to a directory in the index, with or without `/`) ⇒ every file under it outside skip dirs (recursive, cap 30; above the cap only files directly inside). URLs are not materials. Nothing named ⇒ no material findings. The "small document set" idea (arch §2(b)) is note-only ("not opened: …" under Unverified), never a pushback — it is the main FP source on real projects.
- **Observed** (a material counts as opened) iff some window step, by any actor of the session including sub-agents (N8), satisfies one of: a read/fetch/write tool whose input path resolves to it (`hook._paths_from`); a shell command whose text mentions it (evidence.py's own matcher: the relative path or basename as a whole token bounded by start/end/quote/space/`(`/`)`/`,`/`=`, covering `python3 -c "...open('materials/sales_2025.csv')..."`, `cat`, `head`, `file`, pandas — decision §6.4: any bash/python step whose command text or script mentions the file never gets "not opened"); a glob in a shell command that expands to it against the window-start index; a script written in the window and run by a window shell step whose text mentions it; an image material referenced by path in a deliverable's text. `ls`/search output that merely lists the name is not observation (`seen_name` only).

### 5.2 Checks

Each finding is a dict in the blame shape: `claim="ev:<kind>"`, `location`, `value`, `step`, `source`, `fault_class`, `confidence`, `detail`, plus `agent_fixable: bool`, `push_rounds_max: 1|2`, `kind_group`; `feedback.finding_id(b, scope)` gives the stable id (never verifier wording).

1. **`ev:unread_material`** — a given material never observed. One finding per material (stable id), rendered grouped on one line. `push_rounds_max = 1` (R7/G4): after one round it goes to the note only.
2. **`ev:unsourced_value`** — document deliverables only (never code, never `.json`). Extraction per line at the latest index: numbers (`locate._NUM_RE`) with ≥ 2 significant digits or a `$`/`€`/`EUR`/`USD`/`NT$`/`%`/`M`/`K` affix; full dates (ISO, `Month D, YYYY`, `D Month YYYY`, `YYYY/MM/DD`, `YYYY年M月D日`); percentages. Not extracted: bare years 1900–2100, `Q1..Q4`, list numbering, integers 0–10 without affix, times, version-like tokens (`v?\d+\.\d+(\.\d+)+`, `Python \d\.\d+`), hex colours, anything inside fenced/inline code or a table header row. Exempt lines: `rules.assumption_labels` (assume/assumption/assumed/estimate(d)/approx/placeholder/TBD/TBC/example/e.g./sample/hypothetical/rough/ballpark/forecast/projection/scenario, 假設/估計/範例/待定/預估/暫定) or `rules.proposal_labels` (target/goal/proposed/proposal/plan to/aim/objective/KPI, 目標/建議) (R8), and every line under a heading `Unverified`/`Assumptions`/`Open questions`/`TBD`/`未驗證`/`假設` until the next heading of the same or higher level. Values present in the person's prompt(s) are exempt before blame. Each remaining `(line, value)` goes through `blame_location(trace, Location(path, line, value), contract=None)` and is classified:
   - **sourced**: the origin chain has an observation hop (`read …`, `a command's output`, `the command read …`, `fetched …`, `a sub-agent's reply`, `the task message`, `the task the sub-agent was given`, `the instruction file …`, `the output of <tool>`), or the origin is `input`/`pre_existing`/`external`/`unresolved`;
   - **derived** (`derive.py`, §5.3): equal to a recognised computation over observed data;
   - **unsourced** ⇔ `fault_class == "agent"`, `state == "located"`, `source is None`, and every chain hop is the actor's own write (`wrote <path>` / `its own earlier write`): the value was never observed in anything recorded before it was written. This is blame's `direct` condition (the one `provable` starts from), so "no source found in the recorded steps" is literally true.
   - **never flagged**: `state ∈ {UNOBSERVED, UNKNOWN, candidate_set}`, `confidence == "gap"`, broken/unreadable store, `first_look_pending`, `scan_disabled` — counted as "not attributable" in the note.
   Rendering groups per file (≤ 5 `path line n "value"` locators per line, then another line); ids stay per (path, line, value). `push_rounds_max = 2`.
3. **`ev:write_before_read`** — deliverable D first written at step w; material M first observed at step o > w; D not rewritten after o. Heuristic, `push_rounds_max = 1`, suppressed when M already has an unread finding.
4. **`ev:unbacked_test_claim`** (needs the final text) — the last `final_message` in the window is scanned for `rules.claim_patterns` (`(all )?tests? (pass|passed|passing|are green|succeed)`, `test suite (passes|green)`, `(build|lint|typecheck)s? (pass|passes|clean|succeeds)`, `tested and (works|passes)`, 測試(全部)?通過, 測試都過; `verified|validated` only when the same sentence names a runner word, so S3's "complete and verified" is not a claim). Runner steps = window shell steps whose command (any pipeline segment) matches `rules.test_runners` (pytest, `python -m unittest|pytest`, unittest, tox, nox, `npm|pnpm|yarn (run )?(test|build|lint|typecheck)`, jest, vitest, mocha, `go test`, `cargo (test|build|check)`, `make (test|check|lint)`, mvn, gradle, `dotnet test`, rspec, phpunit, ctest, `bazel test`). Outcome: `error`/`is_error` ⇒ failed; output matching `rules.failure_patterns` (`FAILED`, `failures=`, `errors=`, `Traceback`, `\bFAIL\b`, `\d+ failed`, `npm ERR!`, `error\[E`, `test result: FAILED`, `BUILD FAILED`, `Tests:.*failed`) ⇒ failed; `rules.success_patterns` (`\bOK\b$`, `\d+ passed`, `test result: ok`, `BUILD SUCCESS`) with no failure match ⇒ passed; else `unreadable` (no finding, noted; Codex `post_missing` steps are unreadable). At most one of: (a) claim and no runner step; (b) claim and the last runner step failed; (c) claim, last runner passed at step r, a code deliverable changed at a step > r (priority b > c > a). `push_rounds_max = 2`.
5. **`ev:failed_step_ignored`** — window shell steps that failed (`error`, `is_error`, output matching failure patterns ∪ `command not found|No such file|Permission denied|exit code [1-9]`), minus probes (R6: command word in `ls which command type test [ [[ stat find head cat file tail wc du df git-status git-log git-diff pip-show --version`, or `grep|rg|egrep|ag` with no output beyond a count = no match). Handled when a later window step re-runs the same normalised command (command word + first script/file argument) without failure, writes any file named in the error text or the script the failed command ran, or the final message names the failure (`fail|error|crash|could not` within 40 chars of the command word or file name). Otherwise a finding citing step number, command (≤ 60 chars) and the last non-empty error line (≤ 80 chars, escaped). `push_rounds_max = 2`.
6. **`ev:dropped_values`** (R5) — a successful window shell step whose output holds a list of N ≥ 3 distinct tokens (Python/JSON list literal, or ≥ 3 consecutive one-token lines; tokens ≥ 4 chars containing a digit or `/`/`-`/`_`, so prose never qualifies); the latest list per step wins; a later printed strict subset supersedes the earlier list. For each deliverable (text; `.xlsx` via `xlsxread`), M = tokens present. Finding iff 1 ≤ M < N, the prompt(s) contain no integer equal to M and no `first|top|last M` phrase (N7), and the final message does not name the missing tokens. ≤ 4 missing named, then "and k more"; for `.xlsx` the column letter is named. `push_rounds_max = 2`.
7. **`ev:date_outside_data`** (R4) — document deliverables. For each CSV/TSV observed in the window with a date column (≥ 80 % ISO-parseable) whose min..max spans ≤ 366 days: each sentence (split on `.!?`/line ends) containing a full date D outside min..max and within ±2 years of it, containing the CSV's stem or a column name as a whole word (plural tolerated), containing no in-range date, and not on an exempt line or heading ⇒ one finding (id keyed on path+line+D). If not built when the matrix runs, S2 is a KNOWN MISS (0 false pushback still required; the note must not claim the text was checked). `push_rounds_max = 2`.
8. **`ev:project_check`** (§5.4) — regressions only. `push_rounds_max = 2`.
9. **Person's flags** — `vacant flag` stays (`stopcheck._flag_blames` with `contract=None`).

`agent_fixable = True` except: unread findings after their round is spent, `unreadable`/`UNKNOWN` outcomes, project-check timeouts and pre-existing failures (note only).

### 5.3 Derived values (`trace/derive.py`)

Inputs: observed tables of the window (CSV/TSV content that was read: read-tool output, or file content at the pre-index of a shell step mentioning the path; JSON arrays of flat objects; Markdown tables in tool outputs), capped at 20 tables × 50,000 cells, plus the set of observed numbers (every number token in window tool outputs and read contents, cap 5,000). Recognised, with tolerance = rounding to the printed precision: column sum/mean/count/min/max (thousands separators and `$`/`EUR` stripped, R3); group-by sums over another column's value, or over a date/text column's year, year-month, quarter (`Q4` = months 10–12) or month (S1 Q4 = 365,950; S2 North 1,510 / South 1,312); ratio and percentage of two observed/derived numbers (N6 8.2 %), sum and difference of two; date normalisation across formats (`November 15, 2026` = `2026-11-15`), date ± N days with N an observed number ≤ 400. Derived values are never findings; the note counts them as "derived from <file>".

### 5.4 Project checks (`trace/projectchecks.py`)

Runs only when code deliverables changed in the window and `VACANT_PROJECT_CHECKS != "0"`. Discovery at the current index: pytest config ⇒ `python3 -m pytest -q -x -p no:cacheprovider`; else `tests/` or `test_*.py` importing unittest ⇒ `python3 -m unittest -q`; `package.json` scripts `test|lint|typecheck|build` with an existing `node_modules` ⇒ `npm run <s> --silent` (never installs, never network); `Makefile` `test|check`; `Cargo.toml` ⇒ `cargo test --offline`; `go.mod` ⇒ `go test ./...`. Both states rebuilt with `Trace.materialize()` (window-start and current index) into `$VACANT_HOME/tmp/projcheck-<id>/{before,after}` with the intake skip rules (`ALWAYS_SKIP_DIRS`, no symlinks); skipped entirely above 20,000 files or 200 MB. Each run via `vrun/sandbox.py hermetic=True` (`BwrapSandbox` when available, else the plain sandbox with a scrubbed env, `HOME` in the copy, `PYTHONNOUSERSITE=1`; the note records which). Budget 120 s per run, 300 s total; timeout ⇒ `UNKNOWN`, never a finding. Failing test ids parsed (unittest `FAIL:|ERROR: test_x (mod.Class)`; pytest `FAILED path::test`); regression = ids failing after and not before, or overall before-pass/after-fail when unparseable. Pre-existing failures go to the note only. The live workspace is never touched; no `__pycache__` reaches it (G9). The after-copy run is skipped when the agent's own last runner step ran the discovered command after the last edit and printed success (the before-copy run still sets the baseline). Budget tunable via `VACANT_PROJECT_CHECKS_S`.

### 5.5 Output

`evidence_<n>.json` per Stop: window bounds, deliverables (type), materials (observed_by / not observed), extracted values with classification and reason (sourced via / derived from / exempt because / unsourced / not attributable), runner steps and outcomes, failed steps and how handled, dropped-value lists, project-check results, per-phase timings, findings. This is the auditable basis of both the review and the note.

### 5.6 False-positive controls (G1 = 0 on negatives)

Only prompt-named materials can push back; values are flagged only when never observed before being written (blame `direct`) — any observation hop, derived value, exempt label or prompt value is not; numbers in code files are never checked (`.json` counts as code); test claims need a claim phrase ("verified" alone needs a runner word in the sentence); probes and handled failures are exempt; prose never counts as a dropped list, a count in the prompt exempts, a later subset supersedes; date-outside-data needs a single-year table, whole-word stem/column match, and no in-range date in the sentence; project checks report regressions only, timeouts/pre-existing failures never push back; broken/unreadable record, unobserved start, disabled scan ⇒ no pushback (G14); wording never says "wrong"; the no-fault finding rate is measured by `replay_evidence.py` over the L-fake negatives and every recorded chain in `scratchpad/evalrun/try1` and the gate-1 traces before any pilot (decision §6.4: OS read witness, ≤ 10 % unread-material FP in real runs).

## 6. The review round (redo before the person sees it)

### 6.1 Decision (`hookpolicy.decide_stop_zero(ev, *, run_evidence, cap=ZERO_MAX_ROUNDS)`)

`run_evidence(why_open) -> {"text","findings","pushable","material_only","note","report","trace_verified"} | None` is `stopcheck.localize_evidence`. Rules: `None` (no workspace/chain) ⇒ allow, no note. Chain does not verify ⇒ allow; note says the record is broken; `record["trace_broken"]`; no finding is built on it. No pushable finding ⇒ allow; rounds file removed; `record["user_message"] = note` (empty when the window wrote no deliverable ⇒ nothing shown, N2a/N2b). Pushable ⇒ `n = _bump_round(session, ws-scope)`; if `n > cap`, or `material_only and n > 1` ⇒ allow with `rounds_exhausted` and a note listing what is still open; else `continue` with the review text. Round 2+ renders only still-open and new findings; `(still open)` marks and "Resolved since the last review: k." come from `feedback_state.json` as today. **Resolved-as-disclosed**: a finding is resolved when the value is gone from its location; or the line is now labelled (assumption/proposal); or the final message lists the value or `path:line` under an `Unverified`/`Assumptions` heading; for a failed step, when the final message names the failure; for a material, when it is now observed or the final message says under Unverified it was not used; for a test claim, when the claim is gone or a runner passed after the last edit. The note then lists disclosed items under Unverified. No consequences, no reputation: `actors.consequences` stays contract-and-provable only.

### 6.2 Process shape and watchdog (`adapters/zeroconfig.py`, R11/G6/G7)

The parent hook process records the final text, then runs the whole zero-config Stop decision in a child process `python -m vacant_network.trace.stopcheck zero --workspace … --session … --agent …` with `timeout=VACANT_STOP_WATCHDOG_S` (default 330 s < the 600 s Stop timeout of Claude, Codex and the bridges). The child checkpoints the workspace (HOOK_SCAN_S bound), runs the evidence pass and project checks, renders text/note, appends chain events, writes files, prints one JSON line `{"action","text","note","round","findings","pushable","ms"}`. Timeout ⇒ kill the process group, allow, `errors.jsonl` row `{"stage":"zero_stop","error":"watchdog 330s"}`, note "Vacant check did not run (timed out; error recorded)". Non-zero exit or unparsable output ⇒ allow + error row + the one-line note. `VACANT_ZERO_INPROC=1` runs it in-process (tests). The child is where V1/V4 faults (sitecustomize) land, so the parent's fail-open is exercised for real.

### 6.3 Text (`trace/review.py`) — exact strings in AGENT_TEXTS.md / the agent_texts field

Layout: header (1) + persona (1) + evidence lines (≤ 10) [+ "Resolved since the last review: k."] + footer (1) ⇒ ≤ `feedback.MAX_LINES` = 14 (G10). Priority: failed_step, unbacked_test_claim, project_check, unsourced_value (grouped per file), dropped_values, date_outside_data, unread_material (one grouped line), write_before_read. Overflow ⇒ "- … and N more points of the same kinds." (no `$VACANT_HOME` path: G10). Per-line guards, in order: quotes ≤ 80 chars, JSON-escaped; `feedback.feedback_ks1_clean(line, actor_tokens ∪ definition hashes)`; the second-person regex `\byou (ignored|failed|forgot|should have)\b`; path hygiene (every path-like token must be a deliverable, a material, a file written in the window, or a command the agent ran; never `node_modules/`, `.git/`, `.venv/`, `__pycache__/`, `$VACANT_HOME`). A failing line is replaced by the fixed substitute `- <path> line <n>: finding withheld (wording check)` (or `- a finding was withheld (wording check)`), a `review_withheld` counter goes on the chain and into evidence.json, and the count is reported per arm — never silently dropped. Constants are asserted clean at import (as `retry.py` does). Persona mode renders header + persona + footer only.

The review text is appended to the chain as a `prompt` event with `source="vacant_feedback"` as the last event of the Stop, so the chain count of `vacant_feedback` prompts equals the pushbacks (G4), OpenCode's re-report of the same text through `chat.message` is deduplicated by `Recorder.prompt`, and `Blamer.sources` never treats it as a task source (`_TASK_SOURCES` excludes it; group "sources" adds exact-text stripping as a second defence) — the S8 laundering check.

### 6.4 Header recognition

`capture.prompt_source` recognises text starting with `review.HEADER` as `vacant_feedback`, next to `FEEDBACK_HEADER`/`FLAG_HEADER` (prefix only, so a person quoting it mid-message is still a person). Without this, OpenCode TUI's review (a user message) would reset the round cap (endless loop) and become a value source. `ops/intake/mock_model.py` gets the same header in `MOCK_FEEDBACK_MARKS`.

## 7. Delivery note (`trace/delivery.py`)

Built at every allowed Stop (and at session end by `finalize --zero`) from `evidence_<n>.json`, `feedback_state.json` and the chain's `finding` events. Always written to `trace/projects/<key>/delivery.md` (three headings always present) and `delivery.json`; never into the workspace; never sent to the model.

delivery.md — **Checked**: N specifics in <files>: k traced to files or commands, d derived from <files>, u not attributable (why); materials opened m/M (names of the unopened); test/build runs seen (step, command, outcome); project checks run by Vacant on copies (command, before/after); coverage (unrecorded changes, steps without post, window basis). **Fixed**: findings opened then resolved, with the round, or "—". **Unverified**: still-open findings; disclosed assumptions/proposals; pre-existing failures; note-only "not opened" materials; the record-integrity line when the chain is broken. Never "verified", "correct", "right"; allowed: "traced", "opened", "ran", "checked against the record".

Screen text (≤ 6 lines, ≤ 600 chars; G8): nothing written in the window ⇒ empty; no finding ever ⇒ 1–2 lines (`Vacant: checked plan.md — 9 specifics traced to files or commands; materials opened 4/4.` + optional `Unverified: budget $40,000 (assumption); target +15% (proposal).`); fixed ⇒ `Vacant: 1 review round; fixed: 5 values, 4 materials opened.` + Unverified line + `Details: ~/.vacant/trace/projects/<key>/delivery.md`; rounds exhausted ⇒ `Vacant: 2 review rounds; still open: plan.md line 4 "October 1, 2026", line 5 "2026-09-20", line 8 "$50,000", line 11 "$1.2M" (no source found in what this task read); not opened: 4 materials. Details: <path>` wrapped to ≤ 6 lines; Vacant failure ⇒ `Vacant check did not run (error recorded).`; broken record ⇒ `Vacant: the record of this task does not verify (<why>); nothing was checked against it. Details: <path>`; D3 shape ⇒ the "checked" line only, and the file adds "Meaning and correctness were not checked; only sources were traced."

Channels: Claude `systemMessage` (existing render path via `record["user_message"]`); pi `ctx.ui.notify(note, "info")` from the extension when the decision carries `note` (print mode: stderr only when the extension detects no UI; unverified in 0.87.1, WP2 checks `types.d.ts`); OpenCode `client.tui.showToast` (name unverified in 1.18.32) with fallback `client.app.log`; Codex: the file, plus `systemMessage` if the Stop output supports it (unverified; WP2). `observe` mode: file only.

## 8. Per-agent behaviour

| agent | trace | final text | pushback (Stop continue) | note | what Vacant cannot do |
|---|---|---|---|---|---|
| Claude Code 2.1.281 | hooks (settings.json) | Stop `last_assistant_message` (in the binary's schema strings) | `{"decision":"block","reason"}` — `-p` and TUI (L-fake 9/9) | `systemMessage` | `--bare` and `disableAllHooks` kill hooks ⇒ arm C = arm A; a per-trial chain check makes it visible |
| Codex 0.156.1 | hooks (config.toml block + trust hashes) | `last_assistant_message` in the hook schema strings, event membership unverified ⇒ WP2 dumps a real Stop payload; fallback: claim checks off, documented | `{"decision":"block"}` — exec and TUI (L-fake 8/8) | file; `systemMessage` if supported | `apply_patch` failures emit no PostToolUse ⇒ `post_missing` (unreadable outcome, never a finding) |
| pi 0.87.1 | extension | `event.context.llmMessages` last assistant text (types.d.ts:602-622), ~10 JS lines | `agent_before_settle` → `{entries:[custom_message], continue:true}` — `-p` and TUI (L-fake 25/25); two consecutive continues must be re-proven for the 2-round cap (decision §8 item 4) | `ui.notify` / stderr | sub-agents are separate pi processes (VACANT_PI_PARENT keeps their turn end unreviewed) |
| OpenCode 1.18.32 TUI | plugin | `client.session.messages` (name to verify) | `client.session.prompt(review)` on `session.idle` (L-fake e2e_tui) | toast / log | the review is a user message on screen; the header keeps it from counting as a person request |
| OpenCode `run` | plugin | — | none: exits at the first idle | session-end `finalize --zero` writes delivery.md only | no pre-delivery redo; documented row "no pre-delivery review; session-end note only". Outside Harbor the redo route is the wrapper (`vacant do`, contract-typed today; optional `vacant do --zero` is WP9) |

Where an agent cannot be pushed back (OpenCode `run`, hooks off, any agent after the cap), the person still gets the note and `delivery.md`; nothing more is claimed. Exhibition wording for OpenCode always carries "TUI or wrapper".

## 9. Contracts stay the optional hard checks

A contract present ⇒ `decide_stop` runs exactly as today: contract claims decide intake, release and ledger outcomes; their findings enter reputation on `provable` only. v1 coexistence: with a contract, the evidence pass runs note-only at session end (`finalize`) and its stats go to `delivery.md`; no extra pushback lines (contract Stops keep today's latency; archived contract runs stay comparable). v2 (WP9): evidence lines appended below the contract lines within `MAX_LINES`, one shared round counter; they can push back after the contract accepts (like `vacant flag`), never change `outcome`, never enter reputation, never block `vacant release`. `vacant contract quick` remains the way to turn a recurring evidence finding into a hard check. Rounds files are separate (contract path vs workspace scope).

## 10. Logging, failure = fail open

- `events.jsonl` (hashes and names only) gains for zero Stops: `zero: true, round, findings, pushable, material_only, ms, trace_verified`.
- `errors.jsonl` rows carry `stage ∈ {mode, trace, final_text, zero_stop, evidence, projectcheck, delivery, display, finalize}`; the person sees at most one line, only at a Stop; per-step failures are silent and become gaps.
- `perf.jsonl` gains `{"event":"zero_stop","ms","phase":{checkpoint,evidence,derive,blame,projectchecks,render,write}}` (G5/G6).
- Chain events: `final_message`, `finding` (open/resolved, `claim="ev:*"`), `prompt` (`vacant_feedback`), `coverage{"review_withheld": k}`.
- Fail-open matrix: evidence raises (V1) ⇒ child exits non-zero ⇒ allow + error row + 1 line; chain truncated (V2) ⇒ `verify()` false ⇒ allow, note "record does not verify", no pushback built on the broken record, `vacant trace verify` BROKEN; `~/.vacant` read-only (V3) ⇒ every write raises inside try/except, hooks allow, nothing recorded ("when writable"); evidence hangs (V4) ⇒ watchdog 330 s ⇒ allow; dangling hooks after `pipx uninstall` (V5) ⇒ the bridges resolve to allow on spawn error or missing interpreter; Claude/Codex hook commands fail with a shell error and continue (non-blocking exit code) — whether Claude prints a line per failed hook in the TUI is unverified (risk); the documented order is `vacant uninstall` then `pipx uninstall`, and `vacant uninstall` prints it.
- Never a value source: Vacant's review text, its retry text, the agent's scheduled prompts, teammate envelopes (group "sources" rules reused unchanged; the review header is registered with them).

## 11. Installation (minimal, as the audit proposes)

Exactly two commands, no flags, no prompts, no key, no contract, no env var, no restart:

```
pipx install vacant-network        # (pip install --user works too; then ~/.local/bin must be on PATH)
vacant install
```

`vacant install` (≤ 15 s, ≤ 10 lines, exit 0): detects agents with `shutil.which`; per detected agent writes only the hook/extension/plugin/config block (no SKILL.md unless `--skill`: R2/G11 — the default install must be the benchmark's arm C); records every op with sha256 and pre-existing flag in `install.json` (schema 2, `mode: evidence`); prints one compact line per agent, one "done" line, one line naming the data directory and the removal command. Re-running is idempotent (`persistent_hook_file` de-dup already prevents double hooks). The first hook that touches the intake layer still generates the four local Ed25519 keypairs silently under `~/.vacant/intake/keys` (0700/0600); the "done" line names the data directory so this is not hidden. `vacant --help` lists `install`, `uninstall`, `do`, `contract`, `trace`, `flag`, `hook` (thin subparsers or a "see also" epilog).

`vacant uninstall`: key-level reversal as today (byte-identical config when unedited; the person's later keys kept); prints "Data directory: ~/.vacant — remove it with `vacant uninstall --purge` (or `rm -rf ~/.vacant`); then `pipx uninstall vacant-network`". `--purge` removes `$VACANT_HOME` non-interactively and prints what it removed. After purge + pipx uninstall the `$HOME` diff is empty except the agent's own session logs (G13).

## 12. Performance budget

- Per tool step: mechanics unchanged (`capture.observe`, scan bounded by `HOOK_SCAN_S`); the only addition is one ~1 KB `install.json` read per hook process — G5 baseline 136/194 ms holds; ≤ 1k files median ≤ 250 ms, p95 ≤ 600 ms; 10k files p95 ≤ 1.2 s; first look > 8 s goes to the background.
- Stop without project checks: checkpoint scan (≤ 8 s bound, normally ms) + child interpreter start (~150 ms with cryptography) + extraction O(deliverable bytes) + blame per value (cap 60 values/file, 20 files ⇒ ≤ 1,200 blames, ms each on ≤ 1k-file traces) + derive (≤ 20 tables, ≤ 50k cells, ≤ 5k observed numbers) + render/write. Target p95 ≤ 2 s at ≤ 1k files, ≤ 5 s at 10k, ≤ 10 s at 40k (G6). Caps degrade to "not checked: too many values" in the note, never to a timeout.
- Project checks: ≤ 120 s each, ≤ 300 s total, copies only, skipped above 20k files.
- Whole Stop: watchdog 330 s, then fail open.
- Measurement: `perf.jsonl` phases; `ops/usersim` computes C−A intervals per step and Stop p95.

## 13. Compatibility with the concurrent xpath fixes

Review/retry text never a value source (recorded as `vacant_feedback`; `_TASK_SOURCES` excludes it; header registered in `prompt_source`; S8 asserts round-2 origin of `October 1, 2026` is still agent/unsourced and never "in the task message"). Locators stay inside the deliverable (evidence.py names only deliverables, prompt-named materials, window-written files and the agent's own commands; review.py's path guard enforces it, N3b). Agent text KS-1 clean with no actor ids (`feedback_ks1_clean` with the chain's actor tokens plus the definition hashes group "consequences" adds; no second person; substitute line on failure). A person quoting feedback in their own message is still a person (prefix match only); `new_request` resets on every `user` prompt (S8 turn 2). Stable finding ids across rounds (ids from scope, claim, path, line, value; verifier wording never enters the id). File ownership: this design lands after the xpath branches merge; `hook.py`/`capture.py` edits are limited to the call sites in §2/§4; `stopcheck.py`/`finalize.py` gain a twin function and a CLI entry (group "consequences" edits `_anchor`/verify, not touched); `hookpolicy.py` gains `decide_stop_zero` and a scope parameter (group "authority" edits `decide_pre_tool`/`_AUTHORITY_RE` only).

## 14. How the acceptance scenarios become automated tests

- **L0 unit (pytest, no agents, seconds)**: synthetic chains built with `Recorder` in a tmp `VACANT_HOME` from the fixture workspaces (`accept/fixtures/<id>`), replaying each script step as `pre`/`post` with pi-shaped payloads through `hook.handle` (no contract, `VACANT_ZERO_INPROC=1`), asserting the review needles from `expect.json.round1_feedback_must_name`, pushback counts, finding-id stability across rounds, KS-1/actor/path guards, note line counts, evidence.json classifications, and 0 findings on every N/D2/D3 fixture. V1/V4 via monkeypatching `evidence_pass` (raise / sleep with `VACANT_STOP_WATCHDOG_S=2`), V2 via truncating `chain.ndjson`, V3 via `chmod` on the tmp home. I/U via `vacant install`/`uninstall` against a tmp `HOME` with fake agent binaries on PATH.
- **L1 L-fake on the host** (`ops/accountability/e2e_trace.py` + `e2e_tui.py` extended with a `--zero` scenario set; real binaries from the scratchpad, mock model): the four bridges' real payload shapes, final-text forwarding, the OpenCode-TUI user-message round trip, two consecutive pi continues.
- **L2 simulated user in Docker** (`ops/usersim/run.py`, accept spec §5): the only allowed setup (two commands), every surface, 3 repetitions, all gates G1–G15 per cell.
Evidence level stays L-fake; real-model gain is the pre-registered DABstep run and may start only after G1–G15 pass (產品原則 4).