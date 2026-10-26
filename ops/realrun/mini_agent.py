#!/usr/bin/env python3
"""最小一次性編碼 agent，給 `vacant run -- python3 mini_agent.py <out> <prompt>` 用。

設計意圖：這是**故意最小**的 agent——沒有工具、沒有重試、不會跑測試、
只把 prompt 交給 OpenAI 相容 API、把回來的代碼寫進工作區。量測
（plain vs vacant、resample 的增益）要的是「同一個 agent、同一個模型、
不同迴路」的比較；agent 端越笨，差距就越只能來自 Vacant 的迴路本身。

環境變數（`vacant run` 的 launcher 會照 envmap 把 agent 環境組好）：
  OPENAI_BASE_URL  → 在 `vacant run` 子行程裡被指向 wire proxy（真上游
                      由父行程的 VACANT_RUN_UPSTREAM_OPENAI 決定，agent 看不到）
  OPENAI_API_KEY   → sentinel 字串（真鑰只留在 proxy 行程）
  VACANT_EXP_MODEL → 模型 id，預設 qwen/qwen3.8-27b（本機實測用的模型）

用法：
  mini_agent.py <output-file> <prompt...>
把 prompt 當 user message 送出，回傳的第一個 fenced code block（取最大者）
寫成 <output-file> 到**目前目錄**（＝ `vacant run` 的工作區）。
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

FENCE_RE = re.compile(r"```[a-zA-Z0-9_-]*[ \t]*\n(.*?)```", re.S)


def call_model(base: str, key: str, model: str, system: str, user: str,
               *, timeout: float = 300.0, temperature: float = 0.2,
               max_tokens: int = 4096) -> str:
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        # match the established eval harness (ops/ref/run_20_eval.py). Without
        # this, the model can spend the whole budget on reasoning and return
        # empty content — observed in live batch v1 (7/12 runs had at least
        # one empty-reply attempt; wire logs show content="" with a long
        # reasoning_content)
        "reasoning_effort": "none",
    }).encode("utf-8")
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions",
        data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    return d["choices"][0]["message"]["content"]


def extract_code(text: str) -> str:
    """取 fenced block（最大的那個）；沒有 fence 就整段當代碼。"""
    fences = FENCE_RE.findall(text or "")
    if fences:
        return max(fences, key=len).strip("\n")
    return (text or "").strip("\n")


def main() -> None:
    if len(sys.argv) < 3:
        print("usage: mini_agent.py <output-file> <prompt...>", file=sys.stderr)
        raise SystemExit(2)
    out = sys.argv[1]
    prompt = " ".join(sys.argv[2:])
    base = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE")
    if not base:
        print("mini_agent: OPENAI_BASE_URL 未設定"
              "（在 `vacant run` 子行程裡由 launcher 指向 proxy）", file=sys.stderr)
        raise SystemExit(2)
    key = os.environ.get("OPENAI_API_KEY", "sk-sentinel")
    model = os.environ.get("VACANT_EXP_MODEL", "qwen/qwen3.8-27b")
    system = ("You are a coding agent. Complete the task exactly as specified. "
              "Reply with the complete content of the requested file in a single "
              "fenced code block, and nothing else.")
    try:
        text = call_model(base, key, model, system, prompt)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            json.JSONDecodeError) as e:
        print(f"mini_agent: model call failed: {e!r}", file=sys.stderr)
        raise SystemExit(1)
    code = extract_code(text)
    if not code:
        print("mini_agent: empty reply", file=sys.stderr)
        raise SystemExit(1)
    with open(out, "w", encoding="utf-8") as f:
        f.write(code + "\n")
    print(f"mini_agent: wrote {len(code)} chars to {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
