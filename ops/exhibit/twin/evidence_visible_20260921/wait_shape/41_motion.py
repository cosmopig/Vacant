"""「它到底有沒有在動」——量出來，不是用眼睛講的。

判準：相鄰兩格在同一塊區域的**平均絕對灰階差**（0..255）。
三條線一起看，缺一條這個數字就沒有意義：

  clay    他那一團（整段等待態的主體）
  ambient 畫面左上角那塊暗牆 —— **空間對照組**。整頁有底噪（膠捲顆粒、
          場景影片），所以「非零」本身不代表有東西在動；clay 要明顯高過它。
  frozen  把同一格重複 40 次算出來的值 —— **這把尺自己的負控制**。
          它必須是 0；不是 0 就代表這個量法本身在說謊。
"""
import json, os, sys
from PIL import Image

d = sys.argv[1]
out = sys.argv[2]
REG = {
    # x, y, w, h（1920×1080 全幀座標）
    "clay":    (845, 720, 240, 190),   # 黏土團＋成形中的輪廓
    "ambient": (40, 300, 220, 140),    # 左上暗牆：沒有任何等待態元素
}
fr = json.load(open(os.path.join(d, "frames.json")))
if len(fr) < 10:
    sys.exit("frames too few")


def load(n):
    im = Image.open(os.path.join(d, n)).convert("L")
    if im.size != (1920, 1080):
        im = im.resize((1920, 1080))
    return im


series = {k: [] for k in REG}
prev = load(fr[0]["name"])
for e in fr[1:]:
    cur = load(e["name"])
    for k, (x, y, w, h) in REG.items():
        a = prev.crop((x, y, x + w, y + h)).tobytes()
        b = cur.crop((x, y, x + w, y + h)).tobytes()
        series[k].append(sum(abs(p - q) for p, q in zip(a, b)) / len(a))
    prev = cur

# 負控制：同一格重複
one = load(fr[len(fr) // 2]["name"])
x, y, w, h = REG["clay"]
a = one.crop((x, y, x + w, y + h)).tobytes()
frozen = sum(abs(p - q) for p, q in zip(a, a)) / len(a)


def stat(v):
    s = sorted(v)
    return {"n": len(v), "min": round(s[0], 4), "median": round(s[len(s) // 2], 4),
            "max": round(s[-1], 4), "mean": round(sum(v) / len(v), 4),
            "frames_below_0.5": sum(1 for x in v if x < 0.5)}


res = {
    "source_dir": os.path.basename(d),
    "frames": len(fr),
    "span_s": round(fr[-1]["t"] - fr[0]["t"], 2),
    "capture_fps": round((len(fr) - 1) / (fr[-1]["t"] - fr[0]["t"]), 2),
    "regions": {k: stat(v) for k, v in series.items()},
    "frozen_negative_control": round(frozen, 6),
    "verdict": None,
}
c, amb = res["regions"]["clay"], res["regions"]["ambient"]
ok = (res["frozen_negative_control"] == 0
      and c["min"] > 0.5
      and c["median"] > amb["median"] * 1.5)
res["verdict"] = "MOVING" if ok else "INCONCLUSIVE"
json.dump(res, open(out, "w"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
