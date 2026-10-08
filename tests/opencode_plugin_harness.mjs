// OpenCode 外掛（vacant.js）的形狀與行為探針——由 tests/test_091_opencode_v2.py 用 node 跑。
// 用法：node opencode_plugin_harness.mjs <vacant.js 路徑> v1|v2（兩種各開一個行程：外掛的狀態在 globalThis 上）
// 掛鉤指令（ARGV）在產生檔案時已換成一支假的 node 腳本：它把收到的事件與 payload 記到
// $VACANT_FAKE_LOG，stop 時回 continue（一則回饋），其餘回 allow。
// ⚠ 這裡的 v1／v2 ctx 都是假的：只驗形狀與我們自己的邏輯，不是 OpenCode 的載入器。
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const file = process.argv[2];
const mode = process.argv[3] || "v2";
const log = process.env.VACANT_FAKE_LOG;
const results = {};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const events = () => readFileSync(log, "utf-8").split("\n").filter(Boolean).map((l) => JSON.parse(l));

async function waitFor(pred, ms = 5000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    if (pred()) return true;
    await sleep(20);
  }
  return false;
}

const mod = await import(pathToFileURL(file).href);
const def = mod.default;
results.named_exports = Object.keys(mod).filter((k) => k !== "default");
results.default_is_object = !!def && typeof def === "object" && !Array.isArray(def);
results.id = def && def.id;
results.has_setup = typeof (def && def.setup) === "function";
results.has_server = typeof (def && def.server) === "function";
results.has_effect = "effect" in (def || {});

// 1.18.35 的預覽 ctx：沒有 tool／session／event／location
results.preview_setup = await def.setup({ app: {}, options: {} });
results.preview_setup_null = await def.setup(undefined);

// ── v1：假的 { client, directory } ──
async function runV1() {
  const prompts = [];
  const toasts = [];
  const client = { session: {
    messages: async ({ path }) => ({ data: [
      { info: { role: "user" }, parts: [{ type: "text", text: "do it" }] },
      { info: { role: "assistant" }, parts: [{ type: "text", text: "Done, tests pass." },
                                              { type: "text", text: "hidden", synthetic: true }] },
    ] }),
    promptAsync: async (x) => { prompts.push(x); return {}; },
    prompt: async () => { throw new Error("blocking prompt must not be used when promptAsync exists"); },
  }, tui: { showToast: async (x) => { toasts.push(x); return {}; } } };
  const map = await def.server({ client, directory: "/w/proj" });
  results.v1_hooks = Object.keys(map).sort();
  await map["chat.message"]({ sessionID: "S1" }, { parts: [{ type: "text", text: "write report.md" }] });
  await map["tool.execute.before"]({ tool: "write", sessionID: "S1", callID: "c1" }, { args: { filePath: "r.md" } });
  await map.event({ event: { type: "session.created", properties: { info: { id: "S1" } } } });
  await map.event({ event: { type: "session.created", properties: { info: { id: "S2" } } } });
  await map.event({ event: { type: "session.created", properties: { info: { id: "K1", parentID: "S1" } } } });
  await map.event({ event: { type: "session.idle", properties: { sessionID: "K1" } } });
  await map.event({ event: { type: "session.idle", properties: { sessionID: "S1" } } });
  await map.event({ event: { type: "session.idle", properties: { sessionID: "S1" } } });   // the feedback turn ends
  results.v1_prompts = prompts;
  results.v1_toasts = toasts;
  // after server(), a full v2 ctx must not hook a second time
  const extra = {};
  const r = await def.setup({ location: { directory: "/w" }, event: { subscribe: () => [] },
                              session: { hook: async (n) => { extra[n] = 1; return { dispose() {} }; } },
                              tool: { hook: async (n) => { extra[n] = 1; return { dispose() {} }; } } });
  results.v1_then_setup = { returned: r === undefined ? null : typeof r, hooked: Object.keys(extra) };
  await map.dispose();
  await map.dispose();   // re-entry: nothing sent twice
  results.v1_events = events();
}

