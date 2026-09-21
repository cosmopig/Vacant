// 用 CDP 的 Page.startScreencast 把展件的等待態錄下來。
//   node cap.mjs <url> <outdir> <seconds> [evalAtSec:jsfile] ...
// 產出：<outdir>/f00000.jpg…、<outdir>/frames.json（每一格的時間戳）
//       <outdir>/console.log（頁面 console + 例外，**不吞**）
import fs from "node:fs";
import path from "node:path";

const [, , URL_, OUT, SECS_, ...rest] = process.argv;
const SECS = Number(SECS_ || 30);
const PORT = Number(process.env.CDP_PORT || 9333);
fs.mkdirSync(OUT, { recursive: true });

const evals = rest.map((s) => {
  const k = s.indexOf(":");
  return { at: Number(s.slice(0, k)), js: s.slice(k + 1) };
}).sort((a, b) => a.at - b.at);

const ver = await (await fetch(`http://127.0.0.1:${PORT}/json/version`)).json();
const ws = new WebSocket(ver.webSocketDebuggerUrl);
await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });

let id = 0;
const waiters = new Map();
const logLines = [];
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && waiters.has(m.id)) { waiters.get(m.id)(m); waiters.delete(m.id); return; }
  if (m.method === "Page.screencastFrame") onFrame(m.params);
  if (m.method === "Runtime.consoleAPICalled") {
    logLines.push(`[${m.params.type}] ` +
      m.params.args.map((a) => a.value ?? a.description ?? a.type).join(" "));
  }
  if (m.method === "Runtime.exceptionThrown") {
    logLines.push("[EXCEPTION] " +
      JSON.stringify(m.params.exceptionDetails.exception?.description ||
                     m.params.exceptionDetails.text));
  }
  if (m.method === "Log.entryAdded") {
    logLines.push(`[log:${m.params.entry.level}] ${m.params.entry.text}`);
  }
};
function send(method, params = {}, sessionId) {
  const mid = ++id;
  return new Promise((res, rej) => {
    waiters.set(mid, (m) => m.error ? rej(new Error(method + ": " + JSON.stringify(m.error))) : res(m.result));
    ws.send(JSON.stringify({ id: mid, method, params, sessionId }));
  });
}

const { targetId } = await send("Target.createTarget", { url: "about:blank" });
const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });
const S = (m, p) => send(m, p, sessionId);

await S("Runtime.enable");
await S("Log.enable");
await S("Page.enable");
const VW = Number(process.env.CAP_W || 1920), VH = Number(process.env.CAP_H || 1080);
await S("Emulation.setDeviceMetricsOverride",
        { width: VW, height: VH, deviceScaleFactor: 1, mobile: false });

let n = 0;
const frames = [];
let capturing = false;
function onFrame(p) {
  if (capturing) {
    const name = `f${String(n).padStart(5, "0")}.jpg`;
    fs.writeFileSync(path.join(OUT, name), Buffer.from(p.data, "base64"));
    frames.push({ name, t: p.metadata.timestamp });
    n++;
  }
  S("Page.screencastFrameAck", { sessionId: p.sessionId }).catch(() => {});
}

await S("Page.navigate", { url: URL_ });
await new Promise((r) => setTimeout(r, 3500));          // 讓板／影片載進來

capturing = true;
await S("Page.startScreencast", { format: "jpeg", quality: 82,
                                  maxWidth: VW, maxHeight: VH, everyNthFrame: 1 });
const t0 = Date.now();
for (const e of evals) {
  const wait = t0 + e.at * 1000 - Date.now();
  if (wait > 0) await new Promise((r) => setTimeout(r, wait));
  const js = fs.readFileSync(e.js, "utf8");
  const r = await S("Runtime.evaluate", { expression: js, returnByValue: true });
  logLines.push(`[eval@${e.at}s] ${JSON.stringify(r.result?.value ?? r.result?.type)}`);
}
const left = t0 + SECS * 1000 - Date.now();
if (left > 0) await new Promise((r) => setTimeout(r, left));
await S("Page.stopScreencast");
capturing = false;

// 收尾：最後一張全尺寸 PNG（截圖用）
const shot = await S("Page.captureScreenshot", { format: "png" });
fs.writeFileSync(path.join(OUT, "final.png"), Buffer.from(shot.data, "base64"));
const title = await S("Runtime.evaluate", { expression: "document.title", returnByValue: true });
logLines.push("[title] " + title.result.value);

fs.writeFileSync(path.join(OUT, "frames.json"), JSON.stringify(frames, null, 1));
fs.writeFileSync(path.join(OUT, "console.log"), logLines.join("\n") + "\n");
console.log(`frames=${frames.length} out=${OUT}`);
await send("Target.closeTarget", { targetId });
ws.close();
