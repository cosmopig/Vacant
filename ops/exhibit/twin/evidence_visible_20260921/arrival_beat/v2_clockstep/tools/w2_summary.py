#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 wall-clock（真時鐘）那幾臂的關鍵欄位印出來／收成一份 SUMMARY_WALL.json。

⚠ 這一批**不可以**拿連續截圖的檔名時間來講「第幾毫秒」：這台機器 load 300–900，
   Playwright 每拍一張要 2.5–3 秒，`want+150ms` 那一張的 `real` 是 +2811ms。
   能讀的只有頁面自己記的 `latency`（marks 的 at／drawnAt）與「那封信在不在畫面上」。
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
ARMS = ["W_after_0", "W_after_1", "W2_after", "W2_negctl_arrive0"]

rows = []
for d in ARMS:
    p = os.path.join(OUT, d, "probe.json")
    if not os.path.exists(p):
        rows.append({"arm": d, "ran": False})
        continue
    r = json.load(open(p, encoding="utf-8"))
    post = r.get("postState") or {}
    A = post.get("arrivals")
    lat = r.get("latency")
    rows.append({
        "arm": d,
        "ran": True,
        "url": r.get("url"),
        "started": r.get("started"),
        "loadavg1_start": round(r["loadavg"][0], 1) if r.get("loadavg") else None,
        "anchor": r.get("anchor"),
        "latency": lat,
        "writeToCallbackMs": [x.get("writeToCallbackMs") for x in lat] if lat else None,
        "callbackToPaintMs": [x.get("callbackToPaintMs") for x in lat] if lat else None,
        "writeToPaintMs": [x.get("writeToPaintMs") for x in lat] if lat else None,
        "arrivalsTotal": (A or {}).get("total") if A is not None else None,
        "queueShown": [{"place": w.get("place"), "label": w.get("label"),
                        "tok": w.get("tok"), "looked": w.get("looked")}
                       for w in ((A or {}).get("waiting") or [])] or None,
        "fpsWholeRun": r.get("fpsWholeRun"),
        "fpsAroundEvent": r.get("fpsAroundEvent"),
        "pollGapsMs": r.get("pollGapsMs"),
        "video": r.get("video"),
        "shotsRealMs": [s.get("real") for s in (r.get("shots") or [])] or None,
        "console": r.get("console"),
    })

doc = {
    "what": "真時鐘（wall-clock）臂：端到端走產品路徑（寫快照 → bridge 輪詢 → onSubmission → arrivals）",
    "subject_sha256_16": None,
    "read_this_first": [
     "**連續截圖的檔名時間在這一批是假的。** 這台 Mac 同時十幾個 agent 在跑，"
     "Playwright 拍一張要 2.5–3 秒 ⇒ want+150ms 那一張的 real 是 +2811ms。"
     "要看第幾毫秒請看 `callbackToPaintMs`（頁面自己記的），不要看檔名。",
     "`writeToCallbackMs` 是 **bridge.js 輪詢那一層**的延遲，不是這次改的那一層。"
     "設定值 1000 ms，這台機器實測中位 2.7–6.1 秒（被餓到）。展場機（1003）不是這台，"
     "**這個數字不可以拿去說展場會等幾秒**。",
     "負控制 `?arrive=0` 同一份碼、同一條路徑，只把抵達層關掉。",
    ],
    "arms": rows,
}
with open(os.path.join(OUT, "SUMMARY_WALL.json"), "w", encoding="utf-8") as f:
    json.dump(doc, f, ensure_ascii=False, indent=1)
print(json.dumps(doc, ensure_ascii=False, indent=1))
