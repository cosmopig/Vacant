# Pfix2 — Codex Round 2 + manual review findings

This is the consolidated fix dispatch after the second round of independent review (codex round 2 + manual reality check). 14 findings, grouped into three deliverables for sequential PRs.

## Read first

1. `/CLAUDE.md` — full
2. `/architecture/CONSTANTS.md`
3. `/architecture/THEORY_V5.md` §6 (defense framing) and §7 (registry ontology — confirm direct-call invariant)
4. `/architecture/decisions/D015_codex_review_2026_05_06.md` — codex round 1 findings (already addressed)
5. The current state of `main` (HEAD ≈ 2edc2e0+)

## Working rules

1. Open branch `fix/codex-round2-<group>` per group below.
2. Each group becomes ONE PR. After opening a PR, **stop and wait for "merged"** before starting the next group.
3. Don't merge yourself. Ping the user when each PR is ready.
4. Run `uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run pytest` to all-green before opening each PR.
5. Add a regression test for every fix.
6. If a finding requires a theory invariant change, open an ADR (`architecture/decisions/D016+`) before changing code.

---

## Group A — Live-network capability (Blockers F1, F2, F3, F4, F5, F6, F12, F14)

This group makes "嫁接到客戶端" (plug-into-client) actually work. Right now the project claims it does but several pieces only work in-process.

### A1 — Wire the 8 CLI stubs (`F4`)

`src/vacant/cli.py` has 8 commands stubbed to `_NOT_YET`. Wire each:

- **`init <name>`** (P2) — generate Ed25519 keypair, write `~/.vacant/<name>/key.json` + seed logbook (`logbook.jsonl`). Output the new vacant_id.
- **`status [--all]`** (P1) — list vacants under `~/.vacant/` with state, capability, last heartbeat. `--all` includes Hibernating/Stale/Sunk.
- **`heartbeat`** (P1) — manually emit a heartbeat for the current local vacant (env `VACANT_NAME` selects which). Append to logbook.
- **`call <vid> <capability>`** (P6) — outgoing A2A call to a remote vacant via dispatch. Reads target's capability_card from registry (or `--endpoint <url>` for direct-known target).
- **`publish`** (P4) — flip current local vacant from `LOCAL` → `ACTIVE`, push capability_card halo to registry (env `VACANT_REGISTRY_URL` or `--registry`).
- **`unpublish`** (P4) — reverse of publish.
- **`lineage <vid>`** (P4) — print parent_id chain (descendants/ancestors via `--direction`).
- **`attest <target_vid> <claim>`** (P2) — sign a peer attestation, post to registry.

Add a thin local-state helper module `src/vacant/cli/local_store.py` that owns `~/.vacant/` directory layout, name resolution, and logbook persistence. Tests in `tests/unit/test_cli_*.py`.

### A2 — Add `vacant serve` command

`src/vacant/protocol/serve.py` already has `build_a2a_app()` returning a FastAPI app. Wrap it in CLI:

```
vacant serve [--port 8443] [--mcp] [--name <local_vacant_name>]
```

- Starts uvicorn with the A2A app.
- `--mcp` flag also starts the MCP transport (see A3).
- Uses local store (A1) to load the keypair + behavior_bundle.
- Logs structured events.

Acceptance: `vacant serve --port 8443` followed by `vacant call <vid> <cap>` from another shell completes a real network roundtrip. Add `tests/integration/test_live_serve.py` (`@pytest.mark.slow`) that spawns `vacant serve` in a subprocess, sends a real `httpx.AsyncClient` POST, asserts the signed response envelope.

### A3 — Real MCP server transport (`F1`)

`src/vacant/protocol/mcp_adapter.py` admits "the full MCP wire protocol is not re-implemented here." Use the `mcp` Python SDK (or `fastmcp` if simpler) to actually expose the vacant as an MCP server:

- stdio transport (for Claude Desktop / CLI clients)
- SSE transport (for HTTP clients)
- `tools/list` returning the vacant's capabilities derived from `capability_card.capability_text`
- `tools/call` routing through the existing `behavior` callback in `serve.py`

