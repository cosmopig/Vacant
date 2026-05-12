"""Static validation of `examples/openclaw/` bundle manifest.

We don't spawn OpenClaw here. The OpenClaw bundle docs (and the de
facto Claude Code plugin format that OpenClaw shares) prescribe a
specific shape for `.claude-plugin/plugin.json`, `.mcp.json`, and the
`skills/<name>/SKILL.md` skill metadata. These tests assert the
shipped bundle satisfies that shape so we catch regressions when
someone edits the manifest by hand.

References:
- https://docs.openclaw.ai/plugins/bundles (MCP server config shape)
- Claude Code plugin schema (community-maintained):
  https://github.com/hesreallyhim/claude-code-json-schema
"""

from __future__ import annotations

import json
import re
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_ROOT = REPO_ROOT / "examples" / "openclaw"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# -- bundle structure --------------------------------------------------------


def test_bundle_root_has_required_files() -> None:
    """Bundle root must carry the four discoverable files."""
    assert (BUNDLE_ROOT / ".claude-plugin" / "plugin.json").is_file()
    assert (BUNDLE_ROOT / ".mcp.json").is_file()
    assert (BUNDLE_ROOT / "README.md").is_file()
    assert (BUNDLE_ROOT / "skills").is_dir()


# -- plugin.json schema ------------------------------------------------------


def test_plugin_manifest_has_required_fields() -> None:
    """name + version + description are required by the Claude bundle schema."""
    plugin = _load_json(BUNDLE_ROOT / ".claude-plugin" / "plugin.json")
    assert isinstance(plugin.get("name"), str) and plugin["name"]
    assert isinstance(plugin.get("version"), str) and plugin["version"]
    assert isinstance(plugin.get("description"), str) and plugin["description"]


def test_plugin_manifest_name_is_kebab_case() -> None:
    """The plugin id must be filesystem/URL safe; kebab-case is the convention."""
    plugin = _load_json(BUNDLE_ROOT / ".claude-plugin" / "plugin.json")
    assert re.fullmatch(r"[a-z][a-z0-9-]*", plugin["name"]), plugin["name"]


def test_plugin_manifest_version_is_semver_like() -> None:
    plugin = _load_json(BUNDLE_ROOT / ".claude-plugin" / "plugin.json")
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:[-+].*)?", plugin["version"]), plugin["version"]


def test_plugin_manifest_optional_fields_well_formed() -> None:
    plugin = _load_json(BUNDLE_ROOT / ".claude-plugin" / "plugin.json")
    if "author" in plugin:
        assert isinstance(plugin["author"], dict)
        assert "name" in plugin["author"] and plugin["author"]["name"]
    if "homepage" in plugin:
        assert isinstance(plugin["homepage"], str) and plugin["homepage"].startswith(
            ("http://", "https://")
        )
    if "repository" in plugin:
        assert isinstance(plugin["repository"], str) and plugin["repository"].startswith(
            ("http://", "https://", "git+")
        )
    if "license" in plugin:
        assert isinstance(plugin["license"], str) and plugin["license"]
    if "keywords" in plugin:
        assert isinstance(plugin["keywords"], list)
        assert all(isinstance(k, str) for k in plugin["keywords"])
    if "skills" in plugin:
        assert isinstance(plugin["skills"], str)
        # When the value is a path, the directory must exist.
        skills_dir = BUNDLE_ROOT / plugin["skills"].lstrip("./").rstrip("/")
        assert skills_dir.is_dir(), skills_dir


# -- .mcp.json schema (server-name → config map) ----------------------------


def test_mcp_json_registers_vacant_server() -> None:
    """`.mcp.json` body must be a server-name → config map containing "vacant"."""
    mcp = _load_json(BUNDLE_ROOT / ".mcp.json")
    assert isinstance(mcp, dict), "mcp.json must be a JSON object"
    assert "vacant" in mcp, list(mcp.keys())


def test_mcp_json_vacant_entry_is_stdio_shape() -> None:
    """OpenClaw bundle docs forbid mixing `command` and `url` on a server.

    For a stdio server we want command + args + (optional) env. Surface
    a clear error if any of those drift to a wrong type.
    """
    mcp = _load_json(BUNDLE_ROOT / ".mcp.json")
    server = mcp["vacant"]
    assert "url" not in server, "stdio server cannot also declare url"
    assert isinstance(server["command"], str) and server["command"]
    assert isinstance(server["args"], list)
    assert all(isinstance(a, str) for a in server["args"])
    if "env" in server:
        assert isinstance(server["env"], dict)
        assert all(isinstance(k, str) and isinstance(v, str) for k, v in server["env"].items())


