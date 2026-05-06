---
name: vacant-call
description: Use this skill when the user wants to call a Vacant agent — a responsibility-layer residency form on top of A2A / MCP — to delegate a task to a remote vacant identity, attest something about a vacant, or invoke `vacant_call_with_sampling` to run inference under the calling client's own LLM.
allowed-tools:
  - mcp__vacant__vacant_describe
  - mcp__vacant__vacant_call
  - mcp__vacant__vacant_call_with_sampling
---

# When to use this skill

The `vacant` MCP server exposes three tools. Pick the right one:

## `vacant_describe`

When the user asks *who/what is this vacant*, *what does it do*, *what's
its halo version*. Returns the capability text + halo metadata + the
public Ed25519 vacant_id. No side effects, cheap to call.

## `vacant_call`

When the user wants to **send a signed request** to the served vacant.
The `envelope` argument must be a JSON-RPC 2.0 `message/send` body with
the caller's signature, sequence number, and previous envelope hash
mounted under `params.message.metadata.vacant`. Most users don't build
these by hand — defer to the user's own tooling or to `vacant call <vid>
<capability>` from the CLI.

If the response envelope's `from_vacant_id` doesn't match the served
vacant's public key, refuse the result and surface the mismatch — the
signature chain is the load-bearing trust layer.

## `vacant_call_with_sampling`

**This is the headline feature.** The vacant has no API key of its own
— when this tool is invoked, the vacant turns around and asks *the
calling client* (you) to do the inference via MCP `sampling/createMessage`.
The result is wrapped through `ClientInheritedSubstrate` so the substrate
identity is recorded as `client-inherited:<caller>:<model_hint>` for
reputation accounting.

Required arguments:
- `user_prompt` — the prompt to run
- `system_prompt` — optional system instruction
- `model_hint` — what model the borrow should be attributed to (e.g.
  `claude-sonnet-4-6`)
- `caller_vacant_id_hex` — the calling vacant's id (used in the substrate
  identity string)

Use this when the user says things like *"run this through the vacant
under my Claude session"*, *"have the vacant infer this without spending
its own tokens"*, or *"borrow my LLM for this vacant call"*.

# Setup the user must complete first

The bundle ships with `command: uvx --from git+... vacant mcp` which
means the vacant CLI is installed transparently the first time the
plugin starts. The user must, however, have created at least one local
vacant on disk:

```bash
uvx --from git+https://github.com/cosmopig/Vacant.git vacant init alice
```

This writes `~/.vacant/alice/{key.json,logbook.jsonl,meta.json}`.
`VACANT_NAME` (defaults to `default` in the bundle env) selects which
vacant the MCP server hosts. If that named vacant doesn't exist, the
server fails fast on the first tool call — instruct the user to either
`vacant init <name>` or set `VACANT_NAME` to an existing vacant.

# When NOT to use this skill

- The user is asking about *theory* (THEORY_V5), not action — answer
  from the docs at https://vacant.zeabur.app/ instead.
- The user is asking *how to deploy a vacant* — point them at
  `docs/INTEGRATION.md` in the Vacant repo, not the MCP tools.
