"""「排隊那幾團土到底有沒有在動」——量出來，不是用眼睛講的。

判準：相鄰兩格在同一塊區域的**平均絕對灰階差**（0..255）。
五條線一起看，缺任何一條這個數字就沒有意義：

  q_left / q_right  排隊那兩團（這一輪要證明的東西）
  clay_center       中央成形那一位（已知會動，**正對照組**）
  floor_front       同一個景深帶上的空地板 —— **空間對照組**（膠捲顆粒底噪）
  ambient           左上暗牆 —— 第二個空間對照組
  frozen            同一格重複 —— **這把尺自己的負控制**，必須是 0

⚠ `q_left` 的上緣會掃到一位站著的居民的腳。所以量測框從土團頂端下面一點開始
  （y=866 而不是 838），而且**兩團都量**：如果只有左邊在動，那動的是那雙腳。

用法：python3 r3_motion.py <幀目錄> <輸出 json> [起算秒數]
"""
import json, os, sys
from PIL import Image

d = sys.argv[1]
out = sys.argv[2]
FROM_S = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0

REG = {
    "q_left":      (555, 866, 160, 52),
    "q_right":     (1201, 866, 160, 52),
    "clay_center": (845, 720, 240, 190),
    "floor_front": (140, 930, 200, 60),
    "ambient":     (40, 300, 220, 140),
}

fr = json.load(open(os.path.join(d, "frames.json")))
t0 = fr[0]["t"]
fr = [e for e in fr if e["t"] - t0 >= FROM_S]
if len(fr) < 10:
    sys.exit(f"frames too few after cut: {len(fr)}")


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

one = load(fr[len(fr) // 2]["name"])
x, y, w, h = REG["q_left"]
a = one.crop((x, y, x + w, y + h)).tobytes()
frozen = sum(abs(p - q) for p, q in zip(a, a)) / len(a)


def stat(v):
    s = sorted(v)
    return {"n": len(v), "min": round(s[0], 4), "median": round(s[len(s) // 2], 4),
            "max": round(s[-1], 4), "mean": round(sum(v) / len(v), 4),
            "frames_below_0.5": sum(1 for x in v if x < 0.5)}


res = {
    "source_dir": os.path.basename(d),
    "window_from_s": FROM_S,
    "frames": len(fr),
    "span_s": round(fr[-1]["t"] - fr[0]["t"], 2),
    "capture_fps": round((len(fr) - 1) / (fr[-1]["t"] - fr[0]["t"]), 2),
    "regions": {k: stat(v) for k, v in series.items()},
    "frozen_negative_control": round(frozen, 6),
    "verdict": None,
}
ql, qr = res["regions"]["q_left"], res["regions"]["q_right"]
flr = res["regions"]["floor_front"]
ok = (res["frozen_negative_control"] == 0
      and ql["min"] > 0.5 and qr["min"] > 0.5
      and ql["median"] > flr["median"] * 1.5
      and qr["median"] > flr["median"] * 1.5)
res["verdict"] = "QUEUE_MOVING" if ok else "INCONCLUSIVE"
json.dump(res, open(out, "w"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
