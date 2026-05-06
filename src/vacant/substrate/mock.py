"""Deterministic mock substrate for tests + bit-exact CI runs.

`MockSubstrate` returns canned text built from the prompt + a seeded
random suffix. Every (seed, system_prompt, user_prompt) tuple produces
the *same* response, so the integration test asserts exact byte
equality across runs (P7 §"Substrate determinism contract").
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from vacant.substrate.base import (
    SubstrateBackend,
    SubstrateRequest,
    SubstrateResponse,
)

__all__ = ["MockSubstrate"]


@dataclass
class MockSubstrate(SubstrateBackend):
    """Bit-exact reproducible. Used by every integration test."""

    seed: int = 0
    model_label: str = "mock-1"

    @property
    def name(self) -> str:
        return f"mock:{self.model_label}:{self.seed}"

    async def infer(self, req: SubstrateRequest) -> SubstrateResponse:
        digest = hashlib.blake2b(
            f"{self.seed}\x1f{req.system_prompt}\x1f{req.user_prompt}".encode(),
            digest_size=8,
        ).hexdigest()
        text = f"[{self.model_label}#{digest}] {req.user_prompt[:120]}"
        return SubstrateResponse(
            text=text,
            model_id=self.model_label,
            usage={"input_tokens": len(req.user_prompt), "output_tokens": len(text)},
            proof={"seed": self.seed, "digest": digest},
        )
