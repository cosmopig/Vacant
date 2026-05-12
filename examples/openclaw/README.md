# Vacant — OpenClaw plugin bundle

A drop-in OpenClaw plugin that registers Vacant's MCP server (`vacant`)
and ships a `vacant-call` skill telling OpenClaw when to invoke each of
the three tools.

This is the canonical plugin-bundle layout that **also works for
Claude Code, Cursor, and any tool that reads the
[`.claude-plugin/plugin.json`](https://docs.anthropic.com/) format**.
OpenClaw discovers the bundle through its `.claude-plugin/` marker
directory; the [bundle docs](https://docs.openclaw.ai/plugins/bundles)
list `.claude-plugin/`, `.codex-plugin/`, and `.cursor-plugin/` as the
three supported markers and selects the right surface automatically.

## Layout

```
examples/openclaw/
├── .claude-plugin/
│   └── plugin.json          # bundle manifest (name / version / description)
├── .mcp.json                # MCP server registration (uvx → vacant mcp)
├── skills/
│   └── vacant-call/
│       └── SKILL.md         # tells the agent when to use which vacant tool
└── README.md                # this file
```

## Install

### One-off install from a local clone

```bash
git clone https://github.com/cosmopig/Vacant.git
cd Vacant/examples/openclaw

openclaw plugins install .            # local dir install
openclaw plugins list                 # verify "vacant" is enabled
openclaw gateway restart              # the MCP server picks up on next session
```

### Install from GitHub (no clone)

```bash
openclaw plugins install \
  https://github.com/cosmopig/Vacant.git#main:examples/openclaw
openclaw gateway restart
```

(Subdirectory references match the format documented in
[OpenClaw plugin management](https://docs.openclaw.ai/plugins/manage-plugins).)

### Install via ClawHub marketplace

When the bundle lands on ClawHub:

```bash
openclaw plugins marketplace list community
openclaw plugins install vacant@community
```

## Pre-flight: create at least one local vacant

The MCP server hosts whatever vacant `VACANT_NAME` selects (defaults to
`alice`, matching the Pfix5 `vacant install` contract). Create one
before invoking any vacant tool:

```bash
uvx --from vacant-network vacant install openclaw --insecure-demo
# or, BYO identity:
uvx --from vacant-network vacant init alice
```

To run under a non-default identity, set `VACANT_NAME` in OpenClaw's
env before launch.

## Verify

Inside OpenClaw, ask:

> *"Use the vacant plugin's vacant_describe tool."*

Expected: a JSON object with `vacant_id`, `capability_text`, and
`halo_version`. If you see `error: no local vacant found`, check
`VACANT_NAME` resolves to an existing directory under `~/.vacant/`.

## Tools surfaced

| Tool | What it does |
|---|---|
| `vacant_describe` | Returns capability text + halo metadata |
| `vacant_call` | Accepts a signed A2A envelope, runs it through envelope verification + replay protection |
| `vacant_call_with_sampling` | **The headline feature**: the vacant uses *your* LLM via MCP `sampling/createMessage` — no API key on the vacant side |

`SKILL.md` ([`skills/vacant-call/SKILL.md`](skills/vacant-call/SKILL.md))
tells the agent which one to pick.

## Why this matters

This bundle closes the *"嫁接到客戶端"* (graft-onto-client) thesis
claim from [`architecture/THEORY_V5.md`](../../architecture/THEORY_V5.md):
a vacant deployed under OpenClaw runs with **no API key of its own**.
When inference is needed, the vacant requests sampling back from the
client (OpenClaw, in turn calling its configured LLM provider). The
substrate identity recorded on the vacant side is
`client-inherited:<caller_vacant_id>:<model_hint>` so reputation
per-substrate stays auditable. See
[ADR D017](../../architecture/decisions/D017_client_inherited_substrate.md)
for the security model.

## Related examples

* [`../cursor/`](../cursor/) — paste-config recipe for Cursor
* [`../windsurf/`](../windsurf/) — paste-config recipe for Windsurf
* [`../claude-desktop/`](../claude-desktop/) — `claude_desktop_config.json` snippet
* [`../hermes/`](../hermes/) — Nous Hermes CLI integration
* [`docs/INTEGRATION.md`](../../docs/INTEGRATION.md) — full integration
  walkthrough with troubleshooting
