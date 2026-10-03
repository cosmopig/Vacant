
import ext from "./ext.mjs";
const h = {};
ext({ on: (n, f) => { (h[n] = h[n] || []).push(f); } });
const ctl = new AbortController();
const SP = "Be brief.\n\nYou have a hard budget of 15 model turns.";
const ctx = { cwd: "/app", hasUI: false, signal: ctl.signal,
              sessionManager: { getSessionId: () => "S1" }, getSystemPrompt: () => SP };
await h.before_agent_start[0]({ prompt: "q", systemPrompt: SP }, ctx);
for (let t = 1; t <= 15; t++) {
  const fin = t >= 14;
  const ev = { message: { stopReason: fin ? "stop" : "toolUse",
                          content: [{ type: "text", text: fin ? "The answer is 2045." : "" }] },
               toolResults: fin ? [] : [{ toolCallId: "c" + t }], entries: [] };
  if (t === 15) ctl.abort();          // the cap aborts in its own turn_end on turn 15
  await h.turn_end[0](ev, ctx);
  if (t === 14) {
    const r = await h.agent_before_settle[0]({ messages: [ev.message], entries: [] }, ctx);
    console.log("settle ->", JSON.stringify(r && { continue: r.continue }));
  }
}
await h.session_shutdown[0]({ reason: "quit" }, ctx);
