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
import json
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import SamplingMessage, TextContent

from vacant.cli import local_store as ls
from vacant.core.crypto import SigningKey, hash_blake2b
from vacant.core.types import EMPTY_PREV_HASH, Logbook, ResidentForm, VacantId
from vacant.protocol import (
    InMemoryReplayStore,
    ReplayStore,
    VacantAsMCPServer,
)
from vacant.protocol.envelope import (
    A2AMessage,
    A2APart,
    VacantEnvelope,
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
    from vacant.protocol.envelope import A2APart

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

    # vacant_list_children — let the LLM see which D1 children this
    # vacant has previously spawned, plus enough reputation signal to
    # pick one. We surface: policy_mutation (from the child's BIRTH
    # entry), inference_count (how much real work this child has done),
    # attestation_count (peer endorsements on file), last_heartbeat_at
    # (freshness). The LLM uses this catalogue to decide whether to
    # delegate the next task to an existing specialist instead of
    # spawning yet another child or doing the work itself.
    @mcp.tool(
        name="vacant_list_children",
        description=(
            "List the D1 children this vacant has spawned (i.e. local "
            "vacants whose parent_id is this vacant's vacant_id). "
            "Returns one entry per child with: name, vacant_id_hex, "
            "state, capability_text, policy_mutation (the rule the "
            "child was specialised with), inference_count (real "
            "borrows it has served), attestation_count (signed peer "
            "endorsements), last_heartbeat_at. Use this to decide "
            "whether to delegate a task to an existing specialist via "
            "vacant_delegate, or spawn a fresh one."
        ),
    )
    async def vacant_list_children() -> dict[str, Any]:
        home = ls.vacant_home()
        parent_hex = form.identity.hex()
        children: list[dict[str, Any]] = []
        if not home.exists():  # pragma: no cover -- defensive
            return {"parent_vacant_id_hex": parent_hex, "children": children}
        for entry in sorted(home.iterdir()):
            if not entry.is_dir() or not (entry / "meta.json").exists():
                continue
            try:
                child_meta = ls.load_meta(entry.name)
            except (ls.LocalVacantError, OSError, ValueError):  # pragma: no cover
                # Skip directories that aren't a properly-initialised vacant.
                continue
            if child_meta.parent_id_hex != parent_hex:
                continue
            policy_mutation: str | None = None
            inference_count = 0
            try:
                child_lb = ls.load_logbook(entry.name)
            except (ls.LocalVacantError, OSError):  # pragma: no cover
                child_lb = None
            if child_lb is not None:
                for e in child_lb.entries:
                    if e.kind == "BIRTH" and policy_mutation is None:
                        policy_mutation = e.payload.get("policy_mutation")
                    elif e.kind == "INFERENCE_EVENT":  # pragma: no cover
                        inference_count += 1
            attestation_count = 0
            att_path = entry / "attestations_received.jsonl"
            if att_path.exists():
                try:
                    attestation_count = sum(1 for _ in att_path.open(encoding="utf-8"))
                except OSError:  # pragma: no cover
                    pass
            # P8.4: 5D reputation aggregated from reviews_received.jsonl.
            # Beta posterior per dimension, source-weighted 1.0 (caller
            # review). Pure read-side computation — no decay since we
            # don't know the reviewer's intended timestamp granularity
            # at display time. Fuller decay + UCB + cold-start
            # gating lands when the local Registry persists into a
            # dedicated table (P8.3).
            reputation_5d: dict[str, dict[str, float]] = {}
            review_count = 0
            reviews_path = entry / "reviews_received.jsonl"
            if reviews_path.exists():
                from vacant.core.constants import (
                    REPUTATION_DIMS as _DIMS,
                )
                from vacant.reputation.posterior import (
                    five_d_with_priors as _five_d_with_priors,
                )

                beta5d = _five_d_with_priors(now_ts=time.time())
                try:
                    with reviews_path.open(encoding="utf-8") as rf:
                        for line in rf:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                row = json.loads(line)
                                dims_in = row.get("dimensions", {})
                            except json.JSONDecodeError:  # pragma: no cover
                                continue
                            for dim in _DIMS:
                                v = dims_in.get(dim)
                                if not isinstance(v, int | float):
                                    continue
                                if v < 0.0 or v > 1.0:
                                    continue
                                beta_dim = beta5d.get(dim)
                                beta5d = beta5d.with_dim(
                                    dim,
                                    beta_dim.update_with_signal(
                                        signal=float(v),
                                        weight=1.0,
                                        now_ts=time.time(),
                                    ),
                                )
                            review_count += 1
                except OSError:  # pragma: no cover
                    pass
                if review_count > 0:
                    for dim in _DIMS:
                        b = beta5d.get(dim)
                        reputation_5d[dim] = {
                            "mean": b.mean,
                            "variance": b.variance,
                            "n_eff": b.n_eff,
                        }
            children.append(
                {
                    "name": entry.name,
                    "vacant_id_hex": child_meta.vacant_id_hex,
                    "state": child_meta.state,
                    "capability_text": child_meta.capability_text,
                    "policy_mutation": policy_mutation,
                    "inference_count": inference_count,
                    "attestation_count": attestation_count,
                    "review_count": review_count,
                    "reputation_5d": reputation_5d,
                    "last_heartbeat_at": child_meta.last_heartbeat_at,
                }
            )
        return {"parent_vacant_id_hex": parent_hex, "children": children}

    # vacant_delegate — closes the lineage loop the thesis claim relies
    # on. The LLM picks a child from vacant_list_children, hands it a
    # task, and this vacant routes the task through a real signed-
    # envelope path: parent (this vacant) → child. The child borrows
    # the calling client's LLM (same sampling/createMessage primitive
    # vacant_call_with_sampling uses) so its inference is attributed
    # to it under client-inherited substrate. Both vacants' logbooks
    # gain signed entries: child gets SUBSTRATE_BORROWED + INFERENCE_
    # EVENT, parent gets DELEGATION_COMPLETED. The whole chain stays
    # tamper-evident.
    @mcp.tool(
        name="vacant_delegate",
        description=(
            "Delegate a task to one of this vacant's D1 children. The "
            "child must already exist on disk (see vacant_list_children). "
            "This vacant signs an A2A envelope addressed to the child "
            "containing the task; the child borrows the calling client's "
            "LLM via MCP sampling/createMessage to produce its answer "
            "and signs paired SUBSTRATE_BORROWED + INFERENCE_EVENT "
            "entries to its own logbook. This vacant signs a "
            "DELEGATION_COMPLETED entry to its own logbook for audit. "
            "Returns the child's answer text plus identifiers so the "
            "caller can verify the chain."
        ),
    )
    async def vacant_delegate(
        ctx: Context,  # type: ignore[type-arg]
        child_name: str,
        task: str,
        model_hint: str = "client-default",
        max_tokens: int = 512,
    ) -> dict[str, Any]:
        if parent_local_name is None:
            return {
                "error": (
                    "vacant_delegate requires a persistent parent identity; "
                    "this MCP server was launched in ephemeral mode."
                )
            }
        if not child_name or not all(c.isalnum() or c in "-_" for c in child_name):
            return {"error": f"invalid child_name {child_name!r}"}
        try:
            child_meta = ls.load_meta(child_name)
            child_sk = ls.load_signing_key(child_name)
            child_lb = ls.load_logbook(child_name)
        except ls.LocalVacantNotFound:
            return {"error": f"child {child_name!r} not found on disk"}
        except ls.LocalVacantError as exc:
            return {"error": f"could not load child {child_name!r}: {exc}"}

        from datetime import UTC as _UTC
        from datetime import datetime as _datetime

        child_vid = VacantId(pubkey_bytes=bytes.fromhex(child_meta.vacant_id_hex))
        if child_meta.parent_id_hex != form.identity.hex():
            return {
                "error": (
                    f"child {child_name!r} is not a direct descendant of this vacant "
                    f"(parent_id mismatch)"
                )
            }

        # pragma: no cover -- inference path requires a live MCP sampling
        # callback (ctx.session.create_message). Covered end-to-end by
        # tests/integration/test_mcp_delegate.py against a real subprocess.
        request_env = VacantEnvelope(  # pragma: no cover
            from_vacant_id=form.identity,
            to_vacant_id=child_vid,
            sequence_no=1,
            timestamp=_datetime.now(_UTC),
            prev_envelope_hash=EMPTY_PREV_HASH,
            payload=A2AMessage(role="ROLE_USER", parts=[A2APart(text=task)]),
            idempotency_key=f"delegate-{int(time.time() * 1000)}",
        ).signed(signing_key)
        request_env_id_hex = request_env.compute_hash().hex()

        async def sampling_cb(sys_p: str, user_p: str) -> str:  # pragma: no cover
            messages = [  # pragma: no cover
                SamplingMessage(role="user", content=TextContent(type="text", text=user_p)),
            ]
            result = await ctx.session.create_message(  # pragma: no cover
                messages=messages,
                max_tokens=max_tokens,
                system_prompt=sys_p or None,
            )
            content = result.content  # pragma: no cover
            if isinstance(content, TextContent):  # pragma: no cover
                return content.text  # pragma: no cover
            return str(getattr(content, "text", ""))  # pragma: no cover

        substrate = ClientInheritedSubstrate(  # pragma: no cover
            callback=sampling_cb,
            handle=SubstrateHandle(model_hint=model_hint),
            caller_vacant_id_hex=form.identity.hex(),
        )
        try:  # pragma: no cover
            sub_res = await substrate.infer(SubstrateRequest(system_prompt="", user_prompt=task))
        except Exception as exc:  # pragma: no cover
            return {"error": f"delegate_inference_failed: {exc}"}

        now = time.time()  # pragma: no cover
        prompt_hash_hex = hash_blake2b(task.encode("utf-8")).hex()  # pragma: no cover
        response_hash_hex = hash_blake2b(sub_res.text.encode("utf-8")).hex()  # pragma: no cover
        child_lb.append(  # pragma: no cover
            "SUBSTRATE_BORROWED",
            {
                "kind": "SUBSTRATE_BORROWED",
                "caller": form.identity.hex(),
                "substrate": substrate.name,
                "model_hint": model_hint,
                "request_envelope_id_hex": request_env_id_hex,
                "via": "delegate",
                "ts": now,
            },
            child_sk,
        )
        child_lb.append(  # pragma: no cover
            "INFERENCE_EVENT",
            {
                "kind": "INFERENCE_EVENT",
                "caller": form.identity.hex(),
                "request_envelope_id_hex": request_env_id_hex,
                "prompt_hash_hex": prompt_hash_hex,
                "response_hash_hex": response_hash_hex,
                "substrate": substrate.name,
                "model_id": sub_res.model_id,
                "proof": sub_res.proof,
                "via": "delegate",
                "ts": now,
            },
            child_sk,
        )
        ls.save_logbook(child_name, child_lb)  # pragma: no cover

        response_env = VacantEnvelope(  # pragma: no cover
            from_vacant_id=child_vid,
            to_vacant_id=form.identity,
            sequence_no=1,
            timestamp=_datetime.now(_UTC),
            prev_envelope_hash=EMPTY_PREV_HASH,
            payload=A2AMessage(role="ROLE_AGENT", parts=[A2APart(text=sub_res.text)]),
            idempotency_key=f"delegate-resp-{int(time.time() * 1000)}",
        ).signed(child_sk)
        response_env_id_hex = response_env.compute_hash().hex()  # pragma: no cover

        form.logbook.append(  # pragma: no cover
            "DELEGATION_COMPLETED",
            {
                "kind": "DELEGATION_COMPLETED",
                "child_id": child_vid.hex(),
                "child_name": child_name,
                "request_envelope_id_hex": request_env_id_hex,
                "response_envelope_id_hex": response_env_id_hex,
                "model_hint": model_hint,
                "substrate": substrate.name,
                "prompt_hash_hex": prompt_hash_hex,
                "response_hash_hex": response_hash_hex,
                "ts": now,
            },
            signing_key,
        )
        if on_logbook_change is not None:  # pragma: no cover
            on_logbook_change(form.logbook)  # pragma: no cover

        return {  # pragma: no cover
            "ok": True,
            "child_name": child_name,
            "child_vacant_id_hex": child_vid.hex(),
            "answer": sub_res.text,
            "model_hint": model_hint,
            "substrate": substrate.name,
            "request_envelope_id_hex": request_env_id_hex,
            "response_envelope_id_hex": response_env_id_hex,
        }

    # vacant_delegate_a2a — Pfix8 P8.1: vacant-to-vacant communication
    # over A2A HTTP, not MCP. The child must already be running its own
    # ``vacant serve --name <child>`` daemon; its endpoint URL is read
    # from the child's meta.json (advertised on serve start). Alice
    # signs an envelope alice→child and POSTs to the child's
    # ``/a2a/message/send``. The child runs in its OWN process — its
    # signature, its replay store, its logbook. Alice records the
    # envelope chain (request_env_id + response_env_id) in a signed
    # A2A_DELEGATION_COMPLETED logbook entry. The signed response is
    # re-verified under the child's verify key before being surfaced
    # to the caller. This is the "vacant 之間透過 A2A" path the thesis
    # requires.
    @mcp.tool(
        name="vacant_delegate_a2a",
        description=(
            "Delegate a task to a child vacant over A2A HTTP (vacant-to-"
            "vacant, NOT MCP). The child must already be running its "
            "own `vacant serve --name <child>` daemon — its endpoint "
            "URL is read from the child's meta.json. This vacant signs "
            "an A2A envelope addressed to the child and POSTs it; the "
            "child runs in its own process with its own signing key "
            "and produces a signed response envelope. This vacant "
            "records the chain (request_envelope_id + response_envelope_id) "
            "in a signed A2A_DELEGATION_COMPLETED entry on its own "
            "logbook. The child's response signature is re-verified "
            "under the child's verify key before the answer surfaces."
        ),
    )
    async def vacant_delegate_a2a(
        child_name: str,
        task: str,
        timeout_s: float = 60.0,
    ) -> dict[str, Any]:
        if parent_local_name is None:
            return {
                "error": (
                    "vacant_delegate_a2a requires a persistent parent identity; "
                    "this MCP server was launched in ephemeral mode."
                )
            }
        if not child_name or not all(c.isalnum() or c in "-_" for c in child_name):
            return {"error": f"invalid child_name {child_name!r}"}
        try:
            child_meta = ls.load_meta(child_name)
            child_lb_before = ls.load_logbook(child_name)
        except ls.LocalVacantNotFound:
            return {"error": f"child {child_name!r} not found on disk"}
        except ls.LocalVacantError as exc:
            return {"error": f"could not load child {child_name!r}: {exc}"}

        if child_meta.parent_id_hex != form.identity.hex():
            return {
                "error": (
                    f"child {child_name!r} is not a direct descendant of this vacant "
                    f"(parent_id mismatch)"
                )
            }
        if not child_meta.endpoint:
            return {
                "error": (
                    f"child {child_name!r} has no advertised endpoint — start it with "
                    f"`vacant serve --name {child_name}` (it writes meta.endpoint on boot)"
                )
            }

        _ = child_lb_before  # for symmetry; consumed by integration tests, not here
        from datetime import UTC as _UTC  # pragma: no cover
        from datetime import datetime as _datetime  # pragma: no cover

        child_vid = VacantId(
            pubkey_bytes=bytes.fromhex(child_meta.vacant_id_hex)
        )  # pragma: no cover

        request_env = VacantEnvelope(  # pragma: no cover
            from_vacant_id=form.identity,
            to_vacant_id=child_vid,
            sequence_no=1,
            timestamp=_datetime.now(_UTC),
            prev_envelope_hash=EMPTY_PREV_HASH,
            payload=A2AMessage(role="ROLE_USER", parts=[A2APart(text=task)]),
            idempotency_key=f"a2a-delegate-{int(time.time() * 1000)}",
        ).signed(signing_key)
        wire = to_a2a_jsonrpc(request_env)  # pragma: no cover
        request_env_id_hex = request_env.compute_hash().hex()  # pragma: no cover

        url = f"{child_meta.endpoint.rstrip('/')}/a2a/message/send"  # pragma: no cover
        try:  # pragma: no cover
            import httpx as _httpx

            async with _httpx.AsyncClient(timeout=timeout_s) as http:
                r = await http.post(url, json=wire)
        except Exception as exc:  # pragma: no cover
            return {"error": f"a2a_http_failed: {exc}"}
        if r.status_code != 200:  # pragma: no cover
            return {
                "error": (f"a2a_http_status: child returned {r.status_code} ({r.text[:200]!r})")
            }

        body = r.json()  # pragma: no cover
        if "result" not in body or "message" not in body.get("result", {}):  # pragma: no cover
            return {"error": f"a2a_malformed_response: {body!r}"}
        try:  # pragma: no cover
            response_env = from_a2a_jsonrpc(
                {
                    "jsonrpc": "2.0",
                    "id": body.get("id", "rsp"),
                    "method": "message/send",
                    "params": {"message": body["result"]["message"]},
                }
            )
            response_env.verify_or_raise(child_vid.verify_key())
        except Exception as exc:  # pragma: no cover
            return {"error": f"a2a_response_signature: {exc}"}

        response_text = " ".join(p.text for p in response_env.payload.parts)  # pragma: no cover
        response_env_id_hex = response_env.compute_hash().hex()  # pragma: no cover
        prompt_hash_hex = hash_blake2b(task.encode("utf-8")).hex()  # pragma: no cover
        response_hash_hex = hash_blake2b(response_text.encode("utf-8")).hex()  # pragma: no cover

        form.logbook.append(  # pragma: no cover
            "A2A_DELEGATION_COMPLETED",
            {
                "kind": "A2A_DELEGATION_COMPLETED",
                "child_id": child_vid.hex(),
                "child_name": child_name,
                "child_endpoint": child_meta.endpoint,
                "request_envelope_id_hex": request_env_id_hex,
                "response_envelope_id_hex": response_env_id_hex,
                "prompt_hash_hex": prompt_hash_hex,
                "response_hash_hex": response_hash_hex,
                "transport": "a2a-http",
                "ts": time.time(),
            },
            signing_key,
        )
        if on_logbook_change is not None:  # pragma: no cover
            on_logbook_change(form.logbook)

        return {  # pragma: no cover
            "ok": True,
            "child_name": child_name,
            "child_vacant_id_hex": child_vid.hex(),
            "child_endpoint": child_meta.endpoint,
            "answer": response_text,
            "request_envelope_id_hex": request_env_id_hex,
            "response_envelope_id_hex": response_env_id_hex,
            "transport": "a2a-http",
        }

    # vacant_caller_review — Pfix8 P8.2: 5-dimensional signed review.
    # The thesis-load-bearing peer-review primitive. A caller (this
    # vacant) scores a target vacant's work along five orthogonal
    # dimensions (factual / logical / relevance / honesty / adoption).
    # The review is a signed payload over a canonical JSON encoding of
    # (reviewer, target, dimensions, substrate, call_envelope_id_hex,
    # issued_at) — anyone holding this vacant's pubkey can verify it
    # later. Two side effects:
    #   1. Signed REVIEW_ISSUED entry on this vacant's logbook.
    #   2. JSONL line appended to the target's
    #      ``~/.vacant/<target>/reviews_received.jsonl`` (when the
    #      target is on the same VACANT_HOME). The transport detail
    #      (local file vs HTTP A2A) is interchangeable because the
    #      signature is over the payload, not over the wire.
    @mcp.tool(
        name="vacant_caller_review",
        description=(
            "Sign and persist a 5-dimensional peer review of a target "
            "vacant. Dimensions are factual, logical, relevance, "
            "honesty, adoption — each in [0.0, 1.0]. Used after a call "
            "or delegate to record this vacant's judgement of the "
            "target's work. The review is Ed25519-signed by this "
            "vacant; a REVIEW_ISSUED entry lands on this vacant's "
            "logbook, and a matching jsonl row lands in the target's "
            "reviews_received.jsonl (so aggregators can read it later)."
            " Pass call_envelope_id_hex when the review is tied to a "
            "specific delegate/call envelope; pass substrate to "
            "attribute the review to the substrate the target was "
            "running on."
        ),
    )
    async def vacant_caller_review(
        target_vacant_id_hex: str,
        factual: float,
        logical: float,
        relevance: float,
        honesty: float,
        adoption: float,
        substrate: str = "unknown",
        call_envelope_id_hex: str = "",
        claim: str = "",
    ) -> dict[str, Any]:
        if parent_local_name is None:
            return {
                "error": (
                    "vacant_caller_review requires a persistent reviewer "
                    "identity; this MCP server was launched in ephemeral mode."
                )
            }
        dims = {
            "factual": factual,
            "logical": logical,
            "relevance": relevance,
            "honesty": honesty,
            "adoption": adoption,
        }
        for k, v in dims.items():
            if v < 0.0 or v > 1.0:
                return {"error": f"dimension {k!r} out of [0.0, 1.0]: {v}"}
        try:
            target_vid = VacantId(pubkey_bytes=bytes.fromhex(target_vacant_id_hex))
        except (ValueError, TypeError) as exc:  # pragma: no cover -- defensive
            return {"error": f"invalid target_vacant_id_hex: {exc}"}
        if target_vid == form.identity:
            return {"error": "self-review is not allowed"}

        now_iso = datetime.now(UTC).isoformat()
        review_payload: dict[str, Any] = {
            "reviewer": form.identity.hex(),
            "target": target_vid.hex(),
            "dimensions": dims,
            "substrate": substrate,
            "call_envelope_id_hex": call_envelope_id_hex,
            "claim": claim,
            "issued_at": now_iso,
        }
        # Canonical JSON over the full payload (sorted keys, no whitespace
        # padding) — Ed25519 signature is over this byte sequence.
        canonical = json.dumps(review_payload, sort_keys=True, separators=(",", ":"))
        payload_hash = hash_blake2b(canonical.encode("utf-8"))
        signature = signing_key.sign(payload_hash).signature
        signed_record = {
            **review_payload,
            "payload_hash_hex": payload_hash.hex(),
            "signature_hex": signature.hex(),
        }

        # 1. REVIEW_ISSUED on reviewer's own logbook (signed entry).
        form.logbook.append(
            "REVIEW_ISSUED",
            {
                "kind": "REVIEW_ISSUED",
                "target": target_vid.hex(),
                "dimensions": dims,
                "substrate": substrate,
                "call_envelope_id_hex": call_envelope_id_hex,
                "payload_hash_hex": payload_hash.hex(),
                "signature_hex": signature.hex(),
                "ts": time.time(),
            },
            signing_key,
        )
        if on_logbook_change is not None:
            on_logbook_change(form.logbook)

        # 2. Best-effort local delivery: append the signed record to the
        #    target's reviews_received.jsonl when the target lives under
        #    the same VACANT_HOME. Remote / cross-host delivery via A2A
        #    is wired in P8.5; the signature is over the canonical
        #    payload so both transports verify with the same code.
        delivered = False
        home = ls.vacant_home()
        if home.exists():
            for entry in home.iterdir():
                if not entry.is_dir() or not (entry / "meta.json").exists():
                    continue
                try:
                    tm = ls.load_meta(entry.name)
                except (ls.LocalVacantError, OSError, ValueError):  # pragma: no cover
                    continue
                if tm.vacant_id_hex == target_vid.hex():
                    with (entry / "reviews_received.jsonl").open("a", encoding="utf-8") as f:
                        f.write(json.dumps(signed_record, sort_keys=True) + "\n")
                    delivered = True
                    break

        # P8.6: auto-spawn a competitor on consecutive failure
        # (technical.html §06 - "when a vacant fails, a competitor is born").
        # Trigger: target is a direct descendant of this vacant AND
        # the last 3 reviews in reviews_received.jsonl have a mean
        # dimension below 0.3. Spawn a new D1 sibling that inherits
        # the failing child's policy_mutation with a corrective tail.
        # The failing child is NOT deleted (architecture: failed
        # vacants stay alive — history is preserved, network selects).
        competitor: dict[str, Any] | None = None
        if delivered and parent_local_name is not None and persist_spawned_child is not None:
            target_dir = None
            target_meta = None
            for entry in ls.vacant_home().iterdir():
                if not entry.is_dir() or not (entry / "meta.json").exists():  # pragma: no cover
                    continue
                try:
                    tm = ls.load_meta(entry.name)
                except (ls.LocalVacantError, OSError, ValueError):  # pragma: no cover
                    continue
                if tm.vacant_id_hex == target_vid.hex():
                    target_dir = entry
                    target_meta = tm
                    break
            if (
                target_dir is not None
                and target_meta is not None
                and target_meta.parent_id_hex == form.identity.hex()
            ):
                reviews_path = target_dir / "reviews_received.jsonl"
                recent: list[dict[str, float]] = []
                if reviews_path.exists():
                    with reviews_path.open(encoding="utf-8") as rf:
                        for line in rf:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                row = json.loads(line)
                                rd = row.get("dimensions") or {}
                                if isinstance(rd, dict):
                                    recent.append(rd)
                            except json.JSONDecodeError:  # pragma: no cover
                                continue
                last3 = recent[-3:]
                if len(last3) >= 3:
                    means = []
                    for row in last3:
                        nums = [
                            float(row[k])
                            for k in ("factual", "logical", "relevance", "honesty", "adoption")
                            if k in row and isinstance(row[k], int | float)
                        ]
                        if nums:  # pragma: no cover -- branch coverage
                            means.append(sum(nums) / len(nums))
                    if means and all(m < 0.3 for m in means):
                        # Find the failing child's BIRTH policy_mutation to
                        # carry forward into the corrective mutation.
                        old_mutation = ""
                        try:
                            failing_lb = ls.load_logbook(target_dir.name)
                            for e in failing_lb.entries:
                                if e.kind == "BIRTH":
                                    old_mutation = e.payload.get("policy_mutation") or ""
                                    break
                        except (ls.LocalVacantError, OSError):  # pragma: no cover
                            pass
                        corrective = (
                            f"{old_mutation} -- correction after 3 sub-0.3 reviews: "
                            f"prioritise correctness over speed, ask for confirmation "
                            f"on ambiguous inputs"
                        ).strip(" -")
                        try:
                            result = spawn_clone_with_mutation(
                                form, signing_key, policy_mutation=corrective
                            )
                        except Exception as exc:  # pragma: no cover
                            competitor = {"error": f"competitor_spawn_failed: {exc}"}
                        else:
                            child_short = result.child.identity.short()
                            sibling_name = f"{parent_local_name}__competitor__{child_short}"
                            try:
                                persist_spawned_child(result, sibling_name, parent_local_name)
                            except Exception as exc:  # pragma: no cover
                                competitor = {"error": f"competitor_persist_failed: {exc}"}
                            else:
                                form.logbook.append(
                                    "COMPETITOR_SPAWNED",
                                    {
                                        "kind": "COMPETITOR_SPAWNED",
                                        "failing_child_id": target_vid.hex(),
                                        "failing_child_name": target_dir.name,
                                        "competitor_child_id": result.child.identity.hex(),
                                        "competitor_child_name": sibling_name,
                                        "corrective_mutation": corrective,
                                        "reason": "three_consecutive_reviews_below_0.3",
                                        "ts": time.time(),
                                    },
                                    signing_key,
                                )
                                if on_logbook_change is not None:  # pragma: no cover -- branch
                                    on_logbook_change(form.logbook)
                                competitor = {
                                    "competitor_child_name": sibling_name,
                                    "competitor_child_vacant_id_hex": result.child.identity.hex(),
                                    "corrective_mutation": corrective,
                                    "reason": "three_consecutive_reviews_below_0.3",
                                }

        return {
            "ok": True,
            "reviewer_vacant_id_hex": form.identity.hex(),
            "target_vacant_id_hex": target_vid.hex(),
            "dimensions": dims,
            "substrate": substrate,
            "call_envelope_id_hex": call_envelope_id_hex,
            "payload_hash_hex": payload_hash.hex(),
            "signature_hex": signature.hex(),
            "delivered_locally": delivered,
            "competitor_spawned": competitor,
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
