"""OpenAISubstrate unit tests with mocked httpx transport."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from vacant.substrate import OpenAISubstrate, SubstrateRequest
from vacant.substrate.errors import SubstrateRateLimitError, SubstrateUnavailableError


def _patch_async_client(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
) -> list[httpx.Request]:
    """Replace `httpx.AsyncClient` with one that uses MockTransport.

    Returns the list of captured requests for assertions.
    """
    captured: list[httpx.Request] = []

    def _record(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return handler(request)

    transport = httpx.MockTransport(_record)
    real_cls = httpx.AsyncClient

    def _factory(*args: object, **kwargs: object) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return real_cls(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx, "AsyncClient", _factory)
    return captured


@pytest.mark.asyncio
async def test_openai_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "gpt-4o-2024-08-06",
                "choices": [
                    {"message": {"content": "ok"}, "finish_reason": "stop"},
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 1},
            },
        )

    captured = _patch_async_client(monkeypatch, handler)

    sub = OpenAISubstrate()
    assert sub.name == "openai:gpt-4o"
    rsp = await sub.infer(SubstrateRequest(system_prompt="be helpful", user_prompt="hi"))
    assert rsp.text == "ok"
    assert rsp.model_id == "gpt-4o-2024-08-06"
    assert rsp.usage == {"input_tokens": 5, "output_tokens": 1}
    assert rsp.proof["finish_reason"] == "stop"

    assert len(captured) == 1
    req = captured[0]
    assert str(req.url) == "https://api.openai.com/v1/chat/completions"
    assert req.headers["Authorization"] == "Bearer sk-test"
    body = json.loads(req.content)
    assert body["model"] == "gpt-4o"
    assert body["messages"][0]["role"] == "system"
    assert body["temperature"] == 0.0


@pytest.mark.asyncio
async def test_openai_uses_custom_base_url_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.together.xyz/v1")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "gpt-4o",
                "choices": [{"message": {"content": "x"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    captured = _patch_async_client(monkeypatch, handler)

    rsp = await OpenAISubstrate().infer(SubstrateRequest(system_prompt="s", user_prompt="u"))
    assert rsp.proof["endpoint"] == "https://api.together.xyz/v1"
    assert str(captured[0].url).startswith("https://api.together.xyz/v1/chat/completions")


@pytest.mark.asyncio
async def test_openai_explicit_base_url_beats_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://env-wins.example/v1")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "x",
                "choices": [{"message": {"content": ""}, "finish_reason": "stop"}],
                "usage": {},
            },
        )

    captured = _patch_async_client(monkeypatch, handler)
    sub = OpenAISubstrate(base_url="http://localhost:8000/v1")
    await sub.infer(SubstrateRequest(system_prompt="s", user_prompt="u"))
    assert str(captured[0].url).startswith("http://localhost:8000/v1/")


@pytest.mark.asyncio
async def test_openai_missing_api_key(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    # Move cwd to a directory with no `.env`, otherwise dotenv may pull a key
    # from the developer's checkout.
    monkeypatch.chdir(tmp_path)
    from vacant.substrate import _env

    _env.reset_dotenv_cache_for_tests()

    with pytest.raises(SubstrateUnavailableError, match="OPENAI_API_KEY"):
        await OpenAISubstrate().infer(SubstrateRequest(system_prompt="s", user_prompt="u"))


@pytest.mark.asyncio
async def test_openai_rate_limit_retries_then_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "slow down"})

    _patch_async_client(monkeypatch, handler)
    # avoid real backoff sleeps in CI
    monkeypatch.setattr("vacant.substrate.openai.asyncio.sleep", _no_sleep)

    with pytest.raises(SubstrateRateLimitError):
        await OpenAISubstrate(max_retries=2).infer(
            SubstrateRequest(system_prompt="s", user_prompt="u")
        )


async def _no_sleep(_seconds: float) -> None:
    return None
