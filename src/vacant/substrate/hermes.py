"""Hermes substrate stub (Nous Research Hermes Agent).

Hermes Agent is Nous Research's agentic runtime layered on top of
their Hermes-3 / Hermes-4 models. The runtime exposes a tools/JSON
mode contract that is broadly OpenAI-compatible at the chat layer,
but Nous's `hermes-agent-sdk` is not yet on PyPI and the public
endpoint is rate-limited beta access.

For D1 we ship a stub that:
* declares the substrate name (so capability_card matches against
  `hermes:*` resolve to this class), and
* raises `SubstrateUnavailableError` with an actionable message when
  asked to infer.

Promotion to a real implementation is tracked in D1's follow-up.
TODO(D1-followup): wire the Nous Hermes Agent endpoint once the SDK
or stable HTTP contract lands. Likely path is to delegate to
`OpenAISubstrate(base_url="https://inference-api.nousresearch.com/v1",
api_key_env="NOUS_API_KEY")` since the Hermes inference endpoint is
OpenAI-compatible.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from vacant.substrate._env import _load_dotenv_once
from vacant.substrate.base import (
    SubstrateBackend,
    SubstrateRequest,
    SubstrateResponse,
)
from vacant.substrate.errors import SubstrateUnavailableError

__all__ = ["HermesSubstrate"]

DEFAULT_MODEL = "Hermes-3-Llama-3.1-70B"


@dataclass
class HermesSubstrate(SubstrateBackend):
    model: str = DEFAULT_MODEL
    api_key_env: str = "NOUS_API_KEY"

    @property
    def name(self) -> str:
        return f"hermes:{self.model}"

    async def infer(self, req: SubstrateRequest) -> SubstrateResponse:
        # Stub: confirm `.env` is at least loadable so the error message
        # can be specific about whether the key was the problem.
        _load_dotenv_once()
        has_key = bool(os.environ.get(self.api_key_env))
        raise SubstrateUnavailableError(
            "HermesSubstrate is a stub for D1. Hermes Agent SDK is not yet "
            "wired (TODO D1-followup). "
            f"({self.api_key_env} {'is set' if has_key else 'is not set'})"
        )
