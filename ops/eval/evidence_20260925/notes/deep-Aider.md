# Deep-dive: Aider Polyglot (Harbor adapter) — NOTES

Repos (pinned, all read directly, no guessing):
- Harbor: /tmp/.../scratchpad/study/src/harbor, origin https://github.com/laude-institute/harbor, commit `6cb9ff3167596c456e0b24622d473b59fc9ab6c7` (2026-09-24, already cloned by a sibling agent)
- Aider Polyglot dataset source: /tmp/.../scratchpad/study/src/polyglot-benchmark, origin https://github.com/Aider-AI/polyglot-benchmark.git, commit `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f` (2024-12-22) — 225 exercises confirmed by directory count: python 34 + javascript 49 + java 47 + cpp 26 + go 39 + rust 30 = 225.
- Aider official (for benchmark.py, prompts.py, and the ground-truth leaderboard YAML): cloned this session, `git clone --depth 1 https://github.com/Aider-AI/aider.git`, commit `5dc9490bb35f9729ef2c95d00a19ccd30c26339c` (2026-05-22), 141MB.

## 1. Official protocol — exact, file:line

Source: `src/aider-official/benchmark/benchmark.py` (commit 5dc9490).
- `main()` CLI defaults: `tries=2` (`-r/--tries`, benchmark.py:199), `threads=1` (benchmark.py:200), `num_tests=-1` i.e. all 225 (benchmark.py:202), `edit_format=None` → falls back to `main_model.edit_format`, the model's own default edit format from aider's `models.py` settings (benchmark.py:815), `temperature` not set by the benchmark harness itself (uses aider's per-model default, usually 0 for coding models unless overridden).
- Prompt construction (benchmark.py:774-784): `instructions = introduction.md (if present) + instructions.md + instructions.append.md (if present) + prompts.instructions_addendum.format(file_list=...)`. `prompts.instructions_addendum` and `prompts.test_failures` are in `benchmark/prompts.py` verbatim (copied above).
- Retry loop (benchmark.py:848-906): up to `tries` attempts; after a failing attempt, `instructions = errors + prompts.test_failures.format(file_list=...)` — the model is shown the actual failing test output (not just "you failed") and told the tests are correct, don't change them. This is NOT masked feedback — it's the full pytest/go test/etc. stdout, thus the *original* Aider protocol is exactly the "show test failures, retry" design the owner wants for Vacant's own feedback loop (grounded, located, not "try harder").
- Scoring (benchmark.py:468-567, `summarize_results`): `pass_rate_1` = % passing on first try, `pass_rate_2` = % passing by the end of try 2 (the headline number reported on the leaderboard). Denominator = `res.completed_tests` (tasks that actually produced a `.aider.results.json`), which should equal `total_tests=225` for a full run.
- Per-test-run timeout: 180s (`timeout = 60 * 3`, benchmark.py:982), applied to the unit-test subprocess only (not a wall-clock cap on the whole task or on model latency).
- Test commands by extension (benchmark.py:985-992): pytest (py), `cargo test -- --include-ignored` (rs), `go test ./...` (go), `/aider/benchmark/npm-test.sh` (js), `/aider/benchmark/cpp-test.sh` (cpp), `./gradlew test` (java).
- Paper vs code: there is no separate "paper" for aider-polyglot — the leaderboard page (aider.chat/docs/leaderboards, dated "Last updated: 2025-11-20" per WebFetch) and the code are the same source of truth; the YAML in `aider/website/_data/polyglot_leaderboard.yml` is generated directly from `.aider.results.json` runs.

## 2. Harbor adapter protocol (the version our 4 agents would actually run under)

Source: `adapters/aider_polyglot/{README.md,aider_polyglot.yaml,src/aider_polyglot/{adapter.py,main.py,utils.py},src/aider_polyglot/task-template/{Dockerfile,test.sh,solve.sh,task.toml}}` in the Harbor repo (commit 6cb9ff3).
- `n_attempts: 1` in `aider_polyglot.yaml` — Harbor's own orchestrator does **not** implement aider's 2-try/test-failure-feedback loop. Whatever multi-turn behavior happens is up to the *agent itself* (pi/OpenCode/Claude Code/Codex/aider can each decide to run tests and retry inside their own turn budget) — this is the "Fidelity gap" the task asked about (see §5).
- Task packaging: `adapter.py::generate_task` builds `<task>/environment/workspace/` (agent-visible: starter/solution files + language build files, **no test files**) and `<task>/tests/` (verifier-only: `.meta/` config + the real Exercism test file(s) + a rendered `test.sh`). Confirmed empirically (below): a generated task directory has zero test files under `environment/workspace/`.
- `task.toml` (`task-template/task.toml`): `timeout_sec = 1800.0` for both `[agent]` and `[verifier]` (30 min budget, generous vs aider's 180s-per-test-run — Harbor's timeout is end-to-end wall clock, not per-attempt).
- Oracle mechanism: `.oracle/solution.enc` (AES-256-CBC via openssl, PBKDF2, default password `tb-secret-please-change` unless `ORACLE_SECRET` is set) embeds the upstream `.meta/example.*` reference solution; `solution/solve.sh` decrypts+copies it back into the workspace per a manifest. This is how `-a oracle` gets scored.
- Dockerfile: `FROM buildpack-deps:jammy`, then `apt-get install tmux asciinema curl`, then a per-language block (python: add-apt-repository ppa:deadsnakes + python3.11; go: curl golang.org tarball; java: openjdk-21-jdk; javascript: nodesource + global npm jest; rust: rustup; cpp: cmake+boost+tbb) — **every single language's Dockerfile starts with an apt-get against archive.ubuntu.com/security.ubuntu.com**, so the blocker in §3 applies to all 6 languages equally, not just the "big" ones.

## 3. Smoke run — commands, results, blocker

All commands + full stdout logged under this directory (`live_smoke.log`, `live_logs/`, `live_smoke_results.json`).

### 3a. Model-free (oracle vs nop), WITHOUT Docker
Generated 2 task dirs with the adapter's own `main.py` (no network needed beyond the already-local `polyglot-benchmark` clone):
```
python3 main.py --polyglot-root .../polyglot-benchmark --task-ids python_beer-song,go_beer-song --output-dir <OUT>
```
Then tried the documented path: `docker build --network host --build-arg HTTPS_PROXY ... -t ... .` on `polyglot_python_beer-song/environment/Dockerfile`.

**Blocker (reproduced, exact)**: the `apt-get update` step inside the container fails —
```
Err:1 http://archive.ubuntu.com/ubuntu jammy InRelease
  405  Method Not Allowed [IP: 127.0.0.1 36343]
```
`archive.ubuntu.com` / `security.ubuntu.com` are not on this proxy's allowlist (the environment facts list pypi.org, registry.npmjs.org, api.github.com, raw.githubusercontent.com, huggingface.co, openrouter.ai — no apt mirror). This is a container-network limitation, not a disk or language-size issue: it blocks the FIRST `RUN` line of every one of the 6 per-language Dockerfiles, before any language-specific or size-specific cost is even incurred. **No Aider Polyglot task can be built as a real Harbor Docker environment from inside this sandbox**, regardless of which language subset is chosen.

Given that, ran the actual Harbor-generated packaging logic (adapter's oracle apply + the real Exercism test suite) directly on the host, which already has Python 3.11 + pytest (`/root/.local/bin/pytest`) and Go 1.24 pre-installed (equivalent to what the Dockerfile would have installed, minus the container isolation):
- `polyglot_python_beer-song`, oracle solution applied via `solution/solve.sh` (decrypts `.oracle/solution.enc`) → `pytest . -q` → **8 passed in 0.01s** (reward=1, matches `test.sh`'s exit-code→reward.txt logic).
- Fresh `polyglot_python_beer-song` (nop, unmodified starter stub `def recite(...): pass`) → `pytest . -q` → **8 failed** (reward=0).
This confirms the adapter's packaging (config-driven file routing, oracle encryption/decryption, hidden-tests separation) is internally consistent — the oracle/nop floor-and-ceiling sanity check the smoke plan asked for passes, just not via the Docker path documented in the README.

### 3b. Live model smoke (qwen/qwen3.5-9b via the lead's recording proxy)
Two small exercises chosen deliberately for low prompt-token cost (the full `beer-song` instructions.md is ~5KB of repeated verse text — expensive for no reason): `python_robot-name` (633B instructions) and `go_hexadecimal` (381B instructions). Script: `live_smoke.py` in this directory — implements a one-shot version of aider's own protocol (§1): prompt = instructions + `instructions_addendum`-equivalent asking for the full file in a fenced code block; on test failure, a second turn with the actual test output + `test_failures`-equivalent, exactly matching benchmark.py's 2-try design. Calls go through `http://127.0.0.1:18900/t/live-aider-polyglot-<task>/api/v1/chat/completions`, tests run on host (pytest / `go test ./...`) since Docker is blocked.

Results (from `live_smoke_results.json` and the proxy's own ledger, `scratchpad/evalrun/ledger/summary.json` → `by_tag`):

| task | attempt | prompt_tok | completion_tok | reasoning_tok | cost (USD) | wall (s) | test result |
|---|---|---|---|---|---|---|---|
| python_robot-name | 1 | 276 | 679 | 553 | 0.00011 | 3.81 | **PASS** (4/4 tests) |
| go_hexadecimal | 1 | 253 | 2000 | 2000 | 0.00028 | 8.24 | **no code produced** — finish_reason=`length`, all 2000 completion tokens spent on `reasoning`, zero content tokens |

Total for this deep-dive's live smoke: 3 requests (python task run twice across two script invocations while debugging max_tokens), **$0.00120** — well under the $0.15 cap. Global proxy budget used across all sibling agents so far: $0.0067 / $4.80.

**Model-behavior finding, not a proxy bug**: raising the client's `max_tokens` to 6000 did not change the go_hexadecimal outcome — the response still stopped at exactly 2000 completion tokens with `finish_reason: "length"`, and the `reasoning` field shows the model stuck in a visible repetition loop ("The key steps involve... I'll create a mapping... The conversion will multiply...", repeated ~9x near-verbatim) without ever reaching the code. I confirmed the proxy (`ops/eval/orproxy.py`) does not inject any `max_tokens` override — it forwards the client's JSON body unmodified (`sent = dict(body)`, only `provider`/`usage.include` are added, orproxy.py:169-172). Cross-checking the shared ledger, sibling deep-dive agents on other benchmarks (`live-lcb-*`, `live-tb2-regex-log`) show the **same pattern**: completion_tokens == reasoning_tokens (10000/10000, 8000/8000, 16384/16384) — i.e. **qwen/qwen3.5-9b at Darkbloom/fp4 has a real, reproducible failure mode of exhausting its entire output budget on visible chain-of-thought without emitting an answer**, independent of benchmark or max_tokens ceiling, for tasks that look like "implement this function." This is a first-class feasibility fact for the model choice, not specific to Aider Polyglot, and should be flagged to the lead: at minimum it means `pass_rate_1`-style single-shot smoke numbers for this model will be **systematically deflated by truncated-reasoning non-answers**, not just by wrong code — a different failure mode than aider's own `num_malformed_responses`/`error_outputs` counters were built to detect (those count malformed *edits*, not empty answers).

Source for the model/provider facts: `/tmp/.../scratchpad/orq/qwen_qwen3.5-9b.json` (OpenRouter model listing, read via API, 2026-09-25) — Darkbloom/fp4 endpoint: `max_completion_tokens: 65536`, pricing prompt $0.00000008/tok, completion $0.00000013/tok (i.e. OpenRouter/Darkbloom itself allows far more than 2000 output tokens; the model chose to stop there while still mid-`reasoning`).

## 4. Published baselines (ground truth, not a scrape)

Read directly from `src/aider-official/aider/website/_data/polyglot_leaderboard.yml` (commit 5dc9490, same repo/commit as the harness code — this is the file the leaderboard site is built from), via `yaml.safe_load`. 69 total model rows, `total_tests: 225` (matches the dataset size) for every row I list. Columns: `pass_rate_1`/`pass_rate_2` (%), `edit_format`, `versions` (aider release used), `date`, `seconds_per_case`, `total_cost` (USD), `percent_cases_well_formed`.

Small/open-weight models ≤~35B (no entry below 27B exists on this leaderboard at all — smallest listed open model is gemma-3-27b-it; there is no published 8-14B-class row to anchor qwen3.5-9b or gemma-3-12b-it against directly):

| model | pass_rate_1 | **pass_rate_2** | edit_format | well_formed% | date | aider ver | sec/case | cost |
|---|---|---|---|---|---|---|---|---|
| gemma-3-27b-it | 1.8 | **4.9** | whole | 100.0 | 2025-03-15 | 0.77.1.dev | 79.7 | $0.00 (openrouter free tier at the time) |
| Qwen2.5-Coder-32B-Instruct | 4.9 | **16.4** | whole | 99.6 | 2024-12-26 | 0.69.2.dev | 42.0 | $0.00 |
| Qwen2.5-Coder-32B-Instruct | 4.4 | **8.0** | diff | 71.6 | 2024-12-22 | 0.69.2.dev | 84.4 | $0.00 (via Hyperbolic) |
| Codestral 25.01 (~22B) | 4.0 | **11.1** | whole | 100.0 | 2025-01-13 | 0.71.2.dev | 9.3 | $1.98 |
| openhands-lm-32b-v0.1 | 4.0 | **10.2** | whole | 95.1 | 2025-04-19 | — | 195.6 | $0.00 |
| QwQ-32B | 8.0 | **20.9** | diff | 67.6 | 2025-03-06 | — | 228.6 | $0.00 |
| Qwen3 32B | 14.2 | **40.0** | diff | 83.6 | 2025-05-08 | — | 372.2 | $0.76 |
| gpt-oss-120b (high reasoning) | 13.8 | **41.8** | diff | 79.1 | 2025-08-06 | — | 35.5 | $0.74 |

This directly answers the deep-dive's premise: published small/mid open-model scores are confirmed **not at the floor** (4.9%–41.8%, never 0%), which is exactly why the owner picked this as the TB2 backup. It also sharpens the "9B-class" claim: our qwen3.5-9b is **smaller than every open model actually on the leaderboard**, so any number we get has no direct anchor — gemma-3-27b-it's 4.9% (whole-file format) is the nearest size/family analogue and should be treated as a soft upper bound, not a prediction, for a 9B/12B quantized model.

Sources: [aider.chat leaderboard page](https://aider.chat/docs/leaderboards/) (WebFetch summary, read 2026-09-25, cross-checked against the YAML — the YAML is authoritative and is what I quote above); `polyglot_leaderboard.yml` in Aider-AI/aider @ 5dc9490bb35f9729ef2c95d00a19ccd30c26339c.

## 5. Which agents can run it / Vacant hook point

Source: `src/harbor/src/harbor/models/agent/name.py` (`AgentName` enum) + `src/harbor/src/harbor/agents/installed/{pi,opencode,claude_code,codex,aider}.py`, all present in the Harbor repo at commit 6cb9ff3.
- Harbor has **native "installed agent" adapters for all four**: `AgentName.PI = "pi"`, `AgentName.OPENCODE = "opencode"`, `AgentName.CLAUDE_CODE = "claude-code"`, `AgentName.CODEX = "codex"` — runnable as `harbor run -d aider_polyglot -a pi -m "<model>"` etc. (README.md's own documented invocation pattern, just swapping `-a claude-code` for `-a pi`/`-a opencode`/`-a codex`).
- Harbor **also** has a native `AgentName.AIDER = "aider"` adapter (`agents/installed/aider.py`) — this is the reproduction-anchor path: it drives the real `aider` CLI (with `--reasoning-effort`/`--thinking-tokens`/`--cache-prompts`/`--auto-test` etc. exposed as Harbor CLI options), so a true "run the *original* benchmark.py-equivalent single-turn-per-file edit protocol through Harbor" is possible without going back to the fork repo, IF the Docker build problem (§3) is solved.
- Given each of these installed agents is just a CLI binary invoked inside the task's Docker container (same mechanism the other deep-dives found for TB2/LCB, per the shared ledger tags), Vacant's hook point is identical to the general plan: install Vacant inside the task image (or bind-mount it in) and run `vacant possess install` against whichever of the four agents Harbor invokes, before the agent's turn starts, so the model endpoint the agent calls is Vacant's proxy. This is blocked by the same apt-get issue for actually *building* the task images here, but is not a protocol blocker — it's the same generic "get Vacant into the Harbor task container" problem every benchmark in this study faces, not something specific to Aider Polyglot.
- `mini_swe_agent.py` also exists as an installed agent if a bare-bones official-scaffold fallback is wanted instead of the 4 target agents, but Aider Polyglot's own natural "official scaffold" is `aider` itself (unlike e.g. SWE-bench where a generic scaffold like mini-swe-agent stands in for "no native support").

## 6. Arms B/C and "no materials folder"

- **Fidelity/protocol choice (owner's question 1)**: I'd count the **Harbor adapter's own protocol** (hidden tests, `n_attempts: 1`, agent decides its own retry behavior) as "official" for the Vacant claim, precisely *because* it does NOT hand the agent test output automatically — that gap is exactly where Vacant's value proposition (locate the failure, hand back grounded feedback, "up to N rounds" per KS-1) has something to do that the raw benchmark doesn't already do for free. Running aider's own `benchmark.py` in parallel as a reproduction anchor is possible (`aider` is a native Harbor agent per §5) and is valuable as a sanity check that our stack (proxy, model) reproduces roughly plausible numbers vs. the published YAML, but it should **not** be the number used for the Vacant with/without claim, since aider's harness already gives every arm the 2-try test-failure loop "for free" — that would wash out exactly the effect Vacant is supposed to add. Use Harbor's `n_attempts:1` bare protocol as arm A (no Vacant, no feedback at all) so arms B (reviewer persona, no Vacant evidence) and C (Vacant) each have to independently supply whatever iteration they get credit for.
- **Materials-folder question**: Aider Polyglot exercises genuinely have none (§2 — workspace = code file(s) + build metadata only, no images/spreadsheets/schedules/logo-type "context the agent should have opened but didn't"). So the owner's "did the agent skip reading provided materials" accountability check has nothing to bite on for this benchmark specifically. What Vacant *can* check here, grounded in the trace (per CLAUDE.md's `trace/` module): (a) did the agent actually run the test suite/build before declaring done, or is "tests pass" an unverified claim in its own transcript with no matching `provable` rerun in `blame.py`'s sense; (b) did the agent change function/class names the instruction explicitly forbids ("Don't change the names of existing functions or classes"); (c) for the oracle/example-solution family of exercises, did the agent's final diff show any evidence of reading/copying the `.meta/example.*` file it was never given (a integrity check, not a materials-use check — the encrypted oracle payload means this is actually hard for the agent to cheat on, which is a nice property to keep, not a gap to fix).

## 7. Calls/tokens per task, feasibility

- No published official per-call/per-token trajectory logs are bundled with the leaderboard YAML — it only has `seconds_per_case` and `total_cost`, not calls-per-task. From our own live smoke (§3b): 1 model call for a task that passes on the first try (robot-name: 276+679=955 tokens, $0.00011), but the officially-documented protocol allows up to `tries=2` calls per task under the *original* harness; Harbor's `n_attempts:1` means Harbor itself makes 0 extra calls beyond whatever the agent (pi/OpenCode/etc.) decides to make internally in its own tool-use loop, which for a real coding agent (not our one-shot smoke) will be several calls (read file, edit, run tests, maybe retry) — realistically 3-8 model calls/task based on the `try1-pi-qwen9b` sibling tag in the shared ledger (4 requests, 8327 prompt + 980 completion tokens for what looks like a single task run under `pi`).
- Full 225-task set at ~1 call/task (best case, like our robot-name result): 225 calls/day — **exceeds the 50 free-model-calls/UTC-day cap by 4.5x**, so the full set cannot run in one day even on paid-but-cheap models if the intent is also to stay inside a free-tier-shaped daily cadence; at the realistic 3-8 calls/task for an actual agent loop (not one-shot), it's 675-1800 calls, still fine under the "<1000/day" bucket only at the low end.
- A **sensible subset** for the demo: 20-30 tasks spanning all 6 languages (the disk/build blocker in §3 means language choice doesn't matter for cost until the Docker problem is fixed) fits comfortably: at 3-8 calls/task that's 60-240 calls, well under 1000/day, and at the observed $0.0001-0.0003/call for qwen3.5-9b, total cost for the whole subset is well under $0.10.
- USD cost with the paid fallback from MODELS.md (`openai/gpt-oss-20b`, ~$0.02-0.03/M input): full 225-task set at realistic agent-loop token volumes (say 8k prompt + 2k completion tokens/task, informed by our go_hexadecimal reasoning-loop finding that completion budgets need real headroom) ≈ 225 × (8k×$0.025/M + 2k×$0.03/M-ish) ≈ 225 × $0.00026 ≈ **$0.06** for the full set — cheap; the binding constraint is the free-tier daily call cap and the Docker/apt-get blocker, not USD.

## 8. Unavoidable differences from the published runs

1. **No apt access from inside a Harbor task container in this sandbox** (§3) — every language's Dockerfile fails at its first `RUN apt-get update`. This blocks running the *actual* Harbor-Docker-isolated agent loop entirely, for any agent, any language, here. Recorded by: this NOTES.md + `live_smoke.log` (docker build output) — not by a synthetic score.
2. **Live smoke ran the test suite on the bare host, not inside the Harbor sandbox/container** — no network/filesystem isolation, no per-task Docker image, tests executed with whatever host Python/Go toolchain versions happen to be installed (Python 3.11.15, Go 1.24.7), which may not exactly match the pinned toolchain versions the adapter's Dockerfiles specify (python3.11 via deadsnakes, Go 1.21.5, not 1.24.7). Recorded in `live_smoke_results.json`/`live_smoke.log`, and flagged here.
3. **One-shot chat-completion smoke, not a real agentic tool-calling loop** — the live smoke used a single/two-turn raw chat-completions call scripted to imitate aider's own whole-file-edit protocol, not an actual Harbor `-a pi`/`-a aider` run (blocked by #1). This is explicitly the smoke-plan's own fallback framing ("if the harness can drive an agent or model... do a LIVE smoke"); a true Harbor-driven run would additionally spend agent-framework overhead tokens (tool-call scaffolding, system prompts) not present in this smoke.
4. **Model class has no leaderboard anchor** (§4) — qwen/qwen3.5-9b (or gemma-3-12b-it) is smaller than every model on the published leaderboard; any comparison to the YAML numbers is an extrapolation, not a reproduction, and should be labeled as such in any exhibit.
5. **Oracle secret / task generation is local**, not the registry-published `datasets/aider_polyglot` artifact — tasks were generated fresh from the local `polyglot-benchmark` clone via the adapter's `main.py`, which is deterministic given the same upstream commit but was not diffed byte-for-byte against a Harbor-registry-published copy of the same task.
