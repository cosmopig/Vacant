"""CLI tests for `vacant registry …` subcommands — anchor, witness, OTS.

The subcommands operate on a local SQLite registry DB, so each test
seals at least one epoch through `RegistryStore` before exercising the
CLI. Tests run synchronously via Typer's `CliRunner`; the async store
runs inside each command via `asyncio.run`.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from typer.testing import CliRunner

from vacant.cli import app
from vacant.core.crypto import keygen
from vacant.core.types import CapabilityCard, SubstrateSpec, VacantId, VacantState
from vacant.registry import (
    RegistryStore,
    issue_witness_cosignature,
    publish_halo,
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


def _seal_an_epoch(db_path: Path) -> tuple[int, bytes]:
    """Stand up a fresh registry at `db_path`, publish a halo, seal an
    epoch, and return `(epoch_id, root_hash)`."""

    async def _go() -> tuple[int, bytes]:
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        store = RegistryStore(engine)
        await store.init_schema()
        sk, vk = keygen()
        card = CapabilityCard(
            vacant_id=VacantId.from_verify_key(vk),
            capability_text="x",
            substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
        ).signed(sk)
        await publish_halo(store=store, card=card, runtime_state=VacantState.ACTIVE, signing_key=sk)
        epoch = await store.seal_epoch(signing_key=sk)
        await engine.dispose()
        return int(epoch.epoch_id or 0), epoch.root_hash

    return asyncio.run(_go())


def test_registry_help_lists_subcommands(runner: CliRunner) -> None:
    result = runner.invoke(app, ["registry", "--help"])
    assert result.exit_code == 0
    for cmd in (
        "anchor",
        "witness-statement",
        "witness-cosign",
        "witnesses",
        "verify-quorum",
        "ots-upgrade",
    ):
        assert cmd in result.stdout


def test_witness_statement_prints_hex(runner: CliRunner, tmp_path: Path) -> None:
    db = tmp_path / "reg.db"
    epoch_id, root = _seal_an_epoch(db)
    result = runner.invoke(app, ["registry", "witness-statement", str(epoch_id), "--db", str(db)])
    assert result.exit_code == 0, result.stdout
    parsed = json.loads(result.stdout)
    assert parsed["epoch_id"] == epoch_id
    assert parsed["root_hex"] == root.hex()
    assert len(parsed["statement_hex"]) == 64  # BLAKE2b digest, 32 bytes hex


def test_witness_statement_missing_epoch_fails(runner: CliRunner, tmp_path: Path) -> None:
    db = tmp_path / "reg.db"
    _seal_an_epoch(db)
    result = runner.invoke(app, ["registry", "witness-statement", "9999", "--db", str(db)])
    assert result.exit_code != 0


def test_witness_cosign_and_quorum_round_trip(runner: CliRunner, tmp_path: Path) -> None:
    db = tmp_path / "reg.db"
    epoch_id, _root = _seal_an_epoch(db)

    # Initialise a local vacant (gives us a keypair on disk).
    init_res = runner.invoke(app, ["init", "alice"])
    assert init_res.exit_code == 0, init_res.stdout
    alice = json.loads(init_res.stdout)
    alice_pubkey_hex = alice["vacant_id"]

    cosign_res = runner.invoke(
        app,
        [
            "registry",
            "witness-cosign",
            str(epoch_id),
            "--db",
            str(db),
            "--name",
            "alice",
            "--witness-id",
            "alice-witness",
        ],
    )
    assert cosign_res.exit_code == 0, cosign_res.stdout
    cos = json.loads(cosign_res.stdout)
    assert cos["witness_id"] == "alice-witness"
    assert cos["witness_pubkey_hex"] == alice_pubkey_hex

    # `witnesses` should now list the row.
    ls_res = runner.invoke(app, ["registry", "witnesses", str(epoch_id), "--db", str(db)])
    assert ls_res.exit_code == 0, ls_res.stdout
    rows = json.loads(ls_res.stdout)
    assert len(rows) == 1
    assert rows[0]["witness_pubkey_hex"] == alice_pubkey_hex

    # 1-of-1 quorum with alice should be satisfied.
    quorum_res = runner.invoke(
        app,
        [
            "registry",
            "verify-quorum",
            str(epoch_id),
            "--db",
            str(db),
            "--threshold",
            "1",
            "--rootset",
            alice_pubkey_hex,
        ],
    )
    assert quorum_res.exit_code == 0, quorum_res.stdout
    out = json.loads(quorum_res.stdout)
    assert out["quorum_satisfied"] is True


def test_verify_quorum_returns_nonzero_when_insufficient(runner: CliRunner, tmp_path: Path) -> None:
    db = tmp_path / "reg.db"
    epoch_id, _root = _seal_an_epoch(db)
    init_res = runner.invoke(app, ["init", "alice"])
    assert init_res.exit_code == 0, init_res.stdout

    # Need 2 cosignatures from an unrelated rootset → quorum unsatisfied.
    bogus_pubkey = ("aa" * 32) + "," + ("bb" * 32)
    quorum_res = runner.invoke(
        app,
        [
            "registry",
            "verify-quorum",
            str(epoch_id),
            "--db",
            str(db),
            "--threshold",
            "2",
            "--rootset",
            bogus_pubkey,
        ],
    )
    assert quorum_res.exit_code != 0
    out = json.loads(quorum_res.stdout)
    assert out["quorum_satisfied"] is False


def test_ots_upgrade_replaces_pending(runner: CliRunner, tmp_path: Path) -> None:
    """End-to-end: seal an epoch with `ots_anchor=True`, then drop in a
    fake `.ots` proof via the CLI and confirm the digest is recorded."""
    db = tmp_path / "reg.db"

    async def _seal_with_ots() -> int:
        engine = create_async_engine(f"sqlite+aiosqlite:///{db}")
        store = RegistryStore(engine)
        await store.init_schema()
        sk, vk = keygen()
        card = CapabilityCard(
            vacant_id=VacantId.from_verify_key(vk),
            capability_text="x",
            substrate_spec=SubstrateSpec(allowed_substrates=["mock"]),
        ).signed(sk)
        await publish_halo(store=store, card=card, runtime_state=VacantState.ACTIVE, signing_key=sk)
        epoch = await store.seal_epoch(signing_key=sk, ots_anchor=True)
        await engine.dispose()
        return int(epoch.epoch_id or 0)

    epoch_id = asyncio.run(_seal_with_ots())
    # Mock `.ots` file: real OTS magic header + opaque body.
    from vacant.registry.ots_anchor import OTS_UPGRADED_MAGIC

    proof_path = tmp_path / "epoch.ots"
    proof_path.write_bytes(OTS_UPGRADED_MAGIC + b"\xff" * 64)
    result = runner.invoke(
        app,
        [
            "registry",
            "ots-upgrade",
            str(epoch_id),
            "--db",
            str(db),
            "--proof",
            str(proof_path),
        ],
    )
    assert result.exit_code == 0, result.stdout
    out = json.loads(result.stdout)
    assert out["epoch_id"] == epoch_id
    assert len(out["ots_proof_hash_hex"]) == 64
    assert out["ots_upgraded_at"] > 0


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_anchor_records_commit_sha(runner: CliRunner, tmp_path: Path) -> None:
    db = tmp_path / "reg.db"
    epoch_id, _root = _seal_an_epoch(db)
    repo = tmp_path / "transparency"
    result = runner.invoke(
        app,
        [
            "registry",
            "anchor",
            str(epoch_id),
            "--db",
            str(db),
            "--repo",
            str(repo),
        ],
    )
    assert result.exit_code == 0, result.stdout
    out = json.loads(result.stdout)
    assert out["epoch_id"] == epoch_id
    assert len(out["commit_sha"]) == 40
    assert (repo / "epochs" / f"{epoch_id:08d}.json").exists()


# Silence "unused import" — issue_witness_cosignature is re-exported as proof
# the CLI's witness-cosign path uses the same code path tests already cover.
_ = issue_witness_cosignature
