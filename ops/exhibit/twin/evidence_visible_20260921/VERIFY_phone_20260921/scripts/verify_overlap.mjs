// 我在自己的截圖裡看到：完成頁底部那兩行字被固定的「撤回碼…刪掉它」那一條蓋住。
// 先證明量得動：量 .wbar 的矩形 vs 被它蓋住的元素的矩形，算實際重疊像素高度。
// 並且捲到底再量一次——如果捲到底還蓋著，那就不是「捲一下就好」。
import { chromium } from "playwright";
import fs from "node:fs"; import path from "node:path";
const BASE="http://127.0.0.1:3378", TOKEN="vt1";
const OUT=process.argv[2]; fs.mkdirSync(OUT,{recursive:true});
const log=[]; const say=s=>{console.log(s);log.push(s);};

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport:{width:390,height:844}, deviceScaleFactor:2,
  isMobile:true, hasTouch:true, locale:"zh-TW" });
const page = await ctx.newPage();
await page.goto(BASE+"/",{waitUntil:"networkidle"});
await page.click("#startBtn"); await page.waitForTimeout(350);
await page.click("#adultBtn"); await page.waitForTimeout(350);
await page.click("#copyBtn");  await page.waitForTimeout(1300);
await page.click("#gotBtn");   await page.waitForTimeout(350);
await page.fill("#paste","需求：整理收據\n形狀：圓潤\n質感：指紋\n色系：暖土\n氣質：安靜\n第一句話：這裡的光有點暖。");
await page.click("#mine"); await page.click("#submitBtn"); await page.waitForTimeout(800);
const id = await page.evaluate(()=>localStorage.getItem("vacant_id"));
await fetch(`${BASE}/api/claim?token=${TOKEN}`,{method:"POST",
  headers:{"Content-Type":"application/json"},body:JSON.stringify({ids:[id]})});
await page.waitForTimeout(4600);
const b64=fs.readFileSync("/Users/cosmopig/Documents/GitHub/vacant-world-cloud/public/img/c3.png").toString("base64");
await fetch(`${BASE}/api/result?token=${TOKEN}`,{method:"POST",
  headers:{"Content-Type":"application/json"},
  body:JSON.stringify({id,verdict:"matched",matched:true,card_png:"data:image/png;base64,"+b64})});
for (let i=0;i<80;i++){
  if (await page.evaluate(()=>document.getElementById("p6").classList.contains("on"))) break;
  await page.waitForTimeout(100);
}
await page.waitForTimeout(1500);

const measure = () => page.evaluate(() => {
  const wbar = document.getElementById("wbar");
  const wr = wbar.getBoundingClientRect();
  const p6 = document.getElementById("p6");
  const cands = [...p6.querySelectorAll("p,span,a,div,h2")]
    .filter(e => e.offsetParent !== null && e.textContent.trim());
  const hit = [];
  for (const e of cands){
    const r = e.getBoundingClientRect();
    if (r.height === 0 || r.width === 0) continue;
    if (r.bottom <= 0 || r.top >= window.innerHeight) continue;   // 不在視窗內就不算
    const ov = Math.min(r.bottom, wr.bottom) - Math.max(r.top, wr.top);
    if (ov > 1) hit.push({ txt: e.textContent.trim().slice(0,28),
                           overlapPx: +ov.toFixed(1),
                           coveredPct: +(100*ov/r.height).toFixed(0) });
  }
  return {
    wbar: { top:+wr.top.toFixed(1), height:+wr.height.toFixed(1),
            opaque: getComputedStyle(wbar).backgroundColor,
            zIndex: getComputedStyle(wbar).zIndex },
    panelPadBottom: getComputedStyle(p6).paddingBottom,
    scrollTop: p6.scrollTop, scrollHeight: p6.scrollHeight, clientHeight: p6.clientHeight,
    atBottom: p6.scrollHeight - p6.clientHeight - p6.scrollTop < 2,
    covered: hit,
  };
});

say("── 完成頁載入時（沒捲）──");
let m = await measure(); say(JSON.stringify(m, null, 2));
await page.screenshot({ path: path.join(OUT,"OVERLAP_1_top.png"), animations:"disabled" });

say("── 捲到底 ──");
await page.evaluate(()=>{ const p=document.getElementById("p6"); p.scrollTop = p.scrollHeight; });
await page.waitForTimeout(600);
m = await measure(); say(JSON.stringify(m, null, 2));
await page.screenshot({ path: path.join(OUT,"OVERLAP_2_scrolled_to_bottom.png"), animations:"disabled" });

fs.writeFileSync(path.join(OUT,"overlap_measurements.txt"), log.join("\n")+"\n");
await browser.close();
