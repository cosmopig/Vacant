// 項目 4 的體驗側：「我不想給我自己的資料」按下去之後發生什麼。
// 量：按下到畫面出現回饋的毫秒數；示範分身的標示有沒有真的出現。
// 另外驗 app-link：三顆按鈕的 href 是不是真的隨 UA 算出不同深連結。
import { chromium, devices } from "playwright";
import fs from "node:fs"; import path from "node:path";
const BASE="http://127.0.0.1:3378", TOKEN="vt1";
const OUT=process.argv[2]; fs.mkdirSync(OUT,{recursive:true});
const log=[]; const say=s=>{console.log(s);log.push(s);};
const browser = await chromium.launch();

// ── A. 不用 AI 的路 ──
{
  const ctx = await browser.newContext({ viewport:{width:390,height:844}, deviceScaleFactor:2,
    isMobile:true, hasTouch:true, locale:"zh-TW" });
  const page = await ctx.newPage();
  page.on("pageerror", e=>say("  [pageerror] "+e.message));
  await page.goto(BASE+"/",{waitUntil:"networkidle"});
  await page.click("#startBtn"); await page.waitForTimeout(450);
  await page.screenshot({path:path.join(OUT,"NOAI_1_fork.png"),animations:"disabled"});

  const label0 = await page.textContent("#refuseBtn");
  const t0 = Date.now();
  await page.click("#refuseBtn");
  // 輪詢到按鈕文字變了為止，量真正的回饋延遲
  let label1=label0, dt=null;
  for (let i=0;i<200;i++){
    label1 = await page.textContent("#refuseBtn");
    if (label1 !== label0){ dt = Date.now()-t0; break; }
    await page.waitForTimeout(10);
  }
  say(`  按鈕文字 "${label0.trim()}" → "${label1.trim()}"，延遲 ${dt===null?"null（沒變）":dt+" ms"}`);
  await page.screenshot({path:path.join(OUT,"NOAI_2_instant_feedback.png"),animations:"disabled"});

  // 等進 p5
  let onP5=false;
  for (let i=0;i<200;i++){
    if (await page.evaluate(()=>document.getElementById("p5").classList.contains("on"))){onP5=true;break;}
    await page.waitForTimeout(50);
  }
  const arriveMs = Date.now()-t0;
  say(`  按下到進入「成形中」頁：${onP5? arriveMs+" ms":"null（沒進到 p5）"}`);
  await page.waitForTimeout(600);
  const note = await page.evaluate(()=>{
    const n=[...document.querySelectorAll(".presetNote")].filter(e=>e.offsetParent!==null);
    return { count:n.length, texts:n.map(e=>e.textContent.trim()) };
  });
  say("  示範分身標示："+JSON.stringify(note));
  await page.screenshot({path:path.join(OUT,"NOAI_3_forming_with_demo_note.png"),animations:"disabled"});

  const id = await page.evaluate(()=>localStorage.getItem("vacant_id"));
  const api = await (await fetch(`${BASE}/api/status/${id}`)).json();
  say("  伺服器端 origin="+api.origin+" preset_key="+(api.preset_key??"(無)"));
  await ctx.close();
}

// ── B. app-link 深連結：真的隨 UA 變嗎 ──
for (const [name, dev] of [["iPhone", devices["iPhone 13"]], ["Android", devices["Pixel 5"]]]){
  const ctx = await browser.newContext({ ...dev, locale:"zh-TW" });
  const page = await ctx.newPage();
  await page.goto(BASE+"/?step=3&debug=applink",{waitUntil:"networkidle"});
  await page.waitForTimeout(500);
  const links = await page.evaluate(()=>
    [...document.querySelectorAll(".appbtn")].map(a=>({t:a.textContent.trim().slice(0,12), href:a.getAttribute("href")})));
  say(`  ${name} UA → ` + JSON.stringify(links));
  await page.screenshot({path:path.join(OUT,`APPLINK_${name}.png`),animations:"disabled"});
  await ctx.close();
}
fs.writeFileSync(path.join(OUT,"noai_applink_measurements.txt"), log.join("\n")+"\n");
await browser.close();
