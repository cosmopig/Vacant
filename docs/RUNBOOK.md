# P7 Demo Runbook

How to run the Vacant MVP demo locally.

## One-time setup

```bash
uv sync                              # install deps from pyproject.toml + uv.lock
uv run pytest -m slow tests/integration/test_mvp_full.py
# expect: 4 scenario tests + the law_firm tamper-detection regression
```

## Run a single scenario from the CLI

```bash
vacant demo law_firm
vacant demo code_review --seed=137
vacant demo multilingual_translation
vacant demo self_replication
```

(`uv run python -m vacant.mvp.demo --scenario=<name>` is still the
underlying entrypoint; the `vacant demo <name>` wrapper is the
load-bearing interface and the one all other docs reference.)

`--substrate` selects the backend:

| Backend | When to use | Notes |
|---|---|---|
| `mock` (default) | CI, unit tests, deterministic demo | Bit-exact reproducible |
| `deterministic` | Demo with canned answers | Uses prompt-hash lookup table |
| `anthropic` | Live demo (claude-sonnet-4-6) | `ANTHROPIC_API_KEY`; rate-limit aware |
| `openai` | Live demo (gpt-4o; also any OAI-compat endpoint) | `OPENAI_API_KEY` (+ optional `OPENAI_BASE_URL`) |
| `gemini` | Live demo (gemini-2.0-flash) | `GOOGLE_API_KEY` |
| `mistral` | Live demo (mistral-large-latest) | `MISTRAL_API_KEY` |
| `ollama` | Token-free local demo | Requires Ollama server at `http://localhost:11434` |
| `client-inherited` | Vacant served via MCP, brain comes from the calling client | No key on the vacant side; D2, see "Hosting under your client" |

Real-LLM substrates auto-load `.env`; copy `.env.example` → `.env` and
fill only the keys you actually use.

Output is JSON-encoded `ScenarioResult` on stdout. Pipe into `jq` to
inspect specific fields:

```bash
vacant demo self_replication | jq '.metrics'
```

## Live network: serve a vacant + call it

```bash
# Terminal 1 — start a vacant on localhost
vacant init alice
vacant serve --port 8443 --name alice

# Terminal 2 — call it from another shell (real network roundtrip)
vacant call <alice_vid> capability/echo
```

This exercises the A4 path: the request leaves over HTTP, lands on a
real `uvicorn` server, the envelope is signature-verified, and the
response is signed back. The integration test that pins this is
`tests/integration/test_live_serve.py` (`@pytest.mark.slow`).

## MCP transport

```bash
vacant serve --port 8443 --mcp        # exposes A2A + MCP transports
```

Verify externally with `npx @modelcontextprotocol/inspector` or the
`mcp` Python SDK's client. The integration test pinning this end is
`tests/integration/test_mcp_external_client.py`.

## Run the dashboard

```bash
uv run streamlit run src/vacant/mvp/dashboard.py
```

Streamlit opens at <http://localhost:8501>. The dashboard reads
events from a SQLite event store at `var/demo.db` (written by every
`vacant demo <scenario>` run), so a fresh dashboard session replays
the most recent run without recomputing it.

```bash
vacant demo --tail                    # stream live events from var/demo.db to stdout
```

Sidebar pages:

- **網路** — list of vacants per scenario, state + 5-dim mean reputation.
- **血緣** — `self_replication`'s `parent_id` chain.
- **情境** — pick a scenario, run it, see events stream + metrics + chain check.
- **指標** — the 8 metrics from `dispatch/P7_mvp.md` §3.
- **對抗** — adversarial seed-666 ring; same-controller signal detected
  from evidence (CLAUDE.md §Same-* detection: cost-raising, not preventing).

## Expected output at default seeds

See `dispatch/P7_demo_seed.md` for the full spec. Quick reference:

| Scenario | Seed | Highlight |
|---|---|---|
| `law_firm` | 42 | Parent F ≥ 0.7, R ≥ 0.65 after 30 calls |
| `code_review` | 137 | Top-2 reviewers F ≥ 0.8, ranking stable, ring downweighted |
| `multilingual_translation` | 271 | Per-(vacant, substrate) posteriors tracked separately |
| `self_replication` | 314 | 4 spawns (D1/D2/D3/D5), depth=2, D2 graduates |
| `adversarial` (seed-666) | 666 | 4-ring detected by same-controller signal ≥ 0.7 |

## Common failures

- **`SubstrateUnavailableError: ANTHROPIC_API_KEY not set`** — export the
  key, drop it into `.env`, or pick a different `--substrate`.
- **`SubstrateUnavailableError: cannot reach http://localhost:11434`** —
  Ollama server not running. Start with `ollama serve` or use a
  different substrate.
- **`vacant: command not found`** — `uv sync` didn't install the script.
  Either run via `uv run vacant ...` or activate the venv
  (`. .venv/bin/activate`).
- **Dashboard shows stale data** — the dashboard reads from
  `var/demo.db`. Either run a fresh scenario (`vacant demo <name>`) or
  delete `var/demo.db` to start clean.

## Resetting between runs

```bash
rm var/demo.db                        # wipe the demo event store
vacant demo law_firm                  # repopulate
```

The dashboard auto-reloads when `var/demo.db` changes.

## Generating updated fixtures

If a scenario's expected output legitimately changes (per
`dispatch/P7_demo_seed.md` §"Updating fixtures"):

```bash
vacant demo <name> > tmp.json
# Inspect tmp.json — does it still satisfy the spec invariants?
# If yes, copy the relevant fields into
# tests/integration/fixtures/<name>_seed<N>_expected.json and explain
# the change in the PR description.
```
