# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Pre-1.0 means breaking changes can land in any minor bump.

## [0.4.0](https://github.com/cosmopig/Vacant/compare/v0.3.0...v0.4.0) (2026-05-09)


### Features

* **cli:** vacant install &lt;client&gt; unified installer (Pfix4 B) ([1b46fdc](https://github.com/cosmopig/Vacant/commit/1b46fdca040118eee5db4d3b4eebabd661900149))


### Bug Fixes

* **alembic:** make upgrade head SQLite-safe (Pfix3 B3) ([1bc106b](https://github.com/cosmopig/Vacant/commit/1bc106bdefb79cf82260245a7ebc4b04add6adab))
* **cli:** publish flags use None defaults so omitted → preserve (Pfix3 F2 follow-up) ([4e97515](https://github.com/cosmopig/Vacant/commit/4e97515d8689ff3d0692aeff07fd23198a6ab4ca))
* **dispatch+cli:** A2A response validation + per-pair envelope_state (Pfix3 B6) ([5c9c2d8](https://github.com/cosmopig/Vacant/commit/5c9c2d8cf678d759c89c9da0b624c31e5f2568b1))
* **halo:** parent_id invariant treats None as preserve, not as 'unset' (Pfix3 F2 follow-up) ([210d10d](https://github.com/cosmopig/Vacant/commit/210d10db3dddcdbdbcc3729f4db4b2ddef3a7114))
* **mcp:** vacant_call_with_sampling requires signed envelope + signed audit trail (Pfix3 B7) ([da8eca9](https://github.com/cosmopig/Vacant/commit/da8eca9b88d680fb468a83f7493e5a7ae610cb7c))
* **plugin:** plugin.json author must be object + marketplace version 0.3.0 ([8e2c485](https://github.com/cosmopig/Vacant/commit/8e2c485cc6717a43c9415f01f08dda12e340f8c8))
* **registry:** republish overwrites whole card row + invariants (Pfix3 B5) ([bfb0410](https://github.com/cosmopig/Vacant/commit/bfb04101ae35bf62e6604afb9510ff9192e4bd50))
* **reputation:** atomic record_review + fail-closed audit (Pfix3 B4) ([71b99b9](https://github.com/cosmopig/Vacant/commit/71b99b934d252fe06047f37de471adc6b479cd6b))
* **rpc:** HTTP /v1/halo schema also uses None defaults (Pfix3 F2 follow-up) ([f43dbee](https://github.com/cosmopig/Vacant/commit/f43dbee74aacd10154553505cf93a054ddc06ca5))


### Documentation

* **changelog:** close Pfix2 [Unreleased] section — all 4 groups landed ([d4bff6f](https://github.com/cosmopig/Vacant/commit/d4bff6fd00a7812ae547d217d4412f14963e43cd))
* open Pfix3 — codex round-3 review response plan ([cb16170](https://github.com/cosmopig/Vacant/commit/cb161701caaa598c2806624eeffdcfa3eb7c717e))
* **pfix3:** record F1–F4 + 4 follow-up fixes from self-review ([0a24ada](https://github.com/cosmopig/Vacant/commit/0a24ada09ef300b61e9ec78d1c0860d7e27ce91f))
* **pfix3:** record outcome — 7 batches landed, 867 tests pass ([88d1451](https://github.com/cosmopig/Vacant/commit/88d145112f5804ba7d72e1da436a96756c53a2a3))
* **plugin:** disclose 14-week MVP / thesis status in plugin descriptions ([fcbac60](https://github.com/cosmopig/Vacant/commit/fcbac60599a1e5a2cbb47c82bb8d6aff75d1f9c3))
* **readme:** correct MCP transport claim — stdio, not HTTP /mcp (Pfix3 B2) ([c4b2cd0](https://github.com/cosmopig/Vacant/commit/c4b2cd063e860ccb9fe2843b7ef3d0acb7fe2be8))
* **readme:** surface OpenClaw / Hermes / Claude Desktop install commands (Pfix4 A) ([51c3810](https://github.com/cosmopig/Vacant/commit/51c3810068029aecf2c6be1b0006d3ebf776633a))

## [0.3.0](https://github.com/cosmopig/Vacant/compare/v0.2.0...v0.3.0) (2026-05-07)


### Features

* add 30-second promo video (narration + bgm + sfx) to README ([#44](https://github.com/cosmopig/Vacant/issues/44)) ([c294958](https://github.com/cosmopig/Vacant/commit/c2949582f7ee99bc592dd0e9311b924612d07dca))
* rename pypi distribution to vacant-network + auto-publish workflow ([#43](https://github.com/cosmopig/Vacant/issues/43)) ([74f5e7c](https://github.com/cosmopig/Vacant/commit/74f5e7cfbe79ec121cb7dae002ff15b9f1104229))


### Documentation

* refresh README badges + Status table for v0.2.0 ([#41](https://github.com/cosmopig/Vacant/issues/41)) ([93c3207](https://github.com/cosmopig/Vacant/commit/93c3207df83fcdd1bf1ba1f1f75b3d739ef9d442))

## [0.2.0](https://github.com/cosmopig/Vacant/compare/v0.1.0...v0.2.0) (2026-05-06)


### Features

* **cli:** vacant mcp stdio + Claude Code plugin manifest ([85c10a0](https://github.com/cosmopig/Vacant/commit/85c10a0663f7fd39b3851e9ae2761211d3bea1a7))
* OpenClaw plugin bundle + paste-config recipes for 4 other clients ([#35](https://github.com/cosmopig/Vacant/issues/35)) ([4670680](https://github.com/cosmopig/Vacant/commit/4670680e81a1fabc4b8f4b4ef035fa9469874812))
* **plugin:** Claude Code marketplace + `vacant mcp` stdio subcommand ([#37](https://github.com/cosmopig/Vacant/issues/37)) ([5bf89c5](https://github.com/cosmopig/Vacant/commit/5bf89c5a228a4de332e69075ce727375460ea37a))


### Bug Fixes

* **ci:** use manifest-mode for release-please action ([94c5c8e](https://github.com/cosmopig/Vacant/commit/94c5c8ebad5ac9dd77c954ed90c098a07bba2c36))


### Documentation

* SEO + discoverability + community readiness ([#38](https://github.com/cosmopig/Vacant/issues/38)) ([10b0591](https://github.com/cosmopig/Vacant/commit/10b059110eea83b4f0df3c74b3ce182a72c5ed06))

## Pfix2 historical note (closed before 0.3.0)

The Pfix2 codex-round-2 follow-up work originally tracked four parallel
branches. All of them landed via individual PRs that release-please rolled
into `0.2.0` / `0.3.0`; the branches themselves have been pruned.

- Group α (CLI stubs, A2A envelope validation, halo HTTP publish, Aggregator
  wiring, dotenv auto-load) — landed pre-0.2.0.
- Group D1 (`SubstrateBackend` implementations for OpenAI / Gemini / Mistral
  / Hermes / OpenClaw + `.env` matrix) — landed pre-0.2.0.
- Group B (SQLite demo store, real metrics snapshot, adversarial seed-666
  scenario, self-replication completeness, multilingual portability
  hardening, frozen numeric fixtures) — landed pre-0.2.0.
- Group A8 (versioned `RootSet` + rotation history) — design recorded in
  [ADR D016](architecture/decisions/D016_federation_root_rotation_history.md);
  implementation lives in `src/vacant/identity/federation.py`.

## [0.1.0] — historical project-snapshot description

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
