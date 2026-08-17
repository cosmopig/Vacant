#!/usr/bin/env python3
"""S13：**墨跡帶高量具的容差，以及用區間重讀第 116 輪的 C3。**

第 118 輪。第 116 輪把帶高當精確點值報（`T3`=7.0、`T4`=17.0、`T5`=6.0），
並據此宣布「宣稱比誠實邊界大 **2.83 倍**」。第 117 輪事後發現同一個量具在
同一格重複量會給 6–8（`n=4`）。⇒ **那個 2.83 帶著一個從來沒被量過的誤差，
而它正是本專題對外會講的那句話的量。**

**它在架構裡承重什麼**：三條誠實邊界之一是「不准把量不到的東西講成量到的」。
一個沒量過重複性的點值，就是把量不到的精度講成量到了。這一支不改畫面上任何
一個像素——它改的是**我們有沒有資格說那個數字**。判準本身要可究責。

## 量法

程序（URL、settle、等待、雙拍相減、縮 1/3）與 `s11_legibility.py` 第 116 輪
**逐項相同**，否則量到的容差配不上那一輪的數字。差別只有兩點：

1. `T3`/`T4`/`T5` 各重複量 `n=8`，且**輪替順序**（T3,T4,T5,T3,T4,T5,…）——
   不是連做八次同一格。這樣時間漂移平均落在三格上，不會被誤讀成某格特別抖。
2. 每一次量測**前後**都驗 `#worlds-reveal.on` 仍為 true、且 rect 與第一次相同
   （±1px）。第 117 輪踩過：`--repeat` 在同一頁連量，第 3、4 次讀到 0.0，
   那不是抖動是**導演已經走掉**。「量具在抖」與「量錯對象」長得一模一樣。

## 判準（`STATE.md` 第 118 輪【事前】，一條沒放寬）

  R1  三格各報 中位數 / 最小 / 最大 / 全距（全距即該格容差）
  R2  C3 改區間判：`T4/T3` 區間 = [min(T4)/max(T3), max(T4)/min(T3)]
      下界 > 1.5 ⇒ C3 FAIL 成立；區間跨過 1.5 ⇒ 判不了，照實寫
  R3  重讀 G1164（預測 T4/T3 > 2.5）：區間跨過 2.5 ⇒ 那格判不了
  R4  C1 方向用區間再確認：T4 的 min 是否 ≥ 12、T3/T5 的 max 是否 < 12

## 探針自己要先過的三格（不過就 exit 2，不准讀任何主量測數字）

  P3a  沿用 s11 的五格自驗（P0a–P0e），原封不動 import，不重寫第二份
  P3b  靜態正控制：純色零動畫的 `s11_ctl.html` 上量 `#ctl-big` n=8，全距 ≤ 1
       ——分辨「量具自己在抖」與「被量的頁面在動」，第 117 輪把這兩件混在一起
  P3c  解析度負控制：同頁量 `#ctl-small` n=8，
       `median(big) − median(small)` > `range(big) + range(small)`
       ——沒有這格，一個壞成「永遠回同一個數」的量具會在 P3b 拿滿分

用法：
  python3 runs/s13_tolerance.py            # 自驗 ＋ 主量測（約 6–10 分鐘）
  python3 runs/s13_tolerance.py --selftest # 只跑自驗
"""
from __future__ import annotations

import json
import statistics
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
import s11_legibility as s11                                  # noqa: E402

CHROME = HOME / ".local" / "bin" / "chrome-headless-shell"
HM_ROOT = HOME / "vacant" / "vacant_hm"
OUT = RUNS_ROOT / "s13_shots"
DBG_PORT = 9363
HM_PORT = 8763
CTL_PORT = 8764

N_REPEAT = 8
STATIC_RANGE_MAX = 1        # P3b
MIN_H = s11.MIN_H           # 12.0，C1 判準，沿用不重訂

TARGETS = [("T3", "#worlds-reveal .wall-sub"),
           ("T4", "#worlds-reveal .wall"),
           ("T5", "#worlds-reveal .bound")]


def stats(vals):
    """R1 的四個數。空的就照實回 None，不要回 0——0 會被讀成量到了。"""
    if not vals:
        return {"n": 0, "median": None, "min": None, "max": None, "range": None}
    return {"n": len(vals), "median": statistics.median(vals),
            "min": min(vals), "max": max(vals), "range": max(vals) - min(vals),
            "values": list(vals)}


def fmt(name, st):
    if not st["n"]:
        return f"  {name:<6} 沒有有效樣本"
    return (f"  {name:<6} n={st['n']} 中位數 {st['median']:>5.1f} · "
            f"最小 {st['min']:>4.1f} · 最大 {st['max']:>4.1f} · "
            f"全距 {st['range']:>4.1f}  {st['values']}")


