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
from vacant.core.crypto import hash_blake2b
from vacant.core.types import VacantId
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


def _sign_review_for_target(
    *,
    reviewer_name: str,
    target_vid_hex: str,
    dims: dict[str, float] | None = None,
    substrate: str = "peer-review:heuristic",
    call_envelope_id_hex: str = "0" * 64,
    claim: str = "test review",
    issued_at_iso: str = "2026-05-14T12:00:00+00:00",
) -> dict[str, object]:
    """Build a signed review record the way peer_review_tick does."""
    import json as _json

    reviewer_meta = ls.load_meta(reviewer_name)
    reviewer_sk = ls.load_signing_key(reviewer_name)
    dims = dims or {"factual": 0.7, "logical": 0.7, "relevance": 0.7}
    payload: dict[str, object] = {
        "reviewer": reviewer_meta.vacant_id_hex,
        "target": target_vid_hex,
        "dimensions": dims,
        "substrate": substrate,
        "call_envelope_id_hex": call_envelope_id_hex,
        "claim": claim,
        "issued_at": issued_at_iso,
    }
    canonical = _json.dumps(payload, sort_keys=True, separators=(",", ":"))
    h = hash_blake2b(canonical.encode("utf-8"))
    sig = reviewer_sk.sign(h).signature
    return {**payload, "payload_hash_hex": h.hex(), "signature_hex": sig.hex()}


def test_reviews_ingest_accepts_signed_review() -> None:
    """P2P review path: a peer POSTs a signed review for THIS vacant.
    Server verifies signature, writes to local reviews_received.jsonl."""
    ls.init_vacant("alice")
    ls.init_vacant("bob")
    alice_bundle = build_serve_app("alice")
    record = _sign_review_for_target(
        reviewer_name="bob",
        target_vid_hex=alice_bundle.form.identity.hex(),
    )

    async def _go() -> None:
        async with AsyncClient(
            transport=ASGITransport(app=alice_bundle.app), base_url="http://test"
        ) as ac:
            r = await ac.post("/reviews/ingest", json=record)
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["ok"] is True
            assert data["duplicate"] is False
            assert data["signature_hex"] == record["signature_hex"]
            # Second POST → idempotent dedupe.
            r2 = await ac.post("/reviews/ingest", json=record)
            assert r2.status_code == 200
            assert r2.json()["duplicate"] is True

    asyncio.run(_go())

    import json as _json

    home = Path(ls.vacant_home())
    jsonl = home / "alice" / "reviews_received.jsonl"
    assert jsonl.exists()
    rows = [_json.loads(line) for line in jsonl.read_text().splitlines() if line.strip()]
    assert len(rows) == 1  # dedupe
    assert rows[0]["reviewer"] == ls.load_meta("bob").vacant_id_hex
    assert rows[0]["target"] == alice_bundle.form.identity.hex()


def test_reviews_ingest_rejects_wrong_target() -> None:
    """Server must reject reviews whose target != self — otherwise any
    attacker could plant reviews into anyone's jsonl."""
    ls.init_vacant("alice")
    ls.init_vacant("bob")
    ls.init_vacant("carol")
    alice_bundle = build_serve_app("alice")
    bob_vid = ls.load_meta("bob").vacant_id_hex
    record = _sign_review_for_target(
        reviewer_name="carol",
        target_vid_hex=bob_vid,  # NOT alice
    )

    async def _go() -> None:
        async with AsyncClient(
            transport=ASGITransport(app=alice_bundle.app), base_url="http://test"
        ) as ac:
            r = await ac.post("/reviews/ingest", json=record)
            assert r.status_code == 422
            assert r.json()["error"] == "target_mismatch"

    asyncio.run(_go())
    home = Path(ls.vacant_home())
    assert not (home / "alice" / "reviews_received.jsonl").exists()


def test_reviews_ingest_rejects_bad_signature() -> None:
    """Tampered review (dimensions changed after signing) → 401."""
    ls.init_vacant("alice")
    ls.init_vacant("bob")
    alice_bundle = build_serve_app("alice")
    record = _sign_review_for_target(
        reviewer_name="bob",
        target_vid_hex=alice_bundle.form.identity.hex(),
    )
    # Tamper after signing.
    record["dimensions"] = {"factual": 0.99, "logical": 0.99, "relevance": 0.99}

    async def _go() -> None:
        async with AsyncClient(
            transport=ASGITransport(app=alice_bundle.app), base_url="http://test"
        ) as ac:
            r = await ac.post("/reviews/ingest", json=record)
            assert r.status_code == 401
            assert r.json()["error"] == "signature_invalid"

    asyncio.run(_go())


