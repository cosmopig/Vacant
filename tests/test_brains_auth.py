"""OpenAI-compatible adapter 的 Bearer token 支援，不把金鑰寫進 URL/payload。"""

from __future__ import annotations

from vacant import brains


def test_openai_brain_passes_api_key_as_authorization(monkeypatch):
    seen = {}

    def fake_post(url, payload, timeout, *, api_key=None):
        seen.update(url=url, payload=payload, timeout=timeout, api_key=api_key)
        return {
            "choices": [{"message": {"content": "OK"}}],
            "usage": {"total_tokens": 3},
        }

    monkeypatch.setattr(brains, "_post", fake_post)
    brain = brains.OpenAIBrain(
        "https://example.test", "model", api_key="secret-token", max_tokens=None)
    assert brain.generate("hello") == "OK"
    assert seen["api_key"] == "secret-token"
    assert "secret-token" not in seen["url"]
    assert "secret-token" not in str(seen["payload"])


def test_lmstudio_openai_path_forwards_api_key(monkeypatch):
    seen = {}

    def fake_post(url, payload, timeout, *, api_key=None):
        seen["api_key"] = api_key
        return {"choices": [{"message": {"content": "OK"}}]}

    monkeypatch.setattr(brains, "_post", fake_post)
    brain = brains.LMStudioBrain(
        "https://example.test", "model", api="openai", api_key="token")
    assert brain.generate("hello") == "OK"
    assert seen["api_key"] == "token"
