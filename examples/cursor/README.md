# Vacant ↔ Cursor

Paste-config recipe for Cursor's MCP integration.

## Pre-flight

```bash
uvx --from git+https://github.com/cosmopig/Vacant.git vacant init alice
```

## Install

Cursor reads MCP config from one of two locations:

* **Per-project**: `<your-project>/.cursor/mcp.json`
* **Global** (Cursor ≥ 0.42): `~/.cursor/mcp.json`

Drop the contents of [`mcp.json`](mcp.json) into whichever scope you
prefer. The shape mirrors Claude Desktop's `mcpServers` block, so a
single config works in both — see Cursor's
[Model Context Protocol docs](https://docs.cursor.com/context/model-context-protocol)
for the latest filename and reload behaviour.

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

Open Cursor's *MCP Servers* panel (Settings → Features → MCP) and
flip the toggle on `vacant` if it isn't auto-enabled.

## Tools surfaced

* `vacant_describe`
* `vacant_call`
* `vacant_call_with_sampling` — needs Cursor builds with sampling
  capability (recent releases; check release notes if absent)

## See also

* [`docs/INTEGRATION.md`](../../docs/INTEGRATION.md)
* [`../openclaw/`](../openclaw/) for the full plugin-bundle layout
