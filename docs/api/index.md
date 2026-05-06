# API reference

The reference below is **auto-generated** from the source docstrings
via [mkdocstrings](https://mkdocstrings.github.io/). Each top-level
module under `src/vacant/` gets its own page. Use the search
(<kbd>Cmd</kbd>/<kbd>Ctrl</kbd>+<kbd>K</kbd>) to jump straight to a
class or function.

| Module | What lives here |
|---|---|
| [`vacant.core`](core.md) | shared types (`VacantId`, `Logbook`, `ResidentForm`), constants, crypto primitives, errors |
| [`vacant.identity`](identity.md) | Ed25519 keys, layered identity (L0–L3), wash cost, peer attestations, federation root sets |
| [`vacant.runtime`](runtime.md) | 5-state lifecycle, heartbeat, shadow-self drift, D1–D5 spawn paths |
| [`vacant.reputation`](reputation.md) | 5-dim Beta posterior, UCB exploration, STYLO discount, cold start, same-controller detection |
| [`vacant.registry`](registry.md) | SQLite halo store, RPC, aggregation, anti-tamper, visibility |
| [`vacant.composite`](composite.md) | composite parents, child manifests, Tree-Only protocol, graduation |
| [`vacant.protocol`](protocol.md) | A2A / MCP envelope, dispatch, replay protect, capability cards, `vacant serve` |
| [`vacant.substrate`](substrate.md) | abstract `SubstrateBackend` + Mock / Deterministic / Anthropic / OpenAI / Gemini / Mistral / Ollama / client-inherited |
| [`vacant.mvp`](mvp.md) | the four reference scenarios + dashboard + 8 metrics |
| [`vacant.cli`](cli.md) | `vacant` console-script (`init` / `serve` / `call` / `demo` / …) |

## Conventions

- **Docstring style:** Google. Each public function has `Args:`,
  `Returns:`, and (where applicable) `Raises:` blocks.
- **Private members:** functions and classes whose name starts with
  `_` are hidden from the reference by default. If you need to see
  them, read the source — every page has a "show source" toggle on
  individual entries.
- **Drift between docstring and behaviour:** treat as a bug. Open an
  issue and cite the page URL.
