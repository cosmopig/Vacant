#!/usr/bin/env node
/**
 * flow_ui.mjs —— Google Flow 管線的「CLI 沒有、但管線非有不可」那幾件 UI 事。
 *
 * 這支**不取代** `~/Desktop/flow/src/cli.js`，也不改它一個 byte。
 * 它只補三個 CLI 本來就沒有的原語，其餘全部仍然走 CLI：
 *
 *   focus              把專案分頁帶到前景（見下面「為什麼非做不可」）
 *   probe              讀目前的媒體（多帶 duration／readyState）
 *   await-media        在**單一連線**內輪詢新媒體候選，並加上穩定性／時長閘門
 *                      （--kind video|image|any，預設 any：模態是 Flow 自己判的）
 *   attach             把本機檔案掛進提示詞（「新增素材 → 上傳媒體檔案」）
 *   open-download-menu hover 圖塊 → 開「更多選項」→ 展開「下載」子選單（除錯用）
 *   download           上面那串＋按下去＋等下載完成＋落到 --out
 *   repair             按掉「無法載入影片／重試」的失敗圖塊（久開分頁會這樣）
 *   close-menus        收尾：Escape ×2、滑鼠移開
 *
 * **消耗額度的動作（submit）留在 CLI**，因為 CLI 有 `.flow/jobs/<id>.json`
 * 的防重送紀錄——那是這條管線唯一會花錢的地方，必須留在有防重送的那支手上。
 *
 * ── 為什麼 download 沒有留在 CLI（2026-09-19 實測）──────────────────────
 * `cli.js download` 在這台機器上**量到「檔案有下來、事件沒來」**：連跑兩次，
 * 檔案都準時落在 `~/Downloads/`（2,646,017 bytes，兩次同大小），但
 * `page.waitForEvent('download')` 每次都 30 秒逾時、CLI 回 ok:false。
 * 原因是 connectOverCDP 接上的是**既有**瀏覽器 context，Playwright 沒有
 * 替它掛上下載攔截；從外部先設 `Browser.setDownloadBehavior` 也沒用——
 * CLI 一連上來就被蓋回預設（實測：私有目錄空的，檔案仍進 ~/Downloads）。
 * 所以這支自己做，而且做得比 CLI 更硬：
 *   · 下載前把 `Browser.setDownloadBehavior` 指到一個**空的私有暫存目錄**
 *     （behavior: allowAndName ⇒ 檔名就是 CDP 給的 guid）
 *   · 完成訊號取 `Browser.downloadProgress` 的 `state === 'completed'`，
 *     不是「看資料夾多了一個檔」——後者正是 ops/exhibit/DECISION_CONCURRENCY.md
 *     記載過的踩雷方式（共用池子＋時間戳猜歸屬，併發時會撿到別人的產物）
 *   · 事後把 behavior 還原成 default，不留下副作用
 *
 * ── 為什麼非做 focus 不可（2026-09-19 實測）────────────────────────────
 * Flow 分頁如果**不是所在視窗的前景分頁**，Chrome 會節流 rAF，於是
 * Playwright 的 actionability 檢查（「visible, enabled and stable」需要連續
 * 兩個 animation frame 盒子不變）永遠不會通過：
 *   · `cli.js screenshot` → `page.screenshot: Timeout 10000ms exceeded`
 *   · `cli.js discover`   → `locator.ariaSnapshot: Timeout 10000ms exceeded`
 *   · 任何 hover／click    → `Timeout ... waiting for element to be stable`
 * `cli.js status`（純 innerText）不吃這個，所以 `doctor` 一切正常也**不代表**
 * 能操作 UI。focus 用 CDP `Target.activateTarget`＋（必要時）
 * `Browser.setWindowBounds` 把視窗從 minimized 拉回 normal。
 * **不導航、不關閉、不開新分頁**；且 CDP 位址沿用 CLI 的 loopback 檢查。
 *
 * ── 為什麼非做 hover 不可 ──────────────────────────────────────────
 * 媒體圖塊上的工具列（favorite／重複使用提示詞／更多選項）是
 * `visibility: hidden`，只有 hover 才現形。CLI 的 `unique()` 會擋
 * `ELEMENT_NOT_VISIBLE`，所以沒有 hover 就沒有下載路徑。
 *
 * 用法：node flow_ui.mjs <sub> [--flow-home DIR] [--config FILE] ...
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import {parseArgs} from 'node:util';

const FLOW_HOME = process.env.FLOW_HOME || path.join(process.env.HOME, 'Desktop/flow');
const emit = x => process.stdout.write(JSON.stringify(x, null, 2) + '\n');
const die = (code, extra = {}) => { emit({ok: false, error: code, ...extra}); process.exit(1); };

const {values: v, positionals: [sub = 'help']} = parseArgs({
  options: {
    'flow-home': {type: 'string'}, config: {type: 'string'}, id: {type: 'string'},
    key: {type: 'string'}, quality: {type: 'string'}, timeout: {type: 'string'},
    interval: {type: 'string'}, 'stable-polls': {type: 'string'},
    trace: {type: 'string'}, out: {type: 'string'}, kind: {type: 'string'},
    ref: {type: 'string'}, 'max-candidates': {type: 'string'},
    'allow-upscale': {type: 'boolean'}, 'accept-upload-rights': {type: 'boolean'},
    'pause-at-rights': {type: 'boolean'},
  },
  allowPositionals: true, strict: true,
});
const home = v['flow-home'] || FLOW_HOME;
const config = JSON.parse(await fs.readFile(v.config || path.join(home, 'flow.config.json'), 'utf8'));

// CLI 自己的模組：連線守則（loopback-only）、專案比對、媒體 key 演算法、新媒體差集
// 都直接沿用，不重寫——重寫就會有「兩套 key」對不起來的風險。
const core = await import(path.join(home, 'src/core.js'));
const {connect} = await import(path.join(home, 'src/connection.js'));

/**
 * 穩定 key。**不能照抄 CLI 的 key 演算法**——2026-09-19 實測：
 * Flow 的圖片網址是簽章網址 `…/image/<uuid>?Expires=…&Signature=…`，
 * 裡面沒有 `name=` 參數，所以 CLI 的 `keyOf` 會退化成「整串含簽章的 URL」，
 * 而 **Expires 會換**（同一張圖前後看到 1789853310 / 1789853914）⇒
 * 同一份舊素材在下一次輪詢會被算成「新素材」。
 * 這裡改成取 uuid；影片網址（`/asb/…=mm,22,15`，無 query）維持原樣。
 * ⚠ 用了這個 key 就**不能再用 core.newMedia** 去跟 job.before 比對
 *   （那邊存的是 CLI 的原始 key），差集要自己在兩邊都套同一個函式。
 */
