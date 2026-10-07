#!/usr/bin/env python3
"""Haiku 盲評題目：把離線重組的 24 張卡的第 2–4 行逐行抽出，混入已知殘句（負控制）與完整句（正控制），三種亂序給三位評審。
只問：這一行是不是完整、通順的一句中文（是／否＋哪裡斷）。"""
import json, pathlib, random, sys
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[4]))
sys.path.insert(0, str(HERE.parent.parent.parent.parent.parent))
rows = json.loads((HERE / "cards_offline.json").read_text(encoding="utf-8"))
items = []
for r in rows:
    for ln in r["lines"][1:]:
        items.append({"src": f"{r['id']}", "kind": "card", "text": ln})
NEG = [("它心裡想：", "讓那封信裡沉重的、沒說出口的情感"), ("試完它說：", "雖然沒有聽到預想中的旋律，但這種構造被撥動後的反應"),
       ("試完它說：", "他想面對債務，而我給他的這個動作"), ("試完它說：", "雖然種子還沒動彈，但看到那些邏輯線條與這艘靜止的船結合在一起"),
       ("它試了：", "點數單對齊紀錄"), ("它試了，", "現在放著這個帶有沙金質感的紙團"), ("它試了：", "把那張紙放在"),
       ("試完它說：", "那種緊繃的感覺"), ("它試了：", "在草稿角那面刻有高低線的石壁上"), ("它心裡想：", "讓盒子裡那根斷掉的齒")]
POS = [("它試了：", "把補片塞進了碗口的缺口裡"), ("試完它說：", "那個斷掉的字現在完整了"), ("它心裡想：", "讓碗口缺了三角的陶碗重新完整"),
       ("它試了：", "把長椅上的紙筒拿走了，現在長椅中間是空的"), ("試完它說：", "它終於有了正確的位置，這讓我安心了許多"), ("它試了：", "盒子發出了「咚」一聲")]
for a, b in NEG: items.append({"src": "ctl", "kind": "neg", "text": a + b})
for a, b in POS: items.append({"src": "ctl", "kind": "pos", "text": a + b})
for i, it in enumerate(items): it["id"] = f"L{i:03d}"
(HERE / "judge" / "key.json").write_text(json.dumps(items, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
HEAD = ("下面是一些從卡片上抽出來的單獨一行中文（含行首的短前綴，如「它心裡想：」）。請你**逐行**判斷：這一行的內容（前綴之後的部分）"
        "是不是一句**完整、通順**的中文？完整＝有主語（或省略得自然）、有動詞、語意收得住，讀完不會覺得「話沒說完」或「少了一半」。"
        "不要管內容好不好、對不對，只管句子有沒有講完。\n輸出格式（每行一筆，不要別的字）：\nID<TAB>是或否<TAB>若否，一句話說哪裡斷（若是，寫「-」）\n\n")
for k in range(3):
    order = items[:]
    random.Random(100 + k).shuffle(order)
    (HERE / "judge" / f"prompt_rater{k+1}.txt").write_text(HEAD + "\n".join(f"{it['id']}\t{it['text']}" for it in order) + "\n", encoding="utf-8")
print(len(items), "items")