def test_reviews_ingest_rejects_missing_dimensions() -> None:
    """Reviews must carry F/L/R per spec; missing → 422."""
    ls.init_vacant("alice")
    ls.init_vacant("bob")
    alice_bundle = build_serve_app("alice")
    record = _sign_review_for_target(
        reviewer_name="bob",
        target_vid_hex=alice_bundle.form.identity.hex(),
        dims={"factual": 0.7},  # missing L, R
    )

    async def _go() -> None:
        async with AsyncClient(
            transport=ASGITransport(app=alice_bundle.app), base_url="http://test"
        ) as ac:
            r = await ac.post("/reviews/ingest", json=record)
            assert r.status_code == 422
            assert "dimensions" in r.json()["error"]

    asyncio.run(_go())


def test_blinded_ingest_buffers_below_threshold_then_flushes() -> None:
    """P1 wire-up of THEORY_V5 §3.9 #4 — blinded reviews accumulate
    until threshold (3 by default); only then are they unblinded and
    written to reviews_received.jsonl."""
    import json as _json

    from vacant.core.crypto import SigningKey as _SigningKey
    from vacant.reputation.blinded_review import make_blinded_review_record

    ls.init_vacant("alice")
    bundle = build_serve_app("alice")
    alice_vid_hex = bundle.form.identity.hex()

    def _build_pair() -> tuple[dict, dict]:
        sk = _SigningKey.generate()
        rec, env = make_blinded_review_record(
            reviewer_signing_key=sk,
            target_vid_hex=alice_vid_hex,
            dimensions={"factual": 0.7, "logical": 0.7, "relevance": 0.7},
            substrate="peer-review:heuristic",
            call_envelope_id_hex="00" * 32,
            claim="blinded test",
            issued_at_iso="2026-05-15T12:00:00+00:00",
        )
        return rec, env.to_dict()

    async def _go() -> None:
        async with AsyncClient(
            transport=ASGITransport(app=bundle.app), base_url="http://test"
        ) as ac:
            # First two pairs: buffered, not flushed.
            for expected_buffered in (1, 2):
                rec, rev = _build_pair()
                r = await ac.post(
                    "/reviews/blinded_ingest", json={"record": rec, "reveal": rev}
                )
                assert r.status_code == 200, r.text
                data = r.json()
                assert data["ok"] is True
                assert data["buffered"] == expected_buffered
                assert data["flushed_count"] == 0
            # Third pair: triggers flush.
            rec, rev = _build_pair()
            r = await ac.post(
                "/reviews/blinded_ingest", json={"record": rec, "reveal": rev}
            )
            data = r.json()
            assert data["ok"] is True
            assert data["flushed_count"] == 3
            assert data["buffered"] == 0

    asyncio.run(_go())

    # All 3 unblinded rows should now be in reviews_received.jsonl with
    # plaintext `reviewer` field restored.
    home = Path(ls.vacant_home())
    jsonl = home / "alice" / "reviews_received.jsonl"
    rows = [_json.loads(line) for line in jsonl.read_text().splitlines() if line.strip()]
    assert len(rows) == 3
    for row in rows:
        assert "reviewer" in row and len(row["reviewer"]) == 64
        assert "reviewer_commitment" not in row
        assert row["target"] == alice_vid_hex


def test_blinded_ingest_rejects_replayed_commitment() -> None:
    """Same commitment submitted twice → 409. Spent-commitment store
    prevents an attacker from inflating the batch with duplicates."""
    from vacant.core.crypto import SigningKey as _SigningKey
    from vacant.reputation.blinded_review import make_blinded_review_record

    ls.init_vacant("alice")
    bundle = build_serve_app("alice")
    sk = _SigningKey.generate()
    rec, env = make_blinded_review_record(
        reviewer_signing_key=sk,
        target_vid_hex=bundle.form.identity.hex(),
        dimensions={"factual": 0.7, "logical": 0.7, "relevance": 0.7},
        substrate="peer-review:heuristic",
        call_envelope_id_hex="00" * 32,
        claim="replay test",
        issued_at_iso="2026-05-15T12:00:00+00:00",
    )
    payload = {"record": rec, "reveal": env.to_dict()}

    async def _go() -> None:
        async with AsyncClient(
            transport=ASGITransport(app=bundle.app), base_url="http://test"
        ) as ac:
            r1 = await ac.post("/reviews/blinded_ingest", json=payload)
            assert r1.status_code == 200
            r2 = await ac.post("/reviews/blinded_ingest", json=payload)
            assert r2.status_code == 409
            assert r2.json()["error"] == "commitment_already_spent"

    asyncio.run(_go())


def test_blinded_ingest_rejects_wrong_target() -> None:
    from vacant.core.crypto import SigningKey as _SigningKey
    from vacant.reputation.blinded_review import make_blinded_review_record

    ls.init_vacant("alice")
    ls.init_vacant("bob")
    alice_bundle = build_serve_app("alice")
    sk = _SigningKey.generate()
    # Commit/sign against BOB but POST to alice.
    bob_vid_hex = ls.load_meta("bob").vacant_id_hex
    rec, env = make_blinded_review_record(
        reviewer_signing_key=sk,
        target_vid_hex=bob_vid_hex,
        dimensions={"factual": 0.7, "logical": 0.7, "relevance": 0.7},
        substrate="peer-review:heuristic",
        call_envelope_id_hex="00" * 32,
        claim="target test",
        issued_at_iso="2026-05-15T12:00:00+00:00",
    )

    async def _go() -> None:
        async with AsyncClient(
            transport=ASGITransport(app=alice_bundle.app), base_url="http://test"
        ) as ac:
            r = await ac.post(
                "/reviews/blinded_ingest", json={"record": rec, "reveal": env.to_dict()}
            )
            assert r.status_code == 422
            assert r.json()["error"] == "target_mismatch"

    asyncio.run(_go())


