#!/usr/bin/env python3
"""S11：**展場距離下，宣稱句與限定句誰讀得到。**

第 116 輪。第 115 輪把兩句誠實邊界的文案改長了（25 字 → 34 字），
但那一輪自己在結尾寫下：「本輪沒有任何像素驗收，上面沒有一個數字來自截圖。」
這一支就是還那筆帳。

**它在架構裡承重什麼**：三條誠實邊界（不准說信任、真實與模擬分開標、
不准說保證）全部寫在 `.wall-sub` / `.bound` / `.act .sub` 這些**最小號的字**裡，
而宣稱寫在 `.wall` / `.act .big` 這些**最大號的字**裡。如果限定句在展場距離
讀不到而宣稱讀得到，觀眾實際接收到的就只有宣稱——**這等於在畫面上違反鐵律 5，
而且不需要任何人寫錯一個字。**所以「限定句的字高」是一個可究責性的量，
不是排版偏好。

## 量法：雙拍相減

背景是會動的（world 是即時 3D、首頁有 radial-gradient ＋ 活體模擬），
所以「哪些像素是字」不能用亮度門檻猜。改成問一個後果問題：
**把這個元素藏起來，畫面上哪些像素變了？**變了的就是這行字的墨跡。

  S1  元素可見
  S2  `visibility:hidden`（只藏這一個元素，版面不動）
  S3  元素又可見          ← 用來量**背景自己在動多少**（雜訊底）

  訊號 = |L(S1) − L(S2)| ；雜訊 = |L(S1) − L(S3)|
  墨跡門檻 T = max(10, p99.5(雜訊))；若 p99.5(雜訊) > 40 ⇒ 該格判 VOID，
  **不報數字**。景動得比字還兇的時候，任何數字都是雜訊。

三張都先縮到 640 寬（`shrink.py` 的 `box_shrink`，1/3 ＝ 展場距離慣例）再相減。

## 判準（`STATE.md` 第 116 輪【事前】，一條沒放寬）

  C1  640 縮圖上單行墨跡帶高 ≥ 12 px
  C2  |mean(ΔL) over 墨跡像素| / 255 ≥ 0.25
  C3  落差比 ＝ 宣稱字高 / 限定字高 ≤ 1.5
  C4  `#act` 文字實際留在畫面上的秒數 ÷ 字數 ≥ 0.25 秒/字

## 探針自己要先過的五格（不過就 exit 2，不准讀任何主量測數字）

  P0a 幾何比例：同一控制塊 1920 圖與 640 圖的帶高比 = 3.00 ± 0.25
  P0b 正控制 48px 高對比 ⇒ C1 PASS
  P0c 負控制 21px 高對比 ⇒ C1 FAIL
  P0d 對比負控制 48px 低對比 ⇒ C1 PASS 且 C2 FAIL
  P0e 先裁後縮 == 先縮後裁，**逐像素相同**（裁切對齊 k 的倍數才成立；
      這是為了跑得動而抄的近路，近路要自己驗）

PNG 解碼與縮圖都借既有那一份，不另寫第二份（HANDOFF §8）。

用法：
  python3 runs/s11_legibility.py            # 自驗 ＋ 主量測
  python3 runs/s11_legibility.py --selftest # 只跑五格自驗
"""
from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
sys.path.insert(0, str(HOME / "vacant" / "vacant-docs-web" / "probe"))
sys.path.insert(0, str(HOME / "vacant" / "vacant_hm" / "styles" / "probe"))
import cdp                                          # noqa: E402
from measure_silhouette import read_png             # noqa: E402
from shrink import box_shrink                       # noqa: E402

