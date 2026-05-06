"""Shared fixtures for unit / property / integration tests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine

from vacant.core.crypto import SigningKey, VerifyKey, keygen
from vacant.core.types import Logbook
from vacant.registry import RegistryStore


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
