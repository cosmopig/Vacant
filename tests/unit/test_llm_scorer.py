"""Phase 2 — LLM 5D scorer + substrate-driven serve behavior.

Covers:
- `parse_scorer_response` tolerates markdown fences, preamble, missing
  dims, out-of-range floats
- `score_response_with_llm` round-trips through a fake substrate
- `LLMScorer.score` returns 5 dims in [0,1]; `substrate_tag` is shaped
- `substrate_behavior` wraps a backend into a `BehaviorFn` that sets a
  `SelfEval` on the response
- `resolve_substrate("mock")` returns a working `MockSubstrate`;
  unknown name raises `ValueError`
"""

from __future__ import annotations

import pytest

from vacant.cli.substrate_behavior import (
    SUBSTRATE_FACTORIES,
    build_scorer_from_name,
    resolve_substrate,
    substrate_behavior,
)
from vacant.core.constants import REPUTATION_DIMS
from vacant.core.crypto import keygen
from vacant.core.types import EMPTY_PREV_HASH, VacantId
from vacant.protocol.envelope import A2AMessage, A2APart, VacantEnvelope
from vacant.substrate.base import SubstrateBackend, SubstrateRequest, SubstrateResponse
from vacant.substrate.scorer import (
    LLMScorer,
    parse_scorer_response,
    score_response_with_llm,
)

# --- parse_scorer_response --------------------------------------------------


def test_parse_plain_json() -> None:
    raw = '{"factual": 0.9, "logical": 0.8, "relevance": 0.7, "honesty": 0.6, "adoption": 0.5}'
    out = parse_scorer_response(raw)
    assert out == {
        "factual": 0.9,
        "logical": 0.8,
        "relevance": 0.7,
        "honesty": 0.6,
        "adoption": 0.5,
    }


def test_parse_markdown_fence() -> None:
    raw = '```json\n{"factual": 0.5, "logical": 0.5, "relevance": 0.5, "honesty": 0.5, "adoption": 0.5}\n```'
    out = parse_scorer_response(raw)
    assert out["factual"] == 0.5


def test_parse_preamble_tolerated() -> None:
    raw = 'Sure, here\'s my evaluation:\n{"factual": 0.3, "logical": 0.4, "relevance": 0.5, "honesty": 0.6, "adoption": 0.7}\nLet me know if you want more detail.'
    out = parse_scorer_response(raw)
    assert out["honesty"] == 0.6


def test_parse_missing_dim_defaults_to_half() -> None:
    raw = '{"factual": 0.9}'
    out = parse_scorer_response(raw)
    assert set(out) == set(REPUTATION_DIMS)
    assert out["logical"] == 0.5


def test_parse_out_of_range_clamped() -> None:
    raw = '{"factual": 1.5, "logical": -0.2, "relevance": 0.5, "honesty": 0.5, "adoption": 0.5}'
    out = parse_scorer_response(raw)
    assert out["factual"] == 1.0
    assert out["logical"] == 0.0


def test_parse_no_json_raises() -> None:
    with pytest.raises(ValueError):
        parse_scorer_response("This is just commentary with no scores")


# --- score_response_with_llm + LLMScorer -----------------------------------


class _FakeBackend(SubstrateBackend):
    """A controllable backend that records calls + returns canned text."""

    def __init__(
        self,
        text: str = '{"factual":0.8,"logical":0.7,"relevance":0.9,"honesty":0.6,"adoption":0.5}',
    ) -> None:
        self._text = text
        self.received: list[SubstrateRequest] = []

    @property
    def name(self) -> str:
        return "fake"

    async def infer(self, req: SubstrateRequest) -> SubstrateResponse:
        self.received.append(req)
        return SubstrateResponse(text=self._text, model_id="fake-1")


@pytest.mark.asyncio
async def test_score_response_with_llm_happy_path() -> None:
    backend = _FakeBackend()
    out = await score_response_with_llm(
        request_text="What is 2+2?",
        response_text="4",
        scorer=backend,
    )
    assert out["relevance"] == 0.9
    assert set(out) == set(REPUTATION_DIMS)
    # System + user prompts went through.
    assert len(backend.received) == 1
    assert "Q: What is 2+2?" in backend.received[0].user_prompt


