"""`vacant install <client>` — register vacant as an MCP server with a client.

Pfix5: turns ``vacant install`` into a real setup command — not just
"write a config file" but "make this client able to actually run a
vacant". That means:

- **Auto-init identity** when ``~/.vacant/<name>/`` doesn't exist.
  Defaults to OS keyring storage so private keys don't live in
  plaintext. ``--insecure-demo`` opts into plaintext for hosts without
  a keyring backend. ``--skip-init`` is the explicit "I'll manage the
  identity myself" escape hatch.
- **Per-client config**: write the canonical MCP server entry into
  the file each client actually reads. Hermes is special — it reads
  ``~/.hermes/config.yaml`` under the ``mcp_servers`` key (NOT the
  ``mcp.toml`` an older Pfix4 version assumed).
- **Idempotent**: re-running with no flags is a no-op when the
  config entry already exists; ``--force`` overwrites. Identity
  init is also skipped if the directory already exists.

The contract Pfix5 establishes is intentionally split into two
commands: ``install`` does the setup side effects (identity + config);
``mcp`` is pure runtime and fails loudly if identity is missing rather
than silently downgrading to ephemeral mode.
"""

from __future__ import annotations

import importlib.resources
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any, Literal

import yaml

from vacant.cli import local_store as ls

__all__ = [
    "SUPPORTED_CLIENTS",
    "default_config_path",
    "ensure_identity",
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
        "args": ["--from", VACANT_GIT_REF, "vacant", "mcp", "--name", name],
        "env": {"VACANT_NAME": name},
    }


# --- identity bootstrap ------------------------------------------------------


def ensure_identity(
    name: str,
    *,
    insecure_demo: bool = False,
    skip_init: bool = False,
    dry_run: bool = False,
) -> str | None:
    """Create ``~/.vacant/<name>/`` if missing. Pfix5 contract.

    Returns a one-line status string for the CLI to echo, or ``None``
    if no action was needed. Returns an ``"ERROR: ..."`` string the
    caller should propagate when the operation can't proceed (e.g.
    no keyring backend without ``--insecure-demo``).
    """
    if skip_init:
        return f"[--skip-init] not initialising identity '{name}'; assuming caller manages it"
    vacant_dir = ls.vacant_dir(name)
    if vacant_dir.exists():
        # Idempotent: identity already on disk, leave it alone.
        return None
    if dry_run:
        store = "plaintext key.json" if insecure_demo else "OS keyring"
        return f"[dry-run] would create identity '{name}' at {vacant_dir} ({store} storage)"
    try:
        vid, _sk = ls.init_vacant(name, insecure_demo=insecure_demo)
    except ls.LocalVacantKeyringUnavailable as exc:
        return (
            "ERROR: OS keyring not available on this host — refusing to "
            "create a private key without explicit consent.\n"
            "  Either:\n"
            "    1. install a keyring backend (e.g. on Linux: "
            "`apt install python3-secretstorage` or `keyrings.alt`), then re-run; or\n"
            "    2. re-run with `--insecure-demo` to accept a plaintext "
            "key.json (mode 0600) — fine for demos / CI, NOT for "
            "production responsibility-layer use.\n"
            f"  underlying error: {exc}"
        )
    storage = "plaintext key.json" if insecure_demo else "OS keyring"
    return f"✓ created identity '{name}' (vacant_id={vid.short()}, storage={storage})"


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
        # Pfix5 correction: Hermes Agent stores MCP servers in its YAML
        # config under the ``mcp_servers`` key, NOT in a separate
        # ``mcp.toml``. Pfix4's earlier ``mcp.toml`` target was wrong —
        # Hermes silently ignored that file and ``hermes mcp list`` showed
        # "No MCP servers configured" even though our installer claimed
        # to have written one.
        return home / ".hermes" / "config.yaml"

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


# --- YAML merge (Hermes) -----------------------------------------------------


