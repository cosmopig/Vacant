"""Shared fixtures for unit / property / integration tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from vacant.core.crypto import SigningKey, VerifyKey, keygen
from vacant.core.types import Logbook


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
