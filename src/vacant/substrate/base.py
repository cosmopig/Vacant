"""Abstract substrate backend interface.

Concrete implementations (Anthropic / Ollama / Mock / Deterministic) are
filled in by later component PRs. P0 ships only the contract so downstream
code can import `SubstrateBackend` for type annotations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SubstrateRequest(BaseModel):
    """A single inference request handed to a substrate backend."""

    model_config = ConfigDict(frozen=True)

    system_prompt: str
    user_prompt: str
    tools: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SubstrateResponse(BaseModel):
    """A single inference response, plus optional substrate proof material."""

    model_config = ConfigDict(frozen=True)

    text: str
    model_id: str
    usage: dict[str, int] = Field(default_factory=dict)
    proof: dict[str, Any] = Field(default_factory=dict)


class SubstrateBackend(ABC):
    """Backend contract. Implementations must be safe to call from async code."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def infer(self, req: SubstrateRequest) -> SubstrateResponse: ...
