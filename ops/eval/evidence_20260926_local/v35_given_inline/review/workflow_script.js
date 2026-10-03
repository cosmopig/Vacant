export const meta = {
  name: 'review-v35-given-inline',
  description: 'Adversarially review the v3.5 change: a named file whose text is already in the request counts as read',
  phases: [
    { title: 'Review', detail: 'two lenses: hidden real misses, and correctness/invariants' },
    { title: 'Verify', detail: 'each finding independently reproduced through the real hook path' },
  ],
}
const S = args.scratch
const COMMON = `
Repo /home/user/Vacant (read CLAUDE.md, especially the zero-config section and the product principle). The change under review is UNCOMMITTED in the main checkout's working tree; its diff is saved at ${S}/v35.diff (read it). It adds Evidence.given_inline() in vacant_network/trace/evidence.py: a file named in the person's request (or in a named folder) counts as read ('observed') when at least 90% of its non-blank text (whitespace-collapsed, per line, weighted by characters) appears in the whitespace-collapsed request text; files over 64 KB or with NUL bytes are skipped; the result lists them as given_in_request and the delivery note (zerostop.py) says 'content already in the request'. Motivation: an offline replay of 59 real recorded coding runs (R530 SOLO; replay script ${S}/r530_v34/replay_v34.py, v3.4 results ${S}/r530_v34/all/cells.jsonl) where the prompt pastes goal.md and contract.md in full AND lists them as workspace files; v3.4 sent back 58/59 runs including all 20 fully correct ones, mostly 'unread goal.md/contract.md'.
Constraints: a preregistered batch is running on this machine: do NOT start docker containers or builds; do NOT touch the proxies on :18900/:18901, ${S}/local/, ${S}/codesuite/; do not read credential files; do NOT modify files under /home/user/Vacant (write your own test files only under /tmp/claude-0/v35_review/). Run python with PYTHONDONTWRITEBYTECODE=1 (a stale .pyc bit us earlier). Tests use the real hook path like tests/test_zero_evidence.py (Agent class).`
const FINDINGS = { type: 'object', properties: { findings: { type: 'array', items: { type: 'object', properties: {
  title: { type: 'string' }, scenario: { type: 'string' }, severity: { type: 'string' }, fix: { type: 'string' } },
  required: ['title', 'scenario', 'severity'] } } }, required: ['findings'] }
const VERDICT = { type: 'object', properties: { real: { type: 'boolean' }, evidence: { type: 'string' } }, required: ['real', 'evidence'] }
const LENSES = [
  'HIDDEN REAL MISSES: find realistic requests where the new rule marks a file as given although the agent really needed to open it and did not (so a real unread send-back is lost): e.g. the person pasted an OLD version while the file on disk changed, pasted most of a file but the key part is in the missing 10%, very short/generic files (\"TODO\", a single header line, JSON braces) matching by accident, a data file whose few rows are all quoted, a file whose lines are all short common tokens, the file content appearing in the request only because the agent itself wrote it earlier in the SAME request window (can agent-written text end up in prompt_texts?), a file named in a folder where siblings are given. Judge each by the product principle (send back only what should be redone; do not send back correct work). Only report cases where a real person would plausibly lose something.',
  'CORRECTNESS AND INVARIANTS: the code does what the docstring says (per-line matching vs re-wrapped paragraphs, the 90% threshold weighting, size and NUL guards, index at the window start vs later edits, files that are deliverables, dir members, performance with a 200 KB prompt and 30 candidate files), the delivery note lines are literally true (opened / content already in the request / not opened; the screen summary \"N/M given file(s) opened\" still counts correctly), KS-1 and no-actor unaffected, nothing changes when no file is named (byte-identical model requests; run the existing simuser/byte-identity tests if any exist for zero-config), no regression in tests/test_zero_*.py tests/test_trace_*.py tests/test_adapters*.py. Also re-run the R530 replay for 2 of the 12 runs with the working tree (python ${S}/r530_v34/replay_v34.py --repo /home/user/Vacant --out /tmp/claude-0/v35_review/replay --runs g_r530_s1_1003_1 g_r530_s2_1004_2 --inproc) and check the given_in_request decisions cell by cell against the actual prompt text.',
]
phase('Review')
const reviews = await pipeline(
  LENSES,
  lens => agent(`${COMMON}\nReview the change through this lens; report only real defects with a concrete failing scenario (inputs → wrong outcome): ${lens}`, { label: 'review', phase: 'Review', schema: FINDINGS }),
  (r, lens, i) => parallel((r && r.findings || []).map((f, j) => () =>
    agent(`${COMMON}\nIndependently reproduce or refute this finding against the working tree with the real hook.handle path (your tests under /tmp/claude-0/v35_review/verify_${i}_${j}/). Default to real=false if you cannot reproduce it or if the outcome would not plausibly harm a real person.\nFINDING: ${JSON.stringify(f)}`, { label: `verify:${i + 1}.${j + 1}`, phase: 'Verify', schema: VERDICT }).then(v => ({ ...f, verdict: v })))),
)
return { findings: reviews.flat().filter(Boolean) }
