# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Vacant — a "responsibility layer" residency form for AI agents that sits on top of A2A / MCP. This repo is the **14-week MVP implementation** of the architecture defined in `architecture/`. It is a working system, not a paper.

The thesis owner works in **繁體中文**. Code, comments, commit messages, and PR descriptions are in **English**. User-facing text in the demo dashboard is in **繁體中文**.

## The core mental model (do not lose this)

A *vacant* is a "resident form": a thing on the network that *can be held responsible*. Its 6 components:

1. `identity` — Ed25519 keypair (idem: numerical sameness)
2. `logbook` — append-only signed history (ipse: continuity through change)
3. `behavior_bundle` — system prompt / policy / tool whitelist (the bridge between idem and ipse)
4. `substrate_spec` — multi-substrate declaration (which LLMs/runtimes it accepts)
5. `runtime` — minimal lifecycle process
6. `capability_card` — public announcement (the halo; every vacant carries its own)

A vacant is **not** an agent framework feature. It is a *form you choose to become*. Anyone can put a vacant on the network. No central authority, no central judge, no central LLM, no central arbiter.

## Load-bearing theory decisions

These decisions have been hardened through 3 rounds of codex adversarial review (`THEORY_V5.md`, `no fatal issues remain`). **Do NOT silently reverse them.** If you must change one, open a `architecture/decisions/D###_*.md` ADR.

- **Agent self-replication (D1-D5) is the primary birth path.** Path A (human-written vacant) is deprecated; do not implement it. Path Zero (one-time human infrastructure) and B/C (transitional) exist but are secondary. See `architecture/THEORY_V5.md` §3.6.
- **Registry is per-vacant, not central.** Each vacant carries its own `capability_card` (the halo). The "Registry" is an aggregation/index layer over halos, with three implementation models (central MVP / federated / DHT). Vacants call each other directly; the registry is never a routed-through component. See §7.1.
- **Sunk-state heartbeat is identity custody attestation, not liveness.** A Sunk vacant cannot do peer review (§4.1). Its heartbeat proves the keypair is still in trusted custody, which matters for lineage attribution. See §4.2.
- **Lineage (parent_id chain), not individual vacants, is the subject of "infinite evolution."** Individual vacants accumulate STYLO-distance discount rollover that bites self-evolution; new lineage members reset the clock. See §4.3.
- **Same-controller / same-substrate / same-stylo detection raises cost, doesn't prevent.** Frame all three as adaptive evasion acknowledged. Don't claim "prevents."
- **Reputation is 5-dimensional Beta posterior**: factual / logical / relevance / honesty / adoption. Per-substrate. With STYLO-based discount rollover. With portability_factor for ecological contribution.
- **Closed children + graduation**: composite parents' children are closed by default (cannot call out), can graduate to public via parent consent + rate limit + 3-layer collusion detection. Same keypair / same logbook through graduation — it's a visibility flag, not an entity upgrade.
- **No central LLM, no central judge.** Verification happens via signed logbooks + peer review + reputation. The Skalse 2022 impossibility theorem framing applies — we don't claim impossibility-defeat, we claim *cost-raising* defenses with quantified bounds.
- **LOCAL state ≠ broken vacant.** A LOCAL vacant (`registry_visibility=none`) is fully functional — it has all 6 components, runs, signs logbooks, evolves. The only difference is it is not in the public announcement layer; only owner/parent can call it directly.

## Repository layout

