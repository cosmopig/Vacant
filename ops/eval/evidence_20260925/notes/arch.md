# arch — zero-config accountability: delta over current code (read 2026-09-25, repo HEAD cf71d6a9)

## 0. What the code does today (verified by reading)

- `adapters/hook.py::handle` — every native hook event -> normalize -> policy -> render. **Stop check only when a contract exists**
  (`elif ev.kind == "stop" and contract is not None ...`). No contract => stop returns allow; nothing is checked.
- `trace/capture.py::workspace_for` — trace recorded only if contract exists, or `VACANT_TRACE=1` (then cwd). Home, `/`, VACANT_HOME excluded.
- `trace/recorder.py` — per-project signed chain; step events carry tool, input_blob, output_blob, writes (Vacant's own diff), error,
  concurrency flags; `unrecorded_change` gaps; prompts with `source` (user / vacant_feedback / subagent_result / parent_agent / machine / scheduled_by_agent).
  Reads are declarative (tool input paths, command strings), a lower bound.
- `trace/blame.py` — `blame_location(trace, Location(path,line,value), contract=None)` works WITHOUT a contract: finds the step that
  introduced the value (line-aligned), then where it came from among what the actor observed before (read output, command output, fetched URL,
  task message, instruction files, sub-agent reply, pre-existing file). Grades provable / lineage_exact / lineage_internal / heuristic / gap.
  `provable` needs a contract claim to re-run; without contract the best grade is inference layer. This is THE primitive for "unsourced specifics".
- `trace/locate.py` — `_NUM_RE`, `occurrences`, `contains` (numeric-aware) — reusable for extracting specifics.
- `trace/feedback.py` — agent text (<=14 lines, no actor, KS-1 checked per line via `feedback_ks1_clean`), human report, `human_summary`,
  finding ids + "still open / resolved" diff via `feedback_state.json`.
- `trace/stopcheck.py::localize` — contract results -> blame -> finding events on chain -> agent text + report.md/report.json in `$VACANT_HOME/trace/projects/<key>/`.
- `adapters/hookpolicy.py::decide_stop` — round cap `max_feedback_rounds` (default 3) per (session, contract path); `new_request` resets on a person's prompt;
  not-agent-fixable (UNKNOWN/CONFLICT) never pushed back; after cap the open list goes to the human (`user_message` -> Claude `systemMessage`).
- `trace/finalize.py` — background re-check at session end (for `opencode run` and late edits); human report only.
- `adapters/agents.py` — pi extension (`agent_before_settle` -> `{entries:[custom_message], continue:true}`), OpenCode plugin
  (`session.idle` -> `client.session.prompt(feedback)`, disabled when argv has `run`), Claude/Codex hooks docs (`Stop` timeout 600 s).
- `adapters/run.py` (`vacant do`) — copies project, runs headless, re-runs with feedback appended on FAIL (this is the OpenCode-run route today).
- `vrun/wireproxy.py` — recording reverse proxy: raw request/response bytes per call + `index.jsonl`; body never re-serialized (runtime check);
  optional sentinel->real key swap; fail-closed sink for unspecified upstream; path policy. **No retries, no HTTPS_PROXY/CONNECT support,
  no response parsing (usage/provider)**.
- `ops/intake/mock_model.py` — scripted fake provider for Anthropic Messages / OpenAI Responses / Chat Completions; logs JSONL; accepts only `sk-fake*`.
  Reuse for L-fake smoke of the whole zero-config loop and of the Harbor wrappers (no quota spent).
- `ops/accountability/r536/run.py` — three arms that differ only by `VACANT_FEEDBACK_MODE` (none/generic/localized) through `vacant do`; resumable rows.
  Pattern to reuse for arms A/B/C bookkeeping.
- Evidence of Stop-feedback reach (L-fake, `ops/accountability/evidence_20260924/e2e_trace_SUMMARY.md`): Claude/Codex/pi headless: feedback reached model;
  OpenCode `run`: never (`feedback reached model = False` in all rows). OpenCode TUI: reached (`e2e_tui_SUMMARY.md`).

## 1. Stop-payload facts checked in the binaries here (for "claims of testing" we need the final assistant text)

- Claude Code 2.1.281: Stop hook input schema has `last_assistant_message: optional, "Text content of the last assistant message before stop"`
  [SRC: strings in /opt/claude-code/bin/claude]. Also `transcript_path` (already sealed by capture).
- Codex 0.156.1: binary contains hook schema with `last_assistant_message`, `transcript_path`, `agent_transcript_path` [SRC: strings of vendor musl binary]. Exact event membership unverified.
- pi 0.87.1: `AgentBeforeSettleEvent extends BoundaryState {entries, continue, context: {contextMessages, llmMessages, pendingMessages, canContinue}, outcome}`
  [SRC dist/core/extensions/types.d.ts:602-622]; `ctx.ui.notify(message, type)` exists (line 77) for the delivery note.
- OpenCode 1.18.32: plugin has `client` (SDK); last message obtainable via `client.session.messages` (unverified name in 1.18.32); `opencode run` exits at first idle.

## 2. OpenRouter response metadata (docs read 2026-09-25)

- https://openrouter.ai/docs/use-cases/usage-accounting : `usage` always included (`prompt_tokens`, `completion_tokens`, `prompt_tokens_details.cached_tokens`,
  `completion_tokens_details.reasoning_tokens`, `total_tokens`, `cost`, `cost_details.upstream_inference_cost`); `usage:{include:true}` deprecated, no effect.
