"""Acceptance: ``vacant_spawn`` MCP tool — autonomous lineage growth.

The thesis-load-bearing claim is that an LLM-driven client can ask a
vacant to give birth to a specialized child *on its own*, and the
resulting parent_id chain + dual signatures + persisted directory
all hold up. This test exercises the MCP surface end-to-end:

1. Persistent vacant ``alice`` on disk (Pfix5 ``--insecure-demo`` flow).
2. External MCP client (this test) calls ``vacant_spawn`` with a
   policy mutation describing the kind of child it wants.
3. We assert:
   - the tool returned a child vacant_id + persistent name
   - the child directory exists with key.json / logbook.jsonl /
     meta.json and a BIRTH entry signed by the child
   - alice's logbook gained a signed SPAWN entry pointing at the child
   - the child's meta.json carries parent_id_hex = alice's id
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from vacant.cli import local_store as ls
from vacant.core.types import VacantId

pytestmark = pytest.mark.slow


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("VACANT_HOME", str(home))
    return home


def _stdio_params(name: str, home: Path) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "vacant.cli.mcp_serve_test_runner", name],
        env={**os.environ, "VACANT_HOME": str(home)},
    )


@pytest.mark.asyncio
async def test_vacant_spawn_creates_child_with_lineage(isolated_home: Path) -> None:
    ls.init_vacant("alice", insecure_demo=True)
    alice_meta = ls.load_meta("alice")
    alice_vid = VacantId(pubkey_bytes=bytes.fromhex(alice_meta.vacant_id_hex))

    params = _stdio_params("alice", isolated_home)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = sorted(t.name for t in tools.tools)
            assert "vacant_spawn" in tool_names, tool_names

            result = await session.call_tool(
                "vacant_spawn",
                arguments={
                    "policy_mutation": "always cite the source paragraph",
                    "child_name_hint": "cite",
                },
            )

    payload: dict[str, Any] = json.loads(result.content[0].text)  # type: ignore[union-attr]
    assert payload.get("ok") is True, payload
    assert payload["path"] == "D1"
    assert payload["parent_vacant_id_hex"] == alice_vid.hex()
    child_name = payload["child_name"]
    child_id_hex = payload["child_vacant_id_hex"]
    assert child_name.startswith("alice__cite__")

    # 1. child directory exists with the three canonical files
    child_dir = isolated_home / child_name
    assert child_dir.is_dir(), child_dir
    assert (child_dir / "key.json").exists()
    assert (child_dir / "logbook.jsonl").exists()
    assert (child_dir / "meta.json").exists()

    # 2. child meta carries parent_id_hex chained back to alice
    child_meta = ls.load_meta(child_name)
    assert child_meta.parent_id_hex == alice_vid.hex()
    assert child_meta.vacant_id_hex == child_id_hex

    # 3. child logbook opens with a signed BIRTH entry
    child_lb = ls.load_logbook(child_name)
    kinds = [e.kind for e in child_lb.entries]
    assert kinds[0] == "BIRTH", kinds
    birth = child_lb.entries[0].payload
    assert birth["parent_id"] == alice_vid.hex()
    assert birth["path"] == "D1"
    assert birth["policy_mutation"] == "always cite the source paragraph"

    # 4. alice's logbook gained a signed SPAWN entry naming the child
    alice_lb = ls.load_logbook("alice")
    alice_kinds = [e.kind for e in alice_lb.entries]
    assert "SPAWN" in alice_kinds, alice_kinds
    spawn_entry = next(e for e in alice_lb.entries if e.kind == "SPAWN")
    assert spawn_entry.payload["child_id"] == child_id_hex
    assert spawn_entry.payload["path"] == "D1"

    # 5. both chains re-verify under their respective keys
    assert alice_lb.verify_chain(alice_vid.verify_key())
    child_vid = VacantId(pubkey_bytes=bytes.fromhex(child_id_hex))
    assert child_lb.verify_chain(child_vid.verify_key())


@pytest.mark.asyncio
async def test_vacant_spawn_refuses_empty_mutation(isolated_home: Path) -> None:
    """D1 requires a non-empty mutation. The tool must surface that as an
    ``error`` field, not a Python traceback."""
    ls.init_vacant("alice", insecure_demo=True)
    params = _stdio_params("alice", isolated_home)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "vacant_spawn",
                arguments={"policy_mutation": "   "},
            )
    payload: dict[str, Any] = json.loads(result.content[0].text)  # type: ignore[union-attr]
    assert "error" in payload, payload
    assert "spawn_failed" in payload["error"]
