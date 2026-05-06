"""Regression tests for codex round-3 final blockers (F-A / F-B / F-C / F-D).

Each section pins one finding to a concrete attack scenario + the
defense that closes it.

* **F-A**: halo publish was a TOCTOU — vacant row landed first, audit
  event submitted after. A failed `submit_event` left a publicly-active
  halo with no audit chain entry.
* **F-B**: registry `submit_event` only had an in-process
  `asyncio.Lock`; multi-worker hosts could race and accept two events
  with the same `(actor_vacant_id, actor_seq)`.
* **F-C**: protocol `replay_protect` used the same in-process lock + a
  read-then-update pattern; concurrent envelope acceptance under the
  same `sequence_no` was possible.
* **F-D**: `vacant init` wrote the Ed25519 seed in plaintext to
  `key.json`. Refused to do so by default after F-D — opt in via
  `--insecure-demo`.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import keyring
import pytest
from keyring.backend import KeyringBackend
from sqlalchemy.ext.asyncio import create_async_engine
from typer.testing import CliRunner

from vacant.cli import app
from vacant.cli import local_store as ls
from vacant.core.crypto import SigningKey, hash_blake2b, keygen, sign
from vacant.core.types import (
    CapabilityCard,
    SubstrateSpec,
    VacantId,
    VacantState,
)
from vacant.protocol import A2AMessage, A2APart
from vacant.protocol.envelope import VacantEnvelope
from vacant.protocol.errors import ReplayDetectedError
from vacant.protocol.replay_protect import SqliteReplayStore
from vacant.registry.antitamper import canonical_event_bytes
from vacant.registry.errors import IdempotencyConflict, SequenceMonotonicityError
from vacant.registry.halo import publish_halo
from vacant.registry.models import Vacant
from vacant.registry.store import RegistryStore, SignedEventDraft, now_ms

# --- shared helpers ----------------------------------------------------------


class _NoLock:
    """Async context manager that's reusable and never blocks. Used to
    swap out an `asyncio.Lock` so race tests can genuinely race."""

    async def __aenter__(self) -> _NoLock:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


def _make_card(sk: SigningKey) -> CapabilityCard:
    vk = sk.verify_key
    vid = VacantId.from_verify_key(vk)
    card = CapabilityCard(
        vacant_id=vid,
        capability_text="test capability",
        substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
        endpoint="http://example.invalid/",
    )
    return card.signed(sk)


async def _fresh_store() -> tuple[RegistryStore, object]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    store = RegistryStore(engine)
    await store.init_schema()
    return store, engine


# --- F-A: halo publish is atomic --------------------------------------------


@pytest.mark.asyncio
async def test_fa_halo_publish_atomic_on_event_failure() -> None:
    """If `submit_event` raises during `publish_halo`, the vacant row
    must NOT survive — otherwise the publicly-visible state and the
    audit chain would diverge."""
    store, engine = await _fresh_store()
    try:
        sk, _vk = keygen()
        card = _make_card(sk)

        # Force `submit_event` to fail by patching the inner helper.
        async def _boom(*_a: object, **_k: object) -> object:
            raise RuntimeError("simulated submit_event failure")

        original = store._submit_event_in_session
        store._submit_event_in_session = _boom  # type: ignore[assignment]

        with pytest.raises(RuntimeError, match="simulated"):
            await publish_halo(
                store=store,
                card=card,
                runtime_state=VacantState.ACTIVE,
                signing_key=sk,
            )

        # Recover for downstream sanity checks.
        store._submit_event_in_session = original  # type: ignore[assignment]

        # Vacant row was rolled back: no public halo persisted.
        assert await store.get_vacant(card.vacant_id.hex()) is None
        # Audit chain has no `register` event for this vacant.
        last = await store.latest_event_for_actor(card.vacant_id.hex())
        assert last is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_fa_halo_publish_happy_path_lands_both() -> None:
    """Sanity check: the atomic helper's success path leaves both the
    vacant row and the audit event in place."""
    store, engine = await _fresh_store()
    try:
        sk, _vk = keygen()
        card = _make_card(sk)
        record = await publish_halo(
            store=store,
            card=card,
            runtime_state=VacantState.ACTIVE,
            signing_key=sk,
        )
        assert record.event_seq > 0
        v = await store.get_vacant(card.vacant_id.hex())
        assert v is not None and v.status == "active"
        last = await store.latest_event_for_actor(card.vacant_id.hex())
        assert last is not None and last.event_type == "register"
    finally:
        await engine.dispose()


# --- F-B: registry event UNIQUE on (actor_vacant_id, actor_seq) -------------


def _build_signed_draft(
    *, sk: SigningKey, vid: VacantId, actor_seq: int, ts: int
) -> SignedEventDraft:
    """Build a register-style event draft signed for `actor_seq`."""
    payload: dict[str, object] = {
        "vacant_id": vid.hex(),
        "card_hash": hash_blake2b(b"x").hex(),
        "halo_version": 1,
        "visibility": "PUBLIC",
    }
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload_hash = hash_blake2b(payload_bytes)
    idempotency_key = f"register:{vid.hex()}:{ts}:seq{actor_seq}"
    canonical = canonical_event_bytes(
        event_type="register",
        actor_vacant_id=vid.hex(),
        subject_vacant_id=None,
        payload_hash=payload_hash,
        idempotency_key=idempotency_key,
        signed_by_pubkey=vid.pubkey_bytes,
        ts=ts,
        actor_seq=actor_seq,
    )
    sig = sign(sk, canonical)
    return SignedEventDraft(
        event_type="register",
        actor_vacant_id=vid.hex(),
        subject_vacant_id=None,
        payload=payload,
        idempotency_key=idempotency_key,
        signed_by_pubkey=vid.pubkey_bytes,
        signature=sig,
        actor_seq=actor_seq,
        ts=ts,
    )


@pytest.mark.asyncio
async def test_fb_concurrent_writes_same_actor_seq_one_loses() -> None:
    """Two coroutines submitting events with the same `actor_seq`
    after both passing the in-process lock must surface
    `SequenceMonotonicityError` for the loser via the DB-level
    UNIQUE constraint, not silently both-accept."""
    store, engine = await _fresh_store()
    try:
        sk, vk = keygen()
        vid = VacantId.from_verify_key(vk)
        # Pre-register the actor so the cross-actor guard passes.
        await store.insert_vacant(
            Vacant(
                vacant_id=vid.hex(),
                public_key=vid.pubkey_bytes,
                base_model="x",
                base_model_family="x",
                version="0",
                declared_capabilities_json=json.dumps([]),
                capability_card_hash=b"\x00" * 32,
                capability_card_sig=b"\x00",
                capability_card_blob=b"",
                registered_at=now_ms(),
            )
        )

        ts = now_ms()
        # Two competing drafts at actor_seq=1, with distinct idempotency
        # keys (otherwise idempotency would short-circuit).
        draft_a = _build_signed_draft(sk=sk, vid=vid, actor_seq=1, ts=ts)
        draft_b = _build_signed_draft(sk=sk, vid=vid, actor_seq=1, ts=ts + 1)

        # Drop the in-process lock to genuinely race the inserts — the
        # only line of defense is now the DB-level UNIQUE constraint
        # on `(actor_vacant_id, actor_seq)`.
        store._write_lock = _NoLock()  # type: ignore[assignment]

        async def _try(draft: SignedEventDraft) -> str:
            try:
                await store.submit_event(draft)
                return "ok"
            except SequenceMonotonicityError:
                return "monotonicity"
            except IdempotencyConflict:
                return "idempotency"

        outcomes = await asyncio.gather(_try(draft_a), _try(draft_b), return_exceptions=False)
        # Exactly one must succeed; the other must report the race
        # via SequenceMonotonicityError.
        assert sorted(outcomes) == ["monotonicity", "ok"], outcomes
    finally:
        await engine.dispose()


# --- F-C: replay store PK on (from, to, sequence_no) ------------------------


def _make_envelope(
    *,
    sk: SigningKey,
    frm: VacantId,
    to: VacantId,
    seq: int,
    body_text: str = "hello",
    prev: bytes | None = None,
) -> VacantEnvelope:
    return VacantEnvelope(
        from_vacant_id=frm,
        to_vacant_id=to,
        sequence_no=seq,
        timestamp=datetime(2026, 5, 6, tzinfo=UTC),
        prev_envelope_hash=prev or b"\x00" * 32,
        payload=A2AMessage(parts=[A2APart(text=body_text)]),
    ).signed(sk)


@pytest.mark.asyncio
async def test_fc_concurrent_envelope_acceptance_one_loses() -> None:
    """Two coroutines concurrently advancing the same pair to the same
    `sequence_no` must produce one success + one `ReplayDetectedError`
    via the `(from, to, seq)` PK collision."""
    sk_a, vk_a = keygen()
    sk_b, vk_b = keygen()
    frm = VacantId.from_verify_key(vk_a)
    to = VacantId.from_verify_key(vk_b)
    _ = sk_b

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        store = SqliteReplayStore(engine)
        await store.init_schema()

        # Two genuinely-distinct envelopes claiming the same seq=1
        # (legitimate for a fresh pair). Different `body_text` so they
        # have distinct envelope hashes and aren't the same envelope.
        env_a = _make_envelope(sk=sk_a, frm=frm, to=to, seq=1, body_text="a")
        env_b = _make_envelope(sk=sk_a, frm=frm, to=to, seq=1, body_text="b")

        # Drop the in-process lock so the race is genuine — the only
        # defense left is the PK uniqueness on `(from, to, seq)`.
        store._lock = _NoLock()  # type: ignore[assignment]

        async def _try(env: VacantEnvelope) -> str:
            try:
                await store.check_and_advance(env)
                return "ok"
            except ReplayDetectedError:
                return "replay"

        outcomes = await asyncio.gather(_try(env_a), _try(env_b))
        assert sorted(outcomes) == ["ok", "replay"], outcomes
    finally:
        await engine.dispose()


# --- F-D: keyring storage default; --insecure-demo opt-in -------------------


class _FailKeyring(KeyringBackend):
    """Mimics `keyring.backends.fail.Keyring` for opt-out tests."""

    priority = 1.0

    def get_password(self, service: str, username: str) -> str | None:
        raise RuntimeError("no backend")

    def set_password(self, service: str, username: str, password: str) -> None:
        raise RuntimeError("no backend")

    def delete_password(self, service: str, username: str) -> None:
        raise RuntimeError("no backend")


@pytest.fixture(autouse=False)
def disable_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    """Override the autouse keyring fixture: simulate a host with no
    working backend by reporting `keyring_backend_available()` False."""
    monkeypatch.setattr(ls, "keyring_backend_available", lambda: False)


@pytest.fixture
def isolated_vacant_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("VACANT_HOME", str(home))
    monkeypatch.delenv("VACANT_NAME", raising=False)
    return home


def test_fd_init_without_keyring_backend_fails_without_flag(
    runner: CliRunner,
    isolated_vacant_home: Path,
    disable_keyring: None,
) -> None:
    """No keyring + no `--insecure-demo` ⇒ refuse to write the seed."""
    result = runner.invoke(app, ["init", "alice"])
    assert result.exit_code == 1, result.output
    assert "keyring" in result.output.lower()
    # Directory must not exist — failed init leaves no partial state.
    assert not (isolated_vacant_home / "alice").exists()


def test_fd_init_with_insecure_demo_writes_plaintext_with_warning(
    runner: CliRunner,
    isolated_vacant_home: Path,
    disable_keyring: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--insecure-demo` ⇒ plaintext seed_hex on disk + a stderr WARN.

    Capture stderr separately via `capsys` rather than relying on
    `CliRunner` (Typer / Click versions disagree on whether stderr is
    captured into `result.output` or kept separate).
    """
    result = runner.invoke(app, ["init", "alice", "--insecure-demo"])
    assert result.exit_code == 0, result.output
    captured = capsys.readouterr()

    key_file = isolated_vacant_home / "alice" / "key.json"
    assert key_file.exists()
    obj = json.loads(key_file.read_text())
    assert "seed_hex" in obj  # plaintext seed present
    assert obj["key_storage"] == "plaintext"
    # Mode 0600 — protect against other users on the host.
    assert (key_file.stat().st_mode & 0o777) == 0o600
    # WARN went to stderr.
    combined = captured.out + captured.err + result.output
    assert "WARN" in combined
    assert "insecure" in combined.lower()
    # Meta records the storage mode for `load_signing_key` to consume.
    meta = ls.load_meta("alice")
    assert meta.key_storage == "plaintext"


