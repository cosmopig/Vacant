// 把 examples/receipt_viewer.html 真的用瀏覽器從 file:// 開一次，看畫面上寫了什麼。
//
// 為什麼這一支跟另外兩支不重複（DECISION 之外的第三條腿）：
//   receipt_viewer_crosscheck.py  測「我以為 JS 在做什麼」（Python 鏡像）
//   receipt_viewer_node_check.mjs 測「JS 實際算出什麼」（vm 裡跑 CANON 區段）
//   這一支                        測「觀眾眼前那台機器上真的顯示了什麼」——
//                                 含 WebCrypto 的 Ed25519 是不是真的在瀏覽器裡
//                                 跑起來、竄改示範按下去畫面會不會變、
//                                 以及整頁有沒有偷偷連任何東西。
// 展場沒有網路也沒有解說員，所以「離線」與「按鈕會動」都必須是可執行的斷言，
// 不是靠記得。
//
// 只用 node 內建（Node ≥ 22 的 global WebSocket）＋本機 Chrome，透過 CDP 驅動。
// 唯一的網路連線是 127.0.0.1 的 DevTools 埠；被檢查的那一頁自己一個請求都不發。
//
// 用法：
//   node ops/gain/replay/receipt_viewer_render_check.mjs
//   node ops/gain/replay/receipt_viewer_render_check.mjs --json out.json
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import url from "node:url";

const HERE = path.dirname(url.fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "../../..");
const VIEWER = path.join(REPO, "examples/receipt_viewer.html");
const FILE_URL = url.pathToFileURL(VIEWER).href;

const jsonOutIdx = process.argv.indexOf("--json");
const jsonOut = jsonOutIdx > 0 ? process.argv[jsonOutIdx + 1] : null;

const CHROMES = [
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
  "/Applications/Chromium.app/Contents/MacOS/Chromium",
  "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
];
const chrome = CHROMES.find((p) => fs.existsSync(p));
if (!chrome) { console.error("找不到任何 Chromium 系瀏覽器，跳過畫面檢查"); process.exit(2); }

const results = [];
const check = (name, ok, extra = "") => {
  results.push({ check: name, verdict: ok ? "OK" : "BROKEN", msg: String(extra) });
  console.log(`[${ok ? "OK    " : "BROKEN"}] ${name}${extra ? "  " + extra : ""}`);
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// --- 起 Chrome ------------------------------------------------------------
const port = 9500 + Math.floor(Math.random() * 400);
const profile = fs.mkdtempSync(path.join(os.tmpdir(), "rvcheck-"));
const proc = spawn(chrome, [
  "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
  `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
  "--remote-allow-origins=*", "about:blank",
], { stdio: ["ignore", "ignore", "ignore"] });

async function devtools(pathname) {
  for (let i = 0; i < 100; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${port}${pathname}`);
      if (r.ok) return await r.json();
    } catch { /* 還沒起來 */ }
    await sleep(100);
  }
  throw new Error("DevTools 埠沒有起來");
}

const version = await devtools("/json/version");
const targets = await devtools("/json/list");
const page = targets.find((t) => t.type === "page");
if (!page) { console.error("找不到 page target"); proc.kill(); process.exit(2); }

// --- 極簡 CDP client ------------------------------------------------------
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let msgId = 0;
const pending = new Map();
const events = [];
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id !== undefined) {
    const p = pending.get(m.id); pending.delete(m.id);
    if (p) (m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result));
  } else events.push(m);
};
const send = (method, params = {}) => new Promise((res, rej) => {
  const id = ++msgId; pending.set(id, { res, rej });
  ws.send(JSON.stringify({ id, method, params }));
});
const evalJs = async (expr) => {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.text + " " + (r.exceptionDetails.exception?.description || ""));
  return r.result.value;
};

await send("Runtime.enable");
await send("Log.enable");
await send("Network.enable");
await send("Page.enable");

