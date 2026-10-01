// CDP soak: node soak.mjs <url> <minutes> <out.jsonl> [port]
import { spawn, execSync } from "node:child_process";
import fs from "node:fs";
const [url, minutes, out, port = "19222"] = process.argv.slice(2);
const udd = `/private/tmp/claude-501/soak/profile_${port}`;
fs.rmSync(udd, { recursive: true, force: true });
const chrome = spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", [
  "--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${udd}`,
  "--window-size=1920,1080", "--no-first-run", "--autoplay-policy=no-user-gesture-required",
  "--enable-precise-memory-info", "--disable-background-timer-throttling",
  "--disable-renderer-backgrounding", "--disable-backgrounding-occluded-windows", "about:blank"], { stdio: "ignore" });
let tabs;
for (let i = 0; i < 40; i++) { try { tabs = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); if (tabs.length) break; } catch {} await new Promise(r => setTimeout(r, 500)); }
const tab = tabs.find(t => t.type === "page");
const ws = new WebSocket(tab.webSocketDebuggerUrl);
await new Promise(r => ws.onopen = r);
let id = 0; const pend = new Map();
ws.onclose = () => { fs.appendFileSync(out, JSON.stringify({ died: true, t: new Date().toISOString() }) + '\n'); console.log('WS CLOSED'); process.exit(3); };
ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
  else if (m.method === "Page.frameNavigated" && !m.params.frame.parentId) nav++; };
let nav = 0;
const send = (method, params = {}) => new Promise(r => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async expr => { const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true }); return r.result?.result?.value; };
await send("Page.enable"); await send("Performance.enable"); await send("Runtime.enable"); await send("HeapProfiler.enable");
await send("Page.navigate", { url });
const t0 = Date.now(); let lastFc = null, lastT = null;
const probe = `(() => { const g = k => { try { return eval(k) } catch (e) { return null } };
 return { fc: g("frameCount"), pending: g("LIVE.pending.length"), seen: g("LIVE.seen.size"), seenQ: g("LIVE.seenQ.length"),
  dropped: g("LIVE.dropped.length"), recent: g("Object.keys(LIVE.recent).length"), abandoned: g("Object.keys(LIVE.abandoned).length"),
  videoPool: g("videoPool.size"), videoEls: document.querySelectorAll("video").length, canvases: document.querySelectorAll("canvas").length,
  domNodes: document.getElementsByTagName("*").length, imgs: document.images.length,
  reloads: sessionStorage.getItem("vw_reloads"), videoMissing: g("videoMissing.size"), srcFrames: g("srcFrames.size"),
  normGain: g("normGain.size"), pt: performance.now() }; })()`;
const rows = [];
while (Date.now() - t0 < minutes * 60000) {
  await new Promise(r => setTimeout(r, 30000));
  await send("HeapProfiler.collectGarbage");
  const m = Object.fromEntries((await send("Performance.getMetrics")).result.metrics.map(x => [x.name, x.value]));
  const p = await ev(probe);
  let fps = null; if (p && lastFc != null && p.fc != null) fps = ((p.fc - lastFc) / ((p.pt - lastT) / 1000)).toFixed(1);
  if (p) { lastFc = p.fc; lastT = p.pt; }
  let rss = null; try { rss = execSync(`ps -axo rss,command | grep "user-data-dir=${udd}" | grep -v grep | awk '{s+=$1} END {print s}'`).toString().trim(); } catch {}
  const row = { min: +((Date.now() - t0) / 60000).toFixed(1), heapMB: +(m.JSHeapUsedSize / 1048576).toFixed(1), heapTotalMB: +(m.JSHeapTotalSize / 1048576).toFixed(1),
    nodes: m.Nodes, docs: m.Documents, listeners: m.JSEventListeners, layoutObjects: m.LayoutObjects, fps, rssMB: rss ? +(rss / 1024).toFixed(0) : null, nav, ...p };
  rows.push(row); fs.appendFileSync(out, JSON.stringify(row) + "\n"); console.log(JSON.stringify(row));
}
ws.close(); chrome.kill();
process.exit(0);
