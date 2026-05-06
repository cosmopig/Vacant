"""MistralSubstrate unit tests with mocked httpx transport."""

from __future__ import annotations

import json

import httpx
import pytest

from tests.unit.test_substrate_openai import _patch_async_client
from vacant.substrate import MistralSubstrate, SubstrateRequest
from vacant.substrate.errors import SubstrateUnavailableError


@pytest.mark.asyncio
async def test_mistral_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", "ml-test")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "mistral-large-2411",
                "choices": [{"message": {"content": "bonjour"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 1},
            },
        )

    captured = _patch_async_client(monkeypatch, handler)

    sub = MistralSubstrate()
    assert sub.name == "mistral:mistral-large-latest"
    rsp = await sub.infer(SubstrateRequest(system_prompt="s", user_prompt="hi"))
    assert rsp.text == "bonjour"
    assert rsp.model_id == "mistral-large-2411"
    assert rsp.usage == {"input_tokens": 4, "output_tokens": 1}

    req = captured[0]
    assert str(req.url) == "https://api.mistral.ai/v1/chat/completions"
    assert req.headers["Authorization"] == "Bearer ml-test"
    body = json.loads(req.content)
    assert body["model"] == "mistral-large-latest"


@pytest.mark.asyncio
async def test_mistral_missing_api_key(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    from vacant.substrate import _env

    _env.reset_dotenv_cache_for_tests()

    with pytest.raises(SubstrateUnavailableError, match="MISTRAL_API_KEY"):
        await MistralSubstrate().infer(SubstrateRequest(system_prompt="s", user_prompt="u"))
