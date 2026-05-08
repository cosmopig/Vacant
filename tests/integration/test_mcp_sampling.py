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

Pfix3 B7: the tool now requires a *signed A2A envelope* from the
caller (same shape as `vacant_call`), and every borrow appends a
paired ``SUBSTRATE_BORROWED`` + ``INFERENCE_EVENT`` to the vacant's
local logbook. The response is returned as a *signed* response
envelope. The README's "the vacant signs the resulting logbook
entry" claim now holds: the audit trail is real, attributable to a
verified caller, and tamper-evident.
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
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
from vacant.core.crypto import keygen
from vacant.core.types import EMPTY_PREV_HASH, VacantId
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
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "vacant.cli.mcp_serve_test_runner", name],
        env={**os.environ, "VACANT_HOME": str(home)},
    )


@pytest.mark.asyncio
async def test_vacant_borrows_caller_llm_via_sampling(isolated_home: Path) -> None:
    # Local vacant 'alice' is the served vacant. The caller (this test)
    # plays the role of a separate vacant 'bob' that signs an A2A
    # envelope addressed to alice.
    ls.init_vacant("alice", insecure_demo=True)  # subprocess can't share fake keyring
    alice_meta = ls.load_meta("alice")
    alice_vid = VacantId(pubkey_bytes=bytes.fromhex(alice_meta.vacant_id_hex))

    bob_sk, bob_vk = keygen()
    bob_vid = VacantId.from_verify_key(bob_vk)

    # Build the signed envelope bob → alice with the user prompt.
    request_env = VacantEnvelope(
        from_vacant_id=bob_vid,
        to_vacant_id=alice_vid,
        sequence_no=1,
        timestamp=datetime.now(UTC),
        prev_envelope_hash=EMPTY_PREV_HASH,
        payload=A2AMessage(
            role="ROLE_USER",
            parts=[A2APart(text="what is 2+2?")],
        ),
        idempotency_key="sampling-test-1",
    ).signed(bob_sk)
    envelope_body = to_a2a_jsonrpc(request_env)

    sampling_calls: list[CreateMessageRequestParams] = []

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
                    "envelope": envelope_body,
                    "model_hint": "claude-test-mock",
                },
            )

    # 1. Tool returned a JSON dict. mcp wraps it as TextContent with the
    #    JSON serialization in `.text`.
    text = res.content[0].text  # type: ignore[union-attr]
    import json

    obj: dict[str, Any] = json.loads(text)
    assert "message" in obj, f"expected signed response envelope, got {obj}"
    assert obj["substrate"] == f"client-inherited:{bob_vid.hex()}:claude-test-mock"
    assert obj["proof"]["substrate_kind"] == "client-inherited"
    assert obj["proof"]["borrowed_from"] == bob_vid.hex()
    assert obj["proof"]["model_hint"] == "claude-test-mock"

    # 2. The "message" is a signed A2A response envelope addressed back
    #    to bob, signed by alice. Re-parse it through the wire format
    #    and verify the signature under alice's verify key.
    response_wire = {
        "jsonrpc": "2.0",
        "id": "rsp",
        "method": "message/send",
        "params": {"message": obj["message"]},
    }
    response_env = from_a2a_jsonrpc(response_wire)
    assert response_env.from_vacant_id == alice_vid
    assert response_env.to_vacant_id == bob_vid
    response_env.verify_or_raise(alice_vid.verify_key())
    assert response_env.payload.parts[0].text == "client-LLM-says: what is 2+2?"

    # 3. The client really was asked to do an inference.
    assert len(sampling_calls) == 1
    p = sampling_calls[0]
    assert p.maxTokens == 256

    # 4. Pfix3 B7 audit trail: alice's logbook gained a paired
    #    SUBSTRATE_BORROWED + INFERENCE_EVENT signed by alice's own key,
    #    persisted to disk by the test runner's on_logbook_change
    #    callback. The chain still verifies.
    lb = ls.load_logbook("alice")
    kinds = [e.kind for e in lb.entries]
    assert kinds[-2:] == ["SUBSTRATE_BORROWED", "INFERENCE_EVENT"]
    sb = lb.entries[-2].payload
    inf = lb.entries[-1].payload
    assert sb["caller"] == bob_vid.hex()
    assert sb["substrate"] == f"client-inherited:{bob_vid.hex()}:claude-test-mock"
    assert inf["caller"] == bob_vid.hex()
    assert inf["request_envelope_id_hex"] == request_env.compute_hash().hex()
    assert "prompt_hash_hex" in inf and "response_hash_hex" in inf
    assert lb.verify_chain(alice_vid.verify_key())
