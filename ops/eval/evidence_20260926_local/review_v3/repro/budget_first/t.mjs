import { BUDGET_RE } from "./re.js";
function readBudget(text) {
  try {
    const m = BUDGET_RE.exec(String(text || ""));
    const n = m ? Number(m[1]) : NaN;
    return Number.isFinite(n) && n >= 4 ? n : null;
  } catch (e) { return null; }
}
const harbor = "\n\nYou have a hard budget of 15 model turns. Complete the task and provide your final answer within that budget.";
const cases = [
  "Use at most 6 steps for a plan.",
  "Plans should have up to 8 steps.",
  "limit yourself to 10 iterations",
  "Keep PRs small: no more than 5 steps per migration.",
  "Retry at most 3 times.",
  "Use at most 2 steps.",
];
for (const c of cases) {
  const sp = "preamble\n<project_context>\n" + c + "\n</project_context>" + harbor;
  console.log(JSON.stringify(c), "->", readBudget(sp));
}
console.log("harbor only ->", readBudget("preamble" + harbor));
