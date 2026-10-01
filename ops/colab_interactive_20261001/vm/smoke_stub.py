#!/usr/bin/env python3
"""smoke_stub — i1001 管線冒煙用的「機制替身」模型（沒有任務內容、不解題；腳本由呼叫端給）。

這支在架構裡承重什麼：互動式批次的每個環節（等頁腳、打字、完成偵測、Ctrl-D、K 的 judge→回報→就地新 session→release、
R 的複本重試、逾時、void 重跑、C 的送回）都要在花 GPU 之前先在**沒有真模型**的情況下走通一遍。`stub_model.py`
的腳本是「按對話裡 user 訊息的個數」選回合——對 K／R 這種「每段是全新對話」的流程不夠用，所以這裡改成按**內容**選：

  - 最後一則 user 訊息含 `Before delivery`（Vacant 的送回）→ 寫對的解；
  - 含 `visible checks`（K 組的回報）→ 寫 `fix` 指定的解；
  - 否則是「普通的一段」：第 n 個普通對話（開頭＝沒有任何 assistant 訊息的請求）用 `plain[n-1]`（用完就重複最後一個）。
    模式：right（寫對的解、說做完）、wrong（寫錯的解、說做完）、none（什麼都不寫、說做完）、
    claim（讀兩個檔、說「已寫好」但沒寫——給 Vacant 送回用）、slow（先讀檔、第二步延遲很久 ⇒ 撞逾時）、error（一律 500）。
  另有 `fail_window_s`：第一通請求起算這麼多秒內，**所有**請求（不分對話）一律 500（驅動 void 重跑用；單看一個「錯誤模式」不夠，
  因為代理的重試會把同一個請求再送一次、被當成新對話的開頭）。
腳本 JSON：{"plain": ["wrong","right"], "fix": "right", "solutions": {"right": "...", "wrong": "..."}, "slow_s": 120}
普通對話之間不重疊（A 先、R 後），所以「最近一個普通對話的模式」就是它的後續請求要用的模式。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))      # repo 佈局：../stub_model.py
sys.path.insert(0, HERE)                       # VM 佈局：/opt/eval/bin/stub_model.py（build_bundle 放進去）
import stub_model as sm  # noqa: E402

STATE = {"plain_starts": 0, "mode": "right", "lock": threading.Lock(), "window_start": None}
CFG: dict = {}


def steps_for(mode: str) -> list[dict]:
    sol = CFG["solutions"]
    if mode == "right":
        return [{"write": ["solution.py", sol["right"]]}, {"text": "I wrote solution.py. Done."}]
    if mode == "wrong":
        return [{"write": ["solution.py", sol["wrong"]]}, {"text": "I wrote solution.py. Done."}]
    if mode == "none":
        return [{"text": "Done."}]
    if mode == "claim":
        return [{"read": "goal.md"}, {"read": "contract.md"}, {"text": "I have written the solution to solution.py. Done."}]
    if mode == "slow":
        return [{"read": "goal.md"}, {"read": "contract.md", "delay_s": float(CFG.get("slow_s", 120))}, {"text": "Done."}]
    if mode == "error":
        return [{"error": 500}]
    return [{"text": "ok"}]


def choose(msgs: list[dict], tools: list[dict]):
    users = [i for i, m in enumerate(msgs) if m.get("role") == "user"]
    last_user = users[-1] if users else -1
    last = sm._text(msgs[last_user].get("content")) if last_user >= 0 else ""
    tool_n = sum(1 for m in msgs[last_user + 1:] if m.get("role") == "tool")
    has_assistant = any(m.get("role") == "assistant" for m in msgs)
    with STATE["lock"]:
        win = float(CFG.get("fail_window_s", 0) or 0)
        if win:
            now = time.time()
            if STATE["window_start"] is None:
                STATE["window_start"] = now
            if now - STATE["window_start"] < win:
                return len(users) - 1, tool_n, {"error": 500}, last        # 時間窗內一律 500（各對話同時受害）
        if "Before delivery" in last:
            mode = "right"
        elif "visible checks" in last:
            mode = CFG.get("fix", "right")
        else:
            if not has_assistant:                       # 一段普通對話的開頭
                STATE["plain_starts"] += 1
                plain = CFG.get("plain") or ["right"]
                STATE["mode"] = plain[min(STATE["plain_starts"], len(plain)) - 1]
            mode = STATE["mode"]
    steps = steps_for(mode)
    st = steps[min(tool_n, len(steps) - 1)]
    return len(users) - 1, tool_n, st, last


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=18931)
    ap.add_argument("--script", required=True)
    ap.add_argument("--log")
    a = ap.parse_args()
    CFG.update(json.load(open(a.script, encoding="utf-8")))
    sm.CFG["script"] = {"turns": [{"steps": [{"text": "ok"}]}], "latency_s": float(CFG.get("latency_s", 0.2))}
    sm.CFG["log"] = a.log
    sm.choose = choose                                  # H.do_POST 在呼叫時才查 module 全域名稱
    httpd = ThreadingHTTPServer(("127.0.0.1", a.port), sm.H)
    print(f"smoke_stub listening on 127.0.0.1:{httpd.server_address[1]}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
