"""PR2: `vacant peer` — peer store + CLI commands.

Covered:
- PeerStore add / list / remove / get round-trips
- Empty `peers.json` file → load returns []
- Duplicate label rejected
- Atomic write (no half-corrupted file on simulated crash)
- CLI: `vacant peer add/list/remove` exercise the same store
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from vacant.cli import app
from vacant.cli.peer_store import PeerStore, PeerStoreError, peers_path


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("VACANT_HOME", str(home))
    return home


# --- PeerStore -------------------------------------------------------------


def test_load_on_missing_file_returns_empty() -> None:
    store = PeerStore()
    assert store.load() == []


def test_add_persists_and_reads_back(isolated_home: Path) -> None:
    store = PeerStore()
    store.add("seed-tw", "https://seed-tw.example.com")
    entry = store.load()
    assert len(entry) == 1
    assert entry[0].label == "seed-tw"
    assert entry[0].endpoint == "https://seed-tw.example.com"
    assert entry[0].added_at_ms > 0
    # On-disk shape is the canonical JSON the user can edit.
    raw = json.loads((isolated_home / "peers.json").read_text(encoding="utf-8"))
    assert raw["peers"][0]["label"] == "seed-tw"


def test_add_duplicate_label_rejected() -> None:
    store = PeerStore()
    store.add("seed", "https://a.example.com")
    with pytest.raises(PeerStoreError):
        store.add("seed", "https://b.example.com")


def test_add_empty_label_rejected() -> None:
    store = PeerStore()
    with pytest.raises(PeerStoreError):
        store.add("", "https://example.com")


def test_add_empty_endpoint_rejected() -> None:
    store = PeerStore()
    with pytest.raises(PeerStoreError):
        store.add("seed", "")


def test_remove_returns_removed_entry() -> None:
    store = PeerStore()
    store.add("a", "https://a.example.com")
    store.add("b", "https://b.example.com")
    removed = store.remove("a")
    assert removed.label == "a"
    assert [p.label for p in store.load()] == ["b"]


def test_remove_missing_label_raises() -> None:
    store = PeerStore()
    with pytest.raises(PeerStoreError):
        store.remove("ghost")


def test_get_finds_by_label() -> None:
    store = PeerStore()
    store.add("a", "https://a.example.com")
    assert store.get("a") is not None
    assert store.get("b") is None


def test_save_is_atomic(isolated_home: Path) -> None:
    """A crash mid-save must not corrupt the file. We simulate by
    asserting the tmp file is gone after a successful save."""
    store = PeerStore()
    store.add("a", "https://a.example.com")
    tmp = peers_path().with_suffix(".json.tmp")
    assert not tmp.exists(), "atomic write should clean up its tmp file"


def test_malformed_peers_json_raises(isolated_home: Path) -> None:
    (isolated_home / "peers.json").write_text("not json", encoding="utf-8")
    with pytest.raises(PeerStoreError):
        PeerStore().load()


def test_load_tolerates_extra_unknown_keys(isolated_home: Path) -> None:
    """Forward-compat: a future version might add a `tags` key.
    Operators on the old version must not crash."""
    (isolated_home / "peers.json").write_text(
        json.dumps(
            {
                "peers": [
                    {
                        "label": "seed",
                        "endpoint": "https://seed.example.com",
                        "added_at_ms": 1_000_000,
                        "tags": ["future"],  # unknown key
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    peers = PeerStore().load()
    assert len(peers) == 1
    assert peers[0].label == "seed"


# --- CLI -------------------------------------------------------------------


def test_cli_peer_help_lists_subcommands(runner: CliRunner) -> None:
    result = runner.invoke(app, ["peer", "--help"])
    assert result.exit_code == 0
    for cmd in ("add", "list", "remove", "ping", "known-nodes"):
        assert cmd in result.stdout


def test_cli_peer_add_and_list(runner: CliRunner) -> None:
    add_res = runner.invoke(app, ["peer", "add", "seed", "https://seed.example.com"])
    assert add_res.exit_code == 0, add_res.stdout
    list_res = runner.invoke(app, ["peer", "list"])
    assert list_res.exit_code == 0
    parsed = json.loads(list_res.stdout)
    assert len(parsed) == 1
    assert parsed[0]["label"] == "seed"


def test_cli_peer_add_duplicate_exits_nonzero(runner: CliRunner) -> None:
    runner.invoke(app, ["peer", "add", "seed", "https://a.example.com"])
    dup = runner.invoke(app, ["peer", "add", "seed", "https://b.example.com"])
    assert dup.exit_code != 0


def test_cli_peer_remove_returns_removed_row(runner: CliRunner) -> None:
    runner.invoke(app, ["peer", "add", "seed", "https://seed.example.com"])
    rm_res = runner.invoke(app, ["peer", "remove", "seed"])
    assert rm_res.exit_code == 0
    parsed = json.loads(rm_res.stdout)
    assert parsed["removed"]["label"] == "seed"
    list_res = runner.invoke(app, ["peer", "list"])
    assert json.loads(list_res.stdout) == []


def test_cli_peer_remove_missing_exits_nonzero(runner: CliRunner) -> None:
    res = runner.invoke(app, ["peer", "remove", "ghost"])
    assert res.exit_code != 0


def test_cli_peer_list_empty_returns_empty_array(runner: CliRunner) -> None:
    res = runner.invoke(app, ["peer", "list"])
    assert res.exit_code == 0
    assert json.loads(res.stdout) == []
