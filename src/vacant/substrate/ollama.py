"""Ollama substrate (local-LLM, "token-free future" simulation).

Talks to a local Ollama server over HTTP (`http://localhost:11434`
by default). Useful for the multilingual_translation scenario's
`local-ollama-llama3` substrate slot.

Failures (server not running, model not pulled) raise
`SubstrateUnavailableError` -- callers can catch and degrade.
"""

from __future__ import annotations

from dataclasses import dataclass

from vacant.substrate.base import (
    SubstrateBackend,
    SubstrateRequest,
    SubstrateResponse,
)
from vacant.substrate.errors import SubstrateUnavailableError

__all__ = ["OllamaSubstrate"]


@dataclass
class OllamaSubstrate(SubstrateBackend):
    """Local Ollama backend. Used in demo to simulate the
    "token-free future" leg of THEORY_V5 §2 substrate diversity."""

    model: str = "llama3"
    base_url: str = "http://localhost:11434"
    timeout_s: float = 60.0

    @property
    def name(self) -> str:
        return f"ollama:{self.model}"

    async def infer(self, req: SubstrateRequest) -> SubstrateResponse:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover -- httpx is a hard dep
            raise SubstrateUnavailableError("httpx not installed") from exc
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                r = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": req.user_prompt,
                        "system": req.system_prompt,
                        "stream": False,
                        "options": {"temperature": 0.0},
                    },
                )
                r.raise_for_status()
                data = r.json()
        except (httpx.ConnectError, httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            raise SubstrateUnavailableError(
                f"OllamaSubstrate cannot reach {self.base_url}: {exc}"
            ) from exc
        text = str(data.get("response", ""))
        return SubstrateResponse(
            text=text,
            model_id=self.model,
            usage={
                "input_tokens": int(data.get("prompt_eval_count", 0)),
                "output_tokens": int(data.get("eval_count", 0)),
            },
            proof={"backend": "ollama", "done": bool(data.get("done", False))},
        )
