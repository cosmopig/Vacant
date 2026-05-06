"""HTTP-path coverage for `vacant.cli.commands`.

The local-disk subcommands are tested in `test_cli.py`. This file covers
the three subcommands that talk to a registry over HTTP (`publish`,
`lineage`, `call`) and the surrounding error paths. We patch
`httpx.AsyncClient` so any client constructed by the CLI uses an
``httpx.MockTransport`` that we route by URL path. Both the registry
HTTP endpoints and the dispatch transport target endpoint go through
the same handler.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from vacant.cli import app
from vacant.cli import local_store as ls
from vacant.core.crypto import keygen
from vacant.core.types import (
    CapabilityCard,
    SubstrateSpec,
    VacantId,
)
from vacant.protocol.capability_card import serialize as serialize_card
from vacant.protocol.envelope import (
    A2AMessage,
    A2APart,
    VacantEnvelope,
    from_a2a_jsonrpc,
    to_a2a_jsonrpc,
)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def isolated_vacant_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("VACANT_HOME", str(home))
    monkeypatch.delenv("VACANT_NAME", raising=False)
    monkeypatch.delenv("VACANT_REGISTRY_URL", raising=False)
    return home


# --- httpx patcher ----------------------------------------------------------


Handler = Callable[[httpx.Request], httpx.Response]


def _install_mock_httpx(monkeypatch: pytest.MonkeyPatch, handler: Handler) -> None:
    """Replace httpx.AsyncClient with a wrapper that injects MockTransport."""

    real_client = httpx.AsyncClient

    def make(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", make)


# --- publish ----------------------------------------------------------------


def test_publish_succeeds_with_mock_registry(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner.invoke(app, ["init", "alice"])
    persisted: dict[str, Any] = {
        "vacant_id": ls.load_meta("alice").vacant_id_hex,
        "halo_version": 1,
        "visibility": "PUBLIC",
    }

    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(f"{request.method} {request.url.path}")
        if request.method == "GET" and request.url.path.startswith("/v1/event_log/"):
            return httpx.Response(200, json=[])
        if request.method == "POST" and request.url.path == "/v1/halo":
            body = json.loads(request.content)
            assert "capability_card_blob_hex" in body
            assert body["runtime_state"] == "ACTIVE"
            return httpx.Response(200, json=persisted)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    _install_mock_httpx(monkeypatch, handler)

    r = runner.invoke(
        app,
        [
            "publish",
            "--capability",
            "echo",
            "--registry",
            "http://reg.test/",  # trailing slash exercises rstrip
            "--endpoint",
            "https://alice.example/a2a",
        ],
    )
    assert r.exit_code == 0, r.stdout
    out = json.loads(r.stdout)
    assert out["vacant_id"] == persisted["vacant_id"]
    after = ls.load_meta("alice")
    assert after.state == "ACTIVE"
    assert after.halo_published is True
    assert any("/v1/halo" in s for s in seen)


def test_publish_paginates_event_log_then_succeeds(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_next_actor_seq` walks event_log pages until empty and returns max+1."""
    runner.invoke(app, ["init", "alice"])

    pages = [
        [{"seq": 5, "actor_seq": 1}, {"seq": 6, "actor_seq": 2}],
        [{"seq": 7, "actor_seq": 3}],
        [],
    ]
    page_idx = {"i": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path.startswith("/v1/event_log/"):
            i = page_idx["i"]
            page_idx["i"] = i + 1
            return httpx.Response(200, json=pages[i] if i < len(pages) else [])
        if request.method == "POST" and request.url.path == "/v1/halo":
            body = json.loads(request.content)
            # actor_seq came from page max (3) + 1 = 4
            assert body["event_actor_seq"] == 4
            return httpx.Response(200, json={"ok": True, "actor_seq": body["event_actor_seq"]})
        raise AssertionError(f"unexpected: {request.method} {request.url}")

    _install_mock_httpx(monkeypatch, handler)
    r = runner.invoke(
        app,
        ["publish", "--capability", "echo", "--registry", "http://reg.test"],
    )
    assert r.exit_code == 0, r.stdout


def test_publish_event_log_404_treated_as_actor_seq_one(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-200 from event_log is treated as 'no prior events', actor_seq=1."""
    runner.invoke(app, ["init", "alice"])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path.startswith("/v1/event_log/"):
            return httpx.Response(404, json={"detail": "not found"})
        if request.method == "POST" and request.url.path == "/v1/halo":
            body = json.loads(request.content)
            assert body["event_actor_seq"] == 1
            return httpx.Response(200, json={"ok": True})
        raise AssertionError(f"unexpected: {request.method} {request.url}")

    _install_mock_httpx(monkeypatch, handler)
    r = runner.invoke(
        app,
        ["publish", "--capability", "echo", "--registry", "http://reg.test"],
    )
    assert r.exit_code == 0, r.stdout


def test_publish_failure_path_surfaces_error(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`/v1/halo` returns 500 → CLI exits 1 with 'publish failed'."""
    runner.invoke(app, ["init", "alice"])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path.startswith("/v1/event_log/"):
            return httpx.Response(200, json=[])
        if request.method == "POST" and request.url.path == "/v1/halo":
            return httpx.Response(500, json={"detail": "boom"})
        raise AssertionError("unexpected")

    _install_mock_httpx(monkeypatch, handler)
    r = runner.invoke(
        app,
        ["publish", "--capability", "echo", "--registry", "http://reg.test"],
    )
    assert r.exit_code == 1
    assert "publish failed" in (r.stdout + (r.stderr or "")).lower()


# --- lineage ---------------------------------------------------------------


def test_lineage_returns_chain_via_mock(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    chain = {
        "root": "ab" * 32,
        "ancestors": ["ab" * 32, "cd" * 32],
        "depth": 2,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path.startswith("/v1/lineage/"):
            assert request.url.params["direction"] == "ancestors"
            assert request.url.params["depth"] == "4"
            return httpx.Response(200, json=chain)
        raise AssertionError(f"unexpected: {request.method} {request.url}")

    _install_mock_httpx(monkeypatch, handler)
    r = runner.invoke(
        app,
        [
            "lineage",
            "ab" * 32,
            "--registry",
            "http://reg.test",
            "--direction",
            "ancestors",
            "--depth",
            "4",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert json.loads(r.stdout) == chain


def test_lineage_rejects_bad_direction(runner: CliRunner) -> None:
    r = runner.invoke(
        app,
        [
            "lineage",
            "ab" * 32,
            "--registry",
            "http://reg.test",
            "--direction",
            "sideways",
        ],
    )
    assert r.exit_code == 2
    assert "direction" in (r.stdout + (r.stderr or "")).lower()


def test_lineage_http_error_surfaces(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "down"})

    _install_mock_httpx(monkeypatch, handler)
    r = runner.invoke(
        app,
        ["lineage", "ab" * 32, "--registry", "http://reg.test"],
    )
    assert r.exit_code == 1
    assert "lineage lookup failed" in (r.stdout + (r.stderr or "")).lower()


# --- call ------------------------------------------------------------------


def _build_target_card(endpoint: str) -> tuple[Any, VacantId, CapabilityCard]:
    """Build a real signed CapabilityCard for a target vacant (bob)."""
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text="echo",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
        endpoint=endpoint,
    ).signed(sk)
    return sk, vid, card


def test_call_succeeds_full_round_trip(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    runner.invoke(app, ["init", "alice"])
    target_endpoint = "https://bob.test/a2a"
    target_sk, target_vid, target_card = _build_target_card(target_endpoint)
    blob_hex = serialize_card(target_card).hex()
    target_vid_hex = target_vid.hex()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == f"/v1/capability_card/{target_vid_hex}":
            return httpx.Response(
                200, json={"capability_card_blob_hex": blob_hex, "vacant_id": target_vid_hex}
            )
        if request.method == "POST" and str(request.url) == target_endpoint:
            body = json.loads(request.content)
            req_env = from_a2a_jsonrpc(body)
            response = VacantEnvelope(
                from_vacant_id=target_vid,
                to_vacant_id=req_env.from_vacant_id,
                sequence_no=1,
                timestamp=datetime.now(UTC),
                payload=A2AMessage(
                    role="ROLE_AGENT",
                    parts=[A2APart(text=f"echo: {req_env.payload.parts[0].text}")],
                ),
            ).signed(target_sk)
            wire = to_a2a_jsonrpc(response)
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": "rsp",
                    "result": {"message": wire["params"]["message"]},
                },
            )
        raise AssertionError(f"unexpected: {request.method} {request.url}")

    _install_mock_httpx(monkeypatch, handler)
    r = runner.invoke(
        app,
        [
            "call",
            target_vid_hex,
            "echo",
            "--text",
            "hi",
            "--registry",
            "http://reg.test",
        ],
    )
    assert r.exit_code == 0, r.stdout
    out = json.loads(r.stdout)
    assert out["target"] == target_vid_hex
    assert out["endpoint"] == target_endpoint
    assert out["response_text"].startswith("echo: hi")
    assert out["response_role"] == "ROLE_AGENT"


def test_call_fails_when_registry_returns_no_blob(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner.invoke(app, ["init", "alice"])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path.startswith("/v1/capability_card/"):
            return httpx.Response(200, json={"vacant_id": "ab" * 32})
        raise AssertionError("unexpected")

    _install_mock_httpx(monkeypatch, handler)
    r = runner.invoke(
        app,
        ["call", "ab" * 32, "echo", "--registry", "http://reg.test"],
    )
    assert r.exit_code == 1
    assert "call failed" in (r.stdout + (r.stderr or "")).lower()


def test_call_fails_when_registry_404(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    runner.invoke(app, ["init", "alice"])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "no card"})

    _install_mock_httpx(monkeypatch, handler)
    r = runner.invoke(
        app,
        ["call", "ab" * 32, "echo", "--registry", "http://reg.test"],
    )
    assert r.exit_code == 1


# --- attest / unpublish / heartbeat / status edge cases --------------------


def test_attest_invalid_target_hex(runner: CliRunner) -> None:
    runner.invoke(app, ["init", "alice"])
    r = runner.invoke(app, ["attest", "not-hex", "is-honest"])
    assert r.exit_code == 2
    assert "invalid vacant_id" in (r.stdout + (r.stderr or "")).lower()


def test_attest_no_local_vacant(runner: CliRunner) -> None:
    r = runner.invoke(app, ["attest", "ab" * 32, "is-honest", "--name", "ghost"])
    assert r.exit_code == 2


def test_unpublish_no_local_vacant(runner: CliRunner) -> None:
    r = runner.invoke(app, ["unpublish", "--name", "ghost"])
    assert r.exit_code == 2


def test_heartbeat_no_local_vacant(runner: CliRunner) -> None:
    r = runner.invoke(app, ["heartbeat", "--name", "ghost"])
    assert r.exit_code == 2


def test_status_skips_dirs_without_meta(runner: CliRunner, isolated_vacant_home: Path) -> None:
    """A bare directory under VACANT_HOME without meta.json is ignored."""
    runner.invoke(app, ["init", "alice"])
    # list_vacant_names already filters by meta.json existence; this also
    # exercises the load_meta-fail branch in case meta.json is removed
    # mid-iteration.
    (isolated_vacant_home / "alice" / "meta.json").unlink()
    r = runner.invoke(app, ["status"])
    assert r.exit_code == 0
    assert json.loads(r.stdout)["vacants"] == []
