#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""改完造型常數之後的冒煙：**頁面還跑不跑得動、抵達還畫不畫得出來。**

比一整批連續截圖便宜得多，先跑這一支再決定要不要開 20 分鐘的批次。
它只問四件事：
  1. 沒有 pageerror（改壞了 canvas 呼叫會直接在這裡紅）
  2. `__arrivals.total` 真的變成 1（走的是 `WorldBridge.onSubmission` 那條真路徑）
  3. `marks[0].drawnAt` 有值 ⇒ 信**真的被畫出來過**（不是只進了資料結構）
  4. 看門狗替身認出來了（`watchdogArmed == 1`）——`strip.py` 改了順序之後要驗
"""
import json, os, sys, time
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from strip import write_snapshot, BLOCK_RELOAD, STATE_JS   # noqa: E402

URL = ("http://127.0.0.1:8622/world3/index.html"
       "?twinfile=/probe/visitors.json&twinpoll=1000&twin=off&lite=1")

write_snapshot([])
errs = []
with sync_playwright() as p:
    br = p.chromium.launch(args=["--mute-audio", "--disable-lcd-text"])
    ctx = br.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)[:220]))
    pg.on("console", lambda m: errs.append("console." + m.type + ": " + m.text[:160])
          if m.type == "error" else None)
    pg.clock.install()
    pg.add_init_script(BLOCK_RELOAD)
    pg.goto(URL, wait_until="domcontentloaded", timeout=120000)

    st = None
    t0 = time.time()
    while time.time() - t0 < 90:
        time.sleep(1.5)
        st = pg.evaluate(STATE_JS)
        if (st.get("castReady") or 0) >= 6 and (st.get("propsLoaded") or 0) >= 3:
            break
    print("暖機", round(time.time() - t0, 1), "秒 ·",
          json.dumps({k: st.get(k) for k in
                      ("castReady", "propsLoaded", "sceneId", "watchdogArmed",
                       "maxFrameGapMs", "bridgeKind")}, ensure_ascii=False))

    write_snapshot(["smoke-0001"])
    seen = False
    for _ in range(40):
        time.sleep(0.5)
        st = pg.evaluate(STATE_JS)
        a = st.get("arrivals") or {}
        if (a.get("total") or 0) >= 1:
            seen = True
            break
    # 讓它飛完＋落地（虛擬時鐘沒停，run_for 只是插隊推進）
    pg.clock.run_for(1200)
    time.sleep(1.5)
    st = pg.evaluate(STATE_JS)
    pg.screenshot(path=os.path.join(HERE, "out", "smoke.jpg"), type="jpeg", quality=85)
    ctx.close(); br.close()

a = st.get("arrivals") or {}
marks = a.get("marks") or []
drawn = [m for m in marks if m.get("drawnAt")]
lat = round(drawn[0]["drawnAt"] - drawn[0]["at"], 1) if drawn else None
checks = {
    "沒有 pageerror": not errs,
    "抵達層收到那一筆（走真路徑）": (a.get("total") or 0) >= 1 and seen,
    "信真的被畫出來過（drawnAt 有值）": bool(drawn),
    "看門狗替身認出來了（armed==1）": st.get("watchdogArmed") == 1,
}
print(json.dumps({"arrivals": a, "回呼到第一次畫出來 ms": lat,
                  "maxFrameGapMs": st.get("maxFrameGapMs"),
                  "watchdogWouldFire": st.get("watchdogWouldFire")}, ensure_ascii=False)[:600])
if errs:
    print("錯誤：", errs[:5])
for k, v in checks.items():
    print(("  PASS  " if v else "  FAIL  ") + k)
print("SMOKE", "PASS" if all(checks.values()) else "FAIL")
sys.exit(0 if all(checks.values()) else 1)