@pytest.mark.asyncio
async def test_score_response_with_llm_raises_on_parse_failure() -> None:
    """The function raises `ValueError` so the caller can decide between
    fallback paths. Previously this function silently fell back to
    heuristic, which made the review's `substrate` field lie about
    which path actually scored."""
    backend = _FakeBackend(text="random text with no json")
    with pytest.raises(ValueError):
        await score_response_with_llm(
            request_text="hi", response_text="hello world", scorer=backend
        )


@pytest.mark.asyncio
async def test_llm_scorer_substrate_tag_shape() -> None:
    backend = _FakeBackend()
    sc = LLMScorer(backend=backend, label="test")
    assert sc.substrate_tag == "test:fake"
    out = await sc.score(request_text="q", response_text="a")
    assert "factual" in out


# --- substrate_behavior end-to-end -----------------------------------------


@pytest.mark.asyncio
async def test_substrate_behavior_wraps_backend_into_BehaviorFn() -> None:
    from datetime import UTC, datetime

    backend = _FakeBackend(text="answer: 42")
    behavior = substrate_behavior(backend, system_prompt="be brief")
    _sk, vk = keygen()
    sk2, vk2 = keygen()
    env = VacantEnvelope(
        from_vacant_id=VacantId.from_verify_key(vk),
        to_vacant_id=VacantId.from_verify_key(vk2),
        sequence_no=1,
        timestamp=datetime.now(UTC),
        prev_envelope_hash=EMPTY_PREV_HASH,
        payload=A2AMessage(role="ROLE_USER", parts=[A2APart(text="What is 6*7?")]),
        idempotency_key="k",
    ).signed(sk2)
    response = await behavior(env)
    assert response.role == "ROLE_AGENT"
    assert response.parts[0].text == "answer: 42"
    # Self-eval cryptographically attached (technical.html §Layer 1).
    assert response.self_eval is not None
    assert 0.0 <= response.self_eval.factual <= 1.0
    assert 0.0 <= response.self_eval.confidence <= 1.0


@pytest.mark.asyncio
async def test_substrate_behavior_self_eval_low_on_empty_response() -> None:
    """An empty response should self-evaluate as low confidence + low
    on factual/relevance — honest acknowledgement of nothing-being-said."""
    backend = _FakeBackend(text="")
    behavior = substrate_behavior(backend)
    from datetime import UTC, datetime

    _sk, vk = keygen()
    sk2, vk2 = keygen()
    env = VacantEnvelope(
        from_vacant_id=VacantId.from_verify_key(vk),
        to_vacant_id=VacantId.from_verify_key(vk2),
        sequence_no=1,
        timestamp=datetime.now(UTC),
        prev_envelope_hash=EMPTY_PREV_HASH,
        payload=A2AMessage(role="ROLE_USER", parts=[A2APart(text="x")]),
        idempotency_key="k",
    ).signed(sk2)
    response = await behavior(env)
    assert response.self_eval is not None
    assert response.self_eval.confidence < 0.5
    assert response.self_eval.factual < 0.5


# --- resolve_substrate ------------------------------------------------------


def test_resolve_substrate_mock_works() -> None:
    backend = resolve_substrate("mock")
    assert backend.name.startswith("mock:")


def test_resolve_substrate_unknown_raises_value_error() -> None:
    with pytest.raises(ValueError):
        resolve_substrate("not-a-real-substrate")


def test_substrate_factory_names_cover_documented_options() -> None:
    """Every name in the `--substrate` help text must resolve."""
    for documented in (
        "mock",
        "deterministic",
        "anthropic",
        "openai",
        "ollama",
        "gemini",
        "mistral",
    ):
        assert documented in SUBSTRATE_FACTORIES


def test_build_scorer_from_none_returns_none() -> None:
    assert build_scorer_from_name(None) is None


def test_build_scorer_from_mock_returns_scorer() -> None:
    sc = build_scorer_from_name("mock")
    assert sc is not None
    assert sc.substrate_tag.startswith("llm-5d-scorer:mock:")
