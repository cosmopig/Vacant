"""Anthropic substrate — F14 dotenv auto-load regression test.

The substrate's `infer()` must surface a `SubstrateUnavailableError`
with a clear message when the API key is missing AND must auto-load
`.env` from the cwd before declaring the key absent (otherwise the
README workflow `echo ANTHROPIC_API_KEY=... > .env` is a lie).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from vacant.substrate import anthropic as ant
from vacant.substrate.base import SubstrateRequest
from vacant.substrate.errors import SubstrateUnavailableError


@pytest.fixture(autouse=True)
def reset_dotenv_cache() -> None:
    """Each test re-resolves dotenv (the loader caches a 'done' flag)."""
    ant._DOTENV_LOADED = False


@pytest.mark.asyncio
async def test_missing_key_raises_substrate_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    sub = ant.AnthropicSubstrate()
    with pytest.raises(SubstrateUnavailableError) as exc:
        await sub.infer(SubstrateRequest(system_prompt="x", user_prompt="y"))
    assert "ANTHROPIC_API_KEY" in str(exc.value)
    assert ".env" in str(exc.value)


@pytest.mark.asyncio
async def test_dotenv_file_supplies_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """F14: a `.env` in the cwd should populate `os.environ` so an
    explicit `export` is not required for the README flow."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-test-from-dotenv\n")

    # Capture whether `infer` got past the key-check by stubbing the
    # SDK call. We don't reach the network — we only need to confirm
    # the key was resolved from `.env`.
    sub = ant.AnthropicSubstrate()
    try:
        await sub.infer(SubstrateRequest(system_prompt="x", user_prompt="y"))
    except SubstrateUnavailableError as exc:
        # The SDK *is* installed (declared dep), so a missing-key
        # error here means dotenv didn't load — the test should
        # surface it. Any other exception (network refusal, bogus
        # key rejection) is fine: it means we got past the gate.
        msg = str(exc)
        assert "ANTHROPIC_API_KEY not set" not in msg, (
            "dotenv did not populate the env var; key gate triggered"
        )
    except Exception:  # noqa: S110
        # Got past the key-check; that's the contract.
        pass
    assert os.environ.get("ANTHROPIC_API_KEY") == "sk-test-from-dotenv"


@pytest.mark.asyncio
async def test_explicit_env_overrides_dotenv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-export")
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-from-dotenv\n")
    sub = ant.AnthropicSubstrate()
    try:
        await sub.infer(SubstrateRequest(system_prompt="x", user_prompt="y"))
    except Exception:  # noqa: S110
        pass
    # `load_dotenv(override=False)` keeps the exported value.
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-from-export"
