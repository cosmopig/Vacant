# Vacant

Responsibility-layer residency form for AI agents — sits on top of A2A / MCP, gives agents identity, history, reputation, and consequences. Undergraduate thesis project, 2026.

> 一個讓 AI agent 變成「能扛責任的居民」的居民形式，疊在 A2A / MCP 之上補「責任」這一層。

## Try it (one line)

```bash
curl -LsSf https://raw.githubusercontent.com/cosmopig/Vacant/main/install.sh | bash
```

This installs [uv](https://docs.astral.sh/uv/) if missing, clones into `~/Vacant`, and syncs deps. Then:

```bash
cd ~/Vacant
uv run vacant demo law_firm                        # composite + sub-vacants demo
uv run vacant demo self_replication --seed=314     # D-series lineage demo
uv run streamlit run src/vacant/mvp/dashboard.py   # interactive dashboard
```

No-install alternative — run a scenario without cloning anything:

```bash
uvx --from git+https://github.com/cosmopig/Vacant vacant demo law_firm
```

## Status

- **Theory**: V5 final, hardened through 3 rounds of codex adversarial review (`no fatal issues remain`). See `architecture/THEORY_V5.md`.
- **Implementation**: 14-week MVP, all 8 components (P0–P7) and 5 adversarial review passes (Padv-P2/P3/P4/P5/P6) merged. 713 tests pass; `mypy --strict` clean.
- **Docs site**: https://vacant.zeabur.app/ (separate repo: [vacant-docs-web](https://github.com/cosmopig/vacant-docs-web))

## Manual install

If you'd rather drive every step yourself:

```bash
git clone https://github.com/cosmopig/Vacant.git && cd Vacant
uv sync --all-extras                  # install runtime + dev deps
uv run vacant --help                  # CLI command tree
uv run pytest                         # unit + property tests
uv run pytest -m slow                 # integration tests
uv run pytest --cov=vacant            # with coverage
uv run ruff check . && uv run ruff format --check .
uv run mypy src/
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
