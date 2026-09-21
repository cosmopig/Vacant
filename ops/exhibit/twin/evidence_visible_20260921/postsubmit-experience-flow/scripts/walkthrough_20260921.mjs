// 390×844 逐步截圖：掃碼 → 用自己的 AI → 貼回來 → 送出 → 三階段 → 抬頭 → 分身上螢幕。
// 另外跑一次「不用 AI」的示範分身路，和一次負控制（把 triggerLookUp 關掉，
// 對照有沒有抬頭那一秒的差別）。
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

const BASE = "http://localhost:3311";
const TOKEN = "t1";
const OUT = process.argv[2] || "/tmp/claude-501/shots_final";
fs.mkdirSync(OUT, { recursive: true });
for (const sub of ["ai-path", "no-ai-path", "negctl-no-lookup"]) {
  fs.mkdirSync(path.join(OUT, sub), { recursive: true });
}

const venueHeaders = { "Content-Type": "application/json", "Authorization": "Bearer " + TOKEN };

async function venueDeliver(id, cardPngPath) {
  // 扮演展場電腦：claim → result（帶一張示範卡圖），把 submission 推進 done。
  await fetch(`${BASE}/api/claim?token=${TOKEN}`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids: [id] }),
  });
  const png = fs.readFileSync(cardPngPath).toString("base64");
  await fetch(`${BASE}/api/result?token=${TOKEN}`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, verdict: "matched", matched: true,
      card_png: "data:image/png;base64," + png }),
  });
}

async function shot(page, dir, name) {
  await page.screenshot({ path: path.join(OUT, dir, name) });
  console.log("  shot:", dir + "/" + name);
}

