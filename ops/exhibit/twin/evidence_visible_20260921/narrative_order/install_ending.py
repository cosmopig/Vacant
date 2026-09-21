#!/usr/bin/env python3
"""把**收尾層**（`world3/scenes/seam_ending.js`，幕 7′＋幕 18）併進展件，或還原。

    python3 install_ending.py            # 掛上去
    python3 install_ending.py --undo     # 還原
    python3 install_ending.py --status   # 現在掛著沒有

## 為什麼不是那個 `.patch`

同目錄的 `wire_in.patch` 留著當**紀錄**（它逐字寫出加了哪三行），但**不要拿它去套**：
`vacant_hm/world3/index.html` 2026-09-21 這一天被別的代理改了**四次**
（本條進行中量到 sha256 `9f9a1a44…` → `3641c259…` → `5d2b1806…` → `709d717d…`，
45 分鐘內）。context diff 遲早爛掉，而爛掉的時間點不可預測。
這一支只認 `</body>`，別人改什麼都對得上。

鄰線 `../narrative_seam/install_seam.py` 是同一個想法（那一支掛 `twinseam.js`），
**先跑那一支再跑這一支**——順序不可對調：收尾層要包在文案層的
`arrivals.update` 外面才讓得了位。

## fail-closed（寧可不做，不做半套）

- 找不到 `index.html` 或 `</body>` ⇒ 丟例外，不寫半成品。
- `scenes/seam_ending.js` 不在 ⇒ 拒絕掛（掛了就是每次載入一個 404）。
- `twinseam.js` 掛在**後面**或根本沒掛 ⇒ **警告但不擋**：收尾層單獨掛也成立
  （它只多接管 s11 的兩個狀態），只是幕 5/6/8/9/16/17 不會出現。
- 做兩次不會插兩行（先查有沒有已經掛上）。
  ⚠ `seam_ending.js` 自己另外還有一道 `window.__seamEnding` 防呆——
    兩道都要，因為別的代理也可能插同一行。
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

LINE = '<script src="scenes/seam_ending.js"></script>'
MARK = re.compile(r'[ \t]*<script src="scenes/seam_ending\.js(\?[^"]*)?"></script>\n?')
SEAM = re.compile(r'<script src="twinseam\.js(\?[^"]*)?"></script>')


def status(html: str) -> bool:
    return bool(MARK.search(html))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hm", default=str(pathlib.Path.home() / "Documents/GitHub/vacant_hm"))
    ap.add_argument("--undo", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()

    w3 = pathlib.Path(a.hm) / "world3"
    idx, js = w3 / "index.html", w3 / "scenes" / "seam_ending.js"
    if not idx.is_file():
        raise SystemExit(f"拒絕動手：找不到 {idx}")
    html = idx.read_text(encoding="utf-8")
    on = status(html)
    seam = SEAM.search(html)

    if a.status:
        print(f"收尾層：{'掛著' if on else '沒掛'}　（{idx}）")
        print(f"scenes/seam_ending.js：{'在' if js.is_file() else '🔴 不在——掛上去也會 404'}")
        print(f"twinseam.js：{'掛著' if seam else '沒掛（幕 5/6/8/9/16/17 不會出現）'}")
        if on and seam and seam.start() > MARK.search(html).start():
            print("🔴 順序錯了：twinseam.js 在收尾層**後面**。"
                  "收尾層會包不到它 ⇒ 幕 17 與幕 18 可能互搶大標。")
        return 0

    if a.undo:
        if not on:
            print("本來就沒掛，什麼都沒做。")
            return 0
        idx.write_text(MARK.sub("", html, count=1), encoding="utf-8")
        print(f"還原完成：{idx} 少了那一行。")
        return 0

    if not js.is_file():
        raise SystemExit(f"拒絕掛上：{js} 不在——掛了就是每次載入一個 404")
    if on:
        print("已經掛著了，不重複插。")
        return 0
    if "</body>" not in html:
        raise SystemExit("拒絕掛上：index.html 裡找不到 </body>")
    if not seam:
        print("⚠ twinseam.js 沒掛：收尾層單獨掛也成立（幕 7′／18 會出現），"
              "但幕 5/6/8/9/16/17 不會。先跑 ../narrative_seam/install_seam.py。")
    idx.write_text(html.replace("</body>", LINE + "\n</body>", 1), encoding="utf-8")
    print(f"掛上完成：{idx} 的 </body> 前面多了一行 {LINE}")
    print("還原：python3 install_ending.py --undo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