def test_chain_reset_accepts_signed_request_and_clears_pair() -> None:
    """P1b: A peer that drifted out of sync can POST a signed
    RESET_CHAIN envelope to /a2a/chain/reset; the server verifies the
    signature, checks freshness, and seeds the replay store back to
    (0, EMPTY) for that pair so the next probe with seq=1 is accepted."""
    from datetime import UTC, datetime

    from vacant.core.types import EMPTY_PREV_HASH, VacantId
    from vacant.protocol.envelope import (
        A2AMessage,
        A2APart,
        VacantEnvelope,
        to_a2a_jsonrpc,
    )
    from vacant.protocol.replay_protect import PairKey, ReplayState

    ls.init_vacant("alice")
    ls.init_vacant("bob")
    alice_bundle = build_serve_app("alice")
    bob_meta = ls.load_meta("bob")
    bob_sk = ls.load_signing_key("bob")
    bob_vid = VacantId(pubkey_bytes=bytes.fromhex(bob_meta.vacant_id_hex))

    # Pre-poison alice's replay store: pretend (bob → alice) is already
    # at seq=42 so any naive probe from bob with seq=1 would be rejected.
    alice_bundle.replay_store.seed(
        PairKey(from_vid=bob_vid, to_vid=alice_bundle.form.identity),
        ReplayState(last_sequence_no=42, chain_tip=b"\xab" * 32),
    )

    reset_env = VacantEnvelope(
        from_vacant_id=bob_vid,
        to_vacant_id=alice_bundle.form.identity,
        sequence_no=1,
        timestamp=datetime.now(UTC),
        prev_envelope_hash=EMPTY_PREV_HASH,
        payload=A2AMessage(role="ROLE_USER", parts=[A2APart(text="RESET_CHAIN")]),
        idempotency_key="reset-test-1",
    ).signed(bob_sk)
    wire = to_a2a_jsonrpc(reset_env)

    async def _go() -> None:
        async with AsyncClient(
            transport=ASGITransport(app=alice_bundle.app), base_url="http://test"
        ) as ac:
            r = await ac.post("/a2a/chain/reset", json=wire)
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["ok"] is True
            assert data["reset_for_peer"] == bob_vid.hex()

    asyncio.run(_go())

    # The pair state must now be (0, EMPTY).
    import asyncio as _asyncio

    state = _asyncio.run(
        alice_bundle.replay_store.get(
            PairKey(from_vid=bob_vid, to_vid=alice_bundle.form.identity)
        )
    )
    assert state.last_sequence_no == 0
    assert state.chain_tip == EMPTY_PREV_HASH


def test_chain_reset_rejects_wrong_payload_text() -> None:
    """/a2a/chain/reset must NOT accept arbitrary signed envelopes —
    only those whose payload is exactly 'RESET_CHAIN'. Otherwise any
    captured A2A envelope could be replayed as a reset."""
    from datetime import UTC, datetime

    from vacant.core.types import EMPTY_PREV_HASH, VacantId
    from vacant.protocol.envelope import (
        A2AMessage,
        A2APart,
        VacantEnvelope,
        to_a2a_jsonrpc,
    )

    ls.init_vacant("alice")
    ls.init_vacant("bob")
    alice_bundle = build_serve_app("alice")
    bob_sk = ls.load_signing_key("bob")
    bob_vid = VacantId(pubkey_bytes=bytes.fromhex(ls.load_meta("bob").vacant_id_hex))

    bad_env = VacantEnvelope(
        from_vacant_id=bob_vid,
        to_vacant_id=alice_bundle.form.identity,
        sequence_no=1,
        timestamp=datetime.now(UTC),
        prev_envelope_hash=EMPTY_PREV_HASH,
        payload=A2AMessage(role="ROLE_USER", parts=[A2APart(text="please reset")]),
        idempotency_key="bad-reset-1",
    ).signed(bob_sk)

    async def _go() -> None:
        async with AsyncClient(
            transport=ASGITransport(app=alice_bundle.app), base_url="http://test"
        ) as ac:
            r = await ac.post("/a2a/chain/reset", json=to_a2a_jsonrpc(bad_env))
            assert r.status_code == 400
            assert r.json()["error"] == "payload_not_reset_chain"

    asyncio.run(_go())