const keyOf = url => {
  const u = url || '';
  const m = u.match(/flow-content\.google\/image\/([0-9a-f-]{8,40})/i);
  if (m) return `image:${m[1]}`;
  const n = u.match(/[?&]name=([^&]+)/);
  if (n) return n[1];
  return u.split('?')[0];
};

// ───────────────────────── 原始 CDP（focus 用，不需要 playwright）─────────
async function browserWs() {
  const base = core.endpoint(config.cdp).replace(/\/$/, '');
  const r = await fetch(`${base}/json/version`, {signal: AbortSignal.timeout(5000)});
  if (!r.ok) throw new Error('CDP_DISCOVERY_FAILED');
  return core.endpoint((await r.json()).webSocketDebuggerUrl);
}
async function cdp(fn) {
  const ws = new WebSocket(await browserWs());
  await new Promise((res, rej) => {
    const t = setTimeout(() => {ws.close(); rej(new Error('CDP_OPEN_TIMEOUT'));}, 15000);
    ws.addEventListener('open', () => {clearTimeout(t); res();}, {once: true});
    ws.addEventListener('error', () => {clearTimeout(t); rej(new Error('CDP_SOCKET_ERROR'));}, {once: true});
  });
  let next = 1; const pending = new Map();
  ws.addEventListener('message', e => {
    const m = JSON.parse(e.data), p = pending.get(m.id);
    if (!p) return;
    clearTimeout(p.timer); pending.delete(m.id);
    m.error ? p.rej(new Error(m.error.message)) : p.res(m.result);
  });
  const call = (method, params = {}) => new Promise((res, rej) => {
    const id = next++;
    const timer = setTimeout(() => {pending.delete(id); rej(new Error(`CDP_TIMEOUT_${method}`));}, 15000);
    pending.set(id, {res, rej, timer});
    ws.send(JSON.stringify({id, method, params}));
  });
  try { return await fn(call); } finally { ws.close(); }
}

