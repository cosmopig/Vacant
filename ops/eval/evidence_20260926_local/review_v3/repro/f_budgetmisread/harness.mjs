import { buildSystemPrompt } from "/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/agents/node_modules/@earendil-works/pi-coding-agent/dist/core/system-prompt.js";
import ext from "/tmp/claude-0/review_v3/f_budgetmisread/ext.mjs";
import { rmSync } from "node:fs";
rmSync("/tmp/claude-0/review_v3/f_budgetmisread/hooklog.txt", { force: true });

const agentsMd = "# Project notes\n\n- Use pnpm, not npm.\n- Keep any retry loop to at most 10 iterations.\n- Run the linter before committing.";
const sp = buildSystemPrompt({ cwd: "/home/u/proj", selectedTools: ["read","bash","edit","write"],
  toolSnippets: { read: "Read file contents", bash: "Execute bash commands", edit: "Edit files", write: "Write files" },
  contextFiles: [{ path: "/home/u/proj/AGENTS.md", content: agentsMd }] });
console.log("system prompt has project_instructions:", sp.includes("<project_instructions"));

const H = {};
const pi = { on: (n, f) => { (H[n] ||= []).push(f); } };
ext(pi);
const ctx = { cwd: "/home/u/proj", sessionManager: { getSessionId: () => "S1" }, getSystemPrompt: () => sp, signal: { aborted: false } };

// Interactive session, no cap enforced by anyone. Request 1: 6 tool turns + final answer.
async function request(prompt, toolTurns) {
  for (const f of H.before_agent_start) await f({ prompt, systemPrompt: sp }, ctx);
  for (let i = 0; i < toolTurns; i++)
    for (const f of H.turn_end) await f({ toolResults: [{}], entries: [] }, ctx);
  for (const f of H.turn_end) await f({ toolResults: [], entries: [] }, ctx);   // final-answer turn
  for (const f of H.agent_before_settle) await f({ entries: [], context: { llmMessages: [] } }, ctx);
}
await request("Refactor utils.py", 6);                       // turns 1..7
await request("Now write a summary of the changes to NOTES.md", 5);  // turns 8..13
await request("Fix the failing test in tests/test_utils.py", 10);    // turns 14..24
