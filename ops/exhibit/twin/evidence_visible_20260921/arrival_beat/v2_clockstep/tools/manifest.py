#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把這一批量測收成一份機器可讀的清單（沒量到的欄位寫 null，不寫 0）。"""
import hashlib, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
HM = os.path.expanduser("~/Documents/GitHub/vacant_hm")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 16), b""):
            h.update(b)
    return h.hexdigest()


def git(*a):
    try:
        return subprocess.run(["git", "-C", HM, *a], capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception as e:
        return "（取不到：%s）" % str(e)[:80]


def load(name, fn):
    p = os.path.join(OUT, name, fn)
    if not os.path.exists(p):
        return None
    return json.load(open(p, encoding="utf-8"))


def main():
    m = {
        "what": "抵達層（arrivals）＝「觀眾按下送出的那一秒，畫面必須動」的可視化量測",
        "when": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "machine": {"loadavg_now": list(os.getloadavg()),
                    "note": "同一批有十幾個 agent 在跑，實測 load 500–1000。"
                            "所有牆上時鐘的端到端數字都被這一點壓住，"
                            "**不可以拿去代表展場機**。"},
        "subject": {
            "file": "vacant_hm/world3/index.html",
            "sha256_at_measure": sha(os.path.join(HM, "world3", "index.html")),
            "git_head": git("rev-parse", "HEAD"),
            "git_branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(git("status", "--porcelain", "world3/index.html")),
            "warning": "這個檔同時被別的 agent 改（MARK 標示層、SIMPLE 精簡模式）。"
                       "sha256 記的是量測當下的整份檔，不是只有抵達層。",
        },
        "revert": "一行還原：網址加 `?arrive=0`（ARRIVE_ON=false ⇒ arrive()／update()／draw() 全部提早 return）",
        "arms": {},
        "wallclock": [],
    }
    for name in ("S01_before_single", "S02_after_single", "S03_negctl_arrive0",
                 "S04_after_triple", "S05_before_triple"):
        j = load(name, "strip.json")
        if not j:
            m["arms"][name] = None
            continue
        m["arms"][name] = {
            "arm": j.get("arm"), "url": j.get("url"), "n_subs": j.get("n_subs"),
            "anchorFound": j.get("anchorFound"),
            "warmRealSec": j.get("warmRealSec"),
            "loadavg_at_end": j.get("loadavg_at_end"),
            "postArrivals": (j.get("postState") or {}).get("arrivals"),
            "frames": [f["file"] for f in j.get("frames", [])],
            "frameStates": [{"ms": f["virtualMs"], "state": f.get("state")}
                            for f in j.get("frames", [])],
            "console": j.get("console"),
        }
    for i in range(6):
        j = load("W_after_%d" % i, "probe.json")
        if j:
            m["wallclock"].append({
                "out": j.get("out"), "latency": j.get("latency"),
                "pollGapsMs": j.get("pollGapsMs"),
                "fpsAroundEvent": j.get("fpsAroundEvent"),
                "fpsWholeRun": j.get("fpsWholeRun"),
                "loadavg": j.get("loadavg"),
            })
    cp = [x["latency"][0]["callbackToPaintMs"] for x in m["wallclock"]
          if x.get("latency") and x["latency"][0].get("callbackToPaintMs") is not None]
    m["headline"] = {
        "callbackToPaintMs_wallclock": sorted(cp) or None,
        "callbackToPaintMs_median": (sorted(cp)[len(cp) // 2] if cp else None),
        "writeToPaintMs_note": "端到端＝輪詢間隔＋這一層。輪詢是 bridge.js 的，"
                               "設定 1000 ms，但這台機器餓到中位 4–11 秒 ⇒ "
                               "端到端在這裡量不準，**不寫成結論**。",
    }
    p = os.path.join(OUT, "manifest.json")
    json.dump(m, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(m["headline"], ensure_ascii=False))
    print("wrote", p)


if __name__ == "__main__":
    main()
