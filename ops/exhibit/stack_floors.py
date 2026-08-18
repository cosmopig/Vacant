#!/usr/bin/env python3
"""把多張樓層排圖縮到同一寬度後上下疊成一棟建築剖面，純標準庫（同 cutout.py 的理由）。

PLAN.md 定案：「樓層＝多張排圖上下疊」。這支只做「疊」這件事本身——
不處理房間對齊（每張排圖是獨立生成的一張圖，房間數一樣但寬度、
牆線、光源角度都是各自的，疊起來不會逐間對齊，只是同一棟樓的
不同樓層各自一張剖面）。

用法：stack_floors.py <輸出.png> <排圖1.png> <排圖2.png> [...] [--width N]
樓層順序＝命令列順序，第一張在最上面。
"""
from __future__ import annotations

import sys

sys.path.insert(0, "/home/user1/vacant/Vacant/ops/exhibit")
from cutout import decode_png, encode_png
from thumb import resize_nearest

DIVIDER_H = 10
DIVIDER_RGBA = (26, 24, 20, 255)


def resize_to(w, h, rgba, target_w):
    tw, th, out = resize_nearest(w, h, rgba, target_w)
    target_h = round(h * target_w / w)
    if th == target_h:
        return tw, th, out
    out2 = bytearray(tw * target_h * 4)
    for ty in range(target_h):
        sy = min(th - 1, ty * th // target_h)
        row_src = sy * tw * 4
        row_dst = ty * tw * 4
        out2[row_dst:row_dst + tw * 4] = out[row_src:row_src + tw * 4]
    return tw, target_h, out2


def main():
    args = sys.argv[1:]
    target_w = 1600
    if "--width" in args:
        i = args.index("--width")
        target_w = int(args[i + 1])
        del args[i:i + 2]

    out_path = args[0]
    floor_paths = args[1:]
    if len(floor_paths) < 2:
        print("用法：stack_floors.py <輸出.png> <排圖1.png> <排圖2.png> [...] [--width N]", file=sys.stderr)
        sys.exit(2)

    floors = []
    for p in floor_paths:
        w, h, rgba = decode_png(p)
        tw, th, out = resize_to(w, h, rgba, target_w)
        floors.append((tw, th, out, p))

    total_h = sum(f[2 - 1] for f in floors)  # placeholder, fixed below
    total_h = sum(f[1] for f in floors) + DIVIDER_H * (len(floors) - 1)
    canvas = bytearray(target_w * total_h * 4)

    y = 0
    for idx, (fw, fh, frgba, p) in enumerate(floors):
        for row in range(fh):
            src = row * fw * 4
            dst = (y + row) * target_w * 4
            canvas[dst:dst + fw * 4] = frgba[src:src + fw * 4]
        y += fh
        if idx < len(floors) - 1:
            for row in range(DIVIDER_H):
                dst = (y + row) * target_w * 4
                for x in range(target_w):
                    canvas[dst + x * 4:dst + x * 4 + 4] = bytes(DIVIDER_RGBA)
            y += DIVIDER_H

    encode_png(out_path, target_w, total_h, canvas)
    print(f"{out_path}  {target_w}x{total_h}  {len(floors)} 層")


if __name__ == "__main__":
    main()