// ───────────────────────── playwright（其餘子指令用）─────────────────────
async function withPage(fn) {
  const {chromium} = await import(path.join(home, 'node_modules/playwright/index.mjs'));
  const browser = await connect(chromium, core.endpoint(config.cdp), config.activePortFile, config.project);
  try {
    const pages = browser.contexts().flatMap(c => c.pages()).filter(p => core.sameProject(p.url(), config.project));
    if (pages.length !== 1) throw new Error(`PROJECT_MATCH_COUNT_${pages.length}`);
    const page = pages[0];
    page.setDefaultTimeout(20000);
    return await fn(page, browser);
  } finally { await browser.close(); }   // connectOverCDP：close＝斷線，不會關瀏覽器
}

/**
 * hover 圖塊 → 開「更多選項」→ 展開「下載」子選單，回傳那個畫質項目的 locator。
 * 成功時**選單留在開啟狀態**（呼叫者負責按或關）。
 */
async function openDownloadMenu(page, key, quality, allowUpscale) {
  // 1) 找到那個素材（影片或圖片都走同一條路；key 用和 CLI 一樣的演算法算）
  //    影片畫質選單是 270p/720p/1080p/4K，圖片是 1K/2K/4K，但「原始大小」那個
  //    字串兩邊都有，所以 --quality 的預設值對兩種素材都成立。
  const media = page.locator('video, img');
  const n = await media.count();
  let idx = -1;
  for (let i = 0; i < n; i++) {
    const url = await media.nth(i).evaluate(e => e.currentSrc || e.src);
    if (keyOf(url) === key) { idx = i; break; }
  }
  if (idx < 0) return {ok: false, error: 'MEDIA_KEY_NOT_ON_PAGE', elements: n};
  const video = media.nth(idx);
  await video.scrollIntoViewIfNeeded();
  await video.hover();                       // ← 工具列是 visibility:hidden，非 hover 不可
  await page.waitForTimeout(500);
  // 2)「更多選項」：用**可見性**當消歧條件，不用 DOM 祖先鏈。
  //    工具列平時 visibility:hidden，只有被 hover 的那一塊會現形，所以
  //    「目前可見的 flowhotbarbutton 更多選項」天然只有一顆。
  //    （祖先鏈試過：hotbar 不一定是 <video> 的祖先，xpath 會落空。）
  const more = page.locator('button[flowhotbarbutton][aria-label="更多選項"]:visible');
  if (await more.count() !== 1) return {ok: false, error: 'UI_DRIFT_NO_HOTBAR',
    visibleMore: await more.count(),
    hotbarAll: await page.locator('button[flowhotbarbutton]').evaluateAll(
      es => es.map(e => ({aria: e.getAttribute('aria-label'), vis: getComputedStyle(e).visibility})))};
  await more.click();
  await page.waitForTimeout(800);
  // 3)「下載」用 Material icon ligature 比對（"download" 不隨語系變），不是靠中文字
  const dl = page.locator('.cdk-overlay-container .mat-mdc-menu-item:has-text("download")');
  if (await dl.count() !== 1) return {ok: false, error: 'UI_DRIFT_NO_DOWNLOAD_ITEM',
    items: await page.locator('.cdk-overlay-container .mat-mdc-menu-item').allInnerTexts()};
  await dl.hover();
  await page.waitForTimeout(900);
  // 4) 畫質子選單：預設只收「原始大小」。1080p／4K 標示「已提升畫質」＝會再跑一次
  //    upscale，那是額外花額度的動作，必須 --allow-upscale 才准。
  const selector = `.cdk-overlay-container .mat-mdc-menu-item:has-text(${JSON.stringify(quality)}):visible`;
  const target = page.locator(selector);
  const items = await page.locator('.cdk-overlay-container .mat-mdc-menu-item').allInnerTexts();
  if (await target.count() !== 1) return {ok: false, error: 'UI_DRIFT_QUALITY_NOT_UNIQUE',
    quality, matched: await target.count(), items};
  const text = (await target.innerText()).replace(/\s+/g, ' ').trim();
  if (/已提升畫質|upscal/i.test(text) && !allowUpscale)
    return {ok: false, error: 'REFUSED_UPSCALE', text,
      note: '這個畫質標示為「已提升畫質」，按下去是另一次付費生成。要就明講 --allow-upscale。'};
  return {ok: true, selector, item: text, items, target};
}

