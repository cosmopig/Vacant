/* 抵達層（arrivals）逐字抄本 —— 給證據目錄用，**不是可 apply 的 patch**
 *
 * 來源：vacant_hm/world3/index.html
 * sha256：e6ff639d1bd2dc298d5c1db4292c9df5a1184f8f8701f3611d61ea32bb13629f
 * 區塊：第 1566–1962 行（共 397 行），邊界用內容找（'══ 抵達層' → '══ 等待態'）
 *
 * 一行還原：網址加 ?arrive=0 ⇒ ARRIVE_ON=false ⇒ arrive()／update()／draw()
 *           全部提早 return，畫面回到改動前。**不用改碼。**
 *
 * 區塊外面的呼叫點（同一份 index.html，行號對應上面那個 sha）：
 *   L1976  抵達   `arrivals.holding()` 為真的那 2.8 秒。信飛進來、塵爆、周圍轉頭。
 *   L2202  holding: arrivals.holding(),
 *   L2233  // ⚠ `arrivals.holding()`＝抵達那 2.8 秒的優先權。閘門（劇團到齊）**沒動**，
 *   L2235  if (spawnQueue.length && !arrivals.holding()
 *   L2278  if (spawnQueue.length && !arrivals.holding()
 *   L3442  *     （`arrivals.arrive()` 與 `visitorLabel` 照舊）。 */
 *   L3982  *    "arrive"    抵達那一拍正在演（`arrivals.holding()`）⇒ **誰都不准插隊**。
 *   L4424  arrivals.arrive(sub); spawnQueue.push(sub);
 *   L4498  //   那一秒畫面是空的。`arrivals.arrive()` 是**同步**的：同一個 tick 就開始
 *   L4500  WorldBridge.onSubmission(sub => { arrivals.arrive(sub); spawnQueue.push(sub); });
 *
 * ⚠ 這個檔**不會被任何東西載入**。它是抄本，改它不會改到展件。
 */
/* ══ 抵達層 ═══════════════════════════════════════════════════════════
   人類 2026-09-21：「觀眾按下送出的那一秒，畫面必須動。」

   ⚠ **抵達 ≠ 成形，這兩件事以前綁在一起，那是這個展件最大的體驗缺陷。**
     舊路徑只有一句 `spawnQueue.push(sub)`：
       投卡 → 進佇列 → 等導演有空 → `startVisitor()` → 分身成形走出來。
     「等導演有空」在演 replay 的時候是整整一格故事（一分鐘起跳），
     而分身的話本身還要 15–700 秒才生得出來（實測中位 312s）。
     ⇒ 觀眾按下送出、抬頭看螢幕，**什麼都不會發生**。

   這一層只負責**抵達**：一封信從畫面邊緣飛進來、落到投遞口、塵爆、
   周圍的黏土人轉頭看過來。它**不吃劇團、不吃影片、不吃模型**——
   只要一張 PNG（`props/envelope_v*.png`，s03 郵筒吞的就是同一張）
   跟一個座標。`spawnQueue` 那一條線**一個字都沒改**。

   ⚠ `Object.keys(byAgent).length >= 6` 那道閘門**刻意保留**。
     它擋的是「劇團還沒到齊就開演」：`startVisitor` 之後 `crowd(7)` 要湊
     七個圍觀者、`castOf()` 要從六個原型裡取 worker，取不到那一格故事
     就演不出來（P1／D1 那個「每一筆被靜靜丟棄」的坑就是這樣來的）。
     抵達不需要這些 ⇒ **拆開之後閘門可以原封不動留著**，這正是拆開的意義。
     新加的只有 `!arrivals.holding()`：抵達先演 2.8 秒，成形排在它後面，
     不是取代它。

   ⚠ 造型不動（〈動物園要用人不用抽象生物〉：抽象發光生物已被連續三次
     否決）。飛進來的是**一封信**，不是發光體；轉頭的是現成的黏土人形。

   ⚠ 畫面上不印觀眾打的原話，只印代號（`visitorCode`，跟 `visitorLabel`
     同一支）——DECISION_20260921_TWIN_CONSENT_AND_ERASURE §三-3。

   負控制：`?arrive=0` 整層關掉 ⇒ 畫面回到改動前（什麼都不會發生）。
   ════════════════════════════════════════════════════════════════════ */
