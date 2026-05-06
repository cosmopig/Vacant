"""`vacant serve` runtime: build the FastAPI app from local-store state.

Split from `commands.py` so unit tests can import `build_serve_app`
directly without going through `subprocess.Popen`. The `serve` CLI
command is a thin wrapper that hands the result to `uvicorn.run`.

The behaviour callback is intentionally minimal — it echoes the request
text back, signed by the vacant's own key. P7 demos / production
deployments swap in a substrate-driven behaviour by re-using the
underlying `build_a2a_app` directly. For the A2/A4 acceptance tests
("vacant serve + vacant call from another shell completes a real network
roundtrip") echo is enough — what's load-bearing is that the response
envelope verifies under the vacant's pubkey on the wire.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import FastAPI

from vacant.cli import local_store as ls
from vacant.core.crypto import SigningKey
from vacant.core.types import (
    BehaviorBundle,
    CapabilityCard,
    Logbook,
    ResidentForm,
    SubstrateSpec,
    VacantId,
    VacantState,
)
from vacant.protocol import (
    A2AMessage,
    A2APart,
    InMemoryReplayStore,
    VacantEnvelope,
    build_a2a_app,
)

__all__ = [
    "ServeBundle",
    "build_serve_app",
    "echo_behavior",
]


BehaviorFn = Callable[[VacantEnvelope], Awaitable[A2AMessage]]


@dataclass
class ServeBundle:
    """The four objects `vacant serve` produces from local-store state."""

    app: FastAPI
    form: ResidentForm
    signing_key: SigningKey
    replay_store: InMemoryReplayStore


async def echo_behavior(env: VacantEnvelope) -> A2AMessage:
    """Echo the incoming text back, prefixed with the vacant's short id.

    Default behaviour for `vacant serve` — keeps the acceptance tests
    self-contained (no LLM key required). Real deployments pass a
    different `behavior` to `build_serve_app`.
    """
    text = " ".join(p.text for p in env.payload.parts)
    short = env.to_vacant_id.short()
    return A2AMessage(
        role="ROLE_AGENT",
        parts=[A2APart(text=f"echo from {short}: {text}")],
    )


def build_serve_app(
    name: str,
    *,
    behavior: BehaviorFn | None = None,
    endpoint: str | None = None,
) -> ServeBundle:
    """Hydrate a `vacant serve` FastAPI app from `~/.vacant/<name>/`.

    `endpoint` overrides the meta endpoint when set (uvicorn assigns
    the bind address but the capability card needs a publishable URL).
    """
    meta = ls.load_meta(name)
    sk = ls.load_signing_key(name)
    lb = ls.load_logbook(name)
    vid = VacantId(pubkey_bytes=bytes.fromhex(meta.vacant_id_hex))

    spec = SubstrateSpec(allowed_substrates=["mock"])
    bundle = BehaviorBundle(system_prompt="vacant serve")

    effective_endpoint = endpoint or meta.endpoint
    cap_text = meta.capability_text or "echo"
    card = CapabilityCard(
        vacant_id=vid,
        capability_text=cap_text,
        substrate_spec=spec,
        endpoint=effective_endpoint,
    ).signed(sk)

    form = ResidentForm(
        identity=vid,
        logbook=lb if lb.entries else Logbook(),
        behavior_bundle=bundle,
        substrate_spec=spec,
        runtime_state=VacantState(meta.state),
        capability_card=card,
    )

    replay_store = InMemoryReplayStore()
    app = build_a2a_app(
        self_form=form,
        self_signing_key=sk,
        behavior=behavior or echo_behavior,
        replay_store=replay_store,
    )

    @app.get("/card")
    async def get_card() -> dict[str, object]:
        from vacant.protocol.capability_card import serialize as serialize_card

        return {
            "vacant_id": vid.hex(),
            "capability_text": cap_text,
            "endpoint": effective_endpoint,
            "halo_version": card.halo_version,
            "capability_card_blob_hex": serialize_card(card).hex(),
        }

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {
            "vacant_id": vid.hex(),
            "state": form.runtime_state.value,
            "name": name,
        }

    return ServeBundle(app=app, form=form, signing_key=sk, replay_store=replay_store)
