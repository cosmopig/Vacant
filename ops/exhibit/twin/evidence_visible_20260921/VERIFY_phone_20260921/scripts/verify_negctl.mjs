// 我自己的負控制 + 直接驗證它宣稱修好的兩件事。
//  N1 抬頭那一秒：ON vs OFF，兩張圖要看得出差別
//  N2 safe center：ON vs OFF（390×844），標題有沒有被切
//  R1 poll() 說謊：status=done 但 card_url 還沒好 → 第三格不可以提前亮
import { chromium } from "playwright";
import fs from "node:fs"; import path from "node:path";
const BASE="http://127.0.0.1:3378", TOKEN="vt1";
const OUT=process.argv[2]; const log=[]; const say=s=>{console.log(s);log.push(s);};
for (const d of ["negctl-lookup","negctl-safecenter","regress"]) fs.mkdirSync(path.join(OUT,d),{recursive:true});

const browser = await chromium.launch();
const harden = (page) => {
  const orig = page.screenshot.bind(page);
  page.screenshot = async (opts) => {
    for (let k=0;k<3;k++){
      try { return await orig({ ...opts, timeout:12000, animations:"disabled" }); }
      catch(e){ say("  [snap retry "+(k+1)+"] "+e.message.split("\n")[0]);
                await page.waitForTimeout(1500); }
    }
    say("  SNAPFAIL "+opts.path); return null;
  };
  return page;
};
const walk = async (page) => {
  await page.click("#startBtn"); await page.waitForTimeout(350);
  await page.click("#adultBtn"); await page.waitForTimeout(350);
  await page.click("#copyBtn");  await page.waitForTimeout(1300);
  await page.click("#gotBtn");   await page.waitForTimeout(350);
  await page.fill("#paste","需求：整理收據\n形狀：圓潤\n質感：指紋\n色系：暖土\n氣質：安靜\n第一句話：這裡的光有點暖。");
  await page.click("#mine"); await page.click("#submitBtn");
  await page.waitForTimeout(800);
  return page.evaluate(()=>localStorage.getItem("vacant_id"));
};
const claim = id => fetch(`${BASE}/api/claim?token=${TOKEN}`,{method:"POST",
  headers:{"Content-Type":"application/json"},body:JSON.stringify({ids:[id]})});
