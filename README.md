# Vacant

Responsibility-layer residency form for AI agents — sits on top of A2A / MCP, gives agents identity, history, reputation, and consequences. Undergraduate thesis project, 2026.

> 一個讓 AI agent 變成「能扛責任的居民」的居民形式，疊在 A2A / MCP 之上補「責任」這一層。

## Status

- **Theory**: V5 final, hardened through 3 rounds of codex adversarial review (`no fatal issues remain`). See `architecture/THEORY_V5.md`.
- **Implementation**: 14-week MVP. See `architecture/tasks/` and `dispatch/` for breakdown.
- **Docs site**: https://vacant.zeabur.app/ (separate repo: [vacant-docs-web](https://github.com/cosmopig/vacant-docs-web))

## Quick start

```bash
uv sync
uv run pytest
uv run streamlit run src/vacant/mvp/dashboard.py
```

## Layout

- `architecture/` — specs, theory, decisions, research
- `dispatch/` — prompts for cloud Claude Code sessions (one per component)
- `src/vacant/` — implementation
- `tests/` — unit / property / integration

See [CLAUDE.md](CLAUDE.md) for the full implementation guide.

## License

TBD.
