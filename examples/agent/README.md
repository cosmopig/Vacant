# `examples/agent/` — `vacant route` recipe

Most agent frameworks (Hermes, OpenClaw, Claude Desktop, Cursor, …)
route LLM ↔ Vacant traffic through OpenAI function-call JSON. Models
below ~7B can't emit that format reliably, so the framework swallows
the call. `vacant route` is the model-agnostic fallback: a tiny
XML-ish action protocol that any LLM with a `/v1/chat/completions`
surface can drive. It ships as a first-class CLI subcommand in
`vacant-network` since Pfix6.

## Run

```bash
# 1. Make sure you have a local vacant identity
uvx --from vacant-network vacant install hermes --insecure-demo
# (or `vacant install openclaw`, or just `vacant init alice --insecure-demo`)

# 2. Point `vacant route` at any OpenAI-compatible LLM
LLM_BASE_URL=http://192.168.50.130:11434/v1 LLM_API_KEY=ollama \
uvx --from vacant-network vacant route \
  --name alice --model gemma4:e2b \
  "Translate this Chinese paragraph; spawn a D1 child if helpful."
```

Works against Ollama, vLLM, LM Studio, Together, Groq, Anthropic
compat shim, OpenAI, … anything that speaks `/v1/chat/completions`.

## Action protocol the LLM is taught

```text
<vacant_action name="vacant_describe"></vacant_action>

<vacant_action name="vacant_spawn">{"policy_mutation": "<rule>",
                                    "child_name_hint": "<short>"}</vacant_action>

<vacant_action name="final">Answer to the user.</vacant_action>
```

Exactly one action block per LLM turn. The loop parses the block,
dispatches the named MCP tool to `vacant mcp --name <name>`, feeds
the result back, and re-prompts the LLM until it emits `final`.

## Why this works on tiny models

ReAct-style protocols predate OpenAI function-calling and have been
known-good on sub-7B models for years. The action block is a single
regex pattern, not a JSON-schema-driven function call, so a 2-5B
model that struggles with strict JSON can still hit the contract.

## Direct script (legacy)

`route.py` is now a thin shim around `vacant.cli.route`. Prefer
`uvx --from vacant-network vacant route ...` over invoking the script
directly — the CLI surface gets the canonical option parsing.

## Caveats

- One action per LLM turn (no parallel calls).
- `vacant_call` / `vacant_call_with_sampling` are intentionally NOT in
  the default action enum — they need hand-crafted signed envelopes
  an LLM shouldn't assemble. Drive those from Python; see
  `tests/integration/test_mcp_sampling.py`.
- Treat this as a *demo of model-agnostic routing*, not a hardened
  agent runtime.
