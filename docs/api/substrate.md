# `vacant.substrate`

LLM / runtime backend abstraction. Substrate is a **resource**, not
the **identity** — the same vacant can run on a different substrate
without changing its keypair. Reputation is tracked
per-`(vacant, substrate)`; `client-inherited` is the load-bearing
deployment for D2 (vacant served via MCP uses the calling client's
LLM).

::: vacant.substrate.base

::: vacant.substrate.errors

::: vacant.substrate.mock

::: vacant.substrate.deterministic

::: vacant.substrate.anthropic

::: vacant.substrate.ollama

::: vacant.substrate.client_inherited