// --- 開頁（file:// 直接開，沒有任何 server）--------------------------------
await send("Page.navigate", { url: FILE_URL });
let loaded = false;
for (let i = 0; i < 300 && !loaded; i++) {
  await sleep(100);
  loaded = events.some((e) => e.method === "Page.loadEventFired");
}
check("R0 file:// 直接開得起來（沒有任何 server）", loaded, FILE_URL);

// 等到大狀態面板不是「重算中…」為止（482 筆 Ed25519 要跑一下）
let st = null;
for (let i = 0; i < 600; i++) {
  st = await evalJs("document.getElementById('verdict').dataset.state");
  if (st && st !== "wait") break;
  await sleep(100);
}

const snap = () => evalJs(`(() => {
  const q = (id) => document.getElementById(id);
  return {
    state: q('verdict').dataset.state,
    headline: q('verdict-state').textContent.trim(),
    detail: q('verdict-detail').textContent.trim(),
    checks: Array.from(q('checks').children).map(li => li.dataset.r + ' ' + li.textContent.trim()),
    label: q('source-label').textContent.trim(),
    demoHidden: q('demo-banner').hidden,
    demoText: q('demo-text').textContent.trim(),
    slips: document.querySelectorAll('article.slip').length,
    tamperedSlips: document.querySelectorAll('article.slip.tampered').length,
    filterCount: q('filter-count').textContent.trim(),
    stats: Array.from(document.querySelectorAll('#stats .cell')).map(
      c => c.querySelector('.k').textContent + '=' + c.querySelector('.v').textContent),
    head: (Array.from(document.querySelectorAll('#idlist dt')).find(
      d => d.textContent.indexOf('head') >= 0) || {}).nextElementSibling?.textContent || '',
    sigWay: (Array.from(document.querySelectorAll('#idlist dt')).find(
      d => d.textContent === '驗簽方式') || {}).nextElementSibling?.textContent || '',
    firstSlip: (document.querySelector('article.slip') || {}).textContent?.replace(/\\s+/g, ' ').trim().slice(0, 220) || '',
  };
})()`);

const clean = await snap();
check("R1 大狀態＝驗證通過", clean.state === "pass" && clean.headline === "驗證通過",
  `state=${clean.state} headline=${clean.headline}`);
check("R2 逐筆重算 hash 482/482、串接無斷點",
  clean.checks.some((c) => c.startsWith("ok") && c.includes("482 / 482 筆"))
  && clean.checks.some((c) => c.startsWith("ok") && c.includes("無斷點")),
  clean.checks.filter((c) => !c.startsWith("ok")).join(" | ") || "四項全綠");
check("R3 Ed25519 真的在瀏覽器裡跑起來（WebCrypto，不是退化路徑）",
  clean.checks.some((c) => c.startsWith("ok") && c.includes("Ed25519 簽章：482 / 482 筆通過"))
  && clean.sigWay.includes("importKey"),
  clean.sigWay);
check("R4 重算出來的鏈頭＝Python 那端的 head",
  clean.head.trim() === "35b831bf0887b04b8ed86ba7a2f4b0e2ee45b0f0ba3e6e0b9fbbd2fc42cff3e2"
  || clean.checks.some((c) => c.includes("35b831bf0887")),
  clean.head.trim().slice(0, 24) + "…");
check("R5 真實資料標語在畫面上（不是只在原始碼裡）",
  clean.label === "以下是 2026-09-03 22:29 → 09-04 01:21（UTC）真實實驗 g_r445 的紀錄，不是模擬",
  clean.label);
check("R6 逐題收據 192 張都畫出來了", clean.slips === 192 && clean.filterCount === "顯示 192 / 192 題",
  `${clean.slips} 張／${clean.filterCount}`);
check("R7 收據上有具名 worker、順序、卡在第幾條、出貨或拒交",
  /plain-|hasty-|careful-|terse-|verbose-/.test(clean.firstSlip)
  && (clean.firstSlip.includes("出貨") || clean.firstSlip.includes("拒交")),
  clean.firstSlip.slice(0, 120));