/** core.media() 的超集：多帶 duration／readyState，供完成判準使用。 */
async function mediaPlus(page) {
  const rows = [];
  for (const frame of page.frames()) {
    rows.push(...await frame.evaluate(() => Array.from(document.querySelectorAll('img,video')).map(e => {
      const url = e.currentSrc || e.src;
      return {
        url, type: e.tagName === 'VIDEO' ? 'video' : 'image',
        ready: e.tagName === 'VIDEO' ? e.readyState >= 2 : e.complete && e.naturalWidth > 0,   // ← type 用 image/video，不是 img
        width: e.videoWidth || e.naturalWidth || 0,
        height: e.videoHeight || e.naturalHeight || 0,
        readyState: e.readyState ?? null,
        duration: e.tagName === 'VIDEO' ? (Number.isFinite(e.duration) ? e.duration : null) : null,
        onscreen: !!(e.offsetParent || e.getClientRects().length),
      };
    }).filter(e => e.url && (e.type === 'video' || e.width > 150))));
  }
  return [...new Map(rows.map(x => [keyOf(x.url), {key: keyOf(x.url), ...x}])).values()];
}

// ───────────────────────────── 子指令 ────────────────────────────────────
if (sub === 'help') {
  emit({name: 'flow_ui', subs: ["focus", "probe", "await-media", "open-download-menu", "download", "attach", "repair", "close-menus"]});
  process.exit(0);
}

if (sub === 'focus') {
  const out = await cdp(async call => {
    const {targetInfos} = await call('Target.getTargets');
    const m = targetInfos.filter(t => t.type === 'page' && core.sameProject(t.url, config.project));
    if (m.length !== 1) throw new Error(`PROJECT_MATCH_COUNT_${m.length}`);
    const targetId = m[0].targetId;
    await call('Target.activateTarget', {targetId});
    let win = null, fixed = false;
    try {
      win = await call('Browser.getWindowForTarget', {targetId});
      if (win?.bounds?.windowState && win.bounds.windowState !== 'normal') {
        await call('Browser.setWindowBounds', {windowId: win.windowId, bounds: {windowState: 'normal'}});
        fixed = true;
      }
    } catch { /* 某些 Chrome 通道沒有 Browser.getWindowForTarget；活化本身已經做了 */ }
    return {ok: true, targetId, url: m[0].url, windowState: win?.bounds?.windowState ?? null, unminimized: fixed};
  }).catch(e => die('FOCUS_FAILED', {detail: e.message}));
  emit(out);
  process.exit(0);
}

if (sub === 'probe') {
  emit(await withPage(async page => ({
    ok: true, at: new Date().toISOString(), url: page.url(), title: await page.title(),
    assets: await mediaPlus(page),
  })).catch(e => die('PROBE_FAILED', {detail: e.message})));
  process.exit(0);
}

