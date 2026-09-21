#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抵達層的**連續截圖**（改動前／後對照）。

為什麼不是直接錄影：這台 Mac 現在 load 500–800（同一批有十幾個 agent 在跑），
headless 的 rAF 被餓到 1–3 fps。照牆上時鐘去截，「+150 ms」那一格拍到的其實是
+1300 ms 的畫面 ⇒ **量具在說謊**，而且是往「看起來比較慢」的方向說謊。

所以這一支把頁面掛到 **Playwright 的假時鐘**上（`clock.install`，連
`requestAnimationFrame`／`performance.now` 一起接管），一格一格往前推：

    clock.run_for(60) → 截圖 → clock.run_for(60) → 截圖 → …

⇒ 每一張的**內容**是虛擬時間軸上精確的那一刻，跟機器忙不忙無關。
   牆上時鐘的延遲另外由 `probe.py` 量（那一支不裝假時鐘）。

兩臂**同一支腳本、同一組虛擬時刻、同一個零點定義**（回呼進到頁面）：
  before  = `git show HEAD:world3/index.html`（`onSubmission(sub => spawnQueue.push(sub))`）
  after   = 現在這一版（抵達層）
  negctl  = 現在這一版 ＋ `?arrive=0`（**單變數**：只把抵達層關掉）