Add `mcp` (or `fastmcp`) to `pyproject.toml`. Write `tests/integration/test_mcp_external_client.py` that uses the mcp SDK's client to call the running server and exchanges a real `tools/call`. **This is the test that the demo presentation rests on.**

### A4 — Live two-vacant network e2e (`F2`)

Replace or supplement `tests/integration/test_a2a_full.py`. The current test uses `httpx.AsyncClient(transport=ASGITransport(app=...))`, which short-circuits the network. Add a new test that:

1. Spawns vacant_A as a subprocess on port 8444
2. Spawns vacant_B as a subprocess on port 8445
3. Has B's behavior callback call A directly via dispatch
4. Asserts the request appears in A's logbook with valid signature, response in B's logbook
5. Tear down both subprocesses

`@pytest.mark.slow`. This is what the user shows during the demo presentation / 答辯 as "live network".

### A5 — A2A endpoint full envelope validation (`F3`)

In `src/vacant/protocol/serve.py:107`, before passing the body to `from_a2a_jsonrpc`:

- Check `Content-Type: application/json`
- Check `body["jsonrpc"] == "2.0"`
- Check `body["method"] == "message/send"` (or whatever the spec defines)
- Reject non-spec envelopes with HTTP 400 + structured error body

Add unit tests in `tests/unit/test_serve.py` for each rejection path.

### A6 — Registry HTTP halo publish (`F5`)

`src/vacant/registry/rpc.py:155` returns 501 for halo publish. Implement it:

- Deserialize `CapabilityCard` from request body
- Verify signature against the claimed `vacant_id`
- Call existing `halo.publish_halo(card)`
- Return the persisted record + 201 Created

Add `tests/unit/test_registry_rpc.py::test_halo_publish_*` covering: success, bad signature, malformed card, replay (same halo_version twice).

### A7 — Aggregation uses real Aggregator, not ZeroOracle (`F6`)

`src/vacant/registry/aggregation.py:66` defaults `/v1/query_capability` to `_ZeroOracle`, which orders by insertion order (zero reputation for everyone). This means the public registry HTTP API **always returns capability matches in arbitrary order**, not by UCB-ranked reputation.

Fix: thread a real `Aggregator` (which already implements `ReputationOracle`) into `build_app(reputation_oracle=...)`. Update all integration tests to wire it.

### A8 — Federation root rotation history (`F12`)

`src/vacant/identity/federation.py:155` `verify_federated` only checks against the *current* rootset. After a `rotate_root` call, all attestations issued under the old rootset become unverifiable.

Fix:

- `RootSet` becomes versioned: each rotation produces a new revision, old revisions kept in a chain
- Each `FederatedAttestation` records the rootset revision it was issued under
- `verify_federated(att, rootset_history)` looks up the issuance revision and verifies against that rootset
- Open ADR `D016_federation_root_rotation_history.md` documenting the data model

Add `tests/integration/test_federation_rotation_history.py` covering: pre-rotation issuance still verifies post-rotation, attempting to issue under stale revision is rejected.

### A9 — Anthropic `.env` auto-load (`F14`)

`src/vacant/substrate/anthropic.py:60` reads `os.environ["ANTHROPIC_API_KEY"]` directly. README's `.env` workflow only works if user `export`s manually.

Fix: at substrate construction, attempt `python-dotenv.load_dotenv()` if installed; otherwise fall back to `os.environ`. Add `python-dotenv` to deps. Surface a clear `SubstrateUnavailableError` with actionable message if the key is missing.

---

## Group B — Demo fidelity (Major F7, F8, F9, F10, F11, F13)

This group makes the dashboard and scenarios actually demonstrate the theses they claim to demonstrate.

### B1 — SQLite demo store (`F7`)

Add `src/vacant/mvp/demo_store.py` — a SQLite-backed event store at `var/demo.db` (path configurable). All scenarios write events as they run; dashboard reads from there.

Schema: `events(id, scenario, ts, kind, payload_json)`. Kinds: `call`, `review`, `spawn`, `state_change`, `halo_publish`, `metric`.

CLI integration: `vacant demo <scenario>` writes to demo store; dashboard reads it instead of recomputing on each session. Add `vacant demo --tail` to stream events into stdout for live visualization.

