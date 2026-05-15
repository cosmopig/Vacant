# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Pre-1.0 means breaking changes can land in any minor bump.

## [0.6.0](https://github.com/cosmopig/Vacant/compare/v0.5.0...v0.6.0) (2026-05-15)


### Features

* 3-PR operator UX — `vacant grow` (local) + `vacant peer` (network) + `serve --public --tls` ([d0881c8](https://github.com/cosmopig/Vacant/commit/d0881c85f5056893eba40774d423f527f823214a))
* close all remaining technical.html gaps (A1-A6, B7-B8, C9-C10) ([a825a45](https://github.com/cosmopig/Vacant/commit/a825a45af73fd9a2bb06248edf9ed8c815e4994f))
* close technical.html follow-ups — CLI surface, adoption indexer, federated backend, dashboard page ([bfcc0c0](https://github.com/cosmopig/Vacant/commit/bfcc0c032873268824fde5b10e103aedeba5f9fb))
* **examples/agent:** model-agnostic Vacant route for non-tool-capable LLMs ([1230e66](https://github.com/cosmopig/Vacant/commit/1230e667b5dfb75bf162d214ce24d07aa7328b7b))
* **grow:** LLM-driven 5D scorer + --substrate flag on serve/grow (Pfix9 Phase 2) ([03a6e12](https://github.com/cosmopig/Vacant/commit/03a6e12f5bc3e42107ae67cd4e5257c173cfdd4c))
* **grow:** self-growth loop — ingest reviews + drift + auto-spawn (Pfix9 Phase 3) ([78c9e82](https://github.com/cosmopig/Vacant/commit/78c9e82b9006cb5354910689c5fff2bd309da68a))
* **mcp:** auto-spawn competitor on 3 consecutive sub-0.3 reviews (Pfix8 P8.6) ([41e33fe](https://github.com/cosmopig/Vacant/commit/41e33fedc1654bf47f2c76fc0207f90e92822111))
* **mcp:** vacant_caller_review + 5D reputation in list_children (Pfix8 P8.2/P8.4) ([fc33cce](https://github.com/cosmopig/Vacant/commit/fc33cce937a281ec571801a39d470decf1ad0ab2))
* **mcp:** vacant_delegate_a2a — vacant-to-vacant over real A2A HTTP (Pfix8 P8.1) ([1fe46c1](https://github.com/cosmopig/Vacant/commit/1fe46c143e90c9eae53a6967e88d21ccbc4350a9))
* **mcp:** vacant_list_children + vacant_delegate (Pfix7) ([f798a77](https://github.com/cosmopig/Vacant/commit/f798a7760c411a4e818469d600613b5345294cab))
* **mcp:** vacant_spawn — client-driven D1 lineage growth (Pfix6) ([80965b8](https://github.com/cosmopig/Vacant/commit/80965b8c07e5a717ec31c12bf0c8c85a86dd82ea))
* **p1+p3:** composite 3-axis ontology + blinded peer review ([d0214c4](https://github.com/cosmopig/Vacant/commit/d0214c4dc5ed11332aeac08c399c50f629e674f3))
* **p2:** close Layer 9 metrics gap — add 7 missing health indicators ([6f97ec8](https://github.com/cosmopig/Vacant/commit/6f97ec8854f5cde95572af011ebae07de276ae0b))
* **p2p:** /reviews/ingest endpoint — make peer-review actually cross-machine ([0ee659a](https://github.com/cosmopig/Vacant/commit/0ee659ac960f7b7d35b8a3471b1b26401f333c08))
* **p2p:** self-recovering replay chain — eager advance + reset endpoint ([8b1c5cc](https://github.com/cosmopig/Vacant/commit/8b1c5cc2df9f9e968595281c66ba0e127ae630f0))
* **registry:** decentralised trust — Git anchor + OpenTimestamps + N-of-M witness cosignatures ([b27b1f8](https://github.com/cosmopig/Vacant/commit/b27b1f846889983938db328c825aa4d683e7530a))
* **runtime:** peer_review_tick — idle sibling probe + 5D scoring (Pfix8 P8.5) ([c8df7ed](https://github.com/cosmopig/Vacant/commit/c8df7ed0b09c834d831e33d52111933a82c8df3b))
* **spec-align:** close 4 codex-review-2 findings + audit-fix attack matrix ([b1c7710](https://github.com/cosmopig/Vacant/commit/b1c77109722260a412c5daf6518ffee5a9c36193))
* universal install + vacant route for any LLM (Pfix6+) ([3fe66f6](https://github.com/cosmopig/Vacant/commit/3fe66f661e38341d2957207db7d37bf3f7ff41ed))


### Bug Fixes

* **grow:** per-pair outbound chain so multi-tick peer review actually works (Pfix9 Bug A) ([0f68d0d](https://github.com/cosmopig/Vacant/commit/0f68d0dd420eb8c352479295c8b33d0f3544498e))
* **grow:** spec-align peer-review scorer to F/L/R only + add --review-all-per-tick ([713c8fb](https://github.com/cosmopig/Vacant/commit/713c8fb8f7867f8b03fc0d7458d3aa0c76d69f47))
* **install:** openclaw `--link` install is incompatible with `--force` ([92eae93](https://github.com/cosmopig/Vacant/commit/92eae93df4e1a6bd2ec28e7a70fbd351b6fb1e21))
* **mcp:** single-Logbook invariant for sampling + spawn coexistence ([3276399](https://github.com/cosmopig/Vacant/commit/3276399cf64245bb3e4ebbfeb4bf99d9b37735e9))
* **openclaw:** align bundle VACANT_NAME default with Pfix5 alice contract ([4d4204d](https://github.com/cosmopig/Vacant/commit/4d4204d526c3db7669a15e0f81c75811839930aa))
* **spec-align:** close codex-review-3 critical findings ([b4e0890](https://github.com/cosmopig/Vacant/commit/b4e0890d2847897a47ebd1a6fa3f60993c6f9a73))
* **spec-align:** close codex-review-3 round-2 — Lock, bounded cache, Sybil docs ([771b8c2](https://github.com/cosmopig/Vacant/commit/771b8c2df7c19b2ae679a9b509b3f89d94730370))

## [0.5.0](https://github.com/cosmopig/Vacant/compare/v0.4.0...v0.5.0) (2026-05-11)


### ⚠ BREAKING CHANGES

* vacant install bootstraps identity; vacant mcp strict on missing (Pfix5)

### Features

* vacant install bootstraps identity; vacant mcp strict on missing (Pfix5) ([5b7dd27](https://github.com/cosmopig/Vacant/commit/5b7dd2796391a785022be8bdebbba2292ad84255))


### Bug Fixes

* **cli:** cover install.py branches + drop dead _main + sync __version__ to 0.4.0 ([7b3cd75](https://github.com/cosmopig/Vacant/commit/7b3cd750a6858be11483be3c549668416f1a6514))

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
