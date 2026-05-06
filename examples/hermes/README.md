# Vacant ↔ Nous Hermes

Paste-config recipe for Nous Research's
[Hermes Agent](https://github.com/NousResearch/Hermes-Agent) /
[Hermes-MCP](https://github.com/NousResearch/Hermes-MCP) — connect
Hermes to a Vacant identity over MCP stdio.

## Pre-flight

```bash
uvx --from git+https://github.com/cosmopig/Vacant.git vacant init alice
```

## Install

Hermes reads its MCP server list from a TOML config (the file path
varies between builds — most Hermes deployments keep it at
`~/.config/hermes/mcp.toml` or pass it via `--mcp-config <path>` on
the CLI; check `hermes --help`). Merge the contents of
[`hermes_mcp.toml`](hermes_mcp.toml):

```toml
[[mcp_servers]]
name = "vacant"
command = "uvx"
args = [
    "--from",
    "git+https://github.com/cosmopig/Vacant.git",
    "vacant",
    "mcp",
]

[mcp_servers.env]
VACANT_NAME = "alice"
```

Restart Hermes (or run `hermes mcp reload`).

> **Sampling status:** Hermes-MCP's reverse `sampling/createMessage`
> support has been landing iteratively. If `vacant_call_with_sampling`
> fails with *"client did not advertise sampling capability"*, your
> Hermes build likely predates that feature; the other two tools work
> regardless.

## Verify

```bash
hermes mcp list
# expect "vacant" with three tools:
#   vacant_describe / vacant_call / vacant_call_with_sampling
```

## See also

* [`docs/INTEGRATION.md`](../../docs/INTEGRATION.md)
* [`../openclaw/`](../openclaw/) — full plugin-bundle layout