def test_chain_reset_rejects_stale_request() -> None:
    """Anti-replay: a reset envelope older than 5 minutes is rejected
    so attackers can't replay an old captured RESET_CHAIN."""
    from datetime import UTC, datetime, timedelta

    from vacant.core.types import EMPTY_PREV_HASH, VacantId
    from vacant.protocol.envelope import (
        A2AMessage,
        A2APart,
        VacantEnvelope,
        to_a2a_jsonrpc,
    )

    ls.init_vacant("alice")
    ls.init_vacant("bob")
    alice_bundle = build_serve_app("alice")
    bob_sk = ls.load_signing_key("bob")
    bob_vid = VacantId(pubkey_bytes=bytes.fromhex(ls.load_meta("bob").vacant_id_hex))

    old_ts = datetime.now(UTC) - timedelta(minutes=10)
    stale_env = VacantEnvelope(
        from_vacant_id=bob_vid,
        to_vacant_id=alice_bundle.form.identity,
        sequence_no=1,
        timestamp=old_ts,
        prev_envelope_hash=EMPTY_PREV_HASH,
        payload=A2AMessage(role="ROLE_USER", parts=[A2APart(text="RESET_CHAIN")]),
        idempotency_key="stale-reset-1",
    ).signed(bob_sk)

    async def _go() -> None:
        async with AsyncClient(
            transport=ASGITransport(app=alice_bundle.app), base_url="http://test"
        ) as ac:
            r = await ac.post("/a2a/chain/reset", json=to_a2a_jsonrpc(stale_env))
            assert r.status_code == 400
            assert "stale_reset_request" in r.json()["error"]

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


def test_build_fastmcp_server_registers_eight_tools() -> None:
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
        "vacant_list_children",
        "vacant_delegate",
        "vacant_delegate_a2a",
        "vacant_caller_review",
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
    assert len(tools) == 8


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


def test_vacant_list_children_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No children yet → returns empty list with parent's vacant_id."""
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    ls.init_vacant("alice", insecure_demo=True)
    bundle = build_serve_app("alice")
    mcp = build_fastmcp_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
        replay_store=bundle.replay_store,
    )
    out = asyncio.run(mcp.call_tool("vacant_list_children", {}))
    payload = out[0] if isinstance(out, tuple) else out
    import json as _json

    text = payload[0].text if hasattr(payload[0], "text") else str(payload[0])
    body = _json.loads(text)
    assert body["children"] == []
    assert body["parent_vacant_id_hex"] == bundle.form.identity.hex()


def test_vacant_list_children_reports_spawned_d1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """vacant_list_children must surface a freshly-spawned D1 child with
    its policy_mutation pulled out of the child's BIRTH log entry."""
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    ls.init_vacant("alice", insecure_demo=True)
    bundle = build_serve_app("alice")

    def _persist(result: object, child_name: str, _parent_name: str) -> None:
        ls.persist_spawned_child(
            child_name,
            child_vacant_id=result.child.identity,  # type: ignore[attr-defined]
            child_signing_key=result.child_signing_key,  # type: ignore[attr-defined]
            child_logbook=result.child.logbook,  # type: ignore[attr-defined]
            parent_vacant_id=result.child.parent_id,  # type: ignore[attr-defined]
            state=result.child.runtime_state.value,  # type: ignore[attr-defined]
        )

    mcp = build_fastmcp_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
        replay_store=bundle.replay_store,
        parent_local_name="alice",
        persist_spawned_child=_persist,
    )
    spawn_out = asyncio.run(
        mcp.call_tool(
            "vacant_spawn",
            {"policy_mutation": "always cite sources", "child_name_hint": "cite"},
        )
    )
    spawn_payload = spawn_out[0] if isinstance(spawn_out, tuple) else spawn_out
    import json as _json

    spawn_body = _json.loads(
        spawn_payload[0].text if hasattr(spawn_payload[0], "text") else str(spawn_payload[0])
    )
    child_name = spawn_body["child_name"]

    list_out = asyncio.run(mcp.call_tool("vacant_list_children", {}))
    list_payload = list_out[0] if isinstance(list_out, tuple) else list_out
    list_body = _json.loads(
        list_payload[0].text if hasattr(list_payload[0], "text") else str(list_payload[0])
    )
    assert len(list_body["children"]) == 1
    entry = list_body["children"][0]
    assert entry["name"] == child_name
    assert entry["vacant_id_hex"] == spawn_body["child_vacant_id_hex"]
    assert entry["policy_mutation"] == "always cite sources"
    assert entry["inference_count"] == 0
    assert entry["attestation_count"] == 0


