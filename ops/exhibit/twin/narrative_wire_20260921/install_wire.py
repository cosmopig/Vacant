#!/usr/bin/env python3
"""把兩層文案掛進展件本尊（`world3/index.html`）——冪等、一行還原。

## 這一支在架構裡承重什麼

2026-09-21 之前，觀眾那一段的文案全部寫在兩個**外掛檔**裡：

    world3/twinseam.js            幕 5／6／8／9／9b／16／17
    world3/scenes/seam_ending.js  幕 7′／18

兩支都寫完了、都有負控制、都有 node 端逐句測試。**但 `index.html` 一行都沒載。**
`grep -c 'twinseam\\.js' world3/index.html` ⇒ `0`（rc=1）。

⇒ 照 CLAUDE.md 那一條唯一判準（「觀眾走到展場前面時，這件事有沒有差別」），
  那 12 拍今天的答案是 **沒有差別**：寫了，但走到螢幕前一句都讀不到。
  `scenes/narrative_order.json` 自己用紅字記著這件事（`not_wired`）。

這一支就是把它接上去，而且**接法本身要禁得起展場的硬約束**：

  - **冪等**：掛過就不再掛。兩個外掛都自己擋重複（`window.__seamEnding`），
    但別讓它們靠「別人不會插第二次」活著——十幾個代理共用這個工作樹。
  - **一行還原**：`--undo` 把那三行（含記號註解）整段拿掉，sha256 回到原樣。
  - **fail-closed**：兩個 .js 少任何一支就**不掛也不寫**（`--check` 回 4）。
    掛一個指向 404 的 <script> ＝ 展場那天靜靜地少一層，而畫面不會說。
  - **順序不可對調**：`seam_ending.js` 必須在 `twinseam.js` **後面**——它包在
    twinseam 的 `arrivals.update` 外面才讓得了位（見 seam_ending.js 開頭）。

## 為什麼是 <script src>，不是把碼併進 index.html

`index.html` 今天 5649 行、301 KB，而且同時有十幾個代理在改。併進去＝每一次
合併都要處理這 41 KB 的衝突，而且**還原不回去**。外掛檔 ＋ 兩行 <script> 的
還原成本是「刪兩行」，這是展場布展前臨時砍功能唯一負擔得起的成本。

## 退出碼

    0  已經掛好（`--check`）／這一次掛上去了／`--undo` 拿掉了
    3  還沒掛（`--check`，這是**狀態不是錯誤**，但要分得出來）
    4  掛不上去：缺 .js、找不到 </body>、頁面讀不到（**不安靜跳過**）

用法：

    python3 install_wire.py --check
    python3 install_wire.py                 # 掛上去（冪等）
    python3 install_wire.py --undo          # 還原
    python3 install_wire.py --page <別的 index.html>
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

DEFAULT_PAGE = Path("/Users/cosmopig/Documents/GitHub/vacant_hm/world3/index.html")

BEGIN = "<!-- NARRATIVE-COPY-LAYERS-BEGIN  (install_wire.py；刪掉這三行就完全還原) -->"
END = "<!-- NARRATIVE-COPY-LAYERS-END -->"

# 🔴 順序不可對調：seam_ending 包在 twinseam 的 arrivals.update 外面才讓得了位。
LAYERS = [
    ("twinseam.js", "world3/twinseam.js"),
    ("scenes/seam_ending.js", "world3/scenes/seam_ending.js"),
]

BLOCK = "\n".join(
    [BEGIN]
    + [f'<script src="{src}"></script>' for src, _ in LAYERS]
    + [END]
)


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def installed(text: str) -> bool:
    return BEGIN in text


def stray_refs(text: str) -> list[str]:
    """別人也插了一行的情況。冪等不等於『我沒插過就一定沒有』。"""
    out = []
    for src, _ in LAYERS:
        # 記號區塊以外還有沒有引用
        outside = text.replace(BLOCK, "") if BLOCK in text else text
        if f'src="{src}"' in outside:
            out.append(src)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--page", type=Path, default=DEFAULT_PAGE)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--undo", action="store_true")
    a = ap.parse_args()

    page: Path = a.page
    if not page.is_file():
        print(f"[掛不上去] 頁面不存在：{page}")
        return 4
    text = page.read_text(encoding="utf-8")

    if a.check:
        ok = installed(text)
        print(f"page={page}")
        print(f"sha256={sha256(page)}")
        print(f"installed={'true' if ok else 'false'}")
        for src, rel in LAYERS:
            f = page.parent / src
            print(f"layer {src}: exists={f.is_file()} "
                  f"sha256={sha256(f) if f.is_file() else 'null'}")
        stray = stray_refs(text)
        print(f"stray_refs={stray if stray else 'none'}")
        return 0 if ok else 3

    if a.undo:
        if not installed(text):
            print("[還原] 本來就沒掛，什麼都沒做。")
            return 0
        i = text.index(BEGIN)
        j = text.index(END) + len(END)
        # 連同記號區塊前面那一個換行一起拿掉 ⇒ sha256 回到原樣
        k = i - 1 if i > 0 and text[i - 1] == "\n" else i
        new = text[:k] + text[j:]
        page.write_text(new, encoding="utf-8")
        print(f"[還原] 拿掉了。新 sha256={sha256(page)}")
        return 0

    # 掛上去
    if installed(text):
        print(f"[冪等] 已經掛好了，這一次不重複掛。sha256={sha256(page)}")
        return 0

    missing = [src for src, _ in LAYERS if not (page.parent / src).is_file()]
    if missing:
        # fail-closed：少一支就整個不掛。掛一個 404 的 <script> ＝ 展場那天
        # 靜靜地少一層，而畫面上不會有任何一句話說出來。
        print(f"[掛不上去] 缺檔：{'／'.join(missing)}（fail-closed，一行都沒寫）")
        return 4

    stray = stray_refs(text)
    if stray:
        print(f"[掛不上去] 記號區塊外面已經有人引用了：{'／'.join(stray)}。"
              f"再掛一次會載兩遍（seam_ending 的 joined 會每輪加 2）。")
        return 4

    if "</body>" not in text:
        print("[掛不上去] 找不到 </body>")
        return 4

    before = sha256(page)
    i = text.rindex("</body>")
    new = text[:i] + BLOCK + "\n" + text[i:]
    page.write_text(new, encoding="utf-8")
    print(f"[掛上去了] {page}")
    print(f"before_sha256={before}")
    print(f"after_sha256={sha256(page)}")
    print("還原：python3 install_wire.py --undo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
