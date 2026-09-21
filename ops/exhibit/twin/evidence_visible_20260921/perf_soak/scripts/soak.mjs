#!/usr/bin/env node
// 獨立泡機腳本（perf_soak key，不借用 asset_loading 那組的程式碼，只借用他們已經
// 驗證過的修法本身）。量：RSS（OS 行程層級，用專屬 user-data-dir 隔離同機其他
// 代理的 Chrome）、fps（rAF 計數）、JS heap、videoPool/cast/visitorCast 機制計數、
// 定期 page.screenshot() 計時（直接重現「凍住幾秒」症狀，不是猜的）。
import puppeteer from 'puppeteer-core';
import fs from 'node:fs';
import { execSync } from 'node:child_process';

function arg(name, def) { const i = process.argv.indexOf(`--${name}`); return i === -1 ? def : process.argv[i + 1]; }
const URL = arg('url', 'http://127.0.0.1:8618/index.html');
const DURATION = parseInt(arg('duration', '3600'), 10);      // 秒
const SAMPLE_EVERY = parseInt(arg('sample', '30'), 10);      // 秒
const SUBMIT_EVERY = parseFloat(arg('submit', '8'));         // 秒；0 = 不灌真人分身
const SHOT_EVERY = parseInt(arg('shotEvery', '900'), 10);    // 秒；0 = 不拍
const OUT = arg('out', './soak_out.json');
const TAG = arg('tag', 'run');
const SHOT_DIR = arg('shotdir', './shots');
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const UDD = `/tmp/perfsoak-udd-${TAG}-${Date.now()}`;   // 專屬 marker，RSS 用它篩選這一個瀏覽器

fs.mkdirSync(SHOT_DIR, { recursive: true });

const SHAPES = ['厚實','方正','粗獷','圓潤','小巧','修長'];
const COLORS = ['奶油','灰藍','暖土','苔綠','赭紅','沙金'];
const TEXTURES = ['光滑','斑駁','指紋'];
const pick = a => a[(Math.random() * a.length) | 0];
let n = 0;
function synth() {
  n++;
  return { id: `soak-${TAG}-${n}-${Date.now()}`, ts: Date.now(),
    card: { shape: pick(SHAPES), color: pick(COLORS), texture: pick(TEXTURES),
      need: `泡機壓測 #${n}`, firstline: `第 ${n} 位` } };
}

// RSS：把 UDD 這個 marker 底下起的所有 Chrome 行程（main+renderer+gpu 等）RSS 加總。
// 這樣同機其他代理的 headless Chrome 不會混進我的數字（負控制：見 selfcheck）。
function rssMB() {
  try {
    const out = execSync(`ps -eo rss,command | grep -F ${JSON.stringify(UDD)} | grep -v grep`, { encoding: 'utf8' });
    let sum = 0;
    for (const line of out.split('\n')) {
      const m = line.trim().match(/^(\d+)/);
      if (m) sum += parseInt(m[1], 10);
    }
    return +(sum / 1024).toFixed(2);
  } catch (e) { return null; }   // grep 找不到任何行時 execSync 會丟非零 exit；誠實回 null 不是 0
}