# ── P3b / P3c 靜態校準頁上的重複性 ──────────────────────────────────
def static_repeat(ch, fails):
    print(f"\n── P3b/P3c 靜態校準頁重複性（n={N_REPEAT}，純色零動畫）──")
    ch.call("Page.navigate", {"url": f"http://127.0.0.1:{CTL_PORT}/s11_ctl.html"})
    time.sleep(2.5)
    got = {"big": [], "small": []}
    for i in range(N_REPEAT):
        for t in ("big", "small"):
            m = s11.measure(ch, f"#ctl-{t}", f"s13ctl_{t}_r{i}", settle=0.35)
            if "error" in m:
                fails.append(f"P3b/c 靜態頁第 {i} 次量 {t} 出錯：{m['error']}")
                continue
            got[t].append(m["band_h"])
    sb, ss = stats(got["big"]), stats(got["small"])
    print(fmt("ctl-big", sb))
    print(fmt("ctl-small", ss))

    ok_b = sb["n"] == N_REPEAT and sb["range"] <= STATIC_RANGE_MAX
    print(f"  P3b 量具在靜態頁的全距 {sb['range']}（要 ≤ {STATIC_RANGE_MAX}）"
          f"  {'PASS' if ok_b else 'FAIL'}")
    if not ok_b:
        fails.append(f"P3b 靜態頁全距 {sb['range']} > {STATIC_RANGE_MAX} "
                     f"⇒ 抖動是量具內生的，真頁的所有帶高都要重新說話")

    sep = (sb["median"] - ss["median"]) if (sb["n"] and ss["n"]) else 0
    need = (sb["range"] + ss["range"]) if (sb["n"] and ss["n"]) else 0
    ok_c = sep > need
    print(f"  P3c 解析度 median(big)−median(small) = {sep}（要 > "
          f"range(big)+range(small) = {need}）  {'PASS' if ok_c else 'FAIL'}")
    if not ok_c:
        fails.append(f"P3c 量具分不開 48px 與 21px（差 {sep} ≤ 容差和 {need}）"
                     f"⇒ 它可能恆答同一個數")
    return {"ctl_big": sb, "ctl_small": ss,
            "P3b": ok_b, "P3c": ok_c, "static_range_max": STATIC_RANGE_MAX}


# ── 主量測：真頁上的重複性 ──────────────────────────────────────────
def reveal_state(ch):
    return json.loads(s11.js(ch, """(() => {
      const r = document.getElementById('worlds-reveal');
      if (!r) return JSON.stringify({on:false, err:'no-el'});
      return JSON.stringify({on: r.classList.contains('on')});
    })()"""))


def page_repeat(ch, fails):
    print(f"\n── T3/T4/T5 真頁重複性（n={N_REPEAT}，輪替順序）──")
    # URL 與等待與第 116 輪逐項相同：`?scene=1&hold=1`（app.js:25-27）。
    # `hold=1` 不能省——不加的話場景自動前進，第 116 輪量到 .wall 雜訊底 227、
    # .bound rect 0×0。`hold` 只擋自動前進，不動版面與字級。
    ch.call("Page.navigate",
            {"url": f"http://127.0.0.1:{HM_PORT}/index.html?scene=1&hold=1"})
    t0, got = time.time(), None
    while time.time() - t0 < 180:
        time.sleep(0.5)
        got = json.loads(s11.js(ch, """(() => {
          const r = document.getElementById('worlds-reveal');
          if (!r) return JSON.stringify({on:false, h:0});
          const s = r.querySelector('.wall-sub');
          const b = s ? s.getBoundingClientRect() : {height:0};
          return JSON.stringify({on: r.classList.contains('on'),
                                 h: Math.round(b.height)});
        })()"""))
        if got.get("on") and got.get("h", 0) > 4:
            break
    print(f"  揭示於 t+{time.time() - t0:.1f}s 出現：{got}")
    if not (got and got.get("on")):
        fails.append("主量測：等 180 秒沒等到 #worlds-reveal.on")
        return None
    # worlds.js:143-144 的壞磚逐一點亮（45ms 間隔）＋ 1.1s opacity transition。
    # 等它跑完，第 116 輪等的是同一個 8.0s。
    time.sleep(8.0)

    samples = {t: [] for t, _ in TARGETS}
    voids = {t: 0 for t, _ in TARGETS}
    guards = {t: 0 for t, _ in TARGETS}
    rect0 = {}
    trace = []
    for i in range(N_REPEAT):
        for tag, sel in TARGETS:                    # 輪替，不是連做八次同一格
            before = reveal_state(ch)
            m = s11.measure(ch, sel, f"s13_{tag}_r{i}")
            after = reveal_state(ch)
            rec = {"i": i, "tag": tag, "band_h": m.get("band_h"),
                   "void": m.get("void"), "noise": m.get("noise_floor"),
                   "rect": m.get("rect"), "on_before": before.get("on"),
                   "on_after": after.get("on"), "error": m.get("error")}
            trace.append(rec)
            if "error" in m:
                guards[tag] += 1
                print(f"  [{i}] {tag} ERROR {m['error']}")
                continue
            # 量錯對象的三種形狀：拍走掉、rect 變了、景動到 VOID。分開記。
            if not (before.get("on") and after.get("on")):
                guards[tag] += 1
                rec["guard"] = "揭示中途消失"
                print(f"  [{i}] {tag} GUARD 揭示中途消失 ⇒ 這格不採用")
                continue
            if tag not in rect0:
                rect0[tag] = m["rect"]
            elif any(abs(a - b) > 1 for a, b in zip(m["rect"], rect0[tag])):
                guards[tag] += 1
                rec["guard"] = f"rect 變了 {rect0[tag]} → {m['rect']}"
                print(f"  [{i}] {tag} GUARD rect 變了 {rect0[tag]} → {m['rect']}")
                continue
            if m["void"]:
                voids[tag] += 1
                print(f"  [{i}] {tag} VOID 雜訊底 {m['noise_floor']}（景在動）⇒ 不採用")
                continue
            samples[tag].append(m["band_h"])
            print(f"  [{i}] {tag} 帶高 {m['band_h']:>5.1f} · 對比 {m['contrast']:.3f}"
                  f" · 雜訊底 {m['noise_floor']:>5.1f} · 帶 {m['n_bands']}")
    return {"samples": samples, "voids": voids, "guards": guards,
            "rect0": rect0, "trace": trace}


