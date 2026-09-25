# Terminal-Bench 2.0 via Harbor — deep dive notes (read 2026-09-25)

## Repos / commits
- Harbor: https://github.com/laude-institute/harbor @ 6cb9ff3167596c456e0b24622d473b59fc9ab6c7 (already cloned at
  scratchpad/study/src/harbor before this session started). `pyproject.toml`: package `harbor`, `requires-python>=3.12`.
- terminal-bench-sample@2.0 task source: https://github.com/laude-institute/terminal-bench-2-0-sample @
  7e917f35c281188532772312d4ad91ca9274febc (pinned in harbor/registry.json, verified by grep). Cloned to
  scratchpad/study/src/terminal-bench-2-0-sample, checked out that exact commit on branch `pinned`.
- Full terminal-bench@2.0 (89 tasks) task source: https://github.com/laude-institute/terminal-bench-2 @
  69671fbaac6d67a7ef0dfec016cc38a64ef7a77c (from registry.json, NOT cloned this session — budget).
- registry.json (harbor repo, 13.6MB) has 4 relevant entries: terminal-bench (v2.0, 89 tasks), terminal-bench-pro
  (v1.0, 200 tasks), terminal-bench-sample (v2.0, 10 tasks), termigen-environments (v1.0, 3566 tasks).

## Protocol facts, with file:line
- Prebuilt image preferred by default: `should_use_prebuilt_docker_image()`,
  src/harbor/environments/definition.py:26-34 — returns True whenever task.toml sets `docker_image` and
  `--force-build` is not passed (CLI default `--no-force-build`). All 10 sample tasks set
  `docker_image = ghcr.io/laude-institute/terminal-bench/<name>:2.0` in task.toml, so `harbor run` by default PULLS
  the prebuilt image rather than building the task's own environment/Dockerfile.
- task.toml uniform across all 10 sample tasks: `[agent] timeout_sec = 900.0`, `[verifier] timeout_sec = 900.0`,
  `[environment] build_timeout_sec = 600.0`.
- Verifier uploads /tests only at verify time, after the agent's run() returns: src/harbor/verifier/verifier.py
  (upload at ~line 182, `env_paths.tests_dir`); trial sequencing in src/harbor/trial/trial.py shows agent run
  ~line 489-700 then `verifier.verify()` ~line 882/952 — no overlap, so the test file/assertions are not visible
  to the agent during its run in the default flow (answers Q6: no leak by default).
- Oracle agent: src/harbor/agents/oracle.py — uploads task's own `solution/` dir into the container and executes
  `solve.sh`/`solve.bat`, writes reward via the verifier's normal test.sh (which reads /app/regex.txt etc., i.e.
  same verifier as an agent run). Nop agent: src/harbor/agents/nop.py (negative control, does nothing).
- `harbor run --help` (captured live, v0.23.0): `--n-concurrent` default 4, `--n-attempts` (-k) default 1,
  `--max-retries` (-r) default 0, `--timeout-multiplier` default 1.0 (and per-phase overrides
  --agent-timeout-multiplier / --verifier-timeout-multiplier / --agent-setup-timeout-multiplier /
  --environment-build-timeout-multiplier). `--env` default `docker`.
- Agent choices (from `--agent` help panel): oracle, nop, acp, terminus/terminus-1/terminus-2 (Harbor's own
  reference scaffold), claude-code, codex, opencode, pi, copilot-cli, cursor-cli, gemini-cli, goose,
  antigravity-cli/-sdk, rovodev-cli, aider, cline-cli, code-puppy, cortex-code, deerflow, devin, dspy-rlm, eve,
  fx/fx-dev, hermes, junie, kimi-cli/-code, langgraph, mcode, mimo, mini-swe-agent, muse-code, nemo-agent,
  openclaw, openhands/-sdk, qwen-coder, strands, swe-agent, trae-agent, vibe, plus `acp:<agent>` shorthand and any
  custom `module:Class` import path.
- pi custom endpoint requires `--ak model_api=<style>` or raises `ValueError("Pi custom endpoints require the
  model_api agent argument")` — src/harbor/agents/installed/pi.py:224-226; reproduced live. Valid `api` values
  documented in pi's own package docs (installed at scratchpad/agents/node_modules/@earendil-works/pi-coding-agent
  /docs/models.md:54 shows `"api": "openai-completions"`; docs/custom-provider.md lists "Anthropic Messages, OpenAI
  Chat Completions and Responses, Google Generative AI and Vertex, Azure OpenAI Responses, Mistral Conversations,
  Bedrock Converse" as the supported wire protocols).
- `--ak max_turns=N` for pi writes a generated extension `max-turns.ts` into `PI_CODING_AGENT_DIR` that aborts
  after N completed turns (pi.py:310-339 `_build_max_turns_extension`/`_write_max_turns_extension`); no default
  (unbounded turns, bounded only by the 900s `[agent] timeout_sec`).
