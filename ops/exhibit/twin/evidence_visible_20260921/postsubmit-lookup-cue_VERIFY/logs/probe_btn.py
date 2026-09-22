# -*- coding: utf-8 -*-
"""量 sendPreset 的按鈕回饋到底看得見多久。MutationObserver，不靠 sleep 猜。
   兩種網路：localhost（≈0ms）與 +600ms（展場 4G 的保守值）。"""
import re, sys, time
from playwright.sync_api import sync_playwright
BASE = "http://127.0.0.1:18764"

def run(delay_ms, out_png):
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        ctx = br.new_context(viewport={"width":390,"height":844}, device_scale_factor=2,
                             is_mobile=True, has_touch=True, locale="zh-TW")
        pg = ctx.new_page()
        if delay_ms:
            def slow(route):
                # 不阻塞 driver thread：用 playwright 自己的 fallback 延遲不行，
                # 改成在 page 內用 fetch 攔截不可靠 => 這裡用 route + 背景 sleep 可接受，
                # 因為量測是 page 內的 MutationObserver 時間戳，不是 driver 的。
                time.sleep(delay_ms/1000.0); route.continue_()
            pg.route("**/api/preset", slow)
        pg.goto(BASE + "/", wait_until="networkidle")
        pg.click("#startBtn"); pg.wait_for_timeout(500)
        pg.evaluate("""() => {
          window.__btn = []; const el = document.getElementById('refuseBtn');
          window.__t0 = null;
          el.addEventListener('click', () => { window.__t0 = performance.now(); }, true);
          new MutationObserver(() => window.__btn.push([el.textContent, performance.now()]))
            .observe(el, {childList:true, characterData:true, subtree:true});
        }""")
        pg.click("#refuseBtn")
        pg.wait_for_function("document.getElementById('p5').classList.contains('on')", timeout=20000)
        ev = pg.evaluate("({t0:window.__t0, log:window.__btn})")
        print(f"delay={delay_ms}ms  t0={ev['t0']}")
        for txt, t in ev["log"]:
            print(f"   +{t-ev['t0']:7.1f}ms  {txt!r}")
        if len(ev["log"]) >= 2:
            print(f"   => 「正在挑一隻示範分身…」可見時長 = {ev['log'][1][1]-ev['log'][0][1]:.1f} ms")
        elif len(ev["log"]) == 1:
            print("   => 只換了一次字，沒換回來（p1 已離開畫面，觀眾看不到）")
        else:
            print("   => 🔴 按鈕文字從頭到尾沒變過")
        br.close()

run(0, None)
print()
run(600, None)
