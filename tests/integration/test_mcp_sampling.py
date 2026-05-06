"""D2 acceptance: MCP `sampling/createMessage` reverse callback. (D2)

This is the test that demonstrates "嫁接到客戶端" literally:

1. The MCP **client** (this test) supplies a `sampling_callback` — its
   own LLM session, abstractly — when opening the session.
2. The MCP **server** (the vacant) runs `vacant_call_with_sampling`.
   Inside the tool, the server uses `Context.session.create_message`
   to ask the *client* to do an inference. No `ANTHROPIC_API_KEY` is
   set on the server side; the client is the brain.
3. The client's `sampling_callback` is called with the request, returns
   the inference. The server wraps the result through
   `ClientInheritedSubstrate` so the borrow is auditable as
   `client-inherited:<caller>:<model_hint>`.

This is the substrate path that closes the thesis claim a vacant can
deploy with **no API key of its own** — the calling client supplies the
LLM through the standard MCP sampling protocol.
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
from mcp.shared.context import RequestContext
from mcp.types import (
    CreateMessageRequestParams,
    CreateMessageResult,
    SamplingCapability,
    TextContent,
)

from vacant.cli import local_store as ls

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
async def test_vacant_borrows_caller_llm_via_sampling(isolated_home: Path) -> None:
    ls.init_vacant("alice", insecure_demo=True)  # subprocess can't share fake keyring

    sampling_calls: list[Any] = []

    async def sampling_cb(
        ctx: RequestContext[ClientSession, Any],
        params: CreateMessageRequestParams,
    ) -> CreateMessageResult:
        sampling_calls.append(params)
        # The "client's LLM" — for the test, just acknowledge the prompt.
        user_text = ""
        for msg in params.messages:
            if isinstance(msg.content, TextContent):
                user_text = msg.content.text
                break
        return CreateMessageResult(
            role="assistant",
            content=TextContent(type="text", text=f"client-LLM-says: {user_text}"),
            model="claude-test-mock",
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
            res = await session.call_tool(
                "vacant_call_with_sampling",
                arguments={
                    "user_prompt": "what is 2+2?",
                    "system_prompt": "be terse",
                    "model_hint": "claude-test-mock",
                    "caller_vacant_id_hex": "ab" * 32,
                },
            )

    # Tool returned the borrowed text plus the substrate audit trail.
    text = res.content[0].text  # type: ignore[union-attr]
    obj: dict[str, Any] = json.loads(text)
    assert obj["text"] == "client-LLM-says: what is 2+2?"
    # Substrate identity records the borrow.
    assert obj["substrate"] == f"client-inherited:{'ab' * 32}:claude-test-mock"
    assert obj["proof"]["substrate_kind"] == "client-inherited"
    assert obj["proof"]["borrowed_from"] == "ab" * 32
    assert obj["proof"]["model_hint"] == "claude-test-mock"
    # The vacant identity is recorded too.
    meta = ls.load_meta("alice")
    assert obj["vacant_id"] == meta.vacant_id_hex

    # The MCP server actually called sampling/createMessage on the client.
    assert len(sampling_calls) == 1
    p = sampling_calls[0]
    assert p.systemPrompt == "be terse"
    assert p.maxTokens == 256
