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
from vacant.substrate.gemini import GeminiSubstrate
from vacant.substrate.hermes import HermesSubstrate
from vacant.substrate.mistral import MistralSubstrate
from vacant.substrate.mock import MockSubstrate
from vacant.substrate.ollama import OllamaSubstrate
from vacant.substrate.openai import OpenAISubstrate
from vacant.substrate.openclaw import OpenClawSubstrate

__all__ = [
    "AnthropicSubstrate",
    "ClientInheritedSubstrate",
    "DeterministicSubstrate",
    "GeminiSubstrate",
    "HermesSubstrate",
    "MistralSubstrate",
    "MockSubstrate",
    "OllamaSubstrate",
    "OpenAISubstrate",
    "OpenClawSubstrate",
    "SamplingCallback",
    "SubstrateBackend",
    "SubstrateError",
    "SubstrateHandle",
    "SubstrateRateLimitError",
    "SubstrateRequest",
    "SubstrateResponse",
    "SubstrateUnavailableError",
]
