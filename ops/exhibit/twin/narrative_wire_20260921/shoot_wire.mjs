// 對**真的跑起來的那一頁**按快門，並且把大標／副標**從頁面上讀回來**。
//
// ## 為什麼不是 `chrome --screenshot`
//
// 這台 Mac 上實測（2026-09-21）：
//   about:blank  → PNG 1040 bytes 寫得出來，**但行程不退出**（正控制成立，
//                  所以「截不到」不是工具壞了）。
//   world3/index.html → renderer 直接 `Abnormal renderer termination`，
//                  `--virtual-time-budget` 碰上不停的 rAF ＋ 影片解碼不收斂。
// ⇒ 走 CDP。做法照 `vacant_hm/tools/twinshot.mjs`（同一台機器上已經驗過的路）。
//
// ## 為什麼要把字讀回來
//
// **一張 PNG 證明不了字是什麼**（縮圖上讀不出來、而且人會把自己想看的讀進去）。
// 這裡用 `index.html` **自己**那一行算法把字算出來：
//
//     head = tov ? tov.head : sc.head
//     sub  = waitOv ? waitOv : tov ? tov.sub : s00 ? standbySub() : s11 ? loopSub() : sc.sub
//
// 逐字抄自 index.html 的 `drawTitle(...)` 呼叫點（見 .json 的 `copy_algo`）。
// ⇒ 讀回來的字與畫出來的字**同源**，不是我謄的。
//
// ## snapA 歸零才按快門
//
// 場景交叉溶接期間 `snapA>0`，畫面上兩幕疊在一起。固定停留時間會截到鬼影。
//
// ## base_sha256
//
// 每一張的 .json 記**這一次拍的到底是哪一版頁面**：截圖器自己 `fetch` 那個
// URL、算 sha256。抓不到寫 `null`（**不寫空字串、不寫 0**）。
// 一批截圖跨越別人改檔的時刻 ⇒ 板子上就看得出來是拼貼的。
//
// 用法：
//   node shoot_wire.mjs <輸出.png> <網址> [停留ms] [除錯埠]
// 退出碼：0＝截到圖也讀到字；2＝起不來／讀不到（**不回 0 假裝成功**）。
import fs from "node:fs";
import crypto from "node:crypto";
import { spawn } from "node:child_process";

const OUT = process.argv[2];
const URL_ = process.argv[3];
const DWELL = parseInt(process.argv[4] || "9000", 10);
const PORT = parseInt(process.argv[5] || "9401", 10);
// 第 6 個參數：等到 `sceneId` 變成這一格才按快門。
// ⚠ 為什麼需要：`?scene=sNN` 是在 `addEventListener("load")` 裡面、而且掛在
//   `READY.then(...)` 後面才生效。headless 上資產載完要十幾秒，固定停留 9 秒
//   拍到的是 **s00**——而那張圖看起來完全正常，只是拍錯了一幕。
//   （2026-09-21 第一張 NEG 就是這樣拍成 s00 的。）
const EXPECT = process.argv[6] || null;
const CHROME = process.env.CHROME_BIN
  || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
