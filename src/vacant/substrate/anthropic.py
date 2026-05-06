"""Anthropic Claude substrate.

Default model: `claude-sonnet-4-6` (latest Claude 4.6 Sonnet,
per CLAUDE.md tech stack).

API key is read from `ANTHROPIC_API_KEY` env var. If `python-dotenv` is
installed (it is — required dep, see `pyproject.toml`), `.env` files in
the cwd / parent dirs are auto-loaded the first time the substrate is
asked to infer, so the README workflow `echo ANTHROPIC_API_KEY=...
> .env && vacant demo --substrate=anthropic` works without `export`
(F14). Initialisation does NOT create the SDK client until the first
`infer` call (lazy import).

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

_DOTENV_LOADED = False


def _load_dotenv_once() -> None:
    """Idempotent best-effort `.env` loader.

    Cached so repeated `infer()` calls do not re-walk the filesystem.
    Falls back silently if `python-dotenv` is not installed: the env
    var must already be exported in that case.
    """
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True
    try:
        from dotenv import find_dotenv, load_dotenv
    except ImportError:
        return
    # `find_dotenv()` walks up from cwd; pass the resolved path so the
    # default cwd-only behaviour does not silently no-op when the env
    # file is in a parent dir of the script's working directory.
    path = find_dotenv(usecwd=True)
    if path:
        load_dotenv(path, override=False)


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

        # F14: try `.env` before declaring the key missing — keeps the
        # README workflow honest. `override=False` so an explicit
        # `export ANTHROPIC_API_KEY=...` always wins over `.env`.
        _load_dotenv_once()
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise SubstrateUnavailableError(
                f"{self.api_key_env} not set; AnthropicSubstrate requires an API key. "
                "Add it to your shell env or create a `.env` file with "
                f"`{self.api_key_env}=...` (python-dotenv loads it automatically)."
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
