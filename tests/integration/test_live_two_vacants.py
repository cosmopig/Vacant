"""A4 acceptance: two vacants, real network, signed round trip.

Spawns two `vacant serve` subprocesses on separate ports, then has
A directly call B (and vice versa) over real HTTP via `call_local`.
Asserts that both response envelopes verify under the served keys
and that B's logbook chain advanced (visible by re-issuing a second
call and getting sequence_no=2 on the response chain).

This is what the thesis defense calls "live two-vacant network": no
ASGITransport, no in-process short-circuit, just two CPython processes
talking to each other through the kernel's TCP stack.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from vacant.cli import local_store as ls
from vacant.core.types import VacantId
from vacant.protocol import (
    A2AMessage,
    A2APart,
    call_local,
    make_httpx_transport,
)
from vacant.protocol.capability_card import deserialize as deserialize_card

pytestmark = pytest.mark.slow


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return int(port)


def _wait_health(port: int, timeout: float = 8.0) -> None:
    deadline = time.time() + timeout
    last: Exception | None = None
    while time.time() < deadline:
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/health", timeout=1.0)
            if r.status_code == 200:
                return
        except Exception as exc:
            last = exc
        time.sleep(0.1)
    raise RuntimeError(f"vacant serve not healthy on :{port}: {last!r}")


def _spawn_vacant(name: str, port: int, home: Path) -> subprocess.Popen[bytes]:
    env = {**os.environ, "VACANT_HOME": str(home)}
    endpoint = f"http://127.0.0.1:{port}/a2a/message/send"
    return subprocess.Popen(  # noqa: S603
        [
            sys.executable,
            "-m",
            "vacant.cli",
            "serve",
            "--port",
            str(port),
            "--host",
            "127.0.0.1",
            "--name",
            name,
            "--endpoint",
            endpoint,
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("VACANT_HOME", str(home))
    return home


@pytest.fixture
def two_vacants(
    isolated_home: Path,
) -> Iterator[tuple[tuple[str, int, VacantId], tuple[str, int, VacantId]]]:
    ls.init_vacant("alice", insecure_demo=True)  # subprocess can't share fake keyring
    ls.init_vacant("bob", insecure_demo=True)  # subprocess can't share fake keyring
    a_meta = ls.load_meta("alice")
    b_meta = ls.load_meta("bob")
    a_vid = VacantId(pubkey_bytes=bytes.fromhex(a_meta.vacant_id_hex))
    b_vid = VacantId(pubkey_bytes=bytes.fromhex(b_meta.vacant_id_hex))

    a_port = _free_port()
    b_port = _free_port()
    a_proc = _spawn_vacant("alice", a_port, isolated_home)
    b_proc = _spawn_vacant("bob", b_port, isolated_home)
    try:
        _wait_health(a_port)
        _wait_health(b_port)
        yield (("alice", a_port, a_vid), ("bob", b_port, b_vid))
    finally:
        for p in (a_proc, b_proc):
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()


@pytest.mark.asyncio
async def test_a_calls_b_over_real_network(
    two_vacants: tuple[tuple[str, int, VacantId], tuple[str, int, VacantId]],
    isolated_home: Path,
) -> None:
    a, b = two_vacants
    _a_name, _a_port, _a_vid = a
    _b_name, b_port, b_vid = b

    # Fetch B's signed capability card from B's /card endpoint.
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(f"http://127.0.0.1:{b_port}/card")
    assert r.status_code == 200
    b_card = deserialize_card(bytes.fromhex(r.json()["capability_card_blob_hex"]))
    assert b_card.vacant_id.hex() == b_vid.hex()
    assert b_card.endpoint and "127.0.0.1" in b_card.endpoint

    # Build a ResidentForm for A (caller) from its on-disk state.
    from vacant.cli.server import build_serve_app

    a_bundle = build_serve_app("alice")
    a_form = a_bundle.form
    a_sk = a_bundle.signing_key

    transport = make_httpx_transport(timeout=5.0)
    payload = A2AMessage(role="ROLE_USER", parts=[A2APart(text="hello B from A")])
    result = await call_local(
        target_card=b_card,
        requester=a_form,
        requester_signing_key=a_sk,
        payload=payload,
        transport=transport,
    )

    # Response envelope is signed by B and verifies under B's pubkey.
    assert result.response_envelope.from_vacant_id.hex() == b_vid.hex()
    assert result.response_envelope.verify(b_vid.verify_key()) is True
    response_text = "".join(p.text for p in result.response_envelope.payload.parts)
    assert "hello B from A" in response_text

    # Second call advances the response chain (B's seq → 2).
    result2 = await call_local(
        target_card=b_card,
        requester=a_form,
        requester_signing_key=a_sk,
        payload=A2AMessage(role="ROLE_USER", parts=[A2APart(text="follow-up")]),
        transport=transport,
        sequence_no=2,
        prev_envelope_hash=result.request_envelope.compute_hash(),
    )
    assert result2.response_envelope.sequence_no == 2
    assert result2.response_envelope.verify(b_vid.verify_key()) is True


@pytest.mark.asyncio
async def test_b_calls_a_over_real_network(
    two_vacants: tuple[tuple[str, int, VacantId], tuple[str, int, VacantId]],
) -> None:
    """Reverse direction: B → A. Confirms the live network is bi-directional."""
    a, b = two_vacants
    _a_name, a_port, a_vid = a
    _b_name, _b_port, _b_vid = b

    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(f"http://127.0.0.1:{a_port}/card")
    a_card = deserialize_card(bytes.fromhex(r.json()["capability_card_blob_hex"]))

    from vacant.cli.server import build_serve_app

    b_bundle = build_serve_app("bob")
    transport = make_httpx_transport(timeout=5.0)
    result = await call_local(
        target_card=a_card,
        requester=b_bundle.form,
        requester_signing_key=b_bundle.signing_key,
        payload=A2AMessage(role="ROLE_USER", parts=[A2APart(text="hi A from B")]),
        transport=transport,
    )
    assert result.response_envelope.from_vacant_id.hex() == a_vid.hex()
    assert result.response_envelope.verify(a_vid.verify_key()) is True


_ = Any  # silence unused-import lint
