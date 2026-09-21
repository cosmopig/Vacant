#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把連續截圖排成一張**不用看碼就看得懂**的對照表。

一列＝一臂，一格＝虛擬時間軸上的一刻，欄位在兩臂之間**完全對齊**
（同一支腳本、同一組時刻、同一個零點：回呼進到頁面的那一刻）。
"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
FONT = "/System/Library/Fonts/STHeiti Medium.ttc"


def f(sz):
    try:
        return ImageFont.truetype(FONT, sz)
    except Exception:
        return ImageFont.load_default()


def build(rows, marks, dest, title, sub, cell_w=326):
    """rows: [(dirname, 左邊的標籤, 說明)]

    ⚠ 缺格畫成紅字方塊，**不留白**。留白會被讀成「那一刻畫面是黑的」，
      而真正的意思是「那一臂沒拍到這一格」。"""
    cell_h = int(cell_w * 9 / 16)
    # lab_w 從 250 加到 420：說明改長之後（不能再寫「完全沒反應」那種短句，
    # 因為那是錯的）字會壓到第一格畫面上。
    pad, lab_w, head_h = 12, 420, 100
    W = lab_w + len(marks) * (cell_w + pad) + pad
    H = head_h + len(rows) * (cell_h + 34 + pad) + pad + 26
    im = Image.new("RGB", (W, H), (22, 18, 14))
    d = ImageDraw.Draw(im)
    d.text((pad, 14), title, font=f(30), fill=(240, 232, 216))
    d.text((pad, 54), sub, font=f(15), fill=(178, 166, 150))

    x0 = lab_w + pad
    for i, m in enumerate(marks):
        x = x0 + i * (cell_w + pad)
        d.text((x + 2, head_h - 20), ("+%d ms" % m) if m else "0 ms（回呼進來）",
               font=f(15), fill=(228, 196, 130))

    y = head_h
    for dirname, label, note in rows:
        d.text((pad, y + 8), label, font=f(19), fill=(240, 232, 216))
        for li, line in enumerate(note):
            d.text((pad, y + 38 + li * 22), line, font=f(15), fill=(170, 158, 142))
        for i, m in enumerate(marks):
            x = x0 + i * (cell_w + pad)
            p = os.path.join(OUT, dirname, "f__%+05dms.jpg" % m)
            if os.path.exists(p):
                im.paste(Image.open(p).convert("RGB").resize((cell_w, cell_h)), (x, y))
            else:
                d.rectangle([x, y, x + cell_w, y + cell_h], fill=(46, 38, 30))
                d.text((x + 10, y + 10), "（沒有這一格）", font=f(15), fill=(190, 120, 110))
            d.rectangle([x, y, x + cell_w, y + cell_h], outline=(70, 60, 48))
        y += cell_h + 34 + pad
    d.text((pad, H - 22),
           "虛擬時鐘（Playwright clock）逐格推進：每一格的內容都落在時間軸上精確的那一刻，"
           "跟當下機器忙不忙無關。牆上時鐘的延遲另外量，見 probe_*/probe.json。",
           font=f(13), fill=(150, 140, 126))
    im.save(dest, quality=88)
    print("wrote", dest, im.size)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "main"
    if which == "main":
        build(
            # ⚠ **這些說明改過一次。** 第一版寫「改動前投卡之後畫面沒有任何反應」，
            #   而這張表自己打臉：+120 ms 就開始淡出、+250 ms 已經是「世界多了
            #   一個人」。導演閒著的時候它反應得很快。差的不是**快不快**，
            #   是**出現的那個東西是不是他的**。照第一版寫法交出去就是對著
            #   自己的截圖說謊。
            [("S01_before_single", "改動前（HEAD）",
              ["onSubmission(sub => spawnQueue.push(sub))",
               "畫面確實馬上動——但換到的是一格通用開場。",
               "他的信、他手機上那枚記號、他排第幾，",
               "**畫面上一個都沒有**。"]),
             ("S02_after_single", "改動後（抵達層）",
              ["先給他看自己那一封：信飛進來→落到",
               "投遞口→塵爆→旁邊的黏土人轉頭（實測",
               "4 個真的翻面）。信上蓋的是他手機上",
               "那一枚章。2.8 秒後才走同一格故事。"]),
             ("S03_negctl_arrive0", "負控制 ?arrive=0",
              ["同一份碼，只把抵達層關掉。",
               "⇒ 逐格回到第一列的樣子。",
               "一行還原，而且證明上面那一列的",
               "差別來自抵達層、不是別的東西。"])],
            [0, 120, 250, 400, 620, 900, 1400],
            os.path.join(OUT, "SHEET_before_after_negctl.jpg"),
            "投卡的那一秒：改動前／改動後／負控制",
            "零點＝WorldBridge.onSubmission 回呼進到頁面的那一刻（三臂同一個定義）。"
            "1280×720、?lite=1（輕量版，不播影片）。導演在這三跑都是閒著的——"
            "他正忙的時候差別更大，見 SHEET_busy.jpg。")
    elif which == "triple":
        build(
            [("S05_before_triple", "改動前（HEAD）· 同時三人",
              ["🔴 這一列 anchorFound=false：零點沒抓到，",
               "十四格落在時間軸上的哪裡**不知道**。",
               "不可以拿它跟下一列逐格對照——",
               "留著是為了讓這個缺口看得見，不是證據。"]),
             ("S04_after_triple", "改動後 · 同時三人",
              ["三封信 0.42 秒一封排隊起飛，不疊在",
               "一起；落地的字比我晚到的往上讓一格。",
               "右下角陶牌列出 1／2／3，第 2、3 位",
               "標「排隊中」。實測 8／424／840 ms 畫出。"])],
            [0, 250, 620, 900, 1400, 1800],
            os.path.join(OUT, "SHEET_triple.jpg"),
            "同時三個人投卡（判準 3）",
            "同一輪輪詢送進三筆。改動前：排在後面的人在畫面上不存在。"
            "改動後：右下角陶牌列出排隊順序，落地的那一封印「收到了 · 你是第 N 個」。")
    elif which == "busy":
        # 🔴 **這一張才是主證據。** S03（導演閒著）拍出來，投卡 620 ms 後畫面
        #    已經硬切到「世界多了一個人」⇒「改動前完全沒反應」是錯的。
        #    真正有落差的是導演正在演別人的故事——展場有人排隊時的常態。
        build(
            [("S06_before_busy", "改動前 · 導演正忙",
              ["第一位的故事正在演（visitor_spawn）。",
               "第二位投卡 ⇒ 這 1.8 秒六格**逐格一樣**，",
               "他在畫面上完全不存在。要等整格演完",
               "才輪到他——這裡沒量那要多久。"]),
             ("S07_after_busy", "改動後 · 導演正忙",
              ["同一個情境。故事**照樣不被打斷**",
               "（toDrop 在非 invite/wait 回 false），",
               "但信照飛、照落，陶牌多一列「小水缸」。",
               "回呼→畫出來 4 ms。⚠ 這一格沒有人轉頭",
               "（turned=0）：台上的人都被故事佔著。"])],
            [0, 250, 620, 900, 1400, 1800],
            os.path.join(OUT, "SHEET_busy.jpg"),
            "導演正在演別人的故事時投卡（展場有人排隊的常態）",
            "先送一位進去把導演帶進故事，等 director.mode 離開 wait，再送第二位並從那一刻起算。"
            "🔴 這一張才是主證據：導演閒著的時候改動前也會馬上換景（見 SHEET_before_after_negctl.jpg 第一列），"
            "真正整片空白的是這一格。")
    elif which == "weight":
        # 自己那一版的前後。**這一張不是「有沒有做」，是「做得夠不夠大」。**
        build(
            [("v1_smallcard/S02_after_single", "第一版 · 信 0.050H",
              ["機制對了，但 1080p 上只有 54 px", "高，縮在右下角。判準 1 問的是", "站在展場前面看不看得出來"]),
             ("S02_after_single", "第二版 · 信 0.092H",
              ["同一層、同一條路徑，只放大", "造型常數：信 99 px、塵爆與", "閃光同步放大、落地縮進投遞口"])],
            [0, 120, 250, 400, 620, 900],
            os.path.join(OUT, "SHEET_visual_weight.jpg"),
            "同一個機制，兩種視覺重量（人類：「給人看得要極度著墨」）",
            "兩列都是抵達層開著、走同一條 onSubmission 路徑。差別只有造型常數。"
            "⚠ 兩列不是同一份碼的同一跑，是同一份機制的兩個版本——這一張比的是重量不是有無。")
