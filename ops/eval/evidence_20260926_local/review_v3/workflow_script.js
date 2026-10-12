export const meta = {
  name: 'review-zero-config-v3',
  description: 'Adversarially review the zero-config v3 diff for bugs that could affect the running local batch or users',
  phases: [
    { title: 'Find', detail: 'three lenses over the v3 diff' },
    { title: 'Verify', detail: 'independent reproduce-or-refute per finding' },
  ],
}

const REPO = '/home/user/Vacant'
const DIFF = `git -C ${REPO} diff 7f7ec52f 11f91f87 -- vacant_network tests/test_zero_budget.py ops/eval/harbor_vacant.py ops/intake/mock_model.py`
const CTX = `You review the "zero-config v3" change of the Vacant repo (read ${REPO}/decisions/DECISION_20260926_ZERO_CONFIG_V3.md first). Get the diff with: ${DIFF}
A preregistered evaluation is RUNNING RIGHT NOW with the frozen v3 wheel (C2) built from commit 11f91f87 on gemma-4-12b via pi 0.87.1 inside Harbor (max_turns=15, whose extension appends "You have a hard budget of 15 model turns" to the system prompt). pi 0.87.1 sources: /tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/agents/node_modules/@earendil-works/pi-coding-agent/dist ; Harbor pi agent: /tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/study/src/harbor/src/harbor/agents/installed/pi.py .
Rules: read-only for ${REPO} (write scratch only under /tmp/claude-0/review_v3/). Report only real defects with a concrete failure scenario (inputs/state -> wrong behavior), file:line, and severity (blocker: invalidates the running experiment or breaks users; major; minor). No style nits.`

const FINDING = {
  type: 'object',
  properties: { findings: { type: 'array', items: { type: 'object', properties: {
    title: { type: 'string' }, file_line: { type: 'string' }, severity: { type: 'string', enum: ['blocker', 'major', 'minor'] },
    scenario: { type: 'string' }, fix: { type: 'string' } }, required: ['title', 'file_line', 'severity', 'scenario', 'fix'] } } },
  required: ['findings'],
}
const LENSES = [
  ['experiment-validity', 'Could anything in v3 make the running A/C1/C2 comparison invalid or biased? e.g. the reminder firing when it should not (file exists, sub-agent, wrong turn count because TURNS counts differently from Harbor completedTurns, BUDGET parsing), exceeding 15 model requests, changing the first request (system prompt) vs A, the Stop narrowing misfiring, extra model calls from continue:true, state carried across runs, the ended() note writing into the workspace, hook latency at turn_end causing timeouts. Trace the JS extension logic against pi 0.87.1 runner/agent-session code.'],
  ['python-correctness', 'Bugs in vacant_network/trace/budget.py, zerostop.py (stop turns_left/budget, ended), hook.py routing (turn_check, session_end zero branch, _budget_of), review.py (render_nudge, KS-1 guards), recorder EVENT_TYPES, capture/feedback header handling (is NUDGE_HEADER correctly treated as Vacant feedback everywhere the other headers are, e.g. capture.classify_prompt, blame, mock?). Edge cases: requested_outputs empty, relative vs absolute paths, workspace not the git root, multiple outputs, new person request resets counts, observe mode, errors -> fail open.'],
  ['product-principles', 'Check against CLAUDE.md product principles: zero-config, install-minimal, "no problem => model sees byte-identical requests", accountability wording (KS-1: no responsibility/punishment words, no actor identity), fail-open, and honesty boundaries (does any text or code claim more than it does; does the session_end note fire for other agents (Claude/Codex/OpenCode) in ways that mislead a person, e.g. every interactive session end without a Stop). Also check the tests actually test what they claim.'],
]

phase('Find')
const found = await parallel(LENSES.map(([k, lens]) => () => agent(`${CTX}\nLens: ${lens}`, { label: `find:${k}`, phase: 'Find', schema: FINDING })))
const all = found.filter(Boolean).flatMap(r => r.findings)
log(`${all.length} candidate findings`)

phase('Verify')
const VERDICT = { type: 'object', properties: { real: { type: 'boolean' }, severity: { type: 'string', enum: ['blocker', 'major', 'minor', 'none'] }, evidence: { type: 'string' }, affects_running_experiment: { type: 'boolean' } }, required: ['real', 'severity', 'evidence', 'affects_running_experiment'] }
const verified = await parallel(all.map((f, i) => () => agent(`${CTX}\nIndependently try to REPRODUCE or REFUTE this finding. Run code where possible (python with ${REPO}/.venv/bin/python, node for the extension). Default to real=false if you cannot demonstrate it.\nFinding: ${JSON.stringify(f)}`, { label: `verify:${i}`, phase: 'Verify', schema: VERDICT }).then(v => ({ ...f, verdict: v }))))
return { findings: verified.filter(Boolean) }