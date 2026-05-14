"""Wired CLI commands.

Each command in this module replaces the `_NOT_YET` stub that shipped
with P0. The local-state store at `~/.vacant/<name>/` is owned by
`vacant.cli.local_store`; HTTP work goes through `httpx.AsyncClient`
against a registry URL (env `VACANT_REGISTRY_URL` or `--registry`).

A few commands (`call`, `attest`) require remote endpoints that ship
with PR-β (`vacant serve` + the wired-up `/v1/submit_attestation`).
Those subcommands degrade gracefully with a clear ``not available
yet`` exit code so the help surface is complete and a future PR can
enable them in place. F4 acceptance only requires the commands to run
end-to-end — the remote-only features have explicit pending tickets.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer

from vacant.cli import local_store as ls
from vacant.cli.local_store import LocalVacantError, LocalVacantNotFound
from vacant.core.types import (
    BehaviorBundle,
    CapabilityCard,
    Logbook,
    ResidentForm,
    SubstrateSpec,
    VacantId,
    VacantState,
)
from vacant.identity.attestation import issue_attestation
from vacant.protocol.capability_card import serialize as serialize_card
from vacant.registry.halo import (
    RegisterEventDraftInputs,
    register_event_canonical_bytes,
)
from vacant.registry.visibility import Visibility
from vacant.runtime.heartbeat import heartbeat_kind, heartbeat_payload

__all__ = ["app", "main"]


app = typer.Typer(
    name="vacant",
    help="Vacant — responsibility-layer residency form for AI agents.",
    add_completion=False,
    no_args_is_help=True,
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _now_ms() -> int:
    return int(datetime.now(UTC).timestamp() * 1000)


def _resolve_name(explicit: str | None) -> str:
    if explicit:
        return explicit
    try:
        return ls.current_name()
    except LocalVacantNotFound as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc


def _resolve_registry(explicit: str | None) -> str:
    url = explicit or os.environ.get("VACANT_REGISTRY_URL")
    if not url:
        typer.echo(
            "error: registry URL required; pass --registry or set VACANT_REGISTRY_URL",
            err=True,
        )
        raise typer.Exit(code=2)
    return url.rstrip("/")


# -- init ---------------------------------------------------------------------


@app.command("init")
def init_cmd(
    name: str,
    insecure_demo: bool = typer.Option(
        False,
        "--insecure-demo",
        help=(
            "Store the Ed25519 seed in plaintext key.json (mode 0600) "
            "instead of the OS keyring. Demo / CI use only — see SECURITY.md."
        ),
    ),
) -> None:
    """Create a fresh keypair + seed logbook for `name`. (P2)

    Writes `~/.vacant/<name>/{key.json,logbook.jsonl,meta.json}` with
    file mode 0600 on the key. The Ed25519 seed is stored in the OS
    keyring by default (Keychain / Secret Service / Credential
    Locker); pass `--insecure-demo` to fall back to plaintext on
    hosts without a keyring backend.
    """
    try:
        vid, _sk = ls.init_vacant(name, insecure_demo=insecure_demo)
    except ls.LocalVacantExists:
        typer.echo(f"error: local vacant {name!r} already exists", err=True)
        raise typer.Exit(code=1) from None
    except ls.LocalVacantKeyringUnavailable as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except LocalVacantError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps({"name": name, "vacant_id": vid.hex()}, sort_keys=True))


# -- status -------------------------------------------------------------------


@app.command("status")
def status_cmd(
    all_: bool = typer.Option(False, "--all", help="Include hibernating/stale/sunk."),
) -> None:
    """Show local vacants and their lifecycle states. (P1)"""
    rows: list[dict[str, Any]] = []
    for n in ls.list_vacant_names():
        try:
            meta = ls.load_meta(n)
        except LocalVacantNotFound:
            continue
        if not all_ and meta.state in {"HIBERNATING", "STALE", "SUNK", "ARCHIVED"}:
            continue
        rows.append(
            {
                "name": n,
                "vacant_id": meta.vacant_id_hex,
                "state": meta.state,
                "capability_text": meta.capability_text,
                "endpoint": meta.endpoint,
                "halo_published": meta.halo_published,
                "last_heartbeat_at": meta.last_heartbeat_at,
            }
        )
    typer.echo(json.dumps({"vacants": rows}, sort_keys=True, indent=2))


# -- heartbeat ----------------------------------------------------------------


@app.command("heartbeat")
def heartbeat_cmd(
    name: str | None = typer.Option(
        None, "--name", help="Local vacant name; defaults to VACANT_NAME."
    ),
) -> None:
    """Manually trigger a heartbeat tick. (P1)"""
    n = _resolve_name(name)
    try:
        meta = ls.load_meta(n)
        sk = ls.load_signing_key(n)
        lb = ls.load_logbook(n)
    except LocalVacantNotFound as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    state = VacantState(meta.state)
    if state == VacantState.ARCHIVED:
        typer.echo("error: ARCHIVED vacants do not heartbeat", err=True)
        raise typer.Exit(code=2)
    payload = heartbeat_payload(state)
    kind = heartbeat_kind(state)
    entry = lb.append(kind, payload, sk)
    ls.save_logbook(n, lb)
    meta.last_heartbeat_at = _now_iso()
    ls.save_meta(n, meta)
    typer.echo(
        json.dumps(
            {
                "name": n,
                "kind": kind,
                "state": state.value,
                "ts": entry.ts.isoformat(),
                "logbook_entries": len(lb.entries),
            },
            sort_keys=True,
        )
    )


# -- publish ------------------------------------------------------------------


def _build_card(
    vid: VacantId,
    *,
    capability_text: str,
    endpoint: str | None,
    allowed_substrates: list[str],
    sk: Any,
) -> CapabilityCard:
    spec = SubstrateSpec(allowed_substrates=allowed_substrates)
    return CapabilityCard(
        vacant_id=vid,
        capability_text=capability_text,
        substrate_spec=spec,
        endpoint=endpoint,
    ).signed(sk)


async def _next_actor_seq(http: Any, registry_url: str, vid_hex: str) -> int:
    """Walk `/v1/event_log/<vid>` pages to find the highest actor_seq."""
    next_seq = 0
    from_seq = 0
    while True:
        r = await http.get(
            f"{registry_url}/v1/event_log/{vid_hex}",
            params={"from_seq": from_seq, "limit": 100},
        )
        if r.status_code != 200:
            return next_seq + 1
        rows = r.json()
        if not rows:
            return next_seq + 1
        for row in rows:
            next_seq = max(next_seq, int(row.get("actor_seq", 0)))
        last_overall_seq = int(rows[-1]["seq"])
        if last_overall_seq <= from_seq:
            return next_seq + 1
        from_seq = last_overall_seq


async def _do_publish(
    *,
    name: str,
    registry_url: str,
    capability_text: str,
    endpoint: str | None,
    base_model: str | None,
    base_model_family: str | None,
) -> dict[str, Any]:
    import httpx

    from vacant.core.crypto import sign

    sk = ls.load_signing_key(name)
    meta = ls.load_meta(name)
    vid = VacantId(pubkey_bytes=bytes.fromhex(meta.vacant_id_hex))
    card = _build_card(
        vid,
        capability_text=capability_text,
        endpoint=endpoint,
        allowed_substrates=["mock", "anthropic"],
        sk=sk,
    )
    blob_hex = serialize_card(card).hex()
    ts_ms = _now_ms()
    idempotency_key = f"register:{vid.hex()}:{ts_ms}"
    visibility = Visibility.PUBLIC

    async with httpx.AsyncClient(timeout=30.0) as http:
        actor_seq = await _next_actor_seq(http, registry_url, vid.hex())
        from vacant.core.crypto import hash_blake2b

        inputs = RegisterEventDraftInputs(
            vacant_id=vid.hex(),
            capability_card_hash=hash_blake2b(card.signing_payload()),
            halo_version=card.halo_version,
            visibility=visibility,
            ts_ms=ts_ms,
            actor_seq=actor_seq,
            idempotency_key=idempotency_key,
        )
        canonical = register_event_canonical_bytes(inputs, signed_by_pubkey=vid.pubkey_bytes)
        signature = sign(sk, canonical)
        body: dict[str, Any] = {
            "capability_card_blob_hex": blob_hex,
            "runtime_state": "ACTIVE",
            "visibility": visibility.value,
            "event_ts_ms": ts_ms,
            "event_actor_seq": actor_seq,
            "event_idempotency_key": idempotency_key,
            "event_signature_hex": signature.hex(),
        }
        # Pfix3 F2: only include caller-supplied metadata in the wire
        # body. Omitted flags → omitted in JSON → server interprets as
        # "preserve existing on republish, fallback to default on insert".
        if base_model is not None:
            body["base_model"] = base_model
        if base_model_family is not None:
            body["base_model_family"] = base_model_family
        r = await http.post(f"{registry_url}/v1/halo", json=body)
        r.raise_for_status()
        result = r.json()

    meta.state = "ACTIVE"
    meta.capability_text = capability_text
    meta.endpoint = endpoint
    meta.halo_published = True
    ls.save_meta(name, meta)
    return dict(result)


@app.command("publish")
def publish_cmd(
    capability: str = typer.Option(..., "--capability", help="Capability text to advertise."),
    endpoint: str | None = typer.Option(None, "--endpoint", help="A2A endpoint URL."),
    registry: str | None = typer.Option(None, "--registry", help="Registry URL."),
    name: str | None = typer.Option(None, "--name", help="Local vacant name."),
    base_model: str | None = typer.Option(
        None,
        "--base-model",
        help=(
            "Base model identifier (e.g. 'claude-sonnet-4-6'). On the "
            "first publish, omitted → defaults to 'unknown'. On a "
            "republish, omitted → preserves the stored value (Pfix3 F2)."
        ),
    ),
    base_model_family: str | None = typer.Option(
        None,
        "--base-model-family",
        help=("Base model family (e.g. 'claude'). Same null-vs-default semantics as --base-model."),
    ),
) -> None:
    """Flip LOCAL → ACTIVE (publish halo to registry). (P4)"""
    n = _resolve_name(name)
    url = _resolve_registry(registry)
    try:
        result = asyncio.run(
            _do_publish(
                name=n,
                registry_url=url,
                capability_text=capability,
                endpoint=endpoint,
                base_model=base_model,
                base_model_family=base_model_family,
            )
        )
    except Exception as exc:
        typer.echo(f"error: publish failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(result, sort_keys=True))


# -- unpublish ----------------------------------------------------------------


@app.command("unpublish")
def unpublish_cmd(
    name: str | None = typer.Option(None, "--name", help="Local vacant name."),
) -> None:
    """Flip ACTIVE → LOCAL (visibility=NONE). (P4)

    Note: this only flips the local meta; the registry record is
    not revoked over HTTP yet (the `/v1/revoke_halo` endpoint
    requires a P6 envelope, see ``rpc.py``). Use the python
    `vacant.registry.halo.revoke_halo` API for full withdrawal.
    """
    n = _resolve_name(name)
    try:
        meta = ls.load_meta(n)
    except LocalVacantNotFound as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    meta.state = "LOCAL"
    meta.halo_published = False
    ls.save_meta(n, meta)
    typer.echo(
        json.dumps(
            {
                "name": n,
                "state": "LOCAL",
                "warning": (
                    "registry halo not actively revoked over HTTP yet; "
                    "see vacant.registry.halo.revoke_halo()"
                ),
            },
            sort_keys=True,
        )
    )


# -- lineage ------------------------------------------------------------------


@app.command("lineage")
def lineage_cmd(
    vid: str,
    direction: str = typer.Option("ancestors", "--direction", help="ancestors | descendants"),
    depth: int = typer.Option(8, "--depth", min=1, max=32),
    registry: str | None = typer.Option(None, "--registry", help="Registry URL."),
) -> None:
    """Print the parent_id chain for `vid`. (P4)"""
    if direction not in {"ancestors", "descendants"}:
        typer.echo("error: --direction must be 'ancestors' or 'descendants'", err=True)
        raise typer.Exit(code=2)
    url = _resolve_registry(registry)

    async def _go() -> dict[str, Any]:
        import httpx

        async with httpx.AsyncClient(timeout=15.0) as http:
            r = await http.get(
                f"{url}/v1/lineage/{vid}",
                params={"direction": direction, "depth": depth},
            )
            r.raise_for_status()
            data: dict[str, Any] = r.json()
            return data

    try:
        out = asyncio.run(_go())
    except Exception as exc:
        typer.echo(f"error: lineage lookup failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(out, sort_keys=True))


# -- attest -------------------------------------------------------------------


@app.command("attest")
def attest_cmd(
    target_vid: str,
    claim: str,
    name: str | None = typer.Option(None, "--name", help="Local vacant name."),
) -> None:
    """Issue a peer attestation about `target_vid`. (P2)

    Signs a `PeerAttestation` and stores it in
    `~/.vacant/<name>/attestations_issued.jsonl`. The HTTP relay to
    the registry's `/v1/submit_attestation` endpoint lands in PR-β
    (the endpoint is currently a P6-envelope stub).
    """
    n = _resolve_name(name)
    try:
        meta = ls.load_meta(n)
        sk = ls.load_signing_key(n)
    except LocalVacantNotFound as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    try:
        attester = VacantId(pubkey_bytes=bytes.fromhex(meta.vacant_id_hex))
        attestee = VacantId(pubkey_bytes=bytes.fromhex(target_vid))
    except ValueError as exc:
        typer.echo(f"error: invalid vacant_id hex: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    att = issue_attestation(
        attester=attester, attestee=attestee, claim=claim, attester_signing_key=sk
    )
    record = {
        "attester": att.attester.hex(),
        "attestee": att.attestee.hex(),
        "claim": att.claim,
        "issued_at": att.issued_at.isoformat(),
        "expires_at": att.expires_at.isoformat(),
        "signature_hex": att.signature.hex(),
    }
    out_path = ls.vacant_dir(n) / "attestations_issued.jsonl"
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    typer.echo(json.dumps(record, sort_keys=True))


# -- call ---------------------------------------------------------------------


def _residentform_for(name: str) -> ResidentForm:
    meta = ls.load_meta(name)
    sk = ls.load_signing_key(name)
    lb = ls.load_logbook(name)
    vid = VacantId(pubkey_bytes=bytes.fromhex(meta.vacant_id_hex))
    bundle = BehaviorBundle(system_prompt="cli")
    spec = SubstrateSpec(allowed_substrates=["mock"])
    _ = sk
    return ResidentForm(
        identity=vid,
        logbook=lb if lb.entries else Logbook(),
        behavior_bundle=bundle,
        substrate_spec=spec,
        runtime_state=VacantState(meta.state),
    )


@app.command("call")
def call_cmd(
    vid: str,
    capability: str,
    text: str = typer.Option("ping", "--text", help="Body text to send."),
    registry: str | None = typer.Option(None, "--registry", help="Registry URL."),
    name: str | None = typer.Option(None, "--name", help="Local vacant name."),
) -> None:
    """Send a request to a remote vacant. (P6)

    Looks up the target's `CapabilityCard` via the registry's
    `/v1/capability_card/<vid>` endpoint and dispatches a signed
    envelope to `card.endpoint`. The `--endpoint` direct-known mode
    lands with PR-β alongside `vacant serve`'s `/card` route.
    """
    n = _resolve_name(name)
    url = _resolve_registry(registry)
    _ = capability  # capability filter is informational for now; lookup is by vid

    async def _go() -> dict[str, Any]:
        import httpx

        from vacant.core.types import EMPTY_PREV_HASH
        from vacant.protocol.capability_card import deserialize as deserialize_card
        from vacant.protocol.dispatch import call_local, make_httpx_transport
        from vacant.protocol.envelope import A2AMessage, A2APart
        from vacant.protocol.replay_protect import (
            InMemoryReplayStore,
            PairKey,
            ReplayState,
        )

        sk = ls.load_signing_key(n)
        form = _residentform_for(n)
        async with httpx.AsyncClient(timeout=15.0) as http:
            r = await http.get(
                f"{url}/v1/capability_card/{vid}",
                params={"caller": form.identity.hex()},
            )
            r.raise_for_status()
            row = r.json()
        blob_hex = row.get("capability_card_blob_hex", "")
        if not blob_hex:
            raise RuntimeError(
                f"registry returned no signed card blob for {vid}; "
                "the row pre-dates the capability_card_blob column"
            )
        target_card = deserialize_card(bytes.fromhex(blob_hex))
        transport = make_httpx_transport(timeout=30.0)

        # Pfix3 B6: continue the per-pair envelope chain from disk.
        # Without this, every CLI call defaulted to seq=1 / EMPTY prev,
        # and the second call to the same target was rejected as
        # replay by the server. Layout in envelope_state.json:
        #   {"<target_hex>": {"request": {...}, "response": {...}}}
        env_state = ls.load_envelope_state(n)
        target_hex = target_card.vacant_id.hex()
        target_state = env_state.get(target_hex, {})
        req_state = target_state.get("request", {})
        last_req_seq = int(req_state.get("last_seq", 0))
        last_req_hash_hex = str(req_state.get("last_hash_hex", ""))
        last_req_hash = bytes.fromhex(last_req_hash_hex) if last_req_hash_hex else EMPTY_PREV_HASH

        # Caller-side response replay store, seeded so the first
        # response on a pair starts at seq=1 / EMPTY prev (matching
        # `make_response_envelope` on the server side).
        rsp_state = target_state.get("response", {})
        last_rsp_seq = int(rsp_state.get("last_seq", 0))
        last_rsp_hash_hex = str(rsp_state.get("last_hash_hex", ""))
        last_rsp_hash = bytes.fromhex(last_rsp_hash_hex) if last_rsp_hash_hex else EMPTY_PREV_HASH
        caller_rsp_store = InMemoryReplayStore()
        if last_rsp_seq > 0:
            inverse_key = PairKey(from_vid=target_card.vacant_id, to_vid=form.identity)
            caller_rsp_store.seed(
                inverse_key,
                ReplayState(last_sequence_no=last_rsp_seq, chain_tip=last_rsp_hash),
            )

        result = await call_local(
            target_card=target_card,
            requester=form,
            requester_signing_key=sk,
            payload=A2AMessage(role="ROLE_USER", parts=[A2APart(text=text)]),
            transport=transport,
            sequence_no=last_req_seq + 1,
            prev_envelope_hash=last_req_hash,
            caller_response_replay_store=caller_rsp_store,
        )

        # Persist the new chain tips so the next call advances.
        env_state[target_hex] = {
            "request": {
                "last_seq": result.request_envelope.sequence_no,
                "last_hash_hex": result.request_envelope.compute_hash().hex(),
            },
            "response": {
                "last_seq": result.response_envelope.sequence_no,
                "last_hash_hex": result.response_envelope.compute_hash().hex(),
            },
        }
        ls.save_envelope_state(n, env_state)

        return {
            "target": target_hex,
            "endpoint": target_card.endpoint,
            "request_seq": result.request_envelope.sequence_no,
            "response_role": result.response_envelope.payload.role,
            "response_text": "".join(p.text for p in result.response_envelope.payload.parts),
        }

    try:
        out = asyncio.run(_go())
    except Exception as exc:
        typer.echo(f"error: call failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(out, sort_keys=True))


# -- serve --------------------------------------------------------------------


@app.command("serve")
def serve_cmd(
    port: int = typer.Option(8443, "--port", "-p", help="HTTP bind port."),
    host: str = typer.Option("127.0.0.1", "--host", help="HTTP bind host."),
    name: str | None = typer.Option(None, "--name", help="Local vacant name."),
    mcp: bool = typer.Option(False, "--mcp", help="Also expose an MCP stdio server."),
    endpoint: str | None = typer.Option(
        None,
        "--endpoint",
        help="Public endpoint URL to advertise in /card (defaults to meta.endpoint).",
    ),
    public: bool = typer.Option(
        False,
        "--public",
        help=(
            "Bind 0.0.0.0 instead of 127.0.0.1 so external machines can "
            "reach this vacant. Implies you've thought about firewall + "
            "TLS (use --tls-cert/--tls-key or a reverse proxy like Caddy)."
        ),
    ),
    tls_cert: Path | None = typer.Option(  # noqa: B008 — Typer-required pattern
        None,
        "--tls-cert",
        help="PEM-encoded TLS certificate. When set, uvicorn serves HTTPS.",
    ),
    tls_key: Path | None = typer.Option(  # noqa: B008 — Typer-required pattern
        None,
        "--tls-key",
        help="PEM-encoded TLS private key. Must be set together with --tls-cert.",
    ),
    substrate: str | None = typer.Option(
        None,
        "--substrate",
        help=(
            "LLM substrate this vacant uses to answer inbound A2A calls. "
            "mock | deterministic | anthropic | openai | ollama | gemini | mistral. "
            "Default: pure echo (no LLM)."
        ),
    ),
) -> None:
    """Start an HTTP A2A server for the local vacant. (P6)

    The server listens on `host:port` and accepts inbound A2A
    `message/send` requests at `/a2a/message/send`. The default
    behaviour callback echoes the request text back, signed by the
    vacant's own key — sufficient for the live-network acceptance test.

    `--mcp` additionally launches an MCP stdio server in a worker
    thread. This is what closes the "嫁接到客戶端" thesis claim: the
    same vacant accepts both A2A HTTP and MCP stdio simultaneously.

    `--public` flips the bind host from 127.0.0.1 to 0.0.0.0 so machines
    on your LAN (or the public internet, if you've configured port
    forwarding / Cloudflare Tunnel / Tailscale / etc.) can reach this
    vacant. By default `vacant serve` only listens on loopback — this
    flag is an explicit acknowledgement that you've thought about how
    callers reach you and whether you need TLS.

    `--tls-cert` + `--tls-key` pin a PEM cert + key pair so uvicorn
    serves HTTPS directly. Useful for Tailscale-internal hostnames
    where Tailscale already issues the cert. For public domains the
    saner pattern is to terminate TLS in Caddy / nginx / Cloudflare
    and leave this vacant on plain HTTP behind it — see
    `docs/DEPLOY_PUBLIC.md`.
    """
    import uvicorn

    from vacant.cli.server import build_serve_app
    from vacant.cli.substrate_behavior import resolve_substrate, substrate_behavior

    if public and host == "127.0.0.1":
        host = "0.0.0.0"  # noqa: S104 — explicit operator opt-in via --public
    if (tls_cert is None) != (tls_key is None):
        typer.echo(
            "error: --tls-cert and --tls-key must be set together",
            err=True,
        )
        raise typer.Exit(code=2)
    n = _resolve_name(name)
    behavior = None
    if substrate is not None:
        backend = resolve_substrate(substrate)
        try:
            meta_for_prompt = ls.load_meta(n)
            sysprompt = meta_for_prompt.capability_text or "You are a helpful vacant."
        except ls.LocalVacantNotFound:
            sysprompt = "You are a helpful vacant."
        behavior = substrate_behavior(backend, system_prompt=sysprompt)
    bundle = build_serve_app(n, behavior=behavior, endpoint=endpoint)

    if mcp:
        # Lazy import — only paid for when --mcp is set.
        import threading

        from vacant.cli.mcp_server import run_mcp_stdio_server

        t = threading.Thread(
            target=run_mcp_stdio_server,
            kwargs={
                "form": bundle.form,
                "signing_key": bundle.signing_key,
                "replay_store": bundle.replay_store,
            },
            daemon=True,
            name="vacant-mcp-stdio",
        )
        t.start()

    # Pfix8 P8.1: advertise our endpoint in meta.json so peers (parent
    # vacants performing A2A delegation, sibling vacants performing
    # peer review) can discover us. Without this, vacant-to-vacant
    # routing has to be configured out-of-band per call.
    advertised = endpoint or f"http://{host}:{port}"
    try:  # pragma: no cover -- exercised by tests/integration/test_a2a_delegation.py
        meta = ls.load_meta(n)
        if meta.endpoint != advertised:
            meta.endpoint = advertised
            ls.save_meta(n, meta)
    except ls.LocalVacantNotFound:  # pragma: no cover
        # Ephemeral / no on-disk identity — nothing to advertise.
        pass

    typer.echo(
        json.dumps(
            {
                "name": n,
                "vacant_id": bundle.form.identity.hex(),
                "host": host,
                "port": port,
                "endpoint": advertised,
                "mcp": mcp,
                "tls": tls_cert is not None,
                "public": public,
            },
            sort_keys=True,
        )
    )
    uvicorn_kwargs: dict[str, Any] = {
        "host": host,
        "port": port,
        "log_level": "warning",
    }
    if tls_cert is not None and tls_key is not None:
        uvicorn_kwargs["ssl_certfile"] = str(tls_cert)
        uvicorn_kwargs["ssl_keyfile"] = str(tls_key)
    uvicorn.run(bundle.app, **uvicorn_kwargs)


# -- grow (serve + background peer-review / redteam / heartbeat loop) -------


@app.command("grow")
def grow_cmd(
    port: int = typer.Option(8443, "--port", "-p", help="HTTP bind port."),
    host: str = typer.Option("127.0.0.1", "--host", help="HTTP bind host."),
    name: str | None = typer.Option(None, "--name", help="Local vacant name."),
    endpoint: str | None = typer.Option(
        None, "--endpoint", help="Public endpoint URL to advertise."
    ),
    peer_review_period_s: float = typer.Option(
        30.0,
        "--peer-review-period",
        help="Seconds between peer-review ticks.",
    ),
    redteam_every_n: int = typer.Option(
        4,
        "--redteam-every-n",
        help="Inject a red-team probe every Nth tick (0 = never).",
    ),
    heartbeat_every_n: int = typer.Option(
        2,
        "--heartbeat-every-n",
        help="Append a heartbeat to our logbook every Nth tick (0 = never).",
    ),
    substrate: str | None = typer.Option(
        None,
        "--substrate",
        help=(
            "LLM substrate this vacant uses to ANSWER incoming probes. "
            "mock | deterministic | anthropic | openai | ollama | gemini | mistral. "
            "Default: pure echo (no LLM). Real substrates need an API key."
        ),
    ),
    scorer_substrate: str | None = typer.Option(
        None,
        "--scorer-substrate",
        help=(
            "LLM substrate this vacant uses to SCORE peers (5D). "
            "Same value space as --substrate. Default: length-based heuristic. "
            "Recommended different from --substrate for cross-model diversity."
        ),
    ),
) -> None:
    """Serve A2A *and* run the local-network grow loop.

    Identical to `vacant serve` plus a background async task that
    periodically peer-reviews siblings under the same `VACANT_HOME`,
    injects red-team probes, and appends heartbeats to our own
    logbook. Multiple `vacant grow` processes on the same machine
    form a fully signed local vacant network — no central arbiter.

    Quick start (one terminal per vacant):

      vacant init alice
      vacant init bob
      vacant init carol
      vacant grow --name alice --port 8443 &
      vacant grow --name bob   --port 8444 &
      vacant grow --name carol --port 8445 &
      # then watch ~/.vacant/<name>/reviews_received.jsonl files fill up
    """
    import uvicorn

    from vacant.cli.server import build_serve_app
    from vacant.cli.substrate_behavior import (
        build_scorer_from_name,
        resolve_substrate,
        substrate_behavior,
    )
    from vacant.runtime.grow import GrowLoop, make_grow_lifespan

    n = _resolve_name(name)
    behavior = None
    if substrate is not None:
        backend = resolve_substrate(substrate)
        # System prompt comes from meta if available; otherwise a default.
        try:
            meta_for_prompt = ls.load_meta(n)
            sysprompt = meta_for_prompt.capability_text or "You are a helpful vacant."
        except ls.LocalVacantNotFound:
            sysprompt = "You are a helpful vacant."
        behavior = substrate_behavior(backend, system_prompt=sysprompt)
    bundle = build_serve_app(n, behavior=behavior, endpoint=endpoint)
    advertised = endpoint or f"http://{host}:{port}"
    try:
        meta = ls.load_meta(n)
        if meta.endpoint != advertised:
            meta.endpoint = advertised
            ls.save_meta(n, meta)
    except ls.LocalVacantNotFound:  # pragma: no cover
        pass

    scorer = build_scorer_from_name(scorer_substrate)

    loop = GrowLoop(
        self_form=bundle.form,
        self_signing_key=bundle.signing_key,
        peer_review_period_s=peer_review_period_s,
        redteam_every_n_ticks=redteam_every_n,
        heartbeat_every_n_ticks=heartbeat_every_n,
        scorer=scorer,
    )
    bundle.app.router.lifespan_context = make_grow_lifespan(loop)

    @bundle.app.get("/grow/stats")
    async def _grow_stats() -> dict[str, Any]:
        return loop.stats.as_dict()

    typer.echo(
        json.dumps(
            {
                "name": n,
                "vacant_id": bundle.form.identity.hex(),
                "host": host,
                "port": port,
                "endpoint": advertised,
                "grow": {
                    "peer_review_period_s": peer_review_period_s,
                    "redteam_every_n": redteam_every_n,
                    "heartbeat_every_n": heartbeat_every_n,
                    "substrate": substrate or "echo",
                    "scorer_substrate": scorer_substrate or "heuristic",
                },
            },
            sort_keys=True,
        )
    )
    uvicorn.run(bundle.app, host=host, port=port, log_level="warning")


# -- mcp (pure stdio, no HTTP) -----------------------------------------------


def _build_ephemeral_form() -> tuple[ResidentForm, Any]:
    """Construct an in-memory `(form, signing_key)` for `vacant mcp`
    when no local vacant exists.

    Useful when a user hits `claude plugin install vacant` without
    having run `vacant init` first — they still get a working MCP
    server backed by a demo identity. The keypair never touches the
    disk; restarting the process gives a fresh identity.
    """
    from vacant.core.crypto import keygen

    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    spec = SubstrateSpec(allowed_substrates=["mock", "client-inherited"])
    bundle = BehaviorBundle(system_prompt="vacant mcp (ephemeral demo)")
    card = CapabilityCard(
        vacant_id=vid,
        capability_text="ephemeral demo vacant — no on-disk state, fresh keypair per launch",
        substrate_spec=spec,
    ).signed(sk)
    form = ResidentForm(
        identity=vid,
        logbook=Logbook(),
        behavior_bundle=bundle,
        substrate_spec=spec,
        runtime_state=VacantState.LOCAL,
        capability_card=card,
    )
    return form, sk


@app.command("route")
def route_cmd(
    prompt: str = typer.Argument(..., help="The user task / question."),
    name: str = typer.Option("alice", "--name", help="Local vacant name to host the MCP server."),
    model: str = typer.Option(
        "gemma4:e2b", "--model", help="Model id at the OpenAI-compatible endpoint."
    ),
    base_url: str = typer.Option(
        None,
        "--base-url",
        envvar=["LLM_BASE_URL", "OLLAMA_BASE_URL"],
        help="OpenAI-compat base URL (must include /v1).",
    ),
    api_key: str = typer.Option(
        "",
        "--api-key",
        envvar=["LLM_API_KEY", "OLLAMA_API_KEY"],
        help="Bearer token for the LLM endpoint (some, e.g. Ollama, accept any value).",
    ),
    max_rounds: int = typer.Option(8, "--max-rounds", help="Maximum LLM ↔ tool rounds."),
    temperature: float = typer.Option(0.0, "--temperature"),
    vacant_home: str | None = typer.Option(
        None,
        "--vacant-home",
        envvar="VACANT_HOME",
        help="Override $VACANT_HOME for the spawned MCP server.",
    ),
    uvx: str = typer.Option(
        "uvx", "--uvx", envvar="UVX", help="uvx executable to spawn `vacant mcp` with."
    ),
) -> None:
    """ReAct-style agent loop for ANY LLM (model-agnostic).

    Hermes / OpenClaw / Claude Desktop / Cursor route LLM ↔ Vacant
    traffic through OpenAI function-call JSON. Models below ~7B can't
    emit that format reliably, so the framework swallows the call.
    `vacant route` is the workaround: a tiny XML-ish action protocol
    that any model with `/v1/chat/completions` can drive.

    Example::

        LLM_BASE_URL=http://192.168.50.130:11434/v1 \\
        LLM_API_KEY=ollama \\
        vacant route --name alice --model gemma4:e2b \\
          "Translate this technical Chinese paragraph; spawn a D1 child if helpful."
    """
    from vacant.cli import route as route_mod

    if not base_url:
        typer.echo(
            "error: --base-url (or LLM_BASE_URL / OLLAMA_BASE_URL) is required",
            err=True,
        )
        raise typer.Exit(code=2)

    rc = route_mod.main(
        prompt=prompt,
        name=name,
        model=model,
        base_url=base_url,
        api_key=api_key,
        max_rounds=max_rounds,
        temperature=temperature,
        vacant_home=vacant_home,
        uvx=uvx,
    )
    if rc != 0:
        raise typer.Exit(code=rc)


@app.command("mcp")
def mcp_cmd(
    name: str | None = typer.Option(
        None,
        "--name",
        help=(
            "Local vacant name to serve. If `--name <n>` (or env "
            "$VACANT_NAME=<n>) is set but `~/.vacant/<n>/` doesn't exist, "
            "this command exits with code 2 — it deliberately does NOT "
            "fall back to ephemeral mode to avoid silently dropping the "
            "audit chain. Run `vacant install <client>` or `vacant init "
            "<n>` to bootstrap the identity first."
        ),
    ),
) -> None:
    """Run the vacant as a pure-stdio MCP server. (D2 / Claude Code plugin)

    No HTTP, no worker threads, no `uvicorn` — the process IS the
    MCP server. Spawned by `uvx vacant mcp` from the
    `.claude-plugin/plugin.json` manifest, which is what Claude Code
    calls when a user runs `/plugin install vacant`. EOF on stdin
    (the parent closing the pipe) ends the loop.

    **Pfix5 runtime contract** — identity resolution is strict and
    side-effect-free:

    1. `--name <n>` or env `$VACANT_NAME=<n>` is set:
       - if `~/.vacant/<n>/` exists ⇒ serve as `<n>`
       - if missing ⇒ print clear stderr error + exit 2
         (does NOT silently fall back; does NOT auto-init)
    2. no `--name` and no `$VACANT_NAME`, but exactly one local vacant
       on disk ⇒ serve as that vacant
    3. no `--name`, no `$VACANT_NAME`, no local vacants ⇒ ephemeral
       in-memory demo + stderr WARN (this is the explicit "no
       identity asked for" case, not a fallback)

    Why strict on case 1: when a client config pins
    `VACANT_NAME=alice`, the operator *intends* for that identity to
    be used. Falling back to ephemeral would mean the client thinks it
    has a persistent vacant alice but every spawn is a fresh keypair —
    audit chains, reputation, and the entire responsibility-layer
    claim silently collapse. Better to fail loudly + point the
    operator at `vacant install <client>` or `vacant init`.
    """
    from vacant.cli.mcp_server import run_mcp_stdio_server
    from vacant.cli.server import build_serve_app

    # Resolve effective name. CLI flag > env var > implicit pick.
    explicit_name = name
    if explicit_name is None:
        env_name = os.environ.get("VACANT_NAME") or None
        if env_name:
            explicit_name = env_name

    persistent_name: str | None = None
    if explicit_name is not None:
        # Pfix5: strict mode. The operator named an identity — refuse
        # to silently swap in an ephemeral one.
        try:
            bundle = build_serve_app(explicit_name)
        except LocalVacantNotFound:
            sys.stderr.write(
                f"ERROR: vacant {explicit_name!r} not initialised at "
                f"{ls.vacant_dir(explicit_name)}\n"
                "\n"
                "  This is a runtime command — it doesn't create identity "
                "on the fly to avoid silently downgrading your audit chain.\n"
                "  Run one of:\n"
                f"    vacant install <client> --name {explicit_name}   "
                "# set up + register with the client config\n"
                f"    vacant init {explicit_name}                       "
                "# create the identity only (uses OS keyring)\n"
                f"    vacant init {explicit_name} --insecure-demo       "
                "# create the identity using plaintext key (CI / demo only)\n"
            )
            raise typer.Exit(code=2) from None
        form = bundle.form
        signing_key = bundle.signing_key
        replay_store = bundle.replay_store
        persistent_name = explicit_name
    else:
        try:
            n = ls.current_name()
        except LocalVacantNotFound:
            sys.stderr.write(
                "WARN: no local vacant on disk and no --name / "
                "$VACANT_NAME given; running an EPHEMERAL demo vacant. "
                "The keypair is fresh-per-launch and never persisted. "
                "Run `vacant init <name>` for a stable identity that "
                "survives process restarts. See SECURITY.md §Local key "
                "storage.\n"
            )
            from vacant.protocol import InMemoryReplayStore

            form, signing_key = _build_ephemeral_form()
            replay_store = InMemoryReplayStore()
        else:
            bundle = build_serve_app(n)
            form = bundle.form
            signing_key = bundle.signing_key
            replay_store = bundle.replay_store
            persistent_name = n

    # Pfix3 B7: persist signed SUBSTRATE_BORROWED + INFERENCE_EVENT
    # entries from sampling calls to the vacant's on-disk logbook
    # when we have a persistent identity. Ephemeral mode gets the
    # entries appended in memory but they're lost at process exit
    # (the keypair is also fresh-per-launch, so there's no audit
    # trail to preserve anyway).
    on_lb_change: Any = None
    persist_child: Any = None
    if persistent_name is not None:
        # Don't load a second Logbook here — form.logbook is already the
        # canonical on-disk logbook (loaded by build_serve_app). Sharing
        # one Logbook between sampling-side appends and spawn-side
        # appends keeps the hash chain consistent; otherwise whichever
        # tool saved last clobbered the other tool's entries.
        captured_name = persistent_name
        on_lb_change = lambda lb: ls.save_logbook(captured_name, lb)  # noqa: E731

        def persist_child(result: Any, child_name: str, _parent_name: str) -> None:
            """Persist a SpawnResult child to ~/.vacant/<child_name>/."""
            ls.persist_spawned_child(
                child_name,
                child_vacant_id=result.child.identity,
                child_signing_key=result.child_signing_key,
                child_logbook=result.child.logbook,
                parent_vacant_id=result.child.parent_id,
                state=result.child.runtime_state.value,
            )

    run_mcp_stdio_server(
        form=form,
        signing_key=signing_key,
        replay_store=replay_store,
        on_logbook_change=on_lb_change,
        parent_local_name=persistent_name,
        persist_spawned_child=persist_child,
    )


# -- install ------------------------------------------------------------------


@app.command("install")
def install_cmd(
    client: str = typer.Argument(
        ...,
        help=(
            "MCP client to register vacant with: claude-code | claude-desktop | "
            "cursor | windsurf | openclaw | hermes"
        ),
    ),
    config_path: str | None = typer.Option(
        None,
        "--config-path",
        help="Override the default config-file location for this client.",
    ),
    name: str = typer.Option(
        "alice",
        "--name",
        help=(
            "VACANT_NAME env var written into the registered MCP entry "
            "(picks which `~/.vacant/<name>/` identity the spawned `vacant mcp` "
            "uses; defaults to `alice`)."
        ),
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite an existing `vacant` entry in the client's config.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print what would be written without touching any file.",
    ),
    insecure_demo: bool = typer.Option(
        False,
        "--insecure-demo",
        help=(
            "When auto-creating identity, store the Ed25519 seed in "
            "plaintext key.json (mode 0600) instead of the OS keyring. "
            "Demo / CI only — never production responsibility-layer use."
        ),
    ),
    skip_init: bool = typer.Option(
        False,
        "--skip-init",
        help=(
            "Don't auto-create `~/.vacant/<name>/` if missing. Use when "
            "you'll bring your own identity (already-init'd elsewhere, "
            "or about to `vacant init` manually with custom flags)."
        ),
    ),
) -> None:
    """Register vacant as an MCP server with a local client. (Pfix5)

    One unified entry point — the README's per-client one-liners
    (OpenClaw / Hermes / Claude Desktop / Cursor / Windsurf) all
    collapse to:

        vacant install <client>

    Pfix5 contract:

    - **Setup-phase**: this command has side effects. By default it
      ALSO bootstraps `~/.vacant/<name>/` (running `vacant init` for
      you with OS-keyring storage) so the runtime `vacant mcp --name
      <name>` invocation that the client spawns later actually works.
    - Idempotent: re-running with no flags is a no-op when the
      identity and the config entry both exist. `--force` overwrites
      the config entry. Identity init is always skipped if the dir
      exists.
    - `--insecure-demo` opts into plaintext key storage (no keyring
      backend needed).
    - `--skip-init` tells the installer "I manage the identity";
      leaves `~/.vacant/<name>/` alone.
    """
    from pathlib import Path

    from vacant.cli.install import SUPPORTED_CLIENTS, install

    if client not in SUPPORTED_CLIENTS:
        typer.echo(
            f"error: unknown client {client!r}; supported: {', '.join(SUPPORTED_CLIENTS)}",
            err=True,
        )
        raise typer.Exit(code=2)

    cp = Path(config_path) if config_path else None
    msg = install(
        client,
        config_path=cp,
        name=name,
        force=force,
        dry_run=dry_run,
        insecure_demo=insecure_demo,
        skip_init=skip_init,
    )
    typer.echo(msg)
    if msg.startswith("ERROR") or "\nERROR" in msg:
        raise typer.Exit(code=1)


# -- demo ---------------------------------------------------------------------


@app.command("demo")
def demo_cmd(
    scenario: str,
    substrate: str = typer.Option(
        "mock",
        "--substrate",
        "-s",
        help=(
            "mock | deterministic | anthropic | ollama | openai | gemini | "
            "mistral | hermes | openclaw"
        ),
    ),
    seed: int | None = typer.Option(None, "--seed", help="override default seed"),
    tail: bool = typer.Option(
        False, "--tail", help="stream demo-store events to stdout instead of running"
    ),
    db_path: str | None = typer.Option(None, "--db", help="demo store path (default: var/demo.db)"),
) -> None:
    """Run a demo scenario end-to-end. (P7)

    Examples:
      vacant demo law_firm
      vacant demo law-firm --seed=42                # hyphen accepted
      vacant demo self_replication --substrate=anthropic
      vacant demo law_firm --tail                   # tail events from demo store
    """
    from vacant.mvp.demo import main as demo_main

    if tail:
        from vacant.mvp.demo_store import DemoStore

        with DemoStore(path=db_path) as store:
            for ev in store.read(scenario=scenario.replace("-", "_")):
                typer.echo(f"[{ev.ts:.1f}] {ev.kind}: {ev.payload}")
        return

    argv = ["--scenario", scenario.replace("-", "_"), "--substrate", substrate]
    if seed is not None:
        argv += ["--seed", str(seed)]
    if db_path is not None:
        argv += ["--db", db_path]
    raise SystemExit(demo_main(argv))


# -- registry (decentralised trust) -------------------------------------------
# Surface for the anti-tamper layers added in feat(registry): git anchor,
# OpenTimestamps, federated witness cosignatures. All subcommands assume a
# local SQLite registry DB (`--db`) for now — federated reads come later.


registry_app = typer.Typer(
    name="registry",
    help="Registry transparency-log operations (anchor, witness, OTS).",
    no_args_is_help=True,
)
app.add_typer(registry_app, name="registry")


def _open_local_store(db_path: str) -> Any:
    """Open a `RegistryStore` against `db_path` (file path or `:memory:`).

    Centralised because every registry subcommand needs identical wiring;
    keeping it inline would invite drift across `anchor` / `witness-cosign`
    / `ots-upgrade`.
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    from vacant.registry import RegistryStore

    url = db_path if "://" in db_path else f"sqlite+aiosqlite:///{db_path}"
    engine = create_async_engine(url)
    return engine, RegistryStore(engine)


@registry_app.command("anchor")
def registry_anchor_cmd(
    epoch_id: int = typer.Argument(..., help="Sealed epoch_id to anchor"),
    db: str = typer.Option(..., "--db", help="Registry SQLite path"),
    repo: str = typer.Option(..., "--repo", help="Local transparency-log git repo"),
    branch: str = typer.Option(
        "transparency-log", "--branch", help="Branch name in the transparency-log repo"
    ),
    remote: str | None = typer.Option(
        None, "--remote", help="Optional remote URL (`git push origin <branch>`)"
    ),
    push: bool = typer.Option(False, "--push", help="Attempt remote push after committing"),
) -> None:
    """Anchor a sealed Merkle epoch root to a git transparency log.

    The git repo is created if absent; `epochs/{epoch_id:08d}.json`
    receives the operator-signed root payload, and `git_commit_sha` is
    persisted back to the `MerkleEpoch` row.
    """

    async def _run() -> None:
        engine, store = _open_local_store(db)
        try:
            receipt = await store.anchor_epoch_to_git(
                epoch_id, repo_path=repo, branch=branch, remote_url=remote, push=push
            )
            typer.echo(
                json.dumps(
                    {
                        "epoch_id": receipt.epoch_id,
                        "commit_sha": receipt.commit_sha,
                        "branch": receipt.branch,
                        "remote_url": receipt.remote_url,
                        "pushed": receipt.pushed,
                    },
                    indent=2,
                )
            )
        finally:
            await engine.dispose()

    asyncio.run(_run())


@registry_app.command("witness-statement")
def registry_witness_statement_cmd(
    epoch_id: int = typer.Argument(..., help="Sealed epoch_id"),
    db: str = typer.Option(..., "--db", help="Registry SQLite path"),
) -> None:
    """Print the canonical witness statement bytes (hex) for `epoch_id`.

    A witness operator hashes + signs this with their Ed25519 key and
    returns the cosignature to the registry via `witness-cosign`.
    """

    async def _run() -> None:
        engine, store = _open_local_store(db)
        try:
            from vacant.registry import build_witness_statement

            epoch = await store.get_merkle_epoch(epoch_id)
            if epoch is None:
                typer.echo(f"error: epoch {epoch_id} not found", err=True)
                raise typer.Exit(code=2)
            statement = build_witness_statement(epoch)
            typer.echo(
                json.dumps(
                    {
                        "epoch_id": epoch_id,
                        "root_hex": epoch.root_hash.hex(),
                        "statement_hex": statement.hex(),
                    },
                    indent=2,
                )
            )
        finally:
            await engine.dispose()

    asyncio.run(_run())


@registry_app.command("witness-cosign")
def registry_witness_cosign_cmd(
    epoch_id: int = typer.Argument(..., help="Sealed epoch_id to cosign"),
    db: str = typer.Option(..., "--db", help="Registry SQLite path"),
    name: str | None = typer.Option(
        None, "--name", help="Local vacant whose key acts as the witness"
    ),
    witness_id: str = typer.Option(
        ..., "--witness-id", help="Witness operator label (free-form, recorded on the row)"
    ),
) -> None:
    """Sign + persist a witness cosignature on a sealed epoch.

    Uses the local vacant's Ed25519 key (from `~/.vacant/<name>/`) as
    the witness key. The cosignature is verified before insert, so
    `EpochWitness` rows are guaranteed cryptographically valid.
    """

    async def _run() -> None:
        from vacant.registry import issue_witness_cosignature

        local_name = _resolve_name(name)
        form = _residentform_for(local_name)
        signing_key = ls.load_signing_key(local_name)
        engine, store = _open_local_store(db)
        try:
            epoch = await store.get_merkle_epoch(epoch_id)
            if epoch is None:
                typer.echo(f"error: epoch {epoch_id} not found", err=True)
                raise typer.Exit(code=2)
            cos = issue_witness_cosignature(
                epoch=epoch,
                witness_id=witness_id,
                witness_signing_key=signing_key,
                witness_pubkey=form.identity.pubkey_bytes,
            )
            row = await store.record_witness_cosignature(epoch_id, cos)
            typer.echo(
                json.dumps(
                    {
                        "epoch_id": epoch_id,
                        "witness_id": row.witness_id,
                        "witness_pubkey_hex": row.witness_pubkey.hex(),
                        "cosigned_at": row.cosigned_at,
                    },
                    indent=2,
                )
            )
        finally:
            await engine.dispose()

    asyncio.run(_run())


@registry_app.command("witnesses")
def registry_witnesses_cmd(
    epoch_id: int = typer.Argument(..., help="Sealed epoch_id"),
    db: str = typer.Option(..., "--db", help="Registry SQLite path"),
) -> None:
    """List all witness cosignatures recorded for `epoch_id`."""

    async def _run() -> None:
        engine, store = _open_local_store(db)
        try:
            rows = await store.list_epoch_witnesses(epoch_id)
            typer.echo(
                json.dumps(
                    [
                        {
                            "witness_id": r.witness_id,
                            "witness_pubkey_hex": r.witness_pubkey.hex(),
                            "cosigned_at": r.cosigned_at,
                        }
                        for r in rows
                    ],
                    indent=2,
                )
            )
        finally:
            await engine.dispose()

    asyncio.run(_run())


@registry_app.command("verify-quorum")
def registry_verify_quorum_cmd(
    epoch_id: int = typer.Argument(..., help="Sealed epoch_id"),
    db: str = typer.Option(..., "--db", help="Registry SQLite path"),
    threshold: int = typer.Option(..., "--threshold", help="Required distinct witnesses (M)"),
    rootset: str = typer.Option(
        ...,
        "--rootset",
        help="Comma-separated hex witness pubkeys (the N candidates)",
    ),
) -> None:
    """Verify a quorum of witness cosignatures over an epoch root.

    Exits 0 iff ≥ `threshold` distinct valid signatures from the
    `rootset` are present on the epoch. This is the verifier surface a
    third-party auditor would call.
    """

    async def _run() -> None:
        from vacant.registry import WitnessRootSet, verify_witness_quorum

        engine, store = _open_local_store(db)
        try:
            epoch = await store.get_merkle_epoch(epoch_id)
            if epoch is None:
                typer.echo(f"error: epoch {epoch_id} not found", err=True)
                raise typer.Exit(code=2)
            keys = tuple(bytes.fromhex(k.strip()) for k in rootset.split(",") if k.strip())
            rs = WitnessRootSet(threshold=threshold, keys=keys)
            rows = await store.list_epoch_witnesses(epoch_id)
            ok = verify_witness_quorum(epoch=epoch, cosignatures=rows, rootset=rs)
            typer.echo(
                json.dumps(
                    {
                        "epoch_id": epoch_id,
                        "threshold": threshold,
                        "rootset_size": len(keys),
                        "witnesses_present": len(rows),
                        "quorum_satisfied": ok,
                    },
                    indent=2,
                )
            )
            if not ok:
                raise typer.Exit(code=1)
        finally:
            await engine.dispose()

    asyncio.run(_run())


# -- peer (remote vacant network membership) ---------------------------------


peer_app = typer.Typer(
    name="peer",
    help="Manage remote vacant network peers (add / list / remove / gossip).",
    no_args_is_help=True,
)
app.add_typer(peer_app, name="peer")


@peer_app.command("add")
def peer_add_cmd(
    label: str = typer.Argument(..., help="Unique label for this peer."),
    endpoint: str = typer.Argument(..., help="HTTP(S) base URL of the peer's A2A server."),
) -> None:
    """Remember a remote vacant network peer locally.

    The peer can be unreachable at add time — we only record the URL.
    `vacant peer gossip` is what actually contacts it.
    """
    from vacant.cli.peer_store import PeerStore, PeerStoreError

    try:
        entry = PeerStore().add(label, endpoint)
    except PeerStoreError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(json.dumps(entry.as_dict(), sort_keys=True))


@peer_app.command("list")
def peer_list_cmd() -> None:
    """Print every peer we know about, in insertion order."""
    from vacant.cli.peer_store import PeerStore

    peers = PeerStore().load()
    typer.echo(json.dumps([p.as_dict() for p in peers], indent=2, sort_keys=True))


@peer_app.command("remove")
def peer_remove_cmd(
    label: str = typer.Argument(..., help="Label of the peer to remove."),
) -> None:
    """Forget a previously-added peer."""
    from vacant.cli.peer_store import PeerStore, PeerStoreError

    try:
        entry = PeerStore().remove(label)
    except PeerStoreError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(json.dumps({"removed": entry.as_dict()}, sort_keys=True))


@peer_app.command("ping")
def peer_ping_cmd(
    label: str | None = typer.Option(None, "--label", help="Only ping this label."),
    timeout_s: float = typer.Option(5.0, "--timeout", help="Per-peer timeout in seconds."),
) -> None:
    """Hit each peer's `/health` endpoint and print whether it answered.

    Useful for diagnosing why `peer gossip` is skipping peers. No state
    is mutated — purely a connectivity check.
    """
    import asyncio as _asyncio

    import httpx

    from vacant.cli.peer_store import PeerStore

    peers = PeerStore().load()
    if label is not None:
        peers = [p for p in peers if p.label == label]
        if not peers:
            typer.echo(f"error: peer {label!r} not in store", err=True)
            raise typer.Exit(code=2)

    async def _ping_one(p: Any) -> dict[str, Any]:
        url = p.endpoint.rstrip("/") + "/health"
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as cli:
                r = await cli.get(url)
            return {
                "label": p.label,
                "endpoint": p.endpoint,
                "status": r.status_code,
                "body": r.json()
                if r.headers.get("content-type", "").startswith("application/json")
                else None,
                "reachable": r.status_code == 200,
            }
        except Exception as exc:
            return {
                "label": p.label,
                "endpoint": p.endpoint,
                "reachable": False,
                "error": repr(exc),
            }

    async def _run() -> list[dict[str, Any]]:
        return await _asyncio.gather(*(_ping_one(p) for p in peers))

    results = asyncio.run(_run())
    typer.echo(json.dumps(results, indent=2, sort_keys=True))
    if any(not r.get("reachable") for r in results):
        raise typer.Exit(code=1)


@peer_app.command("known-nodes")
def peer_known_nodes_cmd(
    url: str = typer.Option(
        "https://raw.githubusercontent.com/cosmopig/Vacant/main/docs/known-nodes.json",
        "--url",
        help="URL of the community-maintained known-nodes seed list.",
    ),
    timeout_s: float = typer.Option(10.0, "--timeout", help="HTTP timeout in seconds."),
) -> None:
    """Fetch the community-maintained seed-node list.

    Doesn't auto-add — prints the list so the operator can choose which
    seeds to `peer add` manually. The community list is just a JSON
    file in the repo: anyone can PR a seed, but no central party
    decides which seed *you* trust.
    """
    import httpx

    try:
        with httpx.Client(timeout=timeout_s) as cli:
            r = cli.get(url)
        r.raise_for_status()
        typer.echo(r.text)
    except Exception as exc:
        typer.echo(f"error: known-nodes fetch failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc


@registry_app.command("ots-upgrade")
def registry_ots_upgrade_cmd(
    epoch_id: int = typer.Argument(..., help="Sealed epoch_id with a pending OTS receipt"),
    db: str = typer.Option(..., "--db", help="Registry SQLite path"),
    proof_path: str = typer.Option(
        ..., "--proof", help="Path to a real `.ots` proof file produced by `ots stamp`"
    ),
) -> None:
    """Replace a pending OTS receipt with a real `.ots` proof.

    Operators run `ots stamp <root>` (or `ots upgrade <pending>.ots`)
    out-of-band, then pipe the resulting file in. The store records the
    real proof's BLAKE2b digest and stamps `ots_upgraded_at`.
    """

    async def _run() -> None:
        from pathlib import Path

        engine, store = _open_local_store(db)
        try:
            data = Path(proof_path).read_bytes()
            digest, upgraded_at = await store.record_ots_upgrade(epoch_id, upgraded_bytes=data)
            typer.echo(
                json.dumps(
                    {
                        "epoch_id": epoch_id,
                        "ots_proof_hash_hex": digest.hex(),
                        "ots_upgraded_at": upgraded_at,
                    },
                    indent=2,
                )
            )
        finally:
            await engine.dispose()

    asyncio.run(_run())


def main() -> None:
    """Console-script entrypoint declared in `pyproject.toml`."""
    app()


if __name__ == "__main__":
    main()
    sys.exit(0)
