#!/usr/bin/env node
// 目標唯一：直接重現「s11 全員上台」那個瞬間的突發，量 activeVideos 在
// **同一個瀏覽器事件迴圈內**（不等任何額外 rAF）有沒有被壓回 MAX_ACTIVE_DECODES。
// 用 CPU throttling 4x 逼近泡機當下 fps<0.2 的同機重負載情境（不是精確重放，
// 但方向一致：讓 rAF 變稀疏，藉此驗證「不依賴 rAF 節流」這句話是不是真的）。
import puppeteer from 'puppeteer-core';
import fs from 'node:fs';

function arg(name, def) { const i = process.argv.indexOf(`--${name}`); return i === -1 ? def : process.argv[i + 1]; }
const URL = arg('url', 'http://127.0.0.1:8701/index.html');
const TAG = arg('tag', 'base');
const THROTTLE = parseFloat(arg('throttle', '1'));   // CDP CPU throttling rate
const OUT = arg('out', './burst_out.json');
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const UDD = `/tmp/burstrepro-udd-${TAG}-${Date.now()}`;

async function main() {
  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: 'new', userDataDir: UDD,
    args: ['--window-size=1280,720', '--autoplay-policy=no-user-gesture-required',
      '--mute-audio', '--disable-gpu', '--disable-gpu-compositing', '--use-gl=swiftshader',
      '--no-first-run', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 720 });
  const pageErrors = [];
  page.on('pageerror', e => pageErrors.push(String(e)));
  page.on('console', msg => { if (msg.type() === 'error') pageErrors.push(`console.error: ${msg.text()}`); });

  const cdp = await page.createCDPSession();

  await page.goto(URL, { waitUntil: 'load', timeout: 60000 });
  await new Promise(r => setTimeout(r, 3000));   // 讓自然的 invite 流程先墊一批片進 pool

  // 節流放在載入完成「之後」才開——節流頁面首次載入本身會撞 navigation
  // timeout（量具第一版的錯，記取 instruments-lie-before-you-conclude-zero）；
  // 我們要模擬的是「頁面已經在跑，這時候同機忽然變擠」，不是「開頁面時就很擠」。
  if (THROTTLE > 1) await cdp.send('Emulation.setCPUThrottlingRate', { rate: THROTTLE });

  // 量具負控制：先確認 videoPool/cast/enforceDecodeCap 這三個名字真的存在，
  // 不是打錯字打到 undefined 恆真恆假（instruments-lie-before-you-conclude-zero）。
  const selfCheck = await page.evaluate(() => ({
    hasPool: typeof videoPool !== 'undefined',
    hasCast: typeof cast !== 'undefined',
    hasEnforce: typeof enforceDecodeCap === 'function',
    hasMax: typeof MAX_ACTIVE_DECODES !== 'undefined' ? MAX_ACTIVE_DECODES : null,
    poolSizeBefore: typeof videoPool !== 'undefined' ? videoPool.size : null,
  }));
  if (!selfCheck.hasPool || !selfCheck.hasCast) {
    fs.writeFileSync(OUT, JSON.stringify({ tag: TAG, url: URL, aborted: 'meter missing globals', selfCheck }, null, 2));
    console.error(`[${TAG}] ABORT: globals missing`, selfCheck);
    await browser.close(); process.exit(1);
  }

  // ── 直接重現突發：模擬「野生世界：全員上台漫遊」──────────────────
  // 不改網頁任何一幀的視覺邏輯，只是在瀏覽器內用跟 index.html 完全一樣的
  // 手法（cast.forEach(c=>{c.onstage=true;...}); 逐一 getVideo()）製造同一種
  // 突發，藉此量「同一個 JS 執行回合內」activeVideos 有沒有被壓住。
  // 這一段本身不是被測的程式碼，是量具（跟 index.html 裡三處既有的
  // 「全員上台」呼叫用的是同一個 API：cast、getVideo，不是另外發明的介面）。
  const before = await page.evaluate(() => {
    const activeCount = () => [...videoPool.values()].filter(e => !e.v.paused).length;
    return { castLen: cast.length, poolSize: videoPool.size, activeBefore: activeCount() };
  });

  const burst = await page.evaluate(() => {
    const activeCount = () => [...videoPool.values()].filter(e => !e.v.paused).length;
    // 補到 29 位（跟泡機那次 incident 的 cast 29/29 同量級），不夠的話用種子
    // 卡司的 vid 借src湊出額外的假 Creature-like 物件（只需要 .vid 給 getVideo 用）。
    const need = 29;
    const srcs = [];
    for (let i = 0; i < need; i++) {
      const c = cast[i % cast.length];
      if (c && c.vid) srcs.push(c.vid);
    }
    // 突發本身：跟 index.html 既有三處「全員上台」完全同款的那一行
    cast.forEach(c => { c.onstage = true; });
    // 緊接著的同一個 JS turn 內，模擬 frame() 對每個 onstage 角色會做的
    // getVideo() 讀取（真實情況是 Creature.draw() 呼叫，這裡直接呼叫
    // 同一個全域函式，效果相同：都會刷新 e.last 並觸發任何掛在 getVideo()
    // 尾端的節流檢查）。
    for (const src of srcs) { try { getVideo(src); } catch (e) {} }
    const activeImmediatelyAfter = activeCount();
    return {
      onstageCount: cast.filter(c => c.onstage).length,
      srcsTouched: srcs.length,
      poolSizeAfter: videoPool.size,
      activeImmediatelyAfter,   // 关键数字：同一个 JS turn 内、完全没等任何 rAF
    };
  });

  // 再等 4 個 rAF（約 4 幀，不管 fps 多低都會排進佇列）之後量一次，看
  // 原本靠 sweepIdleVideos() 週期性收斂的版本最終有沒有追上——用來對照
  // 「立即」vs「最終會不會收斂」兩件事分開講清楚。
  await page.evaluate(() => new Promise(res => {
    let n = 0;
    function tick(){ n++; if (n >= 4) res(); else requestAnimationFrame(tick); }
    requestAnimationFrame(tick);
  }));
  const afterFewFrames = await page.evaluate(() => {
    const activeCount = () => [...videoPool.values()].filter(e => !e.v.paused).length;
    return { activeAfterFewFrames: activeCount(), reloads: parseInt(sessionStorage.getItem('vw_reloads')||'0',10) };
  });

  const result = {
    tag: TAG, url: URL, throttleRate: THROTTLE, pageErrors, selfCheck, before, burst, afterFewFrames,
    verdict: {
      immediate_capped: burst.activeImmediatelyAfter <= selfCheck.hasMax,
      eventually_capped: afterFewFrames.activeAfterFewFrames <= selfCheck.hasMax,
    },
  };
  fs.writeFileSync(OUT, JSON.stringify(result, null, 2));
  console.error(`[${TAG}] onstage=${burst.onstageCount} pool=${burst.poolSizeAfter} ` +
    `active_IMMEDIATELY_after_burst=${burst.activeImmediatelyAfter} (cap=${selfCheck.hasMax}) ` +
    `active_after_4frames=${afterFewFrames.activeAfterFewFrames} reloads=${afterFewFrames.reloads} ` +
    `pageErrors=${pageErrors.length}`);
  await browser.close();
  try { fs.rmSync(UDD, { recursive: true, force: true }); } catch (e) {}
}
main().catch(e => { console.error('fatal', e); process.exit(1); });