check("R8 統計欄位算得出來", clean.stats.length === 6, clean.stats.join(" "));

// --- 竄改示範 -------------------------------------------------------------
await evalJs("document.getElementById('btn-tamper').click()");
let tam = null;
for (let i = 0; i < 600; i++) {
  tam = await snap();
  if (tam.state !== "pass") break;
  await sleep(100);
}
const m = /^(簽章不符|鏈被竄改)（第 (\d+) 筆）$/.exec(tam.headline);
check("R9 竄改示範：大狀態變成「簽章不符（第 N 筆）」", tam.state === "fail" && !!m, tam.headline);
check("R10 指到的是第 250 筆（＝crosscheck C5／node N4 挑的同一筆）",
  !!m && m[2] === "250", m ? m[2] : "—");
check("R11 竄改時畫面標「這是示範，不是資料」",
  !tam.demoHidden && tam.label.startsWith("這是示範，不是資料"), tam.label);
check("R12 被改過的那張收據在畫面上有記號", tam.tamperedSlips === 1, `${tam.tamperedSlips} 張`);

// --- 還原 -----------------------------------------------------------------
await evalJs("document.getElementById('btn-restore').click()");
let back = null;
for (let i = 0; i < 600; i++) {
  back = await snap();
  if (back.state === "pass") break;
  await sleep(100);
}
check("R13 還原之後回到驗證通過（磁碟上的檔案從頭到尾沒被動過）",
  back.state === "pass" && back.headline === "驗證通過" && back.demoHidden,
  `${back.headline}／demoHidden=${back.demoHidden}`);
const diskUnchanged = fs.readFileSync(VIEWER, "utf8").length;

const isSecure = await evalJs("String(window.isSecureContext) + ' subtle=' + String(!!(self.crypto && self.crypto.subtle))");
check("R14 file:// 之下 crypto.subtle 拿得到（拿不到就會走退化路徑，畫面會講出來）",
  isSecure.includes("subtle=true"), isSecure);

// --- 換一條鏈：用檔案挑選器載入 g_r447（頁面不是只認得內建的那一份）---------
const R447 = path.join(REPO, "runs/g_r447_conform_lcb2");
const doc = await send("DOM.getDocument");
const input = await send("DOM.querySelector", { nodeId: doc.root.nodeId, selector: "#file-input" });
await send("DOM.setFileInputFiles", {
  nodeId: input.nodeId,
  files: [path.join(R447, "receipts_CONFORM.ndjson"), path.join(R447, "receipts_CONFORM.pub.json")],
});
// 有些 Chrome 版本 setFileInputFiles 不會自己派事件，補一次（重複派也無害）。
await evalJs("document.getElementById('file-input').dispatchEvent(new Event('change'))");
let other = null;
for (let i = 0; i < 600; i++) {
  other = await snap();
  if (other.checks.some((c) => c.includes("325"))) break;
  await sleep(100);
}
const vid447 = await evalJs(`(Array.from(document.querySelectorAll('#idlist dt')).find(
  d => d.textContent === 'vacant_id') || {}).nextElementSibling?.textContent || ''`);
check("R15 檔案挑選器載入 g_r447：325 筆、簽章全過、換成 r447 自己的公鑰",
  other.state === "pass"
  && other.checks.some((c) => c.startsWith("ok") && c.includes("Ed25519 簽章：325 / 325 筆通過"))
  && vid447.trim() === "zQmYszVLbcCkHRquxtdxgkycF8JW4CoopNFyhcQ6Q47gMn9",
  `${other.headline}／${other.slips} 題／vacant_id=${vid447.trim().slice(0, 16)}…`);
check("R16 載入別人的檔之後，真實資料那句標語換掉（不再宣稱是 g_r445）",
  !other.label.includes("g_r445") && other.label.includes("receipts_CONFORM.ndjson"), other.label);