if (sub === 'await-media') {
  // 這裡只做「可以去按下載了」的觸發條件，**不宣稱完成**（完成由 gen_asset.sh 的
  // ffprobe 那一關認；判準與它會錯在哪，寫在 gen_asset.sh 檔頭那一大段）。
  if (!v.id) die('ID_REQUIRED');
  const jobFile = core.jobPath(path.join(home, '.flow', 'jobs'), v.id);
  const job = JSON.parse(await fs.readFile(jobFile, 'utf8'));
  const budget = Number(v.timeout || 900);
  const interval = Number(v.interval || 6) * 1000;
  const need = Number(v['stable-polls'] || 2);
  const max = Number(v['max-candidates'] || 1);
  const trace = v.trace ? await fs.open(v.trace, 'a') : null;
  const started = Date.now(), deadline = started + budget * 1000;
  const beforeKeys = new Set((job.before || []).map(x => keyOf(x.url || x.key)));
  let streak = 0, lastKey = null, polls = 0, sawAny = 0;
  const out = await withPage(async page => {
    for (;;) {
      polls++;
      const all = await mediaPlus(page);
      // core.newMedia 是 CLI 自己的差集邏輯，直接用，避免兩套語意
      // kind: video|image|any（預設 any）。**Flow 自己決定要生圖還是生片**
      // ——同一個提示詞框，模態由它判讀，不是我們選的——所以預設不預設。
      const kind = v.kind || 'any';
      // 差集自己做：job.before 是 CLI 用原始簽章 URL 當 key 存的，這裡把兩邊
      // 都重新套 keyOf 才比得對（理由見 keyOf 的註解）。
      const fresh = all.filter(x => !beforeKeys.has(x.key))
        .filter(x => kind === 'any' || x.type === kind).filter(x => x.ready);
      // 影片要「時長有限且 > 0」；圖片要夠大（512 是為了擋掉 UI 自己的小圖與載入佔位，
      // 生成結果實測 1376×768 起跳）。
      const good = fresh.filter(x => x.type === 'video'
        ? (x.duration !== null && x.duration > 0)
        : x.width >= 512);
      sawAny = Math.max(sawAny, fresh.length);
      const row = {at: new Date().toISOString(), t: Math.round((Date.now() - started) / 1000),
                   poll: polls, fresh: fresh.length, good: good.length,
                   keys: good.map(x => x.key.slice(0, 40)),
                   detail: fresh.map(x => ({type: x.type, rs: x.readyState, dur: x.duration, w: x.width, h: x.height}))};
      if (trace) await trace.write(JSON.stringify(row) + '\n');
      // max-candidates：一次生幾份是 Flow 的「代理設定」決定的（x1–x4；這台
      // 影片 x1、**圖像 x2**）。超過就停下來交給人，不猜哪一個是我們的。
      if (good.length > max) return {ok: false, error: 'AMBIGUOUS_CANDIDATES', polls, max,
        seconds: Math.round((Date.now() - started) / 1000), candidates: good,
        note: '新素材多於 --max-candidates：可能是設定成一次生多份，也可能是別人在同一專案生成。不猜。'};
      if (good.length >= 1) {
        const sig = good.map(x => x.key).sort().join('|');
        if (sig === lastKey) streak++; else {streak = 1; lastKey = sig;}
        if (streak >= need) return {ok: true, status: 'stable_candidate', polls, streak,
          seconds: Math.round((Date.now() - started) / 1000),
          candidate: good[0], candidates: good,
          verifiedComplete: false, note: '穩定的新素材候選＝可以去按下載，不等於生成完成；完成由 ffprobe 認。'};
      } else { streak = 0; lastKey = null; }
      if (Date.now() >= deadline) return {ok: false, error: 'TIMEOUT_UNVERIFIED', polls,
        seconds: Math.round((Date.now() - started) / 1000), sawFreshMax: sawAny,
        note: '逾時＝沒量到完成，不等於生成失敗（鐵律 3）。job 紀錄留著，可 --resume 續等，不重送。'};
      await page.waitForTimeout(interval);
    }
  }).catch(e => ({ok: false, error: 'AWAIT_FAILED', detail: e.message}));
  if (trace) await trace.close();
  emit(out);
  process.exit(out.ok ? 0 : 1);
}

