#!/usr/bin/env python3
"""K3（Kimi，走 Cline API）當「看得到圖的判斷者」——畫質品管，**額度有限要省**。

為什麼要另外一支，不併進 judge.py：
  judge.py 打的是本地 qwen，那支端點**明講不支援圖片輸入**（PLAN.md 已實測）。
  K3 走的是 Cline API（`~/.cline-keys`，跟 ops/gain/brain_cline.py 共用金鑰），
  是三個算力裡唯一「看得到圖、額度有限」的一個 ⇒ 呼叫端要自己省，
  不能像 judge.py 那樣無限打。

用法：
  python3 vision.py <圖路徑> <檢查項文字>
  python3 vision.py <圖路徑> far   # 內建的「640px 縮圖看不看得出在發生什麼」

只回一行 JSON：{"ok": true/false, "reason": "..."}。
"""
from __future__ import annotations

import base64
import json
import os
import pathlib
import sys
import time
import urllib.request

API = "https://api.cline.bot/api/v1/chat/completions"
MODEL = "cline-pass/kimi-k3"

FAR_CHECK = (
    "這是黏土定格動畫風格的展場素材，縮到展場觀眾隔一段距離看電視的尺寸。"
    "不看細節，只看整體：看不看得出這是什麼場景、在發生什麼事、"
    "紅色（如果有）是不是用在「被退件／被抓」這類負面事件上。"
    "看得出來才 ok=true。"
)


def _keys() -> list[str]:
    p = pathlib.Path(os.environ.get("CLINE_KEYS", "~/.cline-keys")).expanduser()
    ks = [l.strip() for l in p.read_text().splitlines() if l.strip()]
    if not ks:
        raise SystemExit(f"{p} 裡沒有金鑰")
    return ks


def _extract(t: str) -> dict:
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


def ask(image: str | pathlib.Path, question: str, *,
        timeout: int = 240, retries: int = 3) -> dict:
    p = pathlib.Path(image)
    if not p.exists():
        return {"ok": None, "reason": f"檔案不存在: {p}"}
    b64 = base64.b64encode(p.read_bytes()).decode()
    mime = "image/webp" if p.suffix == ".webp" else "image/png"

    body = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content":
             "你是一個嚴格的視覺評審。只回一行 JSON："
             '{"ok": true/false, "reason": "一句話，30字內"}。'
             "不要其他文字。看不出來就 ok=false，理由寫「看不出來」——"
             "不要猜，猜出來的通過比不通過更糟。"},
            {"role": "user", "content": [
                {"type": "text", "text": question},
                {"type": "image_url",
                 "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ]},
        ],
        "temperature": 0.2,
        "stream": False,
    }).encode()

    keys = _keys()
    last_err = ""
    for n in range(retries):
        key = keys[n % len(keys)]
        t0 = time.time()
        try:
            req = urllib.request.Request(
                API, data=body,
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                payload = json.load(r)
            d = payload.get("data", payload)
            txt = d["choices"][0]["message"]["content"].strip()
            parsed = _extract(txt)
            return {"ok": parsed.get("ok"), "reason": parsed.get("reason", ""),
                     "raw": txt[:300], "secs": round(time.time() - t0, 1)}
        except Exception as e:                                    # noqa: BLE001
            last_err = str(e)
            if n < retries - 1:
                time.sleep(5 * (n + 1))
    return {"ok": None, "reason": f"端點失敗: {last_err}",
            "secs": round(time.time() - t0, 1)}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("用法: vision.py <圖路徑> [檢查項文字|far]")
    img = sys.argv[1]
    q = sys.argv[2] if len(sys.argv) > 2 else "far"
    if q == "far":
        q = FAR_CHECK
    r = ask(img, q)
    print(json.dumps(r, ensure_ascii=False, indent=2))
