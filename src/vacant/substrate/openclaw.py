"""OpenClaw substrate stub.

OpenClaw is an open-source Claude-Desktop-style host that exposes a
plugin/tool API and (in newer builds) MCP-server hosting. The
load-bearing OpenClaw integration is `client-inherited` (D2): a
vacant served via MCP under OpenClaw uses OpenClaw's session LLM via
`sampling/createMessage`, no API key on the vacant side.

This file is the "as if OpenClaw were just another LLM provider"
shim, kept for completeness and parity with the substrate matrix
(`--substrate=openclaw`). For most real use the user wants D2
instead.

TODO(D2): once `ClientInheritedSubstrate` lands, this stub should
either delegate to it (if a session handle is in scope) or remain a
clear "use --substrate=client-inherited under MCP" pointer.
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

__all__ = ["OpenClawSubstrate"]

DEFAULT_MODEL = "openclaw-default"


@dataclass
class OpenClawSubstrate(SubstrateBackend):
    model: str = DEFAULT_MODEL
    api_key_env: str = "OPENCLAW_API_KEY"

    @property
    def name(self) -> str:
        return f"openclaw:{self.model}"

    async def infer(self, req: SubstrateRequest) -> SubstrateResponse:
        _load_dotenv_once()
        has_key = bool(os.environ.get(self.api_key_env))
        raise SubstrateUnavailableError(
            "OpenClawSubstrate is a stub for D1. The intended OpenClaw "
            "integration is `--substrate=client-inherited` (D2): vacant "
            "served via MCP uses the OpenClaw session LLM via "
            "sampling/createMessage. TODO D2-followup. "
            f"({self.api_key_env} {'is set' if has_key else 'is not set'})"
        )
