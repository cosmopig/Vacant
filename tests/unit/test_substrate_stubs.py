"""HermesSubstrate / OpenClawSubstrate stub unit tests.

These two substrates are deliberately stubs in D1 (the load-bearing
client integration is `client-inherited` in D2). The tests pin the
contract: they must surface a clear `SubstrateUnavailableError` and
their `name` must be substrate-namespaced so capability_card matching
still works.
"""

from __future__ import annotations

import pytest

from vacant.substrate import HermesSubstrate, OpenClawSubstrate, SubstrateRequest
from vacant.substrate.errors import SubstrateUnavailableError


@pytest.mark.asyncio
async def test_hermes_stub_unavailable(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("NOUS_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    from vacant.substrate import _env

    _env.reset_dotenv_cache_for_tests()

    sub = HermesSubstrate()
    assert sub.name.startswith("hermes:")
    with pytest.raises(SubstrateUnavailableError, match="stub"):
        await sub.infer(SubstrateRequest(system_prompt="s", user_prompt="u"))


@pytest.mark.asyncio
async def test_openclaw_stub_unavailable(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("OPENCLAW_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    from vacant.substrate import _env

    _env.reset_dotenv_cache_for_tests()

    sub = OpenClawSubstrate()
    assert sub.name.startswith("openclaw:")
    with pytest.raises(SubstrateUnavailableError, match="client-inherited"):
        await sub.infer(SubstrateRequest(system_prompt="s", user_prompt="u"))


def test_substrate_registry_exports_all() -> None:
    """All D1 substrates are exposed via the package surface."""
    from vacant import substrate

    for cls_name in (
        "OpenAISubstrate",
        "GeminiSubstrate",
        "MistralSubstrate",
        "HermesSubstrate",
        "OpenClawSubstrate",
    ):
        assert hasattr(substrate, cls_name), cls_name
        assert cls_name in substrate.__all__
