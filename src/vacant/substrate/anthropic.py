"""Anthropic Claude substrate.

Default model: `claude-sonnet-4-6` (latest Claude 4.6 Sonnet,
per CLAUDE.md tech stack).

API key is read from `ANTHROPIC_API_KEY` env var. Initialisation does
NOT create the client until the first `infer` call (lazy import) so
unit tests that import this module without the SDK installed do not
fail.

Rate-limit handling: the SDK raises `anthropic.RateLimitError`; this
wrapper catches it and re-raises as `SubstrateRateLimitError` after
sleeping for `retry_after` seconds (header-driven). Retries up to
`max_retries` times before surfacing the failure.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

from vacant.substrate.base import (
    SubstrateBackend,
    SubstrateRequest,
    SubstrateResponse,
)
from vacant.substrate.errors import SubstrateRateLimitError, SubstrateUnavailableError

__all__ = ["AnthropicSubstrate"]

DEFAULT_MODEL = "claude-sonnet-4-6"


@dataclass
class AnthropicSubstrate(SubstrateBackend):
    """Real-LLM substrate. Used by demo scenarios with `--substrate=anthropic`.

    Tests should NOT use this (they use `MockSubstrate`); CI cannot
    reach the network and bit-exact reproducibility is not possible.
    """

    model: str = DEFAULT_MODEL
    api_key_env: str = "ANTHROPIC_API_KEY"
    max_retries: int = 3
    max_tokens: int = 1024

    @property
    def name(self) -> str:
        return f"anthropic:{self.model}"

    async def infer(self, req: SubstrateRequest) -> SubstrateResponse:
        try:
            import anthropic
        except ImportError as exc:
            raise SubstrateUnavailableError(
                "anthropic SDK not installed; pip install anthropic"
            ) from exc

        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise SubstrateUnavailableError(
                f"{self.api_key_env} not set; AnthropicSubstrate requires an API key"
            )

        client = anthropic.AsyncAnthropic(api_key=api_key)
        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                rsp = await client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=req.system_prompt,
                    messages=[{"role": "user", "content": req.user_prompt}],
                    temperature=0.0,
                )
                text = "".join(
                    getattr(block, "text", "")
                    for block in rsp.content
                    if getattr(block, "type", None) == "text"
                )
                return SubstrateResponse(
                    text=text,
                    model_id=self.model,
                    usage={
                        "input_tokens": rsp.usage.input_tokens,
                        "output_tokens": rsp.usage.output_tokens,
                    },
                    proof={"stop_reason": rsp.stop_reason or ""},
                )
            except anthropic.RateLimitError as exc:
                last_err = exc
                wait = 2**attempt
                await asyncio.sleep(wait)
            except anthropic.APIError as exc:
                last_err = exc
                break
        raise SubstrateRateLimitError(
            f"AnthropicSubstrate exhausted {self.max_retries} retries: {last_err}"
        ) from last_err