# ── R2/R3/R4 用區間重讀第 116 輪 ────────────────────────────────────
def interval(a, b):
    """比值的區間：[min(a)/max(b), max(a)/min(b)]。b 的 min 為 0 就算不了。"""
    if not (a["n"] and b["n"]) or b["min"] == 0 or b["max"] == 0:
        return None
    return (round(a["min"] / b["max"], 2), round(a["max"] / b["min"], 2))


def straddles(iv, x):
    return iv is not None and iv[0] <= x <= iv[1]


def reload_repeat(ch, fails, n=4):
    """**事後追加**（第 118 輪主量測跑完之後才加，照實標）。

    主量測的三格全距都是 0，但那只回答了「同一次載入之內」。事前預註冊的
    盲點 5 寫的正是這件事：跨載入的抖動沒量。而「2.43 / 2.83 這兩個比值配不配
    得上被說出口」真正取決於跨載入——展場每次開機都是一次新載入。
    這一段**沒有事前判準**（它是事後加的），所以只報數字、不判 PASS/FAIL。
    """
    print(f"\n── 事後追加：跨載入重複性（重新載入 {n} 次，每次量一輪 T3/T4/T5）──")
    per = {t: [] for t, _ in TARGETS}
    for r in range(n):
        ch.call("Page.navigate",
                {"url": f"http://127.0.0.1:{HM_PORT}/index.html?scene=1&hold=1"})
        t0, ok = time.time(), False
        while time.time() - t0 < 120:
            time.sleep(0.5)
            st = reveal_state(ch)
            if st.get("on"):
                ok = True
                break
        if not ok:
            print(f"  [載入{r}] 等不到揭示 ⇒ 這輪不採用")
            continue
        time.sleep(8.0)
        for tag, sel in TARGETS:
            m = s11.measure(ch, sel, f"s13rl_{tag}_L{r}")
            if "error" in m or m.get("void"):
                print(f"  [載入{r}] {tag} 不採用（{m.get('error') or 'VOID'}）")
                continue
            per[tag].append(m["band_h"])
            print(f"  [載入{r}] {tag} 帶高 {m['band_h']:>5.1f} · "
                  f"雜訊底 {m['noise_floor']:>5.1f}")
    st = {t: stats(per[t]) for t, _ in TARGETS}
    for t, _ in TARGETS:
        print(fmt(t, st[t]))
    out = {"n_loads": n, "targets": {t: st[t] for t, _ in TARGETS},
           "C3_intervals": {"T4/T3": interval(st["T4"], st["T3"]),
                            "T4/T5": interval(st["T4"], st["T5"])}}
    print(f"  跨載入 C3 區間：{out['C3_intervals']}")
    return out


