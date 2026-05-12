# `examples/agent/` — model-agnostic Vacant route

When the client framework (Hermes, OpenClaw, Claude Desktop, Cursor, …)
exposes vacant as MCP tools, it does so via OpenAI's function-call
contract. Tool-capable models (Claude Sonnet/Opus, GPT-4-class, Qwen
2.5-7B+, Llama-3.1-8B-tool, Mistral-Nemo, …) emit the contract
correctly. Smaller models (Gemma 4 E2B ~5B, Qwen 3 4B, Phi 3 mini, …)
emit free-form text and the framework silently swallows the would-be
tool call.

`route.py` is the bridge: a ReAct-style action loop that lets *any*
LLM with an OpenAI-compatible completions endpoint drive Vacant
correctly, including the small ones.

## Quickstart

```bash
# 1. Make sure you have a local vacant
uvx --from vacant-network vacant install hermes --insecure-demo
# (or `vacant init alice --insecure-demo` if you don't want Hermes wiring)

# 2. Point the route script at any OpenAI-compatible LLM
git clone --depth 1 https://github.com/cosmopig/Vacant.git
cd Vacant
uv sync
LLM_BASE_URL=http://192.168.50.130:11434/v1 LLM_API_KEY=ollama \
LLM_MODEL=gemma4:e2b \
uv run python examples/agent/route.py \
  "Translate this Chinese paragraph and keep cited identifiers verbatim: …"
```

Replace the URL / model with any OpenAI-compat surface. Ollama, vLLM,
LM Studio, Together, Groq, Anthropic compatibility shim, OpenAI itself
— anything that speaks `/v1/chat/completions`.

## Action protocol

The script teaches the LLM (in the system prompt) to emit *exactly
one* action block per turn:

```text
<vacant_action name="vacant_describe"/>

<vacant_action name="vacant_spawn">
{"policy_mutation": "<rule the D1 child should follow>",
 "child_name_hint": "<short label, optional>"}
</vacant_action>

<vacant_action name="final">
The final answer to the user.
</vacant_action>
```

The loop parses these out of plain text, dispatches the named MCP
tool, appends the result to the conversation, and re-prompts the LLM
until it emits `final` (or `--max-rounds` runs out).

## Why this works on tiny models

ReAct-style prompts ("Action: X / Action Input: Y / Observation: Z")
have been validated on sub-7B models for years. The action block is a
single regex pattern, not a JSON-schema-driven function call, so a
2-5B model that can barely follow `Reply with only X` can still hit
the contract.

## Why this isn't a `Skill` in the Hermes / OpenClaw sense

Hermes / OpenClaw skill bundles ship a `SKILL.md` that is *advisory
text* prepended to the LLM's system prompt — they don't intercept the
LLM output. Making small LLMs work requires **dispatcher-side
intervention** (parse the LLM text, route to MCP), which is outside
what a SKILL.md alone can do. `route.py` is that dispatcher, packaged
as a runnable.

To integrate with Hermes / OpenClaw natively, you'd point them at
`route.py` as the agent backend, or run `route.py` as the entry the
user invokes instead of `hermes chat` / `openclaw agent`.

## Tested with

- Gemma 4 E2B (5.1B) via Ollama at a LAN endpoint — reliably emits the
  action block when the system prompt is forceful and `temperature=0`.
- Qwen 3 4B — similar, occasionally drops the closing tag; the loop's
  "nudge" turn recovers it.
- Tool-capable models (Claude, GPT-4) — also work; they don't *need*
  ReAct, but the action protocol is just text so nothing breaks.

## Caveats

- The action protocol does NOT support multi-tool / parallel calls per
  turn. One action per LLM message.
- `vacant_call` / `vacant_call_with_sampling` (signed-envelope tools)
  are intentionally NOT in the default action enum — they require a
  hand-crafted signed envelope that an LLM has no business assembling.
  If your script needs to invoke them, do it directly from Python (as
  the `tests/integration/test_mcp_sampling.py` and the
  `drivers/autonomous_spawn.py` examples show).
- The script is a *demo* of model-agnostic routing, not a hardened
  agent runtime. Don't deploy it as-is on a public host.
