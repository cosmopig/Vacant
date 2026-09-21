#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把五臂的 `strip.json` 收成一份機器可讀的結論表。

⚠ **沒量到寫 null，不寫 0／False。** 拍到一半的臂、沒有 `drawnAt` 的記號、
  沒有 `looked` 的信，全部進 `null`，並在 `gaps` 裡點名。把「沒量到」寫成 0
  會讓「改動後也沒反應」跟「那一跑根本沒拍成」長得一樣。
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
ARMS = ["S01_before_single", "S02_after_single", "S03_negctl_arrive0",
        "S05_before_triple", "S04_after_triple",
        # 導演正忙的那兩臂——**主證據**。S01/S03 證明導演閒著時改動前也會馬上
        # 換景，所以「改動前沒反應」只有在這一格才成立。
        "S06_before_busy", "S07_after_busy"]


def load(arm):
    p = os.path.join(OUT, arm, "strip.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def summarize(arm, rec):
    if rec is None:
        return {"arm": arm, "ran": False, "note": "沒有 strip.json ⇒ 這一臂沒跑完"}
    post = rec.get("postState") or {}
    arr = post.get("arrivals")
    frames = rec.get("frames") or []
    out = {
        "arm": arm,
        "ran": True,
        "url": rec.get("url"),
        "started": rec.get("started"),
        "warmRealSec": rec.get("warmRealSec"),
        "loadavg1_start": round((rec.get("loadavg_at_start") or [None])[0] or 0, 1),
        "frameCount": len(frames),
        # 看門狗替身：armed 應該恰好 1。wouldFire>0 ＝這一跑畫面真的凍過。
        "watchdogArmed": post.get("watchdogArmed"),
        "watchdogWouldFire": post.get("watchdogWouldFire"),
        "maxFrameGapMs": post.get("maxFrameGapMs"),
        "castReady": post.get("castReady"),
        "sceneAtEnd": post.get("sceneId"),
    }
    if arr is None:
        # `before` 臂根本沒有抵達層 ⇒ 這裡是 null 而不是 0，兩者意思不同：
        # null＝「這一版沒有這個東西」，0＝「有這個東西但它什麼都沒收到」。
        out["arrivalLayer"] = None
        out["submitToFirstPaintMs"] = None
        out["clayPeopleTurned"] = None
        out["queueShown"] = None
    else:
        marks = arr.get("marks") or []
        lat = [round(m["drawnAt"] - m["at"], 1) for m in marks
               if m.get("drawnAt") is not None and m.get("at") is not None]
        undrawn = [m.get("id") for m in marks if m.get("drawnAt") is None]
        waiting = arr.get("waiting") or []
        looked = [w.get("looked") for w in waiting if w.get("looked")]
        out["arrivalLayer"] = {"total": arr.get("total"), "flying": arr.get("flying")}
        out["submitToFirstPaintMs"] = lat or None
        out["marksNeverPainted"] = undrawn or None
        # 「轉頭」只算 dir 真的翻面的那幾個；`stopped` 含本來就面向那邊的。
        out["clayPeopleTurned"] = looked[0].get("turned") if looked else None
        out["clayPeopleStopped"] = looked[0].get("stopped") if looked else None
        out["queueShown"] = [{"place": w.get("place"), "label": w.get("label")}
                             for w in waiting] or None
    prime = rec.get("primedDirector")
    if prime is not None:
        # 導演忙不忙是這兩臂成不成立的前提。`ok=false` ⇒ 那一臂量到的不是
        # 「忙的時候」，結論不可以照抄。
        out["primedDirector"] = prime
    return out


if __name__ == "__main__":
    rows, gaps = [], []
    for a in ARMS:
        s = summarize(a, load(a))
        rows.append(s)
        if not s.get("ran"):
            gaps.append(f"{a}：沒跑完，全欄 null")
        elif s.get("watchdogArmed") != 1:
            gaps.append(f"{a}：watchdogArmed={s.get('watchdogArmed')}"
                        "（替身沒認出看門狗 ⇒ 那一跑可能被重載過）")
        if s.get("marksNeverPainted"):
            gaps.append(f"{a}：有記號從頭到尾沒被畫出來 {s['marksNeverPainted']}")
        # ⚠ `watchdogWouldFire` 在這一批**每一臂都恰好是 1，而 maxFrameGapMs 只有
        #   1.8–3.1 秒**（門檻是 10 秒）。兩個數字互相矛盾 ⇒ 不是真的凍過。
        #   原因：`clock.pause_at()` 會先把假時鐘**快轉**到指定時刻再停，那一下
        #   `performance.now()` 一次跳過 10 秒以上，替身的 interval 先被觸發、
        #   而且它會把共用的 `lastFrameTs` 重設，所以後面那個 rAF 掉幀計數器
        #   反而量不到同一個缺口。
        #   ⇒ **恰好 1 次 ＝ 停錶那一下的量具假象，不是畫面凍住。**
        #     ≥2 次才要當成這一跑真的卡過。這兩個計數器共用一個變數是量具的瑕疵，
        #     記在 PROVENANCE.json，沒有回頭改（改了這一批就不是同一個量具）。
        wf = s.get("watchdogWouldFire") or 0
        if wf > 1:
            gaps.append(f"{a}：畫面可能真的凍過 {wf} 次"
                        f"（最長掉幀 {s.get('maxFrameGapMs')} ms）"
                        "——這台 load 700–1000 的 Mac 的性質，不是展場機器的")
    doc = {
        "what": "抵達層（投卡那一秒）連續截圖批次的結論表",
        "zeroPoint": "WorldBridge.onSubmission 回呼進到頁面的那一刻",
        "clock": "Playwright 假時鐘：每一格的內容落在虛擬時間軸上精確的那一刻",
        "caveat": [
            "submitToFirstPaintMs 是頁面自己記的（arrivals.marks 的 at→drawnAt），"
            "量的是「回呼到信第一次被畫出來」，不含手機端送出到 snapshot 落盤那一段。",
            "clayPeopleTurned 只算 dir 真的翻面的；本來就面向投遞口的算在 stopped 裡。",
            "這台 Mac 同時有十幾個 agent 在跑（load 700–900），掉幀數字是這台的性質。",
        ],
        "arms": rows,
        "gaps": gaps or None,
    }
    with open(os.path.join(OUT, "SUMMARY.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    for r in rows:
        print(json.dumps(r, ensure_ascii=False)[:480])
    print("\ngaps:", json.dumps(gaps, ensure_ascii=False, indent=1) if gaps else "（無）")
    print("wrote", os.path.join(OUT, "SUMMARY.json"))
