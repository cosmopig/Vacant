"""In-process unit tests for `vacant.cli.server` + `vacant.cli.mcp_server`.

The integration tests in `tests/integration/test_live_serve.py` and
`test_mcp_external_client.py` exercise these modules through
`subprocess.Popen`, which means they don't contribute to coverage. The
tests here import the same code in-process so the coverage gate sees
it. They aren't redundant — the integration tests still verify the
real-network plumbing — but they let us assert the wiring without
paying for a subprocess.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from vacant.cli import local_store as ls
from vacant.cli.mcp_server import build_fastmcp_server
from vacant.cli.server import build_serve_app, echo_behavior
from vacant.protocol.envelope import (
    A2AMessage,
    A2APart,
    VacantEnvelope,
)


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("VACANT_HOME", str(home))
    monkeypatch.delenv("VACANT_NAME", raising=False)
    return home


# --- cli.server -------------------------------------------------------------


def test_build_serve_app_health_and_card_endpoints() -> None:
    ls.init_vacant("alice")
    bundle = build_serve_app("alice")
    assert bundle.form.identity.hex() == ls.load_meta("alice").vacant_id_hex

    async def _go() -> None:
        async with AsyncClient(
            transport=ASGITransport(app=bundle.app), base_url="http://test"
        ) as ac:
            r = await ac.get("/health")
            assert r.status_code == 200
            assert r.json()["name"] == "alice"
            r = await ac.get("/card")
            assert r.status_code == 200
            data = r.json()
            assert data["vacant_id"] == bundle.form.identity.hex()
            assert data["capability_text"] == "echo"
            assert isinstance(data["capability_card_blob_hex"], str)

    asyncio.run(_go())


def test_build_serve_app_endpoint_override() -> None:
    ls.init_vacant("alice")
    bundle = build_serve_app("alice", endpoint="https://override.test/a2a")

    async def _go() -> None:
        async with AsyncClient(
            transport=ASGITransport(app=bundle.app), base_url="http://test"
        ) as ac:
            r = await ac.get("/card")
            assert r.json()["endpoint"] == "https://override.test/a2a"

    asyncio.run(_go())


def test_build_serve_app_uses_meta_capability_text() -> None:
    """When meta.capability_text is set, the card carries it."""
    ls.init_vacant("alice")
    meta = ls.load_meta("alice")
    meta.capability_text = "translate"
    meta.endpoint = "https://alice.test/a2a"
    ls.save_meta("alice", meta)
    bundle = build_serve_app("alice")

    async def _go() -> None:
        async with AsyncClient(
            transport=ASGITransport(app=bundle.app), base_url="http://test"
        ) as ac:
            r = await ac.get("/card")
            assert r.json()["capability_text"] == "translate"

    asyncio.run(_go())


@pytest.mark.asyncio
async def test_echo_behavior_returns_signed_text() -> None:
    """The default behavior echoes user text under ROLE_AGENT."""
    from vacant.core.crypto import keygen
    from vacant.core.types import VacantId

    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    target_sk, target_vk = keygen()
    target_vid = VacantId.from_verify_key(target_vk)

    env = VacantEnvelope(
        from_vacant_id=vid,
        to_vacant_id=target_vid,
        sequence_no=1,
        timestamp=__import__("datetime").datetime.now(__import__("datetime").UTC),
        payload=A2AMessage(parts=[A2APart(text="hello")]),
    ).signed(sk)
    out = await echo_behavior(env)
    assert out.role == "ROLE_AGENT"
    assert "hello" in out.parts[0].text
    _ = target_sk  # unused but kept for symmetry


# --- cli.mcp_server ---------------------------------------------------------


def test_build_fastmcp_server_registers_four_tools() -> None:
    ls.init_vacant("alice")
    bundle = build_serve_app("alice")
    mcp = build_fastmcp_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
        replay_store=bundle.replay_store,
    )
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert names == {
        "vacant_describe",
        "vacant_call",
        "vacant_call_with_sampling",
        "vacant_spawn",
    }


def test_build_fastmcp_server_default_replay_store() -> None:
    """Omitting `replay_store` falls back to a fresh InMemoryReplayStore."""
    ls.init_vacant("alice")
    bundle = build_serve_app("alice")
    mcp = build_fastmcp_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
    )
    tools = asyncio.run(mcp.list_tools())
    assert len(tools) == 4


def test_persist_spawned_child_refuses_existing_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The persist helper must surface a clear LocalVacantExists when the
    target directory already exists, instead of silently overwriting and
    breaking the chain."""
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    ls.init_vacant("alice", insecure_demo=True)
    bundle = build_serve_app("alice")
    from vacant.runtime.spawn import spawn_clone_with_mutation

    result = spawn_clone_with_mutation(bundle.form, bundle.signing_key, policy_mutation="x")
    ls.persist_spawned_child(
        "alice__d1__first",
        child_vacant_id=result.child.identity,
        child_signing_key=result.child_signing_key,
        child_logbook=result.child.logbook,
        parent_vacant_id=result.child.parent_id,
    )
    # Second call with the same name must raise.
    with pytest.raises(ls.LocalVacantExists):
        ls.persist_spawned_child(
            "alice__d1__first",
            child_vacant_id=result.child.identity,
            child_signing_key=result.child_signing_key,
            child_logbook=result.child.logbook,
            parent_vacant_id=result.child.parent_id,
        )


