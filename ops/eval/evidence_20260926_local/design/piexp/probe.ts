// L-fake probe for pi 0.87.1 boundary/abort mechanics. Auto-discovered from <agentDir>/extensions (like Vacant's vacant.ts).
import { appendFileSync } from "node:fs";
import { spawn } from "node:child_process";
const LOG = process.env.PROBE_LOG || "/dev/null";
const MODE = process.env.PROBE_MODE || "";
const MODES = MODE.split(",");
const INJ = (process.env.INJECT_AT || "").split(",").filter(Boolean); // e.g. "2,3c" (c = continue:true)
const IS_CHILD = !!process.env.PROBE_IS_CHILD;
const log = (ev, rec = {}) => { try { appendFileSync(LOG, JSON.stringify({ pid: process.pid, child: IS_CHILD, ev, ...rec }) + "\n"); } catch {} };
const budget = (s) => (/hard budget of (\d+) model turns/.exec(s || "") || [])[1] ?? null;
let turns = 0; let followed = false;
export default function (pi) {
  log("factory", { mark: process.env.VACANT_PI_PARENT ?? null, ppid: process.ppid });
  pi.on("before_agent_start", (e, ctx) => {
    log("before_agent_start", { budgetInEvent: budget(e.systemPrompt), budgetInCtx: budget(ctx.getSystemPrompt()), prompt: String(e.prompt).slice(0, 80), mode: ctx.mode });
    process.env.VACANT_PI_PARENT = JSON.stringify({ session: ctx.sessionManager.getSessionId(), pid: process.pid, cwd: process.cwd() });
  });
  pi.on("turn_start", (e) => log("turn_start", { turnIndex: e.turnIndex }));
  pi.on("turn_end", (e, ctx) => {
    turns++;
    const m = e.message;
    log("turn_end", { n: turns, turnIndex: e.turnIndex, outcome: e.outcome, stopReason: m.stopReason,
      contentTypes: (m.content || []).map((c) => c.type), toolResults: e.toolResults.length,
      signalAborted: !!(ctx.signal && ctx.signal.aborted), entriesIn: e.entries.length, continueIn: e.continue,
      budgetInCtx: budget(ctx.getSystemPrompt()), sysMsgsInLlm: (e.context.llmMessages || []).filter((x) => x.role === "system").length,
      budgetInLlmSys: budget(JSON.stringify((e.context.llmMessages || []).filter((x) => x.role === "system"))), canContinue: e.context.canContinue });
    for (const spec of INJ) {
      const k = parseInt(spec, 10), cont = spec.endsWith("c");
      if (k === turns) {
        const r = { entries: [...e.entries, { type: "custom_message", customType: "vacant-probe", content: `VACANT-INJECT-AT-TURN${turns}`, display: true }] };
        if (cont) r.continue = true;
        log("inject", { at: turns, cont });
        return r;
      }
    }
    return undefined;
  });
  pi.on("agent_before_settle", async (e, ctx) => {
    log("agent_before_settle", { outcome: e.outcome });
    if (MODES.includes("slow")) {
      const t0 = Date.now();
      await new Promise((r) => setTimeout(r, Number(process.env.SLOW_MS || 20000)));
      log("slow_done", { ms: Date.now() - t0 });
    }
    if (MODES.includes("child") && !IS_CHILD) {
      const args = [process.argv[1], "-p", "--mode", "json", "--provider", ctx.model.provider, "--model", ctx.model.id, "CHILD-TASK"];
      log("child_spawn", { execPath: process.execPath, argv1: process.argv[1], provider: ctx.model.provider, model: ctx.model.id });
      const code = await new Promise((res) => {
        const c = spawn(process.execPath, args, { cwd: ctx.cwd, env: { ...process.env, PROBE_IS_CHILD: "1" }, stdio: ["ignore", "pipe", "pipe"] });
        let out = ""; c.stdout.on("data", (b) => (out += b)); c.stderr.on("data", (b) => (out += b));
        c.on("close", (code) => { log("child_out_tail", { tail: out.slice(-300) }); res(code); });
      });
      log("child_exit", { code });
    }
  });
  let endFollowed = false;
  pi.on("agent_end", (e, ctx) => {
    log("agent_end", { n: e.messages.length, lastStop: (e.messages[e.messages.length - 1] || {}).stopReason, signalAborted: !!(ctx.signal && ctx.signal.aborted), idle: ctx.isIdle() });
    if (MODES.includes("endfollow") && !endFollowed) { endFollowed = true; pi.sendUserMessage("VACANT-FOLLOWUP from agent_end", { deliverAs: "followUp" }); log("endfollow_sent"); }
    if (MODES.includes("endplain") && !endFollowed) { endFollowed = true; pi.sendUserMessage("VACANT-FOLLOWUP from agent_end plain"); log("endplain_sent"); }
  });
  pi.on("agent_settled", (e, ctx) => {
    log("agent_settled", { keys: Object.keys(e) });
    if (MODES.includes("follow") && !followed && !IS_CHILD) {
      followed = true;
      pi.sendUserMessage("VACANT-FOLLOWUP: write your current answer to answer.txt now");
      log("followup_sent");
    }
  });
  pi.on("session_shutdown", (e) => log("session_shutdown", { reason: e.reason }));
}
