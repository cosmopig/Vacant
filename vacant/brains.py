"""Brain 介面 + adapters —— vacant 要包的『腦』。

brain-agnostic：任何能把 prompt 變成文字答案的東西都能當 vacant 的腦。
內建三種 adapter（都只暴露 `.generate(prompt) -> str`）：
  - LMStudioBrain：LM Studio（自動處理 /v1 與 reasoning 模型的 /api/v1）
  - OpenAIBrain ：任何 OpenAI 相容 /v1/chat/completions 端點
  - HermesBrain ：本機 Hermes Agent（`hermes -z` oneshot，腦＝Hermes 自己調模型）

自訂腦：實作 `class MyBrain: name=...; def generate(self, prompt)->str: ...` 即可丟給 Vacant。
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from typing import Protocol, runtime_checkable


@runtime_checkable
class Brain(Protocol):
    name: str
    def generate(self, prompt: str) -> str: ...


class UsageMixin:
    """真實成本落盤（17 §P1／lab P0-real-cost-ledger 同規）：每次 generate 後
    `self.last_usage` 放端點實回的 usage dict（prompt/completion/total tokens 等），
    拿不到 → None。X1 正式 run 以 require_usage=True 把「缺 usage」判 infra_void，
    禁止用 len(text)//4 之類字數代理混進正式成本分母。"""

    last_usage: dict | None = None


def _post(url: str, payload: dict, timeout: int) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


class OpenAIBrain(UsageMixin):
    """任何 OpenAI 相容端點（/v1/chat/completions）。base_url 例：http://host:1234/v1

    max_tokens=None → **不送該欄**（R1：正式實驗不設上限——reasoning 模型被
    砍在思考途中會 content 空，06-30 教訓）。"""

    def __init__(self, base_url: str, model: str, *, temperature: float = 0.0,
                 max_tokens: int | None = 256, timeout: int = 120, system: str = "You are a precise assistant. Output only the answer."):
        self.base_url = base_url.rstrip("/")
        if not self.base_url.endswith("/v1"):
            self.base_url += "/v1"
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.system = system
        self.name = f"openai:{model}"

    def generate(self, prompt: str) -> str:
        payload = {
            "model": self.model, "temperature": self.temperature,
            "messages": [{"role": "system", "content": self.system}, {"role": "user", "content": prompt}],
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        d = _post(self.base_url + "/chat/completions", payload, self.timeout)
        u = d.get("usage")
        self.last_usage = dict(u) if isinstance(u, dict) else None
        return (d["choices"][0]["message"].get("content") or "").strip()


class LMStudioBrain(UsageMixin):
    """LM Studio。預設走 /api/v1/chat（reasoning 模型在這裡才拿得到最終答案；
    /v1 的 content 對 reasoning 模型常為空）。非 reasoning 模型用 api='openai' 即可。"""

    def __init__(self, base_url: str, model: str, *, api: str = "responses",
                 timeout: int = 120, max_tokens: int | None = 256,
                 system: str = "Output only the answer, nothing else."):
        # base_url 給 http://host:1234（含/不含 /v1 都行）
        b = base_url.rstrip("/")
        if b.endswith("/v1"):
            b = b[:-3]
        self.base = b
        self.model = model
        self.api = api          # 'responses' (/api/v1/chat) | 'openai' (/v1/chat/completions)
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.system = system
        self.name = f"lmstudio:{model}"
        self._openai = OpenAIBrain(b + "/v1", model, timeout=timeout, max_tokens=max_tokens, system=system)

    def generate(self, prompt: str) -> str:
        if self.api == "openai":
            out = self._openai.generate(prompt)
            self.last_usage = self._openai.last_usage
            return out
        d = _post(self.base + "/api/v1/chat", {
            "model": self.model, "system_prompt": self.system, "input": prompt,
        }, self.timeout)
        # LM Studio /api/v1/chat 的 usage 在 stats 區塊（prompt/completion tokens）
        stats = d.get("stats")
        if isinstance(stats, dict):
            self.last_usage = {
                "prompt_tokens": stats.get("prompt_tokens"),
                "completion_tokens": stats.get("predicted_tokens"),
                "total_tokens": stats.get("total_tokens"),
                **{k: v for k, v in stats.items()
                   if k not in ("prompt_tokens", "predicted_tokens", "total_tokens")},
            }
        else:
            u = d.get("usage")
            self.last_usage = dict(u) if isinstance(u, dict) else None
        msgs = [o.get("content", "") for o in d.get("output", []) if o.get("type") == "message"]
        return (msgs[-1] if msgs else "").strip()


class HermesBrain:
    """本機 Hermes Agent 當腦（`hermes -z` oneshot）—— Hermes 自己調模型、用自帶 skills/記憶。

    需 Hermes 已安裝、`~/.hermes/config.yaml` 指好模型。toolsets='' 預設關工具（小模型較穩）。
    """

    def __init__(self, *, hermes_bin: str | None = None, model: str | None = None,
                 provider: str = "vllm", toolsets: str = "", timeout: int = 180,
                 base_url: str | None = None):
        self.hermes_bin = hermes_bin or os.path.expanduser("~/hermes-agent/venv/bin/hermes")
        self.model = model
        self.provider = provider
        self.toolsets = toolsets
        self.timeout = timeout
        self.base_url = base_url
        self.name = f"hermes:{model or 'config'}"

    def generate(self, prompt: str) -> str:
        cmd = [self.hermes_bin, "-z", prompt, "--provider", self.provider, "-t", self.toolsets]
        if self.model:
            cmd += ["-m", self.model]
        env = dict(os.environ)
        if self.base_url:
            env["CUSTOM_BASE_URL"] = self.base_url
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout, env=env)
            return (r.stdout or "").strip()
        except subprocess.TimeoutExpired:
            return "[timeout]"