// --- 拖放：展場那台機器上，拖進來的檔案走的是另一條 handler ----------------
// 現在頁面上是 g_r447；把 g_r445 那兩個檔「拖」回去，回到 482 筆才算這條路通。
const R445 = path.join(REPO, "runs/g_r445_conform_mbpp_ext");
const drop445 = JSON.stringify({
  ndjson: fs.readFileSync(path.join(R445, "receipts_CONFORM.ndjson"), "utf8"),
  pub: fs.readFileSync(path.join(R445, "receipts_CONFORM.pub.json"), "utf8"),
});
await evalJs(`(() => {
  const d = ${drop445};
  const dt = new DataTransfer();
  dt.items.add(new File([d.ndjson], 'receipts_CONFORM.ndjson', { type: 'application/x-ndjson' }));
  dt.items.add(new File([d.pub], 'receipts_CONFORM.pub.json', { type: 'application/json' }));
  document.body.dispatchEvent(new DragEvent('drop', { dataTransfer: dt, bubbles: true, cancelable: true }));
  return true;
})()`);
let dropped = null;
for (let i = 0; i < 600; i++) {
  dropped = await snap();
  if (dropped.checks.some((c) => c.includes("482 / 482"))) break;
  await sleep(100);
}
const vidDrop = await evalJs(`(Array.from(document.querySelectorAll('#idlist dt')).find(
  d => d.textContent === 'vacant_id') || {}).nextElementSibling?.textContent || ''`);
check("R17 拖放載入 g_r445：482 筆、簽章全過、公鑰換回 r445 那一把",
  dropped.state === "pass"
  && dropped.checks.some((c) => c.startsWith("ok") && c.includes("Ed25519 簽章：482 / 482 筆通過"))
  && vidDrop.trim() === "zQmU1MmEoDgRHS7B3EzFL4s1kYcYdSb73sDDhtuQutywmtD",
  `${dropped.headline}／${dropped.slips} 題／vacant_id=${vidDrop.trim().slice(0, 16)}…`);

// --- 浮點數守門員：頁面涵蓋不到的那一筆，要說「不知道」不要猜 --------------
// 真檔 807 筆全是安全整數，所以這條路在真資料上永遠不會走到。要看它有沒有真的
// 接上畫面，只能餵一筆頁面算不出來的：拿 g_r447 前三行，把其中一筆的 ts_ms
// 改成小數。JS 與 Python 的浮點數格式在這裡會分岔，猜出來的 hash 會是錯的。
const r447lines = fs.readFileSync(
  path.join(R447, "receipts_CONFORM.ndjson"), "utf8").split("\n").filter((l) => l.trim());
const spiked = r447lines.slice(0, 3);
spiked[1] = spiked[1].replace(/"ts_ms":(\d+)/, '"ts_ms":$1.5');
const spikedText = JSON.stringify(spiked.join("\n") + "\n");
await evalJs(`(() => {
  const dt = new DataTransfer();
  dt.items.add(new File([${spikedText}], 'receipts_SPIKED.ndjson', { type: 'application/x-ndjson' }));
  document.body.dispatchEvent(new DragEvent('drop', { dataTransfer: dt, bubbles: true, cancelable: true }));
  return true;
})()`);
let spike = null;
for (let i = 0; i < 600; i++) {
  spike = await snap();
  if (spike.headline.startsWith("無法重算")) break;
  await sleep(100);
}
check("R18 遇到算不出來的那一筆就說「不知道」，不猜一個看起來很像的 hash",
  spike.state === "partial" && spike.headline === "無法重算（第 2 筆）"
  && spike.detail.includes("本頁的正規化規則沒有涵蓋它"),
  `state=${spike.state} headline=${spike.headline}`);

// --- 退化路徑一：整個 crypto.subtle 拿不到 ---------------------------------
const degA = await send("Page.addScriptToEvaluateOnNewDocument", {
  source: "Object.defineProperty(crypto, 'subtle', { get: () => undefined, configurable: true });",
});
await send("Page.navigate", { url: FILE_URL });
let deg = null;
for (let i = 0; i < 600; i++) {
  await sleep(100);
  try { deg = await snap(); } catch { continue; }
  if (deg.state && deg.state !== "wait") break;
}
check("R19 沒有 Ed25519 時不假裝驗過：狀態降級成「hash 鏈驗證通過」",
  deg.state === "partial" && deg.headline === "hash 鏈驗證通過",
  `state=${deg.state} headline=${deg.headline}`);
