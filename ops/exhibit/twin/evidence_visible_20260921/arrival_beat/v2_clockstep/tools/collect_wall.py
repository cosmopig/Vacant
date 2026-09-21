#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把真時鐘（wall-clock）那四臂收進證據目錄，並做一張**只用得起的那兩格**的對照表。

⚠ 這一批的連續截圖檔名時間是假的（每拍一張要 2.5–3 秒），所以對照表只放
   兩格：`投卡前` 與 `回呼進到頁面那一刻`（零點那一張是真的，它是同步拍的）。
   中間那些 `want+150ms` 的檔照樣收進去**但不進對照表**，免得有人照著檔名讀。

⚠ `.webm`（每支 8–10 MB、而且這台機器只跑得出 1–2.6 fps）**不進 repo**。
   會動的對照看 `v2_clockstep/GIF_*.gif`（假時鐘，每一格的時間是真的）。
"""
import json, os, shutil
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "out")
DST = ("/Users/cosmopig/Documents/GitHub/Vacant/.claude/worktrees/wf_32a45899-6ee-1"
       "/ops/exhibit/twin/evidence_visible_20260921/arrival_beat/v3_wall_liveHEAD")
HM = os.path.expanduser("~/Documents/GitHub/vacant_hm/world3/index.html")
FONT = "/System/Library/Fonts/STHeiti Medium.ttc"
ARMS = ["W_after_0", "W_after_1", "W2_after", "W2_negctl_arrive0"]


def f(sz):
    try:
        return ImageFont.truetype(FONT, sz)
    except Exception:
        return ImageFont.load_default()


def anchor_shot(arm):
    d = os.path.join(SRC, arm)
    for n in sorted(os.listdir(d)):
        if n.startswith("shot__want+0ms"):
            return os.path.join(d, n)
    return None


def sheet(dest):
    rows = [("W2_after", "抵達層開（?arrive 預設）",
             "回呼那一刻右下角就有他的信＋陶牌「投遞口 ▲1」"),
            ("W2_negctl_arrive0", "負控制 ?arrive=0（抵達層關）",
             "同一份碼、同一條路徑，右下角什麼都沒有")]
    cols = [("shot__pre-500ms.jpg", "投卡前"),
            (None, "回呼進到頁面那一刻（頁面自己記的零點）")]
    cw = 560
    ch = int(cw * 9 / 16)
    pad, lab_w, head_h = 12, 400, 104
    W = lab_w + len(cols) * (cw + pad) + pad
    H = head_h + len(rows) * (ch + 34 + pad) + pad + 30
    im = Image.new("RGB", (W, H), (22, 18, 14))
    d = ImageDraw.Draw(im)
    d.text((pad, 12), "真時鐘臂：跑在**現在活著的那一份** index.html 上", font=f(28), fill=(240, 232, 216))
    d.text((pad, 50), "sha256[0:16]=" + SHA[:16] + " · 走完整產品路徑（寫快照 → bridge 輪詢 → "
           "onSubmission → arrivals）· 只放這兩格，中間那些檔名時間是假的", font=f(14), fill=(178, 166, 150))
    d.text((pad, 72), "⚠ 每拍一張要 2.5–3 秒（這台 load 300–900）⇒ 不要照 want+Nms 讀秒數；"
           "毫秒看 SUMMARY_WALL.json 的 callbackToPaintMs", font=f(14), fill=(214, 150, 120))
    x0 = lab_w + pad
    for i, (_, cap) in enumerate(cols):
        d.text((x0 + i * (cw + pad) + 2, head_h - 20), cap, font=f(15), fill=(228, 196, 130))
    y = head_h
    for arm, lab, note in rows:
        d.text((pad, y + 6), lab, font=f(19), fill=(240, 232, 216))
        d.text((pad, y + 36), note, font=f(14), fill=(178, 166, 150))
        for i, (fn, _) in enumerate(cols):
            p = os.path.join(SRC, arm, fn) if fn else anchor_shot(arm)
            x = x0 + i * (cw + pad)
            if p and os.path.exists(p):
                im.paste(Image.open(p).convert("RGB").resize((cw, ch), Image.LANCZOS), (x, y))
            else:
                d.rectangle([x, y, x + cw, y + ch], outline=(180, 60, 50), width=3)
                d.text((x + 14, y + 14), "這一臂沒拍到這一格（不是黑畫面）", font=f(16), fill=(230, 120, 100))
        y += ch + 34 + pad
    d.text((pad, H - 24), "負控制＝把同一層關掉；兩張畫面的差別就是這一層在展場做的事。",
           font=f(14), fill=(150, 140, 126))
    im.save(dest, quality=86)
    return os.path.getsize(dest)


SHA = ""
if __name__ == "__main__":
    import hashlib
    SHA = hashlib.sha256(open(HM, "rb").read()).hexdigest()
    os.makedirs(DST, exist_ok=True)
    kept = {}
    for a in ARMS:
        s = os.path.join(SRC, a)
        if not os.path.isdir(s):
            print("  ⚠ %s 整個不存在——**不要讀成 0，讀成沒跑**" % a)
            continue
        t = os.path.join(DST, a)
        os.makedirs(t, exist_ok=True)
        n = 0
        for fn in sorted(os.listdir(s)):
            if fn.endswith(".webm"):
                continue                      # 8–10 MB 且 1–2.6 fps，不進 repo
            if fn.endswith(".jpg") or fn == "probe.json":
                shutil.copy2(os.path.join(s, fn), os.path.join(t, fn))
                n += 1
        kept[a] = n
    shutil.copy2(os.path.join(SRC, "SUMMARY_WALL.json"), os.path.join(DST, "SUMMARY_WALL.json"))
    # 把主體 sha 補進 SUMMARY_WALL.json（w2_summary.py 寫的時候是 null）
    p = os.path.join(DST, "SUMMARY_WALL.json")
    doc = json.load(open(p, encoding="utf-8"))
    doc["subject_sha256_16"] = SHA[:16]
    doc["subject"] = "vacant_hm/world3/index.html（**這四臂跑的是現在活著的那一份**）"
    doc["video_not_in_repo"] = ("W2 兩臂有 .webm（8–10 MB，1–2.6 fps）留在 scratchpad，"
                                "沒進 repo；會動的對照看 ../v2_clockstep/GIF_*.gif")
    json.dump(doc, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sz = sheet(os.path.join(DST, "SHEET_wall_liveHEAD.jpg"))
    for t in ("w2_summary.py", "collect_wall.py", "mkgif.py"):
        shutil.copy2(os.path.join(HERE, t),
                     os.path.join(os.path.dirname(DST), "v2_clockstep", "tools", t))
    print("收進", DST)
    print(" 每臂檔數", kept, "· 對照表", round(sz / 1e6, 2), "MB · sha", SHA[:16])
