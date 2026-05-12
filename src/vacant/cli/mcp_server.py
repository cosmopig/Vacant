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
- `vacant_call_with_sampling` — same signed-envelope path, but the
  inference is delegated to the calling client's LLM via MCP
  ``sampling/createMessage``. Pfix3 B7 fallback: every borrow is now
  signed into the vacant's logbook as a paired
  ``SUBSTRATE_BORROWED`` + ``INFERENCE_EVENT`` and the response is
  returned as a *signed* response envelope (not raw text).

The thesis-defense claim — "嫁接到客戶端" — rests on this module: a
client like Claude Desktop launches `vacant serve --mcp` as a stdio
subprocess and immediately gets the vacant as a callable tool, with the
same signed-envelope guarantees the HTTP path provides.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import SamplingMessage, TextContent

from vacant.core.crypto import SigningKey, hash_blake2b
from vacant.core.types import Logbook, ResidentForm
from vacant.protocol import (
    InMemoryReplayStore,
    ReplayStore,
    VacantAsMCPServer,
)
from vacant.protocol.envelope import (
    A2AMessage,
    A2APart,
    from_a2a_jsonrpc,
    to_a2a_jsonrpc,
)
from vacant.protocol.errors import EnvelopeFormatError
from vacant.protocol.serve import BehaviorHandler, make_response_envelope
from vacant.runtime.spawn import spawn_clone_with_mutation
from vacant.runtime.state_machine import can_be_called
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
    logbook: Logbook | None = None,
    on_logbook_change: Callable[[Logbook], None] | None = None,
    parent_local_name: str | None = None,
    persist_spawned_child: Callable[[Any, str, str], None] | None = None,
) -> FastMCP:
    """Wrap a vacant as a `FastMCP` server.

    The returned object can be `.run()`'d on stdio or mounted as an
    SSE app via `.sse_app()`. Tools are registered using FastMCP's
    decorator API; under the hood every call is routed through
    `VacantAsMCPServer` so the envelope semantics match the HTTP path.

    ``logbook`` (Pfix3 B7): the vacant's signed logbook. The
    sampling tool appends a paired ``SUBSTRATE_BORROWED`` +
    ``INFERENCE_EVENT`` to it for every call. Defaults to
    ``form.logbook`` so persistent vacants get the entries on disk
    automatically (when ``on_logbook_change`` is wired).

    ``on_logbook_change``: callback invoked after every logbook
    append. Production wiring (``vacant mcp``) saves to disk; tests
    pass ``None`` so the entries stay in memory only.
    """
    rs = replay_store if replay_store is not None else InMemoryReplayStore()
    # `form.logbook` is non-Optional on `ResidentForm`; this fallback
    # makes `lb` provably non-None so the sampling tool can append
    # without a defensive guard.
    lb: Logbook = logbook if logbook is not None else form.logbook
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
    #
    # Pfix3 B7 (fallback path): the tool requires a signed A2A envelope
    # — same shape as `vacant_call` — verifies + replay-checks it on
    # the vacant side, appends a paired SUBSTRATE_BORROWED +
    # INFERENCE_EVENT to the local logbook, and returns a *signed*
    # response envelope. README's "the vacant signs the resulting
    # logbook entry" claim now holds: every borrow leaves a signed
    # audit trail attributable to the verified caller, not to a
    # caller-supplied string.
    @mcp.tool(
        name="vacant_call_with_sampling",
        description=(
            "Run an inference inside this vacant using the calling "
            "client's LLM via MCP `sampling/createMessage`. Requires a "
            "signed A2A envelope (same shape as `vacant_call`); the "
            "envelope's payload text becomes the user prompt. Every "
            "borrow appends signed SUBSTRATE_BORROWED + INFERENCE_EVENT "
            "entries to this vacant's logbook. The response is a signed "
            "A2A envelope; `substrate` metadata is recorded as "
            "`client-inherited:<caller>:<model_hint>` for reputation."
        ),
    )
    async def vacant_call_with_sampling(
        ctx: Context,  # type: ignore[type-arg]
        envelope: dict[str, Any],
        model_hint: str = "client-default",
        max_tokens: int = 256,
    ) -> dict[str, Any]:
        # 1. Parse + verify caller's envelope. Same path as vacant_call
        #    — refusing to run sampling without an authenticated caller
        #    is what makes the "responsibility layer" claim honest.
        try:
            request_env = from_a2a_jsonrpc(envelope)
        except EnvelopeFormatError as exc:
            return {"error": f"envelope_parse: {exc}"}
        if request_env.to_vacant_id != form.identity:
            return {
                "error": (
                    "envelope_to_mismatch: expected "
                    f"{form.identity.hex()}, got {request_env.to_vacant_id.hex()}"
                )
            }
        if not can_be_called(form.runtime_state):
            return {"error": f"vacant {form.runtime_state.value}; not accepting calls"}
        try:
            request_env.verify_or_raise(request_env.from_vacant_id.verify_key())
        except Exception as exc:
            return {"error": f"envelope_signature: {exc}"}
        try:
            await rs.check_and_advance(request_env)
        except Exception as exc:
            return {"error": f"envelope_replay: {exc}"}

        # 2. Run sampling via the calling client's LLM. The user prompt
        #    is the verified envelope's payload text — the caller can't
        #    smuggle a different prompt through the side channel.
        user_prompt = " ".join(p.text for p in request_env.payload.parts)

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
            caller_vacant_id_hex=request_env.from_vacant_id.hex(),
        )
        sub_req = SubstrateRequest(system_prompt="", user_prompt=user_prompt)
        sub_res = await substrate.infer(sub_req)

        # 3. Append signed audit entries to the local logbook. A
        #    SUBSTRATE_BORROWED records the borrow itself; an
        #    INFERENCE_EVENT records the input/output hashes so an
        #    auditor can replay verification without keeping the raw
        #    prompt/response.
        now = time.time()
        request_env_id_hex = request_env.compute_hash().hex()
        prompt_hash_hex = hash_blake2b(user_prompt.encode("utf-8")).hex()
        response_hash_hex = hash_blake2b(sub_res.text.encode("utf-8")).hex()
        lb.append(
            "SUBSTRATE_BORROWED",
            {
                "kind": "SUBSTRATE_BORROWED",
                "caller": request_env.from_vacant_id.hex(),
                "substrate": substrate.name,
                "model_hint": model_hint,
                "request_envelope_id_hex": request_env_id_hex,
                "ts": now,
            },
            signing_key,
        )
        lb.append(
            "INFERENCE_EVENT",
            {
                "kind": "INFERENCE_EVENT",
                "caller": request_env.from_vacant_id.hex(),
                "request_envelope_id_hex": request_env_id_hex,
                "prompt_hash_hex": prompt_hash_hex,
                "response_hash_hex": response_hash_hex,
                "substrate": substrate.name,
                "model_id": sub_res.model_id,
                "proof": sub_res.proof,
                "ts": now,
            },
            signing_key,
        )
        if on_logbook_change is not None:
            on_logbook_change(lb)

        # 4. Build a signed response envelope (target → caller chain).
        response_payload = A2AMessage(role="ROLE_AGENT", parts=[A2APart(text=sub_res.text)])
        response_env = await make_response_envelope(
            request=request_env,
            response_payload=response_payload,
            self_signing_key=signing_key,
            response_replay_store=rs,
            self_form=form,
        )
        wire = to_a2a_jsonrpc(response_env)
        return {
            "message": wire["params"]["message"],
            "substrate": substrate.name,
            "model_id": sub_res.model_id,
            "proof": sub_res.proof,
        }

    # vacant_spawn — autonomous lineage growth. The calling client (or
    # an LLM-driven agent on the client side) decides this vacant should
    # produce a specialized subordinate, and asks for one via the D1
    # clone-with-mutation path. The mutation text is appended to the
    # child's policy DSL; everything else (system prompt, tool whitelist,
    # substrate spec) inherits from this vacant. The child gets a fresh
    # keypair (no key derivation; cf. D003) and is persisted to disk
    # alongside the parent under ``~/.vacant/<child_name>/``. The
    # SPAWN entry on this vacant's logbook is signed by the parent;
    # the child's logbook opens with a BIRTH entry signed by the
    # child's own key.
    @mcp.tool(
        name="vacant_spawn",
        description=(
            "Spawn a child vacant as a clone-with-mutation (D1 path). "
            "Call this when the task at hand would benefit from a "
            "specialised subordinate that inherits this vacant's "
            "capabilities and tool whitelist but carries an extra "
            "policy rule. The child is persisted to disk with its own "
            "Ed25519 keypair, a BIRTH log entry signed by the child, "
            "and a SPAWN log entry on this vacant signed by this "
            "vacant. Returns the child's vacant_id_hex, persistent "
            "name, and parent_id_hex so the caller can verify the "
            "lineage chain. Requires ``parent_local_name`` to have "
            "been set on the server (i.e. this vacant must be a "
            "persistent identity, not an ephemeral one)."
        ),
    )
    async def vacant_spawn(
        policy_mutation: str,
        child_name_hint: str = "",
    ) -> dict[str, Any]:
        if parent_local_name is None or persist_spawned_child is None:
            return {
                "error": (
                    "vacant_spawn requires a persistent parent identity; "
                    "this MCP server was launched without parent_local_name "
                    "wired through (ephemeral mode). Re-launch with "
                    "--name <persistent_name>."
                )
            }
        try:
            result = spawn_clone_with_mutation(form, signing_key, policy_mutation=policy_mutation)
        except Exception as exc:
            return {"error": f"spawn_failed: {exc}"}

        # Persist child + propagate the new SPAWN entry on parent's
        # logbook to disk (sampling tool wires the same callback).
        child_short = result.child.identity.short()
        if child_name_hint and all(c.isalnum() or c in "-_" for c in child_name_hint):
            child_name = f"{parent_local_name}__{child_name_hint}__{child_short}"
        else:
            child_name = f"{parent_local_name}__d1__{child_short}"
        try:
            persist_spawned_child(result, child_name, parent_local_name)
        except Exception as exc:
            return {"error": f"persist_failed: {exc}"}
        # spawn_clone_with_mutation appended SPAWN to form.logbook.
        # When commands.py defaults logbook=None, lb is form.logbook
        # (single-object invariant), so the SPAWN is already on lb.
        # Persist via the same callback the sampling tool uses.
        if on_logbook_change is not None:
            on_logbook_change(form.logbook)

        return {
            "ok": True,
            "path": "D1",
            "child_vacant_id_hex": result.child.identity.hex(),
            "child_name": child_name,
            "parent_vacant_id_hex": form.identity.hex(),
            "policy_mutation": policy_mutation,
        }

    return mcp


