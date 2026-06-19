# AGENTS.md

## Cursor Cloud specific instructions

### Environment

- Python 3.12+, managed by **uv** (Astral). The update script installs `uv` if missing and runs `uv sync --all-extras`.
- No external services (databases, Docker, API keys) are required for development, testing, or running demos. SQLite is in-process; demos use `MockSubstrate` by default.
- `PATH` must include `$HOME/.local/bin` for `uv` (the update script handles this).

### Common commands

All commands are documented in `CLAUDE.md` and `README.md`. Key ones:

| Task | Command |
|---|---|
| Install/update deps | `uv sync --all-extras` |
| Unit + property tests | `uv run pytest` |
| Integration tests | `uv run pytest -m slow` |
| All tests with coverage | `uv run pytest --cov=vacant --cov-report=term-missing` |
| Lint | `uv run ruff check .` |
| Format check | `uv run ruff format --check .` |
| Type check | `uv run mypy src/` |
| Run demo (no API key) | `uv run vacant demo law_firm` |
| Streamlit dashboard | `uv run streamlit run src/vacant/mvp/dashboard.py --server.headless true` |
| CLI help | `uv run vacant --help` |

### Gotchas

- The Streamlit dashboard reads from `var/demo.db` (SQLite event store). Run a `vacant demo` command first to populate it before launching the dashboard.
- The dashboard's Lineage and Scenario pages may raise SQLite threading errors in certain environments; the Network and Metrics pages work reliably.
- Pre-commit hooks (`.pre-commit-config.yaml`) run ruff + mypy on `src/`. The repo currently has some pre-existing ruff lint/format issues in files added by recent PRs.
- Demos run with `MockSubstrate` by default (deterministic, no API key). Real LLM substrates require setting the appropriate API key in `.env` (copy from `.env.example`).
- The project's PyPI distribution name is `vacant-network` but the Python module name is `vacant` (`import vacant`).
