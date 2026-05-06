"""Canned-response substrate for reproducible demos.

`DeterministicSubstrate` looks up responses keyed by a hash of the
prompt. Useful when a scenario needs *meaningful* canned text (e.g.
"this is a law firm answer") rather than the raw mock prefix.
Falls back to a deterministic synthesised response when the prompt
hash is not in the canned table.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from vacant.substrate.base import (
    SubstrateBackend,
    SubstrateRequest,
    SubstrateResponse,
)

__all__ = ["DeterministicSubstrate"]


def _prompt_key(req: SubstrateRequest) -> str:
    return hashlib.blake2b(
        f"{req.system_prompt}\x1f{req.user_prompt}".encode(),
        digest_size=8,
    ).hexdigest()


@dataclass
class DeterministicSubstrate(SubstrateBackend):
    """Responses lookup table; deterministic synthesis on miss."""

    canned: dict[str, str] = field(default_factory=dict)
    model_label: str = "det-1"

    @property
    def name(self) -> str:
        return f"deterministic:{self.model_label}"

    async def infer(self, req: SubstrateRequest) -> SubstrateResponse:
        key = _prompt_key(req)
        if key in self.canned:
            text = self.canned[key]
        else:
            text = f"[{self.model_label}#{key}] {req.user_prompt[:200]}"
        return SubstrateResponse(
            text=text,
            model_id=self.model_label,
            usage={"input_tokens": len(req.user_prompt), "output_tokens": len(text)},
            proof={"prompt_hash": key, "canned_hit": key in self.canned},
        )
