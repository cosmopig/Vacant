export const meta = {
  name: 'candidate2-fix-round',
  description: 'Fix the 10 reproduced findings in the test_run_failed check, replay it on real R530 traces for precision, then re-review adversarially',
  phases: [
    { title: 'Fix', detail: 'same worktree branch; all 10 fixes with regression tests; R530 replay' },
    { title: 'Review', detail: 'two lenses, each finding independently reproduced' },
  ],
}
const S = args.scratch
const WT = '/home/user/Vacant/.claude/worktrees/wf_47b337c8-2fc-1'
const COMMON = `
Repo /home/user/Vacant (read CLAUDE.md). The implementation of the new zero-config send-back kind 'test_run_failed' lives in the git worktree ${WT} on branch worktree-wf_47b337c8-2fc-1 (commit ef9b52bb, based on 9d605b90). Design and guards: decisions/DECISION_20260926_BIGGER_EFFECT_REVIEW.md §二 row 2. The previous review's full findings: ${S}/../tasks/w3jg6ogx4.output is not readable to you, so they are restated below.
A preregistered batch is running on this machine: do NOT start docker containers or builds; do NOT touch the proxies on :18900/:18901 or ${S}/local/heldout_v34; do not read credential files. When running the worktree's code, set PYTHONPATH=${WT} and assert the imports come from the worktree (the venv otherwise imports the main checkout).`

const FINDINGS10 = `
The 10 reproduced findings to fix (each needs a regression test that fails before the fix):
1. Command splitting ignores quotes and heredocs: grep -E "pytest|jest" (no match, exit 1), rg "pytest|tox", sed -i "s|pytest|…|", a README heredoc line '    pytest -q', a git commit -m body line 'make test' are all counted as runner runs → false send-backs. Fix: quote-aware tokenisation (shlex with punctuation_chars; unparseable ⇒ not a runner), drop heredoc bodies, split only at unquoted operators, count a segment only when its first token after the wrappers is a runner; segments whose command is grep/rg/ag/sed/cat/less/head/tail/echo/printf/git are never runners.
2. Non-failure exits read as failures: timeout wrapper 124, 137/143 and codes ≥128, the tool's own 'Command timed out', 'terminated without an exit code', 'aborted', pytest exit 5 (no tests collected). Fix: all of these ⇒ status unknown ⇒ note only, never a send-back. For pi read the tool output's final appended status line if present.
3. Disclosure missed: Chinese (沒過/未通過/不通過/沒有通過/還是失敗/紅) and English ('doesn't pass', 'don't pass', 'not passing', 'pre-existing', 'already failing', 'already broken', 'unrelated', 'still red', 'is red'), and '\\w*Error\\b'. Broaden the disclosure check for this kind (do not change MENTIONS_FAILURE's behaviour for the other kinds unless a test shows it is safe).
4. The request is ignored: when the person's request asks for a failing/red test ('red first', 'reproduce the bug', 'failing test', 'don't fix', '先不要修', '寫一個會失敗的測試') or says to only run/report and not change files ('just run', 'don't change', '不要改', '只要跑'), make it note only. Also reword the send-back neutral and disclose-first: "Step N ran \`cmd\` and it ended with a failure (exit status X); no later run of it passed, and the final message does not say whether this was expected. Say in the final message whether this failure is expected, was already there before this request, or is outside what was asked; if it comes from this request's changes, fix it and run it again." (KS-1 clean, no actor, no output quoted.)
5. A piped/listed runner (runner not the last segment of a pipeline or list, e.g. 'pytest | tail', 'pytest; echo done') has an unreliable exit status ⇒ unknown (unless 'set -o pipefail' is in the same command) — so it can neither be sent back nor count as a later passing run; the note's ok wording must be 'no failure was recorded', and a finding counts as redone only when a later run with a reliable status passed.
6. 'Changed after the failing run' must count any recorded file change (not SKIP_DIRS) after it, not only CODE_EXT ⇒ note only.
7. Runner detection narrower than RUNNERS: 'uv run --frozen pytest', 'poetry run -q pytest', 'uvx pytest', 'python3.11 -m pytest', '/usr/bin/python3.12 -m pytest', 'yarn jest', "bash -c 'pytest -q'", 'if ! pytest; then …' are missed. Use RUNNERS.search as the spec says for what is a test run (both 'last run' and 'later run passed'), and use the stricter first-token filter only to EXCLUDE mention-only segments (fix 1).
8. Guard 5 bypass: suppress test_run_failed whenever _test_claim returned sub='failed' for any step (or have both share one runner list and one 'last run').
9. finding_id for test_run_failed must key on the normalised command (like failed_step), so a different command gets a new id and the same command failing again stays '(still open)'; notes say 'sent back earlier' only for the same command.
10. Covered by 5 (note wording) — make sure delivery.md never says a failure was redone when the only later run had an unreliable status.`

