"""Pfix8 P8.5 — peer_review_tick unit tests.

The tick is pure-data-in / persisted-effects-out so we can drive it
with an injected ``http_post`` mock and assert on the resulting JSONL
row + return shape without spinning up a real HTTP server. The full
HTTP round-trip is verified in tests/integration/test_a2a_delegation.py.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from vacant.cli import local_store as ls
from vacant.cli.server import build_serve_app
from vacant.core.types import EMPTY_PREV_HASH, VacantId
from vacant.protocol.envelope import (
    A2AMessage,
    A2APart,
    VacantEnvelope,
    to_a2a_jsonrpc,
)
from vacant.runtime.peer_review import (
    PROBE_PROMPT,
    peer_review_tick,
    score_response_heuristic,
    select_peer,
)


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("VACANT_HOME", str(home))
    monkeypatch.delenv("VACANT_NAME", raising=False)
    return home


def _seed_peer_with_endpoint(name: str, endpoint: str) -> ls.LocalMeta:
    ls.init_vacant(name, insecure_demo=True)
    meta = ls.load_meta(name)
    meta.endpoint = endpoint
    ls.save_meta(name, meta)
    return meta


# --- select_peer -----------------------------------------------------------


def test_select_peer_skips_self_and_no_endpoint(isolated_home: Path) -> None:
    ls.init_vacant("alice", insecure_demo=True)
    ls.init_vacant("bob", insecure_demo=True)  # no endpoint
    alice_meta = ls.load_meta("alice")
    out = select_peer(self_vacant_id_hex=alice_meta.vacant_id_hex, home=isolated_home)
    assert out is None


def test_select_peer_picks_lowest_review_count(isolated_home: Path) -> None:
    ls.init_vacant("alice", insecure_demo=True)
    alice_meta = ls.load_meta("alice")
    _seed_peer_with_endpoint("bob", "http://127.0.0.1:9001")
    _seed_peer_with_endpoint("carol", "http://127.0.0.1:9002")
    (isolated_home / "bob" / "reviews_received.jsonl").write_text(
        '{"x":1}\n{"x":2}\n{"x":3}\n', encoding="utf-8"
    )
    out = select_peer(self_vacant_id_hex=alice_meta.vacant_id_hex, home=isolated_home)
    assert out is not None
    name, _meta = out
    assert name == "carol"


def test_select_peer_respects_review_count_max(isolated_home: Path) -> None:
    ls.init_vacant("alice", insecure_demo=True)
    alice_meta = ls.load_meta("alice")
    _seed_peer_with_endpoint("bob", "http://127.0.0.1:9001")
    (isolated_home / "bob" / "reviews_received.jsonl").write_text(
        '{"x":1}\n{"x":2}\n{"x":3}\n{"x":4}\n{"x":5}\n', encoding="utf-8"
    )
    out = select_peer(
        self_vacant_id_hex=alice_meta.vacant_id_hex,
        home=isolated_home,
        review_count_max=5,
    )
    assert out is None


# --- score_response_heuristic ---------------------------------------------


def test_score_empty_response() -> None:
    """Spec-aligned 3D scorer (Pfix9 §B): peer reviews emit only F/L/R.
    Honesty + adoption come from separate channels."""
    s = score_response_heuristic("")
    assert s["factual"] == 0.1
    assert s["logical"] == 0.1
    assert s["relevance"] == 0.1
    # Spec contract: H + A NOT written from peer-review path.
    assert "honesty" not in s
    assert "adoption" not in s


def test_score_refusal() -> None:
    """Refusal → low relevance (caller's question dodged) + mid factual
    + mid logical. H + A still come from separate channels."""
    s = score_response_heuristic("I cannot help with that request, sorry.")
    assert s["relevance"] < 0.5
    assert "honesty" not in s
    assert "adoption" not in s


def test_score_echo_caps_below_top() -> None:
    s = score_response_heuristic("echo from abc123: self_describe", request_text="self_describe")
    assert s["factual"] <= 0.55


def test_score_long_response_scales_up() -> None:
    s = score_response_heuristic("a" * 300)
    assert s["factual"] > 0.8


# --- peer_review_tick ------------------------------------------------------


@pytest.mark.asyncio
async def test_peer_review_tick_no_eligible_peer(isolated_home: Path) -> None:
    ls.init_vacant("alice", insecure_demo=True)
    bundle = build_serve_app("alice")
    res = await peer_review_tick(
        self_form=bundle.form,
        self_signing_key=bundle.signing_key,
        home=isolated_home,
    )
    assert res.skipped_reason == "no_eligible_peer"
    assert res.delivered_to is None


@pytest.mark.asyncio
async def test_peer_review_tick_writes_signed_review_to_peer(isolated_home: Path) -> None:
    ls.init_vacant("alice", insecure_demo=True)
    alice_bundle = build_serve_app("alice")
    ls.init_vacant("bob", insecure_demo=True)
    bob_meta = ls.load_meta("bob")
    bob_meta.endpoint = "http://127.0.0.1:9999"
    ls.save_meta("bob", bob_meta)
    bob_sk = ls.load_signing_key("bob")
    bob_vid = VacantId(pubkey_bytes=bytes.fromhex(bob_meta.vacant_id_hex))

    async def fake_post(url: str, json_body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        assert url == "http://127.0.0.1:9999/a2a/message/send"
        response_env = VacantEnvelope(
            from_vacant_id=bob_vid,
            to_vacant_id=alice_bundle.form.identity,
            sequence_no=1,
            timestamp=datetime.now(UTC),
            prev_envelope_hash=EMPTY_PREV_HASH,
            payload=A2AMessage(
                role="ROLE_AGENT",
                parts=[A2APart(text=f"echo from {bob_vid.short()}: {PROBE_PROMPT}")],
            ),
            idempotency_key="peer-review-rsp-1",
        ).signed(bob_sk)
        wire = to_a2a_jsonrpc(response_env)
        return 200, {
            "jsonrpc": "2.0",
            "id": json_body.get("id", "1"),
            "result": {"message": wire["params"]["message"]},
        }

    res = await peer_review_tick(
        self_form=alice_bundle.form,
        self_signing_key=alice_bundle.signing_key,
        home=isolated_home,
        http_post=fake_post,
    )
    assert res.error is None
    assert res.skipped_reason is None
    assert res.target_vacant_id_hex == bob_vid.hex()
    assert res.dimensions is not None
    assert res.dimensions["factual"] <= 0.55

    received = isolated_home / "bob" / "reviews_received.jsonl"
    assert received.exists()
    rows = received.read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1
    row = json.loads(rows[0])
    assert row["reviewer"] == alice_bundle.form.identity.hex()
    assert row["target"] == bob_vid.hex()
    assert row["substrate"] == "peer-review:heuristic"
    assert len(row["signature_hex"]) > 0


@pytest.mark.asyncio
async def test_peer_review_tick_records_http_error(isolated_home: Path) -> None:
    ls.init_vacant("alice", insecure_demo=True)
    alice_bundle = build_serve_app("alice")
    _seed_peer_with_endpoint("bob", "http://127.0.0.1:9999")

    async def boom(url: str, json_body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        raise RuntimeError("network down")

    res = await peer_review_tick(
        self_form=alice_bundle.form,
        self_signing_key=alice_bundle.signing_key,
        home=isolated_home,
        http_post=boom,
    )
    assert res.error is not None
    assert "network down" in res.error
    assert not (isolated_home / "bob" / "reviews_received.jsonl").exists()


@pytest.mark.asyncio
async def test_peer_review_tick_rejects_unsigned_response(isolated_home: Path) -> None:
    """Forged response (claims to be from bob but signed by alice) must
    NOT result in any review row being written — otherwise an attacker
    could plant signed-looking peer reviews on any target."""
    ls.init_vacant("alice", insecure_demo=True)
    alice_bundle = build_serve_app("alice")
    ls.init_vacant("bob", insecure_demo=True)
    bob_meta = ls.load_meta("bob")
    bob_meta.endpoint = "http://127.0.0.1:9999"
    ls.save_meta("bob", bob_meta)
    alice_sk = alice_bundle.signing_key
    bob_vid = VacantId(pubkey_bytes=bytes.fromhex(bob_meta.vacant_id_hex))

    async def fake_post(url: str, json_body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        forged = VacantEnvelope(
            from_vacant_id=bob_vid,
            to_vacant_id=alice_bundle.form.identity,
            sequence_no=1,
            timestamp=datetime.now(UTC),
            prev_envelope_hash=EMPTY_PREV_HASH,
            payload=A2AMessage(role="ROLE_AGENT", parts=[A2APart(text="forged")]),
            idempotency_key="peer-review-forged-1",
        ).signed(alice_sk)
        wire = to_a2a_jsonrpc(forged)
        return 200, {
            "jsonrpc": "2.0",
            "id": json_body.get("id", "1"),
            "result": {"message": wire["params"]["message"]},
        }

    res = await peer_review_tick(
        self_form=alice_bundle.form,
        self_signing_key=alice_sk,
        home=isolated_home,
        http_post=fake_post,
    )
    assert res.error is not None
    assert "signature" in res.error.lower()
    assert not (isolated_home / "bob" / "reviews_received.jsonl").exists()


def test_peer_review_tick_runs_via_asyncio_run(isolated_home: Path) -> None:
    ls.init_vacant("alice", insecure_demo=True)
    bundle = build_serve_app("alice")

    async def go() -> None:
        await peer_review_tick(
            self_form=bundle.form,
            self_signing_key=bundle.signing_key,
            home=isolated_home,
        )

    asyncio.run(go())
