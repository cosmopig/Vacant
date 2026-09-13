#!/usr/bin/env python3
"""本地模型當「判斷者」——短問短答，不是生成。

為什麼只能這樣用（2026-08-18 實測，不是猜的）：
  端點 http://100.119.113.56:8765/v1  模型 qwen/qwen3.6-35b-a3b
  · 30 tok/s
  · 推理 token 佔 58–92%（要 200 字的段落，實際燒 1976 tok 其中 1826 是推理）
  · `/no_think` 沒有效果
  · max_tokens **不被強制**（要 4000 實際輸出 8291，finish_reason=stop）
⇒ 拿它寫東西太慢；拿它做「是/否 ＋ 一句理由」剛好。

一個誠實邊界：**它的判斷是意見不是量測。** 用它篩掉明顯不合格的，
不要用它宣稱合格——合格要靠像素量測與人眼。
"""
from __future__ import annotations

import base64
import json
import pathlib
import sys
import time
import urllib.request

BASE = "http://100.119.113.56:8765/v1/chat/completions"
MODEL = "qwen/qwen3.6-35b-a3b"


def ask(question: str, *, image: str | pathlib.Path | None = None,
        timeout: int = 300, retries: int = 3) -> dict:
    """問一題。回 {ok, answer, reason, secs, tokens}。

    image 給路徑時走 vision（若模型不支援會回錯，呼叫端要處理——
    不要假設它看得到圖）。
    """
    content: object = question
    if image is not None:
        p = pathlib.Path(image)
        b64 = base64.b64encode(p.read_bytes()).decode()
        mime = "image/webp" if p.suffix == ".webp" else "image/png"
        content = [
            {"type": "text", "text": question},
            {"type": "image_url",
             "image_url": {"url": f"data:{mime};base64,{b64}"}},
        ]

    body = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content":
             "你是一個嚴格的評審。只回一行 JSON："
             '{"ok": true/false, "reason": "一句話，20字內"}。'
             "不要其他文字。看不出來就 ok=false，理由寫「看不出來」——"
             "**不要猜**，猜出來的通過比不通過更糟。"},
            {"role": "user", "content": content},
        ],
        "max_tokens": 2000,
    }).encode()

    for n in range(retries):
        t0 = time.time()
        try:
            req = urllib.request.Request(
                BASE, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.load(r)
            txt = d["choices"][0]["message"]["content"].strip()
            u = d.get("usage", {})
            parsed = _extract(txt)
            return {"ok": parsed.get("ok"), "reason": parsed.get("reason", ""),
                    "raw": txt[:300], "secs": round(time.time() - t0, 1),
                    "tokens": u.get("completion_tokens"),
                    "reasoning": u.get("completion_tokens_details", {})
                                  .get("reasoning_tokens")}
        except Exception as e:                                   # noqa: BLE001
            if n == retries - 1:
                return {"ok": None, "reason": f"端點失敗: {e}",
                        "secs": round(time.time() - t0, 1)}
            time.sleep(5 * (n + 1))
    return {"ok": None, "reason": "unreachable"}


def _extract(t: str) -> dict:
    """挖 JSON。挖不到就照實回 ok=None——不要當成 false。

    「模型說不合格」與「我讀不懂它說什麼」必須分得開，
    否則報告裡兩者長得一樣（這個專案已經被這種形狀騙過十四次）。
    """
    s = t
    if "```" in s:
        parts = s.split("```")
        s = parts[1] if len(parts) > 1 else s
        if s.startswith("json"):
            s = s[4:]
    i, j = s.find("{"), s.rfind("}")
    if i >= 0 and j > i:
        try:
            return json.loads(s[i:j + 1])
        except Exception:                                        # noqa: BLE001
            pass
    return {"ok": None, "reason": "回應不是 JSON"}


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "回覆 {\"ok\":true,\"reason\":\"可用\"}"
    img = sys.argv[2] if len(sys.argv) > 2 else None
    r = ask(q, image=img)
    print(json.dumps(r, ensure_ascii=False, indent=2))
