"""Integration: vacant_delegate_a2a — vacant-to-vacant over A2A HTTP.

Phase 8.1 of the technical.html implementation: children must talk
to each other via signed A2A envelopes over HTTP, not by routing
through the parent's MCP process. This test spawns alice + a child,
boots the child's own ``vacant serve`` daemon on a free port, then
calls ``vacant_delegate_a2a`` against alice's MCP server. The child
runs in its own subprocess, signs its response with its own key, and
the chain ends up on disk in alice's signed A2A_DELEGATION_COMPLETED
entry — the proof that the hop was a real HTTP A2A round-trip, not
an in-process shortcut.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from vacant.cli import local_store as ls
from vacant.core.types import VacantId

pytestmark = pytest.mark.slow


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _stdio_params(name: str, home: Path) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "vacant.cli.mcp_serve_test_runner", name],
        env={**os.environ, "VACANT_HOME": str(home)},
    )


def _wait_health(url: str, timeout_s: float = 30.0) -> None:
    deadline = time.time() + timeout_s
    last_exc: Exception | None = None
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=1.0)
            if r.status_code == 200:
                return
        except Exception as exc:
            last_exc = exc
        time.sleep(0.2)
    raise RuntimeError(f"child serve never became healthy at {url}: {last_exc}")


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("VACANT_HOME", str(home))
    return home


@pytest.mark.asyncio
async def test_a2a_delegate_via_http(isolated_home: Path) -> None:
    ls.init_vacant("alice", insecure_demo=True)
    alice_meta = ls.load_meta("alice")
    alice_vid = VacantId(pubkey_bytes=bytes.fromhex(alice_meta.vacant_id_hex))

    # 1. Spawn a child through alice's MCP server (records SPAWN on alice,
    #    BIRTH on child, parent_id chained).
    params = _stdio_params("alice", isolated_home)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            spawn = await session.call_tool(
                "vacant_spawn",
                arguments={
                    "policy_mutation": "translate verbatim",
                    "child_name_hint": "trans",
                },
            )
            spawn_body = json.loads(spawn.content[0].text)  # type: ignore[union-attr]
            assert spawn_body["ok"]
            child_name = spawn_body["child_name"]
            child_vid_hex = spawn_body["child_vacant_id_hex"]
            child_vid = VacantId(pubkey_bytes=bytes.fromhex(child_vid_hex))

    # 2. Boot child's own A2A serve subprocess on a free port.
    port = _free_port()
    child_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "vacant.cli",
            "serve",
            "--name",
            child_name,
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        env={**os.environ, "VACANT_HOME": str(isolated_home)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        _wait_health(f"http://127.0.0.1:{port}/health")

        # 3. Child's meta.endpoint must have been written by `serve_cmd`.
        child_meta = ls.load_meta(child_name)
        assert child_meta.endpoint == f"http://127.0.0.1:{port}"

        # 4. Call vacant_delegate_a2a — runs alice→child HTTP A2A.
        params2 = _stdio_params("alice", isolated_home)
        async with stdio_client(params2) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                res = await session.call_tool(
                    "vacant_delegate_a2a",
                    arguments={"child_name": child_name, "task": "say hello"},
                )

        body = json.loads(res.content[0].text)  # type: ignore[union-attr]
        assert body.get("ok") is True, body
        assert body["transport"] == "a2a-http"
        assert body["child_endpoint"] == f"http://127.0.0.1:{port}"
        # Child's default echo behavior round-trips the text.
        assert "say hello" in body["answer"]

        # 5. Alice's logbook gained a signed A2A_DELEGATION_COMPLETED.
        alice_lb = ls.load_logbook("alice")
        kinds = [e.kind for e in alice_lb.entries]
        assert "A2A_DELEGATION_COMPLETED" in kinds
        entry = next(e for e in alice_lb.entries if e.kind == "A2A_DELEGATION_COMPLETED")
        assert entry.payload["child_name"] == child_name
        assert entry.payload["child_id"] == child_vid_hex
        assert entry.payload["transport"] == "a2a-http"
        assert entry.payload["child_endpoint"] == f"http://127.0.0.1:{port}"
        assert alice_lb.verify_chain(alice_vid.verify_key())

        # 6. Child's logbook gained whatever its own A2A behavior writes
        #    (default is to NOT touch the logbook on echo; replay store
        #    advances but no append). At minimum BIRTH is still there
        #    and chain re-verifies.
        child_lb = ls.load_logbook(child_name)
        assert any(e.kind == "BIRTH" for e in child_lb.entries)
        assert child_lb.verify_chain(child_vid.verify_key())

    finally:
        child_proc.terminate()
        try:
            child_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child_proc.kill()
            child_proc.wait()
