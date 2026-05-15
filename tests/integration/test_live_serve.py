"""A2 acceptance: `vacant serve` real-network round trip.

Spawns the CLI as a subprocess and posts a signed envelope over real
HTTP. Verifies the response envelope is signed by the served vacant's
key. This is the test the live-network claim rests on — earlier
in-process tests (`test_a2a_full.py`) used `httpx.ASGITransport` which
short-circuits the network.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from vacant.cli import local_store as ls
from vacant.core.crypto import keygen
from vacant.core.types import VacantId
from vacant.protocol.envelope import (
    A2AMessage,
    A2APart,
    VacantEnvelope,
    from_a2a_jsonrpc,
    to_a2a_jsonrpc,
)

pytestmark = pytest.mark.slow


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return int(port)


def _wait_health(port: int, timeout: float = 30.0) -> None:
    """Wait up to `timeout` seconds for `vacant serve` to bind.

    Cold-start time on this codebase is ~6-7 seconds due to FastAPI +
    uvicorn + module imports on a fresh Python interpreter. The
    previous 8-second cap was a flaky razor's edge that produced 6
    pre-existing test failures on otherwise-healthy machines. 30s is
    a comfortable buffer that still fails fast when something is
    actually wrong.
    """
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
    raise RuntimeError(f"vacant serve did not become healthy on :{port}: {last!r}")


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("VACANT_HOME", str(home))
    return home


@pytest.fixture
def served_vacant(isolated_home: Path) -> Iterator[tuple[str, int, VacantId]]:
    """Init a local vacant, spawn `vacant serve`, yield (name, port, vid)."""
    name = "alice"
    # Subprocesses can't share the in-process fake keyring; use the
    # plaintext fallback so the spawned `vacant serve` can load the seed.
    ls.init_vacant(name, insecure_demo=True)
    port = _free_port()
    env = {**os.environ, "VACANT_HOME": str(isolated_home)}
    proc = subprocess.Popen(  # noqa: S603
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
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        _wait_health(port)
        meta = ls.load_meta(name)
        vid = VacantId(pubkey_bytes=bytes.fromhex(meta.vacant_id_hex))
        yield name, port, vid
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def _build_caller(name: str = "bob") -> tuple[Any, VacantId]:
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    return sk, vid


@pytest.mark.asyncio
async def test_serve_health_endpoint(
    served_vacant: tuple[str, int, VacantId],
) -> None:
    name, port, vid = served_vacant
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as ac:
        r = await ac.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == name
    assert data["vacant_id"] == vid.hex()


@pytest.mark.asyncio
async def test_serve_card_endpoint_returns_signed_blob(
    served_vacant: tuple[str, int, VacantId],
) -> None:
    _name, port, vid = served_vacant
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as ac:
        r = await ac.get("/card")
    assert r.status_code == 200
    data = r.json()
    assert data["vacant_id"] == vid.hex()
    assert data["capability_text"]
    blob_hex = data["capability_card_blob_hex"]
    assert isinstance(blob_hex, str) and len(blob_hex) > 0
    # Blob deserializes back into a card that verifies under vid.
    from vacant.protocol.capability_card import deserialize as deserialize_card

    card = deserialize_card(bytes.fromhex(blob_hex))
    assert card.vacant_id.hex() == vid.hex()
    assert card.verify() is True


@pytest.mark.asyncio
async def test_serve_signed_round_trip(
    served_vacant: tuple[str, int, VacantId],
) -> None:
    """Real HTTP roundtrip: signed request, signed response that verifies."""
    _name, port, target_vid = served_vacant
    caller_sk, caller_vid = _build_caller()

    request = VacantEnvelope(
        from_vacant_id=caller_vid,
        to_vacant_id=target_vid,
        sequence_no=1,
        timestamp=datetime.now(UTC),
        payload=A2AMessage(role="ROLE_USER", parts=[A2APart(text="please echo")]),
        idempotency_key="t-001",
    ).signed(caller_sk)

    body = to_a2a_jsonrpc(request)
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=5.0) as ac:
        r = await ac.post("/a2a/message/send", json=body)
    assert r.status_code == 200, r.text
    raw: dict[str, Any] = r.json()
    # Re-wrap as a `message/send` request so from_a2a_jsonrpc can parse it.
    wrapped = {
        "jsonrpc": "2.0",
        "id": "rsp",
        "method": "message/send",
        "params": {"message": raw["result"]["message"]},
    }
    response_env = from_a2a_jsonrpc(wrapped)
    # Response signed by the served vacant.
    assert response_env.from_vacant_id.hex() == target_vid.hex()
    assert response_env.verify(target_vid.verify_key()) is True
    # Echo content surfaces.
    assert "please echo" in response_env.payload.parts[0].text


@pytest.mark.asyncio
async def test_serve_rejects_bad_jsonrpc(
    served_vacant: tuple[str, int, VacantId],
) -> None:
    _name, port, _vid = served_vacant
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=5.0) as ac:
        r = await ac.post("/a2a/message/send", json={"hello": "world"})
    assert r.status_code == 400
    assert "jsonrpc" in r.text.lower() or "method" in r.text.lower()


def test_serve_help_lists_options() -> None:
    """`vacant serve --help` advertises the documented flags.

    Uses `CliRunner` rather than `subprocess.run` because Typer's
    rich-formatted help wraps long lines and inserts ANSI escapes when
    stdout is detected as a terminal (which CI sometimes is, depending
    on runner). `CliRunner` invokes the command in-process with stable
    plain output.
    """
    from typer.testing import CliRunner

    from vacant.cli import app

    result = CliRunner().invoke(app, ["serve", "--help"])
    assert result.exit_code == 0, result.stdout
    out = result.stdout
    for flag in ("port", "host", "name", "mcp"):
        # Substring without dashes — Typer can wrap "--port" across two
        # lines under tight terminal widths, which breaks `"--port" in out`.
        assert flag in out


# Acquire local_store's keygen to keep flake8 happy when subprocess fixture
# generates the vacant; the CLI does this via `init` already.
_ = (json, keygen)
