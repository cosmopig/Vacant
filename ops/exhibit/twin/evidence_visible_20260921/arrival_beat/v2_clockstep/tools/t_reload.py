#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""量具自己的負控制／正控制：**先證明舊的 reload 攔截從頭到尾是個空操作。**

`S03_negctl_arrive0` 與 `S05_before_triple` 兩次都死在
`Execution context was destroyed, most likely because of a navigation`，
而 `strip.py` 裡明明有一段 `BLOCK_RELOAD`。在說「換一種攔法」之前先證明
舊那一種真的沒攔到——不然改完不知道是修好了還是運氣好。

三臂，跑在**真的 HTTP 頁面**上（`wd/wd.html` 是 `index.html:4283-4292`
看門狗那一段的逐字複製，只把 `lastFrameTs` 預設成「已經凍了 99 秒」
⇒ 下一槍一定要開）。判準是 `sessionStorage.wd_loads`：這一份文件被載入
第幾次。1 ＝沒被重載走，≥2 ＝被重載走了。

  正控制  什麼都不裝      ⇒ 必須 wd_loads ≥ 2（量具量得動）
  舊招    BLOCK_RELOAD    ⇒ 預期 wd_loads ≥ 2（攔不住）＋ 明確的 TypeError
  新招    blockwatchdog   ⇒ 必須 wd_loads == 1

第四臂另外跑 `wdfreeze.html`（真的卡住主執行緒 12 秒）：替身的 `__maxFrameGapMs`
必須量到那 12 秒。**沒有這一臂，`__maxFrameGapMs` 在真跑裡回 0 就分不出
「沒凍過」跟「計數器是死的」。**

⚠ 第一版這一支用 `page.set_content()`，結果 `add_init_script` 根本沒跑到
  （about:blank 上 `set_content` 不算一次導覽），量出「新招 stillSameDocument
  ＝true」那個綠燈是假的——它為真只是因為 about:blank 重載回 about:blank。
  改成真 URL 才量得準。**這就是〈判成 0 之前先證明量得動〉那條。**
"""
import json, os
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
URL = "http://127.0.0.1:8623/wd.html"
FREEZE_URL = "http://127.0.0.1:8623/wdfreeze.html"

OLD = """
window.__reloadBlocked = 0;
(function(){
  try {
    const orig = location.reload;
    Object.defineProperty(location, 'reload', {
      configurable: true,
      value: function(){ window.__reloadBlocked = (window.__reloadBlocked||0) + 1; }
    });
  } catch (e) { window.__reloadBlockFailed = String(e).slice(0, 120); }
})();
"""
NEW = open(os.path.join(HERE, "blockwatchdog.js"), encoding="utf-8").read()

PROBE = """() => ({
  loads: window.__loads === undefined ? null : window.__loads,
  vwReloads: parseInt(sessionStorage.getItem('vw_reloads') || '0'),
  watchdogArmed: window.__watchdogArmed === undefined ? null : window.__watchdogArmed,
  watchdogWouldFire: window.__watchdogWouldFire === undefined ? null : window.__watchdogWouldFire,
  otherIntervals: window.__otherIntervals === undefined ? null : window.__otherIntervals,
  maxFrameGapMs: window.__maxFrameGapMs === undefined ? null : window.__maxFrameGapMs,
  reloadBlocked: window.__reloadBlocked === undefined ? null : window.__reloadBlocked,
  reloadBlockFailed: window.__reloadBlockFailed || null,
  reloadDescConfigurable: (Object.getOwnPropertyDescriptor(location, 'reload') || {}).configurable,
})"""

RESULT = {}
with sync_playwright() as p:
    br = p.chromium.launch(args=["--mute-audio"])
    for name, init in (("posctl_none", None), ("old_BLOCK_RELOAD", OLD), ("new_blockwatchdog", NEW)):
        ctx = br.new_context()          # 每一臂自己的 sessionStorage
        pg = ctx.new_page()
        if init:
            pg.add_init_script(init)
        pg.goto(URL, wait_until="load")
        pg.wait_for_timeout(13000)      # 5 秒的 interval 至少開兩槍
        try:
            RESULT[name] = pg.evaluate(PROBE)
        except Exception as e:
            RESULT[name] = {"evaluateFailed": str(e)[:120]}
        ctx.close()

    # ── 第四臂：替身的「凍了多久」計數器本身量不量得動 ──────────────
    ctx = br.new_context()
    pg = ctx.new_page()
    pg.add_init_script(NEW)
    pg.goto(FREEZE_URL, wait_until="load")
    pg.wait_for_timeout(20000)          # 1.5 秒後凍 12 秒，等它解凍再問
    RESULT["instrument_freeze12s"] = pg.evaluate(PROBE)
    ctx.close()
    br.close()

for k, v in RESULT.items():
    print(k.ljust(20), json.dumps(v, ensure_ascii=False))

pos = RESULT["posctl_none"]
old = RESULT["old_BLOCK_RELOAD"]
new = RESULT["new_blockwatchdog"]
verdict = {
    "正控制量得動（沒攔就真的被重載走）": (pos.get("loads") or 0) >= 2 or "evaluateFailed" in pos,
    "舊招攔不住（所以 S03／S05 才會死）": (old.get("loads") or 0) >= 2 or "evaluateFailed" in old,
    "舊招失敗原因是 Location 不可設定": old.get("reloadDescConfigurable") is False
                                        and bool(old.get("reloadBlockFailed")),
    "新招擋得住（同一份文件沒被重載）": new.get("loads") == 1,
    "新招只換掉看門狗那一支": new.get("watchdogArmed") == 1,
    # 凍 12 秒 ⇒ 計數器要量到 10 秒以上。量不到就代表它是死的，
    # 真跑裡的 0 也就沒有意義（那才是「量具說謊」）。
    "掉幀計數器量得動（凍 12 秒要看得到）":
        (RESULT["instrument_freeze12s"].get("maxFrameGapMs") or 0) >= 10000,
}
print()
for k, v in verdict.items():
    print(("  PASS  " if v else "  FAIL  ") + k)
with open(os.path.join(HERE, "out", "t_reload.json"), "w", encoding="utf-8") as fh:
    json.dump({"arms": RESULT, "verdict": verdict}, fh, ensure_ascii=False, indent=1)
print("\nALL", "PASS" if all(verdict.values()) else "FAIL")
