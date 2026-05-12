"""`vacant install <client>` unified installer tests (Pfix4 → Pfix5)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from typer.testing import CliRunner

from vacant.cli import app
from vacant.cli.install import (
    SUPPORTED_CLIENTS,
    default_config_path,
    ensure_identity,
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


@pytest.fixture(autouse=True)
def isolated_vacant_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Every test gets its own VACANT_HOME so `ensure_identity` writes
    into an ephemeral dir rather than the real ``~/.vacant/``."""
    home = tmp_path / "vacant_home"
    monkeypatch.setenv("VACANT_HOME", str(home))
    monkeypatch.delenv("VACANT_NAME", raising=False)
    return home


# --- canonical block -------------------------------------------------------


def test_vacant_mcp_server_block_shape() -> None:
    block = vacant_mcp_server_block(name="bob")
    assert block["command"] == "uvx"
    args = block["args"]
    assert "git+https://github.com/cosmopig/Vacant" in args
    # Pfix5: --name is now baked into args so the runtime mcp command
    # honours the registered identity even without env var.
    assert "--name" in args
    name_idx = args.index("--name")
    assert args[name_idx + 1] == "bob"
    assert block["env"]["VACANT_NAME"] == "bob"


# --- default config paths --------------------------------------------------


def test_default_config_path_known_clients() -> None:
    for client in ("claude-desktop", "cursor", "windsurf", "hermes"):
        p = default_config_path(client)  # type: ignore[arg-type]
        assert isinstance(p, Path)
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


def test_default_config_path_hermes_is_config_yaml() -> None:
    """Pfix5: Hermes config target is ``~/.hermes/config.yaml`` (where
    `hermes mcp list` reads), NOT ``~/.hermes/mcp.toml`` (which Pfix4
    wrote to but Hermes ignored)."""
    p = default_config_path("hermes")
    assert p.name == "config.yaml"
    assert ".hermes" in str(p)


# --- ensure_identity (Pfix5) ----------------------------------------------


def test_ensure_identity_creates_dir_when_missing() -> None:
    msg = ensure_identity("alice", insecure_demo=True)
    assert msg is not None
    assert "created identity" in msg
    assert "alice" in msg
    # Re-running is a no-op.
    msg2 = ensure_identity("alice", insecure_demo=True)
    assert msg2 is None


def test_ensure_identity_skip_init_short_circuits() -> None:
    msg = ensure_identity("alice", skip_init=True)
    assert msg is not None
    assert "skip-init" in msg
    assert "alice" in msg


def test_ensure_identity_dry_run_does_not_write(tmp_path: Path) -> None:
    msg = ensure_identity("alice", insecure_demo=True, dry_run=True)
    assert msg is not None
    assert "[dry-run]" in msg
    # No directory created.
    from vacant.cli.local_store import vacant_dir

    assert not vacant_dir("alice").exists()


def test_ensure_identity_keyring_unavailable_returns_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without --insecure-demo and without an OS keyring backend, we
    must refuse to create a plaintext key silently — return an ERROR
    string with two clear next-steps."""
    from vacant.cli import local_store as ls

    def raise_keyring(name: str, *, insecure_demo: bool = False) -> tuple:  # type: ignore[type-arg]
        raise ls.LocalVacantKeyringUnavailable("no backend")

    monkeypatch.setattr("vacant.cli.install.ls.init_vacant", raise_keyring)
    msg = ensure_identity("alice", insecure_demo=False)
    assert msg is not None
    assert msg.startswith("ERROR")
    assert "OS keyring not available" in msg
    assert "--insecure-demo" in msg


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


# --- YAML merge: Hermes (Pfix5) -------------------------------------------


def test_install_hermes_writes_yaml_with_mcp_servers_key(tmp_path: Path) -> None:
    """Pfix5: writes ``mcp_servers.vacant`` into config.yaml."""
    cfg = tmp_path / "hermes" / "config.yaml"
    msg = install_hermes(config_path=cfg, name="alice")
    assert "wrote vacant entry" in msg
    data = yaml.safe_load(cfg.read_text())
    assert "mcp_servers" in data
    assert "vacant" in data["mcp_servers"]
    assert data["mcp_servers"]["vacant"]["env"]["VACANT_NAME"] == "alice"


def test_install_hermes_preserves_existing_yaml_keys(tmp_path: Path) -> None:
    """Hermes config.yaml has lots of other settings (provider, fallback,
    etc.). Merging vacant in must not blow them away."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text("provider: openai\nmodel: gpt-5\n")
    install_hermes(config_path=cfg)
    data = yaml.safe_load(cfg.read_text())
    assert data["provider"] == "openai"
    assert data["model"] == "gpt-5"
    assert data["mcp_servers"]["vacant"]["command"] == "uvx"


