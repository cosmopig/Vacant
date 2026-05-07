# Integrating Vacant into your client

[English](INTEGRATION.md) · [繁體中文](INTEGRATION.zh-TW.md)

A hands-on guide to grafting a vacant onto a real MCP-aware client
(Claude Desktop, Cursor, Zed, the `@modelcontextprotocol/inspector`
CLI, or anything that speaks the MCP wire protocol). Five minutes to
your first call; another ten to understand `ClientInheritedSubstrate`
— the substrate that lets a vacant run with **no API key of its own**
and borrow the calling client's LLM via MCP `sampling/createMessage`.

If you just want the theory, read
[`architecture/THEORY_V5.md`](../architecture/THEORY_V5.md). This
document is operational.

---

## 0 · Claude Code plugin (one-command install)

If your client is [Claude Code](https://claude.com/claude-code), skip
the rest of this document for the first pass and install the plugin.
The plugin manifest spawns `vacant mcp` over stdio via `uvx`, so you
get the same `vacant_describe` / `vacant_call` MCP tools that §2.4
walks through manually — without writing a config file.

### 0.1 Install

Inside any Claude Code session:

```text
/plugin marketplace add cosmopig/Vacant
/plugin install vacant@cosmopig-vacant
```

Restart the session (close + reopen, or `/restart`) so Claude Code
picks up the new MCP server.

### 0.2 Verify

```text
/mcp
```

You should see a `vacant` MCP server listed with status `connected`.
Then ask Claude:

> *Use the vacant_describe tool to show me the local vacant's identity.*

The response is a JSON dict with `vacant_id`, `capability_text`, and
(if you've run `vacant init` locally) on-disk halo metadata. If you
haven't run `vacant init`, the identity is *ephemeral* — fresh
keypair per launch — and the server's stderr shows a `WARN:` line.

### 0.3 Stable identity (optional)

```bash
uv tool install vacant   # or: brew install uv ; uvx pip install vacant
vacant init alice        # creates ~/.vacant/alice/ + stores the seed in your OS keyring
```

The next time Claude Code restarts the plugin's MCP subprocess,
`vacant mcp` picks up `~/.vacant/alice/` automatically. See
[`SECURITY.md`](../SECURITY.md) §"Local key storage" for the threat
model on the keyring vs. `--insecure-demo` paths.

### 0.4 Troubleshooting

- **`/mcp` doesn't list `vacant`.** Confirm `uvx` is on
  `$PATH` from inside Claude Code's shell (some GUI launchers don't
  inherit your interactive shell's path). Check the session log; the
  most common error is `uvx: command not found`. Fix: install
  [uv](https://docs.astral.sh/uv/) and `/plugin reload vacant`.
- **First launch is slow.** First-time `uvx` resolves dependencies
  from PyPI (20–60 seconds on a slow network). Subsequent launches
  are instant (uv caches).
- **You see `WARN: no local vacant on disk`.** Expected — see §0.3.
  The warning lands on the MCP subprocess's stderr; how visible that is
  depends on the host. Claude Desktop and Cursor surface stderr in
  *Logs → MCP servers → vacant* (you may need to scroll up to see the
  startup message). The MCP Inspector CLI prints stderr inline. Some
  IDEs swallow stderr entirely — if you don't see the warning anywhere
  but want to confirm whether identity is ephemeral, call the
  `vacant_describe` tool: the JSON response includes a
  `"key_storage": "ephemeral" | "keyring" | "plaintext"` field that is
  always reliable regardless of how the host renders stderr.
- **You want to drive the vacant from your own MCP client.** Skip the
  plugin path; jump to §2.4 below for a manual `mcp.json` example.

---

## 1 · Prerequisites

| Tool | Version | Why |
|---|---|---|
| Python | ≥ 3.12 | Project requires-python |
| [`uv`](https://docs.astral.sh/uv/) | latest | Project dependency / venv manager |
| An MCP-aware client | any | Claude Desktop, Cursor, Zed, MCP Inspector, or your own SDK code |

Clone and install:

```bash
git clone https://github.com/cosmopig/Vacant.git
cd Vacant
uv sync --all-extras
```

Smoke-check:

```bash
uv run vacant --help            # Typer help; lists all subcommands
uv run vacant serve --help      # confirms the serve command is wired
```

### MCP client compatibility

| Client | stdio | sampling/createMessage |
|---|---|---|
| Claude Desktop | ✓ | ✓ (≥ 1.x) |
| Cursor | ✓ | ✓ (recent builds) |
| Zed | ✓ | ✗ (read-only consumer) |
| `@modelcontextprotocol/inspector` | ✓ | ✓ (passes through to your handler) |
| `mcp` Python SDK (`ClientSession`) | ✓ | ✓ (`sampling_callback=`) |

Sampling is the only feature `ClientInheritedSubstrate` needs back from
the client. Clients without sampling can still call `vacant_describe`
and `vacant_call`, but `vacant_call_with_sampling` will fail.

---

## 2 · 5-minute Quickstart

### 2.1 Create a local vacant

```bash
mkdir -p ~/.vacant
uv run vacant init alice
# {"name": "alice", "vacant_id": "<64-hex>"}
```

This writes `~/.vacant/alice/{key.json,logbook.jsonl,meta.json}`. The
key is mode 0600.

### 2.2 (Optional) Publish a halo to a local registry

If you only want MCP integration you can skip this. To put alice on a
registry:

```bash
# In one terminal: registry server (P4 — see RUNBOOK.md)
uv run uvicorn vacant.registry.rpc:build_app --port 8080

# In another terminal:
export VACANT_REGISTRY_URL=http://127.0.0.1:8080
uv run vacant publish --capability "echo" \
  --endpoint http://127.0.0.1:8443/a2a/message/send
uv run vacant status
```

### 2.3 Start the vacant as a server

```bash
uv run vacant serve --name alice --port 8443
# {"name":"alice","vacant_id":"<hex>","host":"127.0.0.1","port":8443,"mcp":false}
```

Check it:

```bash
curl -s http://127.0.0.1:8443/health
# {"vacant_id":"<hex>","state":"LOCAL","name":"alice"}

curl -s http://127.0.0.1:8443/card | jq
# capability_card_blob_hex + halo_version
```

### 2.4 Plug into Claude Desktop / Cursor over MCP

Add the vacant to your client's MCP config. For Claude Desktop, edit
`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "vacant-alice": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/Vacant",
        "run",
        "python",
        "-m",
        "vacant.cli.mcp_serve_test_runner",
        "alice"
      ]
    }
  }
}
```

> **Why `mcp_serve_test_runner` and not `vacant serve --mcp`?**
> `vacant serve --mcp` runs HTTP **and** MCP at the same time —
> useful when you want both transports. `mcp_serve_test_runner`
> is stdio-only, which is what most MCP clients drive. Pick the
> shape that matches your deployment.

Restart Claude Desktop. You'll see three tools surface:

* `vacant_describe` — capability text + halo metadata
* `vacant_call` — accepts a signed A2A envelope, runs it through the
  same envelope verification + replay protection as the HTTP path
* `vacant_call_with_sampling` — borrows the client's LLM (next section)

Ask Claude: *"Use vacant-alice's vacant_describe tool."* It should
return the vacant_id and the capability text you set.

### 2.5 (Bonus) Driving from MCP Inspector

```bash
npx @modelcontextprotocol/inspector \
  uv --directory $PWD run python -m vacant.cli.mcp_serve_test_runner alice
```

Same three tools. Inspector lets you fire `tools/call` requests
manually — useful for debugging signature failures.

---

## 3 · `ClientInheritedSubstrate` — borrowing the client's LLM

This is the load-bearing piece for "graft a vacant onto your client":
**a deployed vacant carries no API key**. When the client calls a
vacant tool that needs inference, the vacant turns around and asks the
client (over standard MCP `sampling/createMessage`) to do that
inference on its behalf.

### Why

* No secret to leak. A vacant's on-disk state is just an Ed25519
  keypair + logbook; nothing about LLM access.
* No vendor lock-in. Whatever LLM the calling client has access to,
  the vacant uses for that one call.
* Reputation per-substrate stays auditable. The substrate identity is
  recorded as `client-inherited:<caller_vacant_id>:<model_hint>` so
  the borrow is fully attributable. See ADR
  [`D017_client_inherited_substrate.md`](../architecture/decisions/D017_client_inherited_substrate.md).

### Wire flow

```
Client (Claude Desktop)                Vacant (your serve subprocess)
       │                                              │
       │── tools/call vacant_call_with_sampling ──────▶│
       │     { user_prompt, system_prompt,            │
       │       model_hint, caller_vacant_id_hex }     │
       │                                              │
       │                         ┌────────────────────┤
       │                         │ build              │
       │                         │ ClientInherited    │
       │                         │ Substrate(cb=...)  │
       │                         └────────────────────┤
       │                                              │
       │◀──── sampling/createMessage(messages, …) ────│
       │                                              │
       │── createMessage result (your LLM's output) ─▶│
       │                                              │
       │                         ┌────────────────────┤
       │                         │ wrap as            │
       │                         │ SubstrateResponse  │
       │                         │ (substrate name +  │
       │                         │  proof)            │
       │                         └────────────────────┤
       │                                              │
       │◀── tools/call result { text, substrate, …} ──│
```

The vacant's logbook records the substrate name
(`client-inherited:<caller>:<model>`) on the entry it appends — the
borrow is auditable post-hoc by anyone reading the chain.

### Calling it from the `mcp` Python SDK

This is the canonical example, and it's what
[`tests/integration/test_mcp_sampling.py`](../tests/integration/test_mcp_sampling.py)
asserts:

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import (
    CreateMessageRequestParams, CreateMessageResult,
    SamplingCapability, TextContent,
)

async def my_sampling_cb(ctx, params: CreateMessageRequestParams) -> CreateMessageResult:
    user_text = next(
        m.content.text for m in params.messages
        if isinstance(m.content, TextContent)
    )
    # Replace with your real LLM call.
    answer = await my_llm.complete(system=params.systemPrompt, user=user_text)
    return CreateMessageResult(
        role="assistant",
        content=TextContent(type="text", text=answer),
        model="claude-sonnet-4-6",
        stopReason="endTurn",
    )

params = StdioServerParameters(
    command="uv",
    args=["--directory", PROJECT_ROOT, "run", "python",
          "-m", "vacant.cli.mcp_serve_test_runner", "alice"],
)
async with stdio_client(params) as (r, w):
    async with ClientSession(
        r, w,
        sampling_callback=my_sampling_cb,
        sampling_capabilities=SamplingCapability(),
    ) as session:
        await session.initialize()
        result = await session.call_tool(
            "vacant_call_with_sampling",
            arguments={
                "user_prompt": "What is 2+2?",
                "system_prompt": "Be terse.",
                "model_hint": "claude-sonnet-4-6",
                "caller_vacant_id_hex": MY_CALLER_VID_HEX,
            },
        )
```

`result.content[0].text` is JSON containing `text` (the LLM's
response), `substrate` (the auditable identity string), and `proof`
(the borrow metadata).

### Reputation accounting

When a borrowed-substrate inference contributes to a reputation
update, it goes into the `client-inherited:*` bucket — **not** the
vacant's intrinsic substrate score. This means a vacant that always
runs under Claude scores its records as "Claude-via-borrow" and a
later Mistral-via-borrow comparison is still meaningful.

---

## 4 · OpenClaw plugin bundle install

Drop-in plugin bundle for [OpenClaw](https://docs.openclaw.ai/),
following the
[`.claude-plugin/`](https://docs.openclaw.ai/plugins/bundles) bundle
format that OpenClaw shares with Claude Code, Cursor, and Windsurf.
The full bundle ships at [`examples/openclaw/`](../examples/openclaw/) —
this section is the install path.

```
examples/openclaw/
├── .claude-plugin/plugin.json     # bundle manifest
├── .mcp.json                      # MCP server registration
├── skills/vacant-call/SKILL.md    # tells the agent when to call which tool
└── README.md
```

### Install

```bash
git clone https://github.com/cosmopig/Vacant.git
cd Vacant

openclaw plugins install ./examples/openclaw   # local-dir install
openclaw plugins list                          # verify "vacant" enabled
openclaw gateway restart
```

Or install straight from GitHub:

```bash
openclaw plugins install \
  https://github.com/cosmopig/Vacant.git#main:examples/openclaw
openclaw gateway restart
```

### Pre-flight

The bundle needs a local vacant to host. Create one once:

```bash
uvx --from git+https://github.com/cosmopig/Vacant.git vacant init alice
export VACANT_NAME=alice
```

`VACANT_NAME` (default `default` in the bundle env) selects which
vacant the MCP server hosts. The bundle command `uvx --from git+... vacant mcp`
runs the stdio MCP server using the vacant under `~/.vacant/$VACANT_NAME/`.

### Verify

Inside OpenClaw, ask:

> *"Use the vacant plugin's vacant_describe tool."*

Expected: a JSON object with `vacant_id`, `capability_text`, and
`halo_version`. The `vacant-call` skill in the bundle tells the agent
which of the three tools to pick for which user intent.

### Other clients (paste-config recipes)

| Client | Recipe |
|---|---|
| Claude Desktop | [`examples/claude-desktop/`](../examples/claude-desktop/) |
| Cursor | [`examples/cursor/`](../examples/cursor/) |
| Windsurf | [`examples/windsurf/`](../examples/windsurf/) |
| Nous Hermes | [`examples/hermes/`](../examples/hermes/) |

These four are paste-config rather than full bundles — copy the JSON
(or TOML for Hermes) into the client's MCP config and restart. Same
canonical command, same three tools.

---

## 5 · Two vacants talking over real network

Skip ahead if all you want is MCP. This section is the live A2A path.

```bash
# Terminal 1
uv run vacant init alice
uv run vacant serve --name alice --port 8443 \
  --endpoint http://127.0.0.1:8443/a2a/message/send

# Terminal 2
uv run vacant init bob
# Use vacant.cli.server.build_serve_app to get bob's signing key,
# or talk to alice via the dispatch helper:

uv run python <<'PY'
import asyncio, httpx
from vacant.cli.server import build_serve_app
from vacant.protocol import (
    A2AMessage, A2APart, call_local, make_httpx_transport,
)
from vacant.protocol.capability_card import deserialize as deserialize_card

async def main():
    bob = build_serve_app("bob")  # bob isn't running a server here;
                                  # we just need bob's keypair.
    async with httpx.AsyncClient() as c:
        r = await c.get("http://127.0.0.1:8443/card")
    alice_card = deserialize_card(bytes.fromhex(r.json()["capability_card_blob_hex"]))
    transport = make_httpx_transport(timeout=5.0)
    result = await call_local(
        target_card=alice_card,
        requester=bob.form,
        requester_signing_key=bob.signing_key,
        payload=A2AMessage(role="ROLE_USER", parts=[A2APart(text="hi alice")]),
        transport=transport,
    )
    print("response:", result.response_envelope.payload.parts[0].text)
    print("verifies under alice's pubkey:",
          result.response_envelope.verify(alice_card.vacant_id.verify_key()))

asyncio.run(main())
PY
```

Real signed envelope round-trip; alice's response verifies under her
on-disk Ed25519 pubkey. This is the live-network test that lives in
[`tests/integration/test_live_two_vacants.py`](../tests/integration/test_live_two_vacants.py)
boiled down to a script you can run by hand.

---

## 6 · Troubleshooting

### `address already in use` on `--port 8443`

```bash
# Find the process holding the port
lsof -i :8443
# Or pick a different port
uv run vacant serve --name alice --port 8444
```

### MCP client doesn't show `vacant_call_with_sampling`

Either the client doesn't advertise sampling capability or it
silently filters tools whose schemas reference `Context`.

* **Claude Desktop**: ensure your version is recent enough; older
  versions don't pass through `sampling/createMessage`.
* **MCP Inspector**: works out of the box.
* **Cursor / Zed**: check release notes — sampling support is rolling
  out gradually.

### `EnvelopeSignatureError: response envelope did not verify`

The remote vacant's response isn't signed by the key you expected.
Common causes:

1. The card you fetched is stale — re-fetch `/card`.
2. The remote vacant rotated its key without updating the card.
3. You're calling the wrong endpoint (e.g. proxy strips the metadata
   block).

Diff the `vacant_id` in `/card` against the `from_vacant_id` in the
response envelope; they must match.

### `the greenlet library is required`

We pin `greenlet` explicitly. If you see this, your `uv sync` ran
against an older lockfile. Run `uv sync --all-extras` after pulling.

### `vacant init <name>` says "already exists"

Each name maps to one directory under `~/.vacant/`. Pick a different
name or `rm -rf ~/.vacant/<name>` (this is destructive — the keypair
is gone).

### Sampling callback fires but the tool returns empty text

Check that your callback returns a `CreateMessageResult` whose
`content` is a `TextContent` (not `ImageContent` or
`ResourceLinkContent`). The vacant only knows how to read text out of
the sampling response.

### MCP server appears to hang on startup

The vacant's stdio MCP server emits no output until the client
initializes. Check:

* The client really sent `initialize` (Inspector has a "Reconnect"
  button if not).
* `VACANT_HOME` is set if you're running outside `~/.vacant`.
* The named vacant exists (`vacant status`).

---

## Where to go next

* [`docs/RUNBOOK.md`](RUNBOOK.md) — running scenarios and the dashboard
* [`docs/DEMO_SCRIPT.md`](DEMO_SCRIPT.md) — 5-minute walkthrough for
  defense / talks
* [`architecture/THEORY_V5.md`](../architecture/THEORY_V5.md) — the
  full theory document
* [`architecture/decisions/D017_client_inherited_substrate.md`](../architecture/decisions/D017_client_inherited_substrate.md)
  — security model behind borrowed substrates

If you build something, open an issue or PR — examples and
client-specific recipes are very welcome.