def test_vacant_list_children_skips_non_vacant_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A directory under VACANT_HOME without meta.json (e.g. the rendered
    OpenClaw bundle dir, scratch dirs) must NOT appear in the listing."""
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    ls.init_vacant("alice", insecure_demo=True)
    (tmp_path / ".openclaw-bundle").mkdir()
    (tmp_path / "scratch").mkdir()
    bundle = build_serve_app("alice")
    mcp = build_fastmcp_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
        replay_store=bundle.replay_store,
    )
    out = asyncio.run(mcp.call_tool("vacant_list_children", {}))
    payload = out[0] if isinstance(out, tuple) else out
    import json as _json

    body = _json.loads(payload[0].text if hasattr(payload[0], "text") else str(payload[0]))
    assert body["children"] == []


def test_vacant_delegate_refuses_when_no_parent_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ephemeral mode (parent_local_name=None) must reject delegate."""
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    ls.init_vacant("alice", insecure_demo=True)
    bundle = build_serve_app("alice")
    mcp = build_fastmcp_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
        replay_store=bundle.replay_store,
    )
    out = asyncio.run(mcp.call_tool("vacant_delegate", {"child_name": "alice__c__x", "task": "y"}))
    payload = out[0] if isinstance(out, tuple) else out
    text = payload[0].text if hasattr(payload[0], "text") else str(payload[0])
    assert "ephemeral" in text


def test_vacant_delegate_rejects_unsafe_child_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    ls.init_vacant("alice", insecure_demo=True)
    bundle = build_serve_app("alice")
    mcp = build_fastmcp_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
        replay_store=bundle.replay_store,
        parent_local_name="alice",
    )
    for bad in ("", "../escape", "has space", "with/slash"):
        out = asyncio.run(mcp.call_tool("vacant_delegate", {"child_name": bad, "task": "x"}))
        payload = out[0] if isinstance(out, tuple) else out
        text = payload[0].text if hasattr(payload[0], "text") else str(payload[0])
        assert "invalid child_name" in text, bad


def test_vacant_delegate_refuses_unknown_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    ls.init_vacant("alice", insecure_demo=True)
    bundle = build_serve_app("alice")
    mcp = build_fastmcp_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
        replay_store=bundle.replay_store,
        parent_local_name="alice",
    )
    out = asyncio.run(
        mcp.call_tool(
            "vacant_delegate",
            {"child_name": "alice__nope__deadbeef", "task": "x"},
        )
    )
    payload = out[0] if isinstance(out, tuple) else out
    text = payload[0].text if hasattr(payload[0], "text") else str(payload[0])
    assert "not found on disk" in text


def test_vacant_delegate_refuses_non_descendant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A vacant on disk whose parent_id doesn't match this vacant must
    not be delegate-able (otherwise the trust chain is breakable)."""
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    ls.init_vacant("alice", insecure_demo=True)
    ls.init_vacant("bob", insecure_demo=True)  # peer, NOT alice's child
    bundle = build_serve_app("alice")
    mcp = build_fastmcp_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
        replay_store=bundle.replay_store,
        parent_local_name="alice",
    )
    out = asyncio.run(mcp.call_tool("vacant_delegate", {"child_name": "bob", "task": "x"}))
    payload = out[0] if isinstance(out, tuple) else out
    text = payload[0].text if hasattr(payload[0], "text") else str(payload[0])
    assert "not a direct descendant" in text


def test_vacant_delegate_a2a_refuses_when_no_parent_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    ls.init_vacant("alice", insecure_demo=True)
    bundle = build_serve_app("alice")
    mcp = build_fastmcp_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
        replay_store=bundle.replay_store,
    )
    out = asyncio.run(
        mcp.call_tool(
            "vacant_delegate_a2a",
            {"child_name": "alice__x__y", "task": "t"},
        )
    )
    payload = out[0] if isinstance(out, tuple) else out
    text = payload[0].text if hasattr(payload[0], "text") else str(payload[0])
    assert "ephemeral" in text


def test_vacant_delegate_a2a_rejects_unsafe_child_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    ls.init_vacant("alice", insecure_demo=True)
    bundle = build_serve_app("alice")
    mcp = build_fastmcp_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
        replay_store=bundle.replay_store,
        parent_local_name="alice",
    )
    for bad in ("", "../escape", "has space", "with/slash"):
        out = asyncio.run(mcp.call_tool("vacant_delegate_a2a", {"child_name": bad, "task": "x"}))
        payload = out[0] if isinstance(out, tuple) else out
        text = payload[0].text if hasattr(payload[0], "text") else str(payload[0])
        assert "invalid child_name" in text, bad


def test_vacant_delegate_a2a_refuses_unknown_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    ls.init_vacant("alice", insecure_demo=True)
    bundle = build_serve_app("alice")
    mcp = build_fastmcp_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
        replay_store=bundle.replay_store,
        parent_local_name="alice",
    )
    out = asyncio.run(
        mcp.call_tool(
            "vacant_delegate_a2a",
            {"child_name": "alice__ghost__deadbeef", "task": "x"},
        )
    )
    payload = out[0] if isinstance(out, tuple) else out
    text = payload[0].text if hasattr(payload[0], "text") else str(payload[0])
    assert "not found on disk" in text


def test_vacant_delegate_a2a_refuses_non_descendant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    ls.init_vacant("alice", insecure_demo=True)
    ls.init_vacant("bob", insecure_demo=True)
    bundle = build_serve_app("alice")
    mcp = build_fastmcp_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
        replay_store=bundle.replay_store,
        parent_local_name="alice",
    )
    out = asyncio.run(mcp.call_tool("vacant_delegate_a2a", {"child_name": "bob", "task": "x"}))
    payload = out[0] if isinstance(out, tuple) else out
    text = payload[0].text if hasattr(payload[0], "text") else str(payload[0])
    assert "not a direct descendant" in text


def test_vacant_delegate_a2a_refuses_child_without_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A spawned child has endpoint=None until it boots `vacant serve`.
    Delegate_a2a must surface that, not crash."""
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    ls.init_vacant("alice", insecure_demo=True)
    bundle = build_serve_app("alice")

    def _persist(result: object, child_name: str, _parent_name: str) -> None:
        ls.persist_spawned_child(
            child_name,
            child_vacant_id=result.child.identity,  # type: ignore[attr-defined]
            child_signing_key=result.child_signing_key,  # type: ignore[attr-defined]
            child_logbook=result.child.logbook,  # type: ignore[attr-defined]
            parent_vacant_id=result.child.parent_id,  # type: ignore[attr-defined]
            state=result.child.runtime_state.value,  # type: ignore[attr-defined]
        )

    mcp = build_fastmcp_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
        replay_store=bundle.replay_store,
        parent_local_name="alice",
        persist_spawned_child=_persist,
    )
    spawn = asyncio.run(
        mcp.call_tool(
            "vacant_spawn",
            {"policy_mutation": "x", "child_name_hint": "noendpoint"},
        )
    )
    import json as _json

    spawn_payload = spawn[0] if isinstance(spawn, tuple) else spawn
    spawn_body = _json.loads(
        spawn_payload[0].text if hasattr(spawn_payload[0], "text") else str(spawn_payload[0])
    )
    child_name = spawn_body["child_name"]

    out = asyncio.run(mcp.call_tool("vacant_delegate_a2a", {"child_name": child_name, "task": "x"}))
    payload = out[0] if isinstance(out, tuple) else out
    text = payload[0].text if hasattr(payload[0], "text") else str(payload[0])
    assert "no advertised endpoint" in text


