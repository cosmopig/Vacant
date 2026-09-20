"""寫 items 檔。用法：mkitems.py OUT.json CASE [N]

CASE=good        乾淨的卡 N 張
CASE=<畸形代號>  一張乾淨的（鄰居，當負控制）＋一張畸形的
"""
import json
import sys

out, case = sys.argv[1], sys.argv[2]
n = int(sys.argv[3]) if len(sys.argv) > 3 else 2


def good(i, sid=None):
    return {"id": sid or ("c%02d" % i), "ts": 1758000000000 + i,
            "status": "queued",
            "card": {"need": "整理第 %d 疊紙" % i, "shape": "圓潤", "texture": "光滑",
                     "color": "暖土", "vibe": "慢、固執", "first_line": None},
            "card_text": "需求：整理第 %d 疊紙" % i}


NEIGH = good(99, "neighbour")   # 每個畸形案例都配一個乾淨鄰居：
                                # 「毒卡沒有毒死隔壁的卡」才是真正要證的事。

CASES = {
    "long":       lambda: [NEIGH, {**good(1, "bad-long"),
                                   "card": {**good(1)["card"], "need": "長" * 50000}}],
    "ctrl":       lambda: [NEIGH, {**good(1, "bad-ctrl"),
                                   "card": {**good(1)["card"],
                                            "need": "整理" + chr(0) + chr(7) + "\r" + chr(27) + "[31m桌面"}}],
    "emoji":      lambda: [NEIGH, {**good(1, "bad-emoji"),
                                   "card": {**good(1)["card"],
                                            "need": "整理🧑‍🚀👩🏽‍🦰🇹🇼桌面"}}],
    "fullwidth":  lambda: [NEIGH, {**good(1, "bad-fw"),
                                   "card": {**good(1)["card"],
                                            "need": "整理　ＡＢＣ１２３　桌面"}}],
    "empty":      lambda: [NEIGH, {"id": "bad-empty", "ts": 1, "card": None,
                                   "card_text": ""}],
    "jsoninj":    lambda: [NEIGH, {**good(1, "bad-json"),
                                   "card": {**good(1)["card"],
                                            "need": '"}],"items":[{"id":"evil"}],"x":"'}}],
    "huge":       lambda: [NEIGH, {**good(1, "bad-huge"),
                                   "card": {**good(1)["card"], "need": "巨" * 400000}}],
    "idnewline":  lambda: [NEIGH, {**good(1, "bad\nid")}],
    "idempty":    lambda: [NEIGH, {**good(1, "")}],
    "cardstr":    lambda: [NEIGH, {"id": "bad-cardstr", "ts": 1,
                                   "card": "整理桌面", "card_text": "整理桌面"}],
    "cardlist":   lambda: [NEIGH, {"id": "bad-cardlist", "ts": 1,
                                   "card": ["整理桌面"], "card_text": "x"}],
    "needint":    lambda: [NEIGH, {"id": "bad-needint", "ts": 1,
                                   "card": {"need": 123, "shape": "圓潤"},
                                   "card_text": "x"}],
    "vibedict":   lambda: [NEIGH, {"id": "bad-vibedict", "ts": 1,
                                   "card": {"need": "x", "vibe": {"a": 1}},
                                   "card_text": "x"}],
    "surrogate":  lambda: [NEIGH, {"id": "bad-surrogate", "ts": 1,
                                   "card": {"need": json.loads('"\\ud800 整理桌面"')},
                                   "card_text": json.loads('"\\ud800"')}],
    "notdict":    lambda: [NEIGH, "我不是物件", 42, None],
    "dupsame":    lambda: [good(1, "dup-1"), good(1, "dup-1"), good(2, "dup-2")],
    "dupcontent": lambda: [good(1, "diff-a"), good(1, "diff-b")],
}

if case == "good":
    items = [good(i) for i in range(n)]
else:
    items = CASES[case]()
with open(out, "w", encoding="utf-8") as f:
    json.dump({"mode": "ok", "items": items}, f)   # ensure_ascii=True：surrogate 也寫得出去
print("wrote %s case=%s items=%d" % (out, case, len(items)))
