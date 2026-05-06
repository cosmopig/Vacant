"""OpenAI (and OpenAI-compatible) substrate.

Default model: `gpt-4o`. The same class works against any
OpenAI-compatible Chat Completions endpoint by setting
`OPENAI_BASE_URL` (or passing `base_url=...`):

    OPENAI_BASE_URL=https://api.together.xyz/v1
    OPENAI_BASE_URL=https://api.fireworks.ai/inference/v1
    OPENAI_BASE_URL=https://api.groq.com/openai/v1
    OPENAI_BASE_URL=http://localhost:8000/v1   # vLLM / LMStudio / llama.cpp

Implemented over `httpx` directly (no SDK dependency) — keeps the
substrate footprint small and unit tests trivially mockable.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

from vacant.substrate._env import _load_dotenv_once
from vacant.substrate.base import (
    SubstrateBackend,
    SubstrateRequest,
    SubstrateResponse,
)
from vacant.substrate.errors import SubstrateRateLimitError, SubstrateUnavailableError

__all__ = ["OpenAISubstrate"]

DEFAULT_MODEL = "gpt-4o"
DEFAULT_BASE_URL = "https://api.openai.com/v1"


@dataclass
class OpenAISubstrate(SubstrateBackend):
    """Chat Completions backend.

    `base_url` falls back to `OPENAI_BASE_URL` env var, then the OpenAI
    public endpoint. Setting it to e.g. `http://localhost:8000/v1`
    points the same code at any OAI-compat server.
    """

    model: str = DEFAULT_MODEL
    api_key_env: str = "OPENAI_API_KEY"
    base_url: str | None = None
    max_retries: int = 3
    max_tokens: int = 1024
    timeout_s: float = 60.0

    @property
    def name(self) -> str:
        return f"openai:{self.model}"

    def _resolve_base_url(self) -> str:
        return self.base_url or os.environ.get("OPENAI_BASE_URL") or DEFAULT_BASE_URL

    async def infer(self, req: SubstrateRequest) -> SubstrateResponse:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover -- httpx is a hard dep
            raise SubstrateUnavailableError("httpx not installed") from exc

        _load_dotenv_once()
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise SubstrateUnavailableError(
                f"{self.api_key_env} not set; OpenAISubstrate requires an API key. "
                "Add it to your shell env or create a `.env` file with "
                f"`{self.api_key_env}=...` (python-dotenv loads it automatically)."
            )

        url = f"{self._resolve_base_url().rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": req.system_prompt},
                {"role": "user", "content": req.user_prompt},
            ],
            "temperature": 0.0,
            "max_tokens": self.max_tokens,
        }

        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                    r = await client.post(url, headers=headers, json=payload)
                if r.status_code == 429:
                    last_err = httpx.HTTPStatusError("429", request=r.request, response=r)
                    await asyncio.sleep(2**attempt)
                    continue
                r.raise_for_status()
                data = r.json()
                choice = data["choices"][0]
                text = choice["message"].get("content") or ""
                usage = data.get("usage", {})
                return SubstrateResponse(
                    text=text,
                    model_id=str(data.get("model", self.model)),
                    usage={
                        "input_tokens": int(usage.get("prompt_tokens", 0)),
                        "output_tokens": int(usage.get("completion_tokens", 0)),
                    },
                    proof={
                        "finish_reason": str(choice.get("finish_reason", "")),
                        "endpoint": self._resolve_base_url(),
                    },
                )
            except httpx.HTTPStatusError as exc:
                last_err = exc
                break
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                raise SubstrateUnavailableError(
                    f"OpenAISubstrate cannot reach {url}: {exc}"
                ) from exc
        raise SubstrateRateLimitError(
            f"OpenAISubstrate exhausted {self.max_retries} retries: {last_err}"
        ) from last_err