if (sub === 'open-download-menu') {
  if (!v.key) die('KEY_REQUIRED');
  const out = await withPage(async page => {
    const r = await openDownloadMenu(page, v.key, v.quality || '原始大小', v['allow-upscale']);
    delete r.target;
    return r.ok ? {...r, status: 'download_menu_open', note: '選單留在開啟狀態；這個子指令只給人除錯用。'} : r;
  }).catch(e => ({ok: false, error: 'OPEN_MENU_FAILED', detail: e.message.split('\n')[0]}));
  emit(out);
  process.exit(out.ok ? 0 : 1);
}

if (sub === 'download') {
  if (!v.key) die('KEY_REQUIRED');
  if (!v.out) die('OUT_REQUIRED');
  const out = path.resolve(v.out);
  try { await fs.access(out); die('OUTPUT_EXISTS', {file: out}); } catch (e) { if (e.code !== 'ENOENT') throw e; }
  // 私有空目錄：下載歸屬不靠「資料夾多了一個檔」去猜
  const sink = await fs.mkdtemp(path.join(process.env.TMPDIR || '/tmp', 'flowdl-'));
  const res = await withPage(async (page, browser) => {
    const session = await browser.newBrowserCDPSession();
    const done = new Promise((resolve, reject) => {
      const t = setTimeout(() => reject(new Error('DOWNLOAD_PROGRESS_TIMEOUT_120s')), 120000);
      session.on('Browser.downloadProgress', e => {
        if (e.state === 'completed') { clearTimeout(t); resolve(e); }
        if (e.state === 'canceled') { clearTimeout(t); reject(new Error('DOWNLOAD_CANCELED')); }
      });
    });
    let begin = null;
    session.on('Browser.downloadWillBegin', e => { begin = e; });
    // allowAndName ⇒ 檔案就叫 guid，不會撞名、不需要猜哪個是我的
    await session.send('Browser.setDownloadBehavior',
      {behavior: 'allowAndName', downloadPath: sink, eventsEnabled: true});
    try {
      const menu = await openDownloadMenu(page, v.key, v.quality || '原始大小', v['allow-upscale']);
      if (!menu.ok) { delete menu.target; return menu; }
      const clickedAt = Date.now();
      await menu.target.click();
      const ev = await done;
      const src = path.join(sink, ev.guid);
      await fs.copyFile(src, out, fs.constants.COPYFILE_EXCL);
      const stat = await fs.stat(out);
      if (!stat.size) return {ok: false, error: 'EMPTY_DOWNLOAD', file: out};
      return {ok: true, status: 'downloaded', file: out, bytes: stat.size,
              guid: ev.guid, suggestedFilename: begin?.suggestedFilename ?? null,
              totalBytes: begin?.totalBytes ?? null,
              seconds: Math.round((Date.now() - clickedAt) / 100) / 10,
              item: menu.item, quality: v.quality || '原始大小'};
    } finally {
      // 還原，不留副作用（不還原＝這台 Chrome 之後所有下載都進我的暫存目錄）
      await session.send('Browser.setDownloadBehavior', {behavior: 'default'}).catch(() => {});
      await page.keyboard.press('Escape').catch(() => {});
      await page.mouse.move(4, 4).catch(() => {});
    }
  }).catch(e => ({ok: false, error: 'DOWNLOAD_FAILED', detail: e.message.split('\n')[0]}));
  await fs.rm(sink, {recursive: true, force: true});
  emit(res);
  process.exit(res.ok ? 0 : 1);
}

