#!/usr/bin/env python3
"""展件素材總清單——一次跑完，無人值守。

設計理由，每一條都是實測換來的：

1. **序列跑，不並發。** `genimg.sh` 用「生圖池的差集」找新檔，兩個呼叫同時跑會
   撿到對方的圖——`floor_lower` 生歪疑似就是這樣來的。這支自己序列化，
   不依賴 genimg.sh 有沒有鎖。

2. **每張都帶完整的風格與配色規格。** 排圖之間不一致是已知的最大問題
   （三層看起來像三棟不同的樓）。逐字相同的「風格」段不夠——構圖控制不住，
   但**顏色與器物可以用文字釘死**，所以每個提示詞都重複同一份規格。

3. **跳過已存在的。** 中途斷掉可以直接重跑，不會重生。

4. **按優先序排。** 可能跑不完——所以先跑沒有它就做不出東西的，
   最後跑錦上添花的。跑不完時留下的是「缺變化」不是「缺主體」。

5. **逐筆落盤。** 每張的成敗、耗時、尺寸寫進 JSONL，明天可以直接對帳，
   不必翻 log。

用法：
    python3 asset_manifest.py            # 跑全部（跳過已存在）
    python3 asset_manifest.py --list     # 只列出清單不生成
    python3 asset_manifest.py --only P0  # 只跑某個優先層
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time

OUT = pathlib.Path.home() / "vacant/design/lib"
GENIMG = pathlib.Path.home() / "vacant/bin/genimg.sh"
LOG = pathlib.Path.home() / "vacant/design/lib_run.jsonl"

# ── 全域規格：每一個提示詞都會附上，讓不同批之間對得起來 ────────────
STYLE = """黏土定格動畫（Aardman／Laika 風格），手工捏塑的實體感、看得見指紋與拇指壓痕、
霧面質感、輕微不對稱。硬邊陰影，單一主光從正面中低角度打進來。"""

PALETTE = """**配色規格（每一張都必須照這個，不要自由發揮）**：
牆面上半＝暖磚紅（陶土色），牆面下半＝深鼠尾草綠護牆板，高度約牆高三分之一。
地板＝深棕色木板。天花板每格一盞白色圓形嵌燈。
家具＝深綠色金屬桌櫃、深棕木頭椅。
人物膚色＝暖米色。衣服**只能用這四色**：鏽紅、鼠尾草綠、灰紫、奶油白。"""

FACE = """人物是黏土偶：大眼睛、簡單的嘴、**沒有五官細節**、比例可愛。
**不要生成看起來像真實特定人物的臉。**"""

# 角色體型規格——重複使用，讓同一個型在不同動作間認得出來
ARCH = {
  # 十種體型。**剪影辨識度是展場距離下唯一還看得見的東西**——
  # three.js 版失敗就是因為 44 個人形剪影幾乎一樣（365/946 對難分）。
  # 所以差異要下在輪廓上（高矮、胖瘦、頭身比、有沒有頭髮、肩寬），
  # 不是只換衣服顏色。
  "stout":  "矮胖體型：身高偏矮、身體圓、鏽紅色上衣、深咖啡長褲、深棕色捲髮",
  "lanky":  "高瘦體型：很高、四肢細長、鼠尾草綠上衣、深灰長褲、稀疏的深色頭髮",
  "small":  "嬌小體型：矮小纖細、深藍色上衣、棕色長褲、蓬鬆的棕色頭髮",
  "round":  "圓潤體型：中等身高、身體很圓、灰紫色上衣、深綠長褲、光頭",
  "plain":  "中等體型：奶油白襯衫、深褐長褲、黑色短髮",
  "tall":   "高大體型：很高而且壯、肩膀寬、鏽紅色上衣、深灰長褲、深色平頭",
  "hunch":  "駝背體型：中等身高但背明顯彎、脖子前伸、灰紫色上衣、棕色長褲、灰白頭髮",
  "wiry":   "精瘦體型：中等身高、非常瘦、手長、鼠尾草綠上衣、黑色長褲、綁起來的深色頭髮",
  "broad":  "厚實體型：矮而寬、方形身材、奶油白上衣、深綠長褲、濃密的深棕捲髮",
  "slight": "纖細體型：偏矮、非常瘦、肩膀窄、深藍色上衣、灰色長褲、短瀏海",
}

SPRITE_FRAME = """**背景必須是純白色、完全空白，沒有地板、沒有牆、沒有影子投在背景上、
沒有任何道具。** 只有這一個角色本身，置中，全身入鏡，四周留一點白邊。
正面平視，攝影機不歪斜。均勻打光，不要戲劇性陰影。"""

ROW_FRAME = """**構圖**：建築剖面被水平切開，橫向並排六個小房間，隔間牆把它們分開。
正面平視，攝影機不歪斜。房間內部佔滿整個畫框，上下不要留大片空白。
橫幅構圖（約 16:9）。"""


def sprite(name, arch, action, prio):
    return {
        "name": f"sp_{arch}_{name}", "prio": prio, "cat": "角色",
        "prompt": f"一個黏土人偶，{ARCH[arch]}。{action}\n\n{SPRITE_FRAME}\n\n{FACE}\n\n風格：{STYLE}",
    }


def row(name, content, prio):
    return {
        "name": f"row_{name}", "prio": prio, "cat": "排圖",
        "prompt": f"{content}\n\n{ROW_FRAME}\n\n{PALETTE}\n\n{FACE}\n\n風格：{STYLE}",
    }


ITEMS: list[dict] = []

# ══ P0：沒有它就做不出東西 ═══════════════════════════════════════
# 背景排圖。每張至少留一間空房——空格是規格要求的視覺陳述，不是裝飾。
_ROWS = [
 ("work_a", "六個房間：①一人低頭寫字 ②一人坐著等 ③走廊上一人抱著一疊紙走路 "
            "④**空房間（桌椅都在、桌上一疊沒動過的紙、沒有人）** ⑤一人在翻檔案櫃 ⑥一人低頭寫字。"),
 ("work_b", "六個房間：①一人在翻檔案櫃 ②一人低頭寫字 ③**空房間（桌椅都在、沒有人）** "
            "④一人把一疊紙遞給隔壁房間 ⑤一人坐著等 ⑥走廊上一人抱著紙走路。"),
 ("work_c", "六個房間：①一人坐著等 ②走廊上一人抱著紙走路 ③一人低頭寫字 "
            "④一人在翻檔案櫃 ⑤**空房間（桌椅都在、沒有人）** ⑥**空房間（桌椅都在、沒有人）**。"),
 ("work_d", "六個房間：①兩人在同一間對著一份文件討論 ②一人低頭寫字 ③一人坐著等 "
            "④**空房間** ⑤走廊上一人抱著紙走路 ⑥一人在翻檔案櫃。"),
 ("work_e", "六個房間：①一人低頭寫字 ②**空房間** ③一人把一疊紙放到桌上就要離開 "
            "④一人在翻檔案櫃 ⑤一人坐著等 ⑥一人低頭寫字。"),
 ("work_f", "六個房間，**全部都是空房間**：桌椅都在、桌上有沒動過的紙、一個人也沒有。"),
]
for n, c in _ROWS:
    ITEMS.append(row(n, c, "P0"))

# 評審室：先前「一層樓」的構圖連續四次失敗，改成「一個寬房間」
ITEMS.append({"name": "row_review", "prio": "P0", "cat": "排圖",
  "prompt": "一個比較寬的房間的剖面，三個黏土人偶圍著一張深棕色木桌檢查一份文件："
            "左邊那個彎腰拿放大鏡湊近看，中間那個手上舉著木頭印章，右邊那個拿紅筆正要在文件上劃掉。"
            "桌上有一疊紙。背景牆上是一整面一格一格的紀錄卡櫃。\n\n"
            "正面平視，房間佔滿整個畫框，橫幅構圖。\n\n" + PALETTE + "\n\n" + FACE + "\n\n風格：" + STYLE})
ITEMS.append({"name": "row_corridor", "prio": "P0", "cat": "排圖",
  "prompt": "一條走廊的剖面，橫向貫穿整個畫面。三個黏土人偶在走廊上，各自抱著一疊紙往不同方向走。"
            "走廊兩側是關著的門。\n\n"
            "正面平視，走廊佔滿整個畫框，橫幅構圖。\n\n" + PALETTE + "\n\n" + FACE + "\n\n風格：" + STYLE})

# 十個體型 × 兩個最常出現的動作
for a in ARCH:
    ITEMS.append(sprite("carry", a, "站著，雙手抱著一疊紙，正在往前走。", "P0"))
    ITEMS.append(sprite("write", a, "坐著低頭寫字，手裡拿著筆。側身姿態。", "P0"))

# ══ P1：狀態機要完整 ═════════════════════════════════════════════
for a in ARCH:
    ITEMS.append(sprite("wait", a, "坐著，兩手放在桌上，什麼都沒做，在等待。", "P1"))
    ITEMS.append(sprite("submit", a, "站著，雙手把一疊紙往前遞出去，像在交件。", "P1"))
    # 手機端要的：他的臉。這是「你養的那一個」的主體。
    ITEMS.append(sprite("portrait", a, "半身特寫，正對鏡頭，兩手自然垂著，表情平靜。"
                        "只到腰部以上，臉佔畫面較大比例。", "P1"))

# 評審動作（評審是少數）
for a in ["lanky", "round", "plain", "hunch"]:
    ITEMS.append(sprite("magnify", a, "站著，一手舉著放大鏡湊近看，身體微微前傾。", "P1"))
    ITEMS.append(sprite("stamp", a, "站著，一手高舉木頭印章，正要蓋下去。", "P1"))
    ITEMS.append(sprite("redpen", a, "站著，一手拿紅筆往下劃，像在把東西劃掉。", "P1"))

# 被退件的反應
for a in ["stout", "small", "plain", "tall", "wiry"]:
    ITEMS.append(sprite("rejected", a, "站著，肩膀垂下來，低頭看著手上被退回來的紙，有點沮喪。", "P1"))

# ══ P2：排除那一刻 —— 展覽最重要的單一視覺陳述 ══════════════════
ITEMS += [
 {"name": "exit_chair", "prio": "P2", "cat": "排除",
  "prompt": "一個空房間的特寫：木頭椅子被推開離桌子有一段距離，桌上一疊紙沒有動過，"
            "牆上的紀錄卡格子全是空的。**沒有人。**光從正面打進來，椅子在地上留下硬邊影子。\n\n"
            + PALETTE + "\n\n風格：" + STYLE},
 {"name": "exit_walk", "prio": "P2", "cat": "排除",
  "prompt": "一個黏土人偶背對鏡頭，走向一扇打開的門，手上什麼都沒拿，肩膀微垂。"
            "他正在離開。\n\n" + SPRITE_FRAME + "\n\n" + FACE + "\n\n風格：" + STYLE},
 {"name": "exit_cell", "prio": "P2", "cat": "排除",
  "prompt": "一排六個房間，**中間那一間是空的**（桌椅在、沒有人），左右兩間都有人在工作。"
            "空的那間比較暗。\n\n" + ROW_FRAME + "\n\n" + PALETTE + "\n\n" + FACE + "\n\n風格：" + STYLE},
]

# 走路循環 × 四個體型（走廊上會走路的不只一種人）
_WALK = [
  "走路的第一格：左腳往前跨出、右腳在後，雙手抱著一疊紙。",
  "走路的第二格：兩腳接近併攏、身體略微抬高，雙手抱著一疊紙。",
  "走路的第三格：右腳往前跨出、左腳在後，雙手抱著一疊紙。",
  "走路的第四格：兩腳接近併攏、身體略微下沉，雙手抱著一疊紙。"]
for a in ["stout", "lanky", "small", "tall"]:
    for i, pose in enumerate(_WALK, 1):
        ITEMS.append(sprite(f"walk{i}", a, pose, "P2"))

# 紀錄卡牆的密度（信譽的視覺化）
for n, desc in [
  ("empty", "整面牆的紀錄卡格子全部是空的，只有空的木格子"),
  ("few", "整面牆的紀錄卡格子只有少數幾格貼著米色小卡，其餘是空的"),
  ("half", "整面牆的紀錄卡格子大約一半貼著米色小卡"),
  ("full", "整面牆的紀錄卡格子幾乎全部貼滿米色小卡，密密麻麻"),
  ("red", "整面牆的紀錄卡格子大約一半貼著米色小卡，其中三張被紅筆劃上叉")]:
    ITEMS.append({"name": f"wall_{n}", "prio": "P2", "cat": "紀錄牆",
      "prompt": f"一面牆的特寫：{desc}。牆是暖磚紅色，木頭格架。"
                f"正面平視，牆佔滿整個畫框。\n\n風格：{STYLE}"})

# 交付物本身的狀態（畫面上要看得出這一份現在怎麼了）
for n, desc in [
  ("paper_fresh", "一疊乾淨的米色紙，整齊疊著，放在深綠色桌面上"),
  ("paper_stamped", "一疊米色紙，最上面那張蓋著一個深色印章印記，放在深綠色桌面上"),
  ("paper_rejected", "一疊米色紙，最上面那張被紅筆劃了一個大叉，放在深綠色桌面上"),
  ("paper_flagged", "一疊米色紙被單獨放在一個木頭托盤上，跟旁邊其他紙分開，放在深綠色桌面上")]:
    ITEMS.append({"name": n, "prio": "P2", "cat": "交付物",
      "prompt": f"特寫：{desc}。淺景深，背景模糊。\n\n風格：{STYLE}"})

# 道具
ITEMS += [
 {"name": "prop_receipt", "prio": "P2", "cat": "道具",
  "prompt": "特寫：一隻黏土做的手拿著一張蓋了印章的紙質收據，紙上有一行一行的字跡與一個紅色蠟封。"
            f"淺景深，背景是模糊的深色。\n\n風格：{STYLE}"},
 {"name": "prop_stamp", "prio": "P2", "cat": "道具",
  "prompt": "特寫：一個木頭印章立在深綠色桌面上，旁邊有一個小印泥盒。"
            f"淺景深。\n\n風格：{STYLE}"},
 {"name": "prop_magnifier", "prio": "P2", "cat": "道具",
  "prompt": "特寫：一支黃銅框放大鏡放在一疊米色紙上面，深綠色桌面。"
            f"淺景深。\n\n風格：{STYLE}"},
]

def run(items, out_dir, log_path):
    out_dir.mkdir(parents=True, exist_ok=True)
    done = skipped = failed = 0
    t_all = time.time()
    for i, it in enumerate(items, 1):
        dst = out_dir / f"{it['name']}.png"
        if dst.exists() and dst.stat().st_size > 50_000:
            skipped += 1
            print(f"[{i}/{len(items)}] 跳過（已存在）{it['name']}", flush=True)
            continue
        t0 = time.time()
        print(f"[{i}/{len(items)}] {it['prio']} {it['cat']} {it['name']} …", flush=True)
        r = subprocess.run([str(GENIMG), str(dst), it["prompt"]],
                           capture_output=True, text=True)
        secs = round(time.time() - t0, 1)
        ok = dst.exists() and dst.stat().st_size > 50_000
        dims = ""
        if ok:
            try:
                import struct
                d = dst.open("rb").read(24)
                w, h = struct.unpack(">II", d[16:24])
                dims = f"{w}x{h}"
            except Exception:                                  # noqa: BLE001
                pass
        done += ok
        failed += (not ok)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": int(time.time()), "name": it["name"], "prio": it["prio"],
                "cat": it["cat"], "ok": ok, "secs": secs, "dims": dims,
                "kb": dst.stat().st_size // 1024 if ok else 0,
                "err": (r.stderr or "")[-300:] if not ok else None,
            }, ensure_ascii=False) + "\n")
        print(f"    {'✓' if ok else '✗'} {secs}s {dims}", flush=True)
    print(f"\n完成 {done}　跳過 {skipped}　失敗 {failed}　"
          f"總耗時 {round((time.time()-t_all)/60,1)} 分", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--only", default=None, help="P0 / P1 / P2")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()

    items = sorted(ITEMS, key=lambda x: (x["prio"], x["name"]))
    if a.only:
        items = [i for i in items if i["prio"] == a.only]

    if a.list:
        for p in ["P0", "P1", "P2"]:
            g = [i for i in items if i["prio"] == p]
            if g:
                print(f"\n{p}（{len(g)} 張）")
                for i in g:
                    print(f"  {i['cat']:4s} {i['name']}")
        print(f"\n總計 {len(items)} 張")
        sys.exit(0)

    run(items, pathlib.Path(a.out), LOG)
