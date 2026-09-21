// 問題 (c) 的精確版：等待分成兩段——「排隊中（queued）」跟「正在成形（claimed）」。
// TIMER-V1 只在 claimed 起跳。所以要分開量：排隊那一段到底有沒有時間感。
import { chromium } from "playwright";
import fs from "node:fs"; import path from "node:path";
const BASE = "http://127.0.0.1:3378", TOKEN = "vt1";
const OUT = process.argv[2]; fs.mkdirSync(OUT, { recursive: true });
const log = []; const say = s => { console.log(s); log.push(s); };

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport:{width:390,height:844}, deviceScaleFactor:2,
  isMobile:true, hasTouch:true, locale:"zh-TW" });
const page = await ctx.newPage();
page.on("pageerror", e => say("  [pageerror] " + e.message));
await page.goto(BASE + "/", { waitUntil:"networkidle" });
await page.click("#startBtn"); await page.waitForTimeout(350);
await page.click("#adultBtn"); await page.waitForTimeout(350);
await page.click("#copyBtn");  await page.waitForTimeout(1300);
await page.click("#gotBtn");   await page.waitForTimeout(350);
await page.fill("#paste","需求：整理收據\n形狀：圓潤\n質感：指紋\n色系：暖土\n氣質：安靜\n第一句話：這裡的光有點暖。");
await page.click("#mine");
await page.click("#submitBtn");
await page.waitForTimeout(800);
const id = await page.evaluate(() => localStorage.getItem("vacant_id"));
say("submission id = " + id);

const read = () => page.evaluate(() => ({
  stepNow: [...document.querySelectorAll(".stagebar .step")].find(e=>e.classList.contains("now"))?.textContent.trim(),
  elapsed: document.getElementById("elapsed")?.textContent ?? "(no #elapsed)",
  sub: document.querySelector("#p5 .sub")?.textContent?.trim(),
}));

// ── 第一段：queued，沒人來取件。展場電腦忙／佇列前面還有 10 個人。
say("── QUEUED（展場電腦還沒來取件）──");
for (const s of [0, 30, 90, 150]){
  const t0 = Date.now();
  while (Date.now()-t0 < (s===0?0:  0)) {}
  if (s) await page.waitForTimeout(s===30?30000: s===90?60000: 60000);
  const st = await read();
  say(`  t=${s}s  現在這格="${st.stepNow}"  計時器="${st.elapsed}"`);
  await page.screenshot({ path: path.join(OUT, `Q_queued_t${String(s).padStart(3,"0")}s.png`) });
}

// ── 第二段：展場電腦取件了 → claimed
say("── CLAIMED（展場電腦取件，開始生成）──");
await fetch(`${BASE}/api/claim?token=${TOKEN}`, { method:"POST",
  headers:{"Content-Type":"application/json"}, body: JSON.stringify({ ids:[id] })});
await page.waitForTimeout(5000);   // 等下一輪 4s 輪詢
for (const s of [0, 30, 90]){
  if (s) await page.waitForTimeout(s===30?30000:60000);
  const st = await read();
  say(`  claimed+${s}s  現在這格="${st.stepNow}"  計時器="${st.elapsed}"`);
  await page.screenshot({ path: path.join(OUT, `Q_claimed_t${String(s).padStart(3,"0")}s.png`) });
}
fs.writeFileSync(path.join(OUT, "wait_measurements.txt"), log.join("\n")+"\n");
await browser.close();