def run_mcp_stdio_server(
    *,
    form: ResidentForm,
    signing_key: SigningKey,
    replay_store: ReplayStore | None = None,
    behavior: BehaviorHandler | None = None,
    logbook: Logbook | None = None,
    on_logbook_change: Callable[[Logbook], None] | None = None,
    parent_local_name: str | None = None,
    persist_spawned_child: Callable[[Any, str, str], None] | None = None,
) -> None:
    """Blocking entrypoint: run the FastMCP server on stdio.

    Used by `vacant serve --mcp`, where it runs in a worker thread so
    the main thread can keep serving HTTP. Each stdio session is its
    own asyncio event loop.

    ``logbook`` + ``on_logbook_change`` propagate to the sampling tool
    so every borrow is signed into the vacant's logbook (Pfix3 B7).
    """
    # pragma: no cover -- blocking subprocess wrapper; exercised only by
    # the MCP integration tests which spawn this in a subprocess via
    # `python -m vacant.cli.mcp_serve_test_runner` so coverage doesn't
    # propagate back into the test process.
    server = build_fastmcp_server(  # pragma: no cover
        form=form,
        signing_key=signing_key,
        replay_store=replay_store,
        behavior=behavior,
        logbook=logbook,
        on_logbook_change=on_logbook_change,
        parent_local_name=parent_local_name,
        persist_spawned_child=persist_spawned_child,
    )
    asyncio.run(server.run_stdio_async())  # pragma: no cover


# Silence unused-import lint when the module is imported but
# run_mcp_stdio_server is not referenced (tests import build_fastmcp_server only).
_: Callable[..., Awaitable[Any]] | None = None
