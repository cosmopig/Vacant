#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""30 格的收尾原因普查。**衍生物、零模型呼叫**，來源＝逐位元落盤的 `*.resp.bin`。
為什麼要有這一份：11 個拒交格裡有一個共同的機制，而那個機制只在 wire 上看得到
（`finish_reason=length` ＋ request body 的輸出上限），run_*.json 的欄位裡沒有。
⚠ openai 的 `choices[].finish_reason` 與 anthropic 的 `message_delta.delta.stop_reason`
  不是同一個字彙表，不可互相翻譯、不可合計。
"""
import json, pathlib, collections
root = pathlib.Path("/var/tmp/vacant_pbgate2")
print("# 30 格收尾原因普查（衍生物，零模型呼叫）")
print("# openai: choices[].finish_reason | anthropic: message_delta.delta.stop_reason")
print("# req_cap = request body 裡的輸出上限（誰設的見 manifest.json 的 agents[].output_cap）")
print()
for d in sorted(root.glob("rd_*")):
    fr = collections.Counter(); sr = collections.Counter(); caps = set()
    for f in sorted((d / "wire_RUN-ON").glob("*.resp.bin")):
        raw = f.read_bytes().decode("utf-8", "replace")
        for line in raw.splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            p = line[5:].strip()
            if not p or p == "[DONE]":
                continue
            try:
                o = json.loads(p)
            except Exception:
                continue
            for ch in (o.get("choices") or []):
                if ch.get("finish_reason"):
                    fr[ch["finish_reason"]] += 1
            if o.get("type") == "message_delta":
                s = (o.get("delta") or {}).get("stop_reason")
                if s:
                    sr[s] += 1
    for f in sorted((d / "wire_RUN-ON").glob("*.req.bin")):
        try:
            b = json.loads(f.read_bytes().decode("utf-8", "replace"))
        except Exception:
            continue
        for k in ("max_tokens", "max_completion_tokens"):
            if k in b:
                caps.add(f"{k}={b[k]}")
    print(f"{d.name[3:]:22} openai={str(dict(fr)):46} anthropic={str(dict(sr)):34} req_cap={sorted(caps)}")