async function run() {
  const browser = await chromium.launch();

  // ===================== 1) 掃碼 AI 路（主線）=====================
  {
    const ctx = await browser.newContext({
      viewport: { width: 390, height: 844 }, deviceScaleFactor: 2,
      isMobile: true, hasTouch: true, locale: "zh-TW",
      permissions: [],
    });
    const page = await ctx.newPage();
    const dir = "ai-path";

    // 00 掃碼落地（QR 指向這一頁）
    await page.goto(BASE + "/", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    await shot(page, dir, "00_landing.png");

    // 開始 → 分岔（年齡／可以拒絕）
    await page.click("#startBtn");
    await page.waitForTimeout(550);
    await shot(page, dir, "01_fork_before_ai.png");

    // 選「我滿18歲了」→ 進提示詞
    await page.click("#adultBtn");
    await page.waitForTimeout(550);
    await shot(page, dir, "02_copy_prompt.png");

    await page.click("#copyBtn");
    await page.waitForTimeout(1250); // 複製成功動畫 → 自動跳下一景
    await shot(page, dir, "03_go_to_your_ai.png");

    // 開啟 app-link 除錯視圖，證明三顆按鈕真的有算出對應平台的連結。
    // ⚠ 不能用 page.goto 重載這個 page——那會重置 ageGate 等頁面內 JS 狀態，
    // 後面送出會被「缺兩個宣告」擋下。開一個獨立分頁看，不動主流程這頁的狀態。
    {
      const dbgPage = await ctx.newPage();
      await dbgPage.goto(BASE + "/?step=3&debug=applink", { waitUntil: "networkidle" });
      await dbgPage.waitForTimeout(400);
      await dbgPage.screenshot({ path: path.join(OUT, dir, "03b_applink_debug.png") });
      console.log("  shot:", dir + "/03b_applink_debug.png");
      await dbgPage.close();
    }

    // 回到正常流程：貼回來（同一個 page，狀態沒被動過）
    await page.click("#gotBtn");
    await page.waitForTimeout(550);
    await page.fill("#paste",
      "需求：把桌上散開的收據整理成一份清單\n形狀：圓潤\n質感：指紋\n色系：暖土\n氣質：安靜、細心、不慌\n第一句話：這裡的光有點暖。");
    await page.click("#mine");
    await shot(page, dir, "04_paste_and_confirm.png");

    // 送出
    await page.click("#submitBtn");
    await page.waitForTimeout(700);
    await shot(page, dir, "05_stage_arrived.png"); // 抵達了（queued）

    const idAfterSubmit = await page.evaluate(() => localStorage.getItem("vacant_id"));
    console.log("submission id:", idAfterSubmit);

    // 展場電腦 claim → claimed（正在成形）
    await fetch(`${BASE}/api/claim?token=${TOKEN}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: [idAfterSubmit] }),
    });
    await page.waitForTimeout(4300); // 等下一輪 4s 輪詢真的打到 claimed
    await shot(page, dir, "06_stage_forming.png"); // 正在成形（claimed）

    // 展場電腦回結果 → done。用 waitForFunction 在動畫觸發的瞬間連續截幾張，
    // 抓「抬頭看螢幕」那個全螢幕暖光閃光 + 文字的畫面（lookup.on 存在的 ~1.05s 窗口內）。
    const cardPng = "/Users/cosmopig/Documents/GitHub/vacant-world-cloud/public/img/c3.png";
    const b64 = fs.readFileSync(cardPng).toString("base64");
    const resultPromise = fetch(`${BASE}/api/result?token=${TOKEN}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: idAfterSubmit, verdict: "matched", matched: true,
        card_png: "data:image/png;base64," + b64 }),
    });
    await resultPromise;
    // 下一輪 poll 在 4s 內會打到；用短間隔輪詢畫面直到 lookup.on 出現
    let caught = false;
    for (let i = 0; i < 60; i++) {
      const on = await page.evaluate(() => document.getElementById("lookup").classList.contains("on"));
      if (on && !caught) { caught = true; await shot(page, dir, "07_LOOKUP_CUE_flash.png"); }
      const doneVisible = await page.evaluate(() => document.getElementById("p6").classList.contains("on"));
      if (doneVisible) break;
      await page.waitForTimeout(100);
    }
    await page.waitForTimeout(600);
    await shot(page, dir, "08_done_on_screen.png"); // 上螢幕了（完成頁＋卡片＋撤回碼）

    await ctx.close();
  }

  // ===================== 2) 不用自己的 AI（示範分身）路 =====================
  {
    const ctx = await browser.newContext({
      viewport: { width: 390, height: 844 }, deviceScaleFactor: 2,
      isMobile: true, hasTouch: true, locale: "zh-TW",
    });
    const page = await ctx.newPage();
    const dir = "no-ai-path";

    await page.goto(BASE + "/", { waitUntil: "networkidle" });
    await page.click("#startBtn");
    await page.waitForTimeout(500);
    await shot(page, dir, "01_fork.png");

    // 按下「我不想給我自己的資料」——這是體驗這條線要做的：點下去發生什麼
    await page.click("#refuseBtn");
    // 立刻截：要看到「正在挑一隻示範分身…」這個立即文字回饋（不是空白等待）
    await page.waitForTimeout(60);
    await shot(page, dir, "02_INSTANT_FEEDBACK_picking.png");

    await page.waitForTimeout(700);
    await shot(page, dir, "03_stage_with_demo_note.png"); // p5，含「這一隻是示範分身」提示

    const idPreset = await page.evaluate(() => localStorage.getItem("vacant_id"));
    console.log("preset id:", idPreset);
    await fetch(`${BASE}/api/claim?token=${TOKEN}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: [idPreset] }),
    });
    const cardPng2 = "/Users/cosmopig/Documents/GitHub/vacant-world-cloud/public/img/c1.png";
    const b64_2 = fs.readFileSync(cardPng2).toString("base64");
    await fetch(`${BASE}/api/result?token=${TOKEN}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: idPreset, verdict: "matched", matched: true,
        card_png: "data:image/png;base64," + b64_2 }),
    });
    for (let i = 0; i < 60; i++) {
      const doneVisible = await page.evaluate(() => document.getElementById("p6").classList.contains("on"));
      if (doneVisible) break;
      await page.waitForTimeout(150);
    }
    await page.waitForTimeout(500);
    await shot(page, dir, "04_done_demo_avatar.png");

    await ctx.close();
  }

  // ===================== 3) 負控制：把 triggerLookUp 關掉，證明「有差別」=====================
  {
    const ctx = await browser.newContext({
      viewport: { width: 390, height: 844 }, deviceScaleFactor: 2,
      isMobile: true, hasTouch: true, locale: "zh-TW",
    });
    const page = await ctx.newPage();
    const dir = "negctl-no-lookup";

    await page.goto(BASE + "/", { waitUntil: "networkidle" });
    // 負控制：讓 triggerLookUp 變成立刻 resolve、不做任何視覺／震動／聲音動作，
    // 模擬「這次任務要修的舊行為」——done 直接無聲跳轉。
    await page.evaluate(() => { window.triggerLookUp = () => Promise.resolve(); });
    await page.click("#startBtn");
    await page.click("#adultBtn");
    await page.click("#copyBtn");
    await page.waitForTimeout(1250);
    await page.click("#gotBtn");
    await page.fill("#paste", "需求：測試\n形狀：圓潤\n質感：指紋\n色系：暖土\n氣質：安靜\n第一句話：嗨");
    await page.click("#mine");
    await page.click("#submitBtn");
    await page.waitForTimeout(600);
    const id3 = await page.evaluate(() => localStorage.getItem("vacant_id"));
    await fetch(`${BASE}/api/claim?token=${TOKEN}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: [id3] }),
    });
    const cardPng3 = "/Users/cosmopig/Documents/GitHub/vacant-world-cloud/public/img/c2.png";
    const b64_3 = fs.readFileSync(cardPng3).toString("base64");
    await fetch(`${BASE}/api/result?token=${TOKEN}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: id3, verdict: "matched", matched: true,
        card_png: "data:image/png;base64," + b64_3 }),
    });
    // 在 done 出現的瞬間連續截圖，證明「沒有 triggerLookUp」時完全沒有閃光/文字
    let shotOnceAt5 = false;
    for (let i = 0; i < 60; i++) {
      const cur5 = await page.evaluate(() => document.getElementById("p5").classList.contains("on"));
      if (cur5 && !shotOnceAt5) { shotOnceAt5 = true; await shot(page, dir, "01_still_on_p5_forming.png"); }
      const lookupOn = await page.evaluate(() => document.getElementById("lookup").classList.contains("on"));
      if (lookupOn) { await shot(page, dir, "02_UNEXPECTED_lookup_fired.png"); }
      const doneVisible = await page.evaluate(() => document.getElementById("p6").classList.contains("on"));
      if (doneVisible) break;
      await page.waitForTimeout(100);
    }
    await page.waitForTimeout(400);
    await shot(page, dir, "03_done_SILENT_no_cue.png"); // 對照組：直接無聲跳到完成頁

    await ctx.close();
  }

  await browser.close();
  console.log("ALL DONE ->", OUT);
}

run().catch(e => { console.error(e); process.exit(1); });
