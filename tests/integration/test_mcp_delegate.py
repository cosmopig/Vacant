"""Integration: vacant_list_children + vacant_delegate via stdio MCP.

These two tools close the lineage loop for the thesis claim — "the
client can autonomously look at this vacant's children and delegate a
task to a specialist". The unit suite covers the cheap error paths
(no parent, unknown child, non-descendant) via FastMCP's in-process
`call_tool`. This integration test exercises the happy path through a
real `vacant mcp --name alice` subprocess so the sampling-callback +
multi-logbook persistence story actually runs."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.context import RequestContext
from mcp.types import (
    CreateMessageRequestParams,
    CreateMessageResult,
    SamplingCapability,
    TextContent,
)

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
async def test_list_children_then_delegate(isolated_home: Path) -> None:
    ls.init_vacant("alice", insecure_demo=True)
    alice_meta = ls.load_meta("alice")
    alice_vid = VacantId(pubkey_bytes=bytes.fromhex(alice_meta.vacant_id_hex))

    sampling_calls: list[CreateMessageRequestParams] = []

    async def sampling_cb(
        _ctx: RequestContext[ClientSession, Any],
        params: CreateMessageRequestParams,
    ) -> CreateMessageResult:
        sampling_calls.append(params)
        # Fake "specialist did the work" reply.
        user_text = ""
        for msg in params.messages:
            if isinstance(msg.content, TextContent):
                user_text = msg.content.text
                break
        return CreateMessageResult(
            role="assistant",
            content=TextContent(type="text", text=f"translated[{user_text}]"),
            model="test-fixture-llm",
            stopReason="endTurn",
        )

    params = _stdio_params("alice", isolated_home)
    async with stdio_client(params) as (read, write):
        async with ClientSession(
            read,
            write,
            sampling_callback=sampling_cb,
            sampling_capabilities=SamplingCapability(),
        ) as session:
            await session.initialize()

            # 1. Spawn a child so list_children has something to show.
            spawn = await session.call_tool(
                "vacant_spawn",
                arguments={
                    "policy_mutation": "always preserve cited identifiers verbatim",
                    "child_name_hint": "translator",
                },
            )
            spawn_body = json.loads(spawn.content[0].text)  # type: ignore[union-attr]
            assert spawn_body["ok"] is True
            child_name = spawn_body["child_name"]
            child_vid_hex = spawn_body["child_vacant_id_hex"]

            # 2. list_children must surface the spawn with policy_mutation
            #    extracted from BIRTH log entry.
            ls_res = await session.call_tool("vacant_list_children", arguments={})
            ls_body = json.loads(ls_res.content[0].text)  # type: ignore[union-attr]
            assert ls_body["parent_vacant_id_hex"] == alice_vid.hex()
            assert len(ls_body["children"]) == 1
            entry = ls_body["children"][0]
            assert entry["name"] == child_name
            assert entry["vacant_id_hex"] == child_vid_hex
            assert entry["policy_mutation"] == "always preserve cited identifiers verbatim"
            assert entry["inference_count"] == 0

            # 3. Delegate a task to the named child via vacant_delegate.
            #    The test sampling_cb stands in for the "calling client's"
            #    LLM — the same MCP sampling/createMessage primitive.
            deleg = await session.call_tool(
                "vacant_delegate",
                arguments={
                    "child_name": child_name,
                    "task": "翻譯 Vacant 是責任層",
                    "model_hint": "test-fixture-llm",
                },
            )
            deleg_body = json.loads(deleg.content[0].text)  # type: ignore[union-attr]
            assert deleg_body["ok"] is True
            assert deleg_body["child_name"] == child_name
            assert deleg_body["child_vacant_id_hex"] == child_vid_hex
            assert deleg_body["answer"] == "translated[翻譯 Vacant 是責任層]"
            substrate_label = deleg_body["substrate"]
            assert substrate_label.startswith("client-inherited:")
            assert alice_vid.hex() in substrate_label
            assert "test-fixture-llm" in substrate_label

    # 4. Audit chain checks (out of MCP session).
    # The child's logbook gained SUBSTRATE_BORROWED + INFERENCE_EVENT,
    # signed by the child's own key (chain re-verifies).
    child_vid = VacantId(pubkey_bytes=bytes.fromhex(child_vid_hex))
    child_lb = ls.load_logbook(child_name)
    kinds = [e.kind for e in child_lb.entries]
    assert kinds == ["BIRTH", "SUBSTRATE_BORROWED", "INFERENCE_EVENT"]
    assert child_lb.entries[1].payload["caller"] == alice_vid.hex()
    assert child_lb.entries[1].payload["via"] == "delegate"
    assert child_lb.entries[2].payload["via"] == "delegate"
    assert child_lb.verify_chain(child_vid.verify_key())

    # Alice's logbook gained a DELEGATION_COMPLETED entry (signed by alice).
    alice_lb = ls.load_logbook("alice")
    alice_kinds = [e.kind for e in alice_lb.entries]
    assert "DELEGATION_COMPLETED" in alice_kinds
    deleg_entry = next(e for e in alice_lb.entries if e.kind == "DELEGATION_COMPLETED")
    assert deleg_entry.payload["child_id"] == child_vid_hex
    assert deleg_entry.payload["child_name"] == child_name
    assert deleg_entry.payload["substrate"].startswith("client-inherited:")
    assert alice_lb.verify_chain(alice_vid.verify_key())

    # 5. After the delegate call, list_children should now report
    #    inference_count == 1 (specialist has done one piece of real work).
    params2 = _stdio_params("alice", isolated_home)
    async with stdio_client(params2) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            ls_res2 = await session.call_tool("vacant_list_children", arguments={})
            ls_body2 = json.loads(ls_res2.content[0].text)  # type: ignore[union-attr]
            assert ls_body2["children"][0]["inference_count"] == 1


@pytest.mark.asyncio
async def test_delegate_with_unknown_child_returns_error_envelope(
    isolated_home: Path,
) -> None:
    ls.init_vacant("alice", insecure_demo=True)
    params = _stdio_params("alice", isolated_home)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool(
                "vacant_delegate",
                arguments={"child_name": "alice__ghost__deadbeef", "task": "x"},
            )
    body = json.loads(res.content[0].text)  # type: ignore[union-attr]
    assert "error" in body
    assert "not found on disk" in body["error"]


@pytest.mark.asyncio
async def test_list_children_finds_attestation_count(isolated_home: Path) -> None:
    """An attestations_received.jsonl in the child's dir bumps the count."""
    ls.init_vacant("alice", insecure_demo=True)

    params = _stdio_params("alice", isolated_home)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            spawn = await session.call_tool(
                "vacant_spawn",
                arguments={
                    "policy_mutation": "x",
                    "child_name_hint": "rep",
                },
            )
            child_name = json.loads(spawn.content[0].text)["child_name"]  # type: ignore[union-attr]

    # Drop two attestation rows (any opaque JSON line is enough for the count).
    att_path = isolated_home / child_name / "attestations_received.jsonl"
    att_path.write_text('{"x":1}\n{"x":2}\n', encoding="utf-8")

    params2 = _stdio_params("alice", isolated_home)
    async with stdio_client(params2) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool("vacant_list_children", arguments={})
    body = json.loads(res.content[0].text)  # type: ignore[union-attr]
    assert body["children"][0]["attestation_count"] == 2