def test_mcp_json_command_invokes_vacant_mcp() -> None:
    """The shipped command must spell `uvx ... vacant mcp` (matches the CLI)."""
    mcp = _load_json(BUNDLE_ROOT / ".mcp.json")
    server = mcp["vacant"]
    assert server["command"] == "uvx", server["command"]
    args = server["args"]
    # Must contain `vacant` followed by `mcp` somewhere in the arglist —
    # uvx may have flag pairs (--from <pkg>) before them.
    pairs = list(pairwise(args))
    assert ("vacant", "mcp") in pairs, args
    # And must reference the GitHub repo (so `uvx --from git+...` works
    # without requiring a local checkout).
    joined = " ".join(args)
    assert "github.com/cosmopig/Vacant" in joined or "git+" in joined, args


def test_mcp_json_vacant_name_default_aligns_with_pfix5() -> None:
    """`VACANT_NAME` must default to `alice` so a third party who runs
    `vacant install openclaw` (which bootstraps `alice`) gets a working
    bundle without having to `export VACANT_NAME=alice` themselves.

    Pfix5 contract: the installer creates `alice`; the bundle must
    resolve to the same name when no override is present.
    """
    mcp = _load_json(BUNDLE_ROOT / ".mcp.json")
    env = mcp["vacant"].get("env", {})
    assert env.get("VACANT_NAME") == "${VACANT_NAME:-alice}", env.get("VACANT_NAME")


def test_mcp_json_command_is_resolvable_via_vacant_cli() -> None:
    """`vacant mcp` must actually be a registered Typer subcommand."""
    from typer.testing import CliRunner

    from vacant.cli import app

    result = CliRunner().invoke(app, ["mcp", "--help"])
    assert result.exit_code == 0, result.stdout
    assert "stdio MCP server" in result.stdout.lower() or "mcp" in result.stdout.lower()


# -- skills metadata --------------------------------------------------------


def test_vacant_call_skill_has_yaml_frontmatter() -> None:
    """SKILL.md needs a frontmatter block with `name` and `description`."""
    skill = (BUNDLE_ROOT / "skills" / "vacant-call" / "SKILL.md").read_text(encoding="utf-8")
    assert skill.startswith("---\n"), "SKILL.md must lead with YAML frontmatter"
    end = skill.find("\n---", 4)
    assert end > 0, "frontmatter is not closed"
    front = skill[4:end]
    assert "name: vacant-call" in front
    assert "description:" in front


def test_vacant_call_skill_lists_three_tools() -> None:
    """The skill should reference all three vacant MCP tools explicitly."""
    skill = (BUNDLE_ROOT / "skills" / "vacant-call" / "SKILL.md").read_text(encoding="utf-8")
    for tool in ("vacant_describe", "vacant_call", "vacant_call_with_sampling"):
        assert tool in skill, tool


# -- paste-config siblings (cursor / windsurf / claude-desktop / hermes) ----


@pytest.mark.parametrize(
    ("client", "filename"),
    [
        ("claude-desktop", "claude_desktop_config.json"),
        ("cursor", "mcp.json"),
        ("windsurf", "mcp_config.json"),
    ],
)
def test_paste_config_clients_use_canonical_command(client: str, filename: str) -> None:
    """All paste-config snippets must use the same `uvx ... vacant mcp` shape."""
    cfg_path = REPO_ROOT / "examples" / client / filename
    assert cfg_path.is_file(), cfg_path
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    server = cfg["mcpServers"]["vacant"]
    assert server["command"] == "uvx"
    args = server["args"]
    pairs = list(pairwise(args))
    assert ("vacant", "mcp") in pairs
    assert any("github.com/cosmopig/Vacant" in a for a in args)


def test_hermes_toml_uses_canonical_command() -> None:
    """Hermes uses TOML; same canonical command must show up."""
    import tomllib

    cfg_path = REPO_ROOT / "examples" / "hermes" / "hermes_mcp.toml"
    assert cfg_path.is_file()
    cfg = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    servers = cfg["mcp_servers"]
    assert isinstance(servers, list) and len(servers) >= 1
    vacant = next(s for s in servers if s["name"] == "vacant")
    assert vacant["command"] == "uvx"
    args = vacant["args"]
    pairs = list(pairwise(args))
    assert ("vacant", "mcp") in pairs


# -- examples README index --------------------------------------------------


def test_examples_readme_links_each_client() -> None:
    """examples/README.md must link to all five client subdirs."""
    text = (REPO_ROOT / "examples" / "README.md").read_text(encoding="utf-8")
    for client in ("openclaw", "claude-desktop", "cursor", "windsurf", "hermes"):
        assert f"]({client}/)" in text, client
