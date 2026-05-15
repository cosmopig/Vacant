"""PR1: `vacant grow` — local-network grow loop.

These tests exercise the `GrowLoop` directly via `tick()`. The full
`vacant grow` CLI is exercised via `vacant grow --help` only — a real
HTTP serve cycle is covered by `test_cli_grow.py` (Typer CliRunner +
in-process A2A app).

Covered:
- Heartbeat tick advances local logbook
- Peer-review tick increments `peer_reviews_sent` when a peer responds
- Red-team probe tick on the Nth cycle writes a signed review with
  `source="redteam_probe"`
- Loop tolerates a peer that errors out without crashing
- `stop()` short-circuits `run_forever`
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from vacant.cli import local_store as ls
from vacant.core.crypto import keygen
from vacant.core.types import (
    BehaviorBundle,
    Logbook,
    ResidentForm,
    SubstrateSpec,
    VacantId,
    VacantState,
)
from vacant.runtime import GrowLoop, GrowStats


def _make_form(vid: VacantId) -> ResidentForm:
    """Minimal in-memory `ResidentForm` for use as the loop's identity."""
    return ResidentForm(
        identity=vid,
        logbook=Logbook(),
        behavior_bundle=BehaviorBundle(system_prompt="grow-test"),
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
        capability_card=None,
        runtime_state=VacantState.ACTIVE,
    )


@pytest.fixture(autouse=True)
def _vacant_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("VACANT_HOME", str(home))
    return home


def _seed_peer(home: Path, name: str, endpoint: str) -> tuple[VacantId, Any]:
    """Drop a peer's meta.json under VACANT_HOME so `select_peer` finds it."""
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    ls.init_vacant(name)
    meta = ls.load_meta(name)
    meta.endpoint = endpoint
    ls.save_meta(name, meta)
    return vid, sk


# --- happy path --------------------------------------------------------------


