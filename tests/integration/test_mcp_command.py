"""`vacant mcp` stdio subcommand acceptance.

The plugin manifest (`.claude-plugin/plugin.json`) makes Claude Code
spawn the vacant via:

    uvx --from git+https://github.com/cosmopig/Vacant vacant mcp

Tests in this module verify that the `vacant mcp` subprocess speaks
the MCP wire protocol over stdio: connect via the `mcp` SDK's
`stdio_client`, run `initialize`, and then exercise `tools/list` +
`vacant_describe` to confirm the registered vacant is reachable.

Two fixtures cover the two identity-resolution branches in
`mcp_cmd`:

* a local vacant on disk (`vacant init` was run first), and
* no local vacant — `vacant mcp` falls back to an ephemeral demo
  identity and emits a stderr WARN.

Both subprocess paths use `insecure_demo=True` for the on-disk vacant
because the spawned process can't share the in-process fake keyring
fixture from `tests/conftest.py`.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from vacant.cli import local_store as ls

pytestmark = pytest.mark.slow


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("VACANT_HOME", str(home))
    return home


def _stdio_params(*, name: str | None, home: Path) -> StdioServerParameters:
    """Spawn `vacant mcp` (optionally with `--name`) as a stdio MCP server."""
    args = ["-m", "vacant.cli", "mcp"]
    if name is not None:
        args += ["--name", name]
    return StdioServerParameters(
        command=sys.executable,
        args=args,
        env={**os.environ, "VACANT_HOME": str(home)},
    )


@pytest.mark.asyncio
async def test_vacant_mcp_subcommand_initialize_with_local_vacant(
    isolated_home: Path,
) -> None:
    """`vacant mcp --name alice` against an initialised local vacant —
    `initialize` returns server capabilities, `tools/list` shows the
    vacant tools, `vacant_describe` returns alice's identity."""
    ls.init_vacant("alice", insecure_demo=True)  # subprocess needs plaintext seed
    meta = ls.load_meta("alice")

    params = _stdio_params(name="alice", home=isolated_home)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init_result = await session.initialize()
            # Server capabilities present (proves the handshake completed).
            assert init_result.serverInfo is not None
            tools = await session.list_tools()
            describe = await session.call_tool("vacant_describe", arguments={})

    names = [t.name for t in tools.tools]
    assert "vacant_describe" in names
    assert "vacant_call" in names

    text = describe.content[0].text  # type: ignore[union-attr]
    obj = json.loads(text)
    assert obj["vacant_id"] == meta.vacant_id_hex


@pytest.mark.asyncio
async def test_vacant_mcp_subcommand_falls_back_to_ephemeral_when_no_local(
    isolated_home: Path,
) -> None:
    """No local vacant exists ⇒ `vacant mcp` (no `--name`) launches an
    ephemeral demo vacant. The MCP server is still reachable; the
    returned `vacant_id` is a fresh hex string (and the operator gets
    a stderr WARN)."""
    # Confirm precondition: no local vacants before the subprocess starts.
    assert ls.list_vacant_names() == []

    params = _stdio_params(name=None, home=isolated_home)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init_result = await session.initialize()
            assert init_result.serverInfo is not None
            describe = await session.call_tool("vacant_describe", arguments={})

    text = describe.content[0].text  # type: ignore[union-attr]
    obj = json.loads(text)
    assert isinstance(obj["vacant_id"], str)
    # Ed25519 pubkey hex is 64 chars.
    assert len(obj["vacant_id"]) == 64
    # The ephemeral capability_text mentions the demo identity.
    assert obj["capability_text"]
    assert "demo" in obj["capability_text"].lower()