### B2 — Real metrics snapshot (`F8`)

`src/vacant/mvp/dashboard.py:141` builds an empty `MetricsSnapshot`. Compute the 8 P7 metrics from real scenario data (via demo store):

- `reputation_distribution`, `cold_start_uplift`, `same_controller_detection_rate`, `lineage_depth_distribution`, `graduation_rate`, `dispatch_p99_latency`, `signature_verify_throughput`, `registry_consistency_under_concurrency`

Each metric: numeric value + 30-tick time series. Plot with plotly inside Streamlit.

### B3 — Adversarial seed-666 scenario (`F9`)

Create `src/vacant/mvp/scenarios/adversarial.py` per `dispatch/P7_demo_seed.md` §"Adversarial seed (seed=666)":

- 10 active vacants, 4 share `controller_id` (the ring), 6 independent
- Ring exchanges high reviews; rest do normal reviews
- After 200 reviews: same-controller signal fires on the 4-ring with strength ≥ 0.7
- Ring members' reviews count for ≤ 0.5 weight when target is also in ring
- Non-ring vacants outrank the ring under UCB despite ring's inflated raw scores

Dashboard `Adversarial` page (`mvp/dashboard.py:178`) wires to this scenario, NOT `code_review`. Asserts against `tests/integration/fixtures/adversarial_seed666_expected.json`.

### B4 — Self-replication completeness (`F10`)

`src/vacant/mvp/scenarios/self_replication.py:217` is missing the load-bearing demonstrations from THEORY_V5 §4.2-§4.3:

- **STYLO discount stalls individual evolution**: simulate behavior drift over epochs in the parent; call `apply_drift_discount`; assert reputation contribution shrinks per drifted attestation.
- **SUNK custody heartbeat**: when a vacant transitions to SUNK, emit a heartbeat with `key_in_custody=true, liveness=false`; assert lineage attribution still resolves to it.
- **Lineage continuation despite individual stall**: spawn a fresh D1 child after the parent stalls; assert the child has a clean (non-discounted) posterior with optional inherited prior.

This scenario is the ONE that demonstrates THEORY_V5 §4.3's central claim — losing it means the project loses its strongest theoretical claim.

### B5 — Multilingual portability hardening (`F11`)

`src/vacant/mvp/scenarios/multilingual_translation.py:117` skips incompatible substrate claims. Change to:

1. Attempt at least one false substrate claim (vacant declares `gpt-4o` but actually only handles Claude); call fails; record reputation penalty (-0.05 on F).
2. After the run, call `compute_portability(vid, substrates_served, success_rate_per_substrate)` for each vacant; assert ≥ 1 vacant got a measurable portability bonus.
3. Assert post-run portability ranking matches expected from seed.

### B6 — Frozen numeric fixtures (`F13`)

`dispatch/P7_demo_seed.md` §"Updating fixtures" requires fixture files with full numeric snapshots + tolerance bounds, not just structural metrics. Update each:

- `law_firm_seed42_expected.json` — full reputation Beta5D values per vacant per substrate, + tolerance ±0.02
- `code_review_seed137_expected.json` — final ranking + reputation values + same-controller signal strength on the seeded pair
- `multilingual_translation_seed271_expected.json` — per-(vacant, substrate) posteriors + portability scores
- `self_replication_seed314_expected.json` — lineage tree shape + per-vacant final state + STYLO discounts applied

Tests in `tests/integration/test_mvp_full.py` compare to these with `pytest.approx(value, abs=tolerance)`.

---

## Group D — Substrate diversity + client-inherited LLM (extension request)

The user pointed out (correctly) that the README implies Anthropic is the only real-LLM option. The core claim is that **substrate is swappable** — the LLM is a *resource*, not the *identity*. Right now the project ships only `AnthropicSubstrate` and `OllamaSubstrate` (plus mock/deterministic). Two work items here:

### D1 — Multi-provider substrates

Add concrete `SubstrateBackend` implementations for the major providers. Each is small (~50-100 LOC) since the core protocol abstraction is already correct:

