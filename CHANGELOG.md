# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Pre-1.0 means breaking changes can land in any minor bump.

## [0.2.0](https://github.com/cosmopig/Vacant/compare/v0.1.0...v0.2.0) (2026-05-06)


### Features

* **cli:** vacant mcp stdio + Claude Code plugin manifest ([85c10a0](https://github.com/cosmopig/Vacant/commit/85c10a0663f7fd39b3851e9ae2761211d3bea1a7))
* OpenClaw plugin bundle + paste-config recipes for 4 other clients ([#35](https://github.com/cosmopig/Vacant/issues/35)) ([4670680](https://github.com/cosmopig/Vacant/commit/4670680e81a1fabc4b8f4b4ef035fa9469874812))
* **plugin:** Claude Code marketplace + `vacant mcp` stdio subcommand ([#37](https://github.com/cosmopig/Vacant/issues/37)) ([5bf89c5](https://github.com/cosmopig/Vacant/commit/5bf89c5a228a4de332e69075ce727375460ea37a))


### Bug Fixes

* **ci:** use manifest-mode for release-please action ([94c5c8e](https://github.com/cosmopig/Vacant/commit/94c5c8ebad5ac9dd77c954ed90c098a07bba2c36))


### Documentation

* SEO + discoverability + community readiness ([#38](https://github.com/cosmopig/Vacant/issues/38)) ([10b0591](https://github.com/cosmopig/Vacant/commit/10b059110eea83b4f0df3c74b3ce182a72c5ed06))

## [Unreleased]

In flight (parallel branches at the time of this entry):

- `claude/fix-codex-round-2-3StxD` — Pfix2 Group α: wire 8 CLI stubs, A2A envelope validation, halo HTTP publish, real Aggregator wiring, dotenv auto-load.
- `feat/group-d1-multi-substrates` — additional `SubstrateBackend` implementations (OpenAI / Gemini / Mistral / Hermes / OpenClaw), `.env` matrix.
- `feat/group-b-demo-fidelity` — SQLite demo store, real metrics snapshot, adversarial seed-666 scenario, self-replication completeness, multilingual portability hardening, frozen numeric fixtures.
- `feat/a8-federation-rotation` — versioned `RootSet` with rotation history, ADR D016.

## [0.1.0] — 2026-05-XX (post-defense target)

Target release for capstone defense. Items below are preserved as the project's first reproducible snapshot.

### Added

- Theory V5 — codex-hardened theory document, `no fatal issues remain`. 8 layers, 38-attack matrix, 13 honestly-disclosed open questions (H1–H13).
- Eight implementation components (P0–P7):
  - `core/`: VacantId, Logbook, ResidentForm, CapabilityCard, crypto primitives.
  - `runtime/`: 5-state machine, heartbeat, shadow-self drift, D1–D5 self-replication.
  - `identity/`: Ed25519 keys, L0–L3 identity layers, wash cost, federation roots.
  - `registry/`: 13 SQLite tables, 25 FastAPI RPCs, 6 anti-tamper layers, halo aggregation.
  - `reputation/`: 5-dim Beta posterior, UCB exploration, STYLO discount, cold start, same-* detection (controller / substrate / stylo).
  - `composite/`: ChildManifest, Tree-Only protocol, graduation flow.
  - `protocol/`: A2A envelope, capability_card serialization, dispatch, replay protect, MCP bridge.
  - `mvp/`: 4 demo scenarios, 8 metrics, Streamlit dashboard, demo CLI.
- `vacant` console-script with subcommands: `init`, `status`, `heartbeat`, `call`, `publish`, `unpublish`, `lineage`, `attest`, `demo`, `serve`.
- One-line installer: `curl -LsSf https://raw.githubusercontent.com/cosmopig/Vacant/main/install.sh | bash`.
- `uvx --from git+...` no-install runner.
- Light/dark-adaptive SVG hero + social preview.
- Bilingual README (English / 繁體中文).
- Architecture docs + 15+ ADRs in `architecture/decisions/`.
- 800+ tests across unit / property / adversarial / integration. Coverage gate ≥ 90%. mypy `--strict`. ruff lint + format.

### Hardened (adversarial review provenance)

- Theory V3 → V4 → V5: 3 rounds of codex adversarial review.
- Padv-P2 / P3 / P4 / P5 / P6: per-component attack-test passes (≥ 3 attacks per surface).
- Codex round 1 (post-merge): 5 cross-module integration findings → ADR D015.
- Codex round 2 (post-Pfix1): 14 findings → addressed in Pfix2 Groups A / B / D / C.

### Known limitations (H1–H13 + ADRs)

See `architecture/THEORY_V5.md` §6.5 for the full list of honestly-disclosed open questions and `architecture/decisions/` for residual risk acknowledgments.

---

## Tag prefix legend

- `[Theory]` — changes to spec docs in `architecture/`
- `[Runtime]`, `[Identity]`, etc. — per-component changes
- `[CLI]` — `vacant` console-script
- `[Demo]` — `mvp/`, scenarios, dashboard
- `[Docs]` — README, RUNBOOK, this file
- `[Infra]` — CI, packaging, install, tooling
- `[Security]` — explicitly security-relevant fixes (also tracked in SECURITY.md)