def test_vacant_list_children_surfaces_5d_reputation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After signed caller reviews land in a child's reviews_received.jsonl,
    vacant_list_children must surface aggregated 5D Beta-posterior stats
    (mean, variance, n_eff) per dimension so the LLM can pick a
    well-rated specialist for the next task."""
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    ls.init_vacant("alice", insecure_demo=True)
    bundle = build_serve_app("alice")

    def _persist(result: object, child_name: str, _parent_name: str) -> None:
        ls.persist_spawned_child(
            child_name,
            child_vacant_id=result.child.identity,  # type: ignore[attr-defined]
            child_signing_key=result.child_signing_key,  # type: ignore[attr-defined]
            child_logbook=result.child.logbook,  # type: ignore[attr-defined]
            parent_vacant_id=result.child.parent_id,  # type: ignore[attr-defined]
            state=result.child.runtime_state.value,  # type: ignore[attr-defined]
        )

    mcp = build_fastmcp_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
        replay_store=bundle.replay_store,
        parent_local_name="alice",
        persist_spawned_child=_persist,
    )
    spawn = asyncio.run(
        mcp.call_tool(
            "vacant_spawn",
            {"policy_mutation": "x", "child_name_hint": "rep"},
        )
    )
    import json as _json

    spawn_payload = spawn[0] if isinstance(spawn, tuple) else spawn
    spawn_body = _json.loads(
        spawn_payload[0].text if hasattr(spawn_payload[0], "text") else str(spawn_payload[0])
    )
    child_name = spawn_body["child_name"]
    child_vid_hex = spawn_body["child_vacant_id_hex"]

    # Issue two reviews for the child with different scores.
    for f, h in [(0.9, 0.8), (0.7, 0.6)]:
        asyncio.run(
            mcp.call_tool(
                "vacant_caller_review",
                {
                    "target_vacant_id_hex": child_vid_hex,
                    "factual": f,
                    "logical": 0.5,
                    "relevance": 0.5,
                    "honesty": h,
                    "adoption": 0.5,
                },
            )
        )

    out = asyncio.run(mcp.call_tool("vacant_list_children", {}))
    payload = out[0] if isinstance(out, tuple) else out
    body = _json.loads(payload[0].text if hasattr(payload[0], "text") else str(payload[0]))
    entry = body["children"][0]
    assert entry["review_count"] == 2
    rep = entry["reputation_5d"]
    for dim in ("factual", "logical", "relevance", "honesty", "adoption"):
        assert dim in rep
        assert 0.0 <= rep[dim]["mean"] <= 1.0
        assert rep[dim]["variance"] >= 0.0
        # Two reviews × weight 1.0 → n_eff should be roughly 2 per dim.
        assert rep[dim]["n_eff"] > 0.0


def test_vacant_caller_review_auto_spawns_competitor_after_3_low_reviews(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P8.6: after 3 consecutive reviews mean<0.3 against a direct
    descendant, the next review auto-spawns a competitor sibling with
    a corrective policy_mutation. Failing child is NOT removed."""
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    ls.init_vacant("alice", insecure_demo=True)
    bundle = build_serve_app("alice")

    def _persist(result: object, child_name: str, _parent_name: str) -> None:
        ls.persist_spawned_child(
            child_name,
            child_vacant_id=result.child.identity,  # type: ignore[attr-defined]
            child_signing_key=result.child_signing_key,  # type: ignore[attr-defined]
            child_logbook=result.child.logbook,  # type: ignore[attr-defined]
            parent_vacant_id=result.child.parent_id,  # type: ignore[attr-defined]
            state=result.child.runtime_state.value,  # type: ignore[attr-defined]
        )

    mcp = build_fastmcp_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
        replay_store=bundle.replay_store,
        parent_local_name="alice",
        persist_spawned_child=_persist,
    )
    spawn = asyncio.run(
        mcp.call_tool(
            "vacant_spawn",
            {"policy_mutation": "translate slowly", "child_name_hint": "slow"},
        )
    )
    import json as _json

    spawn_payload = spawn[0] if isinstance(spawn, tuple) else spawn
    spawn_body = _json.loads(
        spawn_payload[0].text if hasattr(spawn_payload[0], "text") else str(spawn_payload[0])
    )
    failing_name = spawn_body["child_name"]
    failing_vid = spawn_body["child_vacant_id_hex"]

    # 3 reviews all with mean ~0.2.
    last_competitor = None
    for _ in range(3):
        out = asyncio.run(
            mcp.call_tool(
                "vacant_caller_review",
                {
                    "target_vacant_id_hex": failing_vid,
                    "factual": 0.2,
                    "logical": 0.2,
                    "relevance": 0.2,
                    "honesty": 0.2,
                    "adoption": 0.2,
                },
            )
        )
        payload = out[0] if isinstance(out, tuple) else out
        body = _json.loads(payload[0].text if hasattr(payload[0], "text") else str(payload[0]))
        last_competitor = body["competitor_spawned"]

    assert last_competitor is not None
    assert "competitor_child_name" in last_competitor
    assert last_competitor["reason"] == "three_consecutive_reviews_below_0.3"
    # corrective mutation extends the failing mutation.
    assert "translate slowly" in last_competitor["corrective_mutation"]
    assert "correction" in last_competitor["corrective_mutation"]

    # Failing child still on disk.
    assert (tmp_path / failing_name).exists()
    # Competitor sibling on disk.
    assert (tmp_path / last_competitor["competitor_child_name"]).exists()

    # alice's logbook has COMPETITOR_SPAWNED entry signed.
    kinds = [e.kind for e in bundle.form.logbook.entries]
    assert "COMPETITOR_SPAWNED" in kinds
    comp = next(e for e in bundle.form.logbook.entries if e.kind == "COMPETITOR_SPAWNED")
    assert comp.payload["failing_child_id"] == failing_vid
    assert comp.payload["competitor_child_name"] == last_competitor["competitor_child_name"]