async function main() {
  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: 'new',
    userDataDir: UDD,
    args: ['--window-size=1280,720', '--autoplay-policy=no-user-gesture-required',
      '--mute-audio', '--disable-gpu', '--disable-gpu-compositing', '--use-gl=swiftshader',
      '--no-first-run', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 720 });

  page.on('pageerror', e => console.error(`[${TAG}] pageerror: ${e}`));
  page.on('console', msg => { if (msg.type() === 'error') console.error(`[${TAG}] console.error: ${msg.text()}`); });

  await page.goto(URL, { waitUntil: 'load', timeout: 60000 });
  await page.evaluate(() => {
    window.__perf = { frames: 0 };
    function tick() { window.__perf.frames++; requestAnimationFrame(tick); }
    requestAnimationFrame(tick);
  });
  await new Promise(r => setTimeout(r, 2000));

  // ── 負控制：量具自己會不會動（instruments-lie-before-you-conclude-zero）──
  // ⚠ 頁面是活的，背景本來就會持續載入新片，poolSize 前後不能拿絕對值比較
  // （第一版這樣寫誤判過：兩次 evaluate 之間真的有新片進池，size +2 蓋過了
  // 我自己塞的 +1）。改成塞完在**同一個 evaluate 呼叫**裡直接用 `has()` 驗證
  // 那個 marker 存在，不看 size 的絕對值——不受背景真實流量干擾。
  const self0 = await page.evaluate(() => ({
    poolSize: (typeof videoPool !== 'undefined') ? videoPool.size : null,
    castLen: (typeof cast !== 'undefined') ? cast.length : null,
    hasVisitorCast: (typeof visitorCast !== 'undefined'),
  }));
  const forceOk = await page.evaluate(() => {
    if (typeof videoPool === 'undefined') return false;
    const v = document.createElement('video');
    videoPool.set('__selfcheck_marker__', { v, last: performance.now() });
    const seen = videoPool.has('__selfcheck_marker__');
    videoPool.delete('__selfcheck_marker__');   // 立刻清掉，不污染正式量測
    return seen;
  });
  const selfAfterForce = null;
  // 必中輸入 2：全部暫停，確認 activeVideos 量得到會歸零（量具會動，不是恆真恆假）
  const negControl = await page.evaluate(() => {
    if (typeof videoPool === 'undefined') return null;
    const before = [...videoPool.values()].filter(e => !e.v.paused).length;
    for (const e of videoPool.values()) e.v.pause();
    const after = [...videoPool.values()].filter(e => !e.v.paused).length;
    for (const e of videoPool.values()) e.v.play().catch(()=>{});  // 還原，不要留下副作用
    return { before, after };
  });
  const selfCheck = { self0, selfAfterForce, forceOk, negControl,
    negControlOk: negControl && negControl.after === 0 && negControl.before > negControl.after };
  console.error(`[${TAG}] selfCheck: ${JSON.stringify(selfCheck)}`);
  if (!selfCheck.forceOk || !selfCheck.negControlOk) {
    console.error(`[${TAG}] ⚠ 量具負控制沒過，這一跑的數字不可信——中止`);
    fs.writeFileSync(OUT, JSON.stringify({ tag: TAG, url: URL, selfCheck, aborted: 'meter self-check failed' }, null, 2));
    await browser.close(); process.exit(1);
  }

  const samples = [];
  const screenshots = [];
  const t0 = Date.now();
  let lastSubmitAt = -9999, lastFrameCount = 0, lastSampleT = Date.now(), lastShotAt = -9999;

  // t=0 截圖
  {
    const t = Date.now();
    const shotPath = `${SHOT_DIR}/${TAG}_t0.png`;
    await page.screenshot({ path: shotPath });
    screenshots.push({ tElapsedSec: 0, path: shotPath, ms: Date.now() - t });
  }

  while ((Date.now() - t0) / 1000 < DURATION) {
    const elapsed = (Date.now() - t0) / 1000;
    if (SUBMIT_EVERY > 0 && elapsed - lastSubmitAt >= SUBMIT_EVERY) {
      lastSubmitAt = elapsed;
      try { await page.evaluate(s => { spawnQueue.push(s); }, synth()); } catch (e) {}
    }
    await new Promise(r => setTimeout(r, Math.min(SAMPLE_EVERY, 5) * 1000));
    // 每 SAMPLE_EVERY 秒才真的取樣一次；submit 用更短的內迴圈保節奏，這裡用累計判斷
    if ((Date.now() - t0) / 1000 - (samples.length ? samples[samples.length-1].tElapsedSec : -9999) < SAMPLE_EVERY) continue;

    let m;
    try {
      m = await page.evaluate(() => {
        const active = (typeof videoPool !== 'undefined') ? [...videoPool.values()].filter(e => !e.v.paused).length : null;
        let visitorCastLen = null;
        try { visitorCastLen = visitorCast.length; } catch (e) {}
        const heap = performance.memory ? performance.memory.usedJSHeapSize / 1048576 : null;
        const heapTotal = performance.memory ? performance.memory.totalJSHeapSize / 1048576 : null;
        return {
          castTotal: (typeof cast !== 'undefined') ? cast.length : null,
          castOnstage: (typeof cast !== 'undefined') ? cast.filter(c => c.onstage).length : null,
          visitorCastLen, poolSize: (typeof videoPool !== 'undefined') ? videoPool.size : null,
          activeVideos: active,
          spawnQueueLen: (typeof spawnQueue !== 'undefined') ? spawnQueue.length : null,
          sceneId: (typeof sceneId !== 'undefined') ? sceneId : null,
          mode: (typeof director !== 'undefined') ? director.mode : null,
          reloads: parseInt(sessionStorage.getItem('vw_reloads') || '0', 10),
          frames: window.__perf.frames,
          heapMB: heap, heapTotalMB: heapTotal,
          title: document.title,
        };
      });
    } catch (e) { m = { evalError: String(e) }; }

    const nowT = Date.now();
    const dtSec = (nowT - lastSampleT) / 1000;
    const fps = (dtSec > 0 && m.frames != null) ? +(((m.frames - lastFrameCount) / dtSec)).toFixed(2) : null;
    lastFrameCount = m.frames ?? lastFrameCount;
    lastSampleT = nowT;

    const rec = { tElapsedSec: +elapsed.toFixed(1), wallClock: new Date().toISOString(), fps, rssMB: rssMB(), submittedTotal: n, ...m };
    samples.push(rec);
    console.error(`[${TAG}] t=${rec.tElapsedSec}s fps=${fps} rss=${rec.rssMB}MB heap=${rec.heapMB?.toFixed(1)}MB pool=${m.poolSize} active=${m.activeVideos} cast=${m.castTotal}/${m.castOnstage} visitorCast=${m.visitorCastLen} q=${m.spawnQueueLen} scene=${m.sceneId} submitted=${n}`);
    fs.writeFileSync(OUT, JSON.stringify({ tag: TAG, url: URL, selfCheck, samples, screenshots, submittedTotal: n, done: false }, null, 2));

    if (SHOT_EVERY > 0 && elapsed - lastShotAt >= SHOT_EVERY) {
      lastShotAt = elapsed;
      const shotT0 = Date.now();
      try {
        const shotPath = `${SHOT_DIR}/${TAG}_t${Math.round(elapsed)}.png`;
        await page.screenshot({ path: shotPath, timeout: 60000 });
        const ms = Date.now() - shotT0;
        screenshots.push({ tElapsedSec: +elapsed.toFixed(1), path: shotPath, ms });
        console.error(`[${TAG}] screenshot @t=${elapsed.toFixed(0)}s took ${ms}ms -> ${shotPath}`);
      } catch (e) {
        screenshots.push({ tElapsedSec: +elapsed.toFixed(1), path: null, ms: Date.now() - shotT0, error: String(e) });
        console.error(`[${TAG}] screenshot @t=${elapsed.toFixed(0)}s FAILED after ${Date.now()-shotT0}ms: ${e}`);
      }
      fs.writeFileSync(OUT, JSON.stringify({ tag: TAG, url: URL, selfCheck, samples, screenshots, submittedTotal: n, done: false }, null, 2));
    }
  }

  // 收尾截圖
  {
    const t = Date.now();
    try {
      const shotPath = `${SHOT_DIR}/${TAG}_tEnd.png`;
      await page.screenshot({ path: shotPath, timeout: 60000 });
      screenshots.push({ tElapsedSec: +((Date.now()-t0)/1000).toFixed(1), path: shotPath, ms: Date.now() - t });
    } catch (e) { screenshots.push({ tElapsedSec: null, path: null, ms: Date.now()-t, error: String(e) }); }
  }

  fs.writeFileSync(OUT, JSON.stringify({ tag: TAG, url: URL, selfCheck, samples, screenshots, submittedTotal: n, done: true }, null, 2));
  await browser.close();
  try { fs.rmSync(UDD, { recursive: true, force: true }); } catch (e) {}
}
main().catch(e => { console.error('fatal', e); process.exit(1); });