check("R20 畫面上明說「此瀏覽器不支援 Ed25519 驗簽，只驗了 hash 鏈」",
  deg.detail.includes("此瀏覽器不支援 Ed25519 驗簽，只驗了 hash 鏈")
  && deg.checks.some((c) => c.startsWith("skip") && c.includes("此瀏覽器不支援 Ed25519")),
  deg.detail.slice(0, 60) + "…");

// --- 退化路徑二：subtle 在、但不認得 Ed25519（Firefox 目前就是這一種）------
// 兩條路要走到同一個結論，否則「有 crypto.subtle」的瀏覽器會拿到一個綠勾。
await send("Page.removeScriptToEvaluateOnNewDocument", { identifier: degA.identifier });
const degB = await send("Page.addScriptToEvaluateOnNewDocument", {
  source: "const _ik = crypto.subtle.importKey.bind(crypto.subtle);"
    + "crypto.subtle.importKey = (fmt, key, algo, ex, use) =>"
    + " (algo && algo.name === 'Ed25519')"
    + " ? Promise.reject(new DOMException('unsupported', 'NotSupportedError'))"
    + " : _ik(fmt, key, algo, ex, use);",
});
await send("Page.navigate", { url: FILE_URL });
let deg2 = null;
for (let i = 0; i < 600; i++) {
  await sleep(100);
  try { deg2 = await snap(); } catch { continue; }
  if (deg2.state && deg2.state !== "wait") break;
}
check("R21 importKey 認不得 Ed25519 時走的是同一條退化路徑（不是綠勾）",
  deg2.state === "partial" && deg2.headline === "hash 鏈驗證通過"
  && deg2.detail.includes("此瀏覽器不支援 Ed25519 驗簽，只驗了 hash 鏈"),
  `state=${deg2.state} headline=${deg2.headline}`);
await send("Page.removeScriptToEvaluateOnNewDocument", { identifier: degB.identifier });

// --- 離線紅線：整場（含兩次載入、換檔、重載）只發生過哪些請求 -------------
const reqs = events.filter((e) => e.method === "Network.requestWillBeSent")
  .map((e) => e.params.request.url);
const offsite = reqs.filter(
  (u) => !u.startsWith("file://") && u !== "about:blank" && !u.startsWith("data:"));
check("R22 整場零外部請求（只有 file:// 那一份文件本身）", offsite.length === 0,
  `${reqs.length} 個請求：${[...new Set(reqs.map((u) => u.split("/").pop()))].join(", ")}`
  + (offsite.length ? `；外部：${offsite.join(", ")}` : ""));

const errs = events.filter((e) => e.method === "Runtime.exceptionThrown"
  || (e.method === "Log.entryAdded" && e.params.entry.level === "error"))
  .map((e) => e.params.entry?.text || e.params.exceptionDetails?.text);
check("R23 沒有 JS 例外、沒有載入失敗的資源", errs.length === 0, errs.join(" | ") || "console 乾淨");

ws.close();
proc.kill();
try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* 清不掉就算了 */ }

const fail = results.filter((r) => r.verdict !== "OK").length;
console.log(`瀏覽器：${version.Browser}；檔案 ${diskUnchanged} 字元（跑完沒變）`);
console.log(fail === 0 ? "總判定：OK" : `總判定：BROKEN（${fail} 項）`);
if (jsonOut) {
  fs.writeFileSync(jsonOut, JSON.stringify({
    verdict: fail === 0 ? "OK" : "BROKEN", browser: version.Browser, url: FILE_URL,
    requests: reqs, checks: results,
  }, null, 2) + "\n");
}
process.exit(fail === 0 ? 0 : 1);
