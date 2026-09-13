#!/usr/bin/env python3
"""8-bit 字樣的產生器——**重建＝重跑這一支，不要手改 SVG**。

這支在架構裡承重什麼：README 頂端那張字樣是對外門面的一部分，而門面跟收據一樣，
要能被重算出來才算數（同 `ops/gain/replay/build_multiparty_viewer.py` 的規矩：
產生器是真相，產物是快取）。

產物（相對 repo 根）：
  docs/assets/vacant-8bit.svg    README 用（900×260、純 <rect>、零外部資源、零 script）
  docs/assets/vacant-8bit.txt    ASCII 版（不渲染 SVG 的地方）
  docs/assets/vacant-social.svg  社群預覽（1280×640，副標也是像素字 ⇒ 零字型依賴）
  docs/assets/vacant-social.png  上面那張的點陣版（需要 ImageMagick：`magick`）

用法：
    python3 docs/assets/make_vacant_8bit.py            # 重新產生 SVG／TXT
    python3 docs/assets/make_vacant_8bit.py --check    # 只比對，內容漂了就 exit 1
    python3 docs/assets/make_vacant_8bit.py --png      # 另外用 magick 轉 1280×640 PNG

誠實邊界：`--check` 比對的是**這支自己算出來的位元組**與磁碟上的檔案一不一致；
它擋得住「有人手改 SVG 忘了改產生器」，擋不住「產生器本身被改壞」——後者要靠人看圖。
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "assets"

# 5×7 的字身；'X' 是一個方塊，'.' 是空。
BIG = {
    "V": ["X...X", "X...X", "X...X", "X...X", "X...X", ".X.X.", "..X.."],
    "A": [".XXX.", "X...X", "X...X", "XXXXX", "X...X", "X...X", "X...X"],
    "C": [".XXX.", "X...X", "X....", "X....", "X....", "X...X", ".XXX."],
    "N": ["X...X", "XX..X", "XX..X", "X.X.X", "X..XX", "X..XX", "X...X"],
    "T": ["XXXXX", "..X..", "..X..", "..X..", "..X..", "..X..", "..X.."],
}
WORD = "VACANT"

# 3×5 的副標字身（社群預覽用；不用 <text> 就沒有字型依賴）
SMALL = {
    "A": ["XXX", "X.X", "XXX", "X.X", "X.X"], "B": ["XX.", "X.X", "XX.", "X.X", "XX."],
    "C": ["XXX", "X..", "X..", "X..", "XXX"], "D": ["XX.", "X.X", "X.X", "X.X", "XX."],
    "E": ["XXX", "X..", "XXX", "X..", "XXX"], "F": ["XXX", "X..", "XXX", "X..", "X.."],
    "G": ["XXX", "X..", "X.X", "X.X", "XXX"], "H": ["X.X", "X.X", "XXX", "X.X", "X.X"],
    "I": ["XXX", ".X.", ".X.", ".X.", "XXX"], "J": ["..X", "..X", "..X", "X.X", "XXX"],
    "K": ["X.X", "X.X", "XX.", "X.X", "X.X"], "L": ["X..", "X..", "X..", "X..", "XXX"],
    "M": ["X.X", "XXX", "XXX", "X.X", "X.X"], "N": ["X.X", "XXX", "XXX", "XXX", "X.X"],
    "O": ["XXX", "X.X", "X.X", "X.X", "XXX"], "P": ["XXX", "X.X", "XXX", "X..", "X.."],
    "Q": ["XXX", "X.X", "X.X", "XXX", "..X"], "R": ["XXX", "X.X", "XX.", "X.X", "X.X"],
    "S": ["XXX", "X..", "XXX", "..X", "XXX"], "T": ["XXX", ".X.", ".X.", ".X.", ".X."],
    "U": ["X.X", "X.X", "X.X", "X.X", "XXX"], "V": ["X.X", "X.X", "X.X", "X.X", ".X."],
    "W": ["X.X", "X.X", "XXX", "XXX", "X.X"], "X": ["X.X", "X.X", ".X.", "X.X", "X.X"],
    "Y": ["X.X", "X.X", "XXX", ".X.", ".X."], "Z": ["XXX", "..X", ".X.", "X..", "XXX"],
    "-": ["...", "...", "XXX", "...", "..."], ".": ["...", "...", "...", "...", ".X."],
    " ": ["...", "...", "...", "...", "..."],
}

INK = "#16150f"      # 深色底
ORANGE = "#f26b1d"   # 網站主色
SHADOW = "#7a2f06"   # 落影
PAPER = "#f5efe6"    # 紙色高光

COLS = 6 * len(WORD) - 1   # 35（每字 5 欄 ＋ 1 欄間隙）
ROWS = 7


def big_pixels() -> list[tuple[int, int]]:
    out, col = [], 0
    for ch in WORD:
        for r, line in enumerate(BIG[ch]):
            for c, v in enumerate(line):
                if v == "X":
                    out.append((col + c, r))
        col += 6
    return out


PX = big_pixels()


def small_pixels(text: str) -> tuple[list[tuple[int, int]], int]:
    out, col = [], 0
    for ch in text.upper():
        for r, line in enumerate(SMALL.get(ch, SMALL[" "])):
            for c, v in enumerate(line):
                if v == "X":
                    out.append((col + c, r))
        col += 4
    return out, 4 * len(text) - 1


def rects(px_list, px, x0, y0, fill, opacity=None) -> str:
    op = "" if opacity is None else ' opacity="%s"' % opacity
    parts = ['  <g fill="%s"%s>' % (fill, op)]
    for c, r in px_list:
        parts.append('    <rect x="%g" y="%g" width="%g" height="%g"/>'
                     % (x0 + c * px, y0 + r * px, px, px))
    parts.append("  </g>")
    return "\n".join(parts)


def wordmark(px: int, x0: float, y0: float) -> str:
    """落影 ＋ 形狀上緣的紙色高光（8-bit 斜角，不是整片掃描線）。"""
    off = max(2, px // 6)
    out = [rects(PX, px, x0 + off, y0 + off, SHADOW), rects(PX, px, x0, y0, ORANGE)]
    h = max(1, px // 7)
    on = set(PX)
    hi = ['  <g fill="%s" opacity="0.9">' % PAPER]
    for c, r in PX:
        if (c, r - 1) not in on:
            hi.append('    <rect x="%g" y="%g" width="%g" height="%g"/>'
                      % (x0 + c * px, y0 + r * px, px, h))
    hi.append("  </g>")
    out.append("\n".join(hi))
    return "\n".join(out)


def band(y: int, x_start: int, n: int, step: int, size: int) -> str:
    return "\n".join(
        '  <rect x="%d" y="%d" width="%d" height="%d" fill="%s" opacity="0.55"/>'
        % (x_start + step * i, y, size, size, SHADOW)
        for i in range(n) if i % 2 == 0)


def render_readme_svg() -> str:
    px, w, h = 24, 900, 260
    x0 = (w - COLS * px) / 2
    return "\n".join([
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
        'role="img" aria-label="VACANT">' % (w, h, w, h),
        "  <title>VACANT</title>",
        '  <rect width="%d" height="%d" fill="%s"/>' % (w, h, INK),
        band(20, 30, 53, 16, 8),
        band(h - 28, 30, 53, 16, 8),
        wordmark(px, x0, 46),
        "</svg>",
    ]) + "\n"


def render_social_svg() -> str:
    px, w, h = 30, 1280, 640
    x0 = (w - COLS * px) / 2
    t1, t1w = small_pixels("ACCOUNTABILITY LAYER FOR AI AGENTS")
    t2, t2w = small_pixels("RUN THE TESTS - GATE DELIVERY - SIGN THE RECEIPT")
    return "\n".join([
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" '
        'role="img" aria-label="VACANT - accountability layer for AI agents">' % (w, h, w, h),
        "  <title>VACANT</title>",
        '  <rect width="%d" height="%d" fill="%s"/>' % (w, h, INK),
        band(96, 115, 44, 24, 12),
        wordmark(px, x0, 160),
        rects(t1, 8, (w - t1w * 8) / 2, 420, PAPER, "0.92"),
        rects(t2, 6, (w - t2w * 6) / 2, 496, ORANGE),
        band(h - 64, 115, 44, 24, 12),
        "</svg>",
    ]) + "\n"


def render_ascii() -> str:
    grid = [[" "] * COLS for _ in range(ROWS)]
    for c, r in PX:
        grid[r][c] = "█"
    return "\n".join("".join(row).rstrip() for row in grid) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="只比對，不寫檔；不一致 exit 1")
    ap.add_argument("--png", action="store_true", help="另外用 ImageMagick 轉 1280×640 PNG")
    args = ap.parse_args()

    wanted = {
        OUT / "vacant-8bit.svg": render_readme_svg(),
        OUT / "vacant-8bit.txt": render_ascii(),
        OUT / "vacant-social.svg": render_social_svg(),
    }
    if args.check:
        drift = [p.name for p, body in wanted.items()
                 if not p.exists() or p.read_text(encoding="utf-8") != body]
        if drift:
            print("DRIFT：與產生器不一致 →", ", ".join(drift))
            return 1
        print("OK：%d 個產物與產生器一致" % len(wanted))
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    for p, body in wanted.items():
        p.write_text(body, encoding="utf-8")
        print("wrote", p.relative_to(ROOT))

    if args.png:
        src = OUT / "vacant-social.svg"
        dst = OUT / "vacant-social.png"
        try:
            subprocess.run(["magick", "-background", "none", str(src),
                            "-resize", "1280x640!", "PNG32:" + str(dst)], check=True)
            print("wrote", dst.relative_to(ROOT))
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            print("PNG 沒產生（需要 ImageMagick 的 `magick`）：", exc, file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
