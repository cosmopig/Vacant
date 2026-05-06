"""Shared fixtures for unit / property / integration tests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import keyring
import pytest
import pytest_asyncio
from keyring.backend import KeyringBackend
from sqlalchemy.ext.asyncio import create_async_engine

from vacant.core.crypto import SigningKey, VerifyKey, keygen
from vacant.core.types import Logbook
from vacant.registry import RegistryStore


class _InMemoryKeyring(KeyringBackend):
    """In-memory keyring backend for tests.

    The default `keyring` backend on a CI host (no DBus, no Keychain)
    is `keyring.backends.fail.Keyring`, which raises on every call.
    Tests that exercise `vacant.cli.local_store.init_vacant` need a
    real backend or they all fail. This fake stores a per-test
    `(service, username) -> password` dict with the `priority`
    required by the keyring backend protocol.
    """

    priority = 1.0

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self._store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self._store[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self._store.pop((service, username), None)


@pytest.fixture(autouse=True)
def fake_keyring_backend(monkeypatch: pytest.MonkeyPatch) -> Iterator[_InMemoryKeyring]:
    """Replace the system keyring with a per-test in-memory backend.

    Auto-applied so any test that touches `local_store.init_vacant`
    (or anything else that calls `keyring.set_password` /
    `get_password`) gets deterministic, isolated key storage. Tests
    that need to exercise the *no-backend-available* path can opt out
    by re-monkeypatching `keyring.set_keyring` to the fail backend
    inside the test body.
    """
    fake = _InMemoryKeyring()
    keyring.set_keyring(fake)
    yield fake
    # `keyring.set_keyring(None)` would force re-detection of the host
    # default; safer to leave the fake installed for the next test —
    # the fixture re-runs per-test so each gets a fresh dict.


@pytest.fixture
def test_keypair() -> tuple[SigningKey, VerifyKey]:
    """Fresh Ed25519 keypair, regenerated each test."""
    return keygen()


@pytest.fixture
def fresh_logbook() -> Logbook:
    """Empty `Logbook` ready for `.append()` calls."""
    return Logbook()


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Iterator[Path]:
    """Path to an unopened SQLite file in a per-test tmp dir."""
    db = tmp_path / "vacant_test.db"
    yield db


@pytest_asyncio.fixture
async def registry_store() -> AsyncIterator[RegistryStore]:
    """Fresh in-memory `RegistryStore`. Schema initialised."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    store = RegistryStore(engine)
    await store.init_schema()
    try:
        yield store
    finally:
        await engine.dispose()
