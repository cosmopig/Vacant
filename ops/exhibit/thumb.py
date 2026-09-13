#!/usr/bin/env python3
"""縮圖——純標準庫，理由同 cutout.py（這台 VM 沒有 ImageMagick、沒有 PIL、沒有 pip）。

最近鄰縮放，不是為了畫質，是為了模擬「展場隔一段距離看電視」：
縮到目標寬度後拿去餵 K3，細節（拇指壓痕級別）看不到了，跟真實觀眾一樣。

用法：thumb.py <輸入.png> [輸出.png] [目標寬度，預設 640]
"""
from __future__ import annotations

import sys

from cutout import decode_png, encode_png


def resize_nearest(w: int, h: int, rgba: bytearray, target_w: int):
    target_h = max(1, round(h * target_w / w))
    out = bytearray(target_w * target_h * 4)
    for ty in range(target_h):
        sy = min(h - 1, ty * h // target_h)
        src_row = sy * w * 4
        dst_row = ty * target_w * 4
        for tx in range(target_w):
            sx = min(w - 1, tx * w // target_w)
            si = src_row + sx * 4
            di = dst_row + tx * 4
            out[di:di + 4] = rgba[si:si + 4]
    return target_w, target_h, out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("用法：thumb.py <輸入.png> [輸出.png] [目標寬度]")
    inp = sys.argv[1]
    outp = sys.argv[2] if len(sys.argv) > 2 else inp.rsplit(".png", 1)[0] + "_640.png"
    target_w = int(sys.argv[3]) if len(sys.argv) > 3 else 640

    w, h, rgba = decode_png(inp)
    tw, th, trgba = resize_nearest(w, h, rgba, target_w)
    encode_png(outp, tw, th, trgba)
    print(f"  {outp}  {tw}x{th}")
