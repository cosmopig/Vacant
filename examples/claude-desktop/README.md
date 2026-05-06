# Vacant ↔ Claude Desktop

Paste-config recipe — drop the JSON below into Claude Desktop's MCP
config and you'll get the three vacant tools (`vacant_describe`,
`vacant_call`, `vacant_call_with_sampling`) on next launch.

## Pre-flight

Create at least one local vacant:

```bash
uvx --from git+https://github.com/cosmopig/Vacant.git vacant init alice
```

This writes `~/.vacant/alice/{key.json,logbook.jsonl,meta.json}`. The
`VACANT_NAME` env var below picks which vacant the MCP server hosts.

## Install the config

Edit Claude Desktop's MCP config file:

| Platform | Path |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

Merge the snippet from [`claude_desktop_config.json`](claude_desktop_config.json)
into your existing config. If the file doesn't exist, copy it as-is.

```json
{
  "mcpServers": {
    "vacant": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/cosmopig/Vacant.git",
        "vacant",
        "mcp"
      ],
      "env": {
        "VACANT_NAME": "alice"
      }
    }
  }
}
```

Restart Claude Desktop. Look for the 🔌 icon in the conversation
composer — clicking it should now list `vacant_describe`,
`vacant_call`, and `vacant_call_with_sampling`.

## Sampling note

Claude Desktop ≥ 1.x supports MCP `sampling/createMessage`. That's
what `vacant_call_with_sampling` needs to borrow Claude's LLM session
back from the desktop app. If you're on an older build the first two
tools still work; the sampling tool will return an error explaining
the client doesn't advertise the capability.

## See also

* [`docs/INTEGRATION.md`](../../docs/INTEGRATION.md) — full guide
  including troubleshooting (port conflicts, signature verify failures,
  etc.)
* [`../openclaw/`](../openclaw/) — a real plugin bundle (skills + manifest)
  rather than a paste-config snippet