def test_vacant_caller_review_does_not_spawn_when_reviews_okay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """High-scoring reviews must NOT trigger competitor spawn."""
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    ls.init_vacant("alice", insecure_demo=True)
    bundle = build_serve_app("alice")

    def _persist(result: object, child_name: str, _parent_name: str) -> None:
        ls.persist_spawned_child(
            child_name,
            child_vacant_id=result.child.identity,  # type: ignore[attr-defined]
            child_signing_key=result.child_signing_key,  # type: ignore[attr-defined]
            child_logbook=result.child.logbook,  # type: ignore[attr-defined]
            parent_vacant_id=result.child.parent_id,  # type: ignore[attr-defined]
            state=result.child.runtime_state.value,  # type: ignore[attr-defined]
        )

    mcp = build_fastmcp_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
        replay_store=bundle.replay_store,
        parent_local_name="alice",
        persist_spawned_child=_persist,
    )
    spawn = asyncio.run(
        mcp.call_tool("vacant_spawn", {"policy_mutation": "x", "child_name_hint": "good"})
    )
    import json as _json

    spawn_payload = spawn[0] if isinstance(spawn, tuple) else spawn
    spawn_body = _json.loads(
        spawn_payload[0].text if hasattr(spawn_payload[0], "text") else str(spawn_payload[0])
    )
    for _ in range(3):
        out = asyncio.run(
            mcp.call_tool(
                "vacant_caller_review",
                {
                    "target_vacant_id_hex": spawn_body["child_vacant_id_hex"],
                    "factual": 0.9,
                    "logical": 0.9,
                    "relevance": 0.9,
                    "honesty": 0.9,
                    "adoption": 0.9,
                },
            )
        )
        payload = out[0] if isinstance(out, tuple) else out
        body = _json.loads(payload[0].text if hasattr(payload[0], "text") else str(payload[0]))
        assert body["competitor_spawned"] is None


