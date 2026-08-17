#!/usr/bin/env python3
"""Cline／Kimi 後端——實作 `run_x1` 那個 Brain protocol：`generate(prompt) -> str`。

為什麼是這支：SPEC_GAIN §6 要宣稱「任何 agent platform」，而 Vacant 這一層包的
就是一個 callable。這支是第一個真實後端；宣稱平台無關需要**第二個後端同號**，
只有一個就只能說「在這個後端上成立」。

**全 I/O 落盤（鐵律 3）**：每一次呼叫——含失敗與重試——逐字寫進 JSONL：
prompt 全文、回應全文、耗時、成本、重試次數、錯誤訊息。不做截斷、不做去識別。
理由是這個專案的紀律是「只數產物不看返回值」，而回應全文就是產物本身；
存摘要等於把後來能重新判讀的機會丟掉。

retry×4 指數 backoff；四次都失敗記 `infra_void`（09 §3.5）——
**infra_void 不算成功也不算失敗**，它是「這一格沒有量到」，
與「量到 0」必須分得開。
"""
from __future__ import annotations

import json
import os
import pathlib
import time
import urllib.request

API = "https://api.cline.bot/api/v1/chat/completions"
DEFAULT_MODEL = "cline-pass/kimi-k3"


class InfraVoid(RuntimeError):
    """端點連不上／重試用盡。呼叫端必須把這一格記成 infra_void，不可當成錯誤答案。"""


class ClineBrain:
    """一個 agent。`system` 決定它的性格——異質性就是從這裡來的。"""

    def __init__(self, agent_id: str, system: str, *, key: str,
                 log_path: pathlib.Path, model: str = DEFAULT_MODEL,
                 temperature: float = 0.7, retries: int = 4,
                 backoff_s: float = 2.0, timeout_s: int = 240) -> None:
        self.agent_id = agent_id
        self.system = system
        self.key = key
        self.model = model
        self.temperature = temperature
        self.retries = retries
        self.backoff_s = backoff_s
        self.timeout_s = timeout_s
        self.log_path = pathlib.Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.calls = 0
        self.cost = 0.0

    # ── 落盤 ────────────────────────────────────────────────────────
    def _log(self, rec: dict) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())      # 中途被砍也要留得住

    # ── 呼叫 ────────────────────────────────────────────────────────
    def generate(self, prompt: str, *, role: str = "gen",
                 meta: dict | None = None) -> str:
        body = json.dumps({
            "model": self.model,
            "messages": [{"role": "system", "content": self.system},
                         {"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "stream": False,
        }).encode()

        last_err = ""
        for attempt in range(1, self.retries + 1):
            t0 = time.time()
            req = urllib.request.Request(
                API, data=body,
                headers={"Authorization": f"Bearer {self.key}",
                         "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                    payload = json.load(r)
                d = payload.get("data", payload)
                choice = d["choices"][0]["message"]
                text = choice["content"]
                gw = choice.get("provider_metadata", {}).get("gateway", {})
                cost = float(gw.get("cost") or 0)
                self.calls += 1
                self.cost += cost
                self._log({
                    "ts_ms": int(time.time() * 1000),
                    "agent_id": self.agent_id, "role": role,
                    "model": self.model, "temperature": self.temperature,
                    "attempt": attempt, "ok": True,
                    "latency_ms": int((time.time() - t0) * 1000),
                    "cost_usd": cost,
                    "usage": d.get("usage"),
                    "system": self.system,
                    "prompt": prompt,          # 全文
                    "response": text,          # 全文
                    "meta": meta or {},
                })
                return text
            except Exception as e:                      # noqa: BLE001
                last_err = f"{type(e).__name__}: {e}"
                self._log({
                    "ts_ms": int(time.time() * 1000),
                    "agent_id": self.agent_id, "role": role,
                    "attempt": attempt, "ok": False,
                    "latency_ms": int((time.time() - t0) * 1000),
                    "error": last_err,
                    "prompt": prompt,
                    "meta": meta or {},
                })
                if attempt < self.retries:
                    time.sleep(self.backoff_s * (2 ** (attempt - 1)))

        raise InfraVoid(f"{self.agent_id} 重試 {self.retries} 次仍失敗：{last_err}")


def load_keys(path: str | None = None) -> list[str]:
    p = pathlib.Path(path or os.environ.get("CLINE_KEYS", "~/.cline-keys")).expanduser()
    ks = [l.strip() for l in p.read_text().splitlines() if l.strip()]
    if not ks:
        raise SystemExit(f"{p} 裡沒有金鑰")
    return ks


# ── agent 池：異質性從 system prompt 來 ──────────────────────────────
#
# ⚠ SPEC_GAIN §5.3：池子必須**真的**異質，而且差距要先量出來當前提。
#   全部一樣強的話，信譽路由沒有東西可以路由——那時量到「沒有增益」
#   會是實驗設計的結果，不是機制的性質。
#
# ⚠ KS-1（鐵律 1）：這些 system prompt 一律不得出現「你有責任／會被懲罰」
#   類措辭。差異只能是**工作習慣**，不能是被監督的暗示——
#   否則量到的是提示詞效果不是機制效果。
POOL = [
    ("careful-1", "你是一位資深工程師。寫程式之前先想清楚邊界情況："
                  "空輸入、單一元素、重複值、負數、型別不一致。寫完自己檢查一遍。"),
    ("careful-2", "你是一位注重正確性的工程師。先把題目的條件逐項列出來，"
                  "確認每一項都被處理到，再寫程式碼。"),
    ("plain-1",   "你是一位程式設計師。"),
    ("plain-2",   "你是一位程式設計師。請完成使用者要求的函式。"),
    ("hasty-1",   "你是一位講求速度的程式設計師。直接寫出最短的可行解，不要多想。"),
    ("hasty-2",   "你是一位程式設計師。快速給出答案，以最常見的情況為主即可。"),
]

REVIEWER_SYSTEM = (
    "你是一位程式碼審查者。你會看到一個題目與一份候選解答。"
    "判斷這份解答是否**完全滿足題目要求**，特別注意邊界情況。"
    "只回覆一個字：通過 或 不通過。不要解釋。"
)
