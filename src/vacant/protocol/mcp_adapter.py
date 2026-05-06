"""MCP bridge adapters (P6 §3.4 / D009 §G).

Two adapters:

- `VacantAsMCPServer`: wraps a serving vacant + behaviour callback so
  existing MCP-aware clients (Claude Code, OpenClaw plugin, etc.) can
  call it via the standard `tools/list`, `tools/call` shape. The
  internal flow is identical to `serve.py`'s `/a2a/message/send` —
  same envelope verification, same replay protection.
- `MCPClientSubstrate`: lets a vacant call out to an MCP server as
  part of its behaviour. Implements the P0 `SubstrateBackend` contract.

The full MCP wire protocol is *not* re-implemented here (would require
pulling in the MCP SDK). Both adapters take a small `transport`
callable that the caller wires to a real MCP runtime when needed; for
unit tests we pass an in-process function. P7 demo will swap in the
real transport.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from vacant.core.crypto import SigningKey
from vacant.core.types import ResidentForm
from vacant.protocol.envelope import (
    A2AMessage,
    A2APart,
    VacantEnvelope,
    from_a2a_jsonrpc,
    to_a2a_jsonrpc,
)
from vacant.protocol.replay_protect import ReplayStore
from vacant.protocol.serve import BehaviorHandler, make_response_envelope
from vacant.runtime.state_machine import can_be_called
from vacant.substrate.base import SubstrateBackend, SubstrateRequest, SubstrateResponse

__all__ = [
    "MCPClientSubstrate",
    "MCPTransport",
    "VacantAsMCPServer",
]


MCPTransport = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


# --- vacant-as-MCP-server --------------------------------------------------


@dataclass
class VacantAsMCPServer:
    """Expose a vacant's capabilities as MCP tools.

    Tools:

    - `vacant_call`: dispatches into the vacant's behaviour through the
      standard envelope path (signature verify + replay protect).
    - `vacant_describe`: returns the vacant's capability text + halo
      version (reads from the vacant's signed capability card).

    The MCP transport (real wire protocol) is wired by the caller. This
    adapter is the bridge — what runs *inside* the MCP server when an
    MCP client calls a tool.
    """

    self_form: ResidentForm
    self_signing_key: SigningKey
    behavior: BehaviorHandler
    replay_store: ReplayStore

    def list_tools(self) -> list[dict[str, Any]]:
        """Mirror P6 §3.4 `tools/list`."""
        return [
            {
                "name": "vacant_call",
                "title": "Call this vacant",
                "description": (
                    "Send a task to this vacant via the standard A2A "
                    "envelope path. Builds and verifies the envelope "
                    "internally. Returns the signed response."
                ),
                "inputSchema": {
                    "type": "object",
                    "required": ["envelope"],
                    "properties": {
                        "envelope": {
                            "type": "object",
                            "description": "A signed A2A JSON-RPC body",
                        }
                    },
                },
            },
            {
                "name": "vacant_describe",
                "title": "Describe this vacant",
                "description": "Return capability text + halo metadata.",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Dispatch an MCP `tools/call`."""
        if name == "vacant_describe":
            card = self.self_form.capability_card
            return {
                "vacant_id": self.self_form.identity.hex(),
                "capability_text": card.capability_text if card else None,
                "halo_version": card.halo_version if card else None,
                "endpoint": card.endpoint if card else None,
            }
        if name == "vacant_call":
            envelope_body = arguments["envelope"]
            request_env = from_a2a_jsonrpc(envelope_body)

            if request_env.to_vacant_id != self.self_form.identity:
                return {
                    "error": (
                        "envelope_to_mismatch: expected "
                        f"{self.self_form.identity.hex()}, got "
                        f"{request_env.to_vacant_id.hex()}"
                    )
                }
            if not can_be_called(self.self_form.runtime_state):
                return {
                    "error": f"vacant {self.self_form.runtime_state.value}; not accepting calls"
                }
            request_env.verify_or_raise(request_env.from_vacant_id.verify_key())

            await self.replay_store.check_and_advance(request_env)
            response_payload = await self.behavior(request_env)
            response_env = await make_response_envelope(
                request=request_env,
                response_payload=response_payload,
                self_signing_key=self.self_signing_key,
                response_replay_store=self.replay_store,
                self_form=self.self_form,
            )
            wire = to_a2a_jsonrpc(response_env)
            return {"message": wire["params"]["message"]}

        return {"error": f"unknown tool {name!r}"}


# --- MCP-client substrate --------------------------------------------------


@dataclass
class MCPClientSubstrate(SubstrateBackend):
    """A `SubstrateBackend` that calls an MCP server tool as inference.

    `transport(server_url, body) -> dict` is wired by the caller.
    `tool_name` is the MCP tool to invoke; the substrate forwards
    `req.system_prompt` + `req.user_prompt` as a `params.message`-shaped
    JSON-RPC request to the server.
    """

    server_url: str
    tool_name: str
    transport: MCPTransport

    @property
    def name(self) -> str:
        return f"mcp:{self.server_url}:{self.tool_name}"

    async def infer(self, req: SubstrateRequest) -> SubstrateResponse:
        body = {
            "jsonrpc": "2.0",
            "id": "mcp-call",
            "method": "tools/call",
            "params": {
                "name": self.tool_name,
                "arguments": {
                    "system_prompt": req.system_prompt,
                    "user_prompt": req.user_prompt,
                    "tools": list(req.tools),
                    "metadata": dict(req.metadata),
                },
            },
        }
        result = await self.transport(self.server_url, body)
        text = ""
        # Best-effort: MCP `tools/call` results commonly carry text in
        # `result.content` or a custom shape. Tests pass a transport
        # that returns `{"text": ...}` directly.
        if "text" in result:
            text = str(result["text"])
        elif "result" in result and isinstance(result["result"], dict):
            text = str(result["result"].get("text", ""))
        return SubstrateResponse(
            text=text,
            model_id=self.tool_name,
            usage={},
            proof={"server_url": self.server_url},
        )


# Re-export for downstream sites that prefer `from .mcp_adapter import A2APart`.
_ = (A2APart, A2AMessage, VacantEnvelope)