if (sub === 'attach') {
  // 把本機檔案掛進提示詞（圖生圖 / i2v 的參考圖）。
  //
  // 「新增素材」開的不是普通選單，是一個**素材挑選面板**（2026-09-19 實測）：
  //   button[class*=sidebar-upload]   「upload 上傳媒體檔案」
  //   button[role=option].asset-item  專案裡既有的素材（點一下＝選取）
  //   button.detail-add-to-prompt-btn 「新增至提示詞」← 沒按這顆等於沒掛上
  // 上傳按鈕開的是**作業系統的檔案選擇器**，不是 DOM 的 <input type=file>
  // （點開面板後頁面上仍然 0 個 file input），所以要攔 filechooser 事件。
  // CLI README 明說檔案上傳「尚未封裝」，這一段就是那個缺口。
  //
  // 同名素材已經在專案裡就**直接選它、不重傳**——重傳會在素材庫留一堆副本。
  if (!v.ref) die('REF_REQUIRED');
  const file = path.resolve(v.ref);
  try { await fs.access(file); } catch { die('REF_NOT_FOUND', {file}); }
  const base = path.basename(file);
  const stem = base.replace(/\.[^.]+$/, '');
  const out = await withPage(async page => {
    const OV = '.cdk-overlay-container';
    const add = page.locator('button[aria-label="在提示詞輸入框新增素材"]');
    if (await add.count() !== 1) return {ok: false, error: 'UI_DRIFT_NO_ADD_BUTTON', count: await add.count()};
    await add.click();
    await page.waitForTimeout(1000);
    const items = page.locator(`${OV} button[role="option"].asset-item`);
    const label = t => t.split('\n')[0].trim();
    const find = async () => (await items.allInnerTexts()).findIndex(t => label(t) === stem || label(t) === base);
    let idx = await find(), uploaded = false;
    if (idx < 0) {
      const up = page.locator(`${OV} button[class*="sidebar-upload"]`);
      if (await up.count() !== 1) {
        await page.keyboard.press('Escape');
        return {ok: false, error: 'UI_DRIFT_NO_UPLOAD_BUTTON',
                buttons: await page.locator(`${OV} button`).allInnerTexts()};
      }
      const chooser = page.waitForEvent('filechooser', {timeout: 20000});
      await up.click();
      await (await chooser).setFiles(file);
      // 上傳會先跳一個**使用權聲明**對話框（「請確認您具備必要權限…」取消／我同意）。
      // 那是替人做權利聲明，不是技術步驟 ⇒ **預設一律取消**，只有呼叫端明講
      // --accept-upload-rights 才按同意。（人按過一次之後可能就不再問。）
      const agree = () => page.locator(`${OV} button`).filter({hasText: /^我同意$|^I agree$/i});
      const cancel = () => page.locator(`${OV} button`).filter({hasText: /^取消$|^Cancel$/i});
      // `--pause-at-rights`：**既不替人按，也不替人取消**——把對話框留在畫面上等人自己按。
      //
      // 加這個模式的理由是量出來的，不是方便性：2026-09-20 比對 `s10-green-1`
      // （純文字提示、**沒掛參考圖**）與參考板 `world3/plates/s03.jpg`，箱型（高圓角→矮寬銳邊）、
      // 質感（粗顆粒→光滑）、機位（低平偏右→俯角置中）、符號（信封＋橫線→只有信封）**四項全變**
      // ⇒ 不掛參考圖就不是同一個系列。而掛參考圖一定觸發這個聲明
      // ⇒ **聲明是「同一個系列」的唯一途徑，不是可跳過的步驟；取消掉＝放棄系列一致性。**
      //
      // ⚠ 這支**永遠不替人做那個聲明**。三種模式的差別只在「不同意的時候怎麼辦」：
      //   預設              取消 ＋ 立刻回報（原本的行為，不變）
      //   --pause-at-rights 留著 ＋ 等人按（本模式）
      //   --accept-upload-rights  人已經在別處明示授權，才由腳本代按
      const PAUSE = !!v['pause-at-rights'] && !v['accept-upload-rights'];
      const MAXI = PAUSE ? 600 : 40;                       // 600 × 1.5s = 15 分鐘
      let announced = false;
      for (let i = 0; i < MAXI && idx < 0; i++) {
        if (await agree().count() >= 1) {
          if (v['accept-upload-rights']) {
            await agree().first().click();
          } else if (PAUSE) {
            if (!announced) {
              announced = true;
              // 走 stderr：呼叫端看得到，且不污染 stdout 的 JSON 契約
              process.stderr.write('WAITING_FOR_HUMAN_RIGHTS_CONSENT '
                + JSON.stringify({file, deadline_s: MAXI * 1.5}) + '\n');
            }
            // 什麼都不做——對話框留在畫面上
          } else {
            await cancel().first().click().catch(() => {});
            await page.keyboard.press('Escape');
            return {ok: false, error: 'UPLOAD_NEEDS_RIGHTS_CONSENT', file,
              note: 'Flow 上傳前要人聲明「具備必要權限可使用這個檔案」。這支不替人做那個聲明。'
                  + ' 人同意了就加 --accept-upload-rights（gen_asset.sh 也有同名旗標），或請人在瀏覽器裡按一次，'
                  + '或用 --pause-at-rights 把對話框留著等人按。'};
          }
        }
        await page.waitForTimeout(1500);
        idx = await find();
      }
      // ⚠ 逾時**不取消對話框**：人可能正要按。留著，讓人按完再 --resume。
      if (idx < 0 && PAUSE && announced) {
        return {ok: false, error: 'RIGHTS_CONSENT_TIMEOUT', file, waited_s: MAXI * 1.5,
                note: `等了 ${MAXI * 1.5} 秒沒人按「我同意」。對話框**沒有被我取消**，`
                    + '人按完之後用 --resume 續跑即可（不會重送、不會再花額度）。'};
      }
      if (idx < 0) { await page.keyboard.press('Escape');
        return {ok: false, error: 'UPLOAD_NOT_VISIBLE_AFTER_60s', stem,
                items: await items.allInnerTexts()}; }
      uploaded = true;
    }
    await items.nth(idx).click();
    await page.waitForTimeout(600);
    const addBtn = page.locator(`${OV} button.detail-add-to-prompt-btn`);
    if (await addBtn.count() !== 1) { await page.keyboard.press('Escape');
      return {ok: false, error: 'UI_DRIFT_NO_ADD_TO_PROMPT_BUTTON'}; }
    await addBtn.click();
    await page.waitForTimeout(2000);
    await page.mouse.move(4, 4);
    return {ok: true, status: 'attached', file, stem, uploaded,
            assetLabel: label((await items.allInnerTexts())[idx] || ''),
            note: '已選取素材並按下「新增至提示詞」。真的掛上沒有，看 status 的頁面文字。',
            bodyTail: (await page.locator('body').innerText()).slice(-300)};
  }).catch(e => ({ok: false, error: 'ATTACH_FAILED', detail: e.message.split('\n')[0]}));
  emit(out);
  process.exit(out.ok ? 0 : 1);
}