const ARRIVE_ON = Q.get("arrive") !== "0";
// 抵達要不要 cut 到郵筒那一幕。**分成兩個開關是因為它們的失效模式不同**：
// 換景會逼瀏覽器去載新板／新精靈，機器慢的時候那一下會卡住整條主執行緒
// （headless 實測卡了 ~7 秒）。`?arrivecut=0` 只關換景、信照飛，
// 就是「機器太慢時仍然保得住一秒內有反應」的退路。
const ARRIVE_CUT = Q.get("arrivecut") !== "0";
const ARRIVE_HOLD = 2.8;                      // 抵達的優先權有多長（秒）
// s03 的板上有真的郵筒；投遞口座標＝`sceneDraw` 裡「郵筒吞信」用的同一點。
const DROP_SLOT = { s03: [0.532, 0.628] };
/** 沒有郵筒的景，投遞口就是右下角這塊陶牌上的缺口（這一層自己畫，所以
 *  「卡落到一個看得見的東西上」在**每一個場景**都成立，不只 s03）。 */
function dockGeom(){
  const U = uiScale();
  const w = U * 0.30, h = U * 0.170;
  return { x: W - U*0.03 - w, y: H*0.905 - h, w, h, U };
}
function dropPoint(){
  const p = DROP_SLOT[sceneId];
  if (p) return p;
  const g = dockGeom();
  return [(g.x + g.w*0.5)/W, (g.y + g.U*0.022)/H];
}
/* ── 跟「找到自己」那一條線對齊 ──────────────────────────────────────
   記號層（`TWINTOKEN-V1`／`MARK-LAYER-V1`，另一條線）把同一個不透明 id 算成
   一枚記號（詞＋顏色＋形狀），手機上與電視上是**同一枚**。抵達的視覺鉤子
   由這一層給：**信上蓋的就是他手機上那一枚章**。

   ⚠ 那一支正在被另一個 agent 改。所以這裡一律**防禦式取用**：拿不到、
     壞了、或被關掉（`?mark=0`），就退回自己的蠟封＋`visitorCode` 代號，
     **不讓抵達整層跟著垮**。展場的抵達不可以有單點故障。 */
