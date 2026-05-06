# Vacant

Responsibility-layer residency form for AI agents — sits on top of A2A / MCP, gives agents identity, history, reputation, and consequences. Undergraduate thesis project, 2026.

> 一個讓 AI agent 變成「能扛責任的居民」的居民形式，疊在 A2A / MCP 之上補「責任」這一層。

## Status

- **Theory**: V5 final, hardened through 3 rounds of codex adversarial review (`no fatal issues remain`). See `architecture/THEORY_V5.md`.
- **Implementation**: 14-week MVP. P0 bootstrap landed; component PRs P1–P7 in progress. See `architecture/tasks/` and `dispatch/` for breakdown.
- **Docs site**: https://vacant.zeabur.app/ (separate repo: [vacant-docs-web](https://github.com/cosmopig/vacant-docs-web))

## Quick start

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                              # install runtime + dev deps
uv run vacant --help                 # CLI command tree (stubs until P1+)
uv run pytest                        # unit + property tests
uv run pytest --cov=vacant           # with coverage
uv run ruff check . && uv run ruff format --check .
uv run mypy src/
```

The Streamlit dashboard and demo scenarios:

```bash
# Run the dashboard.
uv run streamlit run src/vacant/mvp/dashboard.py

# Or run a single scenario from the CLI.
uv run python -m vacant.mvp.demo --scenario=law_firm
uv run python -m vacant.mvp.demo --scenario=self_replication --seed=314

# Full integration test (4 scenarios + tamper-detection regression).
uv run pytest -m slow tests/integration/test_mvp_full.py
```

See [`docs/RUNBOOK.md`](docs/RUNBOOK.md) for full demo instructions and
[`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) for the 5-minute thesis-defence walk.

## Layout

- `architecture/` — specs, theory, decisions, research (the **contract**; do not edit without an ADR)
- `dispatch/` — prompts for cloud Claude Code sessions, one per component
- `src/vacant/` — implementation
  - `core/` — shared types (`VacantId`, `Logbook`, `ResidentForm`, …), constants, crypto
  - `identity/ runtime/ reputation/ registry/ composite/ protocol/ substrate/ mvp/` — component modules
  - `cli.py` — `vacant` console-script
- `tests/` — `unit/`, `property/` (hypothesis), `integration/` (`pytest -m slow`)

See [CLAUDE.md](CLAUDE.md) for the full implementation guide and conventions.

## License

TBD.
