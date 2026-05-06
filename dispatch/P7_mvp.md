# P7 — MVP demo

## Goal

Wire all components together into a runnable demo: 4 scenarios + 8 metrics + a Streamlit dashboard. **If you cannot demo it visually, it is not done.**

This is the capstone deliverable. Take 4 weeks (W11–14). Quality matters more than feature breadth — better to have 3 of 4 scenarios solid than 4 of 4 flaky.

## Read first (in order)

1. `/CLAUDE.md`
2. `architecture/components/P7_mvp.md` — 4 scenarios, 8 metrics, 14-week schedule
3. All component specs P1–P6 (so you know each surface area)
4. Skim merged code under `src/vacant/` to confirm the API surface matches what the spec promised

## Repo state at start

- All of P0, P1, P2, P3, P4, P5, P6 merged.
- `src/vacant/mvp/` has only `__init__.py`.
- `src/vacant/substrate/` has at minimum `MockSubstrate`; flesh out `AnthropicSubstrate` and `OllamaSubstrate` here.

## Scope

### 1. Substrate backends — `src/vacant/substrate/`

- `base.py` — `SubstrateBackend(Protocol)` with `async def respond(prompt, behavior_bundle, context) -> Response`
- `mock.py` — `MockSubstrate` (deterministic; for tests)
- `deterministic.py` — `DeterministicSubstrate` (canned responses keyed by prompt hash; for reproducible demos)
- `anthropic.py` — `AnthropicSubstrate` using the `anthropic` SDK. Default model: `claude-sonnet-4-6`. API key via env. Rate-limit aware.
- `ollama.py` — `OllamaSubstrate` against a local Ollama server. Used for "token-free future" simulation.

### 2. Scenarios — `src/vacant/mvp/scenarios/`

Each scenario is a runnable script that takes a `--substrate` flag (`mock` / `deterministic` / `anthropic` / `ollama`). All four scenarios from `P7_mvp.md`:

- `law_firm.py` — composite vacant (legal Q&A) calls patent-search + clause-drafting sub-vacants
- `code_review.py` — multiple vacants race to review the same PR; reputation diverges
- `multilingual_translation.py` — cross-substrate dispatch (different LLMs picked per language)
- `self_replication.py` — D1/D2/D3 spawn from a parent; lineage tree grows over time; one child graduates

Each scenario prints structured logs and writes events to a `var/demo.db` SQLite registry. The dashboard reads from there.

### 3. Metrics — `src/vacant/mvp/metrics.py`

The 8 metrics from `P7_mvp.md`. At minimum:

- `reputation_distribution` — Beta5D summary across all active vacants
- `cold_start_uplift` — new-vacant calls / total calls over time
- `same_controller_detection_rate` — true positives / total flagged on a synthetic adversarial set
- `lineage_depth_distribution` — histogram of parent-chain depth
- `graduation_rate` — graduations per composite per time window
- `dispatch_p99_latency` — wall-clock p99 of `call_capability` end-to-end
- `signature_verify_throughput` — verifications/sec under load
- `registry_consistency_under_concurrency` — % of writes preserving sequence-no monotonicity under N concurrent writers

Each metric exposes both: (a) computed-on-demand function, (b) a writer that emits to a `metrics` table for time-series plotting.

### 4. Dashboard — `src/vacant/mvp/dashboard.py`

Streamlit app (run via `uv run streamlit run src/vacant/mvp/dashboard.py`). Pages:

- **Network** — list of vacants with state, capability, mean reputation per dimension; live-updated; halo visualization (the green-dashed-rect motif from the docs site)
- **Lineage** — tree visualization of parent_id chains
- **Scenarios** — pick a scenario, run it, watch step-by-step events stream in (call → halo lookup → dispatch → response → logbook write → reputation update)
- **Metrics** — time-series plots of the 8 metrics
- **Adversarial** — page that runs the same-controller / same-substrate / same-stylo synthetic adversarial sets and shows detection rates with an explanation of cost-raising-not-preventing framing

繁體中文 UI text. Code in English.

### 5. Demo CLI — `src/vacant/mvp/demo.py`

`python -m vacant.mvp.demo --scenario=<name> --substrate=<backend> [--seed=N]`

Reproducible (seedable) end-to-end runs. Used for both manual demos and the integration test.

### 6. Integration test for the whole system — `tests/integration/test_mvp_full.py`

`@pytest.mark.slow`. Runs each scenario with `MockSubstrate` (fully deterministic), asserts:

- Vacants are spawned with correct lineage
- Halos are published, queryable, and respect visibility
- Dispatch picks the highest-UCB vacant
- Reputation moves in expected direction
- Same-controller detection fires on the seeded colluding pair
- Graduation succeeds when conditions met, fails when missing
- All logbook chains verify after the run

### 7. Documentation

- `docs/RUNBOOK.md` — how to run the demo locally, expected output, common failures
- Update `README.md` Quick start with concrete commands for the demo
- Update top-level `CLAUDE.md` if any new common command emerges

## Acceptance — the bar for demo presentation

- All 4 scenarios run end-to-end on `MockSubstrate` and at least one cloud substrate (`AnthropicSubstrate` or `OllamaSubstrate`).
- All 8 metrics computed and displayed.
- The dashboard runs and is responsive on a laptop.
- The full integration test passes in CI under 5 minutes.
- A 5-minute live demo script is in `docs/DEMO_SCRIPT.md` — exactly what to click in the dashboard, in what order, to tell the project story.

## Output

PR titled **"P7: MVP demo — scenarios, metrics, dashboard"**.

PR description must include screenshots of each dashboard page, a demo script, and the metric values from a deterministic run.

## Out of scope

- Production deployment / hosted demo — local run only is fine for the capstone demo
- Mobile UI for the dashboard — desktop only is fine
- Real-money substrate billing — use Anthropic API in test mode only

## What to do if you run short on time

Priority order if W14 deadline pressure forces cuts:

1. **Cut scenarios first** (4 → 3 → 2). Keep `law_firm` (composite) and `self_replication` (lineage) as the two non-negotiable ones — they tell the core project story.
2. **Cut substrates next** — `MockSubstrate` + `AnthropicSubstrate` are sufficient.
3. **Do not cut metrics or adversarial page** — those are the demo presentation.
4. **Do not cut tests** — they are the proof of correctness for the defense.
