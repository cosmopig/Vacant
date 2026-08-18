#!/usr/bin/env python3
"""去背後的品管一步：貼在深色底上看一次，確認沒有破洞（純標準庫，理由同 cutout.py）。

用法：paste_on_dark.py <去背後.png> [輸出.png]
"""
from __future__ import annotations

import sys
from cutout import decode_png, encode_png

if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("用法：paste_on_dark.py <去背後.png> [輸出.png]")
    inp = sys.argv[1]
    outp = sys.argv[2] if len(sys.argv) > 2 else inp.rsplit(".png", 1)[0] + "_ondark.png"
    pad = 40
    bg_color = (30, 30, 40, 255)

    w, h, rgba = decode_png(inp)
    W, H = w + pad * 2, h + pad * 2
    bg = bytearray(W * H * 4)
    for i in range(W * H):
        bg[i * 4:i * 4 + 4] = bytes(bg_color)
    for y in range(h):
        row_src = y * w * 4
        row_dst = (y + pad) * W * 4 + pad * 4
        for x in range(w):
            si = row_src + x * 4
            if rgba[si + 3] == 0:
                continue
            di = row_dst + x * 4
            bg[di:di + 3] = rgba[si:si + 3]
            bg[di + 3] = 255
    encode_png(outp, W, H, bg)
    print(f"  {outp}  {W}x{H}")
