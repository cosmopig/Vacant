export const meta = {
  name: 'review-v36-reminder-off',
  description: 'Adversarially review v3.6: the turn-budget reminder is off by default and opt-in via vacant install --budget-reminder',
  phases: [
    { title: 'Review', detail: 'two lenses: default really off everywhere; opt-in and invariants' },
    { title: 'Verify', detail: 'each finding independently reproduced' },
  ],
}
const S = args.scratch
const COMMON = `
Repo /home/user/Vacant at commit eb56c02e (read CLAUDE.md zero-config section). Change under review: git show eb56c02e (v3.6): vacant_network/adapters/mode.py budget_reminder_on(), vacant_network/trace/budget.py turn_check early-return, vacant_network/adapters/cli.py install --budget-reminder/--no-budget-reminder, tests/test_zero_budget.py test_v36_*, docs. Human decision (2026-09-27): the reminder is OFF by default; everything else (five send-back kinds, last-turn narrowing, cut-off notes) unchanged.
Constraints: an experiment may run on this machine: do NOT start docker containers or builds; do NOT touch proxies on :18900/:18901 or anything under ${S}/local; do not read credential files; do NOT modify files under /home/user/Vacant (write your own tests under /tmp/claude-0/v36_review/). Use PYTHONDONTWRITEBYTECODE=1. Drive the real hook path (hook.handle('pi', 'turn_check', ...) etc.) like tests/test_zero_budget.py.`
const FINDINGS = { type: 'object', properties: { findings: { type: 'array', items: { type: 'object', properties: {
  title: { type: 'string' }, scenario: { type: 'string' }, severity: { type: 'string' }, fix: { type: 'string' } },
  required: ['title', 'scenario', 'severity'] } } }, required: ['findings'] }
const VERDICT = { type: 'object', properties: { real: { type: 'boolean' }, evidence: { type: 'string' } }, required: ['real', 'evidence'] }
const LENSES = [
  'DEFAULT REALLY OFF: find any path where, without an explicit opt-in, a reminder (or any other Vacant text caused by the turn budget) still reaches the model: other agents (claude/codex/opencode) if they have a budget path, the pi JS extension (vacant_network/adapters/agents.py PI_EXTENSION) doing something on its own at turn_end, VACANT_MODE/VACANT_TRACE env combinations, old install.json files, a contract present, the evaluation installer ops/eval/harbor_vacant.py (the C arm must get exactly what a user gets from `vacant install`), and whether a stale state/zero_state file from an earlier opted-in run can re-enable it. Also: does turning it off change anything else that the human did not ask to change (last-turn narrowing of Stop, cut-off notes, delivery notes wording that still claims a reminder was sent)?',
  'OPT-IN AND INVARIANTS: the install flag semantics (on/off/unspecified keeps previous; idempotent re-install; uninstall/re-install; the key survives Manifest.save for other agents), KS-1 and no-actor unaffected, turn_check returns exactly {"action":"allow","reason":""} when off (byte-identical requests), no exceptions escape the hook when install.json is missing/corrupt/unreadable, docs (README, CLAUDE.md, decisions V3 §十, `vacant install --help`) literally true, and run tests/test_zero_*.py tests/test_trace_*.py tests/test_adapters*.py.',
]
phase('Review')
const reviews = await pipeline(
  LENSES,
  lens => agent(`${COMMON}\nReview through this lens; report only real defects with a concrete failing scenario: ${lens}`, { label: 'review', phase: 'Review', schema: FINDINGS }),
  (r, lens, i) => parallel((r && r.findings || []).map((f, j) => () =>
    agent(`${COMMON}\nIndependently reproduce or refute this finding at commit eb56c02e with the real hook path (tests under /tmp/claude-0/v36_review/verify_${i}_${j}/). Default to real=false if you cannot reproduce it.\nFINDING: ${JSON.stringify(f)}`, { label: `verify:${i + 1}.${j + 1}`, phase: 'Verify', schema: VERDICT }).then(v => ({ ...f, verdict: v })))),
)
return { findings: reviews.flat().filter(Boolean) }
