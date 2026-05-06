"""Google Gemini substrate.

Default model: `gemini-2.0-flash`. Talks to the Generative Language
API directly via `httpx` (no `google-genai` SDK dependency added,
to keep the substrate footprint small and tests easily mockable).
The wire shape matches `https://ai.google.dev/api/rest/v1beta/models/generateContent`.

Auth: `GOOGLE_API_KEY` (auto-loaded from `.env` if `python-dotenv`
is installed).
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any

from vacant.substrate._env import _load_dotenv_once
from vacant.substrate.base import (
    SubstrateBackend,
    SubstrateRequest,
    SubstrateResponse,
)
from vacant.substrate.errors import SubstrateRateLimitError, SubstrateUnavailableError

__all__ = ["GeminiSubstrate"]

DEFAULT_MODEL = "gemini-2.0-flash"
DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


@dataclass
class GeminiSubstrate(SubstrateBackend):
    model: str = DEFAULT_MODEL
    api_key_env: str = "GOOGLE_API_KEY"
    base_url: str = DEFAULT_BASE_URL
    max_retries: int = 3
    max_tokens: int = 1024
    timeout_s: float = 60.0

    @property
    def name(self) -> str:
        return f"gemini:{self.model}"

    async def infer(self, req: SubstrateRequest) -> SubstrateResponse:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover -- httpx is a hard dep
            raise SubstrateUnavailableError("httpx not installed") from exc

        _load_dotenv_once()
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise SubstrateUnavailableError(
                f"{self.api_key_env} not set; GeminiSubstrate requires an API key. "
                "Add it to your shell env or create a `.env` file with "
                f"`{self.api_key_env}=...` (python-dotenv loads it automatically)."
            )

        url = f"{self.base_url.rstrip('/')}/models/{self.model}:generateContent"
        payload: dict[str, Any] = {
            "system_instruction": {"parts": [{"text": req.system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": req.user_prompt}]}],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": self.max_tokens,
            },
        }
        headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}

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
                candidates = data.get("candidates", [])
                if not candidates:
                    raise SubstrateUnavailableError(
                        f"GeminiSubstrate returned no candidates: {data!r}"
                    )
                parts = candidates[0].get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts)
                usage = data.get("usageMetadata", {})
                return SubstrateResponse(
                    text=text,
                    model_id=self.model,
                    usage={
                        "input_tokens": int(usage.get("promptTokenCount", 0)),
                        "output_tokens": int(usage.get("candidatesTokenCount", 0)),
                    },
                    proof={
                        "finish_reason": str(candidates[0].get("finishReason", "")),
                        "endpoint": self.base_url,
                    },
                )
            except httpx.HTTPStatusError as exc:
                last_err = exc
                break
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                raise SubstrateUnavailableError(
                    f"GeminiSubstrate cannot reach {url}: {exc}"
                ) from exc
        raise SubstrateRateLimitError(
            f"GeminiSubstrate exhausted {self.max_retries} retries: {last_err}"
        ) from last_err
