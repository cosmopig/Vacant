const BUDGET_RE = /\b(?:budget|limit|maximum|max|at most|no more than|up to)\b[^.\n]{0,40}?\b(\d{1,4})\s+(?:model\s+|agent\s+|llm\s+)?(?:turns|steps|iterations)\b/i;
function readBudget(text) {
  const m = BUDGET_RE.exec(String(text || ""));
  const n = m ? Number(m[1]) : NaN;
  return Number.isFinite(n) && n >= 4 ? n : null;
}
for (const s of [
  "You have a hard budget of 15 model turns. Complete the task",
  "Break every change into at most 5 steps and commit after each.",
  "Plans should have up to 8 steps.",
  "When debugging, limit yourself to 10 iterations before asking.",
  "Keep answers short.\n\nYou have a hard budget of 15 model turns.",
  "Use at most 6 steps for a plan.\n\nYou have a hard budget of 15 model turns.",
]) console.log(JSON.stringify(s).slice(0,70), "->", readBudget(s));