function arrivalMarkOn(){
  try { return (typeof MARK_ON === "undefined") ? true : !!MARK_ON; } catch (e) { return true; }
}
function arrivalToken(id){
  try { return (typeof twinToken === "function" && arrivalMarkOn()) ? twinToken(id) : null; }
  catch (e) { return null; }
}
function arrivalGlyph(g, x, y, r, tok, alpha){
  try {
    if (tok && typeof twinDrawGlyph === "function"){ twinDrawGlyph(g, x, y, r, tok, alpha); return true; }
  } catch (e) {}
  return false;
}
function hexRgb(hex, fallback){
  const m = /^#?([0-9a-f]{6})$/i.exec(String(hex || ""));
  if (!m) return fallback;
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
const arrivals = {
  flying: [],     // 正在飛／剛落地的信
  waiting: [],    // 已抵達、還沒上台的（陶牌上那幾列）
  total: 0,       // **這一頁開著的期間**收到幾件（不是「今天」——沒有跨頁帳）
  dockT: 0, dock: 0, flash: 0, burstT: null, burstAt: null, holdT: 0,
  marks: [],      // 量測用：每一次抵達的 {id, at, drawnAt}。**不是裝飾**：
                  // 「按下送出到畫面動」要量得動，量不動就不准說「一秒內」。

  holding(){ return this.holdT > 0; },

  /** 投稿抵達。**同步**執行，不等輪詢、不等影片、不等模型。 */
  arrive(sub){
    if (!ARRIVE_ON || !sub) return null;
    const id = sub.id == null ? "" : String(sub.id);
    const card = sub.card || {};
    let h = 0;
    for (let i = 0; i < id.length; i++) h = (h*31 + id.charCodeAt(i)) >>> 0;
    // 起飛方位由 id 決定 ⇒ 同一個人每一次都從同一邊飛進來（可辨識性的一半）
    const side = h % 3;
    // 記號優先（手機上那一枚章）；拿不到才退回代號＋他挑的顏色。
    const tok = arrivalToken(id);
    const a = {
      id, tok, code: visitorCode(id) || "來客", card,
      label: tok ? tok.word : (visitorCode(id) || "來客"),
      // 沒有記號時：蠟封的顏色＝他自己在手機上挑的顏色，而且是 `pickCastFor`
      // 給分身選造型用的**同一組色錨** ⇒ 卡的顏色跟待會成形的那隻同一個顏色。
      rgb: tok ? hexRgb(tok.colorHex, [198, 176, 138])
               : (COLOR_ANCHOR[card.color] || [198, 176, 138]),
      ev: "envelope_v" + (1 + (h % 3)),
      from: side === 0 ? [-0.12, 0.90] : side === 1 ? [0.50, 1.14] : [1.12, 0.90],
      place: this.waiting.length + 1,
      // 同時三個人投卡不會疊在一起：後到的排隊起飛，0.42 秒一封
      wait: this.flying.filter(f => f.t < f.dur).length * 0.42,
      dur: 0.62, landed: false,
    };
    a.t = -a.wait;
    this.total++;
    // 抵達序號（**這一頁開著的期間**單調遞增）。同時多封信落在同一個投遞口時，
    // 靠它決定誰的字疊在誰上面——見 `drawCard` 的 `newer`。
    a.seq = this.total;
    this.flying.push(a);
    this.waiting.push(a);
    while (this.waiting.length > 12) this.waiting.shift();   // 無人值守一整天不長大
    this.dockT = 10;
    this.holdT = ARRIVE_HOLD + a.wait;
    this.marks.push({ id, at: performance.now(), drawnAt: null });
    if (this.marks.length > 50) this.marks.shift();
    // 落點**這一刻就定死，之後不再重算**。舊寫法每一幀問一次 `dropPoint()`，
    // 換景時落點會從陶牌跳到郵筒 ⇒ 飛到一半的信會瞬移。
    a.to = dropPoint();
    // 落點是不是右下角那塊陶牌上的缺口。**跟著這一封走，不看當下的景**——
    // 落點在飛的途中會被換景（s00→s03）改掉判斷，但 `a.to` 早就凍住了
    // ⇒ 用 `sceneId` 去問「要不要避開陶牌」會在換景那一刻答錯。
    a.atDock = !DROP_SLOT[sceneId];
    // ⚠ **換景排在落地之後**，這是量出來才改的：`enterScene("s03")` 會同時叫起
    //   新的板與七支精靈片，軟體解碼的機器上那一下把主執行緒整個卡住。
    //   實測（`ops/exhibit/twin/evidence_visible_20260921/arrival_beat/10_latency`）
    //   「onSubmission → 信第一次畫出來」：**先換景** 3202／4090／11349 ms，
    //   **不換景** 134／256 ms。差的那三到十一秒全是換景。
    //   ⇒ 先讓觀眾看到信落進投遞口（那才是他要的那一秒），再切到郵筒那一幕。
    //   剪接上也更對：先給反應，再給交代場景的那個鏡頭。
    a.wantCut = ARRIVE_CUT;
    a.cutAt = a.dur + 0.35;        // 落地、代號亮出來之後再切
    return a;
  },

  /** 分身真的上台了 ⇒ 從陶牌上劃掉，後面的人序位往前遞補。 */
  spawned(id){
    const k = String(id);
    const i = this.waiting.findIndex(a => a.id === k);
    if (i >= 0) this.waiting.splice(i, 1);
    for (let j = 0; j < this.waiting.length; j++) this.waiting[j].place = j + 1;
  },

  /** 落地那一刻：旁邊**沒在演戲的**人轉頭看過來。
   *  只動 `dir`／`state`／`think` 三個欄位，全部是漫遊邏輯自己會收回去的。
   *
   *  回傳 `{turned, stopped}`：
   *    `turned`  ＝ `dir` **真的翻面**的那幾個（本來就朝著投遞口的不算）
   *    `stopped` ＝ 被叫停下來看的那幾個（含本來就面向那邊的）
   *
   *  ⚠ **兩個數字要分開。** 舊版一律 `n++`，於是「本來就面向那邊、畫面上
   *    一格都沒變」也被記成「轉頭了」——那是把非事件記成事件，跟
   *    「沒量到寫 null 不寫 0」是同一條紀律的反面。判準寫的是
   *    「周圍那群黏土人轉頭看過來」，要拿得出來的是 `turned`。 */
  lookAt(px){
    let turned = 0, stopped = 0;
    for (const c of cast){
      if (!c.onstage || c.reserved || c === director.visitor) continue;
      if (Math.abs(c.nx - px) > 0.60) continue;
      const nd = c.nx > px ? -1 : 1;
      if (c.dir !== nd) turned++;
      c.dir = nd;
      c.state = "idle"; c.target = null;
      c.think = 2.6 + Math.random() * 1.4;
      stopped++;
    }
    return { turned, stopped };
  },

  update(dt){
    if (!ARRIVE_ON) return;
    if (this.holdT > 0) this.holdT = Math.max(0, this.holdT - dt);
    if (this.dockT > 0) this.dockT = Math.max(0, this.dockT - dt);
    if (this.flash > 0) this.flash = Math.max(0, this.flash - dt / 0.6);
    if (this.burstT != null){ this.burstT += dt; if (this.burstT > 0.9) this.burstT = null; }
    const want = (this.waiting.length || this.dockT > 0) ? 1 : 0;
    this.dock += (want - this.dock) * Math.min(1, dt * 5);
    for (const a of this.flying){
      const was = a.t; a.t += dt;
      if (!a.landed && was < a.dur && a.t >= a.dur){
        a.landed = true; this.flash = 1; this.burstT = 0;
        this.burstAt = a.to;                 // 塵爆炸在**這一封**的落點上
        a.looked = this.lookAt(a.to[0]);     // {turned, stopped}——分開記，別混講
      }
      // 換景排在這裡（理由見 `arrive()` 那段實測註解）。只切一次。
      if (a.wantCut && a.t >= a.cutAt){ a.wantCut = false; a.cut = director.toDrop(); }
    }
    this.flying = this.flying.filter(a => a.t < a.dur + 1.35);
  },

  /** 整層畫在**鏡頭變換裡面**（跟著鏡頭呼吸）：陶牌是場上的一塊陶，
   *  不是 HUD。畫在外面的話，鏡頭推到 1.032 時信會落在缺口旁邊 20 幾 px。 */
  draw(){
    if (!ARRIVE_ON) return;
    const [dx, dy] = this.burstAt || dropPoint();
    if (this.dock > 0.02) this.drawDock();
    if (this.flash > 0){
      const f = this.flash * this.flash;
      // 閃光跟著信一起放大（信從 0.050H 改成 0.092H）。半徑比信大一輪，
      // 才讀得出「炸在信落下的那一點」而不是「信後面有一塊亮斑」。
      const g = cx.createRadialGradient(dx*W, dy*H, 0, dx*W, dy*H, H*0.17);
      g.addColorStop(0, `rgba(255,198,118,${0.62*f})`);
      g.addColorStop(1, "rgba(255,198,118,0)");
      cx.save(); cx.globalCompositeOperation = "lighter";
      cx.fillStyle = g; cx.fillRect(dx*W - H*0.18, dy*H - H*0.18, H*0.36, H*0.36);
      cx.restore();
    }
    // 塵爆：**刻意只用 PNG 步進**，不借 `sprites/video/fx_dustburst.mp4`。
    // 那支 video 元素是影池共用的，成形塵爆正在用它時搶過來會讓兩邊都從
    // 中間開始播；而且輕量版根本不載影片。少一點漂亮，換「每一次都一樣、
    // 每一個版本都有」。
    if (this.burstT != null){
      const p = Math.min(1, this.burstT / 0.9);
      drawProp("dust_burst_v" + (1 + (Math.floor(this.burstT * 12) % 3)),
               // 跟著信一起放大。塵爆要**比信寬**，不然信落下去只是「蓋住」
               // 那團煙，讀不出是撞擊濺起來的。
               dx, dy + 0.012, 0.22 + p * 0.17,
               { alpha: (1 - p) * 0.88, anchor: "center" });
    }
    for (const a of this.flying) this.drawCard(a);
  },

  drawCard(a){
    const [dx, dy] = a.to || dropPoint();
    if (a.t < 0) return;                                  // 還在排隊等起飛
    const p = Math.min(1, a.t / a.dur);
    const e = 1 - Math.pow(1 - p, 3);                     // easeOutCubic：飛進來然後坐定
    const q = Math.floor(e * 12) / 12;                    // 12fps 定格（跟全片同一個節拍）
    const x = a.from[0] + (dx - a.from[0]) * q;
    const y = a.from[1] + (dy - a.from[1]) * q - Math.sin(q * Math.PI) * 0.14;
    const after = Math.max(0, a.t - a.dur);
    const alpha = after > 0.80 ? Math.max(0, 1 - (after - 0.80) / 0.55) : 1;
    if (alpha <= 0) return;
    for (const mk of this.marks)
      if (mk.id === a.id && mk.drawnAt == null) mk.drawnAt = performance.now();
    // ⚠ **信要夠大，不然這一層等於沒做。** 第一版是 0.050H（1080p 上 54 px 高）。
    //   連續截圖 `arrival_beat/v1_smallcard/S04_after_triple/f__+0620ms.jpg` 拍到
    //   它縮在右下角、比旁邊的黏土人小一半——判準 1 是「抬頭看螢幕，一秒內
    //   看得出我的東西進去了」，站在展場那個距離**看不出來**。
    //   人類 2026-09-21：「給人看得要極度著墨」。
    //   0.092H ＝ 1080p 上 99 px 高、約 144 px 寬，跟場上的黏土人同一個量級。
    //   飛行中再放大一點（`(1-q)*0.050`）＝同一顆鏡頭推近，不是兩個尺寸在跳。
    //
    // ⚠ 放大之後**落地那一下會蓋住陶牌**（沒有郵筒的景，落點就在陶牌的缺口上，
    //   0.092H 的信往下長 0.046H，正好壓掉「投遞口 · 這一輪收到 N 件」那一列）。
    //   解法不是把信改小回去——那等於把剛剛解決的問題換回來——而是**落地之後
    //   縮進投遞口**：0.30 秒內收到 0.58 倍。讀起來就是「信被吞進去了」，
    //   而觀眾要看的那一秒（飛行的 0–0.62 秒）全程是大的。
    const shrink = a.landed ? 1 - 0.42 * Math.min(1, after / 0.30) : 1;
    const hhFull = 0.092 + (1 - q) * 0.050;
    const hh = hhFull * shrink;
    const rot = (1 - q) * (a.from[0] < 0.5 ? 0.6 : -0.6);
    const sq = a.landed && after < 0.14 ? 0.86 : 1;       // 落地擠壓一拍
    cx.save();
    cx.translate(x*W, y*H); cx.scale(1/Math.sqrt(sq), sq); cx.translate(-x*W, -y*H);
    if (!drawProp(a.ev, x, y, hh, { rot, alpha, anchor: "center" })){
      // PNG 少一張也要看得到：展場不能因為一張圖沒載到就「沒有反應」
      cx.save(); cx.globalAlpha = alpha;
      cx.translate(x*W, y*H); cx.rotate(rot);
      const w2 = H*hh*1.45;
      cx.fillStyle = "#e6dac0"; cx.fillRect(-w2/2, -H*hh/2, w2, H*hh);
      cx.strokeStyle = "rgba(90,66,36,0.55)"; cx.lineWidth = Math.max(1, H*0.0012);
      cx.strokeRect(-w2/2, -H*hh/2, w2, H*hh);
      cx.restore(); cx.globalAlpha = 1;
    }
    // 信上蓋的章：有記號就蓋**他手機上那一枚**，沒有就蓋自己的蠟封
    const [r, g2, b] = a.rgb;
    if (!arrivalGlyph(cx, x*W, y*H, H*hh*0.30, a.tok, alpha)){
      cx.save(); cx.globalAlpha = alpha;
      cx.fillStyle = `rgb(${r},${g2},${b})`;
      cx.beginPath(); cx.arc(x*W, y*H, H*hh*0.26, 0, 7); cx.fill();
      cx.strokeStyle = "rgba(30,20,10,0.45)"; cx.lineWidth = Math.max(1, H*0.0014);
      cx.stroke(); cx.restore(); cx.globalAlpha = 1;
    }
    cx.restore();
    if (a.landed){
      // 落地那三行字（代號／「收到了 · 你是第 N 個」／「手機上同一個記號」）。
      // ⚠ **不能壓在陶牌上。** 沒有郵筒的景，落點就在陶牌的缺口上
      //   ⇒ 照「卡上緣往上」算出來的 `ty`，第三行正好被陶牌的標題列切一半
      //   （連續截圖 `S02_after_single/f__+0620ms.jpg`、`f__+1100ms.jpg` 拍到了）。
      //   三行往下長 TXT_H，所以整塊的上緣要壓到陶牌上緣再減掉 TXT_H 才清得開。
      //   s03 那種板上有真郵筒的景不套這條——那裡落點在畫面中間，本來就沒東西擋。
      //
      // ⚠ 這三個常數**綁在一起**：字級改了，行距、讓位、清空高度要一起改，
      //   不然不是壓到陶牌就是三行散開。所以寫成一組具名常數，不再散落在
      //   六個 `H*0.0xx` 字面值裡（第一版就是那樣，改字級時漏掉兩個）。
      const TXT_1 = 0.036, TXT_2 = 0.026, TXT_3 = 0.020;   // 三行的字級（相對 H）
      const ROW_2 = 0.038, ROW_3 = 0.067;                  // 第二、三行相對第一行的基線
      const TXT_H = ROW_3 + TXT_3;                         // 整塊往下長多少
      // 用**沒縮過**的高度定位：信縮進投遞口的那 0.3 秒，字不要跟著往下爬。
      let ty = (y - hhFull*0.82)*H;
      if (a.atDock) ty = Math.min(ty, dockGeom().y - H*TXT_H - H*0.016);
      // ⚠ **同時多封信落在同一個投遞口，字會疊成一團看不懂。**
      //   `S04_after_triple/f__+1100ms.jpg`（改之前）：第 1 封的「收到了」還沒淡完，
      //   第 2 封的「收到了 · 你是第 2 個」印在同一行上，糊成「收到了 收您是第 2 個」。
      //   判準 3 問的就是這一格，所以不能留。
      //   解法：**比我晚落地的每多一封，我就往上讓一格**。新的在最下面（靠近卡），
      //   舊的往上堆 ⇒ 讀起來就是一疊剛收到的回條。
      let newer = 0;
      for (const o of this.flying) if (o !== a && o.landed && o.seq > a.seq) newer++;
      ty -= newer * H*(TXT_H + 0.014);
      cx.save(); cx.textAlign = "center"; cx.globalAlpha = alpha;
      cx.shadowColor = "rgba(0,0,0,0.75)"; cx.shadowBlur = H*0.010;
      cx.font = serif(H*TXT_1, 700);
      cx.fillStyle = `rgb(${r},${g2},${b})`;
      cx.fillText(a.label, x*W, ty);
      cx.font = serif(H*TXT_2, 600);
      cx.fillStyle = "rgba(240,232,216,0.92)";
      cx.fillText(a.place > 1 ? `收到了 · 你是第 ${a.place} 個` : "收到了",
                  x*W, ty + H*ROW_2);
      if (a.tok){
        // 跟記號層說同一句話（`MARK_HINT`）：手機上那一枚就是這一枚。
        cx.font = serif(H*TXT_3, 500);
        cx.fillStyle = "rgba(240,232,216,0.66)";
        cx.fillText("手機上同一個記號", x*W, ty + H*ROW_3);
      }
      cx.restore(); cx.globalAlpha = 1; cx.shadowBlur = 0;
    }
  },

  /** 右下角那塊陶牌。**判準 3 就靠這一塊**：同時三個人投卡，畫面要看得出
   *  「你是第 2 個」。沒人投的時候完全不出現（`dock` 淡到 0）。 */
  drawDock(){
    const g = dockGeom(), U = g.U, A = Math.min(1, this.dock);
    cx.save();
    cx.globalAlpha = A;
    cx.fillStyle = "rgba(10,7,3,0.62)";
    cx.strokeStyle = "rgba(240,232,216,0.28)";
    cx.lineWidth = Math.max(1, U*0.0014);
    cx.beginPath(); cx.roundRect(g.x, g.y, g.w, g.h, U*0.010);
    cx.fill(); cx.stroke();
    const mx = g.x + g.w*0.5;
    cx.fillStyle = "rgba(0,0,0,0.58)";
    cx.beginPath(); cx.roundRect(mx - U*0.055, g.y + U*0.016, U*0.110, U*0.012, U*0.006);
    cx.fill();
    cx.textAlign = "left";
    cx.font = serif(U*0.020, 700);
    cx.fillStyle = "rgba(240,232,216,0.92)";
    cx.fillText("投遞口", g.x + U*0.018, g.y + U*0.052);
    cx.textAlign = "right";
    cx.font = serif(U*0.016, 600);
    cx.fillStyle = "rgba(240,232,216,0.60)";
    cx.fillText(`這一輪收到 ${this.total} 件`, g.x + g.w - U*0.018, g.y + U*0.052);
    cx.textAlign = "left";
    const rows = this.waiting.slice(0, 3);
    let yy = g.y + U*0.078;
    for (let i = 0; i < rows.length; i++){
      const a = rows[i], [r, g2, b] = a.rgb;
      // 標示層：這一格畫的是**記號本體**（同一支 twinDrawGlyph，手機上也是它），
      // 不是卡片色系的圓點——陶牌上寫著代號，旁邊就該是那個代號的圖案。
      // ⚠ 用抵達那一刻算好的 `a.tok`（跟信上蓋的那一枚是同一枚），不重算；
      //   `arrivalGlyph` 是防禦式的，記號層改壞了也只是退回色點。
      if (!arrivalGlyph(cx, g.x + U*0.026, yy - U*0.005, U*0.0095, a.tok, 1)){
        cx.fillStyle = `rgb(${r},${g2},${b})`;
        cx.beginPath(); cx.arc(g.x + U*0.026, yy - U*0.005, U*0.007, 0, 7); cx.fill();
      }
      cx.font = serif(U*0.0165, 600);
      cx.fillStyle = "rgba(240,232,216,0.90)";
      cx.fillText(`${i+1}　${a.label}`, g.x + U*0.040, yy);
      cx.textAlign = "right";
      cx.font = serif(U*0.0155, 500);
      cx.fillStyle = i === 0 ? "rgba(190,222,190,0.92)" : "rgba(240,232,216,0.55)";
      cx.fillText(i === 0 ? "接下來就是他" : "排隊中", g.x + g.w - U*0.018, yy);
      cx.textAlign = "left";
      yy += U*0.0215;
    }
    if (this.waiting.length > rows.length){
      cx.font = serif(U*0.0145, 500);
      cx.fillStyle = "rgba(240,232,216,0.50)";
      cx.fillText(`…還有 ${this.waiting.length - rows.length} 位在排`, g.x + U*0.040, yy);
    } else if (!this.waiting.length){
      cx.font = serif(U*0.0155, 500);
      cx.fillStyle = "rgba(240,232,216,0.55)";
      cx.fillText("都上台了", g.x + U*0.040, yy);
    }
    cx.font = serif(U*0.0135, 500);
    cx.fillStyle = "rgba(240,232,216,0.42)";
    cx.fillText("一次演一位 · 依抵達順序", g.x + U*0.018, g.y + g.h - U*0.014);
    cx.restore();
    cx.globalAlpha = 1;
  },
};
// 量測與回歸用的把手（**只讀**）。觸發一律走 `WorldBridge.onSubmission`
// 那條真路徑——繞過它直接戳 `arrive()` 就量不到「產品路徑通不通」。
window.__arrivals = arrivals;