def test_install_hermes_preserves_other_mcp_servers(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("mcp_servers:\n  github:\n    command: gh\n")
    install_hermes(config_path=cfg)
    data = yaml.safe_load(cfg.read_text())
    assert data["mcp_servers"]["github"]["command"] == "gh"
    assert "vacant" in data["mcp_servers"]


def test_install_hermes_idempotent_skip(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    install_hermes(config_path=cfg)
    msg = install_hermes(config_path=cfg)
    assert "already installed" in msg


def test_install_hermes_force_overwrites(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    install_hermes(config_path=cfg, name="alice")
    install_hermes(config_path=cfg, name="bob", force=True)
    data = yaml.safe_load(cfg.read_text())
    assert data["mcp_servers"]["vacant"]["env"]["VACANT_NAME"] == "bob"


def test_install_hermes_dry_run_does_not_write(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    msg = install_hermes(config_path=cfg, dry_run=True)
    assert "[dry-run]" in msg
    assert not cfg.exists()


def test_install_hermes_rejects_invalid_existing_yaml(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("not: valid: yaml: too: many: colons")
    msg = install_hermes(config_path=cfg)
    assert msg.startswith("ERROR")


def test_install_hermes_rejects_non_mapping_mcp_servers(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("mcp_servers: [list, not, mapping]\n")
    msg = install_hermes(config_path=cfg)
    assert msg.startswith("ERROR")


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
    assert "openclaw plugins install -l" in msg
    assert ".openclaw-bundle" in msg


def test_install_openclaw_renders_bundle_and_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Happy path: install_openclaw writes a rendered bundle dir
    (substituted .mcp.json + static assets) and invokes
    ``openclaw plugins install -l <bundle>``."""
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    monkeypatch.setattr(
        "vacant.cli.install.shutil.which",
        lambda exe: f"/usr/bin/{exe}",
    )
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], check: bool) -> None:
        calls.append(cmd)
        assert check is True

    monkeypatch.setattr("vacant.cli.install.subprocess.run", fake_run)
    msg = install_openclaw(name="alice")
    assert "rendered OpenClaw bundle" in msg
    assert len(calls) == 1
    assert calls[0][:4] == ["openclaw", "plugins", "install", "-l"]

    bundle_dir = tmp_path / ".openclaw-bundle" / "alice"
    assert (bundle_dir / ".claude-plugin" / "plugin.json").exists()
    assert (bundle_dir / "skills" / "vacant-call" / "SKILL.md").exists()
    assert (bundle_dir / "README.md").exists()
    mcp = json.loads((bundle_dir / ".mcp.json").read_text())
    # Env values must be literal (no shell substitution syntax), since
    # OpenClaw passes env through verbatim.
    env = mcp["vacant"]["env"]
    assert env["VACANT_NAME"] == "alice"
    assert env["VACANT_HOME"] == str(tmp_path)
    assert "${" not in env["VACANT_NAME"]
    assert "${" not in env["VACANT_HOME"]
    # Args must pin --name so the spawned vacant mcp loads the right
    # identity even if env is stripped.
    args = mcp["vacant"]["args"]
    assert "--name" in args
    assert args[args.index("--name") + 1] == "alice"


# --- claude-code (slash command pointer) -----------------------------------


def test_install_claude_code_returns_slash_command_message() -> None:
    msg = install_claude_code()
    assert "/plugin marketplace add cosmopig/Vacant" in msg
    assert "/plugin install vacant@cosmopig-vacant" in msg


# --- top-level dispatcher --------------------------------------------------


def test_install_dispatcher_unknown_client_raises() -> None:
    with pytest.raises(ValueError, match="unknown client"):
        install("nonexistent")


def test_install_dispatcher_auto_inits_then_writes_config(tmp_path: Path) -> None:
    """Pfix5 contract: install does identity bootstrap + config write,
    combined output mentions both steps."""
    cfg = tmp_path / "cursor.json"
    msg = install("cursor", config_path=cfg, name="alice", insecure_demo=True)
    assert "created identity 'alice'" in msg
    assert "wrote vacant entry" in msg


def test_install_dispatcher_skip_init_bypasses_identity(tmp_path: Path) -> None:
    cfg = tmp_path / "cursor.json"
    msg = install("cursor", config_path=cfg, name="alice", skip_init=True)
    assert "skip-init" in msg
    # Identity dir was NOT created.
    from vacant.cli.local_store import vacant_dir

    assert not vacant_dir("alice").exists()


def test_install_dispatcher_propagates_identity_error_early(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """If keyring unavailable + no --insecure-demo, the install command
    must NOT proceed to write the client config."""
    from vacant.cli import local_store as ls

    def raise_keyring(name: str, *, insecure_demo: bool = False) -> tuple:  # type: ignore[type-arg]
        raise ls.LocalVacantKeyringUnavailable("no backend")

    monkeypatch.setattr("vacant.cli.install.ls.init_vacant", raise_keyring)
    cfg = tmp_path / "cursor.json"
    msg = install("cursor", config_path=cfg, name="alice", insecure_demo=False)
    assert msg.startswith("ERROR")
    # Config file NOT written.
    assert not cfg.exists()


def test_install_dispatcher_claude_code_skips_identity() -> None:
    """claude-code never pins --name into the manifest; identity init
    is out of scope. Should print slash commands only."""
    msg = install("claude-code", name="alice", insecure_demo=True)
    assert "/plugin install" in msg
    # Identity NOT created (no side effect for claude-code).
    from vacant.cli.local_store import vacant_dir

    assert not vacant_dir("alice").exists()


def test_install_dispatcher_routes_each_client(tmp_path: Path) -> None:
    """Every entry in SUPPORTED_CLIENTS is reachable."""
    # claude-code: pure print
    msg = install("claude-code")
    assert "/plugin install" in msg

    # JSON-shape clients (auto-init via --insecure-demo for keyring-less CI)
    for c in ("claude-desktop", "cursor", "windsurf"):
        cfg = tmp_path / f"{c}.json"
        msg = install(c, config_path=cfg, name=f"{c}-bot", insecure_demo=True)
        assert "wrote vacant entry" in msg

    # YAML client (Hermes)
    cfg_yaml = tmp_path / "hermes.yaml"
    msg = install("hermes", config_path=cfg_yaml, name="hermes-bot", insecure_demo=True)
    assert "wrote vacant entry" in msg


# --- Typer integration -----------------------------------------------------


def test_typer_install_unknown_client_exits_2(runner: CliRunner) -> None:
    result = runner.invoke(app, ["install", "bogus"])
    assert result.exit_code == 2
    assert "unknown client" in (result.stderr + result.stdout)


def test_typer_install_cursor_writes_config(runner: CliRunner, tmp_path: Path) -> None:
    cfg = tmp_path / "cursor.json"
    result = runner.invoke(
        app,
        [
            "install",
            "cursor",
            "--config-path",
            str(cfg),
            "--name",
            "demo",
            "--insecure-demo",
        ],
    )
    assert result.exit_code == 0, result.output
    assert cfg.exists()
    data = json.loads(cfg.read_text())
    assert data["mcpServers"]["vacant"]["env"]["VACANT_NAME"] == "demo"


def test_typer_install_dry_run_exit_zero(runner: CliRunner, tmp_path: Path) -> None:
    cfg = tmp_path / "cursor.json"
    result = runner.invoke(
        app, ["install", "cursor", "--config-path", str(cfg), "--dry-run", "--insecure-demo"]
    )
    assert result.exit_code == 0
    assert "[dry-run]" in result.output
    assert not cfg.exists()


def test_typer_install_keyring_error_exits_1(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If identity bootstrap fails (no keyring, no --insecure-demo) the
    Typer entry must exit 1."""
    from vacant.cli import local_store as ls

    def raise_keyring(name: str, *, insecure_demo: bool = False) -> tuple:  # type: ignore[type-arg]
        raise ls.LocalVacantKeyringUnavailable("no backend")

    monkeypatch.setattr("vacant.cli.install.ls.init_vacant", raise_keyring)
    cfg = tmp_path / "cursor.json"
    result = runner.invoke(app, ["install", "cursor", "--config-path", str(cfg), "--name", "alice"])
    assert result.exit_code == 1
    assert "ERROR" in result.output


def test_typer_install_skip_init_flag(runner: CliRunner, tmp_path: Path) -> None:
    cfg = tmp_path / "cursor.json"
    result = runner.invoke(
        app,
        [
            "install",
            "cursor",
            "--config-path",
            str(cfg),
            "--name",
            "alice",
            "--skip-init",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "skip-init" in result.output


# --- Coverage edge cases (kept from earlier rounds) -----------------------


def test_default_config_path_windows_without_appdata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APPDATA", raising=False)
    with patch("platform.system", return_value="Windows"):
        p = default_config_path("claude-desktop")
    assert "AppData/Roaming/Claude" in str(p).replace("\\", "/")


def test_install_cursor_rejects_non_dict_mcpservers(tmp_path: Path) -> None:
    cfg = tmp_path / "mcp.json"
    cfg.write_text(json.dumps({"mcpServers": "not-an-object"}))
    msg = install_cursor(config_path=cfg)
    assert msg.startswith("ERROR")
    assert "mcpServers" in msg


def test_install_openclaw_force_passes_force_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    monkeypatch.setattr(
        "vacant.cli.install.shutil.which", lambda exe: f"/usr/bin/{exe}"
    )
    calls: list[list[str]] = []
    monkeypatch.setattr(
        "vacant.cli.install.subprocess.run",
        lambda cmd, check: calls.append(cmd),
    )
    install_openclaw(force=True)
    assert any("--force" in c for c in calls)


def test_install_openclaw_subprocess_failure_returns_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess as sp

    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    monkeypatch.setattr(
        "vacant.cli.install.shutil.which", lambda exe: f"/usr/bin/{exe}"
    )

    def boom(cmd: list[str], check: bool) -> None:
        raise sp.CalledProcessError(returncode=1, cmd=cmd)

    monkeypatch.setattr("vacant.cli.install.subprocess.run", boom)
    msg = install_openclaw()
    assert msg.startswith("ERROR")
    assert "openclaw plugins install failed" in msg


def test_install_hermes_rejects_yaml_top_level_list(tmp_path: Path) -> None:
    """YAML can parse a top-level list — refuse to merge into one."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text("- not\n- a\n- mapping\n")
    msg = install_hermes(config_path=cfg)
    assert msg.startswith("ERROR")
    assert "not a mapping" in msg


def test_install_dispatcher_openclaw_routes_through_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even openclaw goes through ensure_identity so subsequent
    `VACANT_NAME=<name> openclaw …` finds the identity on disk."""
    monkeypatch.setenv("VACANT_HOME", str(tmp_path))
    monkeypatch.setattr(
        "vacant.cli.install.shutil.which", lambda exe: f"/usr/bin/{exe}"
    )
    monkeypatch.setattr("vacant.cli.install.subprocess.run", lambda cmd, check: None)
    msg = install("openclaw", name="oc-bot", insecure_demo=True)
    assert "created identity 'oc-bot'" in msg
    assert "rendered OpenClaw bundle" in msg


def test_install_reinstall_idempotent_identity_message_absent(tmp_path: Path) -> None:
    """Second `vacant install cursor` for the same name: identity dir
    already exists → ensure_identity returns None → output collapses
    to the per-client status line only (no leading identity line)."""
    cfg = tmp_path / "cursor.json"
    install("cursor", config_path=cfg, name="alice", insecure_demo=True)
    msg2 = install("cursor", config_path=cfg, name="alice", insecure_demo=True, force=True)
    # No "created identity" because the dir was already there.
    assert "created identity" not in msg2
    assert "wrote vacant entry" in msg2


def test_supported_clients_set_is_documented() -> None:
    expected = {
        "claude-code",
        "claude-desktop",
        "cursor",
        "windsurf",
        "openclaw",
        "hermes",
    }
    assert set(SUPPORTED_CLIENTS) == expected
