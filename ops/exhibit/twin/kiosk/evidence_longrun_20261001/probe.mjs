import { spawn } from "node:child_process"; import fs from "node:fs";
const [url, port, secs, exprs] = process.argv.slice(2);
const udd = `/private/tmp/claude-501/soak/profile_${port}`; fs.rmSync(udd, { recursive: true, force: true });
const chrome = spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${udd}`, "--window-size=1920,1080", "--no-first-run", "--autoplay-policy=no-user-gesture-required", "about:blank"], { stdio: "ignore" });
let tabs; for (let i = 0; i < 40; i++) { try { tabs = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); if (tabs.length) break; } catch {} await new Promise(r => setTimeout(r, 500)); }
const ws = new WebSocket(tabs.find(t => t.type === "page").webSocketDebuggerUrl); await new Promise(r => ws.onopen = r);
let id = 0; const pend = new Map(); ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } };
const send = (method, params = {}) => new Promise(r => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
await send("Page.enable"); await send("Runtime.enable"); await send("Page.navigate", { url });
for (let k = 0; k < +secs / 10; k++) { await new Promise(r => setTimeout(r, 10000));
  const r = await send("Runtime.evaluate", { expression: exprs, returnByValue: true }); console.log(JSON.stringify(r.result?.result?.value ?? r.result)); }
chrome.kill(); process.exit(0);
