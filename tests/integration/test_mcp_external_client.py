"""A3 acceptance: an external MCP client connects + calls a vacant.

Uses the official `mcp` Python SDK as a client. The vacant runs as a
subprocess driven over stdio (`python -m vacant.cli.mcp_serve_test_runner
<name>`); the test:

1. Lists tools — expects `vacant_describe` and `vacant_call`.
2. Invokes `vacant_describe` — expects capability text in the response.
3. Builds a real signed A2A envelope and invokes `vacant_call` — expects
   a signed response envelope verifiable under the vacant's pubkey.

This is the "the thesis defense rests on this test" integration. If
this passes, an external MCP-aware tool (Claude Desktop, the
@modelcontextprotocol/inspector CLI) can talk to a vacant unmodified.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from vacant.cli import local_store as ls
from vacant.core.crypto import keygen
from vacant.core.types import VacantId
from vacant.protocol.envelope import (
    A2AMessage,
    A2APart,
    VacantEnvelope,
    from_a2a_jsonrpc,
    to_a2a_jsonrpc,
)

pytestmark = pytest.mark.slow


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("VACANT_HOME", str(home))
    return home


def _stdio_params(name: str, home: Path) -> StdioServerParameters:
    """Spawn `python -m vacant.cli.mcp_serve_test_runner <name>` over stdio."""
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "vacant.cli.mcp_serve_test_runner", name],
        env={**os.environ, "VACANT_HOME": str(home)},
    )


@pytest.mark.asyncio
async def test_external_client_lists_tools(isolated_home: Path) -> None:
    ls.init_vacant("alice", insecure_demo=True)  # subprocess can't share fake keyring
    params = _stdio_params("alice", isolated_home)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
    names = [t.name for t in tools.tools]
    assert "vacant_describe" in names
    assert "vacant_call" in names


@pytest.mark.asyncio
async def test_external_client_describes_vacant(isolated_home: Path) -> None:
    ls.init_vacant("alice", insecure_demo=True)  # subprocess can't share fake keyring
    meta = ls.load_meta("alice")
    params = _stdio_params("alice", isolated_home)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool("vacant_describe", arguments={})
    # FastMCP returns the dict serialized as TextContent JSON.
    text = res.content[0].text  # type: ignore[union-attr]
    obj = json.loads(text)
    assert obj["vacant_id"] == meta.vacant_id_hex
    assert obj["capability_text"]


@pytest.mark.asyncio
async def test_external_client_calls_vacant_with_signed_envelope(
    isolated_home: Path,
) -> None:
    ls.init_vacant("alice", insecure_demo=True)  # subprocess can't share fake keyring
    meta = ls.load_meta("alice")
    target_vid = VacantId(pubkey_bytes=bytes.fromhex(meta.vacant_id_hex))

    # Build a fresh caller (not the one being served).
    caller_sk, caller_vk = keygen()
    caller_vid = VacantId.from_verify_key(caller_vk)

    request = VacantEnvelope(
        from_vacant_id=caller_vid,
        to_vacant_id=target_vid,
        sequence_no=1,
        timestamp=datetime.now(UTC),
        payload=A2AMessage(role="ROLE_USER", parts=[A2APart(text="hi from MCP client")]),
        idempotency_key="mcp-001",
    ).signed(caller_sk)
    envelope = to_a2a_jsonrpc(request)

    params = _stdio_params("alice", isolated_home)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool("vacant_call", arguments={"envelope": envelope})

    text = res.content[0].text  # type: ignore[union-attr]
    payload = json.loads(text)
    assert "message" in payload, payload
    wrapped = {
        "jsonrpc": "2.0",
        "id": "rsp",
        "method": "message/send",
        "params": {"message": payload["message"]},
    }
    response_env = from_a2a_jsonrpc(wrapped)
    assert response_env.from_vacant_id.hex() == target_vid.hex()
    assert response_env.verify(target_vid.verify_key()) is True
    assert "hi from MCP client" in response_env.payload.parts[0].text
