# Getting help

## Where to ask

| You want… | Go here |
|---|---|
| **Help running the demo** | [Discussions → Q&A](https://github.com/cosmopig/Vacant/discussions/categories/q-a) |
| **A new feature idea** | [Discussions → Ideas](https://github.com/cosmopig/Vacant/discussions/categories/ideas) |
| **A confirmed bug** | [Issue → Bug report](https://github.com/cosmopig/Vacant/issues/new?template=bug.yml) |
| **A spec inconsistency** | [Issue → Theory inconsistency](https://github.com/cosmopig/Vacant/issues/new?template=theory_inconsistency.yml) |
| **A non-sensitive defense gap** | [Issue → Defense gap](https://github.com/cosmopig/Vacant/issues/new?template=defense_gap.yml) |
| **A security vulnerability** | Email per [SECURITY.md](SECURITY.md) — do **not** file publicly |

## Response time

This is a single-maintainer capstone project. Realistic SLAs:

- Issues: triaged within 1 week
- Discussions: best-effort
- Security reports: 72 hours initial response per [SECURITY.md](SECURITY.md)

If something is blocking your demo / capstone evaluation, mention it in the issue title (`[BLOCKING]`) and I'll prioritize.

## Reading order if you're new

1. [README.md](README.md) — landing page, one-line install, four demo scenarios.
2. [docs/RUNBOOK.md](docs/RUNBOOK.md) — operator manual.
3. [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) — 5-minute walk-through.
4. [CLAUDE.md](CLAUDE.md) — implementation guide, including the 8 load-bearing decisions.
5. [`architecture/THEORY_V5.md`](architecture/THEORY_V5.md) — the spec (45KB, dense).

## Running the demo locally

If you hit issues, please paste the full output of:

```bash
uv --version
python --version
uname -a
git rev-parse HEAD
uv run pytest -q --tb=short
```

into your issue. That covers 90% of the diagnostic context I need.
