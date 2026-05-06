"""Real MCP server transport for `vacant serve --mcp`. (A3)

Wraps the existing `VacantAsMCPServer` adapter (from
`vacant.protocol.mcp_adapter`) in a `FastMCP` instance from the official
`mcp` Python SDK so external MCP clients (Claude Desktop, the
`@modelcontextprotocol/inspector` CLI, the SDK's own
`ClientSession.stdio_client`) can talk to a vacant over stdio.

Tools exposed (mirrors `VacantAsMCPServer.list_tools`):

- `vacant_describe` — returns capability text + halo metadata
- `vacant_call` — accepts a signed A2A envelope, runs it through the
  same envelope verification + replay protection as the HTTP path

The thesis-defense claim — "嫁接到客戶端" — rests on this module: a
client like Claude Desktop launches `vacant serve --mcp` as a stdio
subprocess and immediately gets the vacant as a callable tool, with the
same signed-envelope guarantees the HTTP path provides.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import SamplingMessage, TextContent

from vacant.core.crypto import SigningKey
from vacant.core.types import ResidentForm
from vacant.protocol import (
    InMemoryReplayStore,
    ReplayStore,
    VacantAsMCPServer,
)
from vacant.protocol.envelope import A2AMessage
from vacant.protocol.serve import BehaviorHandler
from vacant.substrate.base import SubstrateRequest
from vacant.substrate.client_inherited import (
    ClientInheritedSubstrate,
    SubstrateHandle,
)

__all__ = [
    "build_fastmcp_server",
    "run_mcp_stdio_server",
]


def _default_behavior() -> BehaviorHandler:
    """Echo behavior — symmetric with `cli.server.echo_behavior`.

    Defined inline so this module doesn't pull in the FastAPI app
    builder when the user only wants stdio MCP.
    """
    from vacant.protocol.envelope import A2APart, VacantEnvelope

    async def behavior(env: VacantEnvelope) -> A2AMessage:
        text = " ".join(p.text for p in env.payload.parts)
        return A2AMessage(
            role="ROLE_AGENT",
            parts=[A2APart(text=f"echo from {env.to_vacant_id.short()}: {text}")],
        )

    return behavior


def build_fastmcp_server(
    *,
    form: ResidentForm,
    signing_key: SigningKey,
    replay_store: ReplayStore | None = None,
    behavior: BehaviorHandler | None = None,
    name: str | None = None,
) -> FastMCP:
    """Wrap a vacant as a `FastMCP` server.

    The returned object can be `.run()`'d on stdio or mounted as an
    SSE app via `.sse_app()`. Tools are registered using FastMCP's
    decorator API; under the hood every call is routed through
    `VacantAsMCPServer` so the envelope semantics match the HTTP path.
    """
    rs = replay_store if replay_store is not None else InMemoryReplayStore()
    bridge = VacantAsMCPServer(
        self_form=form,
        self_signing_key=signing_key,
        behavior=behavior or _default_behavior(),
        replay_store=rs,
    )

    server_name = name or f"vacant-{form.identity.short()}"
    mcp = FastMCP(name=server_name)

    @mcp.tool(
        name="vacant_describe",
        description="Return this vacant's capability text + halo metadata.",
    )
    async def vacant_describe() -> dict[str, Any]:
        return await bridge.call_tool("vacant_describe", {})

    @mcp.tool(
        name="vacant_call",
        description=(
            "Call this vacant with a signed A2A envelope. The envelope "
            "must be a JSON-RPC 2.0 `message/send` body whose metadata "
            "carries the caller's signature, sequence number, and "
            "previous envelope hash. Returns the signed response message."
        ),
    )
    async def vacant_call(envelope: dict[str, Any]) -> dict[str, Any]:
        return await bridge.call_tool("vacant_call", {"envelope": envelope})

    # D2 — `vacant_call_with_sampling` is the load-bearing demonstration
    # of "嫁接到客戶端": this vacant has no LLM of its own, so it asks the
    # *calling client* (via MCP `sampling/createMessage`) to do the
    # inference. The result is wrapped through `ClientInheritedSubstrate`
    # so the substrate identity is recorded as
    # `client-inherited:<caller>:<model_hint>` for reputation purposes.
    @mcp.tool(
        name="vacant_call_with_sampling",
        description=(
            "Run an inference inside this vacant using the calling "
            "client's LLM via MCP `sampling/createMessage`. The vacant "
            "carries no API key — the client supplies the brain. The "
            "substrate identity recorded in the response metadata is "
            "`client-inherited:<caller>:<model_hint>` so the borrow is "
            "auditable."
        ),
    )
    async def vacant_call_with_sampling(
        ctx: Context,  # type: ignore[type-arg]
        user_prompt: str,
        system_prompt: str = "",
        model_hint: str = "client-default",
        caller_vacant_id_hex: str = "",
        max_tokens: int = 256,
    ) -> dict[str, Any]:
        async def sampling_cb(sys_p: str, user_p: str) -> str:
            messages = [
                SamplingMessage(role="user", content=TextContent(type="text", text=user_p)),
            ]
            result = await ctx.session.create_message(
                messages=messages,
                max_tokens=max_tokens,
                system_prompt=sys_p or None,
            )
            content = result.content
            if isinstance(content, TextContent):
                return content.text
            return str(getattr(content, "text", ""))

        substrate = ClientInheritedSubstrate(
            callback=sampling_cb,
            handle=SubstrateHandle(model_hint=model_hint),
            caller_vacant_id_hex=caller_vacant_id_hex,
        )
        sub_req = SubstrateRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        sub_res = await substrate.infer(sub_req)
        return {
            "text": sub_res.text,
            "substrate": substrate.name,
            "model_id": sub_res.model_id,
            "proof": sub_res.proof,
            "vacant_id": form.identity.hex(),
        }

    return mcp


def run_mcp_stdio_server(
    *,
    form: ResidentForm,
    signing_key: SigningKey,
    replay_store: ReplayStore | None = None,
    behavior: BehaviorHandler | None = None,
) -> None:
    """Blocking entrypoint: run the FastMCP server on stdio.

    Used by `vacant serve --mcp`, where it runs in a worker thread so
    the main thread can keep serving HTTP. Each stdio session is its
    own asyncio event loop.
    """
    server = build_fastmcp_server(
        form=form,
        signing_key=signing_key,
        replay_store=replay_store,
        behavior=behavior,
    )
    asyncio.run(server.run_stdio_async())


# Silence unused-import lint when the module is imported but
# run_mcp_stdio_server is not referenced (tests import build_fastmcp_server only).
_: Callable[..., Awaitable[Any]] | None = None
