# Client integration examples

Drop-in configs and bundle layouts for plugging Vacant into the major
MCP-aware tools.

| Directory | Format | Use when |
|---|---|---|
| [`openclaw/`](openclaw/) | full plugin bundle (`.claude-plugin/plugin.json` + `.mcp.json` + `skills/`) | Installing into OpenClaw, where the bundle's skill tells the agent when to invoke each vacant tool |
| [`claude-desktop/`](claude-desktop/) | paste-config (`claude_desktop_config.json` snippet) | Running under Claude Desktop |
| [`cursor/`](cursor/) | paste-config (`mcp.json`) | Running under Cursor |
| [`windsurf/`](windsurf/) | paste-config (`mcp_config.json`) | Running under Codeium Windsurf |
| [`hermes/`](hermes/) | paste-config (`hermes_mcp.toml`) | Running under Nous Hermes |

All five use the same canonical command:

```text
uvx --from git+https://github.com/cosmopig/Vacant.git vacant mcp
```

— and require a local vacant on disk (`vacant init <name>` first; see
each subfolder's README for details).

For the full integration walkthrough — ClientInheritedSubstrate flow,
two-vacant live network demo, troubleshooting — read
[`docs/INTEGRATION.md`](../docs/INTEGRATION.md)
([中文版](../docs/INTEGRATION.zh-TW.md)).
