import vacant from "./vacant_ext.mjs";
import { rmSync, readFileSync, existsSync } from "node:fs";
const log = "/tmp/claude-0/review_v3/budget_first/hook.log";
const agentsMd = process.argv[2];
if (existsSync(log)) rmSync(log);
const H = {};
const pi = { on: (n, f) => { (H[n] ||= []).push(f); } };
vacant(pi);
// Harbor's max-turns extension (registered after, as in harbor order: vacant installed extension first? both orders tested)
const harborText = "\n\nYou have a hard budget of 15 model turns. Complete the task and provide your final answer within that budget.";
const base = "You are an expert coding assistant operating inside pi...\n<addendum>\n...\n</addendum>\n<project_context>\nProject-specific instructions and guidelines:\n\n<project_instructions path=\"/app/AGENTS.md\">\n" + agentsMd + "\n</project_instructions>\n</project_context>\n<cwd>\n/app\n</cwd>";
const full = base + harborText;
const ctx = { cwd: "/app", sessionManager: { getSessionId: () => "s1" }, getSystemPrompt: () => full, signal: { aborted: false } };
await H.before_agent_start[0]({ prompt: "write /app/answer.txt", systemPrompt: full }, ctx);
const nudges = [];
for (let t = 1; t <= 15; t++) {
  const r = await H.turn_end[0]({ toolResults: [{}], entries: [] }, ctx);
  if (r) nudges.push(t);
}
console.log("AGENTS.md:", JSON.stringify(agentsMd), " nudges after turns:", nudges);
const lines = readFileSync(log, "utf8").split("\n").filter(l => l.startsWith("turn_check"));
console.log(lines.join("\n"));
