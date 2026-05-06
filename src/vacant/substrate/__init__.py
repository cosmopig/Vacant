"""Substrate backend abstraction + concrete impls."""

from vacant.substrate.anthropic import AnthropicSubstrate
from vacant.substrate.base import SubstrateBackend, SubstrateRequest, SubstrateResponse
from vacant.substrate.client_inherited import (
    ClientInheritedSubstrate,
    SamplingCallback,
    SubstrateHandle,
)
from vacant.substrate.deterministic import DeterministicSubstrate
from vacant.substrate.errors import (
    SubstrateError,
    SubstrateRateLimitError,
    SubstrateUnavailableError,
)
from vacant.substrate.mock import MockSubstrate
from vacant.substrate.ollama import OllamaSubstrate

__all__ = [
    "AnthropicSubstrate",
    "ClientInheritedSubstrate",
    "DeterministicSubstrate",
    "MockSubstrate",
    "OllamaSubstrate",
    "SamplingCallback",
    "SubstrateBackend",
    "SubstrateError",
    "SubstrateHandle",
    "SubstrateRateLimitError",
    "SubstrateRequest",
    "SubstrateResponse",
    "SubstrateUnavailableError",
]
