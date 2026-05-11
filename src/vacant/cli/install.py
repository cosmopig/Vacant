"""`vacant install <client>` — register vacant as an MCP server with a client.

Pfix4: provides a uniform "one-line" install across all supported MCP
clients so README's per-client sections can collapse to a single
``vacant install <client>`` line. Each handler:

- knows the client's default config file location (with OS-aware fallbacks);
- writes / appends the canonical ``mcpServers`` entry pointing at
  ``uvx --from git+https://github.com/cosmopig/Vacant vacant mcp``;
- is idempotent — re-running with no flags is a no-op when an entry
  already exists; ``--force`` overwrites.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any, Literal

__all__ = [
    "SUPPORTED_CLIENTS",
    "default_config_path",
    "install_claude_desktop",
    "install_cursor",
    "install_hermes",
    "install_openclaw",
    "install_windsurf",
    "vacant_mcp_server_block",
]


SUPPORTED_CLIENTS = (
    "claude-code",
    "claude-desktop",
    "cursor",
    "windsurf",
    "openclaw",
    "hermes",
)
ClientName = Literal["claude-code", "claude-desktop", "cursor", "windsurf", "openclaw", "hermes"]


VACANT_GIT_REF = "git+https://github.com/cosmopig/Vacant"
"""Used in `uvx --from <ref>`. Pinned to the public HTTPS URL so the
install works without an SSH key."""


# --- canonical server block --------------------------------------------------


def vacant_mcp_server_block(*, name: str = "alice") -> dict[str, Any]:
    """Return the JSON-shape ``mcpServers["vacant"]`` block for clients
    that consume Claude-Desktop-style config (Cursor, Windsurf, the
    Claude Desktop config itself).
    """
    return {
        "command": "uvx",
        "args": ["--from", VACANT_GIT_REF, "vacant", "mcp"],
        "env": {"VACANT_NAME": name},
    }


# --- default config paths ----------------------------------------------------


def default_config_path(client: ClientName) -> Path:
    """Per-client default config file. macOS / Linux / Windows paths
    handled inside each branch so callers don't need to special-case."""
    home = Path.home()
    system = platform.system()

    if client == "claude-desktop":
        if system == "Darwin":
            return (
                home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
            )
        if system == "Windows":
            appdata = os.environ.get("APPDATA")
            if appdata:
                return Path(appdata) / "Claude" / "claude_desktop_config.json"
            return home / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
        # Linux / other
        return home / ".config" / "Claude" / "claude_desktop_config.json"

    if client == "cursor":
        return home / ".cursor" / "mcp.json"

    if client == "windsurf":
        return home / ".codeium" / "windsurf" / "mcp_config.json"

    if client == "hermes":
        return home / ".hermes" / "mcp.toml"

    # claude-code / openclaw don't have a config file — they're handled
    # via slash command / external CLI respectively.
    raise ValueError(f"client {client!r} has no config-file install path")


# --- JSON merge (Claude Desktop / Cursor / Windsurf) ------------------------


def _install_json_client(
    *,
    config_path: Path,
    name: str,
    force: bool,
    dry_run: bool,
    label: str,
) -> str:
    """Merge ``mcpServers["vacant"]`` into a Claude-Desktop-style JSON
    config. Returns a one-line status string for the CLI to echo.
    """
    block = vacant_mcp_server_block(name=name)

    existing: dict[str, Any] = {}
    if config_path.exists():
        try:
            existing = json.loads(config_path.read_text())
        except json.JSONDecodeError as exc:
            return f"ERROR: existing {config_path} is not valid JSON ({exc}); refusing to overwrite"

    servers = existing.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        return f"ERROR: {config_path} mcpServers is not an object"

    if "vacant" in servers and not force:
        return f"already installed in {config_path}; pass --force to overwrite"
    servers["vacant"] = block

    if dry_run:
        return f"[dry-run] would write {label} config at {config_path}"

    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(existing, indent=2, ensure_ascii=False) + "\n"
    tmp = config_path.with_suffix(config_path.suffix + ".tmp")
    tmp.write_text(payload)
    os.replace(tmp, config_path)
    return f"wrote vacant entry to {config_path}"


def install_claude_desktop(
    *,
    config_path: Path | None = None,
    name: str = "alice",
    force: bool = False,
    dry_run: bool = False,
) -> str:
    return _install_json_client(
        config_path=config_path or default_config_path("claude-desktop"),
        name=name,
        force=force,
        dry_run=dry_run,
        label="Claude Desktop",
    )


def install_cursor(
    *,
    config_path: Path | None = None,
    name: str = "alice",
    force: bool = False,
    dry_run: bool = False,
) -> str:
    return _install_json_client(
        config_path=config_path or default_config_path("cursor"),
        name=name,
        force=force,
        dry_run=dry_run,
        label="Cursor",
    )