"""
import argparse, json, os, shutil, time
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(HERE, "visitors.json")

EMPTY = {"generated_at": None, "store_id": "probe", "chain": None,
         "counts": {"visitors": 0}, "people": []}
CARDS = [
    {"need": "幫我把一串數字加起來", "shape": "圓潤", "color": "暖土", "texture": "光滑", "first_line": "我來對帳的"},
    {"need": "幫我讀一份很長的報告", "shape": "方正", "color": "青瓷", "texture": "粗糙", "first_line": "我想快點看完"},
    {"need": "幫我把會議記錄整理好", "shape": "細長", "color": "赭紅", "texture": "斑駁", "first_line": "每週三都要交"},
]

# 每一格順手記一次抵達層的狀態。**`looked` 是「真的轉頭了幾個」**——
# 判準裡「周圍那群黏土人轉頭看過來」要量得動，不能只靠我說有。
FRAME_JS = """() => {
  try {
    const A = window.__arrivals;
    if (!A) return null;
    return {total: A.total, flying: A.flying.length, dock: Math.round(A.dock*100)/100,
            burst: A.burstT, scene: sceneId,
            flyingInfo: A.flying.map(x => ({place: x.place, t: Math.round(x.t*1000)/1000,
                                            landed: !!x.landed,
                                            looked: (x.looked === undefined ? null : x.looked)})),
            waiting: A.waiting.map(x => ({label: x.label, place: x.place}))};
  } catch (e) { return null; }
}"""

# 零點偵測。⚠ **只看 `spawnQueue.length` 會漏**：導演閒著的時候，
# `onSubmission` 那一筆會在**同一個 run_for 裡面**被 `startVisitor` 撿走
# （0 → 1 → 0），外面兩次取樣之間什麼都沒看到。`S03_negctl_arrive0`
# 第一次就是這樣 `anchorFound=False` 的——**而畫面上分身其實已經上台了**，
# 也就是量具在說「沒發生」而事情發生了。
# 所以改成看四個**會留下來**的訊號，任何一個動了就算：
#   arrivals.total（改動後那一層）／spawnQueue.length（還沒被撿走時）／
#   director.visitorId（撿走了就會設）／bridge 那一輪送出幾筆（tried[].n）。
# 量測期間把看門狗的 `location.reload()` 擋下來（**記次數，不假裝沒發生**）。
#
# ⚠ **舊版這裡的 `BLOCK_RELOAD` 是個空操作，而且空了整整兩批。**
#   它用 `Object.defineProperty(location, 'reload', …)`，而 `Location` 的屬性在
#   HTML 規格裡是 `[LegacyUnforgeable]`（不可設定）⇒ 直接丟
#   `TypeError: Cannot redefine property: reload`，被 `try/catch` 吞掉，
#   看門狗照樣重載。`S03_negctl_arrive0` 與 `S05_before_triple` 兩跑就是這樣
#   死在 `Execution context was destroyed` 的，而 log 上看起來像是「機器太慢」。
#   證據：`out/t_reload.json`（四臂，含正控制）。
#
#   ⇒ 換成在**上游**攔：認出那一支 setInterval 回呼（原始碼含 `vw_reloads`，
#     全檔唯一），換成判準逐字相同、但**記一筆而不是重載**的替身。
BLOCK_RELOAD = open(os.path.join(HERE, "blockwatchdog.js"), encoding="utf-8").read()

ANCHOR_JS = """() => {
  let q = null, t = null, v = null, n = null;
  try { q = (typeof spawnQueue !== 'undefined') ? spawnQueue.length : null; } catch(e){}
  try { t = window.__arrivals ? window.__arrivals.total : null; } catch(e){}
  try { v = (typeof director !== 'undefined' && director.visitorId) ? 1 : 0; } catch(e){}
  try {
    const st = WorldBridge.sourceState();
    n = (st && st.tried || []).reduce((a, x) => a + (x && x.n ? x.n : 0), 0);
  } catch(e){}
  return [q, t, v, n];
}"""

STATE_JS = """() => {
  let a = null;
  try {
    const A = window.__arrivals;
    if (A) a = { total: A.total, flying: A.flying.length,
                 waiting: A.waiting.map(w => ({label: w.label, place: w.place,
                                               looked: (w.looked === undefined ? null : w.looked)})),
                 marks: A.marks.slice(-8) };
  } catch (e) {}
  let ready = null;
  try { ready = (typeof byAgent !== 'undefined') ? Object.keys(byAgent).length : null; } catch(e){}
  let q = null;
  try { q = (typeof spawnQueue !== 'undefined') ? spawnQueue.length : null; } catch(e){}
  let b = null;
  try { b = WorldBridge.sourceState(); } catch(e){}
  let np = null;
  try { np = (typeof propCache !== 'undefined') ? propCache.size : null; } catch(e){}
  const rb = window.__watchdogWouldFire === undefined ? null : window.__watchdogWouldFire;
  const rbf = window.__watchdogArmed === undefined ? null : window.__watchdogArmed;
  const gap = window.__maxFrameGapMs === undefined ? null : window.__maxFrameGapMs;
  let sT = null, xf = null, sid = null;
  try { sT = sceneT; xf = snapA; sid = sceneId; } catch(e){}   // xfade 恆為 0（死變數），真正在轉場的是 snapA
  return {arrivals: a, castReady: ready, queueLen: q, propsLoaded: np, title: document.title,
          sceneT: sT, snapA: xf, sceneId: sid,
          watchdogWouldFire: rb, watchdogArmed: rbf, maxFrameGapMs: gap,
          bridgeKind: b ? b.kind : null, bridgeErr: b ? b.lastErr : null,
          now: performance.now()};
}"""


def write_snapshot(ids):
    doc = dict(EMPTY)
    doc["people"] = [{"id": p, "card": CARDS[i % len(CARDS)], "arrival": None,
                      "working": None, "handover": None, "engine": None, "status": None}
                     for i, p in enumerate(ids)]
    doc["counts"] = {"visitors": len(doc["people"])}
    tmp = SNAP + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    os.replace(tmp, SNAP)


def tick(pg, virtual_ms, real_wait=0.10):
    """推進假時鐘 virtual_ms，再給真實世界一點時間去跑 fetch／解圖。

    ⚠ **暫停之後才準。** `clock.install()` 自己不停錶（時間照真實世界走，
      只是可以插隊推進），所以暖機階段量到「run_for(500) 走了 910 ms」。
      要一格一格精確踩，必須先 `pause_at()` 把錶停住。"""
    pg.clock.run_for(int(virtual_ms))
    if real_wait:
        time.sleep(real_wait)


def run(port, arm, out, n_subs, marks_ms, warm_ticks):
    outdir = os.path.join(HERE, "out", out)
    shutil.rmtree(outdir, ignore_errors=True)
    os.makedirs(outdir, exist_ok=True)
    write_snapshot([])
    # `index.frozen.html`＝量測開始那一刻的 index.html 副本。用副本是因為
    # 第一批跑到一半，活的那個檔就被別的 agent 改掉了（sha ebabae34→8e2ec474）。
    page_file = "index.before.html" if arm == "before" else "index.frozen.html"
    qs = ["twinfile=/probe/visitors.json", "twinpoll=1000", "twin=off", "lite=1"]
    if arm == "negctl":
        qs.append("arrive=0")
    url = "http://127.0.0.1:%d/world3/%s?%s" % (port, page_file, "&".join(qs))

    rec = {"arm": arm, "out": out, "url": url, "n_subs": n_subs,
           "clock": "Playwright fake clock（rAF／performance.now 一起接管）",
           "viewport": "1280x720", "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "loadavg_at_start": list(os.getloadavg())}
    console = []
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--mute-audio", "--disable-lcd-text"])
        ctx = br.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
        pg = ctx.new_page()
        pg.on("console", lambda m: console.append(m.type + ": " + m.text[:200]))
        pg.on("pageerror", lambda e: console.append("pageerror: " + str(e)[:200]))
        # ⚠ **順序有意義，而且第一次弄反了。** `clock.install()` 自己也會換掉
        #   `window.setInterval`；先裝攔截就會被它整個蓋過去，看門狗照樣直通。
        #   第一批跑出來 `watchdogArmed: 0`（＝一支都沒認出來）就是這個。
        #   那一跑沒死純粹是運氣——停錶之後假時鐘不推進，看門狗才沒開槍；
        #   暖機那一段錶還在走，照樣會被重載走。**先 install 再攔。**
        pg.clock.install()
        pg.add_init_script(BLOCK_RELOAD)
        pg.goto(url, wait_until="domcontentloaded", timeout=90000)
        # 暖機：時鐘還在自己走，只用真實時間等。要等到
        #   （a）劇團到齊（`byAgent` 六個）——`startVisitor` 的既有閘門，**沒動它**；
        #   （b）板／精靈／信封 PNG 真的載進來——不然拍到的是 fallback 方塊；
        #   （c）輪詢至少成功過一次。
        st = None
        t_warm = time.time()
        while time.time() - t_warm < warm_ticks:
            time.sleep(1.0)
            st = pg.evaluate(STATE_JS)
            # ⚠ **不可以在換景的淡入淡出中間停錶**：第一批的 `S01_before_single`
            #   就這樣停在黑畫面上，`f__pre.jpg` 整張全黑 ⇒ 基準線看不出東西，
            #   而且會被誤讀成「改動前本來就是黑的」。要等這一景站穩。
            if (st.get("castReady") or 0) >= 6 and st.get("bridgeKind") \
               and (st.get("propsLoaded") or 0) >= 3 and time.time() - t_warm > 10 \
               and (st.get("sceneT") or 0) > 2.5 and (st.get("snapA") or 0) <= 0.02:
                break
        rec["preState"] = st
        rec["warmRealSec"] = round(time.time() - t_warm, 1)

        # ══ 這一支跟 strip.py 的唯一差別：**先讓導演忙起來** ══════════════
        #
        # 為什麼要有這一臂：S03（負控制、導演閒著）拍出來的是——投卡 620 ms
        # 之後畫面**已經**硬切到「世界多了一個人」。也就是說「改動前投卡完全
        # 沒反應」這句話**是錯的**，導演閒著的時候它反應得很快。
        # 我差一點就照那個錯的說法交報告。
        #
        # 真正有落差的是**導演正在演別人的故事**的時候：`toDrop()` 那時候回
        # false（不打斷一格正在講的故事，那是刻意的），`startVisitor` 也要等
        # 整格演完。改動前那個人在畫面上**完全不存在**，一分鐘起跳；
        # 改動後他還是會看到自己那封信落進投遞口＋陶牌上多一列「排隊中」。
        #
        # 展場的常態就是這一格（有人排隊才叫排隊），所以它是主證據不是補充。
        # 作法：先送 A 進去把導演帶進故事，等 mode 離開 wait，再送 B 並量 B。
        prime_id = "%s-prime-%s" % (out, time.strftime("%H%M%S"))
        write_snapshot([prime_id])
        t_busy = time.time()
        busy = False
        while time.time() - t_busy < 120:
            time.sleep(1.0)
            b = pg.evaluate("() => ({mode: director.mode, vid: director.visitorId || null})")
            if b["mode"] not in ("wait", "invite", "ambient"):
                busy = True
                break
        rec["primedDirector"] = {"ok": busy, "id": prime_id,
                                 "waitedRealSec": round(time.time() - t_busy, 1),
                                 "mode": pg.evaluate("() => director.mode")}
        # 拿不到「忙」就**不要假裝這一臂成立**：記下來，下游讀得到。
        if not busy:
            rec["primedDirector"]["note"] = "導演沒有進入故事 ⇒ 這一臂量到的不是「忙的時候」"

        # ── 停錶 ──────────────────────────────────────────────────────
        # 從這裡開始，虛擬時間只有我 `run_for` 才會動 ⇒ 每一張截圖的**內容**
        # 都落在虛擬時間軸上精確的那一刻，機器多忙都不影響。
        now_ms = pg.evaluate("() => Date.now()")
        pg.clock.pause_at(now_ms)
        pg.screenshot(path=os.path.join(outdir, "f__pre.jpg"), type="jpeg", quality=80)

        ids = ["%s-%s-%d" % (out, time.strftime("%H%M%S"), i) for i in range(n_subs)]
        rec["ids"] = ids
        # ⚠ 先來的那一位**要留在快照裡**。只寫 ids 等於把他從名冊上刪掉，
        #   那不是「第二個人投卡」而是「第一個人消失、換一個人」——
        #   bridge 那一層看到的事件完全不同。
        write_snapshot([prime_id] + ids)
        # 推到回呼進來為止。輪詢的 setTimeout 吃虛擬時間（1000 ms 一輪），
        # 但 fetch 本身是真的網路 ⇒ 每推一次要給真實世界一點時間去把它跑完。
        # **錶是停的**，所以這一段等待完全不佔虛擬時間，畫面一格都不會前進。
        base = pg.evaluate(ANCHOR_JS)

        def moved():
            cur = pg.evaluate(ANCHOR_JS)
            return any(c is not None and b is not None and c > b
                       for c, b in zip(cur, base))

        found, virt_used = False, 0
        for _ in range(24):
            for _ in range(6):          # 真實世界先跑：讓上一輪的 fetch 落地
                if moved():
                    found = True
                    break
                time.sleep(0.25)
            if found:
                break
            pg.clock.run_for(250)
            virt_used += 250
        rec["anchorFound"] = found
        rec["anchorVirtualMsFromWrite"] = virt_used if found else None

        frames = []
        prev = 0
        for want in marks_ms:
            step = want - prev
            if step > 0:
                tick(pg, step, 0.06)
            prev = want
            fn = "f__%+05dms.jpg" % want
            pg.screenshot(path=os.path.join(outdir, fn), type="jpeg", quality=80)
            frames.append({"virtualMs": want, "file": fn,
                           "state": pg.evaluate(FRAME_JS)})
        rec["frames"] = frames
        rec["postState"] = pg.evaluate(STATE_JS)
        rec["console"] = console
        rec["loadavg_at_end"] = list(os.getloadavg())
        ctx.close()
        br.close()
    with open(os.path.join(outdir, "strip.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    ps = rec["postState"]
    print(json.dumps({"arm": arm, "out": out, "anchorFound": found,
                      "postArrivals": ps.get("arrivals"),
                      "castReady": ps.get("castReady"),
                      # 看門狗替身：armed 應該恰好 1（認出那一支）。
                      # wouldFire>0 ＝這一跑畫面真的凍過，**要寫出來不要吞掉**。
                      "watchdogArmed": ps.get("watchdogArmed"),
                      "watchdogWouldFire": ps.get("watchdogWouldFire"),
                      "maxFrameGapMs": ps.get("maxFrameGapMs"),
                      "loadavg": [round(x) for x in rec["loadavg_at_end"]]},
                     ensure_ascii=False)[:900])
    print("  console:", console[:3])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8622)
    ap.add_argument("--arm", required=True, choices=["before", "after", "negctl"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--subs", type=int, default=1)
    ap.add_argument("--warm", type=int, default=40)
    a = ap.parse_args()
    # 虛擬時刻：抵達那 620 ms 要密（那是「畫面動了沒有」的那一段），之後放寬。
    # ⚠ 2400／3200／4200 那三格在 load 900 的機器上一格要跑三到四分鐘
    #   （一格＝把虛擬時間往前推幾百毫秒＝幾十個 rAF frame），而那時候故事
    #   早就切到 s03 了，對「投卡那一秒」沒有新資訊。第二批砍掉尾巴。
    #   對照表只用 [0,120,250,400,620,900,1400]，兩批都涵蓋得到。
    marks = [0, 60, 120, 180, 250, 320, 400, 500, 620, 760, 900, 1100, 1400, 1800]
    # 看門狗擋下來之後應該不會再炸，但**擋不住不等於沒發生**：真的被導覽掉
    # （`Execution context was destroyed`）就整跑重來一次，重來也失敗就讓它紅。
    # 悄悄吞掉會留下一份「拍到一半」的證據目錄，那比沒有更糟。
    for attempt in (1, 2):
        try:
            run(a.port, a.arm, a.out, a.subs, marks, a.warm)
            break
        except Exception as e:
            print("attempt %d 失敗：%s" % (attempt, str(e)[:200]), flush=True)
            if attempt == 2:
                raise
