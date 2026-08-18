#!/usr/bin/env python3
"""從去背貼圖的真實輪廓生接觸陰影——不是固定形狀的橢圓。

為什麼：b2.html 原本的 `.shadow` 是一個寫死的 `radial-gradient` 橢圓，
courier（走路，雙腳前後）跟 submit（遞交，雙手前伸站定）共用同一個形狀，
跟角色實際站姿的輪廓寬窄無關——SPEC 說接觸陰影是「合成必要的一步」，
固定橢圓只補了「有沒有陰影」，沒補「陰影對不對」。

做法：只取輪廓**下半部**（預設下 42%，約腳／小腿到裙擺的範圍，避開頭肩
手臂——手往前伸的 submit 姿態如果連上半身一起壓，陰影會被拉寬成整個
軀幹的形狀，不是「腳踩在地上」的形狀）壓扁成投影，每一段壓扁後的列取
原本對應列段裡的**最大** alpha（保輪廓，不是平均，平均會把陰影稀釋到
看不出形狀），再做一次簡單的水平／垂直方框模糊把邊緣化開，輸出純黑、
alpha 已經乘上強度上限的 PNG。純標準庫（沿用 cutout.py 的
decode/encode），這台 VM 沒有 PIL。

用法：shadow.py <去背輸入.png> <輸出.png> [squash=0.16] [blur=2] [max_alpha=0.5] [bottom_frac=0.42]
"""
from __future__ import annotations

import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from cutout import decode_png, encode_png, trim  # noqa: E402


def squash_alpha(w: int, h: int, rgba: bytearray, squash: float, bottom_frac: float) -> tuple[int, bytearray]:
    src_y0 = h - max(1, round(h * bottom_frac))
    src_h = h - src_y0
    new_h = max(1, round(src_h * squash))
    out = bytearray(w * new_h)
    for ny in range(new_h):
        y0 = src_y0 + (ny * src_h) // new_h
        y1 = max(y0 + 1, src_y0 + ((ny + 1) * src_h) // new_h)
        row_out_off = ny * w
        for x in range(w):
            m = 0
            for y in range(y0, y1):
                a = rgba[(y * w + x) * 4 + 3]
                if a > m:
                    m = a
            out[row_out_off + x] = m
    return new_h, out


def box_blur(w: int, h: int, chan: bytearray, radius: int) -> bytearray:
    if radius <= 0:
        return chan
    # 水平
    tmp = bytearray(w * h)
    for y in range(h):
        row = y * w
        for x in range(w):
            lo, hi = max(0, x - radius), min(w - 1, x + radius)
            s = 0
            for xx in range(lo, hi + 1):
                s += chan[row + xx]
            tmp[row + x] = s // (hi - lo + 1)
    # 垂直
    out = bytearray(w * h)
    for x in range(w):
        for y in range(h):
            lo, hi = max(0, y - radius), min(h - 1, y + radius)
            s = 0
            for yy in range(lo, hi + 1):
                s += tmp[yy * w + x]
            out[y * w + x] = s // (hi - lo + 1)
    return out


def make_shadow(inp: str, outp: str, squash: float, blur: int, max_alpha: float, bottom_frac: float) -> None:
    w, h, rgba = decode_png(inp)
    sh, salpha = squash_alpha(w, h, rgba, squash, bottom_frac)
    salpha = box_blur(w, sh, salpha, blur)
    cap = int(255 * max_alpha)
    out = bytearray(w * sh * 4)
    for i in range(w * sh):
        a = salpha[i]
        out[i * 4 + 3] = a * cap // 255  # RGB 留 0（黑），只寫 alpha
    ow, oh, out = trim(w, sh, out)
    encode_png(outp, ow, oh, out)
    print(f"  {outp}  {ow}x{oh}（原圖 {w}x{h} 壓扁 squash={squash}）")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit("用法：shadow.py <去背輸入.png> <輸出.png> [squash] [blur] [max_alpha] [bottom_frac]")
    inp, outp = sys.argv[1], sys.argv[2]
    squash = float(sys.argv[3]) if len(sys.argv) > 3 else 0.16
    blur = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    max_alpha = float(sys.argv[5]) if len(sys.argv) > 5 else 0.5
    bottom_frac = float(sys.argv[6]) if len(sys.argv) > 6 else 0.42
    make_shadow(inp, outp, squash, blur, max_alpha, bottom_frac)