def test_vacant_caller_review_signs_and_persists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Happy path: 5D review signed by alice, REVIEW_ISSUED on alice's
    logbook, JSONL row appended to target's reviews_received.jsonl."""
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    ls.init_vacant("alice", insecure_demo=True)
    ls.init_vacant("bob", insecure_demo=True)
    bob_meta = ls.load_meta("bob")
    bundle = build_serve_app("alice")
    mcp = build_fastmcp_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
        replay_store=bundle.replay_store,
        parent_local_name="alice",
    )
    out = asyncio.run(
        mcp.call_tool(
            "vacant_caller_review",
            {
                "target_vacant_id_hex": bob_meta.vacant_id_hex,
                "factual": 0.8,
                "logical": 0.7,
                "relevance": 0.9,
                "honesty": 0.85,
                "adoption": 0.5,
                "substrate": "ollama:gemma4:e2b",
                "claim": "bob handled the translation task correctly",
            },
        )
    )
    payload = out[0] if isinstance(out, tuple) else out
    import json as _json

    text = payload[0].text if hasattr(payload[0], "text") else str(payload[0])
    body = _json.loads(text)
    assert body["ok"] is True
    assert body["target_vacant_id_hex"] == bob_meta.vacant_id_hex
    assert body["dimensions"]["factual"] == 0.8
    assert body["delivered_locally"] is True

    # REVIEW_ISSUED on alice's in-memory logbook (form.logbook).
    kinds = [e.kind for e in bundle.form.logbook.entries]
    assert "REVIEW_ISSUED" in kinds
    issued = next(e for e in bundle.form.logbook.entries if e.kind == "REVIEW_ISSUED")
    assert issued.payload["target"] == bob_meta.vacant_id_hex
    assert issued.payload["dimensions"] == body["dimensions"]
    assert issued.payload["signature_hex"] == body["signature_hex"]

    # Bob's reviews_received.jsonl gained the signed row.
    bob_received = tmp_path / "bob" / "reviews_received.jsonl"
    assert bob_received.exists()
    rows = bob_received.read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1
    row = _json.loads(rows[0])
    assert row["reviewer"] == bundle.form.identity.hex()
    assert row["target"] == bob_meta.vacant_id_hex
    assert row["signature_hex"] == body["signature_hex"]


def test_vacant_caller_review_rejects_out_of_range_dimension(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    ls.init_vacant("alice", insecure_demo=True)
    ls.init_vacant("bob", insecure_demo=True)
    bob_meta = ls.load_meta("bob")
    bundle = build_serve_app("alice")
    mcp = build_fastmcp_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
        replay_store=bundle.replay_store,
        parent_local_name="alice",
    )
    out = asyncio.run(
        mcp.call_tool(
            "vacant_caller_review",
            {
                "target_vacant_id_hex": bob_meta.vacant_id_hex,
                "factual": 1.5,  # out of [0,1]
                "logical": 0.5,
                "relevance": 0.5,
                "honesty": 0.5,
                "adoption": 0.5,
            },
        )
    )
    payload = out[0] if isinstance(out, tuple) else out
    text = payload[0].text if hasattr(payload[0], "text") else str(payload[0])
    assert "out of [0.0, 1.0]" in text


def test_vacant_caller_review_refuses_self_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    ls.init_vacant("alice", insecure_demo=True)
    bundle = build_serve_app("alice")
    mcp = build_fastmcp_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
        replay_store=bundle.replay_store,
        parent_local_name="alice",
    )
    out = asyncio.run(
        mcp.call_tool(
            "vacant_caller_review",
            {
                "target_vacant_id_hex": bundle.form.identity.hex(),
                "factual": 0.5,
                "logical": 0.5,
                "relevance": 0.5,
                "honesty": 0.5,
                "adoption": 0.5,
            },
        )
    )
    payload = out[0] if isinstance(out, tuple) else out
    text = payload[0].text if hasattr(payload[0], "text") else str(payload[0])
    assert "self-review is not allowed" in text


def test_vacant_caller_review_refuses_ephemeral(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    ls.init_vacant("alice", insecure_demo=True)
    bundle = build_serve_app("alice")
    mcp = build_fastmcp_server(
        form=bundle.form,
        signing_key=bundle.signing_key,
        replay_store=bundle.replay_store,
    )
    out = asyncio.run(
        mcp.call_tool(
            "vacant_caller_review",
            {
                "target_vacant_id_hex": "00" * 32,
                "factual": 0.5,
                "logical": 0.5,
                "relevance": 0.5,
                "honesty": 0.5,
                "adoption": 0.5,
            },
        )
    )
    payload = out[0] if isinstance(out, tuple) else out
    text = payload[0].text if hasattr(payload[0], "text") else str(payload[0])
    assert "ephemeral" in text


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
