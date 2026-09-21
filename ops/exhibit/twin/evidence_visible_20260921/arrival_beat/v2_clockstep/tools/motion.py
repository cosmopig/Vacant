#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「畫面動了沒有」的**數字**，給連續截圖當背書。

判準 1 是「我按下送出，抬頭看螢幕，一秒內看得出我的東西進去了嗎」。
截圖是主要證據，但截圖會被「你挑了好看的那張」質疑，所以另外算一條曲線：
**每一格相對於投卡前那一張（`f__pre.jpg`）差了多少像素。**

⚠ **基線不是 0，而且不該是 0。** 這個世界本來就一直在動（黏土人在走、
  光在呼吸、12fps 定格），所以改動前那一臂也會有一個非零的底噪。
  ⇒ 單看「改動後有數字」不算數，要看的是**兩臂在同一時刻的差距**，
    以及**差在畫面的哪裡**。所以每一格算兩個數：

    whole   整張畫面的平均絕對差（底噪：環境動畫）
    dock    右下角投遞口那一塊的平均絕對差（訊號：信落進去、陶牌亮起來）

  沒有郵筒的景，落點就在 dock 這一塊裡（`dropPoint()` 的 fallback），
  所以 `dock` 這一欄就是「我的東西進去了」那個動效本身。

⚠ 三臂用**同一個** dock 方框（照 `dockGeom()` 的比例算，與場景無關），
  不是各自挑一塊。挑框就等於挑結論。
"""
import json, os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

# `dockGeom()`（index.html）：U = uiScale() = Math.min(W, H)，1280x720 時 U = 720。
#   w = U*0.30, h = U*0.170, x = W - U*0.03 - w, y = H*0.905 - h
# 這裡照抄那個算式，並往上放一段（落地的三行字會長出陶牌上緣）。
def dock_box(w, h):
    U = min(w, h)
    bw, bh = U * 0.30, U * 0.170
    x = w - U * 0.03 - bw
    y = h * 0.905 - bh
    pad_y = h * 0.075                      # 「收到了 · 你是第 N 個」那幾行在陶牌上方
    return (int(x - w * 0.01), int(max(0, y - pad_y)), int(w), int(min(h, y + bh)))


def mad(a, b):
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def curve(dirname):
    d = os.path.join(OUT, dirname)
    pre_p = os.path.join(d, "f__pre.jpg")
    if not os.path.exists(pre_p):
        return None
    pre = Image.open(pre_p).convert("L")
    w, h = pre.size
    x0, y0, x1, y1 = dock_box(w, h)
    pre_a = np.asarray(pre)
    pre_d = pre_a[y0:y1, x0:x1]
    rows = []
    for fn in sorted(os.listdir(d)):
        if not fn.startswith("f__+") or not fn.endswith("ms.jpg"):
            continue
        ms = int(fn[len("f__+"):-len("ms.jpg")])
        cur = np.asarray(Image.open(os.path.join(d, fn)).convert("L"))
        rows.append({"ms": ms, "whole": round(mad(cur, pre_a), 3),
                     "dock": round(mad(cur[y0:y1, x0:x1], pre_d), 3)})
    rows.sort(key=lambda r: r["ms"])
    return {"dir": dirname, "dockBox": [x0, y0, x1, y1], "frames": rows}


if __name__ == "__main__":
    arms = sys.argv[1:] or ["S01_before_single", "S02_after_single", "S03_negctl_arrive0",
                            "S05_before_triple", "S04_after_triple"]
    res = {}
    for a in arms:
        c = curve(a)
        # 拍到一半的臂寫 None，**不寫 0**：「沒量到」跟「量到 0」是兩件事。
        res[a] = c
        if c is None:
            print(a.ljust(22), "（沒有 f__pre.jpg ⇒ 這一臂沒拍成，記 null）")
            continue
        head = "  ".join("%5d:%6.2f/%6.2f" % (r["ms"], r["whole"], r["dock"])
                         for r in c["frames"] if r["ms"] <= 1400)
        print(a.ljust(22), head)
    with open(os.path.join(OUT, "motion.json"), "w", encoding="utf-8") as f:
        json.dump({"metric": "mean absolute difference vs f__pre.jpg（灰階 0-255）",
                   "columns": "ms: whole/dock", "arms": res}, f, ensure_ascii=False, indent=1)
    print("\nwrote", os.path.join(OUT, "motion.json"))
