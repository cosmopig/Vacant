// Fake pi driving the real Vacant pi extension: stated 15-turn budget, every turn runs a bash tool;
// the cap aborts on turn 15. FINAL=1 makes turn 15 a final answer instead (the v3.2 path).
import ext from "./ext.mjs";
const h = {};
ext({ on: (n, f) => { (h[n] = h[n] || []).push(f); } });
const ctl = new AbortController();
const SP = "Be brief.\n\nYou have a hard budget of 15 model turns.";
const ctx = { cwd: process.env.APP, hasUI: false, signal: ctl.signal,
              sessionManager: { getSessionId: () => "S1" }, getSystemPrompt: () => SP };
const FINAL = process.env.FINAL === "1";
const ASK = "Answer the question using the files in data/. Question: what is the total amount? " +
            "Write the answer to /app/answer.txt as a single number.";
await h.before_agent_start[0]({ prompt: ASK, systemPrompt: SP }, ctx);
for (let t = 1; t <= 15; t++) {
  const fin = FINAL && t === 15;
  if (!fin) {
    const input = { command: "ls data" };
    await h.tool_call[0]({ toolName: "bash", input, toolCallId: "c" + t }, ctx);
    await h.tool_result[0]({ toolName: "bash", input, toolCallId: "c" + t,
                             content: [{ type: "text", text: "sales.csv" }], isError: false }, ctx);
  }
  const ev = { message: { stopReason: fin ? "stop" : "toolUse",
                          content: [{ type: "text", text: fin ? "The answer is 2045." : "" }] },
               toolResults: fin ? [] : [{ toolCallId: "c" + t }], entries: [] };
  if (t === 15) ctl.abort();
  await h.turn_end[0](ev, ctx);
}
const t0 = Date.now();
await h.session_shutdown[0]({ reason: "quit" }, ctx);
console.log(JSON.stringify({ session_shutdown_ms: Date.now() - t0 }));
