"""A5 — OTS calendar HTTP submit (`submit_to_calendar` / `submit_to_calendars`).

Tests run with an injected `httpx.MockTransport` so we never hit the
real network.
"""

from __future__ import annotations

import httpx
import pytest

from vacant.registry import (
    OTSAnchorError,
    OTSCalendarReceipt,
    submit_to_calendar,
    submit_to_calendars,
)
from vacant.registry.ots_anchor import OTS_UPGRADED_MAGIC


def _patched_async_client(responder, monkeypatch):
    """Replace `httpx.AsyncClient` with one that uses our MockTransport."""

    class _Patched(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(responder)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("vacant.registry.ots_anchor.httpx.AsyncClient", _Patched)


@pytest.mark.asyncio
async def test_submit_to_calendar_returns_real_ots_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mock calendar returns bytes that *do* look like a real
    `.ots` proof — receipt's `is_real` should be True."""
    fake_proof = OTS_UPGRADED_MAGIC + b"\xaa" * 64

    def _responder(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/digest")
        assert request.content == (b"\x42" * 32)
        return httpx.Response(200, content=fake_proof)

    _patched_async_client(_responder, monkeypatch)

    receipt = await submit_to_calendar(
        digest=b"\x42" * 32, calendar_url="https://calendar.example/"
    )
    assert isinstance(receipt, OTSCalendarReceipt)
    assert receipt.proof_bytes == fake_proof
    assert receipt.is_real is True
    assert len(receipt.proof_digest) == 32


@pytest.mark.asyncio
async def test_submit_to_calendar_marks_non_ots_response_as_unreal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"\xde\xad\xbe\xef" * 8)

    _patched_async_client(_responder, monkeypatch)

    receipt = await submit_to_calendar(
        digest=b"\x42" * 32, calendar_url="https://calendar.example/"
    )
    assert receipt.is_real is False


@pytest.mark.asyncio
async def test_submit_to_calendar_rejects_wrong_digest_length() -> None:
    with pytest.raises(OTSAnchorError):
        await submit_to_calendar(digest=b"too short", calendar_url="https://calendar.example/")


@pytest.mark.asyncio
async def test_submit_to_calendar_raises_on_server_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server down")

    _patched_async_client(_responder, monkeypatch)

    with pytest.raises(OTSAnchorError):
        await submit_to_calendar(digest=b"\x42" * 32, calendar_url="https://calendar.example/")


@pytest.mark.asyncio
async def test_submit_to_calendars_collects_only_successes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mix one calendar that succeeds with one that 500s — the parallel
    helper must return just the successful receipt, not crash."""

    def _responder(request: httpx.Request) -> httpx.Response:
        if "good" in str(request.url):
            return httpx.Response(200, content=OTS_UPGRADED_MAGIC + b"\x01" * 32)
        return httpx.Response(500, text="bad")

    _patched_async_client(_responder, monkeypatch)

    receipts = await submit_to_calendars(
        digest=b"\x42" * 32,
        calendar_urls=("https://good.example/", "https://bad.example/"),
    )
    assert len(receipts) == 1
    assert receipts[0].calendar_url == "https://good.example/"
    assert receipts[0].is_real is True


@pytest.mark.asyncio
async def test_submit_to_calendars_all_fail_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="all down")

    _patched_async_client(_responder, monkeypatch)

    receipts = await submit_to_calendars(
        digest=b"\x42" * 32,
        calendar_urls=("https://a.example/", "https://b.example/"),
    )
    assert receipts == []
