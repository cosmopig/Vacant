#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抵達層（arrivals）的可視化量測。

量的是人類問的那一句：**「我按下送出，抬頭看螢幕，一秒內看得出我的東西進去了嗎？」**

觸發一律走**產品路徑**：寫 `visitors.json` → `bridge.js` 輪詢 → `WorldBridge.onSubmission`
→ `arrivals.arrive()`。**不直接戳 `arrive()`**——繞過去就量不到「接線通不通」。

三個時間點（拿不到一律 `null`，不寫 0）：
  t_write  我把那個人寫進快照的那一刻（＝觀眾按下送出）
  t_cb     `onSubmission` 回呼進到頁面裡（`marks[].at`）   ← 差＝輪詢間隔，bridge 那一層的
  t_paint  那封信**第一次被畫出來**（`marks[].drawnAt`）    ← 差＝抵達層自己的延遲
"""
import argparse, json, os, shutil, time
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(HERE, "visitors.json")
BASE = "http://127.0.0.1:%d"

EMPTY = {"generated_at": None, "store_id": "probe", "chain": None,
         "counts": {"visitors": 0}, "people": []}

CARDS = [
    {"need": "幫我把一串數字加起來", "shape": "圓潤", "color": "暖土", "texture": "光滑", "first_line": "我來對帳的"},
    {"need": "幫我讀一份很長的報告", "shape": "方正", "color": "青瓷", "texture": "粗糙", "first_line": "我想快點看完"},
    {"need": "幫我把會議記錄整理好", "shape": "細長", "color": "赭紅", "texture": "斑駁", "first_line": "每週三都要交"},
]


def write_snapshot(ids):
    people = []
    for i, pid in enumerate(ids):
        people.append({"id": pid, "card": CARDS[i % len(CARDS)],
                       "arrival": None, "working": None, "handover": None,
                       "engine": None, "status": None})
    doc = dict(EMPTY)
    doc["people"] = people
    doc["counts"] = {"visitors": len(people)}
    tmp = SNAP + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    os.replace(tmp, SNAP)       # 原子換檔：不讓輪詢讀到半寫的檔
    return time.time()


INIT = """
window.__fps = [];
window.__polls = [];
(function(){
  const raf = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = function(cb){
    return raf(function(ts){ window.__fps.push(ts); if (window.__fps.length > 6000) window.__fps.shift(); return cb(ts); });
  };
  // 輪詢那一層是 bridge.js 的（**不是我改的那一層**），但端到端延遲裡它佔大頭，
  // 所以要量得動：每一通打到快照的 fetch 記一筆「送出／回來」。
  const of = window.fetch.bind(window);
  window.fetch = function(u, o){
    const s = String((u && u.url) ? u.url : u);
    if (s.indexOf('visitors.json') < 0) return of(u, o);
    const t0 = performance.now();
    return of(u, o).then(function(r){
      window.__polls.push({t0: t0, t1: performance.now(), ok: !!(r && r.ok), st: r ? r.status : null});
      if (window.__polls.length > 400) window.__polls.shift();
      return r;
    }, function(e){
      window.__polls.push({t0: t0, t1: performance.now(), ok: false, st: null});
      throw e;
    });
  };
})();
"""

SNAPSHOT_JS = """() => {
  let a = null;
  try {
    const A = window.__arrivals;
    if (A) a = { total: A.total,
                 flying: A.flying.length,
                 waiting: A.waiting.map(w => ({label: w.label, code: w.code, place: w.place,
                                               tok: w.tok ? String(w.tok.word) : null,
                                               looked: (w.looked === undefined ? null : w.looked)})),
                 marks: A.marks.slice(-8) };
  } catch (e) { a = null; }
  let b = null;
  try { b = window.WorldBridge && WorldBridge.sourceState ? WorldBridge.sourceState() : null; } catch (e) {}
  const fp = window.__fps || [];
  return { arrivals: a, bridge: b, timeOrigin: performance.timeOrigin,
           now: performance.now(), title: document.title,
           polls: (window.__polls || []).slice(-40),
           frameTs: fp.slice(-260),
           frames: fp.length, firstFrame: (fp.length ? fp[0] : null),
           lastFrame: (fp.length ? fp[fp.length-1] : null),
           queueLen: (typeof spawnQueue !== 'undefined') ? spawnQueue.length : null,
           // 看門狗替身的三個數字。`watchdogArmed` 不是 1 就代表這一跑**可能被
           // 整頁重載過**，端到端延遲要作廢，不可以當成「這一版就是這麼慢」。
           watchdogArmed: window.__watchdogArmed === undefined ? null : window.__watchdogArmed,
           watchdogWouldFire: window.__watchdogWouldFire === undefined ? null : window.__watchdogWouldFire,
           maxFrameGapMs: window.__maxFrameGapMs === undefined ? null : window.__maxFrameGapMs,
           castReady: (typeof byAgent !== 'undefined') ? Object.keys(byAgent).length : null };
}"""


def run(port, label, out, n_subs, extra_qs, lite, warm_s, shots_ms, video):
    outdir = os.path.join(HERE, "out", out)
    shutil.rmtree(outdir, ignore_errors=True)
    os.makedirs(outdir, exist_ok=True)
    write_snapshot([])
    page_file = "index.before.html" if label == "before" else "index.html"
    qs = ["twinfile=/probe/visitors.json", "twinpoll=1000", "twin=off"]
    if lite is not None:
        qs.append("lite=%d" % (1 if lite else 0))
    qs += extra_qs
    url = (BASE % port) + "/world3/" + page_file + "?" + "&".join(qs)

    rec = {"label": label, "out": out, "url": url, "n_subs": n_subs,
           "viewport": "1280x720", "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    console = []
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required",
                                     "--mute-audio", "--disable-lcd-text"])
        ctxargs = {"viewport": {"width": 1280, "height": 720}, "device_scale_factor": 1}
        if video:
            ctxargs["record_video_dir"] = os.path.join(outdir, "video")
            ctxargs["record_video_size"] = {"width": 1280, "height": 720}
        ctx = br.new_context(**ctxargs)
        # 看門狗替身要**排在計數器前面**（它自己也要 rAF）。這一支沒有假時鐘，
        # 所以沒有 `clock.install()` 蓋掉 `setInterval` 的問題（那是 strip.py 的坑）。
        # 早幾批的 probe 沒裝這個，畫面標題上出現過 `reloads=1`——**那幾跑的
        # 端到端數字含一次整頁重載**，不可以跟這一批混在一起講。
        ctx.add_init_script(open(os.path.join(HERE, "blockwatchdog.js"), encoding="utf-8").read())
        ctx.add_init_script(INIT)
        pg = ctx.new_page()
        pg.on("console", lambda m: console.append(m.type + ": " + m.text[:220]))
        pg.on("pageerror", lambda e: console.append("pageerror: " + str(e)[:220]))
        pg.goto(url, wait_until="load", timeout=60000)
        # 暖機：讓板／精靈載完、劇團到齊、輪詢跑過幾輪。這一段刻意不量。
        t_warm = time.time()
        while time.time() - t_warm < warm_s:
            time.sleep(0.5)
        rec["preState"] = pg.evaluate(SNAPSHOT_JS)

        pg.screenshot(path=os.path.join(outdir, "shot__pre-500ms.jpg"), type="jpeg", quality=72)
        ids = ["%s-%s-%d" % (out, time.strftime("%H%M%S"), i) for i in range(n_subs)]
        rec["ids"] = ids
        t_write = write_snapshot(ids)
        rec["t_write_epoch_ms"] = t_write * 1000.0

        # ── 連續截圖的零點：**回呼進到頁面裡的那一刻**，不是我寫檔那一刻 ──
        #
        # ⚠ 這不是把數字調漂亮。這台機器現在 load 500+（同時有十幾個 agent 在跑），
        #   `bridge.js` 的輪詢被餓到 4–11 秒才跑一輪（設定值是 1000 ms）。
        #   零點放在寫檔那一刻，整條 0–7 秒的截圖帶會全部落在「回呼還沒進來」，
        #   兩臂都拍到空畫面 ⇒ 什麼都比不出來。
        #   **輪詢那一段是 `bridge.js` 的，不是這次改的那一層**；這一層要回答的是
        #   「回呼進來之後，畫面動了沒有」。兩臂用**同一個零點定義**（`spawnQueue`
        #   或 `arrivals.total` 增加），所以比較仍然公平。
        #   端到端那個數字另外記在 `latency[].writeToPaintMs`，**不藏**。
        anchor_js = """() => {
          let q = null, t = null;
          try { q = (typeof spawnQueue !== 'undefined') ? spawnQueue.length : null; } catch(e){}
          try { t = window.__arrivals ? window.__arrivals.total : null; } catch(e){}
          return [q, t];
        }"""
        q0, a0 = pg.evaluate(anchor_js)
        t_anchor, anchor_wait = None, None
        deadline = time.time() + 75
        while time.time() < deadline:
            q1, a1 = pg.evaluate(anchor_js)
            if (q1 is not None and q0 is not None and q1 > q0) or \
               (a1 is not None and a0 is not None and a1 > a0):
                t_anchor = time.time()
                anchor_wait = round((t_anchor - t_write) * 1000)
                break
            time.sleep(0.04)
        rec["anchor"] = {"t0_def": "回呼進到頁面（spawnQueue／arrivals.total 增加）",
                         "writeToAnchorMs_outerPolled": anchor_wait,
                         "found": t_anchor is not None}
        t0 = t_anchor if t_anchor is not None else t_write

        shots = []
        for want in (shots_ms or []):
            dt = t0 + want / 1000.0 - time.time()
            if dt > 0:
                time.sleep(dt)
            real = int(round((time.time() - t0) * 1000))
            fn = "shot__want+%dms__real+%dms.jpg" % (want, real)
            pg.screenshot(path=os.path.join(outdir, fn), type="jpeg", quality=72)
            shots.append({"want": want, "real": real, "file": fn})
        rec["shots"] = shots
        if not shots_ms:
            # 不截圖的那一趟（全功能模式）：截圖本身會把這台已經 load 400+ 的機器
            # 逼到每張 10–20 秒，反而量不到東西。改成只錄影＋讀頁內量測。
            tail = max(shots_ms or [0]) if shots_ms else 8000
            time.sleep(tail / 1000.0)

        post = pg.evaluate(SNAPSHOT_JS)
        rec["postState"] = post

        lat = []
        A = post.get("arrivals")
        if A and A.get("marks"):
            origin = post["timeOrigin"]
            for mk in A["marks"]:
                cb = origin + mk["at"] if mk.get("at") is not None else None
                pt = origin + mk["drawnAt"] if mk.get("drawnAt") is not None else None
                lat.append({
                    "id": mk.get("id"),
                    "writeToCallbackMs": None if cb is None else round(cb - t_write * 1000.0),
                    "callbackToPaintMs": None if (cb is None or pt is None) else round(pt - cb),
                    "writeToPaintMs": None if pt is None else round(pt - t_write * 1000.0),
                })
        rec["latency"] = lat or None

        n, f0, f1 = post.get("frames"), post.get("firstFrame"), post.get("lastFrame")
        if n and f0 is not None and f1 is not None and n > 1 and (f1 - f0) > 0:
            rec["fpsWholeRun"] = round(n / ((f1 - f0) / 1000.0), 2)
        else:
            rec["fpsWholeRun"] = None
        # 事件前後那 3 秒的 fps（整跑平均被「載入時卡住」拖垮，那一段跟展場無關）
        rec["fpsAroundEvent"] = None
        try:
            ts = post.get("frameTs") or []
            cb_at = None
            if A and A.get("marks"):
                cb_at = A["marks"][-1].get("at")
            if cb_at is not None:
                win = [t for t in ts if cb_at - 1500 <= t <= cb_at + 1500]
                if len(win) > 1 and (win[-1] - win[0]) > 0:
                    rec["fpsAroundEvent"] = round(len(win) / ((win[-1] - win[0]) / 1000.0), 2)
        except Exception:
            pass
        pl = post.get("polls") or []
        gaps = sorted(round(pl[i]["t0"] - pl[i - 1]["t0"]) for i in range(1, len(pl)))
        rec["pollGapsMs"] = {"n": len(gaps), "median": gaps[len(gaps) // 2] if gaps else None,
                             "max": gaps[-1] if gaps else None}
        rec["loadavg"] = list(os.getloadavg())
        post.pop("frameTs", None)          # 只是拿來算 fps 的，別把幾百個浮點數寫進證據
        rec["console"] = console
        vid = None
        if video:
            try:
                vid = pg.video.path()
            except Exception as e:
                rec["videoErr"] = str(e)[:200]
        ctx.close()
        br.close()
        if vid and os.path.exists(vid):
            dst = os.path.join(outdir, out + ".webm")
            shutil.move(vid, dst)
            rec["video"] = os.path.basename(dst)
            shutil.rmtree(os.path.join(outdir, "video"), ignore_errors=True)
        else:
            rec["video"] = None
    with open(os.path.join(outdir, "probe.json"), "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1)
    print(json.dumps({k: rec.get(k) for k in ("label", "out", "latency", "fpsWholeRun",
                                              "fpsAroundEvent", "pollGapsMs", "loadavg", "video")},
                     ensure_ascii=False))
    print("  arrivals=", json.dumps(rec["postState"].get("arrivals"), ensure_ascii=False)[:500])
    print("  bridge=", json.dumps(rec["postState"].get("bridge"), ensure_ascii=False)[:300])
    print("  console=", console[:4])
    return rec


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8622)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--subs", type=int, default=1)
    ap.add_argument("--qs", default="")
    ap.add_argument("--lite", default="")
    ap.add_argument("--warm", type=float, default=20)
    ap.add_argument("--novideo", action="store_true")
    ap.add_argument("--noshots", action="store_true")
    a = ap.parse_args()
    lite = None if a.lite == "" else (a.lite == "1")
    shots = [] if a.noshots else [0, 150, 300, 450, 600, 800, 1000, 1300,
                                  1700, 2200, 3000, 4500, 7000]
    run(a.port, a.label, a.out, a.subs,
        [x for x in a.qs.split(",") if x], lite, a.warm, shots, not a.novideo)