if (!OUT || !URL_) {
  console.error("用法：node shoot_wire.mjs <輸出.png> <網址> [停留ms] [埠]");
  process.exit(2);
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const udd = `/tmp/wire5/cdp-${PORT}`;

// 🔴 **開工先把舊的刪掉。** 這一格如果失敗，上一次成功的 PNG＋.json 會留在原地，
//    而板子照樣讀得到、看起來完全正常——那就是一張「上一版的圖配這一版的表」。
//    2026-09-21 實際踩到：b05 這一格 rc=2，但目錄裡躺著十分鐘前單跑成功的那一張。
for (const f of [OUT, OUT.replace(/\.png$/, ".json")]) {
  try { fs.rmSync(f, { force: true }); } catch (e) { /* 本來就沒有 */ }
}

// `detached: true` ⇒ Chrome 自己一個行程群組，收尾殺得掉**整群**。
// ⚠ 只 `chrome.kill()` 殺得到父行程，renderer／gpu 這些 helper 會活下來變孤兒
//   （2026-09-21 實測：跑了兩批就躺著六個，機器變慢之後下一批就開始逾時，
//    而逾時看起來像「這一頁截不出來」）。
const chrome = spawn(CHROME, [
  "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
  "--window-size=1920,1080", "--autoplay-policy=no-user-gesture-required",
  "--mute-audio", "--no-first-run", "--no-default-browser-check",
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${udd}`, URL_,
], { stdio: ["ignore", "pipe", "pipe"], detached: true });
let chromeErr = "";
chrome.stderr.on("data", (b) => { chromeErr += String(b); });
function killChrome() {
  try { process.kill(-chrome.pid, "SIGKILL"); } catch (e) { /* 群組已經沒了 */ }
  try { chrome.kill("SIGKILL"); } catch (e) { /* 同上 */ }
}

// 硬上限：任何一格最多 200 秒。到了就**說截不到**並收掉 Chrome，
// 不要掛在那裡讓整批看起來像當掉。
const watchdog = setTimeout(() => {
  console.log(JSON.stringify({ ok: false, url: URL_,
    why: "逾時 200s：這一格沒截到（看門狗開槍）" }, null, 2));
  killChrome();
  process.exit(2);
}, 200000);
watchdog.unref?.();

async function targetWs() {
  for (let k = 0; k < 80; k++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const list = await r.json();
      const page = list.find((t) => t.type === "page" && t.webSocketDebuggerUrl);
      if (page) return page.webSocketDebuggerUrl;
    } catch (e) { /* 還沒起來 */ }
    await sleep(500);
  }
  return null;
}

function cdp(wsUrl) {
  const ws = new WebSocket(wsUrl);
  let id = 0;
  const waiting = new Map();
  const events = [];
  ws.addEventListener("message", (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id != null && waiting.has(m.id)) {
      const { resolve, reject } = waiting.get(m.id);
      waiting.delete(m.id);
      m.error ? reject(new Error(JSON.stringify(m.error))) : resolve(m.result);
    } else if (m.method) events.push(m);
  });
  const open = new Promise((res, rej) => {
    ws.addEventListener("open", res);
    ws.addEventListener("error", () => rej(new Error("CDP WebSocket 連不上")));
  });
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const n = ++id;
    waiting.set(n, { resolve, reject });
    ws.send(JSON.stringify({ id: n, method, params }));
  });
  return { open, send, events, close: () => ws.close() };
}

// 🔴 大標／副標的算法**逐字抄自 index.html 的 drawTitle 呼叫點**。
//    抄錯＝板子上那兩句跟畫面不一樣，而且看起來一樣像成功。
const COPY_ALGO =
  'head = tov ? tov.head : sc.head；' +
  'sub = waitOv ? waitOv : tov ? tov.sub : s00 ? standbySub(REPLAY,LIVE.stage) ' +
  ': s11 ? loopSub(REPLAY,LIVE.stage) : sc.sub';

const PROBE = `(function(){
  try {
    const sc = (typeof scene === "function") ? scene() : null;
    const tov = (typeof director !== "undefined") ? director.titleOv : null;
    const waitOv = (typeof director !== "undefined" && director.mode === "wait"
        && typeof waitSub === "function")
      ? waitSub(director.waitAct, (typeof spawnQueue !== "undefined" ? spawnQueue.length : 0))
      : null;
    const sid = (typeof sceneId !== "undefined") ? sceneId : null;
    const sub = waitOv ? waitOv
      : tov ? tov.sub
      : sid === "s00" && typeof standbySub === "function"
          ? standbySub(REPLAY, LIVE.stage)
      : sid === "s11" && typeof loopSub === "function"
          ? loopSub(REPLAY, LIVE.stage)
      : (sc ? sc.sub : null);
    return JSON.stringify({
      scene_id: sid,
      head: tov ? tov.head : (sc ? sc.head : null),
      sub: (sub && typeof sub === "object") ? JSON.stringify(sub) : sub,
      title_ov_source: tov ? (tov.__seam ? "twinseam.js"
                             : tov.__seamEnd ? "scenes/seam_ending.js"
                             : "index.html(beatTitle/其他)")
                           : "index.html(SCENES 烤死字串)",
      data_twinseam: document.documentElement.getAttribute("data-twinseam"),
      data_seamending: document.documentElement.getAttribute("data-seamending"),
      // 兩層到底掛上去了沒有——**問頁面，不是問我們裝過了**
      layer_twinseam_loaded: !!window.__twinSeam,
      layer_seamending_loaded: !!window.__seamEnding,
      script_srcs: Array.from(document.scripts).map(s => s.getAttribute("src")).filter(Boolean),
      director_mode: (typeof director !== "undefined") ? director.mode : null,
      waiting_len: (typeof arrivals !== "undefined" && arrivals.waiting)
                   ? arrivals.waiting.length : null,
      snapA: (typeof snapA !== "undefined") ? snapA : null,
      viewport: [window.innerWidth, window.innerHeight],
      scene_index_keys: (typeof SCENE_INDEX !== "undefined" && SCENE_INDEX)
                        ? Object.keys(SCENE_INDEX).length : null
    });
  } catch (e) { return JSON.stringify({ probe_error: String(e) }); }
})()`;

async function baseSha(url) {
  try {
    const r = await fetch(url);
    if (!r.ok) return null;
    const b = Buffer.from(await r.arrayBuffer());
    return crypto.createHash("sha256").update(b).digest("hex");
  } catch (e) { return null; }   // 抓不到寫 null，不寫空字串、不寫 0
}

let code = 2;
try {
  const wsUrl = await targetWs();
  if (!wsUrl) throw new Error("找不到 CDP 目標（Chrome 沒起來？）\n" + chromeErr.slice(-800));
  const c = cdp(wsUrl);
  await c.open;
  await c.send("Runtime.enable");
  await c.send("Page.enable");
  await sleep(DWELL);

  // 等到指定的那一幕真的上來（見 EXPECT 的註解）。等不到就**說出來**，
  // 不按快門——一張拍錯幕的圖跟一張拍對的圖看起來一樣像成功。
  // 🔴 **上限用牆上的時間，不用迴圈次數。** 第一版寫 `for (k<120)` ＋ 每圈
  //    `sleep(500)`，算起來以為是 60 秒。實際上 headless 這一頁只跑 2.8 fps，
  //    每一發 `Runtime.evaluate` 要排在 rAF 後面 ⇒ 一圈實際 2–3 秒，
  //    120 圈 ＝ **五分鐘**。整批 11 格就這樣掛在第一格上，
  //    而且外面看起來跟「當掉」一模一樣（log 0 bytes）。
  const t0 = Date.now();
  let scene_wait_s = 0;
  if (EXPECT) {
    let got = null;
    while (Date.now() - t0 < 75000) {
      const r = await c.send("Runtime.evaluate", {
        expression: '(typeof sceneId !== "undefined") ? sceneId : null',
        returnByValue: true });
      got = r.result && r.result.value;
      if (got === EXPECT) break;
      await sleep(600);
    }
    scene_wait_s = Math.round((Date.now() - t0) / 100) / 10;
    if (got !== EXPECT) {
      throw new Error(`等不到 ${EXPECT}（等了 ${scene_wait_s}s，現在是 ${got}）`);
    }
  }

  // snapA 歸零才按快門（交叉溶接沒跑完就截 ⇒ 兩幕疊在一起）
  let settled = false;
  const t1 = Date.now();
  while (Date.now() - t1 < 20000) {          // 牆上時間，理由同上
    const r = await c.send("Runtime.evaluate", {
      expression: '(typeof snapA !== "undefined") ? snapA : 0', returnByValue: true });
    const v = r.result && r.result.value;
    if (!v || v <= 0.001) { settled = true; break; }
    await sleep(300);
  }

  const ev = await c.send("Runtime.evaluate", { expression: PROBE, returnByValue: true });
  if (ev.exceptionDetails) throw new Error("讀字時炸了：" + JSON.stringify(ev.exceptionDetails));
  const state = JSON.parse(ev.result.value);
  if (state.probe_error) throw new Error("頁面上取字失敗：" + state.probe_error);

  const shot = await c.send("Page.captureScreenshot", { format: "png" });
  fs.writeFileSync(OUT, Buffer.from(shot.data, "base64"));

  const consoleLines = c.events
    .filter((e) => e.method === "Runtime.consoleAPICalled")
    .map((e) => e.params.type + ": "
      + (e.params.args || []).map((a) => a.value ?? a.description ?? "").join(" "))
    .slice(-14);

  const meta = {
    ok: true,
    out: OUT,
    url: URL_,
    shot_at: new Date().toISOString(),
    dwell_ms: DWELL,
    expect_scene: EXPECT,
    scene_wait_s,
    snap_settled: settled,
    png_bytes: fs.statSync(OUT).size,
    base_sha256: await baseSha(URL_.split("?")[0]),
    copy_algo: COPY_ALGO,
    ...state,
    console: consoleLines,
  };
  fs.writeFileSync(OUT.replace(/\.png$/, ".json"), JSON.stringify(meta, null, 2));
  console.log(JSON.stringify(meta, null, 2));
  c.close();
  code = 0;
} catch (err) {
  console.log(JSON.stringify({ ok: false, url: URL_,
                               why: String((err && err.message) || err) }, null, 2));
} finally {
  clearTimeout(watchdog);
  killChrome();
}
process.exit(code);
