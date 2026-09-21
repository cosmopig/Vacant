#!/usr/bin/env node
// 泡機那次只自然撞到 s11 全員上台一次。這裡刻意連續觸發 N 次（不是等敘事
// 節奏排到 s11，而是直接呼叫同一套「全員上台」手法），比被動等一次更嚴格：
// 如果 enforceDecodeCap() 真的把突發吃掉了，N 次重複應該 0 次撞看門狗、
// activeVideos 每次都被壓回 MAX_ACTIVE_DECODES 以內；如果只是運氣好躲過一次，
// 重複 N 次應該會露餡。
import puppeteer from 'puppeteer-core';
import fs from 'node:fs';

function arg(name, def) { const i = process.argv.indexOf(`--${name}`); return i === -1 ? def : process.argv[i + 1]; }
const URL = arg('url', 'http://127.0.0.1:8702/index.html');
const TAG = arg('tag', 'new');
const REPEATS = parseInt(arg('repeats', '15'), 10);
const OUT = arg('out', './burst_repeat_out.json');
const SHOT_DIR = arg('shotdir', './shots_repeat');
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const UDD = `/tmp/burstrepeat-udd-${TAG}-${Date.now()}`;

fs.mkdirSync(SHOT_DIR, { recursive: true });

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

  await page.goto(URL, { waitUntil: 'load', timeout: 60000 });
  await new Promise(r => setTimeout(r, 3000));

  const selfCheck = await page.evaluate(() => ({
    hasEnforce: typeof enforceDecodeCap === 'function',
    hasMax: typeof MAX_ACTIVE_DECODES !== 'undefined' ? MAX_ACTIVE_DECODES : null,
  }));

  const rounds = [];
  for (let i = 0; i < REPEATS; i++) {
    // 每一輪：CPU 節流強度輪流變化（1x/4x/8x），模擬「同機負載忽大忽小」而
    // 不是固定用一個順風的節流值。
    const rate = [1, 4, 8][i % 3];
    const cdp = await page.createCDPSession();
    await cdp.send('Emulation.setCPUThrottlingRate', { rate });
    const r = await page.evaluate(() => {
      const activeCount = () => [...videoPool.values()].filter(e => !e.v.paused).length;
      const need = 29;
      const srcs = [];
      for (let i = 0; i < need; i++) { const c = cast[i % cast.length]; if (c && c.vid) srcs.push(c.vid); }
      cast.forEach(c => { c.onstage = true; });
      for (const src of srcs) { try { getVideo(src); } catch (e) {} }
      const immediatelyAfter = activeCount();
      // 隨手把一半人設回不上台，模擬場景收尾（不影響量測意義，純粹讓下一輪
      // 的「全員上台」還是一次有效的突發，不是對已經全上台的 cast 重複呼叫）
      cast.forEach((c, idx) => { if (idx % 2 === 0) c.onstage = false; });
      return { onstageCount: cast.filter(c=>c.onstage).length, poolSize: videoPool.size, immediatelyAfter };
    });
    await cdp.detach();
    const reloads = await page.evaluate(() => parseInt(sessionStorage.getItem('vw_reloads')||'0',10));
    rounds.push({ round: i, throttleRate: rate, ...r, reloadsSoFar: reloads });
    if (i === 0 || i === REPEATS - 1) {
      try { await page.screenshot({ path: `${SHOT_DIR}/${TAG}_round${i}.png`, timeout: 20000 }); } catch (e) {}
    }
    await new Promise(res => setTimeout(res, 500));
  }

  const finalReloads = await page.evaluate(() => parseInt(sessionStorage.getItem('vw_reloads')||'0',10));
  const maxObserved = Math.max(...rounds.map(r => r.immediatelyAfter));
  const anyOverCap = rounds.some(r => selfCheck.hasMax != null && r.immediatelyAfter > selfCheck.hasMax);
  const result = { tag: TAG, url: URL, repeats: REPEATS, selfCheck, rounds, finalReloads,
    maxObserved, anyOverCap, pageErrorsCount: pageErrors.length };
  fs.writeFileSync(OUT, JSON.stringify(result, null, 2));
  console.error(`[${TAG}] ${REPEATS} rounds done. maxObserved=${maxObserved} cap=${selfCheck.hasMax} ` +
    `anyOverCap=${anyOverCap} finalReloads=${finalReloads} pageErrors=${pageErrors.length}`);
  await browser.close();
  try { fs.rmSync(UDD, { recursive: true, force: true }); } catch (e) {}
}
main().catch(e => { console.error('fatal', e); process.exit(1); });
