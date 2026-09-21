#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 v2_clockstep 那兩臂的連續截圖拼成**會動的**對照（左右並排，同一個虛擬時刻）。

為什麼是 GIF 不是 mp4：這台機器的 `ffmpeg` 壞了
（`Library not loaded: libx265.215.dylib`），而修它要動 brew、這台正在跑展件，
不划算。GIF 用 PIL 就寫得出來，而且**每一格的時間是假時鐘給的**，
不是「拍照當下剛好是幾點」——比真時鐘錄影誠實。

⚠ 每一格上面印的毫秒是**虛擬時間**（零點＝`onSubmission` 回呼進到頁面那一刻）。
   播放速度是給人看的，不代表現場的秒數。
"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

E = ("/Users/cosmopig/Documents/GitHub/Vacant/.claude/worktrees/wf_32a45899-6ee-1"
     "/ops/exhibit/twin/evidence_visible_20260921/arrival_beat/v2_clockstep")
FONT = "/System/Library/Fonts/STHeiti Medium.ttc"
PW, PH = 520, 293          # 每一格畫面的大小


def f(sz):
    try:
        return ImageFont.truetype(FONT, sz)
    except Exception:
        return ImageFont.load_default()


def frames_of(arm):
    d = os.path.join(E, arm)
    fs = sorted(x for x in os.listdir(d) if x.startswith("f__+") and x.endswith(".jpg"))
    out = [(os.path.join(d, "f__pre.jpg"), None)]
    for x in fs:
        ms = int(x[len("f__+"):-len("ms.jpg")])
        out.append((os.path.join(d, x), ms))
    return out


def build(left, right, dest, title, lcap, rcap, hold_ms=420, pre_hold=1400, end_hold=2000):
    L, R = frames_of(left), frames_of(right)
    n = min(len(L), len(R))
    head, gap, pad, cap_h = 74, 16, 14, 34
    W = pad * 2 + PW * 2 + gap
    H = head + cap_h + PH + 30 + pad
    out, durs = [], []
    for i in range(n):
        im = Image.new("RGB", (W, H), (22, 18, 14))
        d = ImageDraw.Draw(im)
        d.text((pad, 10), title, font=f(24), fill=(240, 232, 216))
        ms = L[i][1]
        d.text((pad, 44), "投卡前" if ms is None else
               ("回呼進到頁面那一刻（0 ms）" if ms == 0 else "回呼之後 +%d ms" % ms),
               font=f(17), fill=(228, 196, 130))
        for k, (fp, cap) in enumerate(((L[i][0], lcap), (R[i][0], rcap))):
            x = pad + k * (PW + gap)
            d.text((x, head), cap, font=f(15), fill=(178, 166, 150))
            try:
                pic = Image.open(fp).convert("RGB").resize((PW, PH), Image.LANCZOS)
            except Exception:
                pic = Image.new("RGB", (PW, PH), (80, 20, 20))
            im.paste(pic, (x, head + cap_h))
        d.text((pad, head + cap_h + PH + 6),
               "虛擬時鐘（Playwright clock）· 零點＝onSubmission 回呼 · "
               "播放速度是給人看的，不是現場秒數",
               font=f(13), fill=(150, 140, 126))
        out.append(im.convert("P", palette=Image.ADAPTIVE, colors=200))
        durs.append(pre_hold if ms is None else
                    (end_hold if i == n - 1 else hold_ms))
    out[0].save(dest, save_all=True, append_images=out[1:],
                duration=durs, loop=0, optimize=True)
    return dest, os.path.getsize(dest), n


if __name__ == "__main__":
    jobs = [
        ("S06_before_busy", "S07_after_busy",
         os.path.join(E, "GIF_busy_before_vs_after.gif"),
         "導演正在演別人的故事時投卡（展場有人排隊時的常態）",
         "改動前（git HEAD）：六格逐格一樣，他在畫面上不存在",
         "改動後：信照飛照落，右下角陶牌多一列，故事不被打斷"),
        ("S03_negctl_arrive0", "S02_after_single",
         os.path.join(E, "GIF_negctl_vs_after.gif"),
         "負控制：同一份碼，只把抵達層關掉（單變數）",
         "?arrive=0（抵達層關）", "抵達層開"),
    ]
    for a, b, dest, t, lc, rc in jobs:
        p, sz, n = build(a, b, dest, t, lc, rc)
        print("%s  %.2f MB  %d 格" % (os.path.basename(p), sz / 1e6, n))
