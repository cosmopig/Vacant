"""CLI smoke + regression tests.

F4 acceptance: every previously-stubbed subcommand now performs a
real action (`init` writes a keypair, `status` reads disk, etc).
Tests cover the local-disk subcommands; tests that need a live
registry HTTP server live in `tests/integration/`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from vacant.cli import app
from vacant.cli import local_store as ls


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


def test_help_lists_all_subcommands(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in (
        "init",
        "status",
        "heartbeat",
        "call",
        "publish",
        "unpublish",
        "lineage",
        "attest",
        "demo",
    ):
        assert cmd in result.stdout


def test_init_writes_key_logbook_meta(runner: CliRunner, isolated_vacant_home: Path) -> None:
    result = runner.invoke(app, ["init", "alice"])
    assert result.exit_code == 0, result.stdout
    data = json.loads(result.stdout)
    assert data["name"] == "alice"
    assert len(data["vacant_id"]) == 64

    d = isolated_vacant_home / "alice"
    assert (d / "key.json").exists()
    assert (d / "logbook.jsonl").exists()
    assert (d / "meta.json").exists()
    # Genesis entry is present.
    lb = ls.load_logbook("alice")
    assert len(lb.entries) == 1
    assert lb.entries[0].kind == "GENESIS"
    # Logbook chain verifies under the loaded pubkey.
    sk = ls.load_signing_key("alice")
    assert lb.verify_chain(sk.verify_key)


def test_init_rejects_duplicate(runner: CliRunner) -> None:
    runner.invoke(app, ["init", "alice"])
    r = runner.invoke(app, ["init", "alice"])
    assert r.exit_code == 1


def test_init_rejects_path_traversal(runner: CliRunner) -> None:
    r = runner.invoke(app, ["init", "../escape"])
    assert r.exit_code == 1


def test_status_reports_local_vacants(runner: CliRunner) -> None:
    runner.invoke(app, ["init", "alice"])
    runner.invoke(app, ["init", "bob"])
    r = runner.invoke(app, ["status"])
    assert r.exit_code == 0
    data = json.loads(r.stdout)
    names = sorted(v["name"] for v in data["vacants"])
    assert names == ["alice", "bob"]
    assert all(v["state"] == "LOCAL" for v in data["vacants"])


def test_status_filters_archived_unless_all(runner: CliRunner) -> None:
    runner.invoke(app, ["init", "alice"])
    meta = ls.load_meta("alice")
    meta.state = "ARCHIVED"
    ls.save_meta("alice", meta)
    r = runner.invoke(app, ["status"])
    assert r.exit_code == 0
    assert json.loads(r.stdout)["vacants"] == []
    r = runner.invoke(app, ["status", "--all"])
    assert json.loads(r.stdout)["vacants"][0]["state"] == "ARCHIVED"


def test_heartbeat_appends_signed_entry(runner: CliRunner) -> None:
    runner.invoke(app, ["init", "alice"])
    r = runner.invoke(app, ["heartbeat"])
    assert r.exit_code == 0
    data = json.loads(r.stdout)
    assert data["kind"] == "HEARTBEAT"
    assert data["logbook_entries"] == 2
    # Chain still verifies.
    sk = ls.load_signing_key("alice")
    lb = ls.load_logbook("alice")
    assert lb.verify_chain(sk.verify_key)


def test_heartbeat_archived_rejects(runner: CliRunner) -> None:
    runner.invoke(app, ["init", "alice"])
    meta = ls.load_meta("alice")
    meta.state = "ARCHIVED"
    ls.save_meta("alice", meta)
    r = runner.invoke(app, ["heartbeat"])
    assert r.exit_code == 2


def test_unpublish_flips_state(runner: CliRunner) -> None:
    runner.invoke(app, ["init", "alice"])
    meta = ls.load_meta("alice")
    meta.state = "ACTIVE"
    meta.halo_published = True
    ls.save_meta("alice", meta)
    r = runner.invoke(app, ["unpublish"])
    assert r.exit_code == 0
    after = ls.load_meta("alice")
    assert after.state == "LOCAL"
    assert after.halo_published is False


def test_attest_signs_and_records(runner: CliRunner, isolated_vacant_home: Path) -> None:
    runner.invoke(app, ["init", "alice"])
    runner.invoke(app, ["init", "bob"])
    bob_meta = ls.load_meta("bob")
    r = runner.invoke(app, ["attest", bob_meta.vacant_id_hex, "is-honest", "--name", "alice"])
    assert r.exit_code == 0, r.stdout
    record = json.loads(r.stdout)
    assert record["claim"] == "is-honest"
    assert record["attestee"] == bob_meta.vacant_id_hex
    out_path = isolated_vacant_home / "alice" / "attestations_issued.jsonl"
    assert out_path.exists()
    assert "is-honest" in out_path.read_text()


def test_current_name_resolves_singleton(runner: CliRunner) -> None:
    runner.invoke(app, ["init", "alice"])
    # No VACANT_NAME → singleton resolution.
    r = runner.invoke(app, ["heartbeat"])
    assert r.exit_code == 0


def test_current_name_requires_disambiguation(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner.invoke(app, ["init", "alice"])
    runner.invoke(app, ["init", "bob"])
    # Two vacants, no VACANT_NAME — should error.
    monkeypatch.delenv("VACANT_NAME", raising=False)
    r = runner.invoke(app, ["heartbeat"])
    assert r.exit_code == 2


def test_publish_requires_registry_url(runner: CliRunner) -> None:
    runner.invoke(app, ["init", "alice"])
    r = runner.invoke(app, ["publish", "--capability", "echo"])
    assert r.exit_code == 2
    assert "registry" in r.stdout.lower() or "registry" in (r.stderr or "").lower()


def test_lineage_requires_registry_url(runner: CliRunner) -> None:
    r = runner.invoke(app, ["lineage", "00" * 32])
    assert r.exit_code == 2


def test_demo_command_runs_scenario(runner: CliRunner) -> None:
    """`vacant demo` is no longer a stub — it delegates to vacant.mvp.demo.
    Also verifies hyphen normalization (Bug 3): `law-firm` → `law_firm`."""
    result = runner.invoke(app, ["demo", "law-firm", "--seed", "42"])
    assert result.exit_code == 0
    assert '"name": "law_firm"' in result.stdout
    assert '"logbook_chains_ok": true' in result.stdout