@pytest.mark.asyncio
async def test_peer_review_tick_increments_sent_when_peer_answers(
    _vacant_home: Path,
) -> None:
    """If a peer is available and responds with a properly-signed
    envelope, the loop should bump `peer_reviews_sent`. The fake post
    has to *actually sign* with bob's key because `peer_review_tick`
    verifies the response signature against the advertised peer pubkey."""
    from datetime import UTC, datetime

    from vacant.core.types import EMPTY_PREV_HASH
    from vacant.protocol.envelope import (
        A2AMessage,
        A2APart,
        VacantEnvelope,
        to_a2a_jsonrpc,
    )

    ls.init_vacant("alice")
    ls.init_vacant("bob")
    bob_meta = ls.load_meta("bob")
    bob_meta.endpoint = "http://127.0.0.1:9999"
    ls.save_meta("bob", bob_meta)
    bob_vid = VacantId(pubkey_bytes=bytes.fromhex(bob_meta.vacant_id_hex))
    bob_sk = ls.load_signing_key("bob")
    alice_meta = ls.load_meta("alice")
    alice_vid = VacantId(pubkey_bytes=bytes.fromhex(alice_meta.vacant_id_hex))
    alice_sk = ls.load_signing_key("alice")

    async def _fake_post(url: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        # P2P review-ingest: peer_review_tick POSTs the signed review to
        # the peer's /reviews/ingest after a successful probe. Tests
        # don't need to verify ingest server logic here (covered by
        # test_runtime_peer_review), so short-circuit with an ack.
        if url.endswith("/reviews/ingest"):
            return 200, {"ok": True, "duplicate": False}
        # Construct a real signed response envelope from bob → alice.
        response_env = VacantEnvelope(
            from_vacant_id=bob_vid,
            to_vacant_id=alice_vid,
            sequence_no=1,
            timestamp=datetime.now(UTC),
            prev_envelope_hash=EMPTY_PREV_HASH,
            payload=A2AMessage(
                role="ROLE_AGENT",
                parts=[A2APart(text=f"echo from {bob_vid.short()}: probe")],
            ),
            idempotency_key="resp-1",
        ).signed(bob_sk)
        wire = to_a2a_jsonrpc(response_env)
        return 200, {
            "jsonrpc": "2.0",
            "id": "rsp",
            "result": {"message": wire["params"]["message"]},
        }

    loop = GrowLoop(
        self_form=_make_form(alice_vid),
        self_signing_key=alice_sk,
        peer_review_period_s=0.1,
        redteam_every_n_ticks=0,
        heartbeat_every_n_ticks=0,
        http_post=_fake_post,
    )
    await loop.tick()
    assert loop.stats.peer_reviews_sent == 1
    assert loop.stats.ticks_completed == 1


@pytest.mark.asyncio
async def test_peer_review_tick_skip_when_no_peer(_vacant_home: Path) -> None:
    """No siblings → tick should record `peer_reviews_skipped`."""
    ls.init_vacant("alice")
    alice_meta = ls.load_meta("alice")
    alice_vid = VacantId(pubkey_bytes=bytes.fromhex(alice_meta.vacant_id_hex))
    alice_sk = ls.load_signing_key("alice")

    loop = GrowLoop(
        self_form=_make_form(alice_vid),
        self_signing_key=alice_sk,
        redteam_every_n_ticks=0,
        heartbeat_every_n_ticks=0,
    )
    await loop.tick()
    assert loop.stats.peer_reviews_skipped == 1


@pytest.mark.asyncio
async def test_peer_review_tick_handles_http_failure(_vacant_home: Path) -> None:
    ls.init_vacant("alice")
    _seed_peer(_vacant_home, "bob", endpoint="http://127.0.0.1:9999")
    alice_meta = ls.load_meta("alice")
    alice_vid = VacantId(pubkey_bytes=bytes.fromhex(alice_meta.vacant_id_hex))
    alice_sk = ls.load_signing_key("alice")

    async def _broken_post(url: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        raise ConnectionError("peer down")

    loop = GrowLoop(
        self_form=_make_form(alice_vid),
        self_signing_key=alice_sk,
        redteam_every_n_ticks=0,
        heartbeat_every_n_ticks=0,
        http_post=_broken_post,
    )
    await loop.tick()
    # `peer_review_tick` returns a result with `error` set; our loop
    # increments `peer_reviews_failed`.
    assert loop.stats.peer_reviews_failed == 1


@pytest.mark.asyncio
async def test_heartbeat_appends_to_logbook(_vacant_home: Path) -> None:
    ls.init_vacant("alice")
    alice_meta = ls.load_meta("alice")
    alice_vid = VacantId(pubkey_bytes=bytes.fromhex(alice_meta.vacant_id_hex))
    alice_sk = ls.load_signing_key("alice")

    # Heartbeat every tick.
    loop = GrowLoop(
        self_form=_make_form(alice_vid),
        self_signing_key=alice_sk,
        redteam_every_n_ticks=0,
        heartbeat_every_n_ticks=1,
    )
    before = len(ls.load_logbook("alice").entries)
    await loop.tick()
    after = len(ls.load_logbook("alice").entries)
    assert after == before + 1
    assert loop.stats.heartbeats == 1


# --- redteam path -----------------------------------------------------------


@pytest.mark.asyncio
async def test_redteam_writes_signed_review_to_peer(_vacant_home: Path) -> None:
    """Every Nth tick the loop should send a redteam probe and the
    responder's reviews_received.jsonl should grow by one row tagged
    `source="redteam_probe"`."""
    ls.init_vacant("alice")
    _seed_peer(_vacant_home, "bob", endpoint="http://127.0.0.1:9999")
    alice_meta = ls.load_meta("alice")
    alice_vid = VacantId(pubkey_bytes=bytes.fromhex(alice_meta.vacant_id_hex))
    alice_sk = ls.load_signing_key("alice")

    captured_prompts: list[str] = []

    async def _refusal_post(url: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        # Capture the prompt + return a clean refusal so REFUSAL probes pass.
        prompt = body["params"]["message"]["parts"][0]["text"]
        captured_prompts.append(prompt)
        return 200, {
            "jsonrpc": "2.0",
            "id": "rsp",
            "result": {
                "message": {
                    "role": "ROLE_AGENT",
                    "parts": [{"type": "text", "text": "I can't help with that."}],
                }
            },
        }

    # Redteam on tick #1 — easiest to test.
    loop = GrowLoop(
        self_form=_make_form(alice_vid),
        self_signing_key=alice_sk,
        redteam_every_n_ticks=1,
        heartbeat_every_n_ticks=0,
        http_post=_refusal_post,
    )
    await loop.tick()
    assert loop.stats.redteam_probes_sent == 1
    assert captured_prompts  # we did send a probe
    reviews_file = _vacant_home / "bob" / "reviews_received.jsonl"
    assert reviews_file.exists()
    lines = [ln for ln in reviews_file.read_text(encoding="utf-8").splitlines() if ln]
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["source"] == "redteam_probe"
    assert rec["reviewer"] == alice_vid.hex()
    # Signature is a 64-byte Ed25519 sig as hex (128 chars).
    assert len(rec["signature_hex"]) == 128


@pytest.mark.asyncio
async def test_redteam_skips_when_no_peer(_vacant_home: Path) -> None:
    ls.init_vacant("alice")
    alice_meta = ls.load_meta("alice")
    alice_vid = VacantId(pubkey_bytes=bytes.fromhex(alice_meta.vacant_id_hex))
    alice_sk = ls.load_signing_key("alice")

    loop = GrowLoop(
        self_form=_make_form(alice_vid),
        self_signing_key=alice_sk,
        redteam_every_n_ticks=1,
        heartbeat_every_n_ticks=0,
    )
    await loop.tick()
    assert loop.stats.redteam_probes_sent == 0
    assert loop.stats.peer_reviews_skipped == 1


# --- stats shape ------------------------------------------------------------


# --- Phase 1: multi-tick chain (Bug A regression) ---------------------------


@pytest.mark.asyncio
async def test_multiple_ticks_each_increment_envelope_seq(_vacant_home: Path) -> None:
    """Regression for Pfix9 Bug A: a GrowLoop with the outbound replay
    store hooked up must send `seq=1, 2, 3, …` across consecutive ticks,
    so the recipient's replay store accepts every envelope.

    Without the fix every tick re-uses `seq=1` and the second one would
    be rejected. We capture the sequence numbers and assert they're
    strictly monotonic.
    """
    from datetime import UTC, datetime

    from vacant.core.types import EMPTY_PREV_HASH
    from vacant.protocol.envelope import (
        A2AMessage,
        A2APart,
        VacantEnvelope,
        from_a2a_jsonrpc,
        to_a2a_jsonrpc,
    )

    ls.init_vacant("alice")
    ls.init_vacant("bob")
    bob_meta = ls.load_meta("bob")
    bob_meta.endpoint = "http://127.0.0.1:9999"
    ls.save_meta("bob", bob_meta)
    bob_vid = VacantId(pubkey_bytes=bytes.fromhex(bob_meta.vacant_id_hex))
    bob_sk = ls.load_signing_key("bob")
    alice_meta = ls.load_meta("alice")
    alice_vid = VacantId(pubkey_bytes=bytes.fromhex(alice_meta.vacant_id_hex))
    alice_sk = ls.load_signing_key("alice")

    captured_seqs: list[int] = []

    async def _fake_post(url: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        if url.endswith("/reviews/ingest"):
            return 200, {"ok": True, "duplicate": False}
        # Capture the inbound seq from the metadata so we can assert
        # monotonicity AND construct a properly-signed response.
        env = from_a2a_jsonrpc(body)
        captured_seqs.append(env.sequence_no)
        # Build a real response envelope from bob.
        response_env = VacantEnvelope(
            from_vacant_id=bob_vid,
            to_vacant_id=alice_vid,
            sequence_no=env.sequence_no,
            timestamp=datetime.now(UTC),
            prev_envelope_hash=EMPTY_PREV_HASH,
            payload=A2AMessage(
                role="ROLE_AGENT",
                parts=[A2APart(text="echo back: " + env.payload.parts[0].text)],
            ),
            idempotency_key=f"rsp-{env.sequence_no}",
        ).signed(bob_sk)
        wire = to_a2a_jsonrpc(response_env)
        return 200, {
            "jsonrpc": "2.0",
            "id": "rsp",
            "result": {"message": wire["params"]["message"]},
        }

    loop = GrowLoop(
        self_form=_make_form(alice_vid),
        self_signing_key=alice_sk,
        redteam_every_n_ticks=0,
        heartbeat_every_n_ticks=0,
        http_post=_fake_post,
    )
    for _ in range(5):
        await loop.tick()
    # 5 ticks all delivered, sequence numbers strictly 1..5.
    assert captured_seqs == [1, 2, 3, 4, 5]
    assert loop.stats.peer_reviews_sent == 5
    assert loop.stats.peer_reviews_failed == 0


@pytest.mark.asyncio
async def test_redteam_shares_chain_with_peer_review(_vacant_home: Path) -> None:
    """A redteam probe and a peer-review probe on the same `(self →
    peer)` pair must share the outbound chain — otherwise the redteam
    probe re-uses an already-spent seq and the recipient rejects it."""
    from datetime import UTC, datetime

    from vacant.core.types import EMPTY_PREV_HASH
    from vacant.protocol.envelope import (
        A2AMessage,
        A2APart,
        VacantEnvelope,
        from_a2a_jsonrpc,
        to_a2a_jsonrpc,
    )

    ls.init_vacant("alice")
    ls.init_vacant("bob")
    bob_meta = ls.load_meta("bob")
    bob_meta.endpoint = "http://127.0.0.1:9999"
    ls.save_meta("bob", bob_meta)
    bob_vid = VacantId(pubkey_bytes=bytes.fromhex(bob_meta.vacant_id_hex))
    bob_sk = ls.load_signing_key("bob")
    alice_meta = ls.load_meta("alice")
    alice_vid = VacantId(pubkey_bytes=bytes.fromhex(alice_meta.vacant_id_hex))
    alice_sk = ls.load_signing_key("alice")

    captured: list[tuple[int, str]] = []

    async def _refusal_post(url: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        if url.endswith("/reviews/ingest"):
            return 200, {"ok": True, "duplicate": False}
        env = from_a2a_jsonrpc(body)
        captured.append((env.sequence_no, env.payload.parts[0].text))
        response_env = VacantEnvelope(
            from_vacant_id=bob_vid,
            to_vacant_id=alice_vid,
            sequence_no=env.sequence_no,
            timestamp=datetime.now(UTC),
            prev_envelope_hash=EMPTY_PREV_HASH,
            payload=A2AMessage(
                role="ROLE_AGENT",
                parts=[A2APart(text="I can't help with that.")],
            ),
            idempotency_key=f"rsp-{env.sequence_no}",
        ).signed(bob_sk)
        wire = to_a2a_jsonrpc(response_env)
        return 200, {
            "jsonrpc": "2.0",
            "id": "rsp",
            "result": {"message": wire["params"]["message"]},
        }

    # Alternating: peer review (tick 1), redteam (tick 2), peer review (3), …
    loop = GrowLoop(
        self_form=_make_form(alice_vid),
        self_signing_key=alice_sk,
        redteam_every_n_ticks=2,
        heartbeat_every_n_ticks=0,
        http_post=_refusal_post,
    )
    for _ in range(4):
        await loop.tick()
    # 4 envelopes total, all seq=1..4, both redteam + peer mixed.
    seqs = [c[0] for c in captured]
    assert seqs == [1, 2, 3, 4]
    assert loop.stats.peer_reviews_sent + loop.stats.redteam_probes_sent == 4


# --- Pfix9 §A: review_all_per_tick fan-out ---------------------------------


@pytest.mark.asyncio
async def test_review_all_per_tick_reviews_every_sibling(_vacant_home: Path) -> None:
    """With 3 vacants and `review_all_per_tick=True`, alice's single
    tick should send 2 peer-review probes (one to bob, one to carol),
    so `peer_reviews_sent` ends at 2 (not 1 like rotation mode)."""
    from datetime import UTC, datetime

    from vacant.core.types import EMPTY_PREV_HASH
    from vacant.protocol.envelope import (
        A2AMessage,
        A2APart,
        VacantEnvelope,
        from_a2a_jsonrpc,
        to_a2a_jsonrpc,
    )

    ls.init_vacant("alice")
    ls.init_vacant("bob")
    ls.init_vacant("carol")
    # Both peers need a serving endpoint to be eligible.
    for peer in ("bob", "carol"):
        meta = ls.load_meta(peer)
        meta.endpoint = f"http://127.0.0.1:{9000 + ord(peer[0])}"
        ls.save_meta(peer, meta)

    alice_meta = ls.load_meta("alice")
    alice_vid = VacantId(pubkey_bytes=bytes.fromhex(alice_meta.vacant_id_hex))
    alice_sk = ls.load_signing_key("alice")
    peer_keys = {
        peer: (
            VacantId(pubkey_bytes=bytes.fromhex(ls.load_meta(peer).vacant_id_hex)),
            ls.load_signing_key(peer),
        )
        for peer in ("bob", "carol")
    }

    delivered_targets: list[str] = []

    async def _fake_post(url: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        if url.endswith("/reviews/ingest"):
            return 200, {"ok": True, "duplicate": False}
        # Pull the to_vacant_id out of the metadata to know which peer
        # we're answering as.
        env = from_a2a_jsonrpc(body)
        to_hex = env.to_vacant_id.hex()
        peer_name, (peer_vid, peer_sk) = next(
            (name, kv) for name, kv in peer_keys.items() if kv[0].hex() == to_hex
        )
        delivered_targets.append(peer_name)
        response_env = VacantEnvelope(
            from_vacant_id=peer_vid,
            to_vacant_id=alice_vid,
            sequence_no=env.sequence_no,
            timestamp=datetime.now(UTC),
            prev_envelope_hash=EMPTY_PREV_HASH,
            payload=A2AMessage(
                role="ROLE_AGENT",
                parts=[A2APart(text=f"echo from {peer_name}")],
            ),
            idempotency_key=f"rsp-{env.sequence_no}",
        ).signed(peer_sk)
        wire = to_a2a_jsonrpc(response_env)
        return 200, {
            "jsonrpc": "2.0",
            "id": "rsp",
            "result": {"message": wire["params"]["message"]},
        }

    loop = GrowLoop(
        self_form=_make_form(alice_vid),
        self_signing_key=alice_sk,
        review_all_per_tick=True,
        redteam_every_n_ticks=0,
        heartbeat_every_n_ticks=0,
        enable_self_reputation_ingest=False,
        enable_auto_spawn=False,
        http_post=_fake_post,
    )
    await loop.tick()
    # 2 peers → 2 reviews sent in a single tick.
    assert loop.stats.peer_reviews_sent == 2
    assert sorted(delivered_targets) == ["bob", "carol"]


@pytest.mark.asyncio
async def test_review_all_per_tick_with_no_peers_skips(_vacant_home: Path) -> None:
    """Fan-out with zero siblings should record skip + not crash."""
    ls.init_vacant("alice")
    alice_meta = ls.load_meta("alice")
    alice_vid = VacantId(pubkey_bytes=bytes.fromhex(alice_meta.vacant_id_hex))
    alice_sk = ls.load_signing_key("alice")

    loop = GrowLoop(
        self_form=_make_form(alice_vid),
        self_signing_key=alice_sk,
        review_all_per_tick=True,
        redteam_every_n_ticks=0,
        heartbeat_every_n_ticks=0,
        enable_self_reputation_ingest=False,
        enable_auto_spawn=False,
    )
    await loop.tick()
    assert loop.stats.peer_reviews_skipped == 1


def test_grow_stats_as_dict_is_json_serialisable() -> None:
    """The `/grow/stats` HTTP endpoint returns this dict; make sure it
    round-trips through json without surprises."""
    stats = GrowStats(
        ticks_completed=10,
        peer_reviews_sent=4,
        peer_reviews_skipped=3,
        peer_reviews_failed=1,
        redteam_probes_sent=2,
        heartbeats=5,
        last_tick_at_ms=1_700_000_000_000,
    )
    out = stats.as_dict()
    json.dumps(out)  # must not raise
    assert out["peer_reviews_sent"] == 4
    assert out["last_error"] is None
    assert out["last_errors"] == []
    assert out["chain_resets"] == 0


def test_grow_stats_record_error_keeps_ring_buffer_bounded() -> None:
    """P3: record_error appends to a ring buffer capped at
    MAX_RECENT_ERRORS so an operator inspecting /grow/stats sees the
    recent failure history without paginating through hundreds of rows."""
    stats = GrowStats()
    for i in range(stats.MAX_RECENT_ERRORS + 3):
        stats.record_error("peer_review", f"to=bob: failure #{i}")
    assert len(stats.last_errors) == stats.MAX_RECENT_ERRORS
    # Oldest entries should have been pushed out.
    details = [e["detail"] for e in stats.last_errors]
    assert all("failure #" in d for d in details)
    assert details[0].endswith("failure #3")  # first 3 dropped
    assert details[-1].endswith(f"failure #{stats.MAX_RECENT_ERRORS + 2}")
    # last_error mirrors the newest entry for back-compat.
    assert stats.last_error == details[-1]


@pytest.mark.asyncio
async def test_chain_drift_auto_recovers_via_reset_endpoint(_vacant_home: Path) -> None:
    """P1c: when peer_review_tick fails with a chain-mismatch error,
    GrowLoop POSTs a signed RESET_CHAIN to the peer and seeds its local
    outbound store, so the next tick re-establishes the chain from
    seq=1. This is the recovery path that prevents permanently-broken
    peer-review links after a single drift event."""
    from datetime import UTC, datetime

    from vacant.core.types import EMPTY_PREV_HASH
    from vacant.protocol.envelope import (
        A2AMessage,
        A2APart,
        VacantEnvelope,
        from_a2a_jsonrpc,
        to_a2a_jsonrpc,
    )
    from vacant.protocol.replay_protect import InMemoryReplayStore, PairKey, ReplayState

    ls.init_vacant("alice")
    ls.init_vacant("bob")
    bob_meta = ls.load_meta("bob")
    bob_meta.endpoint = "http://127.0.0.1:9999"
    ls.save_meta("bob", bob_meta)
    bob_vid = VacantId(pubkey_bytes=bytes.fromhex(bob_meta.vacant_id_hex))
    bob_sk = ls.load_signing_key("bob")
    alice_meta = ls.load_meta("alice")
    alice_vid = VacantId(pubkey_bytes=bytes.fromhex(alice_meta.vacant_id_hex))
    alice_sk = ls.load_signing_key("alice")

    reset_envelopes: list[VacantEnvelope] = []

    async def _fake_post(url: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        if url.endswith("/a2a/chain/reset"):
            # Capture the reset envelope so the test can verify it's signed
            # and contains the RESET_CHAIN sentinel.
            reset_envelopes.append(from_a2a_jsonrpc(body))
            return 200, {"ok": True, "reset_for_peer": alice_vid.hex()}
        if url.endswith("/reviews/ingest"):
            return 200, {"ok": True, "duplicate": False}
        # First probe: simulate a drifted peer rejecting our envelope with
        # the canonical chain-mismatch error string the recovery logic
        # looks for. Probes after the reset succeed.
        if not reset_envelopes:
            return 409, {"detail": "non-monotonic sequence_no: expected 5, got 1"}
        # Post-reset: return a signed response so the loop proceeds normally.
        env = from_a2a_jsonrpc(body)
        response_env = VacantEnvelope(
            from_vacant_id=bob_vid,
            to_vacant_id=alice_vid,
            sequence_no=env.sequence_no,
            timestamp=datetime.now(UTC),
            prev_envelope_hash=EMPTY_PREV_HASH,
            payload=A2AMessage(role="ROLE_AGENT", parts=[A2APart(text="echo back: probe")]),
            idempotency_key=f"rsp-{env.sequence_no}",
        ).signed(bob_sk)
        return 200, {
            "jsonrpc": "2.0",
            "id": "rsp",
            "result": {"message": to_a2a_jsonrpc(response_env)["params"]["message"]},
        }

    loop = GrowLoop(
        self_form=_make_form(alice_vid),
        self_signing_key=alice_sk,
        redteam_every_n_ticks=0,
        heartbeat_every_n_ticks=0,
        enable_self_reputation_ingest=False,
        enable_auto_spawn=False,
        http_post=_fake_post,
    )
    # Pre-poison: pretend alice's outbound to bob is already at seq=99 so
    # the first probe goes out with a "wrong" seq, triggering the simulated
    # remote rejection.
    store = loop._ensure_outbound_replay()
    store.seed(
        PairKey(from_vid=alice_vid, to_vid=bob_vid),
        ReplayState(last_sequence_no=99, chain_tip=b"\x11" * 32),
    )

    await loop.tick()

    # Tick 1: probe fails with chain mismatch → recovery POSTs reset.
    assert loop.stats.peer_reviews_failed == 1
    assert loop.stats.chain_resets == 1
    assert len(reset_envelopes) == 1
    reset = reset_envelopes[0]
    assert " ".join(p.text for p in reset.payload.parts) == "RESET_CHAIN"
    assert reset.from_vacant_id.hex() == alice_vid.hex()
    # And alice's local outbound store for (alice, bob) is back to (0, EMPTY).
    state = await store.get(PairKey(from_vid=alice_vid, to_vid=bob_vid))
    assert state.last_sequence_no == 0
    assert state.chain_tip == EMPTY_PREV_HASH
    # last_errors ring buffer captured the underlying chain error too.
    assert any("non-monotonic" in e["detail"] for e in loop.stats.last_errors)

    await loop.tick()
    # Tick 2: probe now uses seq=1, mock returns success → sent counter bumps.
    assert loop.stats.peer_reviews_sent >= 1
