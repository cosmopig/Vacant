# Vacant ↔ Windsurf

Paste-config recipe for Codeium Windsurf's Cascade MCP integration.

## Pre-flight

```bash
uvx --from git+https://github.com/cosmopig/Vacant.git vacant init alice
```

## Install

Windsurf reads MCP config from `~/.codeium/windsurf/mcp_config.json`
(consult Cascade's release notes if your build uses a different
location). Merge the contents of [`mcp_config.json`](mcp_config.json):

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

Reload the Cascade pane. The vacant tools should appear in the tool
picker.

## Tools surfaced

* `vacant_describe`
* `vacant_call`
* `vacant_call_with_sampling` — Windsurf's sampling support is rolling
  out; the tool will surface a clear error if your build doesn't
  advertise the capability

## See also

* [`docs/INTEGRATION.md`](../../docs/INTEGRATION.md)
* [`../openclaw/`](../openclaw/) — full plugin-bundle layout
