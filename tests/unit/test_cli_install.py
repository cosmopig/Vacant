"""Pfix4 B — `vacant install <client>` unified installer tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from vacant.cli import app
from vacant.cli.install import (
    SUPPORTED_CLIENTS,
    default_config_path,
    install,
    install_claude_code,
    install_claude_desktop,
    install_cursor,
    install_hermes,
    install_openclaw,
    install_windsurf,
    vacant_mcp_server_block,
)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# --- canonical block -------------------------------------------------------


def test_vacant_mcp_server_block_shape() -> None:
    block = vacant_mcp_server_block(name="bob")
    assert block["command"] == "uvx"
    assert "git+https://github.com/cosmopig/Vacant" in block["args"]
    assert block["args"][-2:] == ["vacant", "mcp"]
    assert block["env"]["VACANT_NAME"] == "bob"


# --- default config paths --------------------------------------------------


def test_default_config_path_known_clients() -> None:
    # Just verify each known client returns *some* Path under the home
    # dir; OS branches are exercised via the patched-platform tests below.
    for client in ("claude-desktop", "cursor", "windsurf", "hermes"):
        p = default_config_path(client)  # type: ignore[arg-type]
        assert isinstance(p, Path)
        # All default paths live under the user's home.
        assert str(Path.home()) in str(p)


def test_default_config_path_no_config_clients_raise() -> None:
    with pytest.raises(ValueError):
        default_config_path("claude-code")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        default_config_path("openclaw")  # type: ignore[arg-type]


def test_default_config_path_macos_claude_desktop() -> None:
    with patch("platform.system", return_value="Darwin"):
        p = default_config_path("claude-desktop")
    assert p.name == "claude_desktop_config.json"
    assert "Library/Application Support/Claude" in str(p)


def test_default_config_path_linux_claude_desktop() -> None:
    with patch("platform.system", return_value="Linux"):
        p = default_config_path("claude-desktop")
    assert p.name == "claude_desktop_config.json"
    assert ".config/Claude" in str(p)


def test_default_config_path_windows_claude_desktop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APPDATA", "C:\\Users\\Test\\AppData\\Roaming")
    with patch("platform.system", return_value="Windows"):
        p = default_config_path("claude-desktop")
    assert "Claude" in str(p)
    assert p.name == "claude_desktop_config.json"


# --- JSON merge: Cursor / Windsurf / Claude Desktop ------------------------


def test_install_cursor_creates_fresh_config(tmp_path: Path) -> None:
    cfg = tmp_path / "cursor_dir" / "mcp.json"
    msg = install_cursor(config_path=cfg, name="alice")
    assert "wrote vacant entry" in msg
    data = json.loads(cfg.read_text())
    assert data["mcpServers"]["vacant"]["command"] == "uvx"
    assert data["mcpServers"]["vacant"]["env"]["VACANT_NAME"] == "alice"


def test_install_cursor_idempotent_skip(tmp_path: Path) -> None:
    cfg = tmp_path / "mcp.json"
    install_cursor(config_path=cfg)
    msg = install_cursor(config_path=cfg)
    assert "already installed" in msg
    # File still has exactly one vacant entry.
    data = json.loads(cfg.read_text())
    assert "vacant" in data["mcpServers"]


def test_install_cursor_force_overwrites(tmp_path: Path) -> None:
    cfg = tmp_path / "mcp.json"
    install_cursor(config_path=cfg, name="alice")
    msg = install_cursor(config_path=cfg, name="bob", force=True)
    assert "wrote vacant entry" in msg
    data = json.loads(cfg.read_text())
    assert data["mcpServers"]["vacant"]["env"]["VACANT_NAME"] == "bob"


def test_install_cursor_preserves_other_servers(tmp_path: Path) -> None:
    cfg = tmp_path / "mcp.json"
    cfg.write_text(json.dumps({"mcpServers": {"other": {"command": "echo"}}}))
    install_cursor(config_path=cfg)
    data = json.loads(cfg.read_text())
    assert "other" in data["mcpServers"]
    assert "vacant" in data["mcpServers"]


def test_install_cursor_dry_run_does_not_write(tmp_path: Path) -> None:
    cfg = tmp_path / "mcp.json"
    msg = install_cursor(config_path=cfg, dry_run=True)
    assert "[dry-run]" in msg
    assert not cfg.exists()


def test_install_cursor_rejects_invalid_existing_json(tmp_path: Path) -> None:
    cfg = tmp_path / "mcp.json"
    cfg.write_text("{ not valid json")
    msg = install_cursor(config_path=cfg)
    assert msg.startswith("ERROR")
    # File is left untouched.
    assert cfg.read_text() == "{ not valid json"


def test_install_claude_desktop_writes_to_path(tmp_path: Path) -> None:
    cfg = tmp_path / "Claude" / "claude_desktop_config.json"
    msg = install_claude_desktop(config_path=cfg)
    assert "wrote vacant entry" in msg
    data = json.loads(cfg.read_text())
    assert "vacant" in data["mcpServers"]


def test_install_windsurf_writes_to_path(tmp_path: Path) -> None:
    cfg = tmp_path / "windsurf" / "mcp_config.json"
    msg = install_windsurf(config_path=cfg)
    assert "wrote vacant entry" in msg
    data = json.loads(cfg.read_text())
    assert "vacant" in data["mcpServers"]


# --- TOML append: Hermes ---------------------------------------------------


def test_install_hermes_creates_fresh_config(tmp_path: Path) -> None:
    cfg = tmp_path / "hermes" / "mcp.toml"
    msg = install_hermes(config_path=cfg, name="alice")
    assert "appended vacant block" in msg
    text = cfg.read_text()
    assert "[[mcp_servers]]" in text
    assert 'name = "vacant"' in text
    assert 'VACANT_NAME = "alice"' in text


def test_install_hermes_idempotent_skip(tmp_path: Path) -> None:
    cfg = tmp_path / "mcp.toml"
    install_hermes(config_path=cfg)
    msg = install_hermes(config_path=cfg)
    assert "already installed" in msg
    # Only one block — count occurrences.
    assert cfg.read_text().count('name = "vacant"') == 1


def test_install_hermes_force_appends_again(tmp_path: Path) -> None:
    cfg = tmp_path / "mcp.toml"
    install_hermes(config_path=cfg)
    install_hermes(config_path=cfg, force=True)
    # With force we don't dedupe; user asked explicitly.
    assert cfg.read_text().count('name = "vacant"') == 2


def test_install_hermes_dry_run_does_not_write(tmp_path: Path) -> None:
    cfg = tmp_path / "mcp.toml"
    msg = install_hermes(config_path=cfg, dry_run=True)
    assert "[dry-run]" in msg
    assert not cfg.exists()


# --- OpenClaw (subprocess) -------------------------------------------------


def test_install_openclaw_missing_cli_returns_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("vacant.cli.install.shutil.which", lambda _: None)
    msg = install_openclaw()
    assert msg.startswith("ERROR")
    assert "openclaw CLI" in msg


def test_install_openclaw_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vacant.cli.install.shutil.which", lambda _: "/usr/bin/openclaw")
    msg = install_openclaw(dry_run=True)
    assert msg.startswith("[dry-run]")
    assert "openclaw plugins install" in msg
    assert "openclaw gateway restart" in msg


def test_install_openclaw_runs_two_subprocess_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("vacant.cli.install.shutil.which", lambda _: "/usr/bin/openclaw")
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], check: bool) -> None:
        calls.append(cmd)
        assert check is True

    monkeypatch.setattr("vacant.cli.install.subprocess.run", fake_run)
    msg = install_openclaw()
    assert "gateway restarted" in msg
    assert len(calls) == 2
    assert calls[0][:3] == ["openclaw", "plugins", "install"]
    assert calls[1] == ["openclaw", "gateway", "restart"]


# --- claude-code (slash command pointer) -----------------------------------


def test_install_claude_code_returns_slash_command_message() -> None:
    msg = install_claude_code()
    assert "/plugin marketplace add cosmopig/Vacant" in msg
    assert "/plugin install vacant@cosmopig-vacant" in msg


# --- top-level dispatcher --------------------------------------------------


def test_install_dispatcher_unknown_client_raises() -> None:
    with pytest.raises(ValueError, match="unknown client"):
        install("nonexistent")


def test_install_dispatcher_routes_to_each_client(tmp_path: Path) -> None:
    """Sanity check: every entry in SUPPORTED_CLIENTS is reachable."""
    # claude-code: pure print
    msg = install("claude-code")
    assert "/plugin install" in msg

    # JSON-shape clients
    for c in ("claude-desktop", "cursor", "windsurf"):
        cfg = tmp_path / f"{c}.json"
        msg = install(c, config_path=cfg)
        assert "wrote vacant entry" in msg

    # TOML client
    cfg = tmp_path / "hermes.toml"
    msg = install("hermes", config_path=cfg)
    assert "appended vacant block" in msg


# --- Typer integration -----------------------------------------------------


def test_typer_install_unknown_client_exits_2(runner: CliRunner) -> None:
    result = runner.invoke(app, ["install", "bogus"])
    assert result.exit_code == 2
    assert "unknown client" in (result.stderr + result.stdout)


def test_typer_install_cursor_writes_config(runner: CliRunner, tmp_path: Path) -> None:
    cfg = tmp_path / "cursor.json"
    result = runner.invoke(app, ["install", "cursor", "--config-path", str(cfg), "--name", "demo"])
    assert result.exit_code == 0, result.output
    assert cfg.exists()
    data = json.loads(cfg.read_text())
    assert data["mcpServers"]["vacant"]["env"]["VACANT_NAME"] == "demo"


def test_typer_install_dry_run_exit_zero(runner: CliRunner, tmp_path: Path) -> None:
    cfg = tmp_path / "cursor.json"
    result = runner.invoke(app, ["install", "cursor", "--config-path", str(cfg), "--dry-run"])
    assert result.exit_code == 0
    assert "[dry-run]" in result.output
    assert not cfg.exists()


def test_supported_clients_set_is_documented() -> None:
    """If we add a client, the SUPPORTED_CLIENTS tuple must include it
    so the dispatcher rejects unknown values uniformly."""
    expected = {
        "claude-code",
        "claude-desktop",
        "cursor",
        "windsurf",
        "openclaw",
        "hermes",
    }
    assert set(SUPPORTED_CLIENTS) == expected