- **`OpenAISubstrate`** (`src/vacant/substrate/openai.py`) — uses `openai` SDK. Default model `gpt-4o`. Supports custom base_url so any OpenAI-compatible endpoint (Together, Fireworks, Groq, vLLM, LMStudio, llama.cpp server, etc.) works via the same class. Env: `OPENAI_API_KEY`, optional `OPENAI_BASE_URL`.
- **`GeminiSubstrate`** (`src/vacant/substrate/gemini.py`) — uses `google-genai` SDK. Default model `gemini-2.0-flash`. Env: `GOOGLE_API_KEY`.
- **`MistralSubstrate`** (`src/vacant/substrate/mistral.py`) — uses `mistralai` SDK. Default `mistral-large-latest`. Env: `MISTRAL_API_KEY`.
- **`HermesSubstrate`** (`src/vacant/substrate/hermes.py`) — uses Nous Research's Hermes Agent if accessible (otherwise stub with TODO).
- **`OpenClawSubstrate`** (`src/vacant/substrate/openclaw.py`) — uses OpenClaw's plugin API if it's exposed (otherwise stub with TODO; the more important integration is D2).

Each substrate registered in `src/vacant/substrate/__init__.py` and exposed via the demo CLI:

```bash
vacant demo law_firm --substrate=openai
vacant demo law_firm --substrate=gemini
vacant demo law_firm --substrate=ollama --model=llama3.2
```

Update `.env.example` with placeholders for all keys (commented out) and a note that only the keys you set need to be valid.

### D2 — `ClientInheritedSubstrate` — the load-bearing one

This is the feature the user named directly: **a vacant can use the calling client's LLM, no API key of its own**. Architecturally:

- When a client (OpenClaw / Hermes / Claude Code / Claude Desktop / any MCP-aware tool) calls a vacant via MCP, the client passes a *substrate handle* in the call envelope.
- The substrate handle is a callback: `async (prompt, opts) -> response`. The client owns the LLM session; the vacant *borrows* it for the duration of the call.
- The vacant's `substrate_spec.allowed_substrates` includes `client-inherited` — declaring "I will use whatever LLM the caller has".
- This is **the killer feature** for the "嫁接到客戶端" claim: deploying a vacant requires NO API key, NO local model — just `vacant serve` and the calling client supplies the brain.

Implementation:

1. `src/vacant/substrate/client_inherited.py` — `ClientInheritedSubstrate(SubstrateBackend)`:
   - constructor takes the caller's substrate callback (passed by serve.py from the incoming envelope)
   - `respond()` delegates to that callback
   - Records "borrowed_from" in the response metadata for logbook attestation (so the substrate identity is auditable)
2. `src/vacant/protocol/envelope.py` — extend `VacantEnvelope` with optional `caller_substrate_handle: SubstrateHandleProto` (a small dataclass: `substrate_kind: str`, `model_hint: str`, `transport_callback_id: str`).
3. `src/vacant/protocol/serve.py` — when an incoming call carries a substrate handle, instantiate `ClientInheritedSubstrate(handle)` and inject into the behavior_bundle resolution.
4. `src/vacant/protocol/mcp_adapter.py` — when the vacant is being called via MCP and the calling MCP client has its own LLM session (which Claude Desktop, Claude Code, OpenAI MCP clients all do), expose a way to use that. MCP's `sampling/createMessage` is the actual mechanism — the server (vacant) asks the client to do an LLM call on its behalf. Use it.
5. ADR `D017_client_inherited_substrate.md` — documents the security model: the vacant trusts the caller for LLM output, but signs its own logbook entry; the substrate identity is recorded as `client-inherited:<caller_vacant_id>:<model_hint>` so reputation per-substrate still works.

Tests (must include):

- `tests/unit/test_client_inherited.py` — substrate callback round-trip, logbook records the borrowed_from
- `tests/integration/test_mcp_sampling.py` (`@pytest.mark.slow`) — real MCP client (e.g. via `mcp` SDK) calls the vacant, vacant uses MCP `sampling/createMessage` back to the client, response signed and returned. **This test demonstrates "嫁接到客戶端" literally.**

### D3 — README + DEMO_SCRIPT updates

Update both `README.md` and `README.zh-TW.md`:

