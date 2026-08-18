#!/usr/bin/env python3
"""測試合成：把去背角色貼到背景圖上的指定位置，純標準庫（沿用 cutout.py 的 decode/encode）。
用法：composite.py <背景.png> <角色.png> <輸出.png> <目標高度px> <center_x> <feet_y> [陰影寬度倍率]
"""
import sys
sys.path.insert(0, "/home/user1/vacant/Vacant/ops/exhibit")
from cutout import decode_png, encode_png
from thumb import resize_nearest


def paste(bg_w, bg_h, bg, sp_w, sp_h, sp, cx, feet_y, shadow=True):
    x0 = cx - sp_w // 2
    y0 = feet_y - sp_h
    # soft shadow ellipse first
    if shadow:
        sw, sh = int(sp_w * 0.5), int(sp_w * 0.14)
        scx, scy = cx, feet_y
        for dy in range(-sh, sh):
            for dx in range(-sw, sw):
                nx2 = (dx / sw) ** 2 + (dy / sh) ** 2
                if nx2 > 1:
                    continue
                px, py = scx + dx, scy + dy
                if 0 <= px < bg_w and 0 <= py < bg_h:
                    i = (py * bg_w + px) * 4
                    a = 0.45 * (1 - nx2)
                    for c in range(3):
                        bg[i + c] = int(bg[i + c] * (1 - a))
    for y in range(sp_h):
        by = y0 + y
        if by < 0 or by >= bg_h:
            continue
        for x in range(sp_w):
            bx = x0 + x
            if bx < 0 or bx >= bg_w:
                continue
            si = (y * sp_w + x) * 4
            a = sp[si + 3]
            if a == 0:
                continue
            di = (by * bg_w + bx) * 4
            if a == 255:
                bg[di:di + 3] = sp[si:si + 3]
            else:
                af = a / 255.0
                for c in range(3):
                    bg[di + c] = int(sp[si + c] * af + bg[di + c] * (1 - af))
    return bg


if __name__ == "__main__":
    bg_path, sp_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    target_h = int(sys.argv[4])
    cx = int(sys.argv[5])
    feet_y = int(sys.argv[6])

    bw, bh, bg = decode_png(bg_path)
    sw, sh, sp = decode_png(sp_path)
    target_w = round(sw * target_h / sh)
    tw, th, tsp = resize_nearest(sw, sh, sp, target_w)
    # resize_nearest only scales width & derives height; need exact target_h too
    if th != target_h:
        # rescale again on height axis via same nearest logic transposed
        out2 = bytearray(tw * target_h * 4)
        for ty in range(target_h):
            sy = min(th - 1, ty * th // target_h)
            for tx in range(tw):
                si = (sy * tw + tx) * 4
                di = (ty * tw + tx) * 4
                out2[di:di + 4] = tsp[si:si + 4]
        tsp = out2
        th = target_h

    bg = paste(bw, bh, bg, tw, th, tsp, cx, feet_y)
    encode_png(out_path, bw, bh, bg)
    print(f"{out_path}  sprite {tw}x{th} @ cx={cx} feet_y={feet_y}")
