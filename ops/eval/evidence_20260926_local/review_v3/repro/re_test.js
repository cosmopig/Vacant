const {BUDGET_RE} = require('/tmp/claude-0/review_v3/budget_re.js');
function readBudget(text) {
  try {
    const m = BUDGET_RE.exec(String(text || ""));
    const n = m ? Number(m[1]) : NaN;
    return Number.isFinite(n) && n >= 4 ? n : null;
  } catch (e) { return null; }
}
const samples = [
 'Break large changes into at most 6 steps',
 'Retry flaky tests up to 5 iterations',
 'no more than 8 steps per PR',
 'Keep functions short; limit loops to 10 iterations.',
 'You have a hard budget of 15 model turns. Complete the task and provide your final answer within that budget.',
 '<project_instructions path="/repo/AGENTS.md">\n- Break large changes into at most 6 steps\n</project_instructions>\n\nYou have a hard budget of 15 model turns.',
];
for (const s of samples) console.log(JSON.stringify(s.slice(0,60)), '->', readBudget(s));
