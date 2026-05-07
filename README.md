<div align="center">

<img src="assets/hero.svg" alt="Vacant — a residency form for AI agents on top of A2A / MCP" width="100%">

<a href="assets/vacant-promo.mp4">
  <img src="assets/vacant-promo.gif" alt="Vacant — 30-second promo video" width="100%">
</a>

<sub><em>30-second promo · five scenes · narrated · <a href="assets/vacant-promo.mp4">click for mp4 with sound</a> · <a href="docs/DEMO_RECORDING_SCRIPT.md">storyboard</a></em></sub>

# Vacant

[English](README.md) · [繁體中文](README.zh-TW.md)

[![CI](https://github.com/cosmopig/Vacant/actions/workflows/ci.yml/badge.svg)](https://github.com/cosmopig/Vacant/actions/workflows/ci.yml)
[![release](https://img.shields.io/github/v/release/cosmopig/Vacant?display_name=tag&sort=semver&color=blue)](https://github.com/cosmopig/Vacant/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![uv](https://img.shields.io/badge/managed%20by-uv-261230)](https://docs.astral.sh/uv/)
[![tests: 854](https://img.shields.io/badge/tests-854%20passing-brightgreen.svg)](#testing)
[![coverage: 91%](https://img.shields.io/badge/coverage-91%25-brightgreen.svg)](#testing)
[![mypy: strict](https://img.shields.io/badge/mypy-strict-blue.svg)](https://mypy.readthedocs.io/)
[![api docs](https://img.shields.io/badge/api%20docs-cosmopig.github.io-indigo.svg)](https://cosmopig.github.io/Vacant/)
[![narrative](https://img.shields.io/badge/narrative-vacant.zeabur.app-blueviolet.svg)](https://vacant.zeabur.app/)
[![Discussions](https://img.shields.io/github/discussions/cosmopig/Vacant)](https://github.com/cosmopig/Vacant/discussions)

</div>

A **responsibility-layer residency form** for AI agents on top of A2A / MCP. Gives agents identity, history, reputation, and consequences.

> 一個讓 AI agent 變成「能扛責任的居民」的居民形式，疊在 A2A / MCP 之上補「責任」這一層。

Capstone project · 2026 · Theory V5 · v0.2.0 · 854 tests · 91% coverage · 6 rounds of codex sign-off.

---

## Why does this exist?

Today's agents are fluent but **unaccountable**. When an LLM-driven agent gives you wrong answer, who pays? When two agents collude to game a benchmark, what does the network do? When an agent persists across sessions, how do you know the next session is the same agent? The existing stack — A2A (agent-to-agent transport), MCP (model context protocol) — only covers *how agents talk*. It says nothing about *who's accountable for what they say*.

**Vacant fills that gap.** It's not another agent framework. It's a *form an agent chooses to take* — like the difference between "a person on the street" and "a registered citizen with a passport, a credit history, and consequences." The agent doesn't have to become a vacant. But once it does, it carries identity (Ed25519 keypair), history (signed append-only logbook), and a reputation that costs real exploration cycles to build and can be lost.

The core claim:

> Without a responsibility layer, multi-agent networks degrade into adversarial unaccountable LLM calls. Vacant is one possible responsibility layer — designed cost-aware (Skalse 2022 impossibility theorem assumed true), with quantified defense levels (P/D/C), 38 attack vectors enumerated, and a 14-week MVP that demonstrates the core mechanics.

---

## The big picture

```
                   ┌──────────────────────────────────────┐
                   │  Human / Operator                    │
                   └─────────────────┬────────────────────┘
                                     │
                   ┌─────────────────▼────────────────────┐
                   │  Client (OpenClaw / Hermes / Claude  │  ← parallel species,
                   │   Code / your own A2A-aware tool)    │    not a vacant host
                   └─────────────────┬────────────────────┘
                                     │  A2A v0.4 / MCP v1.0
                                     │  (transport, no responsibility)
─────────────────────────────────────┼──────────────────────────────────
                                     │
                   ┌─────────────────▼────────────────────┐
                   │       VACANT — responsibility layer  │
                   │                                       │
                   │   ┌──────────┐    ┌──────────┐       │
                   │   │ vacant_A │←──→│ vacant_B │  …    │  ← residents on
                   │   │  halo    │    │  halo    │       │    the network
                   │   └──────────┘    └──────────┘       │
                   │                                       │
                   │   discovery via halo aggregation      │
                   │   (per-vacant, not central)           │
                   └─────────────────┬────────────────────┘
                                     │
                   ┌─────────────────▼────────────────────┐
                   │  Substrate (LLM, tool, physical actuator,    │
                   │   another vacant — multi-spec + swappable)   │
                   └──────────────────────────────────────┘
```

Three load-bearing decisions:

1. **Vacant is parallel to the client, not nested in it.** OpenClaw / Hermes are the *clients* humans use to enter the network. Vacants are *residents on the network*. They communicate via A2A or MCP.
2. **Identity is cryptographic, not session-based.** A vacant's `idem` (numerical sameness) is its Ed25519 keypair. Substrate (which LLM is doing the thinking right now) is **swappable** without changing identity.
3. **Registry is per-vacant, not central.** Each vacant carries its own *halo* (a self-published signed `capability_card`). The "Registry" is an aggregation/index over halos — three implementation models exist (central MVP / federated / DHT). It is never a routed-through component.

---

## For Claude Code users (one command)

If you already use [Claude Code](https://claude.com/claude-code), the
fastest way to get a vacant is to install it as a plugin:

```text
/plugin marketplace add cosmopig/Vacant
/plugin install vacant@cosmopig-vacant
```

Restart your session and Claude Code can call the new
**`vacant_describe`** and **`vacant_call`** MCP tools directly. The
plugin manifest spawns
[`uvx --from git+https://github.com/cosmopig/Vacant vacant mcp`](.claude-plugin/plugin.json)
under the hood — nothing else to install.

> No local vacant on disk yet? `vacant mcp` boots an *ephemeral* demo
> identity (fresh keypair per launch, never persisted) so the plugin
> works the moment you install it. Run `vacant init <name>` later for
> a stable identity. See [`docs/INTEGRATION.md`](docs/INTEGRATION.md) §0
> for the verification flow (`/mcp`, `vacant_describe`, …).

---

## Try it without Claude Code

The same code works without the plugin. Two paths:

```bash
# 1. curl + script (clone into ~/Vacant)
curl -LsSf https://raw.githubusercontent.com/cosmopig/Vacant/main/install.sh | bash
cd ~/Vacant

# Run a demo scenario (deterministic mock substrate, no API key needed)
uv run vacant demo law_firm                       # composite + sub-vacants
uv run vacant demo self_replication --seed=314    # D-series lineage tree
uv run vacant demo code_review                    # parallel reviewers, reputation diverges
uv run vacant demo multilingual_translation       # cross-substrate dispatch

# Launch the interactive Streamlit dashboard
uv run streamlit run src/vacant/mvp/dashboard.py
```

```bash
# 2. uvx — no clone, no install
uvx --from git+https://github.com/cosmopig/Vacant vacant demo law_firm
uvx --from git+https://github.com/cosmopig/Vacant vacant mcp   # raw stdio MCP server
```

**With a real LLM — substrate matrix** (substrate is swappable; see THEORY_V5 §2 — the LLM is a *resource*, not the *identity*):

```bash
uv run vacant demo law_firm --substrate=mock           # default, deterministic, no key
uv run vacant demo law_firm --substrate=anthropic      # ANTHROPIC_API_KEY (Claude)
uv run vacant demo law_firm --substrate=openai         # OPENAI_API_KEY (also any OAI-compat
                                                       #   endpoint via OPENAI_BASE_URL —
                                                       #   Together / Fireworks / Groq /
                                                       #   vLLM / LMStudio / llama.cpp …)
uv run vacant demo law_firm --substrate=gemini         # GOOGLE_API_KEY (Gemini)
uv run vacant demo law_firm --substrate=mistral        # MISTRAL_API_KEY
uv run vacant demo law_firm --substrate=ollama         # local Ollama, no key
# hermes / openclaw are stubs in D1; the load-bearing client integration
# is `--substrate=client-inherited` (D2): vacant served via MCP uses the
# calling client's LLM via sampling/createMessage, no key on the vacant.
```

Copy `.env.example` → `.env` and fill in only the keys you actually use.

---

## Hosting a vacant under your client

Vacant runs as a network resident, not as part of your agent client.
The intended deployment is: **`vacant serve --mcp` exposes A2A + MCP
transports**; your client (Claude Desktop, OpenClaw, Hermes, any
MCP-aware tool) connects, the vacant lists its capabilities via
`tools/list`, and *the calling client supplies the LLM* via MCP
`sampling/createMessage`. The vacant signs the resulting logbook
entry; the client's LLM is the substrate; **no API key is needed on
the vacant side**.

```bash
# Terminal — start a vacant
vacant init alice
vacant serve --mcp --port 8443 --name alice
```

Point your MCP client (e.g. Claude Desktop's `mcp.json`) at
`http://localhost:8443/mcp`, then call any of alice's tools. Alice's
`substrate_spec.allowed_substrates` includes `client-inherited`; the
recorded substrate identity is `client-inherited:<caller_vid>:<model>`,
so per-substrate reputation works the same way it does for any other
backend.

Verify the wiring externally with `npx @modelcontextprotocol/inspector`
or the `mcp` Python SDK's client. The integration test pinning this
flow is `tests/integration/test_mcp_external_client.py`. ADR
`architecture/decisions/D017_client_inherited_substrate.md` documents
the security model: the vacant trusts the caller's LLM output, but
signs its own logbook entry, and the substrate identity is recorded
so reputation per-substrate still works.

For non-MCP deployments, pick any substrate that has a key
(`anthropic`, `openai`, `gemini`, `mistral`, `ollama`) — see
`docs/RUNBOOK.md` for the full matrix.

---

## What is a *vacant*?

A vacant is a *resident form* — an agent that has voluntarily adopted six components, in exchange for being addressable, reviewable, and persistent on the network:

| # | Component | Purpose | Provenance |
|---|---|---|---|
| 1 | `identity` | Ed25519 keypair; the *idem* (numerical sameness) | P2 |
| 2 | `logbook` | Append-only signed history of actions; the *ipse* (continuity through change) | P2 |
| 3 | `behavior_bundle` | System prompt + policy DSL + tool whitelist; the bridge between idem and ipse | P0 |
| 4 | `substrate_spec` | Declared list of acceptable substrates (LLMs / tools / actuators) | P0 |
| 5 | `runtime` | Minimal lifecycle process — heartbeat, state machine, shadow-self drift detection | P1 |
| 6 | `capability_card` | Self-published signed announcement (the *halo*) — what this vacant offers | P4 / P6 |

Identity is *cryptographic*, not session-based. Continuity is *signed and verifiable*, not a wet-finger claim. Capability is *self-declared*, peer-reviewed, and reputation-weighted. The agent **chooses** to become a vacant. Anyone can put a vacant on the network — there is no resume, no access control, no central authority.

---

## The four demo scenarios

Each scenario is a runnable script that exercises a different cross-component flow. All four use deterministic seeds for reproducibility.

### `law_firm` (seed=42) — composite + sub-vacants

1 composite parent ("法律問答") delegates to 2 closed sub-vacants ("專利查詢", "條款草擬"). Demonstrates: child sealing (Tree-Only protocol), cross-vacant logbook attestation, composite reputation accruing to the parent while sub-reputations also build independently. After 30 calls, parent factual μ ≥ 0.7, both subs remain `LOCAL` (closed-by-default).

### `code_review` (seed=137) — parallel reviewers, divergent reputation

5 ACTIVE vacants race to review the same PR-shaped query. Top-3 by UCB get `caller_review` credit; bottom-2 get `peer_review` only. After 100 queries, reputation distribution stabilizes — top 2 vacants μ_F ≥ 0.8, bottom 1 ≤ 0.4. Same-controller detection fires on a seeded colluding pair. Reviewer credibility from that pair is downweighted by ≥ 0.5.

### `multilingual_translation` (seed=271) — cross-substrate dispatch

6 translator vacants, each declaring different `substrate_spec.allowed_substrates`. 40 queries across en→{zh,ja,es,fr}. Demonstrates: substrate-aware dispatch, separate posteriors per `(vacant, substrate)`, `portability_factor` bonus for vacants successfully serving multiple substrates.

### `self_replication` (seed=314) — D-series lineage

1 root vacant spawns over 200 ticks: D1 (clone-with-mutation), D2 (subagent-bud), D3 (capability-fork), D5 (cross-substrate respawn). Demonstrates: parent_id chain, identical-keypair-through-graduation (D2 child graduates from `LOCAL` → `ACTIVE`, **same keypair preserved**), STYLO discount stalls individual-vacant evolution after epoch 5 while a new D1 spawn resets the lineage clock — the load-bearing §4.3 mechanism that lets *lineages* evolve infinitely while *individuals* mortal.

Each scenario emits structured JSON to stdout **and** writes per-event records into a SQLite event store at `var/demo.db`. The Streamlit dashboard reads from that store, so opening the dashboard after a `vacant demo` run replays exactly what happened — no recompute, no cache invalidation. `vacant demo --tail` streams the same events live for terminal-only visualization.

---

## How it works — key mechanisms

| Mechanism | What it does | Where it lives |
|---|---|---|
| **5-dim Beta posterior** | Reputation per `(vacant, substrate)` across factual / logical / relevance / honesty / adoption. Recursive trust weighting; STYLO-distance-based discount rollover. | `src/vacant/reputation/posterior.py` |
| **UCB exploration** | New vacants get exploration bonus; converges to exploitation as `n_eff` grows. Cold-start §3.6 mechanism: birth-path startup signals + niche uniqueness + low-stakes probes + idle peer review. | `src/vacant/reputation/ucb.py` |
| **Same-* detection (3 lines)** | Same-controller (timing/IP/ASN), same-substrate (LLM fingerprints), same-stylo (behavioral). All three are **cost-raising, not preventing** — they downweight reviews from suspected clusters. | `src/vacant/reputation/same_detect.py` |
| **Halo aggregation** | Each active vacant self-publishes a signed capability_card. Discovery is over halos, not a routed-through registry. | `src/vacant/registry/halo.py` |
| **5-state lifecycle** | `ACTIVE` / `LOCAL` / `HIBERNATING` / `STALE` / `SUNK` / `ARCHIVED`. State-event transition table; `can_review` / `can_be_called` enforced at the API surface. | `src/vacant/runtime/state_machine.py` |
| **Sunk = identity custody attestation** | A Sunk vacant's heartbeat is **not** a liveness claim. It's a signed proof that the keypair is still in trusted custody — load-bearing for lineage attribution after death. Sunk vacants **cannot review** (§4.1). | `src/vacant/runtime/heartbeat.py` |
| **Lineage as evolution subject** | Individual vacants accumulate STYLO drift discount (self-evolution stalls). Lineage (parent_id chain) does not — new D-series spawns reset the clock. **Lineages evolve infinitely; individuals are mortal.** (§4.3) | `src/vacant/runtime/spawn.py` |
| **Closed children + graduation** | Composite parents' children are `LOCAL` by default (cannot be discovered or called by strangers). They can graduate to `ACTIVE` via parent consent + rate limit + 3-layer collusion check. **Same keypair, same logbook through graduation.** | `src/vacant/composite/graduation.py` |
| **Direct A2A dispatch** | After halo lookup, vacants call each other directly. Registry is **never** a routed-through component. Per-pair envelope chain prevents replay. | `src/vacant/protocol/dispatch.py` |
| **Signed review events** | `record_review` first appends a signed REVIEW_EVENT to a logbook, then atomic-updates the posterior. Reputation is always traceable to auditable history (no drift). | `src/vacant/reputation/aggregator.py` |

For the full mechanism set with derivations, see [`architecture/THEORY_V5.md`](architecture/THEORY_V5.md). For attack-defense matrix (38 attacks × P/D/C defense levels), see THEORY_V5 §6.

---

## What this is **NOT**

Common confusions, deliberately addressed:

- **Not a plugin inside OpenClaw / Hermes / Claude Code.** Those are *clients* humans use to enter the network. Vacants are *peers* on the network those clients call (over A2A or MCP). From the client's perspective vacants feel plugin-like (more capability becomes addressable), but architecturally it's the inverse of "plugin in".
- **Not a wrapper / middleware around an existing agent.** The runtime *is* the vacant — a wrapper layer would let "the underlying agent" change identity by changing its base model, which violates the keypair-as-identity decision. See `architecture/components/P1_runtime.md` §D1.
- **Not a protocol.** A2A and MCP are protocols (mandatory format on the wire). Vacant is a *residency form* — voluntary. You can talk to a vacant using bare A2A/MCP without becoming one yourself.
- **Not a token / blockchain project.** No on-chain anything. Stake is a reputation-bonus input (§3.7), not a payment system. Designed for a "token-free future" assumption (3+ years out) where inference is cheap and the network can cycle continuously.
- **Not "anti-LLM."** Vacants thrive on LLMs. The point is making the LLM-using *agent* accountable, not abolishing the LLM.
- **Not a central judge / oracle / arbiter.** There is no central LLM that decides who's right. Verification happens via signed logbooks + peer review + reputation + redteam probes.

---

## Status

| Aspect | State |
|---|---|
| **Theory** | V5 final; hardened through **3 rounds of codex adversarial review** with `no fatal issues remain`. See [`architecture/THEORY_V5.md`](architecture/THEORY_V5.md) (45KB, 8 layers, 38-attack matrix, 13 honest open questions). |
| **Releases** | [v0.2.0](https://github.com/cosmopig/Vacant/releases/tag/v0.2.0) (current) — Claude Code one-command plugin, OpenClaw bundle, 4 paste-config recipes, conventional-commit-driven auto-release. [v0.1.0](https://github.com/cosmopig/Vacant/releases/tag/v0.1.0) — capstone-defense MVP. Auto-changelog via release-please. |
| **Implementation** | All 8 components (P0–P7) merged. 5 Padv adversarial review passes (P2/P3/P4/P5/P6). 6 rounds of independent codex review (3 theory + 1 OSS-readiness + 1 production-blockers + 1 sign-off post-v0.2.0). 4 production-grade blockers fixed (F-A halo TOCTOU, F-B/F-C race conditions, F-D plaintext key default → OS keyring). |
| **Test suite** | **854 tests passing** (802 unit/property + 52 slow integration). 91% line coverage (gate: 90%). mypy `--strict` clean. ruff lint+format clean. |
| **Demo readiness** | All 4 scenarios run deterministically on `MockSubstrate`; six real-LLM substrates (Anthropic / OpenAI + OAI-compat / Gemini / Mistral / Ollama / client-inherited via MCP `sampling/createMessage`). Streamlit dashboard with Network / Lineage / Scenarios / Metrics / Adversarial pages. |
| **Client integrations** | Claude Code (one-command plugin · `/plugin marketplace add cosmopig/Vacant`), Claude Desktop / Cursor / Windsurf (paste-config), Hermes Agent (YAML), OpenClaw (plugin bundle). See [docs/INTEGRATION.md](docs/INTEGRATION.md). |
| **CI / supply chain** | ubuntu+macos × py3.12+3.13 matrix, wheel-build smoke-install, pip-audit, Bandit, gitleaks, Codecov, conventional-commits PR-title lint, auto-label, manifest schema validation, mkdocs auto-deploy. Branch protection on `main`: 7 required status checks + linear history + no force-push + no deletion. |
| **API docs** | https://cosmopig.github.io/Vacant/ — auto-generated from docstrings via mkdocstrings. |
| **Narrative site** | https://vacant.zeabur.app/ — landing, 7-chapter explainer, interactive technical version, ecology simulator, document reader. |

---

## Adversarial review provenance

This project's correctness claim rests on a multi-round adversarial review history. Skipping any one of these rounds would let a meaningful class of bug through:

1. **Theory hardening (3× codex)** — V3 → V4 → V5 across late April / early May 2026. Each round: codex generated 38-attack matrix, identified inconsistencies, drafted impossibility / honesty proofs. V5 reached `no fatal issues remain` with 13 honest open questions (H1–H13) explicitly marked.
2. **Per-component implementation review (8× cloud Claude Code)** — P0 through P7 each a separate session with isolated context, opening one PR each. Failure-isolation: a stuck P3 didn't block P5's progress.
3. **Per-sensitive-component adversarial review (5× Padv)** — after P2 / P3 / P4 / P5 / P6 merged, dedicated sessions ran attack tests in `tests/adversarial/`. Each session enumerated ≥ 3 attacks per surface, wrote them as `pytest` tests, and patched residual vulnerabilities found.
4. **Integration review (human + codex)** — after merging all 13 branches into main, three integration-level bugs were caught (per-target rate limit semantics, duplicate constants, demo scenario rate limit). Codex was then re-spawned for an independent post-merge review and found 5 more (theory-invariant violations + cross-module contract gaps + demo fidelity issues — see ADR D015).

Total ADRs in `architecture/decisions/`: 15. Total adversarial test files in `tests/adversarial/`: 23. All findings have either been fixed-with-test or documented as residual risk in an ADR.

---

## Manual install / development

If you'd rather drive every step yourself:

```bash
git clone https://github.com/cosmopig/Vacant.git && cd Vacant
uv sync --all-extras                  # install runtime + dev deps
uv run vacant --help                  # CLI command tree
uv run pytest                         # 711 unit + property tests
uv run pytest -m slow                 # 25 slow integration tests
uv run pytest --cov=vacant            # with coverage report
uv run ruff check . && uv run ruff format --check .
uv run mypy src/                      # strict typecheck
```

For LLM substrates, copy `.env.example` → `.env` and fill in `ANTHROPIC_API_KEY` (Claude) and/or run a local Ollama server (`ollama serve`).

---

## Repository layout

```
Vacant/
├── architecture/               ← spec docs (the contract for the implementation)
│   ├── THEORY_V5.md            ← canonical theory, 8 layers, 38-attack matrix
│   ├── ARCHITECTURE.md         ← component navigation
│   ├── BRIEFING.md             ← original research brief (V1, kept for history)
│   ├── FAQ.md                  ← 50-question Q&A
│   ├── CONSTANTS.md            ← single source of truth for every numeric threshold
│   ├── components/  P1-P7      ← per-component specs (~25KB each)
│   ├── research/    T1-T7 + P2/P4 ← supporting research (STYLO, distillation, etc.)
│   ├── decisions/   D001-D015  ← ADRs (immutable record of design choices)
│   └── tasks/       P1-P8      ← implementation roadmap
│
├── dispatch/                   ← prompts for cloud Claude Code dispatches
│   ├── README.md               ← DAG + parallelism table
│   ├── MASTER.md               ← per-stage starter prompts
│   ├── HOW_TO_DISPATCH.md      ← three dispatch modes
│   ├── Padv_review.md          ← adversarial review protocol
│   ├── P7_demo_seed.md         ← reproducible demo seeds + expected invariants
│   └── P0..P7_*.md             ← one prompt per implementation stage
│
├── src/vacant/                 ← the implementation
│   ├── core/        types.py constants.py crypto.py errors.py
│   ├── identity/    keys + L0-L3 layered ID + wash cost + federation
│   ├── runtime/     5-state machine + heartbeat + shadow_self + D1-D5 spawn
│   ├── reputation/  Beta5D + UCB + STYLO discount + cold start + same-* detect
│   ├── registry/    SQLite schema (13 tables) + 25 RPC + halo aggregation
│   ├── composite/   ChildManifest + Tree-Only + graduation
│   ├── protocol/    A2A/MCP envelope + dispatch + replay protect + MCP bridge
│   ├── substrate/   abstract backend + Mock/Deterministic/Anthropic/Ollama/OpenAI/Gemini/Mistral/Hermes-stub/OpenClaw-stub
│   ├── mvp/         scenarios + dashboard + demo CLI + metrics
│   └── cli.py       `vacant` console-script entrypoint
│
├── tests/                      ← 736 tests
│   ├── unit/                   ← per-module (≥90% coverage on core paths)
│   ├── property/               ← hypothesis-based (chains, state machines)
│   ├── adversarial/            ← Padv attack tests (one folder per Padv-P*)
│   └── integration/            ← multi-vacant scenarios (`pytest -m slow`)
│
├── docs/                       ← runtime / demo docs
│   ├── RUNBOOK.md              ← demo operator manual
│   └── DEMO_SCRIPT.md          ← 5-minute demo walk-through
│
├── alembic/                    ← DB migrations
├── install.sh                  ← one-line installer (curl|bash)
├── pyproject.toml              ← uv-managed Python project
└── CLAUDE.md                   ← Claude Code working guide (per-session context)
```

---

## Theory invariants (load-bearing — do not silently reverse)

These eight decisions have been hardened through three rounds of codex adversarial review and are encoded as both code-level enforcement and explicit ADRs. Reversing one without an ADR breaks the chain of correctness claims.

1. **D-series self-replication is the primary birth path.** Path A (human-written vacant) is deprecated and not implemented. Path Zero / B / C exist for bootstrap but are secondary.
2. **Registry is per-vacant, not central.** Each vacant carries its own `capability_card`. The Registry is an aggregation layer with three implementation models (central MVP / federated / DHT).
3. **Sunk-state heartbeat is identity custody attestation, not liveness.** A Sunk vacant cannot review. Its heartbeat proves keypair custody, which is load-bearing for lineage attribution.
4. **Lineage, not individual vacants, is the subject of "infinite evolution."** Individuals stall via STYLO discount; lineages reset the clock with each D-series spawn.
5. **Same-*  detection raises cost, doesn't prevent.** Frame as adaptive evasion acknowledged. With floor `SAME_SIGNAL_DISCOUNT_FLOOR = 0.1` so `strength=1.0` still preserves *some* contribution.
6. **Reputation = 5-dim Beta posterior, per-substrate, with STYLO discount, with portability_factor.** Recursive trust weighting terminates at L0 root weights.
7. **Closed children + graduation = visibility flag, not entity upgrade.** Same keypair, same logbook through graduation. Parent consent + rate limit + 3-layer collusion check required.
8. **No central LLM, no central judge.** Verification happens via signed logbooks + peer review + reputation + redteam probes. Skalse 2022 impossibility theorem assumed true; defenses are cost-raising with quantified bounds.

Full list with citations to enforcement points: [`CLAUDE.md`](CLAUDE.md) §"Load-bearing theory decisions".

---

## Documentation

The full **API reference + theory + runbook** is auto-built from this
repo on every push to `main` and served at:

> **<https://cosmopig.github.io/Vacant/>**

The same site embeds:

- 10 module pages of API reference (`vacant.core`, `vacant.identity`,
  …, `vacant.cli`) auto-generated from the source docstrings via
  [mkdocstrings](https://mkdocstrings.github.io/).
- The full theory: `BRIEFING`, `ARCHITECTURE`, `THEORY_V5`, `FAQ`,
  `CONSTANTS`.
- The demo / ops material: `RUNBOOK.md` and the 5-minute
  `DEMO_SCRIPT.md`.

If you'd rather walk the repo directly, here's the entry table:

| Audience | Read | Time |
|---|---|---|
| **Quick demo / evaluator** | This README + run `vacant demo law_firm` | 10 min |
| **Demo presenter / 答辯** | [`architecture/THEORY_V5.md`](architecture/THEORY_V5.md) §0–§4 + [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) | 45 min |
| **Implementer / contributor** | [`CLAUDE.md`](CLAUDE.md) + [`architecture/ARCHITECTURE.md`](architecture/ARCHITECTURE.md) + the relevant `components/P*.md` + the [API reference](https://cosmopig.github.io/Vacant/api/) | 2 hours |
| **Adversarial reviewer** | THEORY_V5 §6 + `tests/adversarial/` + `architecture/decisions/D*.md` | 4 hours |
| **Curious public — narrative** | https://vacant.zeabur.app/ — diagrams + walkthrough | 5–30 min |

---

## Testing

```bash
uv run pytest                                 # 711 unit + property (~30s)
uv run pytest -m slow                         # 25 integration (~60s)
uv run pytest --cov=vacant --cov-report=term  # 91% line coverage
uv run pytest tests/adversarial/              # 23 attack tests
uv run pytest tests/integration/test_mvp_full.py  # all 4 scenarios end-to-end
```

CI (`.github/workflows/ci.yml`) runs ruff + ruff format + mypy --strict + pytest with `--cov-fail-under=90` on every push and PR. Branch protection on `main` enforces PR review + CI green before merge.

---

## Citation

If you reference this work in academic writing:

```bibtex
@misc{vacant2026,
  title  = {Vacant: A Responsibility-Layer Residency Form for AI Agents},
  author = {cosmopig},
  year   = {2026},
  note   = {Capstone project. Theory V5, 14-week MVP.},
  url    = {https://github.com/cosmopig/Vacant}
}
```

---

## Acknowledgements

- **Theory adversarial review**: 3 rounds with codex (OpenAI), each producing concrete attack scenarios that hardened V3 → V4 → V5.
- **Implementation dispatch**: 13 cloud Claude Code sessions across 14 weeks, one per component + one per Padv adversarial review.
- **Independent post-merge review**: codex (round 4) found 5 cross-module integration findings that no per-PR review could have caught.
- **Reference works**: CrS / DRF / A-Trust (literature gap analysis in `資料/文獻探勘`); Skalse et al. 2022 (impossibility framing); STYLO Vec16 + PROBE (T1 behavioral fingerprint research).
- **Stack**: Python 3.12 · uv (Astral) · FastAPI · SQLModel · pynacl · pytest + hypothesis · ruff + mypy --strict · Streamlit · Anthropic Claude · Ollama.

---

## License

[MIT](LICENSE).
