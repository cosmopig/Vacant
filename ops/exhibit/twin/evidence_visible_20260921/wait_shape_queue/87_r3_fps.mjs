// 量頁面自己的 rAF 幀率（不錄影）。判成「卡住」之前先證明量得動。
// node r3_fps.mjs <url> <seconds>
const [, , URL_, SECS_] = process.argv;
const SECS = Number(SECS_ || 20);
const PORT = Number(process.env.CDP_PORT || 9337);
const ver = await (await fetch(`http://127.0.0.1:${PORT}/json/version`)).json();
const ws = new WebSocket(ver.webSocketDebuggerUrl);
await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
let id = 0; const waiters = new Map();
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && waiters.has(m.id)) { waiters.get(m.id)(m); waiters.delete(m.id); }
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
await S("Runtime.enable"); await S("Page.enable");
await S("Emulation.setDeviceMetricsOverride", { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });
await S("Page.navigate", { url: URL_ });
await new Promise((r) => setTimeout(r, 4000));
const INSTALL = `(() => { window.__f = 0; window.__f0 = performance.now();
  const g = () => { window.__f++; requestAnimationFrame(g); }; requestAnimationFrame(g);
  window.__iv = 0; window.__iv0 = performance.now();
  window.__ivh = setInterval(() => window.__iv++, 500);
  return "on"; })()`;
await S("Runtime.evaluate", { expression: INSTALL, returnByValue: true });
await new Promise((r) => setTimeout(r, SECS * 1000));
const DUMP = `JSON.stringify({ frames: window.__f, secs: (performance.now()-window.__f0)/1000,
  fps: window.__f / ((performance.now()-window.__f0)/1000),
  intervalTicks: window.__iv, intervalExpected: (performance.now()-window.__iv0)/500,
  visibility: document.visibilityState })`;
const r = await S("Runtime.evaluate", { expression: DUMP, returnByValue: true });
console.log(r.result.value);
await send("Target.closeTarget", { targetId });
ws.close();