- https://openrouter.ai/docs/api/api-reference/generations/get-request-&-usage-metadata-for-a-generation : `GET /api/v1/generation?id=` returns
  `provider_name`, `total_cost`, `tokens_*`, `native_tokens_*`, `latency`, `generation_time`, `finish_reason`, `native_finish_reason`, `streamed`, `cancelled`,
  `provider_responses`, `router`, `is_byok`, `data_region`, `request_id` ... **no quantization field** => quantization must come from the endpoints listing
  snapshot (`/api/v1/models/<author>/<slug>/endpoints`, as saved in scratchpad/orq/<model>.json) keyed by provider_name.
- https://openrouter.ai/docs/features/provider-routing : pinning is a request-body field (`provider.order/only/allow_fallbacks/quantizations/...`),
  or account-wide settings. No header. Free models listed in MODELS.md each have exactly one provider, so no pinning needed for them.
- Whether a 429 counts against the 50/day free cap: unverified.

## 3. Harbor (official harness of Terminal-Bench 2.0), clone at study/src/harbor @ 6cb9ff31 (2026-09-24)

- README.md:30-35 "Harbor is the official harness for Terminal-Bench-2.0"; also runs SWE-Bench, Aider Polyglot adapters (README:59).
- Installed agents exist for pi (`Pi`), OpenCode (`OpenCode`), Claude Code (`ClaudeCode`), Codex (`Codex`) in `src/harbor/agents/installed/`.
  `harbor run --agent module.path:ClassName` accepts a custom class (`src/harbor/cli/jobs.py:575-590`).
- `BaseInstalledAgent.setup()` -> `install(environment)`; run() is one shell command per agent:
  - pi: `pi --print --mode json --session-dir ... --provider P --model M {--extension ...} {cli_flags} <instr>`; isolated config dir
    `PI_CODING_AGENT_DIR=/tmp/harbor-pi-agent` when a custom models.json is used (pi.py:46-47, 397-450) => `~/.pi/agent/extensions` autoload NOT reliable; pass `--extension`.
  - opencode: `opencode --model=M run --format=json --thinking --dangerously-skip-permissions -- <instr>` (opencode.py:616-627); writes `~/.config/opencode/opencode.json`.
  - claude: `CLAUDE_CONFIG_DIR=<environment_logs_dir>/sessions`, optional `--settings /tmp/claude-code-settings/settings.json` from agent `config` (claude_code.py:152, 523, 1920-1960).
  - codex: `CODEX_HOME=/tmp/codex-home`, native config.toml via agent `config` (codex.py:84-104).
- Paths (`src/harbor/models/trial/paths.py:12-50`): `/logs/agent` mounted from trial_dir/agent (collected automatically);
  **`/tests` is copied in by the verifier AFTER the agent runs** => Vacant cannot see hidden tests during the run.

## 4. Design decisions (see StructuredOutput for the full text)

- New `VACANT_MODE` (install-time setting, env override): `off` | `observe` (trace only, no injection) | `persona` (arm B: same wrapper, fixed persona text,
  no evidence) | `evidence` (arm C, default for zero-config installs). Contract path unchanged and takes precedence when `vacant.toml` exists.
- The evidence pass is a pure function over the chain (replayable offline on any recorded trace => FP rate measurable without model calls).
- New feedback headers MUST be added to `capture.prompt_source` recognition (else OpenCode TUI feedback counts as a person's prompt: resets the round cap
  = infinite loop, and becomes a value source = launders unsourced values).
- Benchmark install = hooks only, no SKILL.md (skills change the model's system prompt/tool listing; would add a second difference between arms).
- Nothing Vacant writes may land in the task workspace (graders read it); all state under `VACANT_HOME=/logs/agent/vacant`.