def install_windsurf(
    *,
    config_path: Path | None = None,
    name: str = "alice",
    force: bool = False,
    dry_run: bool = False,
) -> str:
    return _install_json_client(
        config_path=config_path or default_config_path("windsurf"),
        name=name,
        force=force,
        dry_run=dry_run,
        label="Windsurf",
    )


# --- TOML append (Hermes) ----------------------------------------------------


def install_hermes(
    *,
    config_path: Path | None = None,
    name: str = "alice",
    force: bool = False,
    dry_run: bool = False,
) -> str:
    """Append a ``[[mcp_servers]] name = "vacant"`` block to Hermes's
    TOML config. If a vacant entry already exists, skip unless force.
    """
    cfg = config_path or default_config_path("hermes")

    existing_text = cfg.read_text() if cfg.exists() else ""
    has_vacant_entry = "[[mcp_servers]]" in existing_text and 'name = "vacant"' in existing_text
    if has_vacant_entry and not force:
        return f"already installed in {cfg}; pass --force to append a duplicate"

    block = (
        "\n"
        "[[mcp_servers]]\n"
        'name = "vacant"\n'
        'command = "uvx"\n'
        f'args = ["--from", "{VACANT_GIT_REF}", "vacant", "mcp"]\n'
        "\n"
        "[mcp_servers.env]\n"
        f'VACANT_NAME = "{name}"\n'
    )

    if dry_run:
        return f"[dry-run] would append vacant block to {cfg}"

    cfg.parent.mkdir(parents=True, exist_ok=True)
    with cfg.open("a") as f:
        f.write(block)
    return f"appended vacant block to {cfg}"


# --- OpenClaw (external CLI) ------------------------------------------------


def install_openclaw(*, force: bool = False, dry_run: bool = False) -> str:
    """Shell out to ``openclaw plugins install`` + restart gateway.

    ``--force`` is forwarded as ``--reinstall`` so OpenClaw re-pulls.
    """
    if shutil.which("openclaw") is None:
        return (
            "ERROR: openclaw CLI not on PATH. Install OpenClaw per its "
            "own docs (https://docs.openclaw.ai/) then re-run."
        )

    install_cmd = [
        "openclaw",
        "plugins",
        "install",
        "https://github.com/cosmopig/Vacant.git#main:examples/openclaw",
    ]
    if force:
        install_cmd.append("--reinstall")
    restart_cmd = ["openclaw", "gateway", "restart"]

    if dry_run:
        return f"[dry-run] would run:\n  $ {' '.join(install_cmd)}\n  $ {' '.join(restart_cmd)}"

    # S603: args are hard-coded strings except for the optional
    # --reinstall flag; no user-controlled input reaches the shell.
    try:
        subprocess.run(install_cmd, check=True)  # noqa: S603
        subprocess.run(restart_cmd, check=True)  # noqa: S603
    except subprocess.CalledProcessError as exc:
        return f"ERROR: openclaw command failed: {exc}"
    return "openclaw plugin installed + gateway restarted"


# --- claude-code (slash-command only) ---------------------------------------


def install_claude_code() -> str:
    """Claude Code uses its own slash-command install path. We can't
    drive that from outside the CC CLI, so just print the command for
    the user to copy-paste.
    """
    return (
        "Claude Code installs through its own slash command. From inside "
        "Claude Code, run:\n\n"
        "  /plugin marketplace add cosmopig/Vacant\n"
        "  /plugin install vacant@cosmopig-vacant"
    )


# --- top-level dispatcher ---------------------------------------------------


def install(
    client: str,
    *,
    config_path: Path | None = None,
    name: str = "alice",
    force: bool = False,
    dry_run: bool = False,
) -> str:
    """Dispatch ``vacant install <client>`` to the right handler.

    Returns the status line the CLI should print. Raises
    ``ValueError`` for unknown clients.
    """
    if client not in SUPPORTED_CLIENTS:
        supported = ", ".join(SUPPORTED_CLIENTS)
        raise ValueError(f"unknown client {client!r}; supported: {supported}")
    if client == "claude-code":
        return install_claude_code()
    if client == "claude-desktop":
        return install_claude_desktop(
            config_path=config_path, name=name, force=force, dry_run=dry_run
        )
    if client == "cursor":
        return install_cursor(config_path=config_path, name=name, force=force, dry_run=dry_run)
    if client == "windsurf":
        return install_windsurf(config_path=config_path, name=name, force=force, dry_run=dry_run)
    if client == "hermes":
        return install_hermes(config_path=config_path, name=name, force=force, dry_run=dry_run)
    if client == "openclaw":
        return install_openclaw(force=force, dry_run=dry_run)
    # Unreachable by the SUPPORTED_CLIENTS guard above; keeps mypy happy.
    raise AssertionError(f"unhandled client {client!r}")