def main() -> int:
    only_self = "--selftest" in sys.argv
    only_reload = "--reload" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    s11.OUT = OUT                       # 借 s11 的 measure()，截圖落到本輪的目錄
    srvs = [
        subprocess.Popen([sys.executable, "-m", "http.server", str(HM_PORT),
                          "--bind", "127.0.0.1", "--directory", str(HM_ROOT)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
        subprocess.Popen([sys.executable, "-m", "http.server", str(CTL_PORT),
                          "--bind", "127.0.0.1", "--directory", str(RUNS_ROOT)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
    ]
    ch, fails, static, page = None, [], None, None
    try:
        time.sleep(1.5)
        ch = cdp.Chrome(str(CHROME), DBG_PORT, size=(s11.VW, s11.VH),
                        extra_flags=s11.CFLAGS)
        ch.call("Page.enable")
        ch.call("Runtime.enable")

        # P3a：原封不動沿用 s11 的五格自驗（它自己會 print 並往 fails 塞）
        s11.CTL_PORT = CTL_PORT
        s11.selftest(ch, fails)
        static = static_repeat(ch, fails)
        if fails:
            print("\n量具沒過自驗 ⇒ **不讀主量測任何數字**")
            for f in fails:
                print("  FAIL " + f)
            return 2
        print("\nPASS 自驗全過（P0a–P0e ＋ P3b ＋ P3c）")
        if only_self:
            return 0
        if only_reload:
            rl = reload_repeat(ch, fails)
            (RUNS_ROOT / "s13_reload.json").write_text(
                json.dumps(rl, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"\n落盤：{RUNS_ROOT / 's13_reload.json'}")
            return 0
        page = page_repeat(ch, fails)
    finally:
        if ch:
            ch.close()
        for s in srvs:
            s.terminate()
            try:
                s.wait(timeout=10)
            except Exception:
                s.kill()

    if page is None:
        print("\n主量測沒有成立，不報任何區間")
        for f in fails:
            print("  FAIL " + f)
        return 2

    st = {t: stats(page["samples"][t]) for t, _ in TARGETS}
    print("\n── R1 三格容差 ──")
    for t, _ in TARGETS:
        print(fmt(t, st[t]))
        print(f"         VOID {page['voids'][t]} 次 · GUARD 擋掉 {page['guards'][t]} 次"
              f" · 名目 n={N_REPEAT}")

    print("\n── R2/R3 C3 落差比改區間判（判準 ≤ 1.5；第 116 輪報的點值 2.43 / 2.83）──")
    ivs = {}
    for name, a, b, pt116 in (("T4/T3", "T4", "T3", 2.43), ("T4/T5", "T4", "T5", 2.83)):
        iv = interval(st[a], st[b])
        ivs[name] = iv
        if iv is None:
            print(f"  {name}  算不出來（缺樣本）")
            continue
        med = round(st[a]["median"] / st[b]["median"], 2) if st[b]["median"] else None
        if iv[0] > 1.5:
            v15 = "FAIL 成立（整段 > 1.5）"
        elif iv[1] <= 1.5:
            v15 = "PASS 成立（整段 ≤ 1.5）"
        else:
            v15 = "**判不了**（區間跨過 1.5）"
        print(f"  {name}  區間 [{iv[0]}, {iv[1]}] · 中位數比 {med} · "
              f"第116輪點值 {pt116} · C3 {v15}")
        if name == "T4/T3":
            g = ("**判不了**（區間跨過 2.5）" if straddles(iv, 2.5)
                 else ("成立 > 2.5" if iv[0] > 2.5 else "不成立 ≤ 2.5"))
            print(f"         R3 重讀第 116 輪 G1164（預測 > 2.5）：{g}")

    print(f"\n── R4 C1 方向用區間再確認（判準 帶高 ≥ {MIN_H:.0f}）──")
    c1 = {}
    for t, _ in TARGETS:
        s = st[t]
        if not s["n"]:
            c1[t] = None
            print(f"  {t:<6} 缺樣本")
            continue
        if s["min"] >= MIN_H:
            v = "PASS 成立（整段 ≥ 12）"
        elif s["max"] < MIN_H:
            v = "FAIL 成立（整段 < 12）"
        else:
            v = "**判不了**（區間跨過 12）"
        c1[t] = v
        print(f"  {t:<6} [{s['min']}, {s['max']}]  {v}")

    rep = {"round": 118, "n_repeat": N_REPEAT,
           "procedure_same_as": "s11_legibility.py 第116輪（URL/settle/等待/縮1/3 逐項相同）",
           "selftest": {"P0a_P0e": "PASS（沿用 s11.selftest）", **(static or {})},
           "targets": {t: st[t] for t, _ in TARGETS},
           "voids": page["voids"], "guards": page["guards"], "rect0": page["rect0"],
           "C3_intervals": ivs, "C3_max_ratio": 1.5,
           "C1_min_band_px": MIN_H, "C1_by_interval": c1,
           "round116_point_values": {"T3": 7.0, "T4": 17.0, "T5": 6.0,
                                     "T4/T3": 2.43, "T4/T5": 2.83},
           "trace": page["trace"]}
    (RUNS_ROOT / "s13_report.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n落盤：{RUNS_ROOT / 's13_report.json'} · 截圖 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
