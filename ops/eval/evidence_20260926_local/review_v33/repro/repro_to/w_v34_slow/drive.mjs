import ext from "./ext.mjs";
const h = {};
ext({ on: (n, f) => { (h[n] = h[n] || []).push(f); } });
const ctl = new AbortController();
const SP = "Be brief.";
const ctx = { cwd: "/tmp/claude-0/review_v33/repro_to/w_v34_slow/app", hasUI: false, signal: ctl.signal,
              sessionManager: { getSessionId: () => "S1" }, getSystemPrompt: () => SP };
const ASK = "Answer the question using the files in data/. Question: what is the total amount? Write the answer to /tmp/claude-0/review_v33/repro_to/w_v34_slow/app/answer.txt as a single number.";
await h.before_agent_start[0]({ prompt: ASK, systemPrompt: SP }, ctx);
await h.tool_call[0]({ toolName: "bash", input: { command: "ls data" }, toolCallId: "c1" }, ctx);
await h.tool_result[0]({ toolName: "bash", input: { command: "ls data" }, toolCallId: "c1",
                         content: [{ type: "text", text: "sales.csv" }] }, ctx);
await h.turn_end[0]({ message: { stopReason: "toolUse", content: [] }, toolResults: [{ toolCallId: "c1" }], entries: [] }, ctx);
await h.tool_call[0]({ toolName: "bash", input: { command: "cat data/sales.csv" }, toolCallId: "c2" }, ctx);
ctl.abort();   // the person presses Esc
await h.tool_result[0]({ toolName: "bash", input: { command: "cat data/sales.csv" }, toolCallId: "c2",
                         content: [{ type: "text", text: "aborted" }], isError: true }, ctx);
await h.turn_end[0]({ message: { stopReason: "aborted", content: [] }, toolResults: [{ toolCallId: "c2" }], entries: [] }, ctx);
const t0 = Date.now();
await h.session_shutdown[0]({ reason: "quit" }, ctx);
console.log("session_shutdown returned after", Date.now() - t0, "ms");
