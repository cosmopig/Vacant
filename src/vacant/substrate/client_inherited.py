"""`ClientInheritedSubstrate` — borrow the calling client's LLM. (D2)

This is the substrate that closes the "嫁接到客戶端" thesis claim. The
vacant carries no API key and runs no local model. Instead, when an
MCP-aware client calls the vacant, the client *lends* its own LLM
session for the duration of the call: the vacant asks the client (via
MCP `sampling/createMessage`) to do an inference on its behalf and
treats the result as the substrate's response.

Architecture:

- `SubstrateHandle` — the small dataclass that travels in the envelope
  metadata. It names the substrate kind (e.g. "client-inherited"),
  the model hint the client offers, and an opaque transport callback id.
- `SamplingCallback` — `async (system_prompt, user_prompt) -> text`,
  i.e. the function `serve.py` builds at the moment of receiving an
  MCP `tools/call` and hands to this substrate.
- `ClientInheritedSubstrate` — the `SubstrateBackend` proper. Its
  `name` records the borrowed identity so reputation per-substrate
  works (a vacant that always runs under Claude scores its records as
  `client-inherited:<caller>:claude-sonnet-4-6`).

Security model: see ADR D017. The vacant trusts the caller's LLM
output, but signs its own logbook entry. The substrate identity is
recorded as `client-inherited:<caller_vacant_id>:<model_hint>` so a
reviewer can attribute behaviour to the borrowed brain.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from vacant.substrate.base import SubstrateBackend, SubstrateRequest, SubstrateResponse

__all__ = [
    "ClientInheritedSubstrate",
    "SamplingCallback",
    "SubstrateHandle",
]


SamplingCallback = Callable[[str, str], Awaitable[str]]


@dataclass(frozen=True)
class SubstrateHandle:
    """Caller-supplied substrate identifier, carried in envelope metadata.

    The values are advisory — the actual inference happens through the
    `SamplingCallback` the serve layer constructs from the MCP session.
    `transport_callback_id` is opaque to the vacant; it lets the serve
    layer route the sampling request back to the right MCP session.
    """

    substrate_kind: str = "client-inherited"
    model_hint: str = "unknown"
    transport_callback_id: str = ""

    def borrowed_from(self, caller_vacant_id_hex: str) -> str:
        """Reputation key: `client-inherited:<caller>:<model_hint>`.

        Used by the logbook attestation so that "this vacant ran on a
        borrowed Claude session" is auditable post-hoc.
        """
        return f"{self.substrate_kind}:{caller_vacant_id_hex}:{self.model_hint}"


@dataclass
class ClientInheritedSubstrate(SubstrateBackend):
    """Substrate that delegates inference to a caller-supplied callback.

    Constructed by `serve.py` (or `mcp_adapter.py`) at the moment an
    incoming call carries a `SubstrateHandle`. The instance lives only
    for the duration of that one call — the vacant has no LLM state of
    its own.
    """

    callback: SamplingCallback
    handle: SubstrateHandle = field(default_factory=SubstrateHandle)
    caller_vacant_id_hex: str = ""

    @property
    def name(self) -> str:
        return self.handle.borrowed_from(self.caller_vacant_id_hex or "anonymous")

    async def infer(self, req: SubstrateRequest) -> SubstrateResponse:
        text = await self.callback(req.system_prompt, req.user_prompt)
        return SubstrateResponse(
            text=text,
            model_id=self.handle.model_hint,
            usage={},
            proof={
                "substrate_kind": self.handle.substrate_kind,
                "borrowed_from": self.caller_vacant_id_hex,
                "model_hint": self.handle.model_hint,
                "transport_callback_id": self.handle.transport_callback_id,
            },
        )

    def to_logbook_entry(self) -> dict[str, Any]:
        """Logbook entry payload describing the borrowed substrate.

        Use this when appending a `SUBSTRATE_BORROWED` log entry so the
        chain records "this inference was outsourced to the caller's
        LLM at `<model_hint>` for `<caller>`".
        """
        return {
            "substrate_kind": self.handle.substrate_kind,
            "model_hint": self.handle.model_hint,
            "borrowed_from": self.caller_vacant_id_hex,
            "transport_callback_id": self.handle.transport_callback_id,
        }
