// VERIFY: 我自己站在展場前面當觀眾。三個問題各自量。
// (a) 按下送出，一秒內看得出我的東西進去了嗎  → 量 click→p5 可見的毫秒數
// (b) 螢幕上哪一個是我，我認得出來嗎          → 截記號那一塊，並印出頁面上的文字
// (c) 我等了五分鐘，這期間我知道發生什麼事嗎  → 完全不讓展場電腦動，看 0s/30s/120s/300s
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

const BASE = "http://127.0.0.1:3377";
const OUT = process.argv[2];
fs.mkdirSync(OUT, { recursive: true });
const log = [];
function say(s){ console.log(s); log.push(s); }

async function fill(page){
  await page.click("#startBtn");
  await page.waitForTimeout(400);
  await page.click("#adultBtn");
  await page.waitForTimeout(400);
  await page.click("#copyBtn");
  await page.waitForTimeout(1300);
  await page.click("#gotBtn");
  await page.waitForTimeout(400);
  await page.fill("#paste",
    "需求：把桌上散開的收據整理成一份清單\n形狀：圓潤\n質感：指紋\n色系：暖土\n氣質：安靜、細心、不慌\n第一句話：這裡的光有點暖。");
  await page.click("#mine");
}

const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width: 390, height: 844 }, deviceScaleFactor: 2,
  isMobile: true, hasTouch: true, locale: "zh-TW",
});
const page = await ctx.newPage();
page.on("console", m => { if (m.type()==="error") say("  [console.error] "+m.text()); });
page.on("pageerror", e => say("  [pageerror] "+e.message));

await page.goto(BASE + "/", { waitUntil: "networkidle" });
await page.screenshot({ path: path.join(OUT, "audience-q", "A0_landing.png") });
await fill(page);
await page.screenshot({ path: path.join(OUT, "audience-q", "A1_ready_to_submit.png") });

// ---------- (a) 送出那一秒 ----------
// 在瀏覽器裡插一個 rAF 觀測器：記 click 到 p5 真的可見（畫面上畫出來）之間的時間。
await page.evaluate(() => {
  window.__t = {};
  const p5 = document.getElementById("p5");
  window.__t.click = null;
  document.getElementById("submitBtn").addEventListener("click",
    () => { window.__t.click = performance.now(); }, true);
  const tick = () => {
    if (window.__t.click && !window.__t.p5visible){
      const cs = getComputedStyle(p5);
      if (p5.classList.contains("on") && cs.opacity > 0.5 && cs.visibility !== "hidden"){
        window.__t.p5visible = performance.now();
      }
    }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
});

await page.click("#submitBtn");
// 200ms 就截 —— 觀眾按完馬上看螢幕
await page.waitForTimeout(200);
await page.screenshot({ path: path.join(OUT, "audience-q", "A2_t+200ms.png") });
await page.waitForTimeout(300);
await page.screenshot({ path: path.join(OUT, "audience-q", "A3_t+500ms.png") });
await page.waitForTimeout(500);
await page.screenshot({ path: path.join(OUT, "audience-q", "A4_t+1000ms.png") });

const t = await page.evaluate(() => window.__t);
const latency = (t.p5visible && t.click) ? (t.p5visible - t.click) : null;
say(`(a) click→p5 實際可見：${latency === null ? "null（沒量到）" : latency.toFixed(1)+" ms"}`);

// ---------- (b) 記號 ----------
const markTxt = await page.evaluate(() => {
  const b = document.getElementById("mark5");
  if (!b) return null;
  return {
    word: b.querySelector(".markword")?.textContent,
    say:  b.querySelector(".marksay")?.textContent,
    sub:  b.querySelector(".marksub")?.innerText,
    glyphPainted: (() => {
      const c = b.querySelector("canvas.markglyph");
      if (!c) return null;
      try {
        const g = c.getContext("2d");
        const d = g.getImageData(0,0,c.width,c.height).data;
        let nz = 0; for (let i=3;i<d.length;i+=4) if (d[i]>8) nz++;
        return { w:c.width, h:c.height, nonTransparentPx: nz };
      } catch(e){ return "ERR:"+e.message; }
    })(),
  };
});
say("(b) 記號區塊：" + JSON.stringify(markTxt, null, 2));
const box = await page.locator("#mark5").boundingBox();
if (box) await page.screenshot({ path: path.join(OUT,"audience-q","B1_mark_closeup.png"), clip: box });

// ---------- (c) 五分鐘沒人理你 ----------
// 完全不呼叫 /api/claim、不回 result。展場電腦忙著、佇列前面還有人的情況。
const marks = [0, 30, 60, 120, 300];
const start = Date.now();
const seen = [];
for (const s of marks){
  while ((Date.now() - start) / 1000 < s) await page.waitForTimeout(500);
  const state = await page.evaluate(() => {
    const steps = [...document.querySelectorAll(".stagebar .step")]
      .map(e => ({ text: e.textContent.trim(), cls: e.className }));
    return {
      panel: [...document.querySelectorAll("section.panel")].find(p=>p.classList.contains("on"))?.id,
      h2: document.querySelector("#p5 h2")?.textContent,
      hint: document.querySelector("#p5 .hint")?.textContent,
      steps,
    };
  });
  seen.push({ at: s, state });
  say(`(c) t=${s}s → panel=${state.panel} steps=${state.steps.map(x=>x.text+"["+x.cls+"]").join(" | ")}`);
  await page.screenshot({ path: path.join(OUT, "wait-5min", `C_t${String(s).padStart(3,"0")}s.png`) });
}
// 五分鐘內畫面上的「文字資訊」有沒有任何一個字變過？
const sigs = seen.map(x => JSON.stringify(x.state));
const distinct = new Set(sigs).size;
say(`(c) 五個時間點畫面狀態去重後 = ${distinct} 種（1 = 五分鐘完全沒變）`);

fs.writeFileSync(path.join(OUT, "audience-q", "measurements.txt"), log.join("\n")+"\n");
await browser.close();
