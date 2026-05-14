"""Substrate-driven `vacant serve` behavior + scorer wiring (Pfix9 Phase 2).

The default `echo_behavior` in `cli.server` returns the request text
verbatim — useful for CI / acceptance tests but useless for actually
answering questions. This module provides:

- `substrate_behavior(backend, system_prompt)` — a `BehaviorFn` that
  forwards the incoming A2A user text to an `SubstrateBackend.infer`
  and wraps the result in a signed response envelope. Also attaches a
  `SelfEval` so the responder cryptographically commits to its own
  confidence (technical.html §Layer 1).
- `resolve_substrate(name)` — name → `SubstrateBackend` factory shared
  by `vacant grow --substrate` and `vacant serve --substrate`.
- `build_scorer_from_name(name)` — same for the LLM scorer side.

Design notes:
- We don't cache substrate instances. Each call to `resolve_substrate`
  builds a fresh client; cheap because the SDK clients are lazy.
- The `system_prompt` is per-vacant — taken from the vacant's
  `BehaviorBundle.system_prompt`, so different vacants on the same
  machine can have different personalities.
- Self-eval scores are *self-estimated* and intentionally heuristic
  (length + refusal markers). The honest signal is the gap with
  peer/external scoring; we don't want the responder to also be a
  good judge of itself or the self/peer eval gap collapses.
"""

from __future__ import annotations

from typing import Any

from vacant.cli.server import BehaviorFn
from vacant.protocol.envelope import A2AMessage, A2APart, SelfEval, VacantEnvelope
from vacant.substrate.base import SubstrateBackend, SubstrateRequest
from vacant.substrate.scorer import LLMScorer

__all__ = [
    "SUBSTRATE_FACTORIES",
    "build_scorer_from_name",
    "resolve_substrate",
    "substrate_behavior",
]


def _self_estimate(response_text: str) -> SelfEval:
    """Heuristic 5D self-assessment.

    Deliberately simple — the responder's job is to honestly *guess*,
    not to be a great judge. If the responder's self-eval consistently
    diverges from peer reviews, the aggregator's
    `record_self_eval_gap` channel will detect dishonesty and tank the
    honesty dim.
    """
    text = (response_text or "").strip()
    n = len(text)
    if not text:
        return SelfEval(
            factual=0.1, logical=0.1, relevance=0.1, honesty=0.5, adoption=0.1, confidence=0.1
        )
    refusal = any(
        marker in text.lower()
        for marker in ("i cannot", "i can't", "refuse", "unable to", "i don't know")
    )
    if refusal:
        # Refusals admit uncertainty → high honesty, lower relevance.
        return SelfEval(
            factual=0.5, logical=0.6, relevance=0.4, honesty=0.85, adoption=0.3, confidence=0.5
        )
    base = min(0.85, 0.5 + n / 600.0)
    return SelfEval(
        factual=round(base, 3),
        logical=round(base * 0.95, 3),
        relevance=round(base, 3),
        honesty=0.75,
        adoption=round(min(0.8, base * 0.9), 3),
        confidence=round(min(0.9, base + 0.05), 3),
    )


def substrate_behavior(
    backend: SubstrateBackend,
    system_prompt: str = "You are a helpful AI agent residing as a vacant on a peer-to-peer network.",
) -> BehaviorFn:
    """Return a `BehaviorFn` that runs incoming A2A text through `backend`.

    The returned callable:
    1. Concatenates all `text` parts of the incoming envelope as the
       user prompt.
    2. Calls `backend.infer(SubstrateRequest(system, user))`.
    3. Returns an `A2AMessage` with the response text + a self-eval
       cryptographically bound to the response (via the envelope
       signature, see `protocol.envelope.SelfEval`).
    """

    async def _behavior(env: VacantEnvelope) -> A2AMessage:
        user_text = " ".join(p.text for p in env.payload.parts if p.type == "text")
        req = SubstrateRequest(
            system_prompt=system_prompt,
            user_prompt=user_text,
            metadata={
                "caller_vid": env.from_vacant_id.hex(),
                "responder_vid": env.to_vacant_id.hex(),
            },
        )
        resp = await backend.infer(req)
        return A2AMessage(
            role="ROLE_AGENT",
            parts=[A2APart(text=resp.text)],
            self_eval=_self_estimate(resp.text),
        )

    return _behavior


# --- substrate name resolution ---------------------------------------------


def _make_mock(seed: int = 0) -> SubstrateBackend:
    from vacant.substrate.mock import MockSubstrate

    return MockSubstrate(seed=seed)


def _make_deterministic() -> SubstrateBackend:
    from vacant.substrate.deterministic import DeterministicSubstrate

    return DeterministicSubstrate()


def _make_anthropic() -> SubstrateBackend:
    from vacant.substrate.anthropic import AnthropicSubstrate

    return AnthropicSubstrate()


def _make_openai() -> SubstrateBackend:
    from vacant.substrate.openai import OpenAISubstrate

    return OpenAISubstrate()


def _make_ollama() -> SubstrateBackend:
    from vacant.substrate.ollama import OllamaSubstrate

    return OllamaSubstrate()


def _make_gemini() -> SubstrateBackend:
    from vacant.substrate.gemini import GeminiSubstrate

    return GeminiSubstrate()


def _make_mistral() -> SubstrateBackend:
    from vacant.substrate.mistral import MistralSubstrate

    return MistralSubstrate()


SUBSTRATE_FACTORIES: dict[str, Any] = {
    "mock": _make_mock,
    "deterministic": _make_deterministic,
    "anthropic": _make_anthropic,
    "openai": _make_openai,
    "ollama": _make_ollama,
    "gemini": _make_gemini,
    "mistral": _make_mistral,
}


def resolve_substrate(name: str) -> SubstrateBackend:
    """Build a fresh substrate backend by name.

    `name` matches the strings used by `vacant demo --substrate=<name>`
    so operators have a single mental model. Unknown names raise
    `ValueError` — fail loud rather than silently degrade.
    """
    factory = SUBSTRATE_FACTORIES.get(name)
    if factory is None:
        raise ValueError(f"unknown substrate {name!r}; known: {sorted(SUBSTRATE_FACTORIES)}")
    result: SubstrateBackend = factory()
    return result


def build_scorer_from_name(name: str | None) -> LLMScorer | None:
    """Construct an `LLMScorer` from a substrate name, or None when no
    scorer is requested.

    Operator passes `--scorer-substrate=anthropic` to `vacant grow` and
    the grow loop wires the scorer into every peer-review tick.
    """
    if name is None:
        return None
    backend = resolve_substrate(name)
    return LLMScorer(backend=backend)
