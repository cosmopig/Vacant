#!/usr/bin/env python3
"""S7b：把「互動之後才存在的文案」抓下來，餵給 S7 的紅線掃描。

**為什麼要有這一支**：第 97 輪的 S7 掃描自己寫下一個洞——DOM 那條路
**只涵蓋初始渲染**。而同一輪也證明了 DOM 路徑看得見原始碼路徑看不見的東西
（拼接字串的 canary：原始碼路徑 1、DOM 路徑抓到）。兩件事合起來的意思是：
**互動後才拼出來的字，兩條路都沒有看過。**

而那正是觀眾最專心的那一秒——他們剛按下抽樣格，正在讀後果。
`sampler.js` 的 `hint`／`rp-wall`／`rp-bound` 全是點下去之後才存在的字，
其中 `rp-bound` 還是 `${outcome}` 拼進去的，原始碼路徑看到的是佔位符。

這支**只抓狀態、不下判定**。判定仍由 `s7_claim_audit.py` 做候選、由人工做結論。

用法：
    python3 runs/s7b_interact_dom.py --sweep OUTDIR   # 真掃：無注入，抓互動狀態
    python3 runs/s7b_interact_dom.py --canary OUTDIR  # Q1 自驗：注入只在點擊後出現的句子

兩者都要求 http（`file://` 下 ES module 被 CORS 擋掉、頁面根本沒跑，
`--dump-dom` 照樣回傳 HTML ⇒ 掃出一片假的乾淨。第 97 輪實測 21 倍差距）。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HOME = Path.home()
sys.path.insert(0, str(HOME / "vacant" / "vacant-docs-web" / "probe"))
import cdp  # noqa: E402  ← 全 repo 唯一那份 CDP 客戶端（HANDOFF §8：不寫第二份）

CHROME = HOME / ".local" / "bin" / "chrome-headless-shell"
CFLAGS = ["--disable-gpu", "--no-sandbox", "--hide-scrollbars",
          "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
SIZE = (1400, 900)
DBG_PORT = 9341
HTTP_PORT = 8741

# ── Q1 canary：只在「點擊之後」才寫進 DOM 的句子。──────────────────────
# 正樣本＝S7 fixture 的 V2（〈抓到類〉稽核/抓到 ＋〈排除類〉再也）。
# decoy＝只有〈排除類〉，不准進候選；它擋的是「無序字元比對」那種壞探針。
CANARY_HIT = "稽核抓到之後它就再也拿不到工作。"
CANARY_DECOY = "這一件被排除了。"
CANARY_JS = f"""
(() => {{
  const mark = () => {{
    if (document.getElementById('s7b-canary')) return;
    const d = document.createElement('div');
    d.id = 's7b-canary';
    d.textContent = {json.dumps(CANARY_HIT)};
    const e = document.createElement('div');
    e.id = 's7b-decoy';
    e.textContent = {json.dumps(CANARY_DECOY)};
    (document.body || document.documentElement).append(d, e);
  }};
  addEventListener('click', mark, true);
  addEventListener('DOMContentLoaded', () => {{
    document.addEventListener('click', mark, true);
  }});
}})();
"""

_SCRIPT_STYLE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.S | re.I)
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_TAG = re.compile(r"<[^>]+>")


def dom_text_len(html: str) -> int:
    """DOM 純文字長度。判準要看的是這個數字，不是位元組數
    （位元組會被 style 屬性、class 名撐大，那些觀眾看不到）。"""
    s = _COMMENT.sub(" ", _SCRIPT_STYLE.sub(" ", html))
    return len(re.sub(r"\s+", "", _TAG.sub(" ", s)))


class Driver:
    def __init__(self, out: Path, base: str, inject: bool):
        self.out = out
        self.base = base
        self.inject = inject
        self.states: list[dict] = []
        self.userdir = tempfile.mkdtemp(prefix="s7b-")
        self.ch = cdp.Chrome(str(CHROME), DBG_PORT, size=SIZE,
                             extra_flags=CFLAGS, userdir=self.userdir)
        self.ch.call("Page.enable")
        self.ch.call("Runtime.enable")
        if inject:
            self.ch.call("Page.addScriptToEvaluateOnNewDocument",
                         {"source": CANARY_JS})

    def goto(self, path: str, wait_s: float) -> None:
        self.ch.call("Page.navigate", {"url": self.base + path})
        time.sleep(wait_s)

    def js(self, expr: str):
        r = self.ch.call("Runtime.evaluate",
                         {"expression": expr, "returnByValue": True,
                          "awaitPromise": True})
        return r.get("result", {}).get("value")

    def dump(self, name: str, note: str) -> dict:
        html = self.js("document.documentElement.outerHTML")
        if not isinstance(html, str):
            html = ""
        (self.out / f"{name}.html").write_text(html, encoding="utf-8")
        st = {"state": name, "note": note, "bytes": len(html),
              "text_len": dom_text_len(html)}
        self.states.append(st)
        print(f"  {name:<26} bytes={st['bytes']:<7} text={st['text_len']}")
        return st

    def close(self):
        self.ch.close()
        shutil.rmtree(self.userdir, ignore_errors=True)


HM = "/vacant_hm/index.html"


def sweep(d: Driver) -> None:
    """真掃：主頁三拍 ＋ 抽樣格的兩條分支 ＋ world 兩頁的時間演進。"""
    # ── 主頁三拍（?hold=1 停住自動前進，否則抓到的是哪一拍靠運氣）──
    d.goto(f"{HM}?scene=0&hold=1", 3.0)
    d.dump("hm_s0_hero", "場景 0 主視覺（E10 真資料兩行）")
    d.goto(f"{HM}?scene=1&hold=1", 4.0)
    d.dump("hm_s1_worlds_early", "場景 1 漏斗剛開始跑")
    time.sleep(12.0)
    d.dump("hm_s1_worlds_late", "場景 1 跑久之後（reveal 文案已填）")

    # ── 抽樣：被標記的格（bad 分支：hint 走「被扣分了」）──
    d.goto(f"{HM}?scene=2&hold=1", 4.0)
    d.dump("hm_s2_idle", "場景 2 抽樣格已排好、還沒有人按")
    n = d.js("document.querySelectorAll('#samp-grid .cell').length")
    nf = d.js("document.querySelectorAll('#samp-grid .cell.flagged').length")
    print(f"  [grid] cells={n} flagged={nf}")
    d.js("(document.querySelector('#samp-grid .cell.flagged')"
         " || document.querySelector('#samp-grid .cell')).click()")
    time.sleep(3.0)
    d.dump("hm_s2_rerun_mid", "點下去 3 秒：沙箱重跑逐行吐字中")
    time.sleep(6.0)
    d.dump("hm_s2_consequence", "重跑完＋信譽/評審條圖＋hint 改寫")
    time.sleep(8.0)
    d.dump("hm_s2_ripple", "漣漪揭曉：rp-wall／rp-bound（${outcome} 拼進去的那句）")

    # ── 抽樣：沒被標記的格（clean 分支：hint 走「這一件是乾淨的」）──
    d.goto(f"{HM}?scene=2&hold=1", 4.0)
    d.js("(document.querySelector('#samp-grid .cell:not(.flagged)')"
         " || document.querySelector('#samp-grid .cell')).click()")
    time.sleep(9.0)
    d.dump("hm_s2b_clean_consequence", "未標記格的分支：hint 走另一句")
    time.sleep(8.0)
    d.dump("hm_s2b_clean_ripple", "未標記格的漣漪文案")

    # ── world 兩頁：文字隨時間演進（ledger／字幕／phone 面板）──
    for page, waits, tag in (("/vacant_hm/world/index.html", (4.0, 12.0, 14.0), "world"),
                             ("/vacant_hm/world/phone.html", (4.0, 12.0), "phone")):
        d.goto(page, waits[0])
        d.dump(f"{tag}_t0", f"{page} 載入後 {waits[0]:.0f}s")
        for i, w in enumerate(waits[1:], 1):
            time.sleep(w)
            d.dump(f"{tag}_t{i}", f"{page} 累計 {sum(waits[:i + 1]):.0f}s")
        d.js("document.body.click()")
        time.sleep(4.0)
        d.dump(f"{tag}_click", f"{page} 點一下之後")


def findbad(d: Driver) -> None:
    """事後加的一格：`ev.bad` 那條分支的文案在 --sweep 裡**一次都沒被渲染出來**。

    原因是 `flagged` ＝ `ev.residual`（機器自己說「我檢查不了」），**不等於**
    `ev.bad`。點被標記的格拿到的仍是乾淨分支，於是
    「`${res.agent}` 被扣分了 —— 下一件工作因此會交給別人」
    與「判定：不通過　—　這件東西本來已經被收下了」兩句從沒進過 DOM。

    而那正是 S7 紅線最可能踩到的一句——「重跑抓到 ⇒ 扣分」。漏掉它，
    本輪等於掃了一個不含待測物的樣本。

    種子固定（`ctx.seed='S1'`、cycle 1），所以第 i 格每次載入都是同一個事件
    ⇒ 命中是可複現的，不是碰運氣。逐格試到重跑吐出「不通過」為止。
    """
    grids = []
    for _ in range(2):
        d.goto(f"{HM}?scene=2&hold=1", 4.0)
        grids.append(d.js("document.getElementById('samp-grid').textContent"))
    print(f"  [determinism] 兩次載入的格子序列相同：{grids[0] == grids[1]}")

    n = d.js("document.querySelectorAll('#samp-grid .cell').length")
    for i in range(min(int(n or 0), 24)):
        d.goto(f"{HM}?scene=2&hold=1", 3.5)
        d.js(f"document.querySelectorAll('#samp-grid .cell')[{i}].click()")
        time.sleep(3.0)
        log = d.js("document.getElementById('rerun-log').textContent") or ""
        bad = "不通過" in log
        print(f"  cell[{i:02d}] 不通過={bad}")
        if bad:
            d.dump("hm_s2c_bad_rerun", f"第 {i} 格＝ev.bad：重跑判定不通過")
            time.sleep(6.0)
            d.dump("hm_s2c_bad_consequence", f"第 {i} 格：hint 走「被扣分了」那句")
            time.sleep(8.0)
            d.dump("hm_s2c_bad_ripple", f"第 {i} 格：漣漪的 ${{outcome}} 拼接句")
            return
    print("  [findbad] 前 24 格沒有一格是 bad —— 照實記，不改判準")


def phonehurt(d: Driver) -> None:
    """第二格事後加的：`world/js/phone.js:125` 那句只在 `hurt` 狀態才渲染。

    `--sweep` 抓到的那隻居民是 `節點`，所以那句從來沒進過 DOM——
    而它是本輪讀原始碼時判定**最像 S7 紅線**的一句
    （被抽查到 ⇒ 工作不會交到牠手上）。宣稱它「會出現在觀眾眼前」之前，
    要先真的把它渲染出來。`?id=` 是既有參數，不是為了這次加的。
    """
    for i in list(range(1, 40)):
        d.goto(f"/vacant_hm/world/phone.html?id={i}", 2.2)
        hurt = d.js("document.getElementById('me-now')"
                    "?.classList.contains('hurt') === true")
        if hurt:
            print(f"  id={i} hurt=True")
            d.dump("phone_hurt", f"phone.html?id={i}：被抽查到之後的那一屏")
            return
        print(f"  id={i} hurt=False")
    print("  [phonehurt] 前 39 個 id 沒有一個在 hurt 狀態 —— 照實記")


def canary(d: Driver) -> None:
    """Q1：同一條管線、同一個頁面，只差「有沒有點下去」。"""
    d.goto(f"{HM}?scene=2&hold=1", 4.0)
    d.dump("canary_before_click", "注入已掛好，但還沒有人點 ⇒ 句子不該存在")
    d.js("document.querySelector('#samp-grid .cell').click()")
    time.sleep(3.0)
    d.dump("canary_after_click", "點了 ⇒ 句子必須在")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", type=Path)
    ap.add_argument("--canary", type=Path)
    ap.add_argument("--findbad", type=Path)
    ap.add_argument("--phonehurt", type=Path)
    a = ap.parse_args()
    out = a.sweep or a.canary or a.findbad or a.phonehurt
    if not out:
        ap.print_help()
        return 2
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.html"):
        old.unlink()

    srv = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(HTTP_PORT), "--bind", "127.0.0.1"],
        cwd=str(HOME / "vacant"),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    base = f"http://127.0.0.1:{HTTP_PORT}"
    d = None
    try:
        d = Driver(out, base, inject=bool(a.canary))
        (canary if a.canary else findbad if a.findbad
         else phonehurt if a.phonehurt else sweep)(d)
    finally:
        if d:
            states = d.states
            d.close()
        else:
            states = []
        srv.terminate()

    (out / "states.json").write_text(
        json.dumps(states, ensure_ascii=False, indent=1), encoding="utf-8")
    if states:
        lens = [s["text_len"] for s in states]
        print(f"\n狀態數 {len(states)} · text_len min={min(lens)} max={max(lens)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
