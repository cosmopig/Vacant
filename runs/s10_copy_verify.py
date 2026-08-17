#!/usr/bin/env python3
"""S10b：驗**後果**——改完的那句話，在真的跑起來的頁面上長什麼樣。

第 115 輪。改文案很容易只驗前提（「檔案裡有新字串」），那證明不了觀眾看得到。
這一支把 `world/index.html` 真的跑起來，用 `?shot=layeron` 跳到那一拍，
再從 DOM 讀 `#act` 的文字。順帶收 console 的錯誤——這台沒有 node，
`main.js` 改完之後**能不能 parse** 只有瀏覽器答得出來。

判準（三個都要過）：
  V1  console 沒有任何 error（含 SyntaxError ⇒ 證明 main.js parse 得過）
  V2  `#act` 的文字**不含**舊句「它保證做過什麼會留下來」
  V3  `#act` 的文字**含**新句「留得住的也只有一部分」

同一套也驗首頁 `index.html` 的兩處（紅線 B 那句 ＋ 揭示那句）。

用法：python3 runs/s10_copy_verify.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
sys.path.insert(0, str(HOME / "vacant" / "vacant-docs-web" / "probe"))
import cdp  # noqa: E402

CHROME = HOME / ".local" / "bin" / "chrome-headless-shell"
HM_ROOT = HOME / "vacant" / "vacant_hm"
CFLAGS = ["--disable-gpu", "--no-sandbox", "--hide-scrollbars",
          "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
DBG_PORT = 9353
HTTP_PORT = 8753

OLD_C = "它保證做過什麼會留下來"
NEW_C = "留得住的也只有一部分"
OLD_B = "可不可信是不知道的"
NEW_B = "你沒辦法自己查證它做了什麼"


def grab(ch, url, sel, wait):
    ch.call("Runtime.evaluate", {"expression": "window.__errs = [];"})
    ch.call("Page.navigate", {"url": url})
    time.sleep(wait)
    res = ch.call("Runtime.evaluate", {
        "expression": f"JSON.stringify({{"
                      f"txt: (document.querySelector({json.dumps(sel)})||{{}}).textContent || '',"
                      f"body: document.body ? document.body.textContent.slice(0, 4000) : ''}})",
        "returnByValue": True})
    return json.loads(res["result"]["value"])


def main() -> int:
    srv = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(HTTP_PORT),
         "--bind", "127.0.0.1", "--directory", str(HM_ROOT)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ch = None
    fails = []
    try:
        time.sleep(1.2)
        ch = cdp.Chrome(str(CHROME), DBG_PORT, size=(1280, 800), extra_flags=CFLAGS)
        ch.call("Page.enable")
        ch.call("Runtime.enable")
        ch.call("Log.enable")

        # ── 大螢幕：world/?shot=layeron ──
        # `director.startAt` 是在第一次 `next()` 才被消化的（camera.js:190），
        # 而第一拍有 dur+hold ⇒ 6 秒讀到空字串不代表壞了，代表還沒輪到。
        # **等到它出現為止**，並且把沿路看到的每一拍都印出來（分辨「還沒到」與「沒有」）。
        # ⚠ `?sim=1` 不能省：`main.js:138` 的 `useSim` 沒開的話 `sim` 是 null，
        #   而 `setAct` 第一行就 `if (!sim) return` ⇒ `#act` 永遠是空字串。
        #   第一版漏了它，導演明明跑到 layeron 了（`__dbg().shot === 'layeron'`）
        #   卻讀到空字串——「還沒到」與「不會有」長得一模一樣。
        ch.call("Page.navigate",
                {"url": f"http://127.0.0.1:{HTTP_PORT}/world/?sim=1&shot=layeron"})
        seen, w = [], {"txt": "", "body": ""}
        for _ in range(80):                       # 最多等 80 秒
            time.sleep(1.0)
            r = ch.call("Runtime.evaluate", {
                "expression": "JSON.stringify({txt:(document.querySelector('#act')||{}).textContent||''})",
                "returnByValue": True})
            t = json.loads(r["result"]["value"])["txt"].strip()
            if t and (not seen or seen[-1] != t):
                seen.append(t)
            if NEW_C in t or OLD_C in t:
                w = {"txt": t, "body": t}
                break
        print("── world/?shot=layeron · 沿路看到的每一拍 ──")
        for s in seen:
            print("   · " + s.replace("\n", " ")[:110])
        errs = [e for e in ch.drain_events("Runtime.exceptionThrown")] if hasattr(ch, "drain_events") else []
        if OLD_C in w["txt"]:
            fails.append("V2 大螢幕：舊句還在")
        if NEW_C not in w["txt"]:
            fails.append(f"V3 大螢幕：新句沒出現（讀到 {w['txt'][:80]!r}）")

        # ── 首頁 index.html 兩處 ──
        h = grab(ch, f"http://127.0.0.1:{HTTP_PORT}/index.html", ".hero-lede", 3.0)
        print("\n── index.html · .hero-lede 文字 ──")
        print("   " + h["txt"].strip().replace("\n", " "))
        if OLD_B in h["body"]:
            fails.append("V4 首頁：紅線 B 舊句還在")
        if NEW_B not in h["body"]:
            fails.append("V5 首頁：紅線 B 新句沒出現")
        if OLD_C in h["body"]:
            fails.append("V6 首頁：紅線 C 舊句還在")
        if NEW_C not in h["body"]:
            fails.append("V7 首頁：紅線 C 新句沒出現")
        # 揭示段預設是 hidden 的，所以從 body 全文找；印出來給人看
        i = h["body"].find(NEW_C)
        print("── index.html · 揭示段 ──")
        print("   " + (h["body"][max(0, i - 60):i + 60].replace("\n", " ") if i >= 0 else "（找不到）"))

        # ── V1：console 錯誤 ──
        js_err = ch.call("Runtime.evaluate", {
            "expression": "(() => { try { return String(window.__loadError || ''); } catch(e) { return 'x'; } })()",
            "returnByValue": True})["result"].get("value", "")
        print(f"\nV1 console：exceptionThrown {len(errs)} 筆 · window.__loadError = {js_err!r}")
    finally:
        if ch:
            ch.close()
        srv.terminate()
        try:
            srv.wait(timeout=10)
        except Exception:
            srv.kill()

    print()
    if fails:
        for f in fails:
            print("FAIL " + f)
        return 1
    print("PASS 三處文案在真的跑起來的頁面上都是新的，舊句一個字都讀不到")
    return 0


if __name__ == "__main__":
    sys.exit(main())
