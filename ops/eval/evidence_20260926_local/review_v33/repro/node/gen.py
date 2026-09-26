import json, pathlib
from vacant_network.adapters import agents as AG
d = pathlib.Path("/tmp/claude-0/review_v33/node")
log = d/"calls.jsonl"; log.unlink(missing_ok=True)
stub = d/"stub.sh"
stub.write_text(f'#!/bin/sh\nprintf \'{{"event":"%s","payload":%s}}\\n\' "$1" "$(cat)" >> {log}\n'
                'if [ "$1" = stop ]; then echo \'{"action":"continue","reason":"The request asks for /app/answer.txt, but it does not exist."}\'; else echo \'{"action":"allow"}\'; fi\n')
stub.chmod(0o755)
(d/"ext.mjs").write_text(AG.PI_EXTENSION % {"argv": json.dumps([str(stub)]), "timeout_ms": 5000,
                                  "budget_re": "/" + AG.BUDGET_RE_SRC.replace("/", r"\/") + "/i"})
(d/"drive.mjs").write_text(r"""
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
""")