async function runV2() {
const hooks = {};
const prompts = [];
let push;
const queue = [];
const stream = {
  [Symbol.asyncIterator]() {
    return {
      next: () => new Promise((resolve) => {
        if (queue.length) resolve({ value: queue.shift(), done: false });
        else push = (v) => { push = null; resolve({ value: v, done: false }); };
      }),
      return: async () => ({ done: true }),
    };
  },
};
const emit = (ev) => { if (push) push(ev); else queue.push(ev); };
let disposed = 0;
const reg = (domain) => async (name, fn) => { hooks[domain + ":" + name] = fn; return { dispose: async () => { disposed++; } }; };
const toasts = [];
const ctx = {
  ui: { toast: async (x) => { toasts.push(x); } },
  location: { directory: "/w/proj" },
  tool: { hook: reg("tool") },
  session: { hook: reg("session"), prompt: async (x) => { prompts.push(x); return {}; },
             get: async ({ sessionID }) => {
               if (sessionID === "K2") await sleep(300);   // slow lookup: the race window
               return sessionID === "K1" ? { id: "K1", parentID: "S1" }
                    : sessionID === "K2" ? { id: "K2", parentID: "S1" } : { id: sessionID }; } },
  event: { subscribe: (opts) => { results.subscribe_has_signal = !!(opts && opts.signal); return stream; } },
};
const cleanup = await def.setup(ctx);
results.v2_hooks = Object.keys(hooks).sort();
results.v2_cleanup_is_function = typeof cleanup === "function";

await hooks["session:prompt"]({ sessionID: "S1", prompt: { text: "write report.md" } });
await hooks["tool:execute.before"]({ tool: "write", sessionID: "S1", id: "c1", input: { filePath: "r.md" } });
let denied = null;
try {
  await hooks["tool:execute.before"]({ tool: "bash", sessionID: "S1", id: "c2", input: { command: "DENYME" } });
} catch (e) { denied = String(e.message || e); }
results.v2_deny_message = denied;
await hooks["tool:execute.after"]({ tool: "write", sessionID: "S1", id: "c1", input: { filePath: "r.md" },
                                     status: "completed", result: { content: "wrote r.md" } });
emit({ id: "e1", type: "session.created", data: { sessionID: "S1" } });
emit({ id: "e2", type: "session.created", data: { sessionID: "S2" } });
// K1 is a sub-agent known only through session.get (2.0.24 sends no session.created for it)
await hooks["tool:execute.before"]({ tool: "read", sessionID: "K1", id: "k1", input: { filePath: "a" } });
emit({ id: "e4", type: "session.text.ended", data: { sessionID: "S1", assistantMessageID: "m1", ordinal: 0, text: "All tests pass." } });
emit({ id: "e5", type: "session.execution.succeeded", data: { sessionID: "K1" } });   // child: no check
emit({ id: "e5b", type: "session.idle", data: { sessionID: "S2" } });   // not the 2.x turn end: ignored
emit({ id: "e6", type: "session.execution.succeeded", data: { sessionID: "S1" } });
await waitFor(() => prompts.length >= 1);
// the end of the feedback turn must get a second check (busy set released before sending)
emit({ id: "e7", type: "session.text.ended", data: { sessionID: "S1", assistantMessageID: "m2", ordinal: 0, text: "Fixed." } });
emit({ id: "e8", type: "session.execution.succeeded", data: { sessionID: "S1" } });
await waitFor(() => prompts.length >= 2);
results.v2_prompts = prompts;
results.v2_toasts = toasts;
// (2) race: two concurrent first tool calls of a new child session K2 are both seen as a child
await Promise.all([1, 2].map((i) => hooks["tool:execute.before"]({ tool: "read", sessionID: "K2", id: "r" + i, input: { filePath: "a" } })));
// (1) stale text: S1 already consumed "Fixed."; a new prompt then a tool-only turn carries no final_text
await hooks["session:prompt"]({ sessionID: "S1", prompt: { text: "now rename foo" } });
emit({ id: "e9", type: "session.execution.succeeded", data: { sessionID: "S1" } });
await waitFor(() => prompts.length >= 3);
// also: text of turn A, then a new prompt BEFORE the stop ran (no consume) must not leak into turn B
emit({ id: "e10", type: "session.text.ended", data: { sessionID: "S3", assistantMessageID: "m9", ordinal: 0, text: "Old claim." } });
await sleep(150);   // let the event loop consume it before the new prompt
await hooks["session:prompt"]({ sessionID: "S3", prompt: { text: "next task" } });
emit({ id: "e11", type: "session.execution.succeeded", data: { sessionID: "S3" } });
await waitFor(() => prompts.length >= 4);
await cleanup();
results.v2_disposed = disposed;
results.v2_events = events();

}

if (mode === "v1") await runV1(); else await runV2();
console.log(JSON.stringify(results));
process.exit(0);
