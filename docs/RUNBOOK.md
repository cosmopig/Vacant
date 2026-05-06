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
uv run python -m vacant.mvp.demo --scenario=law_firm
uv run python -m vacant.mvp.demo --scenario=code_review --seed=137
uv run python -m vacant.mvp.demo --scenario=multilingual_translation
uv run python -m vacant.mvp.demo --scenario=self_replication
```

`--substrate` selects the backend:

| Backend | When to use | Notes |
|---|---|---|
| `mock` (default) | CI, unit tests, deterministic demo | Bit-exact reproducible |
| `deterministic` | Demo with canned answers | Uses prompt-hash lookup table |
| `anthropic` | Live demo (claude-sonnet-4-6) | Requires `ANTHROPIC_API_KEY`; rate-limit aware |
| `ollama` | Token-free local demo | Requires Ollama server at `http://localhost:11434` |

Output is JSON-encoded `ScenarioResult` on stdout. Pipe into `jq` to
inspect specific fields:

```bash
uv run python -m vacant.mvp.demo --scenario=self_replication \
  | jq '.metrics'
```

## Run the dashboard

```bash
uv run streamlit run src/vacant/mvp/dashboard.py
```

Streamlit opens at <http://localhost:8501>. Navigate via the left sidebar:

- **網路** -- list of vacants per scenario, with state + 5-dim mean reputation.
- **血緣** -- self_replication's parent_id chain.
- **情境** -- pick a scenario, run it, see events stream + metrics + chain check.
- **指標** -- the 8 metrics from `dispatch/P7_mvp.md` §3.
- **對抗** -- same-controller ring detection demo with the
  "cost-raising not preventing" framing (CLAUDE.md §Same-* detection).

## Expected output at default seeds

See `dispatch/P7_demo_seed.md` for the full spec. Quick reference:

| Scenario | Seed | Highlight |
|---|---|---|
| `law_firm` | 42 | Parent F >= 0.7, R >= 0.65 after 30 calls |
| `code_review` | 137 | Top-2 reviewers F >= 0.8, ranking stable, ring downweighted |
| `multilingual_translation` | 271 | Per-(vacant, substrate) posteriors tracked separately |
| `self_replication` | 314 | 4 spawns (D1/D2/D3/D5), depth=2, D2 graduates |

## Common failures

- **`SubstrateUnavailableError: ANTHROPIC_API_KEY not set`** -- export the
  key or use `--substrate=mock`.
- **`SubstrateUnavailableError: cannot reach http://localhost:11434`**
  -- Ollama server not running. Start with `ollama serve` or use a
  different substrate.
- **Dashboard reports `RuntimeError: There is no current event loop`**
  on first scenario run -- click *Run* once more; Streamlit re-uses
  the loop on subsequent runs.

## Resetting between runs

The dashboard caches scenario results in Streamlit session state. Click
the rerun button (Ctrl+R / `R`) to invalidate the cache and re-run with
a fresh seed.

## Generating updated fixtures

If a scenario's expected output legitimately changes (per
`dispatch/P7_demo_seed.md` §"Updating fixtures"):

```bash
uv run python -m vacant.mvp.demo --scenario=<name> > tmp.json
# Inspect tmp.json -- does it still satisfy the spec invariants?
# If yes, copy the relevant fields into
# tests/integration/fixtures/<name>_seed<N>_expected.json and explain
# the change in the PR description.
```