def install_hermes(
    *,
    config_path: Path | None = None,
    name: str = "alice",
    force: bool = False,
    dry_run: bool = False,
) -> str:
    """Merge a ``mcp_servers.vacant`` entry into Hermes's
    ``~/.hermes/config.yaml`` (Pfix5).

    Earlier Pfix4 appended to ``~/.hermes/mcp.toml`` but Hermes never
    reads that file — its CLI (``hermes mcp list / test / add``) reads
    ``config.yaml`` under the ``mcp_servers`` key. Confirmed by reading
    Hermes Agent source (``hermes_cli/mcp_config.py`` line 8).
    """
    cfg = config_path or default_config_path("hermes")

    existing: dict[str, Any] = {}
    if cfg.exists():
        try:
            loaded = yaml.safe_load(cfg.read_text()) or {}
        except yaml.YAMLError as exc:
            return f"ERROR: existing {cfg} is not valid YAML ({exc}); refusing to overwrite"
        if not isinstance(loaded, dict):
            return f"ERROR: {cfg} top-level is not a mapping"
        existing = loaded

    servers = existing.setdefault("mcp_servers", {})
    if not isinstance(servers, dict):
        return f"ERROR: {cfg} mcp_servers is not a mapping"

    if "vacant" in servers and not force:
        return f"already installed in {cfg}; pass --force to overwrite"

    # Hermes uses the same shape as Claude Desktop / Cursor / Windsurf
    # (command/args/env) — its loader is JSON/YAML agnostic about the
    # value shape, only about where the entry sits in the document tree.
    servers["vacant"] = vacant_mcp_server_block(name=name)

    if dry_run:
        return f"[dry-run] would write Hermes config at {cfg}"

    cfg.parent.mkdir(parents=True, exist_ok=True)
    payload = yaml.safe_dump(
        existing, default_flow_style=False, sort_keys=False, allow_unicode=True
    )
    tmp = cfg.with_suffix(cfg.suffix + ".tmp")
    tmp.write_text(payload)
    os.replace(tmp, cfg)
    return f"wrote vacant entry to {cfg}"


# --- OpenClaw (external CLI) ------------------------------------------------


