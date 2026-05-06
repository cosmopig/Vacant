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
def init_cmd(name: str) -> None:
    """Create a fresh keypair + seed logbook for `name`. (P2)

    Writes `~/.vacant/<name>/{key.json,logbook.jsonl,meta.json}` with
    file mode 0600 on the key. Subsequent commands (`status`,
    `heartbeat`, `publish`) operate on this directory.
    """
    try:
        vid, _sk = ls.init_vacant(name)
    except ls.LocalVacantExists:
        typer.echo(f"error: local vacant {name!r} already exists", err=True)
        raise typer.Exit(code=1) from None
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
    base_model: str,
    base_model_family: str,
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
        body = {
            "capability_card_blob_hex": blob_hex,
            "runtime_state": "ACTIVE",
            "visibility": visibility.value,
            "base_model": base_model,
            "base_model_family": base_model_family,
            "event_ts_ms": ts_ms,
            "event_actor_seq": actor_seq,
            "event_idempotency_key": idempotency_key,
            "event_signature_hex": signature.hex(),
        }
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
    base_model: str = typer.Option("unknown", "--base-model"),
    base_model_family: str = typer.Option("unknown", "--base-model-family"),
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

        from vacant.protocol.capability_card import deserialize as deserialize_card
        from vacant.protocol.dispatch import call_local, make_httpx_transport
        from vacant.protocol.envelope import A2AMessage, A2APart

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
        result = await call_local(
            target_card=target_card,
            requester=form,
            requester_signing_key=sk,
            payload=A2AMessage(role="ROLE_USER", parts=[A2APart(text=text)]),
            transport=transport,
        )
        return {
            "target": target_card.vacant_id.hex(),
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
) -> None:
    """Start an HTTP A2A server for the local vacant. (P6)

    The server listens on `host:port` and accepts inbound A2A
    `message/send` requests at `/a2a/message/send`. The default
    behaviour callback echoes the request text back, signed by the
    vacant's own key — sufficient for the live-network acceptance test.

    `--mcp` additionally launches an MCP stdio server in a worker
    thread. This is what closes the "嫁接到客戶端" thesis claim: the
    same vacant accepts both A2A HTTP and MCP stdio simultaneously.
    """
    import uvicorn

    from vacant.cli.server import build_serve_app

    n = _resolve_name(name)
    bundle = build_serve_app(n, endpoint=endpoint)

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

    typer.echo(
        json.dumps(
            {
                "name": n,
                "vacant_id": bundle.form.identity.hex(),
                "host": host,
                "port": port,
                "mcp": mcp,
            },
            sort_keys=True,
        )
    )
    uvicorn.run(bundle.app, host=host, port=port, log_level="warning")


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


def main() -> None:
    """Console-script entrypoint declared in `pyproject.toml`."""
    app()


if __name__ == "__main__":
    main()
    sys.exit(0)