- Model connection is generic, not per-agent special-cased: `ModelConnectionSpec(passthrough=True)` (used by pi.py:98,
  opencode.py:79, aider.py:56, goose.py:58, mimo.py:71, trae_agent.py:93, swe_agent.py:250, strands.py:126, plus
  code_puppy.py/gemini_cli.py/mcode.py/mini_swe_agent.py/qwen_code.py) resolves provider/base_url/api-key from a
  shared `PROVIDERS` table with 40+ entries INCLUDING "openrouter" (base_url_envs=("OPENROUTER_BASE_URL",),
  api_key_envs=("OPENROUTER_API_KEY",), default base_url "https://openrouter.ai/api/v1") —
  src/harbor/agents/model_connection.py:104-107, 154-168. This CONTRADICTS the task brief's premise that
  "opencode.py only sets baseURL for anthropic/google/openai providers" — at commit 6cb9ff31 that is not what the
  code does; the base-URL/API-key passthrough is generic across all 40+ PROVIDERS entries for every agent whose
  MODEL_CONNECTION has passthrough=True, not narrowed to 3 providers. (I did not fully read opencode.py's own
  install()/run() to rule out a narrower override on top of this — flagged as an open question.)
- Harbor Hub leaderboards are self-reported: "Harbor Hub intentionally does not calculate row scores from linked
  trials, to enable maximally flexible leaderboard construction." — docs-mintlify/core-concepts/harbor-hub/
  leaderboards.mdx. There is no central score verifier; the closest thing to "official" is the pinned dataset
  commit (task.toml/instruction.md/tests/ byte-identical) plus which reference agent adapter was used.

## Smoke run log (this session, 2026-09-25, times UTC-ish per job.log)
1. `uv venv --python 3.12 scratchpad/harbor-venv && uv pip install -e scratchpad/study/src/harbor` — clean, no
   errors (uv_install.log).
2. `docker pull ghcr.io/laude-institute/terminal-bench/regex-log:2.0` — 118MB disk / 30.6MB content, ~5s.
3. First oracle run (`harbor run --path .../sample/regex-log --agent oracle --env docker -n 1`) got **reward 0.0**,
   NOT because of a task/Harbor bug: verifier's test.sh does `curl -LsSf https://astral.sh/uv/0.7.13/install.sh | sh`
   to bootstrap `uv`, and that curl failed `SSL certificate problem: self-signed certificate in certificate chain`.
4. Root-caused: confirmed with a plain `docker run` (no --network host, no proxy env set) that even pypi.org (which
   the earlier environment probe said is proxy-noProxy-listed and reachable with no CA bundle under `--network
   host` + explicit HTTPS_PROXY) fails the SAME way under the default bridge network with nothing set — i.e. ALL
   container egress in this sandbox is transparently TLS-intercepted regardless of docker network mode or proxy
   env vars; it is not conditional on --network host. Fix verified in three steps:
   - curl/apt (OpenSSL-linked, Ubuntu default CAfile is /etc/ssl/certs/ca-certificates.crt): mounting
     /root/.ccr/ca-bundle.crt over that exact path fixes it, no `update-ca-certificates` needed.
   - `uv` (Rust/rustls, separate trust store): needs `SSL_CERT_FILE=<bundle>` pointed at a bundle mounted at a
     DIFFERENT path (overwriting ca-certificates.crt directly caused a `dpkg`/`mv` "Device or resource busy" error
     when the package's postinst tried to rewrite that same file — mount at a distinct path instead, e.g.
     /usr/local/share/ccr-ca-bundle.crt).
   - Node/npm (bundled CA list, ignores OS trust store): needs `NODE_EXTRA_CA_CERTS=<bundle>` (same distinct-path
     mount works for both).
5. Re-ran oracle with `--mounts '[{"type":"bind","source":"/root/.ccr/ca-bundle.crt",
   "target":"/usr/local/share/ccr-ca-bundle.crt","read_only":true}]' --ve SSL_CERT_FILE=... --ve CURL_CA_BUNDLE=...`
   → **reward 1.0**, 32s. Same task, `--agent nop` (same mounts/env) → **reward 0.0**, 36s. Positive/negative
   controls both confirmed on regex-log.
6. Second oracle task, `log-summary-date-ranges` (python:3.13-slim-bookworm base) with the same fix →
   **reward 1.0**, 37s. Confirms the mechanism generalizes across at least 2 of the 10 sample tasks.
7. Pulled the remaining 7 relevant sample task images (build-cython-ext, chess-best-move,
   configure-git-webserver, fix-code-vulnerability, log-summary-date-ranges, polyglot-c-py, sqlite-with-gcov) to
   record `docker images` sizes (see deep-dive report). Did NOT pull qemu-alpine-ssh / qemu-startup: their
   Dockerfiles `wget` a multi-hundred-MB Alpine extended ISO and `qemu-img create` a 32GB sparse qcow2 disk at
   build time — judged too disk-risky for the 4GB task budget without a dedicated test; recommend testing those on
   the owner's own machine instead.