```
Vacant/
├── architecture/                  ← spec docs (the contract for implementation)
│   ├── THEORY_V5.md               ← canonical theory (V3/V4 are historical, ignore)
│   ├── ARCHITECTURE.md, BRIEFING.md, FAQ.md
│   ├── components/  P1-P7 component specs (read before implementing each)
│   ├── research/    T1-T7 supporting research (cite when implementing)
│   ├── decisions/   D### ADRs (read all before changing protocol)
│   └── tasks/       P1-P8 implementation tasks
│
├── dispatch/                      ← prompts for cloud Claude Code sessions
│   ├── P0_bootstrap.md, P1_runtime.md, P2_identity.md, ... P7_mvp.md
│   └── README.md  (operation guide — order, dependencies, parallelism)
│
├── src/vacant/                    ← the implementation
│   ├── identity/      P2 — keypair, logbook, L0-L3 ID, wash cost
│   ├── runtime/       P1 — 5-state machine, heartbeat, shadow-self, spawn (D1-D5)
│   ├── reputation/    P3 — 5-dim Beta posterior, UCB, STYLO discount, cold start
│   ├── registry/      P4 — SQLite schema, RPC endpoints, halo aggregation
│   ├── composite/     P5 — child sealing/graduation, ChildManifest, Tree-Only
│   ├── protocol/      P6 — A2A/MCP envelope, capability card, direct vacant-call
│   ├── substrate/     ← LLM/runtime backend abstraction
│   ├── core/          ← shared types: VacantId, Logbook, ResidentForm, errors
│   └── mvp/           P7 — 4 demo scenarios + 8 metrics + dashboard
│
├── tests/             ← mirrors src/vacant/ structure
│   ├── unit/          ← per-module tests (target: ≥90% coverage on core paths)
│   ├── property/      ← hypothesis-based: hash chain integrity, state machine invariants
│   ├── integration/   ← multi-vacant scenarios, marked @pytest.mark.slow
│   └── conftest.py    ← shared fixtures
│
├── scripts/           ← one-shot ops (init demo registry, run scenario, dump metrics)
├── alembic/           ← DB migrations
├── pyproject.toml     ← uv-managed; declared deps below
└── .github/workflows/ ← CI: ruff + mypy + pytest on every push
```

## Tech stack (decided — do not switch without raising in PR)

- **Python 3.12** managed by **uv**. `uv sync` to install, `uv run pytest` to test.
- **FastAPI** + **httpx** for HTTP/A2A/MCP endpoints and outgoing calls.
- **SQLite + sqlmodel** for P4. Migrations via **alembic**. (Architected so the swap to Postgres is local to one module.)
- **pynacl** for Ed25519 (the canonical implementation; spec-aligned). **cryptography** for adjacent needs.
- **pytest + pytest-asyncio + hypothesis** for testing.
- **ruff** (lint+format, replaces black/isort/flake8) and **mypy --strict**.
- **structlog** for logging (JSON-formatted).
- **Streamlit** for the P7 demo dashboard.
- LLM substrate: abstract `SubstrateBackend`. Concrete impls: `AnthropicSubstrate` (uses `anthropic` SDK; default model `claude-sonnet-4-6`), `OllamaSubstrate`. Test impls: `MockSubstrate`, `DeterministicSubstrate`.

## The `vacant` CLI

P0 scaffolds `vacant` as a console_script. Each subsequent component PR fills in its commands:

| Command | Owned by | Behavior |
|---|---|---|
| `vacant init <name>` | P2 | create keypair + seed logbook |
| `vacant status [--all]` | P1 | show local vacants and their states |
| `vacant heartbeat` | P1 | manually trigger a heartbeat tick |
| `vacant call <vid> <capability>` | P6 | send a request to a vacant |
| `vacant publish` | P4 | flip LOCAL → ACTIVE (publish halo) |
| `vacant unpublish` | P4 | flip ACTIVE → LOCAL |
| `vacant lineage <vid>` | P4 | print parent chain |
| `vacant attest <target_vid> <claim>` | P2 | issue peer attestation |
| `vacant demo <scenario>` | P7 | run a demo scenario |

Each component PR must:
1. Implement its commands (replace the `"Not yet implemented"` stub)
2. Add `tests/unit/test_cli_<component>.py` with click/typer test runner
3. Update `docs/CLI.md` (create if needed) with usage examples

## Common commands

```bash
uv sync                              # install/update deps from pyproject.toml + uv.lock
uv run pytest                        # full test suite (unit + property; slow excluded)
uv run pytest -m slow                # integration tests
uv run pytest tests/unit/test_identity.py::test_logbook_chain  # single test
uv run pytest --cov=vacant --cov-report=term-missing
uv run ruff check . && uv run ruff format --check .
uv run ruff format .                 # autofix formatting
uv run mypy src/                     # strict typecheck
uv run alembic upgrade head          # apply DB migrations
uv run python -m vacant.mvp.demo --scenario=law-firm
uv run streamlit run src/vacant/mvp/dashboard.py
```

