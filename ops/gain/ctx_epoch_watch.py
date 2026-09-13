#!/usr/bin/env python3
"""每輪打一次 8766 的**唯讀**狀態，把 gemma 的 `loaded_context_length` 與當下的載入世代
記成一行——為了直接驗 H-E（`DECISION_20260904_R447_CTX400_ATTRIBUTION.md` §七）。

為什麼要用「攢的」：`/api/status` 只給**現在**的 loaded_context_length，
`/api/events` 只給 load/unload 的時刻、不給那次載入用了多大 context。
所以 H-E（每次載入的有效 context 不同）**只能前瞻性地攢**。零 API、零成本、唯讀。

判準（先寫死，round707）：
  - 攢到 **≥ 6 個不同世代**之後才判。
  - 出現任一世代 `loaded_context_length != 262144` ⇒ **H-E 直接證實**。
  - 6 個世代全是 262144 ⇒ H-E 的「載入時 VRAM 決定 context」這個版本被推翻，
    要回頭找別的機制（且要照實寫「推翻的是這個版本，不是 H-E 全部」）。

用法：python3 ops/gain/ctx_epoch_watch.py            # 追加一行到 runs/_ctx_epoch_watch.jsonl
      python3 ops/gain/ctx_epoch_watch.py --summary  # 看攢了幾個世代
"""
from __future__ import annotations
import argparse, json, pathlib, time, urllib.request

BASE = "http://100.119.113.56:8766"
OUT = pathlib.Path(__file__).resolve().parents[2] / "runs" / "_ctx_epoch_watch.jsonl"
MODEL = "gemma-4-12b-it-qat"


def get(path: str):
    with urllib.request.urlopen(BASE + path, timeout=20) as r:
        return json.loads(r.read())


def sample() -> dict:
    st = get("/api/status")
    ev = get("/api/events?limit=50")
    loads = [e["ts"] for e in ev["events"] if e["event"] == "loaded" and e["model"] == MODEL]
    m = None
    for mach in st["machines"]:
        for mm in mach.get("models") or []:
            if mm["id"] == MODEL and mm.get("state") == "loaded":
                m = {"machine": mach["name"], "loaded_context_length": mm.get("loaded_context_length"),
                     "max_context_length": mm.get("max_context_length")}
    return {"ts": time.time(), "epoch_loaded_ts": max(loads) if loads else None,
            "model_state": m, "server_time": st["server_time"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args()
    if not a.summary:
        rec = sample()
        with OUT.open("a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(json.dumps(rec, ensure_ascii=False))
    if OUT.exists():
        recs = [json.loads(l) for l in OUT.open() if l.strip()]
        by = {}
        for r in recs:
            if r["epoch_loaded_ts"] is not None and r["model_state"]:
                by.setdefault(r["epoch_loaded_ts"], set()).add(r["model_state"]["loaded_context_length"])
        print(f"樣本 {len(recs)} 筆／不同世代 {len(by)} 個（判準：≥6 個世代才判）")
        for k in sorted(by):
            print(f"  epoch_loaded_ts={k:.0f}  loaded_context_length={sorted(by[k], key=str)}")
        vals = {v for s in by.values() for v in s}
        if len(by) >= 6:
            print("判決:", "H-E_CONFIRMED（有世代不是 262144）" if vals != {262144}
                  else "H-E_VRAM_VERSION_REFUTED（六個世代全 262144；推翻的是這個版本不是 H-E 全部）")
        else:
            print("判決: 世代數不足，尚不可判")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