if (sub === 'repair') {
  // 久開的分頁會出現「無法載入影片 / 重試」（簽名 URL 過期）。按「重試」不花額度。
  emit(await withPage(async page => {
    const retry = page.locator('button[aria-label="重試"]:visible');
    const n = await retry.count();
    for (let i = 0; i < n; i++) await retry.nth(i).click().catch(() => {});
    if (n) await page.waitForTimeout(4000);
    await page.mouse.move(4, 4);
    return {ok: true, status: 'repaired', clicked: n,
            note: n ? '按過重試；重新 probe 確認影片回來了沒。' : '沒有失敗圖塊。'};
  }).catch(e => ({ok: false, error: 'REPAIR_FAILED', detail: e.message.split('\n')[0]})));
  process.exit(0);
}

if (sub === 'close-menus') {
  emit(await withPage(async page => {
    await page.keyboard.press('Escape'); await page.waitForTimeout(250);
    await page.keyboard.press('Escape'); await page.waitForTimeout(250);
    await page.mouse.move(4, 4);
    return {ok: true, status: 'menus_closed'};
  }).catch(e => ({ok: false, error: 'CLOSE_FAILED', detail: e.message.split('\n')[0]})));
  process.exit(0);
}

die('UNKNOWN_SUBCOMMAND', {sub});