## Code conventions

- **Type everything.** `mypy --strict` is on; no `Any` without `# type: ignore[reason]`.
- **Pydantic v2 / dataclasses for all wire/persistent types.** No bare dicts crossing module boundaries.
- **Async by default** for anything I/O. `async def` + `httpx.AsyncClient` + `aiosqlite`.
- **Dependency injection over globals.** Modules export classes; main wires them up. No singleton `registry = Registry()` at import time.
- **No magic numbers.** Constants live in `src/vacant/core/constants.py` with citations to spec sections (e.g. `STALE_THRESHOLD_DAYS = 180  # THEORY_V5.md §4.1`).
- **Errors are typed.** Each module defines its own `XxxError` hierarchy in `errors.py`. No bare `Exception`.
- **Cryptographic invariants are tested with hypothesis.** Hash chains, signature verification, key derivation — never just example-based.
- **Comments only when WHY is non-obvious.** Spec citations are encouraged (e.g. `# §4.3: lineage resets STYLO discount`). Do not restate what the code already says.

## Testing philosophy

- **Every public function has at least one test.** No exceptions.
- **State machines have exhaustive transition tests.** All `(state, event) → state'` pairs covered.
- **Anti-tamper: write attack tests.** For each defense (sig verify, hash chain, halo signature, attestation freshness), write a test that *tries* to break it and asserts the defense detects/raises.
- **Property tests for cryptographic structures.** hypothesis strategies for: random byte sequences passed to verify must reject; appending to logbook must preserve chain; reordering attestations must invalidate.
- **Integration tests live in `tests/integration/` and are marked `@pytest.mark.slow`.** They spin up multiple vacants in-process and exercise full flows. Excluded from normal `pytest`; included in `pytest -m slow` and CI.
- **No mocking the database in integration tests.** Use real SQLite (in-memory or `tmp_path`). Mocks lie about behavior under concurrent writes.

## What "done" looks like for a component

A component PR is mergeable when:

1. All public APIs are implemented per `architecture/components/P*_*.md`
2. Unit tests cover every public function (≥90% line coverage on the module)
3. Property tests for any cryptographic / state-machine / chain invariants
4. Integration tests for the cross-component flows the spec describes
5. `uv run ruff check`, `uv run ruff format --check`, and `uv run mypy src/` all clean
6. PR description includes: spec sections covered, deviations (if any) with rationale, follow-up work
7. New constants/decisions added to `architecture/decisions/D###_*.md` if the spec was ambiguous

## Adversarial review

Before merging any PR that touches reputation, identity, or registry, run an adversarial review pass: list at least 3 attacks the change might enable, and add tests covering them. The thesis went through 3 rounds of codex adversarial review with `no fatal issues remain`. Do not regress that property.

## What this MVP must demonstrate (P7)

Four scenarios, eight metrics. See `architecture/components/P7_mvp.md`. At minimum, the demo dashboard must show:

- Live vacants on the network (state, capability, current reputation by dimension)
- A scenario being executed end-to-end (client → halo lookup → vacant call → logbook signing → reputation update)
- Same-controller detection firing on a colluding pair
- Lineage tree of a self-replicated vacant family

If you cannot demo it visually, it is not done.

## Things to NOT do

- Do not implement Path A. Path A is deprecated.
- Do not add a central judge / oracle / arbiter. The whole point is there isn't one.
- Do not make Sunk vacants reviewable. They cannot review (§4.1).
- Do not make LOCAL vacants centrally discoverable. Visibility=none is load-bearing.
- Do not bypass `--no-verify` on git hooks; do not skip CI.
- Do not introduce new abstractions speculatively. Three similar lines is better than premature abstraction.
- Do not commit secrets. The Anthropic API key goes in `.env`, never in code.
- Do not silently change theory invariants — open an ADR.
