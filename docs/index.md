# Vacant — documentation

A **responsibility-layer residency form** for AI agents on top of A2A /
MCP. Identity, history, reputation, and consequences as a stand-alone
layer that any agent can adopt.

This site has three things:

- **[Theory & background](explain/briefing.md)** — what a vacant is, why
  the problem matters, and the load-bearing decisions that the
  implementation is required to preserve.
- **[Demo & ops](RUNBOOK.md)** — how to run the four reference scenarios
  (`law_firm` / `code_review` / `multilingual_translation` /
  `self_replication`), the live-network walkthrough, and the
  [5-minute demo script](DEMO_SCRIPT.md).
- **[API reference](api/index.md)** — auto-generated from the source
  docstrings via [mkdocstrings](https://mkdocstrings.github.io/). One
  page per top-level module under `src/vacant/`.

## Where to start

| If you want to … | Read this |
|---|---|
| Run the demo in 10 minutes | [Runbook](RUNBOOK.md) → run `vacant demo law_firm` |
| Pitch the project in 5 minutes | [5-minute demo script](DEMO_SCRIPT.md) |
| Understand the central claim | [Briefing](explain/briefing.md) → [Theory V5](explain/theory.md) §1–§4 |
| Wire a vacant into your own client | [Hosting under your client](https://github.com/cosmopig/Vacant#hosting-a-vacant-under-your-client) |
| Find a specific function | [API reference](api/index.md) — Cmd/Ctrl-K opens a search |
| Verify a load-bearing invariant | the `architecture/ENFORCEMENT_POINTS.md` file in the repo (rendered here once PR #29 lands) |

## Quick links

- Source: <https://github.com/cosmopig/Vacant>
- Marketing site: <https://vacant.zeabur.app>
- License: MIT (capstone project, 2026)
