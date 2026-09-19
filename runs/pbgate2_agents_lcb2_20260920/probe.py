#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""發射前後端探針。**先證明量具活著，再去量真的東西。**

三件事：
 1. /v1/chat/completions 的 reasoning_content（thinking 判準；⚠ 不看
    頂層 usage.reasoning_tokens——兩台都回 None，讀它永遠是 None）
 2. 巢狀 usage.completion_tokens_details.reasoning_tokens
 3. /v1/messages（Anthropic Messages）在不在（Claude Code 零接線的前提）
負控制：同一支腳本對 1004 跑一次——量得出兩台不同，才證明它量得動。
"""
import json, sys, urllib.request

def post(url, body, hdrs=None, timeout=180):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"content-type": "application/json", **(hdrs or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode()

def probe_chat(base, model):
    raw = post(f"{base}/v1/chat/completions", {
        "model": model, "stream": False, "max_tokens": 512,
        "messages": [{"role": "user",
                      "content": "What is 17*23? Answer with the number only."}]})
    d = json.loads(raw)
    msg = d["choices"][0].get("message", {})
    rc = msg.get("reasoning_content")
    usage = d.get("usage", {})
    ctd = (usage.get("completion_tokens_details") or {})
    return {
        "raw_first_600": raw[:600],
        "content": (msg.get("content") or "")[:200],
        "reasoning_content_present": rc is not None,
        "reasoning_content_len": len(rc) if isinstance(rc, str) else None,
        "reasoning_content_first_200": (rc or "")[:200] if isinstance(rc, str) else None,
        "nested_reasoning_tokens": ctd.get("reasoning_tokens"),
        "TOP_LEVEL_usage_reasoning_tokens_DO_NOT_USE": usage.get("reasoning_tokens"),
        "usage": usage,
    }

def probe_messages(base, model):
    try:
        raw = post(f"{base}/v1/messages", {
            "model": model, "max_tokens": 128, "stream": False,
            "tools": [{"name": "Bash", "description": "Run a shell command",
                       "input_schema": {"type": "object",
                                        "properties": {"command": {"type": "string"}},
                                        "required": ["command"]}}],
            "messages": [{"role": "user",
                          "content": "Use the Bash tool to run: echo hi"}]},
            hdrs={"anthropic-version": "2023-06-01"})
        d = json.loads(raw)
        return {"ok": True, "stop_reason": d.get("stop_reason"),
                "block_types": [b.get("type") for b in d.get("content", [])],
                "raw_first_400": raw[:400]}
    except Exception as e:
        return {"ok": False, "error": repr(e)}

if __name__ == "__main__":
    out = {}
    for name, base, model in [
            ("1003", "http://100.119.113.56:1234", "gemma-4-12b-it-qat"),
            ("1004", "http://100.86.226.21:1234", "gemma-4-12b-it-qat")]:
        e = {}
        try:
            e["chat"] = probe_chat(base, model)
        except Exception as ex:
            e["chat"] = {"error": repr(ex)}
        e["messages"] = probe_messages(base, model)
        out[name] = e
    print(json.dumps(out, ensure_ascii=False, indent=2))