def test_fd_init_with_keyring_writes_pubkey_only(
    runner: CliRunner,
    isolated_vacant_home: Path,
) -> None:
    """Default path: seed lives in (fake) keyring, key.json carries
    only the pubkey + storage discriminator."""
    result = runner.invoke(app, ["init", "alice"])
    assert result.exit_code == 0, result.stdout
    key_file = isolated_vacant_home / "alice" / "key.json"
    obj = json.loads(key_file.read_text())
    assert "seed_hex" not in obj
    assert obj["key_storage"] == "keyring"
    # Reload via `load_signing_key`: pulls from keyring.
    sk = ls.load_signing_key("alice")
    # The seed in the fake keyring matches the freshly-loaded key.
    seed = keyring.get_password(ls.KEYRING_SERVICE, "alice")
    assert seed is not None
    assert SigningKey(bytes.fromhex(seed)).verify_key == sk.verify_key


def test_fd_load_signing_key_legacy_plaintext_still_works(
    isolated_vacant_home: Path,
) -> None:
    """A `key.json` written before F-D landed (no `key_storage` field,
    has `seed_hex`) must keep loading. Treat it as plaintext."""
    sk, vk = keygen()
    vid = VacantId.from_verify_key(vk)
    d = isolated_vacant_home / "alice"
    d.mkdir()
    (d / "key.json").write_text(
        json.dumps({"pubkey_hex": vid.hex(), "seed_hex": bytes(sk).hex()}, sort_keys=True)
    )
    os.chmod(d / "key.json", 0o600)
    # meta.json is required by load_meta — write a minimal one.
    from vacant.cli.local_store import LocalMeta

    ls.save_meta(
        "alice",
        LocalMeta(
            vacant_id_hex=vid.hex(),
            state="LOCAL",
            created_at="2026-05-06T00:00:00+00:00",
            # key_storage defaults to "plaintext" (back-compat).
        ),
    )

    loaded = ls.load_signing_key("alice")
    assert loaded.verify_key == sk.verify_key


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()
