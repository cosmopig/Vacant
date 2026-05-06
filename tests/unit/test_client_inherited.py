"""Unit tests for `ClientInheritedSubstrate`. (D2)

The substrate's contract is small but load-bearing — it must round-trip
the caller's LLM callback faithfully and record enough metadata for
reputation per-substrate to attribute the inference correctly.
"""

from __future__ import annotations

import pytest

from vacant.substrate.base import SubstrateRequest
from vacant.substrate.client_inherited import (
    ClientInheritedSubstrate,
    SubstrateHandle,
)


@pytest.mark.asyncio
async def test_substrate_round_trips_callback() -> None:
    seen: list[tuple[str, str]] = []

    async def cb(system_prompt: str, user_prompt: str) -> str:
        seen.append((system_prompt, user_prompt))
        return f"borrowed: {user_prompt}"

    sub = ClientInheritedSubstrate(
        callback=cb,
        handle=SubstrateHandle(model_hint="claude-sonnet-4-6"),
        caller_vacant_id_hex="ab" * 32,
    )
    req = SubstrateRequest(system_prompt="be honest", user_prompt="ping")
    res = await sub.infer(req)

    assert res.text == "borrowed: ping"
    assert res.model_id == "claude-sonnet-4-6"
    assert seen == [("be honest", "ping")]
    # Substrate identity is auditable.
    assert sub.name == f"client-inherited:{'ab' * 32}:claude-sonnet-4-6"
    assert res.proof["borrowed_from"] == "ab" * 32
    assert res.proof["model_hint"] == "claude-sonnet-4-6"
    assert res.proof["substrate_kind"] == "client-inherited"


@pytest.mark.asyncio
async def test_substrate_anonymous_caller_is_handled() -> None:
    """When `caller_vacant_id_hex` is empty the name still well-formed."""

    async def cb(_s: str, _u: str) -> str:
        return "ok"

    sub = ClientInheritedSubstrate(callback=cb)
    assert sub.name == "client-inherited:anonymous:unknown"


def test_handle_borrowed_from_format() -> None:
    h = SubstrateHandle(model_hint="gpt-4o", transport_callback_id="cb-7")
    assert h.borrowed_from("cd" * 32) == f"client-inherited:{'cd' * 32}:gpt-4o"
    assert h.transport_callback_id == "cb-7"


def test_logbook_entry_payload_records_borrow() -> None:
    async def cb(_s: str, _u: str) -> str:
        return ""

    sub = ClientInheritedSubstrate(
        callback=cb,
        handle=SubstrateHandle(model_hint="mistral-large", transport_callback_id="t-1"),
        caller_vacant_id_hex="ef" * 32,
    )
    payload = sub.to_logbook_entry()
    assert payload == {
        "substrate_kind": "client-inherited",
        "model_hint": "mistral-large",
        "borrowed_from": "ef" * 32,
        "transport_callback_id": "t-1",
    }


@pytest.mark.asyncio
async def test_substrate_propagates_callback_exceptions() -> None:
    """If the caller's LLM raises, the substrate surfaces the error.

    The caller's brain failing must not be masked by the borrowing
    layer — reputation tracking depends on knowing the inference
    failed, not on a silent empty response.
    """

    async def cb(_s: str, _u: str) -> str:
        raise RuntimeError("client LLM unavailable")

    sub = ClientInheritedSubstrate(callback=cb)
    with pytest.raises(RuntimeError, match="client LLM unavailable"):
        await sub.infer(SubstrateRequest(system_prompt="", user_prompt="ping"))