def _render_openclaw_bundle(*, bundle_dir: Path, name: str) -> None:
    """Materialise an OpenClaw plugin bundle on disk with absolute env
    values (no shell substitution), because OpenClaw passes ``.mcp.json``
    env values through verbatim — `${VACANT_NAME:-alice}` would land in
    the spawned MCP subprocess as the literal string. Static assets
    (plugin.json, SKILL.md) come from `vacant.cli.openclaw_bundle` so
    the wheel ships one canonical copy.
    """
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / ".claude-plugin").mkdir(exist_ok=True)
    (bundle_dir / "skills" / "vacant-call").mkdir(parents=True, exist_ok=True)

    data = importlib.resources.files("vacant.cli.openclaw_bundle")
    (bundle_dir / ".claude-plugin" / "plugin.json").write_text(
        (data / "plugin.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (bundle_dir / "skills" / "vacant-call" / "SKILL.md").write_text(
        (data / "SKILL.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (bundle_dir / "README.md").write_text(
        "# Vacant — OpenClaw bundle (rendered)\n\n"
        "Auto-generated by `vacant install openclaw`. Do not edit; "
        "re-run install instead. Upstream template at "
        "https://github.com/cosmopig/Vacant/tree/main/examples/openclaw.\n",
        encoding="utf-8",
    )

    uvx_path = shutil.which("uvx") or "uvx"
    vacant_home = str(ls.vacant_home())
    mcp_config = {
        "vacant": {
            "command": uvx_path,
            "args": ["--from", VACANT_GIT_REF, "vacant", "mcp", "--name", name],
            "env": {
                "VACANT_NAME": name,
                "VACANT_HOME": vacant_home,
                "PATH": os.environ.get(
                    "PATH",
                    "/usr/local/bin:/usr/bin:/bin",
                ),
            },
        }
    }
    (bundle_dir / ".mcp.json").write_text(json.dumps(mcp_config, indent=2) + "\n", encoding="utf-8")


def install_openclaw(*, name: str = "alice", force: bool = False, dry_run: bool = False) -> str:
    """Render a Vacant OpenClaw bundle to disk and link it via
    ``openclaw plugins install -l``.

    The previous implementation pointed OpenClaw at the GitHub URL
    ``https://github.com/cosmopig/Vacant.git#main:examples/openclaw``
    which OpenClaw 2026.5.x rejects ("URLs are not allowed"), and the
    upstream bundle's `.mcp.json` env values use shell-substitution
    syntax (`${VACANT_NAME:-alice}`) that OpenClaw passes through
    verbatim — the spawned MCP subprocess saw the literal string and
    failed Pfix5 strict-on-missing. This implementation renders a
    self-contained bundle directory under
    ``~/.vacant/.openclaw-bundle/<name>/`` with absolute paths and
    literal env values, then hands that path to OpenClaw.
    """
    if shutil.which("openclaw") is None:
        return (
            "ERROR: openclaw CLI not on PATH. Install OpenClaw per its "
            "own docs (https://docs.openclaw.ai/) — typically "
            "`npm install -g openclaw` — then re-run."
        )

    bundle_dir = ls.vacant_home() / ".openclaw-bundle" / name

    install_cmd = ["openclaw", "plugins", "install", "-l", str(bundle_dir)]
    if force:
        install_cmd.append("--force")

    if dry_run:
        return (
            f"[dry-run] would render bundle at {bundle_dir} and run:\n"
            f"  $ {' '.join(install_cmd)}\n"
            f"  (then restart OpenClaw gateway to load: `openclaw gateway restart`"
            f" or `systemctl --user restart openclaw-gateway.service`)"
        )

    try:
        _render_openclaw_bundle(bundle_dir=bundle_dir, name=name)
    except OSError as exc:
        return f"ERROR: could not render bundle at {bundle_dir}: {exc}"

    # S603: install_cmd args are hard-coded strings except for the rendered
    # bundle path which we just created, and the optional --force flag.
    try:
        subprocess.run(install_cmd, check=True)  # noqa: S603
    except subprocess.CalledProcessError as exc:
        return f"ERROR: openclaw plugins install failed: {exc}"
    return (
        f"rendered OpenClaw bundle at {bundle_dir} and linked into OpenClaw.\n"
        "Restart the gateway to pick it up:\n"
        "  $ systemctl --user restart openclaw-gateway.service "
        "  (if installed as service)\n"
        "  $ openclaw gateway restart "
        "  (otherwise)"
    )


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
    insecure_demo: bool = False,
    skip_init: bool = False,
) -> str:
    """Dispatch ``vacant install <client>`` to the right handler.

    Returns the status line the CLI should print. Raises
    ``ValueError`` for unknown clients.

    Pfix5 contract: for clients whose runtime invocation embeds a
    specific ``--name``, ensure ``~/.vacant/<name>/`` exists first
    (creating it via ``init_vacant`` if needed). Returns an ERROR
    string immediately if identity bootstrap can't proceed (e.g.
    no keyring + no ``--insecure-demo``).
    """
    if client not in SUPPORTED_CLIENTS:
        supported = ", ".join(SUPPORTED_CLIENTS)
        raise ValueError(f"unknown client {client!r}; supported: {supported}")

    # claude-code prints the slash-command flow only; doesn't bind to
    # a specific identity (the plugin manifest uses no --name), so no
    # identity work makes sense here.
    if client == "claude-code":
        return install_claude_code()

    # openclaw bundle uses VACANT_NAME=${VACANT_NAME:-default} so a
    # specific name isn't pinned. We still bootstrap the requested
    # name so a follow-up `VACANT_NAME=<name> openclaw …` finds it.
    if client == "openclaw":
        identity_msg = ensure_identity(
            name, insecure_demo=insecure_demo, skip_init=skip_init, dry_run=dry_run
        )
        if identity_msg and identity_msg.startswith("ERROR"):
            return identity_msg
        openclaw_msg = install_openclaw(name=name, force=force, dry_run=dry_run)
        return _join_msgs(identity_msg, openclaw_msg)

    # Clients that pin --name into the runtime invocation: bootstrap
    # identity first so spawning vacant later doesn't fail.
    identity_msg = ensure_identity(
        name, insecure_demo=insecure_demo, skip_init=skip_init, dry_run=dry_run
    )
    if identity_msg and identity_msg.startswith("ERROR"):
        return identity_msg

    if client == "claude-desktop":
        cfg_msg = install_claude_desktop(
            config_path=config_path, name=name, force=force, dry_run=dry_run
        )
    elif client == "cursor":
        cfg_msg = install_cursor(config_path=config_path, name=name, force=force, dry_run=dry_run)
    elif client == "windsurf":
        cfg_msg = install_windsurf(config_path=config_path, name=name, force=force, dry_run=dry_run)
    elif client == "hermes":
        cfg_msg = install_hermes(config_path=config_path, name=name, force=force, dry_run=dry_run)
    else:
        # Unreachable by the SUPPORTED_CLIENTS guard above; keeps mypy happy.
        raise AssertionError(f"unhandled client {client!r}")

    return _join_msgs(identity_msg, cfg_msg)


def _join_msgs(identity_msg: str | None, cfg_msg: str) -> str:
    """Combine the identity-bootstrap status line and the per-client
    config status into a single multi-line output."""
    if identity_msg is None:
        return cfg_msg
    return f"{identity_msg}\n{cfg_msg}"