def test_vacant_spawn_refuses_when_no_parent_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """vacant_spawn requires a persistent parent; ephemeral mode must surface a
    clear error rather than spawn an unattributable orphan."""
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    ls.init_vacant("alice", insecure_demo=True)
    bundle = build_serve_app("alice")
    mcp = build_fastmcp_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
        # parent_local_name + persist_spawned_child intentionally omitted
    )
    out = asyncio.run(mcp.call_tool("vacant_spawn", {"policy_mutation": "x"}))
    payload = out[0] if isinstance(out, tuple) else out
    text = payload[0].text if hasattr(payload[0], "text") else str(payload[0])
    assert "vacant_spawn requires a persistent parent identity" in text


def test_vacant_spawn_creates_child_directly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise the vacant_spawn tool body without an MCP subprocess so the
    happy + persistence path lands inside the unit-test coverage window."""
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    ls.init_vacant("alice", insecure_demo=True)
    bundle = build_serve_app("alice")

    captured: dict[str, object] = {}

    def _persist(result: object, child_name: str, parent_name: str) -> None:
        captured["result"] = result
        captured["child_name"] = child_name
        captured["parent_name"] = parent_name
        ls.persist_spawned_child(
            child_name,
            child_vacant_id=result.child.identity,  # type: ignore[attr-defined]
            child_signing_key=result.child_signing_key,  # type: ignore[attr-defined]
            child_logbook=result.child.logbook,  # type: ignore[attr-defined]
            parent_vacant_id=result.child.parent_id,  # type: ignore[attr-defined]
            state=result.child.runtime_state.value,  # type: ignore[attr-defined]
        )

    saved_logbooks: list[object] = []
    mcp = build_fastmcp_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
        replay_store=bundle.replay_store,
        parent_local_name="alice",
        persist_spawned_child=_persist,
        on_logbook_change=lambda lb: saved_logbooks.append(lb),
    )
    out = asyncio.run(
        mcp.call_tool(
            "vacant_spawn",
            {"policy_mutation": "always quote the source", "child_name_hint": "quote"},
        )
    )
    payload = out[0] if isinstance(out, tuple) else out
    import json as _json

    text = payload[0].text if hasattr(payload[0], "text") else str(payload[0])
    body = _json.loads(text)
    assert body["ok"] is True
    assert body["path"] == "D1"
    assert body["child_name"].startswith("alice__quote__")
    assert "result" in captured
    assert "parent_name" in captured and captured["parent_name"] == "alice"
    # The parent's SPAWN entry should have triggered an on_logbook_change.
    assert saved_logbooks, "expected on_logbook_change to fire after spawn"


def test_vacant_spawn_surfaces_persist_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure inside the persist callback must come back as
    ``{"error": "persist_failed: ..."}`` so an LLM caller sees a textual
    reason instead of an MCP-level crash."""
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    ls.init_vacant("alice", insecure_demo=True)
    bundle = build_serve_app("alice")

    def _persist(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    mcp = build_fastmcp_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
        replay_store=bundle.replay_store,
        parent_local_name="alice",
        persist_spawned_child=_persist,
    )
    out = asyncio.run(mcp.call_tool("vacant_spawn", {"policy_mutation": "x"}))
    payload = out[0] if isinstance(out, tuple) else out
    text = payload[0].text if hasattr(payload[0], "text") else str(payload[0])
    assert "persist_failed: disk full" in text


def test_vacant_spawn_surfaces_spawn_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty policy_mutation must come back as `{"error": "spawn_failed: ..."}`,
    not raise a Python exception across the wire."""
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    ls.init_vacant("alice", insecure_demo=True)
    bundle = build_serve_app("alice")

    def _persist(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("persist must not be called on a failed spawn")

    mcp = build_fastmcp_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
        replay_store=bundle.replay_store,
        parent_local_name="alice",
        persist_spawned_child=_persist,
    )
    out = asyncio.run(mcp.call_tool("vacant_spawn", {"policy_mutation": "   "}))
    payload = out[0] if isinstance(out, tuple) else out
    text = payload[0].text if hasattr(payload[0], "text") else str(payload[0])
    assert "spawn_failed" in text


# --- cli.mcp_serve_test_runner ---------------------------------------------


def test_mcp_serve_test_runner_no_args_returns_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from vacant.cli.mcp_serve_test_runner import main

    rc = main([])
    assert rc == 2
    captured = capsys.readouterr()
    assert "usage" in captured.err.lower()


# --- cli.serve_cmd (smoke + error paths) -----------------------------------


def test_serve_cmd_exits_when_local_store_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`vacant serve` errors clean when no local vacant exists."""
    from typer.testing import CliRunner

    from vacant.cli import app

    runner = CliRunner()
    r = runner.invoke(app, ["serve", "--name", "ghost"])
    # build_serve_app raises LocalVacantNotFound; Typer surfaces it as exit 1.
    assert r.exit_code != 0


def test_serve_cmd_invokes_uvicorn_with_built_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Smoke-test the serve command path without actually binding a port.

    Patches `uvicorn.run` to a no-op so the CLI command exits as soon as
    the app is built and the JSON status line is emitted.
    """
    from typer.testing import CliRunner

    from vacant.cli import app

    ls.init_vacant("alice")
    seen: dict[str, object] = {}

    def fake_uvicorn_run(app_arg: object, **kwargs: object) -> None:
        seen["app"] = app_arg
        seen["kwargs"] = kwargs

    import uvicorn

    monkeypatch.setattr(uvicorn, "run", fake_uvicorn_run)

    runner = CliRunner()
    r = runner.invoke(app, ["serve", "--port", "9999", "--name", "alice"])
    assert r.exit_code == 0, r.stdout
    assert seen["app"] is not None
    kwargs = seen["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["port"] == 9999
    assert kwargs["host"] == "127.0.0.1"