- Replace the "用真的 LLM（Anthropic Claude — 需要 `ANTHROPIC_API_KEY`）" section with a substrate matrix:

  ```bash
  vacant demo law_firm --substrate=mock           # default; deterministic; no API key
  vacant demo law_firm --substrate=anthropic      # ANTHROPIC_API_KEY
  vacant demo law_firm --substrate=openai         # OPENAI_API_KEY (also any OAI-compat endpoint)
  vacant demo law_firm --substrate=gemini         # GOOGLE_API_KEY
  vacant demo law_firm --substrate=mistral        # MISTRAL_API_KEY
  vacant demo law_firm --substrate=ollama         # local Ollama, no key
  vacant demo law_firm --substrate=client-inherited  # for use under MCP; client supplies the LLM
  ```

- Add a "Hosting a vacant under your client" section showing how to run `vacant serve --mcp` and then point Claude Desktop / OpenClaw / Hermes at it. The vacant uses the client's LLM via MCP `sampling/createMessage`. **This is the demo that closes the "嫁接到客戶端" core claim.**

- Update `docs/DEMO_SCRIPT.md` minute-by-minute to include this flow.

---

## Group C — Demo narrative cleanup (cross-cutting)

After A and B merge, these are smaller cleanups that make the demo presentation / 答辯 walkthrough tight.

### C1 — Single citable enforcement points

For each load-bearing decision in CLAUDE.md "Load-bearing theory decisions", make sure there's a SINGLE file:line that enforces it. Document in a new file `architecture/ENFORCEMENT_POINTS.md`:

- "Sunk vacant cannot review" → `src/vacant/runtime/state_machine.py:104` (`_REVIEW_OK` excludes SUNK + ARCHIVED) AND `src/vacant/reputation/aggregator.py:203` (consumed via `can_review`)
- "Per-vacant Registry, not central" → `src/vacant/protocol/dispatch.py:128` (direct call after halo lookup)
- "Path A is deprecated" → `src/vacant/runtime/spawn.py:12` (only D1-D5 paths exposed)
- ... etc for all 8

### C2 — Update RUNBOOK and README

- `docs/RUNBOOK.md` — update all command examples to use `vacant <cmd>` (CLI) instead of `python -m vacant.mvp.demo` where the CLI now wires it.
- `README.md` and `README.zh-TW.md` — update the dashboard ↔ demo store mention to reflect the new SQLite-backed flow.
- `docs/DEMO_SCRIPT.md` — the 5-minute demo presentation walk should reference: live network demo (A4), MCP external client demo (A3), adversarial scenario (B3), self-replication completeness (B4). One claim per minute.

---

## Suggested PR sequence

1. **PR-A: Live-network capability** (Group A, ~2 weeks of work, ~3000-4000 LOC)
2. **PR-D: Substrate diversity + client-inherited** (Group D, ~1 week, ~1500 LOC). D2 (`client-inherited` via MCP `sampling/createMessage`) is what closes the "嫁接到客戶端" core claim.
3. **PR-B: Demo fidelity** (Group B, ~1.5 weeks, ~2000 LOC)
4. **PR-C: Demo narrative** (Group C, ~3 days, ~500 LOC)

If time-constrained, prioritize A1 + A2 + A3 + A4 + D2 (live CLI + serve + real MCP + live e2e + client-inherited substrate) — these together are the literal "嫁接到客戶端" deliverables the core claims. D1 (more provider substrates) and Group B/C can degrade gracefully.

## Acceptance for the whole batch

- All 14 codex findings + the substrate-diversity gap addressed (citation per PR)
- 736 → 850+ tests; coverage stays ≥ 90%
- `vacant serve` + `vacant call` from two shells completes a real network roundtrip
- An external MCP client (verify with `npx @modelcontextprotocol/inspector`) connects and lists tools
- `client-inherited` substrate works: vacant under Claude Desktop uses Claude's LLM via `sampling/createMessage`, no `ANTHROPIC_API_KEY` set on the vacant side
- 5+ provider substrates available (anthropic / openai / gemini / mistral / ollama + client-inherited)
- Dashboard's Adversarial page shows the seed-666 ring detected from evidence (not hardcoded signal)
- All P7 invariants in `dispatch/P7_demo_seed.md` are asserted in CI