8. Live smoke: `harbor run --path .../sample/regex-log --agent pi --model openrouter/qwen/qwen3.5-9b --env docker
   -n 1 --mounts <CA bundle> --ae OPENROUTER_API_KEY=sk-dummy --ae
   OPENROUTER_BASE_URL=http://172.17.0.1:18900/t/live-tb2-regex-log/api/v1 --ae SSL_CERT_FILE=... --ae
   CURL_CA_BUNDLE=... --ae NODE_EXTRA_CA_CERTS=... --ve SSL_CERT_FILE=... --ve CURL_CA_BUNDLE=... --ak
   max_turns=15 --ak model_api=openai-completions`.
   - First attempt (no `model_api`) failed fast with the expected `ValueError` (see above) — 0 cost, useful
     confirmation of the pi.py code path.
   - Second attempt succeeded end-to-end: pi installed via nvm+npm inside the SAME task container (no separate
     node: image pull needed — avoided the Docker Hub 429 rate limit we hit when testing `docker pull node:22-slim`
     directly), reached the recording proxy via the default bridge network's gateway IP (172.17.0.1:18900) with NO
     `--network host` and no other network flag changes, made exactly 1 real model call, and finished with
     **reward 0.0**. Total wall time 2m37s.
   - Ledger for tag `live-tb2-regex-log`: requests=1, ok=1, prompt_tokens=1717, completion_tokens=16384,
     reasoning_tokens=16384 (100% of the completion budget was reasoning tokens), cost_usd=0.00226728.
   - trajectory.json: exactly 2 steps (1 user, 1 agent), the agent step's `message` is empty — the model spent its
     entire 16384-token output budget on chain-of-thought and produced NEITHER a tool call NOR visible text, so
     /app/regex.txt was never written. This is a real (non-infra) result: the 9B model failed to complete even one
     turn within its own reasoning budget on a non-trivial regex task.
   - Total proxy-wide spend after this run: $0.00552156 of the $4.80 test cap (other tags present from earlier/
     sibling sessions: smoke-proxy, try1-pi-qwen9b, live-lcb-lcb_3594, live-lcb-lcb_3607).
9. Cleanup: all 8 pulled ghcr.io images `docker rmi`'d; `docker images` / `docker ps -a` empty afterward; disk back
   to ~15G avail (baseline), confirmed with `df -h /`.

## Image sizes (docker images, DISK USAGE / CONTENT SIZE), read 2026-09-25
| task | base (Dockerfile FROM) | disk usage | content size |
|---|---|---|---|
| regex-log | ubuntu:24.04 | 118MB | 30.6MB |
| log-summary-date-ranges | python:3.13-slim-bookworm | 189MB | 45.8MB |
| sqlite-with-gcov | ubuntu:24.04 (+12.6MB vendor tarball) | 143MB | 43.1MB |
| configure-git-webserver | ubuntu:24.04 | 224MB | 71.8MB |
| polyglot-c-py | ubuntu:24.04 | 504MB | 148MB |
| fix-code-vulnerability | python:3.11-slim | 709MB | 192MB |
| chess-best-move | ubuntu:24.04 | 843MB | 226MB |
| build-cython-ext | python:3.13-slim-bookworm | 1.18GB | 304MB |
| qemu-alpine-ssh | debian:bullseye-slim (+Alpine ISO dl, +32GB sparse qcow2) | NOT PULLED (risk) | — |
| qemu-startup | debian:bullseye-slim (same pattern) | NOT PULLED (risk) | — |

Sum of the 8 pulled: disk usage ≈3.9GB, content size ≈1.06GB. Smallest 3-5 that fit comfortably in 4GB together:
regex-log, log-summary-date-ranges, sqlite-with-gcov, configure-git-webserver, polyglot-c-py (sum ≈1.18GB disk
usage) — leaves headroom; adding fix-code-vulnerability or chess-best-move still keeps 5-6 tasks under 3GB.

## Published baselines (secondary sources — NOT cross-checked against primary tables, flag as unverified)
- WebSearch snippet (2026-09-25), citing two papers (not fetched directly):
  "Terminal-Lego-Qwen3-8B improved from 2.5% to 11.8% on Terminal-Bench 2.0" and "Nemotron-Terminal-8B achieves
  13.0±2.2 on Terminal-Bench 2.0, a five-fold increase over Qwen3-8B (2.47±0.5)." Aggregator blog hits also
  surfaced: codingfleet.com/blog/terminal-bench-leaderboard-2026/ ("Terminal-Bench 2.1 Leaderboard") and
  benchlm.ai/benchmarks/terminalbench21 — both third-party, unverified, and about TB2.1 not TB2.0.
- WebFetch of https://www.tbench.ai/leaderboard (2026-09-25) now defaults to Terminal-Bench 4.0 and did not surface
  TB2.0 rows in the fetched content (page said a leaderboard table exists but the row data wasn't in what was
  returned). Did not find an archived TB2.0-specific leaderboard URL in the time budgeted — open question.
- Our own live smoke (1 real trial, qwen/qwen3.5-9b, reward 0.0, model burned its full output budget on reasoning
  with no action taken) is directionally consistent with a near-floor resolve rate for 8-9B reasoning models on
  TB2.0, but is a single n=1 trial and not a statistically meaningful reproduction.