const result = (id, withCard) => {
  const body = { id, verdict:"matched", matched:true };
  if (withCard){
    const b64 = fs.readFileSync("/Users/cosmopig/Documents/GitHub/vacant-world-cloud/public/img/c3.png").toString("base64");
    body.card_png = "data:image/png;base64,"+b64;
  }
  return fetch(`${BASE}/api/result?token=${TOKEN}`,{method:"POST",
    headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
};

// ───────── N1 抬頭那一秒 ─────────
for (const mode of ["ON","OFF"]){
  const ctx = await browser.newContext({ viewport:{width:390,height:844}, deviceScaleFactor:2,
    isMobile:true, hasTouch:true, locale:"zh-TW" });
  const page = harden(await ctx.newPage());
  await page.goto(BASE+"/",{waitUntil:"networkidle"});
  if (mode==="OFF"){
    // 負控制：把 triggerLookUp 換成空實作（頂層 function 宣告 ⇒ 是 window 屬性，蓋得掉）
    const ok = await page.evaluate(()=>{
      const before = typeof window.triggerLookUp;
      window.triggerLookUp = () => Promise.resolve();
      return { before, after: typeof window.triggerLookUp,
               overrodeRealOne: before === "function" };
    });
    say("  N1-OFF 覆寫檢查："+JSON.stringify(ok));
    if (!ok.overrodeRealOne) say("  🔴 負控制無效：triggerLookUp 本來就不在 window 上");
  }
  const id = await walk(page);
  await claim(id); await page.waitForTimeout(4600);
  await result(id, true);
  let caught=false, frames=0;
  for (let i=0;i<80;i++){
    const on = await page.evaluate(()=>document.getElementById("lookup").classList.contains("on"));
    if (on){ frames++; if(!caught){caught=true;
      await page.screenshot({path:path.join(OUT,"negctl-lookup",`N1_${mode}_at_cue.png`)}); } }
    if (await page.evaluate(()=>document.getElementById("p6").classList.contains("on"))) break;
    await page.waitForTimeout(80);
  }
  say(`  N1-${mode}: lookup.on 出現過 ${caught?"是":"否"}（抓到 ${frames} 次輪詢）`);
  if (!caught) await page.screenshot({path:path.join(OUT,"negctl-lookup",`N1_${mode}_at_cue.png`)});
  await page.waitForTimeout(700);
  await page.screenshot({path:path.join(OUT,"negctl-lookup",`N1_${mode}_after.png`)});
  await ctx.close();
}

// ───────── N2 safe center ─────────
for (const mode of ["ON","OFF"]){
  const ctx = await browser.newContext({ viewport:{width:390,height:844}, deviceScaleFactor:2,
    isMobile:true, hasTouch:true, locale:"zh-TW" });
  const page = harden(await ctx.newPage());
  await page.goto(BASE+"/",{waitUntil:"networkidle"});
  if (mode==="OFF") await page.addStyleTag({content:".panel{justify-content:center !important}"});
  const id = await walk(page);
  await claim(id); await page.waitForTimeout(4600); await result(id,true);
  for (let i=0;i<80;i++){
    if (await page.evaluate(()=>document.getElementById("p6").classList.contains("on"))) break;
    await page.waitForTimeout(100);
  }
  await page.waitForTimeout(900);
  const m = await page.evaluate(()=>{
    const p = document.getElementById("p6");
    const h = p.querySelector("h2");
    return { scrollTop:p.scrollTop, scrollHeight:p.scrollHeight, clientHeight:p.clientHeight,
             h2Top: h.getBoundingClientRect().top, h2Text: h.textContent,
             h2FullyVisible: h.getBoundingClientRect().top >= 0 };
  });
  say(`  N2-${mode}: ${JSON.stringify(m)}`);
  await page.screenshot({path:path.join(OUT,"negctl-safecenter",`N2_${mode}_p6_390x844.png`)});
  await ctx.close();
}

// ───────── R1 poll() 說謊回歸測試 ─────────
{
  const ctx = await browser.newContext({ viewport:{width:390,height:844}, deviceScaleFactor:2,
    isMobile:true, hasTouch:true, locale:"zh-TW" });
  const page = harden(await ctx.newPage());
  await page.goto(BASE+"/",{waitUntil:"networkidle"});
  const id = await walk(page);
  await claim(id); await page.waitForTimeout(4600);
  // 關鍵：回 done 但**不帶 card_png** ⇒ status=done、card_url 還沒有
  const r = await result(id, false);
  say("  R1 /api/result(no card) → HTTP "+r.status);
  await page.waitForTimeout(5200);           // 讓 poll 至少打到一輪
  const st = await page.evaluate(()=>({
    serverSays: null,
    panel:[...document.querySelectorAll("section.panel")].find(p=>p.classList.contains("on"))?.id,
    now:[...document.querySelectorAll(".stagebar .step")].find(e=>e.classList.contains("now"))?.textContent.trim(),
    thirdLit: document.getElementById("stage2").classList.contains("now")
           || document.getElementById("stage2").classList.contains("done"),
  }));
  const api = await (await fetch(`${BASE}/api/status/${id}`)).json();
  say(`  R1 伺服器說 status=${api.status} card_url=${api.card_url ?? "(無)"}`);
  say(`  R1 畫面：panel=${st.panel} 現在這格="${st.now}" 第三格亮了嗎=${st.thirdLit}`);
  say(`  R1 判定：${api.status==="done" && !api.card_url && st.panel==="p5" && !st.thirdLit
        ? "✅ 沒說謊——停在正在成形" : "🔴 說謊或前提不成立"}`);
  await page.screenshot({path:path.join(OUT,"regress",`R1_done_without_card_url.png`)});
  await ctx.close();
}

fs.writeFileSync(path.join(OUT,"negctl_measurements.txt"), log.join("\n")+"\n");
await browser.close();