CHROME = HOME / ".local" / "bin" / "chrome-headless-shell"
HM_ROOT = HOME / "vacant" / "vacant_hm"
RUNS_ROOT = HOME / "vacant" / "Vacant" / "runs"
OUT = RUNS_ROOT / "s11_shots"
CFLAGS = ["--disable-gpu", "--no-sandbox", "--hide-scrollbars",
          "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
DBG_PORT = 9361
HM_PORT = 8761
CTL_PORT = 8762

VW, VH = 1920, 1080
K = 3                       # 展場距離：縮到 1/3
MIN_H = 12.0                # C1
MIN_CONTRAST = 0.25         # C2
MAX_RATIO = 1.5             # C3
MIN_SEC_PER_CHAR = 0.25     # C4
INK_T_FLOOR = 10            # 墨跡門檻下限
NOISE_VOID = 40             # 雜訊底超過這個值 ⇒ 該格 VOID
MIN_ROW_INK = 3             # 一列至少幾個墨跡像素才算「這一列有字」
NEW_C = "留得住的也只有一部分"   # 第 115 輪那句限定語，用來確認量到的是它


# ── 影像小工具（都建立在借來的 read_png / box_shrink 上）────────────
def lum(r, g, b):
    return (r * 299 + g * 587 + b * 114) // 1000


def crop_raw(w, h, nch, buf, x0, y0, cw, ch):
    """從 read_png 的原始緩衝裁一塊出來，回傳同樣的 (w,h,nch,buf) 四元組。"""
    out = bytearray()
    for y in range(y0, y0 + ch):
        base = (y * w + x0) * nch
        out += buf[base:base + cw * nch]
    return cw, ch, nch, bytes(out)


def shrunk_lum(w, h, nch, buf, k=K):
    """裁好的一塊 → 縮 1/k → 每列的亮度陣列。回傳 (W, H, rows)。"""
    W, H, raw = box_shrink(w, h, nch, buf, k)
    rows, stride = [], 1 + W * 3          # box_shrink 每列開頭有一個 filter 0
    for Y in range(H):
        b = Y * stride + 1
        rows.append([lum(raw[b + X * 3], raw[b + X * 3 + 1], raw[b + X * 3 + 2])
                     for X in range(W)])
    return W, H, rows


def full_lum(w, h, nch, buf):
    return [[lum(buf[(y * w + x) * nch], buf[(y * w + x) * nch + 1],
                 buf[(y * w + x) * nch + 2]) for x in range(w)] for y in range(h)]


def align(rect):
    """把 CSS rect 對齊到 k 的倍數並夾進 viewport；先裁後縮才會等於先縮後裁。"""
    x0 = max(0, (int(rect["x"]) // K) * K)
    y0 = max(0, (int(rect["y"]) // K) * K)
    x1 = min(VW, -(-int(rect["x"] + rect["w"]) // K) * K)
    y1 = min(VH, -(-int(rect["y"] + rect["h"]) // K) * K)
    return x0, y0, max(K, x1 - x0), max(K, y1 - y0)


def pctl(vals, p):
    if not vals:
        return 0.0
    s = sorted(vals)
    i = min(len(s) - 1, int(round(p * (len(s) - 1))))
    return float(s[i])


def bands_and_contrast(sig, noise, min_row_ink=MIN_ROW_INK):
    """sig/noise：兩張同尺寸的 |ΔL| 矩陣。回傳墨跡帶、帶高、對比、雜訊底。"""
    flat_n = [v for row in noise for v in row]
    floor = pctl(flat_n, 0.995)
    T = max(INK_T_FLOOR, floor)
    counts, ink_vals = [], []
    for row in sig:
        c = 0
        for v in row:
            if v > T:
                c += 1
                ink_vals.append(v)
        counts.append(c)
    bands, start = [], None
    for y, c in enumerate(counts):
        if c >= min_row_ink and start is None:
            start = y
        elif c < min_row_ink and start is not None:
            bands.append((start, y - 1))
            start = None
    if start is not None:
        bands.append((start, len(counts) - 1))
    heights = [b[1] - b[0] + 1 for b in bands if b[1] - b[0] + 1 >= 2]
    return {
        "noise_floor": round(floor, 1),
        "ink_T": round(T, 1),
        "n_bands": len(heights),
        "band_heights": heights,
        "band_h": round(statistics.median(heights), 1) if heights else 0.0,
        "n_ink_px": len(ink_vals),
        "contrast": round(statistics.fmean(ink_vals) / 255.0, 3) if ink_vals else 0.0,
        "contrast_p90": round(pctl(ink_vals, 0.90) / 255.0, 3),
        "void": floor > NOISE_VOID,
    }


# ── 瀏覽器側 ────────────────────────────────────────────────────────
def js(ch, expr):
    r = ch.call("Runtime.evaluate", {"expression": expr, "returnByValue": True})
    return r["result"].get("value")


def shot(ch, path):
    data = ch.call("Page.captureScreenshot", {"format": "png"})["data"]
    import base64
    path.write_bytes(base64.b64decode(data))
    return path


def rect_of(ch, sel):
    return json.loads(js(ch, f"""(() => {{
      const e = document.querySelector({json.dumps(sel)});
      if (!e) return 'null';
      const r = e.getBoundingClientRect();
      const cs = getComputedStyle(e);
      return JSON.stringify({{x:r.left, y:r.top, w:r.width, h:r.height,
        fs: parseFloat(cs.fontSize), lh: cs.lineHeight, color: cs.color,
        chars: (e.textContent||'').replace(/\\s/g,'').length}});
    }})()"""))


def measure(ch, sel, tag, settle=0.9):
    """雙拍相減量一個元素。回傳量測 dict（含 rect 與判準結果）。"""
    r = rect_of(ch, sel)
    if r is None:
        return {"tag": tag, "sel": sel, "error": "元素不存在"}
    if r["w"] < 4 or r["h"] < 4:
        return {"tag": tag, "sel": sel, "error": f"rect 太小 {r['w']}×{r['h']}"}
    if r["y"] + r["h"] <= 0 or r["y"] >= VH:
        return {"tag": tag, "sel": sel, "error": f"不在 viewport 內 y={r['y']:.0f}"}
    x0, y0, cw, chh = align(r)

    OUT.mkdir(parents=True, exist_ok=True)
    hide = f"document.querySelector({json.dumps(sel)}).style.visibility="
    s1 = shot(ch, OUT / f"{tag}_s1.png")
    js(ch, hide + "'hidden'")
    time.sleep(settle)
    s2 = shot(ch, OUT / f"{tag}_s2.png")
    js(ch, hide + "''")
    time.sleep(settle)
    s3 = shot(ch, OUT / f"{tag}_s3.png")

    grids = []
    for p in (s1, s2, s3):
        w, h, nch, buf = read_png(p)
        W, H, rows = shrunk_lum(*crop_raw(w, h, nch, buf, x0, y0, cw, chh))
        grids.append(rows)
    g1, g2, g3 = grids
    sig = [[abs(a - b) for a, b in zip(r1, r2)] for r1, r2 in zip(g1, g2)]
    noi = [[abs(a - b) for a, b in zip(r1, r3)] for r1, r3 in zip(g1, g3)]
    m = bands_and_contrast(sig, noi)
    m.update({"tag": tag, "sel": sel, "font_px": r["fs"], "chars": r["chars"],
              "rect": [round(r["x"]), round(r["y"]), round(r["w"]), round(r["h"])],
              "crop": [x0, y0, cw, chh], "color": r["color"]})
    m["C1"] = (not m["void"]) and m["band_h"] >= MIN_H
    m["C2"] = (not m["void"]) and m["contrast"] >= MIN_CONTRAST
    return m


def line(m):
    if "error" in m:
        return f"  {m['tag']:<20} ERROR {m['error']}"
    v = " VOID(景在動)" if m["void"] else ""
    return (f"  {m['tag']:<20} 字級@1920 {m['font_px']:>5.1f}px · 縮圖帶高 "
            f"{m['band_h']:>5.1f}px {'PASS' if m['C1'] else 'FAIL'} · 對比 "
            f"{m['contrast']:.3f} {'PASS' if m['C2'] else 'FAIL'} · "
            f"帶 {m['n_bands']} · 雜訊底 {m['noise_floor']:.0f} · {m['chars']} 字{v}")


# ── 五格自驗 ────────────────────────────────────────────────────────
def selftest(ch, fails):
    print("── P0 量具自驗（已知答案）──")
    ch.call("Page.navigate", {"url": f"http://127.0.0.1:{CTL_PORT}/s11_ctl.html"})
    time.sleep(2.5)
    ctl = {t: measure(ch, f"#ctl-{t}", f"ctl_{t}", settle=0.35)
           for t in ("big", "small", "lowc")}
    for t in ("big", "small", "lowc"):
        print(line(ctl[t]))

    # P0a 幾何比例：同一控制塊在 1920 原圖上的帶高 ÷ 640 縮圖上的帶高
    b = ctl["big"]
    w, h, nch, buf = read_png(OUT / "ctl_big_s1.png")
    x0, y0, cw, chh = b["crop"]
    cw_, ch_, nch_, cbuf = crop_raw(w, h, nch, buf, x0, y0, cw, chh)
    w2, h2, nch2, buf2 = read_png(OUT / "ctl_big_s2.png")
    _, _, _, cbuf2 = crop_raw(w2, h2, nch2, buf2, x0, y0, cw, chh)
    f1, f2 = full_lum(cw_, ch_, nch_, cbuf), full_lum(cw_, ch_, nch_, cbuf2)
    sig = [[abs(a - c) for a, c in zip(r1, r2)] for r1, r2 in zip(f1, f2)]
    zero = [[0] * cw_ for _ in range(ch_)]
    fullm = bands_and_contrast(sig, zero, min_row_ink=MIN_ROW_INK * K)
    ratio = fullm["band_h"] / b["band_h"] if b["band_h"] else 0.0
    ok_a = abs(ratio - 3.0) <= 0.25
    print(f"  P0a 幾何比例  原圖帶高 {fullm['band_h']:.1f}px ÷ 縮圖 {b['band_h']:.1f}px "
          f"= {ratio:.2f}（要 3.00±0.25）{'PASS' if ok_a else 'FAIL'}")
    if not ok_a:
        fails.append(f"P0a 幾何比例 {ratio:.2f} 不在 3.00±0.25")

    # P0e 先裁後縮 == 先縮後裁（逐像素）
    _, _, ffull = shrunk_lum(w, h, nch, buf)
    _, _, fcrop = shrunk_lum(cw_, ch_, nch_, cbuf)
    diff = sum(1 for yy in range(len(fcrop))
               for xx in range(len(fcrop[0]))
               if fcrop[yy][xx] != ffull[y0 // K + yy][x0 // K + xx])
    ok_e = diff == 0
    print(f"  P0e 裁縮可交換  不同像素 {diff} 個（要 0）{'PASS' if ok_e else 'FAIL'}")
    if not ok_e:
        fails.append(f"P0e 先裁後縮與先縮後裁差 {diff} 個像素 ⇒ 裁切座標映射壞了")

    for code, tag, want in (("P0b", "big", (True, True)),
                            ("P0c", "small", (False, None)),
                            ("P0d", "lowc", (True, False))):
        m = ctl[tag]
        want_c1, want_c2 = want
        bad = []
        if m.get("C1") is not want_c1:
            bad.append(f"C1 應為 {want_c1} 實為 {m.get('C1')}（帶高 {m.get('band_h')}）")
        if want_c2 is not None and m.get("C2") is not want_c2:
            bad.append(f"C2 應為 {want_c2} 實為 {m.get('C2')}（對比 {m.get('contrast')}）")
        print(f"  {code} {tag:<6} {'PASS' if not bad else 'FAIL ' + '；'.join(bad)}")
        if bad:
            fails.append(f"{code} {tag}：" + "；".join(bad))
    return ctl


# ── 主量測 ──────────────────────────────────────────────────────────
def act_state(ch):
    return json.loads(js(ch, """JSON.stringify({
      shot: (window.__dbg ? window.__dbg().shot : ''),
      on: !!document.querySelector('#act.on'),
      txt: ((document.querySelector('#act')||{}).textContent||'').trim()})"""))


def measure_world(ch, results):
    print("\n── T1/T2 · world/?sim=1&shot=openworld → 自然走到 layeron（大螢幕）──")
    # ⚠ **不能用 `?shot=layeron` 深連結。** `main.js:199` 的 layeron 分支只寫
    #   `innerHTML`，沒有 `classList.add('on')`；`on` 是 `openworld` 分支
    #   （`main.js:170`）加上去、之後一路留著的。直接跳進 layeron ⇒ 字在 DOM 裡
    #   但 `.act{opacity:0}` ⇒ **畫面上一個字都看不到**。第 115 輪的 V2/V3 只讀
    #   textContent，讀得到，所以完全沒發現。這一支改成從 `openworld` 進、
    #   讓導演自己走到 layeron（camera.js:82-84 的順序），走的是觀眾那條路。
    ch.call("Page.navigate",
            {"url": f"http://127.0.0.1:{HM_PORT}/world/?sim=1&shot=openworld"})
    # `?sim=1` 不能省：`main.js:138` 的 `useSim` 沒開 ⇒ `sim` 是 null ⇒
    # `setAct` 第一行就 return ⇒ `#act` 永遠空字串（第 115 輪踩過）。
    t0, on_at, seen, trail = time.time(), None, "", []
    while time.time() - t0 < 180:
        time.sleep(0.4)
        s = act_state(ch)
        if not trail or trail[-1][0] != s["shot"] or trail[-1][1] != s["on"]:
            trail.append((s["shot"], s["on"], round(time.time() - t0, 1)))
        if s["shot"] == "layeron" and s["on"] and NEW_C in s["txt"]:
            on_at, seen = time.time(), s["txt"]
            break
    print("  沿路的拍／可見狀態：" + " → ".join(
        f"{n}{'(可見)' if o else '(隱形)'}@{t}s" for n, o, t in trail))
    if on_at is None:
        results.append({"tag": "T1", "error": "等 180 秒沒等到 layeron 且可見"})
        return None
    # camera.js:84 layeron 是 dur 4 + hold 9。等過運鏡段再量，背景才靜得下來；
    # 這只是挑量測時機，不動被量的對象（字級與顏色整段不變）。
    time.sleep(4.5)
    for sel, tag in (("#act .sub", "T1_world_sub"), ("#act .big", "T2_world_big")):
        before = act_state(ch)
        m = measure(ch, sel, tag, settle=0.3)
        after = act_state(ch)
        if before["shot"] != "layeron" or after["shot"] != "layeron" or not after["on"]:
            m = {"tag": tag, "sel": sel,
                 "error": f"量測中途換拍 {before['shot']}→{after['shot']} on={after['on']}"}
        results.append(m)
        print(line(m))
    off_at = time.time()
    while time.time() - t0 < 240:                # 等它自己走掉，拿完整停留秒數
        time.sleep(0.4)
        s = act_state(ch)
        if s["shot"] != "layeron" or not s["on"]:
            break
        off_at = time.time()
    return {"dwell_s": round(off_at - on_at, 1), "text": seen,
            "trail": trail}


def measure_index(ch, results):
    print("\n── T3/T4/T5 · index.html?scene=1 → 等揭示自己出現 ──")
    # ⚠ 第一版在這裡量到三個 0×0 的 rect：`css/scenes.css:103` 的
    #   `#sc-worlds{display:none}`，場景要拿到 `.live`（`stage.css:133`）才有版面。
    #   原本打算自己補 `.on` ⇒ 那是硬掰一個觀眾走不到的狀態。改成 `?scene=1`
    #   （`app.js:26`）讓場景真的跑，`worlds.js:143` 在漏斗跑完 900ms 後自己
    #   `reveal.classList.add('on')`——量的是觀眾真的會看到的那一幕。
    # `&hold=1`（`app.js:25-27`）不能省：不加的話場景會自動前進，第二版量到
    # `.wall` 雜訊底 227（揭示正在淡出）、`.bound` rect 0×0（`#sc-worlds` 已經
    # 收回 display:none）。`hold` 只擋自動前進，不動版面與字級。
    ch.call("Page.navigate",
            {"url": f"http://127.0.0.1:{HM_PORT}/index.html?scene=1&hold=1"})
    t0 = time.time()
    got = None
    while time.time() - t0 < 180:
        time.sleep(0.5)
        got = json.loads(js(ch, """(() => {
          const r = document.getElementById('worlds-reveal');
          if (!r) return JSON.stringify({on:false, h:0, err:'no-el'});
          const s = r.querySelector('.wall-sub');
          const b = s ? s.getBoundingClientRect() : {height:0};
          return JSON.stringify({on: r.classList.contains('on'), h: Math.round(b.height),
                                 fs: s ? getComputedStyle(s).fontSize : ''});
        })()"""))
        if got.get("on") and got.get("h", 0) > 4:
            break
    print(f"  揭示於 t+{time.time() - t0:.1f}s 出現：{got}")
    # 揭示的 opacity transition 是 1.1s，而 `worlds.js:143-144` 同時把每一塊
    # 壞磚以 45ms 間隔逐一點亮——那是動的，會把雜訊底推到 200 以上。等它跑完。
    time.sleep(8.0)
    for sel, tag in (("#worlds-reveal .wall-sub", "T3_index_wallsub"),
                     ("#worlds-reveal .wall", "T4_index_wall"),
                     ("#worlds-reveal .bound", "T5_index_bound")):
        m = measure(ch, sel, tag)
        results.append(m)
        print(line(m))
    return got


def main() -> int:
    only_self = "--selftest" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    srvs = [
        subprocess.Popen([sys.executable, "-m", "http.server", str(HM_PORT),
                          "--bind", "127.0.0.1", "--directory", str(HM_ROOT)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
        subprocess.Popen([sys.executable, "-m", "http.server", str(CTL_PORT),
                          "--bind", "127.0.0.1", "--directory", str(RUNS_ROOT)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
    ]
    ch, fails, results, dwell, fs_check = None, [], [], None, None
    try:
        time.sleep(1.5)
        ch = cdp.Chrome(str(CHROME), DBG_PORT, size=(VW, VH), extra_flags=CFLAGS)
        ch.call("Page.enable")
        ch.call("Runtime.enable")
        selftest(ch, fails)
        if fails:
            print("\n量具沒過自驗 ⇒ **不讀主量測任何數字**")
            for f in fails:
                print("  FAIL " + f)
            return 2
        if only_self:
            print("\nPASS 五格自驗全過（--selftest，未跑主量測）")
            return 0
        dwell = measure_world(ch, results)
        fs_check = measure_index(ch, results)
    finally:
        if ch:
            ch.close()
        for s in srvs:
            s.terminate()
            try:
                s.wait(timeout=10)
            except Exception:
                s.kill()

    by = {m["tag"].split("_")[0]: m for m in results if "error" not in m}
    print("\n── C3 落差比（宣稱字高 ÷ 限定字高；判準 ≤ 1.5）──")
    ratios = {}
    for name, a, b in (("world  T2/T1", "T2", "T1"),
                       ("首頁   T4/T3", "T4", "T3"),
                       ("首頁   T4/T5", "T4", "T5")):
        if a in by and b in by and by[b]["band_h"]:
            r = by[a]["band_h"] / by[b]["band_h"]
            ratios[name] = round(r, 2)
            print(f"  {name}  {by[a]['band_h']:.1f} ÷ {by[b]['band_h']:.1f} = "
                  f"{r:.2f}  {'PASS' if r <= MAX_RATIO else 'FAIL'}")
        else:
            print(f"  {name}  算不出來（缺格或帶高 0）")

    print("\n── C4 停留時間（判準 ≥ 0.25 秒/字）──")
    if dwell and "T1" in by and by["T1"].get("chars"):
        sec_per_char = dwell["dwell_s"] / by["T1"]["chars"]
        print(f"  #act 停留 {dwell['dwell_s']:.1f}s ÷ {by['T1']['chars']} 字 = "
              f"{sec_per_char:.3f} 秒/字  "
              f"{'PASS' if sec_per_char >= MIN_SEC_PER_CHAR else 'FAIL'}")
    else:
        print("  沒量到（那一拍沒出現或字數為 0）")

    rep = {"criteria": {"C1_min_band_px": MIN_H, "C2_min_contrast": MIN_CONTRAST,
                        "C3_max_ratio": MAX_RATIO, "C4_min_sec_per_char": MIN_SEC_PER_CHAR},
           "targets": results, "ratios": ratios, "dwell": dwell,
           "index_fontsize_before_after": fs_check}
    (RUNS_ROOT / "s11_report.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n落盤：{RUNS_ROOT / 's11_report.json'} · 截圖 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
