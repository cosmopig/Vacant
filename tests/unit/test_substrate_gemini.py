"""GeminiSubstrate unit tests with mocked httpx transport."""

from __future__ import annotations

import json

import httpx
import pytest

from tests.unit.test_substrate_openai import _patch_async_client
from vacant.substrate import GeminiSubstrate, SubstrateRequest
from vacant.substrate.errors import SubstrateUnavailableError


@pytest.mark.asyncio
async def test_gemini_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"parts": [{"text": "hello"}, {"text": " world"}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 2},
            },
        )

    captured = _patch_async_client(monkeypatch, handler)

    sub = GeminiSubstrate()
    assert sub.name == "gemini:gemini-2.0-flash"
    rsp = await sub.infer(SubstrateRequest(system_prompt="s", user_prompt="hi"))
    assert rsp.text == "hello world"
    assert rsp.usage == {"input_tokens": 3, "output_tokens": 2}
    assert rsp.proof["finish_reason"] == "STOP"

    req = captured[0]
    assert "gemini-2.0-flash:generateContent" in str(req.url)
    assert req.headers["x-goog-api-key"] == "google-test"
    body = json.loads(req.content)
    assert body["system_instruction"]["parts"][0]["text"] == "s"
    assert body["contents"][0]["parts"][0]["text"] == "hi"


@pytest.mark.asyncio
async def test_gemini_missing_api_key(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    from vacant.substrate import _env

    _env.reset_dotenv_cache_for_tests()

    with pytest.raises(SubstrateUnavailableError, match="GOOGLE_API_KEY"):
        await GeminiSubstrate().infer(SubstrateRequest(system_prompt="s", user_prompt="u"))


@pytest.mark.asyncio
async def test_gemini_no_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test")
    _patch_async_client(
        monkeypatch,
        lambda _r: httpx.Response(200, json={"candidates": []}),
    )

    with pytest.raises(SubstrateUnavailableError, match="no candidates"):
        await GeminiSubstrate().infer(SubstrateRequest(system_prompt="s", user_prompt="u"))