phase('Fix')
const fix = await agent(`${COMMON}
${FINDINGS10}
Work in the worktree ${WT} (cd there; commit on its branch). Implement all fixes with regression tests in tests/test_zero_testrun.py (keep the existing 38 passing or update them only where the behaviour intentionally changed, and say which). Run: the zero-config, trace, adapters test files (.venv/bin/python -m pytest tests/test_zero_*.py tests/test_trace_*.py tests/test_adapters_*.py -q with PYTHONPATH=${WT}), CI's mypy scope and ruff selection (see .github/workflows/ci.yml). Mutation-check the new guards.
THEN an offline replay on REAL traces with test runs (no model, no docker): runs/g_r530_s{1,2,3}_{1003,1004}_{1,2} in the repo (see runs/INDEX.md and decisions/*R530* for the format; SOLO arm = the agent alone; each cell has the agent's bash steps with exit codes and outputs, its final message, and hidden-test outcomes). Feed each SOLO cell's steps through the real hook path (hook.handle with the 'claude' event shapes — UserPromptSubmit with the task text, PreToolUse/PostToolUse(Failure) per bash step with 'Exit code N' on failure, Stop with last_assistant_message) into a fresh VACANT_HOME with install.json mode=evidence, and record whether test_run_failed fires (send-back vs note-only) at the final Stop. Report: fires, note-only, and precision/recall against the hidden-test outcome (a send-back on a cell that was fully correct is a false send-back). The decision's gate is precision ≥ 0.8 and 0 send-backs on question turns. Save the replay script and its per-cell output under ${S}/testrun_r530/ and copy the script into the worktree at ops/eval/replay_r530_testrun.py (Chinese docstring).
Commit in the worktree with a Chinese message ending with:
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01MubgqryqvfE5urfHU21Pvd
Report: commit hash, per-finding fix + test name, test/mypy/ruff results, mutation results, R530 replay numbers.`, { label: 'fix', phase: 'Fix' })

phase('Review')
const FINDINGS = { type: 'object', properties: { findings: { type: 'array', items: { type: 'object', properties: {
  title: { type: 'string' }, scenario: { type: 'string' }, severity: { type: 'string' }, fix: { type: 'string' } },
  required: ['title', 'scenario', 'severity'] } } }, required: ['findings'] }
const VERDICT = { type: 'object', properties: { real: { type: 'boolean' }, evidence: { type: 'string' } }, required: ['real', 'evidence'] }
const LENSES = [
  'FALSE SEND-BACKS in real interactive use of pi / Claude Code (Codex/OpenCode do not report errors): enumerate realistic sessions (TDD, pre-existing failures, monorepos, flaky tests, lint vs test, build commands, the agent asking a question, the person asking only to run, long test runs killed, commands in scripts/Makefiles) and try to make the fixed code send back wrongly or loop. Also check the R530 replay numbers the fixer reported by re-running its script.',
  'CORRECTNESS of the 10 fixes and INVARIANTS: each fix actually closes its finding (re-run the previous repro ideas), KS-1 and no-actor on every rendered line, no output/values quoted, byte-identical requests when nothing is wrong, Vacant errors never block, rounds limit, finding ids, delivery-note lines literally true, no regression in the other five kinds.',
]
const reviews = await pipeline(
  LENSES,
  lens => agent(`${COMMON}
Fix report: ${String(fix).slice(0, 5000)}
Review the worktree's latest commit through this lens; report only real defects with a concrete failing scenario: ${lens}`, { label: 'review', phase: 'Review', schema: FINDINGS }),
  (r, lens, i) => parallel((r && r.findings || []).map((f, j) => () =>
    agent(`${COMMON}
Independently reproduce or refute this finding against the worktree's latest commit with the real hook.handle path (tests under /tmp/claude-0/cand2_verify2/). Default to real=false if you cannot reproduce it.
FINDING: ${JSON.stringify(f)}`, { label: `verify:${i + 1}.${j + 1}`, phase: 'Review', schema: VERDICT }).then(v => ({ ...f, verdict: v })))),
)
return { fix, findings: reviews.flat().filter(Boolean) }
