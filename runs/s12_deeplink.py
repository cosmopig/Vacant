#!/usr/bin/env python3
"""S12：`?shot=` 深連結的可見性——驗**畫面上有沒有字**，不驗 DOM 裡有沒有字。

第 117 輪。第 116 輪查到：`world/js/main.js` 的 `on` class 是 `openworld` 分支
（:170）加上去、之後一路留著的，`openreveal`(:181) 與 `layeron`(:199) 兩個分支
都只寫 `innerHTML`。正常播放沒事，但 `?shot=layeron` 深連結直接跳進去 ⇒
`#act` 有文字、`.act{opacity:0}` ⇒ **畫面上一個字都看不到**，而 DOM 說一切正常。
`?shot=` 是展場布展調機與現場備援的路徑，所以這是會被人用到的狀態。

這一支做四件事，每一件都是「後果」不是「前提」：

  D0/D1  深連結進 `openreveal` 與 `layeron`：`#act.on` 與 computed opacity
  D2     深連結進 layeron 之後，在**展場距離**（縮到 1/3）量 `#act .sub` 帶高
  D3     自然路徑（`?shot=openworld` 走到 layeron）同一格帶高——兩條路要一樣
  P1a/b  探針自驗：正控制（自然路徑，一定可見）＋負控制（CDP 拔掉 `.on`，
         一定不可見）。兩格都答對才准讀上面任何一個數字。

帶高量具整份借 `s11_legibility.py`（同一份 read_png/shrink/bands_and_contrast），
不另寫第二份——兩份會漂移。

用法：
  python3 runs/s12_deeplink.py              # 自驗 ＋ D0/D1 ＋ D2/D3
  python3 runs/s12_deeplink.py --selftest   # 只跑 P1a/P1b
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
RUNS_ROOT = HOME / "vacant" / "Vacant" / "runs"
sys.path.insert(0, str(RUNS_ROOT))
sys.path.insert(0, str(HOME / "vacant" / "vacant-docs-web" / "probe"))
sys.path.insert(0, str(HOME / "vacant" / "vacant_hm" / "styles" / "probe"))
import cdp                                                    # noqa: E402
import s11_legibility as S11                                  # noqa: E402

CHROME = HOME / ".local" / "bin" / "chrome-headless-shell"
HM_ROOT = HOME / "vacant" / "vacant_hm"
CFLAGS = ["--disable-gpu", "--no-sandbox", "--hide-scrollbars",
          "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
DBG_PORT = 9371
HM_PORT = 8771

OUT = RUNS_ROOT / "s12_shots"
NEW_C = S11.NEW_C                     # 「留得住的也只有一部分」
EXPECT_BAND = 7.0                     # 第 116 輪自然路徑量到的 `#act .sub` 帶高
BAND_TOL = 0.0                        # 字級顏色都沒動 ⇒ 容差 0


def vis(ch):
    """探針本體：一次回報拍名、on class、computed opacity、可見高度、文字。

    **opacity 讀的是 computed style，不是 class**——class 只是前提，
    `.act{opacity:0}` 才是觀眾看不到的那個原因。
    """
    return json.loads(S11.js(ch, """JSON.stringify((() => {
      const e = document.getElementById('act');
      if (!e) return {shot:'', on:false, opacity:null, h:0, txt:'', exists:false};
      const cs = getComputedStyle(e), r = e.getBoundingClientRect();
      return {shot: (window.__dbg ? window.__dbg().shot : ''),
              on: e.classList.contains('on'),
              opacity: parseFloat(cs.opacity),
              vis: cs.visibility, disp: cs.display,
              h: Math.round(r.height), w: Math.round(r.width),
              txt: (e.textContent||'').trim(), exists:true};
    })())"""))


def visible(s):
    """判準：畫面上讀得到 = opacity ≥ 0.9 且沒被 hidden/none 且有高度。"""
    return (s["exists"] and s["opacity"] is not None and s["opacity"] >= 0.9
            and s["vis"] != "hidden" and s["disp"] != "none" and s["h"] > 4)


def goto(ch, url, want_shot, timeout=180, need_on=False):
    """導到 url，等導演走到 want_shot。回傳沿路 trail 與最後狀態。

    等的條件刻意**不含**可見性（除非 need_on）——不然「還沒到」與「隱形」
    會長得一模一樣，而那正是第 115 輪踩過的坑。
    """
    ch.call("Page.navigate", {"url": url})
    t0, trail, last = time.time(), [], None
    while time.time() - t0 < timeout:
        time.sleep(0.4)
        s = vis(ch)
        last = s
        key = (s["shot"], s["on"], s["opacity"])
        if not trail or trail[-1][:3] != key:
            trail.append((s["shot"], s["on"], s["opacity"], round(time.time() - t0, 1)))
        if s["shot"] == want_shot and (s["on"] or not need_on) and s["txt"]:
            if need_on and not visible(s):
                continue
            break
    # `.act` 的 opacity 是漸入的（自驗實測 0.026 → 0.67 → 0.97 花了 1.3 秒）。
    # 一到就讀會讀到淡入中途的值 ⇒ 把「在淡入」誤判成「隱形」。等 2.5 秒再讀一次。
    time.sleep(2.5)
    last = vis(ch)
    trail.append((last["shot"], last["on"], last["opacity"], round(time.time() - t0, 1)))
    return last, trail


def show_trail(trail):
    print("  沿路：" + " → ".join(
        f"{n or '?'}{'(on)' if o else '(off)'}op={op}@{t}s" for n, o, op, t in trail))


def band_of(ch, sel, tag):
    """借 s11 的量具在展場距離量帶高。回傳 s11 的量測 dict。"""
    S11.OUT = OUT                      # 截圖落在 s12_shots，不覆蓋 s11 的證據
    OUT.mkdir(parents=True, exist_ok=True)
    return S11.measure(ch, sel, tag, settle=0.3)


def selftest(ch, fails):
    """P1a 正控制 ＋ P1b 負控制。探針有沒有能力說「不」，先驗。"""
    print("── 探針自驗 P1a/P1b（不過就不准讀主量測）──")
    last, trail = goto(ch, f"http://127.0.0.1:{HM_PORT}/world/?sim=1&shot=openworld",
                       "openworld", timeout=60, need_on=True)
    show_trail(trail)
    if visible(last):
        print(f"  P1a 正控制（自然路徑 openworld）PASS 探針答『可見』"
              f" on={last['on']} opacity={last['opacity']} h={last['h']}")
    else:
        fails.append(f"P1a 正控制：自然路徑應可見，探針卻答不可見 {last}")

    S11.js(ch, "document.getElementById('act').classList.remove('on')")
    time.sleep(0.6)
    neg = vis(ch)
    if not visible(neg):
        print(f"  P1b 負控制（CDP 拔掉 .on）PASS 探針答『不可見』"
              f" on={neg['on']} opacity={neg['opacity']}")
    else:
        fails.append(f"P1b 負控制：拔掉 .on 後應不可見，探針卻答可見 {neg}")
    return {"P1a": last, "P1b": neg}


def repeat_mode(ch, n=4):
    """事後追加（**不是判準的一部分**）：量具在這一格的重複性有多少。

    第 117 輪 `D2`(深連結 6.0) vs `D3`(自然路徑 7.0) 差 1.0 px，而事前訂的容差是 0。
    差 1 px 有兩種可能：兩條路真的不一樣，或者這個量具在這一格本來就有 ±1 的抖動。
    **分不出來就不准挑一個講。** 所以同一條路各量 n 次：
    如果路內抖動本來就有 1 px，那 `D2≠D3` 證明不了兩條路不同（但判準仍記 FAIL——
    事後放寬判準等於沒有判準；要改的是下一輪的容差，不是這一輪的結論）。

    `layeron` 的 `sim.paused = false` ⇒ 背景一直在動，每次量都是不同影格，
    這正是抖動的主要來源，所以重複量測不重新導頁也量得到它。
    """
    out = {}
    for label, url, want, need_on in (
            ("deeplink", f"http://127.0.0.1:{HM_PORT}/world/?sim=1&shot=layeron", "layeron", True),
            ("natural", f"http://127.0.0.1:{HM_PORT}/world/?sim=1&shot=openworld", "layeron", True)):
        vals, voids = [], 0
        for i in range(n):
            # **每一次都重新導頁。** 第一版在同一頁連量 4 次，第 3、4 次讀到 0.0——
            # 不是抖動，是 `layeron` 只有 dur 4 + hold 9（camera.js:84），量到第三次
            # 導演已經走到下一拍了。「量具在抖」與「量錯對象」長得一模一樣，
            # 所以每次重導 ＋ 量前量後都確認還在 layeron 且可見，不然這一格記 VOID。
            last, _ = goto(ch, url, want, timeout=180, need_on=True)
            if not visible(last):
                voids += 1
                continue
            time.sleep(3.0)
            before = vis(ch)
            m = band_of(ch, "#act .sub", f"R_{label}_{i}")
            after = vis(ch)
            if (before["shot"] != "layeron" or after["shot"] != "layeron"
                    or not visible(after) or "error" in m):
                voids += 1
                continue
            vals.append(m["band_h"])
        out[label] = {"band_h": vals, "void": voids}
        print(f"  {label:<9} 帶高 {vals}  (VOID {voids})")
    return out


def main() -> int:
    only_self = "--selftest" in sys.argv
    only_rep = "--repeat" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    srv = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(HM_PORT),
         "--bind", "127.0.0.1", "--directory", str(HM_ROOT)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ch, fails, rep = None, [], {}
    try:
        time.sleep(1.5)
        ch = cdp.Chrome(str(CHROME), DBG_PORT, size=(S11.VW, S11.VH), extra_flags=CFLAGS)
        ch.call("Page.enable")
        ch.call("Runtime.enable")
        rep["selftest"] = selftest(ch, fails)
        if fails:
            print("\n探針沒過自驗 ⇒ **不讀主量測任何數字**")
            for f in fails:
                print("  FAIL " + f)
            return 2
        if only_self:
            print("\nPASS 探針兩格自驗都過（--selftest，未跑主量測）")
            return 0
        if only_rep:
            print("\n── 重複性（事後追加，不是判準）──")
            rep["repeat"] = repeat_mode(ch)
            (RUNS_ROOT / "s12_repeat.json").write_text(
                json.dumps(rep["repeat"], ensure_ascii=False, indent=1), encoding="utf-8")
            return 0

        # ── D0/D1 深連結兩拍 ──
        for shot_name in ("openreveal", "layeron"):
            print(f"\n── 深連結 ?sim=1&shot={shot_name} ──")
            last, trail = goto(ch, f"http://127.0.0.1:{HM_PORT}/world/?sim=1&shot={shot_name}",
                               shot_name, timeout=120)
            show_trail(trail)
            v = visible(last)
            rep[shot_name] = {"on": last["on"], "opacity": last["opacity"],
                              "h": last["h"], "visible": v,
                              "txt_len": len(last["txt"]), "txt": last["txt"][:120]}
            print(f"  on={last['on']}  opacity={last['opacity']}  高度={last['h']}px"
                  f"  文字 {len(last['txt'])} 字  ⇒ 畫面上{'讀得到' if v else '**一個字都看不到**'}")
            if shot_name == "layeron":
                rep[shot_name]["has_new_c"] = NEW_C in last["txt"]
                # D2：畫面上有沒有那麼多墨，才是後果
                if v:
                    time.sleep(3.0)          # 等運鏡停，背景靜下來
                    m = band_of(ch, "#act .sub", "D2_deeplink_sub")
                    rep["D2"] = m
                    print("  D2 展場距離帶高 " + S11.line(m).strip())
                else:
                    rep["D2"] = {"skipped": "深連結隱形 ⇒ 沒有墨可量（這本身就是結果）"}
                    print("  D2 跳過：畫面上沒有字，量帶高沒有意義")

        # ── D3 自然路徑同一格 ──
        print("\n── D3 自然路徑 ?sim=1&shot=openworld → 走到 layeron ──")
        last, trail = goto(ch, f"http://127.0.0.1:{HM_PORT}/world/?sim=1&shot=openworld",
                           "layeron", timeout=180, need_on=True)
        show_trail(trail)
        if visible(last) and NEW_C in last["txt"]:
            time.sleep(3.0)
            m = band_of(ch, "#act .sub", "D3_natural_sub")
            rep["D3"] = m
            print("  D3 展場距離帶高 " + S11.line(m).strip())
        else:
            rep["D3"] = {"error": f"沒走到可見的 layeron: on={last['on']} op={last['opacity']}"}
            print("  D3 ERROR " + rep["D3"]["error"])
    finally:
        if ch:
            ch.close()
        srv.terminate()
        try:
            srv.wait(timeout=10)
        except Exception:
            srv.kill()

    # ── 判準對帳 ──
    print("\n── 判準 ──")
    ok = True
    for tag, key in (("D1 layeron 深連結可見", "layeron"),
                     ("D1 openreveal 深連結可見", "openreveal")):
        got = rep.get(key, {}).get("visible")
        print(f"  {tag:<26} {'PASS' if got else 'FAIL'}  (visible={got})")
        ok = ok and bool(got)
    d2, d3 = rep.get("D2", {}), rep.get("D3", {})
    b2, b3 = d2.get("band_h"), d3.get("band_h")
    if b2 is not None and b3 is not None:
        same = abs(b2 - b3) <= BAND_TOL
        exp = abs(b3 - EXPECT_BAND) <= BAND_TOL
        print(f"  {'D2==D3 兩條路帶高相同':<26} {'PASS' if same else 'FAIL'}  {b2} vs {b3}")
        print(f"  {'D3==第116輪基線 7.0':<26} {'PASS' if exp else 'FAIL'}  {b3}")
        ok = ok and same and exp
    else:
        print(f"  D2/D3 帶高          量不到（D2={b2} D3={b3}）⇒ FAIL")
        ok = False

    (RUNS_ROOT / "s12_report.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n落盤：{RUNS_ROOT / 's12_report.json'} · 截圖 {OUT}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
