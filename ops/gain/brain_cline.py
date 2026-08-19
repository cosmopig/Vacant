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
import urllib.error
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
        self.market_cost = 0.0

    # ── 落盤 ────────────────────────────────────────────────────────
    def _log(self, rec: dict) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())      # 中途被砍也要留得住

    # ── 呼叫 ────────────────────────────────────────────────────────
    def generate(self, prompt: str, *, role: str = "gen",
                 meta: dict | None = None, system: str | None = None) -> str:
        effective_system = system or self.system
        body = json.dumps({
            "model": self.model,
            "messages": [{"role": "system", "content": effective_system},
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
                usage = d.get("usage") or {}
                cost = float(usage.get("cost") or gw.get("cost") or 0)
                # BYOK calls may bill $0 at the Cline gateway while still consuming paid
                # provider inference. market_cost preserves equal-cost comparisons.
                market_cost = float(usage.get("market_cost") or cost)
                self.calls += 1
                self.cost += cost
                self.market_cost += market_cost
                self._log({
                    "ts_ms": int(time.time() * 1000),
                    "agent_id": self.agent_id, "role": role,
                    "model": self.model, "temperature": self.temperature,
                    "attempt": attempt, "ok": True,
                    "latency_ms": int((time.time() - t0) * 1000),
                    "cost_usd": cost,
                    "market_cost_usd": market_cost,
                    "usage": usage,
                    "system": effective_system,
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
                    "model": self.model, "temperature": self.temperature,
                    "attempt": attempt, "ok": False,
                    "latency_ms": int((time.time() - t0) * 1000),
                    "error": last_err,
                    "system": effective_system,
                    "prompt": prompt,
                    "meta": meta or {},
                })
                non_retryable = isinstance(e, urllib.error.HTTPError) and e.code in {
                    400, 401, 402, 403, 404,
                }
                if non_retryable:
                    break
                if attempt < self.retries:
                    time.sleep(self.backoff_s * (2 ** (attempt - 1)))

        raise InfraVoid(f"{self.agent_id} 重試 {self.retries} 次仍失敗：{last_err}")


def load_keys(path: str | None = None) -> list[str]:
    p = pathlib.Path(path or os.environ.get("CLINE_KEYS", "~/.cline-keys")).expanduser()
    ks = [line.strip() for line in p.read_text().splitlines() if line.strip()]
    if not ks:
        raise SystemExit(f"{p} 裡沒有金鑰")
    slots = os.environ.get("CLINE_KEY_INDICES", "").strip()
    if slots:
        try:
            indices = [int(item.strip()) for item in slots.split(",")]
            if not indices or any(index < 0 or index >= len(ks) for index in indices):
                raise ValueError
        except ValueError as exc:
            raise SystemExit(
                "CLINE_KEY_INDICES 必須是現有 key 的零起算索引，例如 0,2,4"
            ) from exc
        ks = [ks[index] for index in indices]
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
    "你是一位獨立程式碼審查者。你會看到題目與候選解答。"
    "找出會讓解答不符合題意的具體反例；不要因為程式看起來合理就通過。"
    "第一行必須且只能是 VERDICT: PASS 或 VERDICT: FAIL。"
    "第二行以 CONCERN: 開頭，寫最重要的一個問題或『none』。"
    "若判 FAIL，第三行必須是 TEST_ARGS: 加上一個 Python literal list，表示呼叫"
    "目標函式的 positional arguments；第四行必須是 EXPECTED: 加上預期回傳值的"
    "Python literal。例：TEST_ARGS: [[-1, 0, 2]] 與 EXPECTED: 1。"
    "若判 PASS，第三、四行分別寫 TEST_ARGS: NONE 與 EXPECTED: NONE。"
    "反例會由系統實際執行；無法解析或沒有推翻候選解答的 FAIL 不會計票。"
    "不要重寫完整答案，也不要在這四行之外輸出文字。"
)

# 同一模型家族仍有共同盲區；這些 lens 只能讓「當下做的事」不同，不能假裝成
# 模型家族異質化。實驗必須繼續單報 reviewer accuracy 與錯誤相關性。
REVIEW_LENSES = {
    "careful-1": "你的審查視角：邊界值、空輸入、重複值與負數。",
    "careful-2": "你的審查視角：逐條對照題目契約，找遺漏條件。",
    "plain-1": "你的審查視角：用最小反例推翻候選解答。",
    "plain-2": "你的審查視角：函式簽名、回傳型別、例外與副作用。",
    "hasty-1": "你的審查視角：語法、名稱、匯入與能否實際執行。",
    "hasty-2": "你的審查視角：複雜度、極端輸入與隱含假設。",
}
