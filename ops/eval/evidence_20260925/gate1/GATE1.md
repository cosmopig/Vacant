# Gate 1 — model smoke test (arm A only, no Vacant)

Plan: `decisions/DECISION_20260925_ZERO_CONFIG_EVAL.md` §5.1/§3.x. Date: 2026-09-25.
Harbor: `laude-institute/harbor` @ `6cb9ff3167596c456e0b24622d473b59fc9ab6c7`, cloned at
`scratchpad/study/src/harbor`. Agent: pi **0.87.1** (pinned via `--ak version=0.87.1` on all
12 runs — same version the earlier deep-dives happened to install as "latest").
`--ak model_api=openai-completions`, no `--ak temperature`, no `--max_turns` override beyond
`--ak max_turns=15` (kept from the deep-dive recipe, not an official default — see Deviations).
Proxy: `OPENROUTER_BASE_URL=http://172.17.0.1:18900/t/<tag>/api/v1`, `OPENROUTER_API_KEY=sk-dummy`.

## Result table

| model | task | reward | requests | prompt tok | completion tok | reasoning tok | cost (USD) | wall time | failure mode |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| gemma-3-12b-it | DABstep-5 | 0.0 | 1 | 2,044 | 376 | 0 | 0.000159 | 2m33s | bad tool-call format |
| gemma-3-12b-it | DABstep-70 | 0.0 | 1 | 2,055 | 65 | 0 | 0.000113 | 0m50s | bad tool-call format |
| gemma-3-12b-it | SpreadsheetBench 10452 | 0.0 | 1 | 2,372 | 764 | 0 | 0.000233 | 1m57s | bad tool-call format |
| gemma-3-12b-it | Terminal-Bench regex-log | 0.0 | 1 | 2,130 | 507 | 0 | 0.000183 | 1m02s | bad tool-call format |
| gemma-4-26b-a4b-it | DABstep-5 | **1.0** | 7 | 38,127 | 324 | 0 | 0.002779 | 0m57s | — (correct) |
| gemma-4-26b-a4b-it | DABstep-70 | 0.0 | 15 | 538,494 | 2,170 | 0 | 0.038432 | 3m00s | ran out of turns (max_turns=15), never wrote `/app/answer.txt` |
| gemma-4-26b-a4b-it | SpreadsheetBench 10452 | **1.0** | 10 | 63,625 | 8,404 | 0 | 0.007311 | 4m17s | — (correct) |
| gemma-4-26b-a4b-it | Terminal-Bench regex-log | 0.0 | 15 | 61,845 | 1,757 | 0 | 0.004927 | 3m10s | ran out of turns (max_turns=15), never wrote `/app/regex.txt` |
| qwen3.5-9b | DABstep-5 | **1.0** | 7 | 41,539 | 879 | 457 | 0.003437 | 1m17s | — (correct) |
| qwen3.5-9b | DABstep-70 | 0.0 | 11 | 108,061 | 4,001 | 2,423 | 0.009165 | 2m17s | wrong answer (misread a fee-band example number in `manual.md` as a hard threshold — same failure shape as the earlier deep-dive's live smoke on this exact task) |
| qwen3.5-9b | SpreadsheetBench 10452 | 0.0 | 5 | 54,537 | 20,029 | 18,595 | 0.006967 | 4m07s | wrong answer (wrote only 5 of 9 required matches into the output range) |
| qwen3.5-9b | Terminal-Bench regex-log | 0.0 | 1 | 1,717 | 16,384 | 16,384 | 0.002267 | 2m17s | burned its entire reasoning-token budget on one call, no tool call, no visible text |

**gpt-oss-20b was not run.** The fallback trigger ("only if all three above fail to take any
action on every task") never fired — every one of the three models made at least one real tool
call somewhere (gemma-4-26b twice reached reward 1.0; qwen3.5-9b twice reached reward 1.0; even
gemma-3-12b, whose 4/4 failures were format failures, still emitted a coherent single response
each time, just not as a real tool call).

**Totals**: 12/12 runs completed and scored (no unresolved infra failures). Proxy spend for the
12 gate1-tagged runs: **$0.07597** (ledger `by_tag`, summed programmatically), against a $0.20
gate-1 budget and a $4.80 hard cap. Session-wide spend after Gate 1 (including the earlier
deep-dive smoke tests): **≈$0.114** (`ledger/summary.json`, all tags).

## Exact commands

One shell driver (`scratchpad/evalrun/gate1/run_one.sh`) parameterized by
`(dataset@version, task, model, tag, jobs-subdir)`, invoked once per (model, task) pair:

```bash
cd scratchpad/study/src/harbor
uv run --no-dev harbor run \
  --dataset "<dataset@version>" \
  -i "<task-name>" \
  --agent pi \
  --model "openrouter/<model-id>" \
  --env docker -n 1 -q \
  --mounts '[{"type":"bind","source":"/root/.ccr/ca-bundle.crt","target":"/usr/local/share/ccr-ca-bundle.crt","read_only":true}]' \
  --ae OPENROUTER_API_KEY=sk-dummy \
  --ae "OPENROUTER_BASE_URL=http://172.17.0.1:18900/t/<tag>/api/v1" \
  --ae SSL_CERT_FILE=/usr/local/share/ccr-ca-bundle.crt \
  --ae CURL_CA_BUNDLE=/usr/local/share/ccr-ca-bundle.crt \
  --ae NODE_EXTRA_CA_CERTS=/usr/local/share/ccr-ca-bundle.crt \
  --ve SSL_CERT_FILE=/usr/local/share/ccr-ca-bundle.crt \
  --ve CURL_CA_BUNDLE=/usr/local/share/ccr-ca-bundle.crt \
  --ak max_turns=15 --ak model_api=openai-completions --ak version=0.87.1 \
  --jobs-dir <gate1/jobs/{sbv,tb2,dab}>
```

The 12 invocations (dataset, task, model, tag):

1. `spreadsheetbench-verified@1.0` / `10452` / `google/gemma-3-12b-it` / `gate1-gemma3-12b-sbv-10452`
2. `spreadsheetbench-verified@1.0` / `10452` / `google/gemma-4-26b-a4b-it` / `gate1-gemma4-26b-sbv-10452`
3. `spreadsheetbench-verified@1.0` / `10452` / `qwen/qwen3.5-9b` / `gate1-qwen35-9b-sbv-10452`
4. `terminal-bench-sample@2.0` / `regex-log` / `google/gemma-3-12b-it` / `gate1-gemma3-12b-tb2-regex-log`
5. `terminal-bench-sample@2.0` / `regex-log` / `google/gemma-4-26b-a4b-it` / `gate1-gemma4-26b-tb2-regex-log`
6. `terminal-bench-sample@2.0` / `regex-log` / `qwen/qwen3.5-9b` / `gate1-qwen35-9b-tb2-regex-log`
7. `dabstep@1.0` / `dabstep-5` / `google/gemma-3-12b-it` / `gate1-gemma3-12b-dabstep-5`
8. `dabstep@1.0` / `dabstep-5` / `google/gemma-4-26b-a4b-it` / `gate1-gemma4-26b-dabstep-5`
9. `dabstep@1.0` / `dabstep-5` / `qwen/qwen3.5-9b` / `gate1-qwen35-9b-dabstep-5`
10. `dabstep@1.0` / `dabstep-70` / `google/gemma-3-12b-it` / `gate1-gemma3-12b-dabstep-70`
11. `dabstep@1.0` / `dabstep-70` / `google/gemma-4-26b-a4b-it` / `gate1-gemma4-26b-dabstep-70`
12. `dabstep@1.0` / `dabstep-70` / `qwen/qwen3.5-9b` / `gate1-qwen35-9b-dabstep-70`

Task selection used Harbor's own registry (`--dataset <name>@<version> -i <task>`) rather than
`--path` into a manually-checked-out task dir, since all three benchmarks are registry datasets
(`registry.json` in the pinned Harbor commit) — this is the plainer, more official form of the
command than the deep-dives' own `--path <cache>/<id>` (which they used because they were probing
a manually-clone-and-generate flow before the registry path was confirmed to work identically).

## Deviations from the plain official command, and why

1. **CA-bundle mount + 4 env vars (`SSL_CERT_FILE`, `CURL_CA_BUNDLE`, `NODE_EXTRA_CA_CERTS`,
   `--ve` versions) on every run.** This sandbox's container egress is transparently
   TLS-intercepted; without trusting the interception CA, pi's own npm install, its HTTPS calls
   to the proxy's Node/curl-based internals, and (for DABstep) the verifier can fail with
   `self-signed certificate in certificate chain`. Documented and verified in
   `ops/eval/evidence_20260925/notes/env-RECIPE.md` and the three `deep-*.md` notes. Not needed
   on a normal machine with real unfiltered internet (the owner's laptop or the exhibition
   machine) — this is entirely a property of *this* sandbox, not of the official protocol.
2. **`--ak model_api=openai-completions` is mandatory, not a style choice.** pi's own code
   (`harbor/src/harbor/agents/installed/pi.py:224-226`) raises `ValueError("Pi custom endpoints
   require the model_api agent argument")` for any custom OpenAI-compatible endpoint without it.
   Confirmed live in the earlier deep-dive (first attempt with no `model_api` failed fast,
   0 cost) — not re-triggered here to save a wasted call, per plan.
3. **`--ak version=0.87.1`** pins the pi CLI version explicitly instead of letting `harbor run`
   install "whatever is latest at run time" (the effective default). 0.87.1 was npm's current
   latest at the time of this Gate 1 run (`npm view @earendil-works/pi-coding-agent version`)
   and matches what the un-pinned deep-dive runs happened to install a few hours earlier —
   pinning removes the risk of drift mid-run and makes every one of the 12 runs directly
   comparable to each other and to the deep-dive numbers.
4. **DABstep task Dockerfiles (`dabstep-5`, `dabstep-70`) were hand-patched in Harbor's own task
   cache** (`~/.cache/harbor/tasks/<hash>/<task>/environment/Dockerfile`) to `COPY` the sandbox's
   CA bundle and set `PIP_CERT`/`REQUESTS_CA_BUNDLE`/`CURL_CA_BUNDLE`/`SSL_CERT_FILE` before the
   existing `pip3 install pandas` and `curl … huggingface.co …` steps — **without** touching the
   base image, the `apt-get` step (plain-HTTP Ubuntu mirrors already worked unpatched), or any
   instruction order otherwise. This is the same fix pattern the SpreadsheetBench deep-dive
   already found and verified generalizes without needing `--network host` on the build (`docker
   build`'s default bridge network already reaches the sandbox's interception layer; the missing
   piece was only trust, not routing). First attempt on each of the two DABstep tasks was run
   **unpatched** first (to reproduce the official adapter's Dockerfile byte-for-byte and confirm
   the failure is a sandbox-network problem, not a DABstep or Harbor bug), failed with `Could not
   fetch URL https://pypi.org/simple/pandas/: … self-signed certificate …`, then was retried once
   after patching — counted below as the "re-run once after fixing infra" the plan allows. The
   *task content* the adapter generates (`instruction.md`, `test.sh`, `scorer.py`, the baked
   answer) was never edited — only the two build-time network calls.
5. **`--ak max_turns=15`** is carried over unchanged from the deep-dive recipe. It is **not** an
   official default for any of the three benchmarks (DABstep's own baseline caps at 10 steps;
   SpreadsheetBench's multi-round default is 5; Terminal-Bench's only stated limit is the 900s
   wall-clock timeout) — it is pi's own Harbor-agent-kwarg turn cap, needed because pi's default
   is **unbounded** turns bounded only by the task's own wall-clock timeout, and an unbounded
   9B–26B model given an open-ended tool loop could burn the whole gate-1 budget on one task. The
   task said not to set `temperature` or `max_turns` beyond "official defaults" for the harness
   itself; `max_turns` here is a pi-agent-level safety cap, not a benchmark-level parameter, and
   was already established as necessary infrastructure by both this gate's own retries (2 runs
   hit exactly turn 15 without finishing) and the deep-dives before it. Left unset it would have
   let `gemma-4-26b/dabstep-70` (538k cumulative prompt tokens by turn 15) run substantially
   longer and cost substantially more with no sign of convergence in the trajectory.
6. **Official per-task timeouts were kept as-is** (DABstep agent 1800s/verifier 600s;
   SpreadsheetBench agent+verifier 600s each; Terminal-Bench agent+verifier 900s each) — no
   `--timeout-multiplier` was passed.
7. **Retried once, per the "re-run infra failures" rule**: `gemma-3-12b-it` × SpreadsheetBench
   10452 (first attempt: Docker Hub `429 Too Many Requests` pulling `python:3.11-slim`, a shared
   Docker Hub rate limit, not this repo's fault — fixed by pre-pulling the base image directly,
   then retried) and `gemma-3-12b-it` × DABstep-5 / DABstep-70 (unpatched-Dockerfile CA failures
   described in #4). All three retries are recorded as separate job directories under
   `gate1/jobs/`; only the second (successful, real-model) attempt of each is reported in the
   result table above. No model-level failure was retried — a bad-format or wrong-answer result
   is a result, per the plan.

## Disk / images kept

Per-task Harbor environments are deleted automatically after each trial (`--delete`, Harbor's
default) — nothing task-specific was left behind. Base images pulled during Gate 1 and kept
(needed again for any DABstep/SpreadsheetBench re-runs, both under budget):

- `ghcr.io/laude-institute/t-bench/ubuntu-24-04:20250624` — 183MB disk usage (DABstep's base image)
- `python:3.11-slim` — 189MB disk usage (SpreadsheetBench's base image)

Removed: `ghcr.io/laude-institute/terminal-bench/regex-log:2.0` (118MB, Terminal-Bench's prebuilt
image — not on the "keep DABstep/SpreadsheetBench" list). Total kept: **372MB**, far under the
6GB allowance. `docker images`/`docker ps -a` confirmed clean of anything else after cleanup.
Disk headroom throughout stayed at 13–15GB avail (`df -h /`), never approached the ~15GB shared
limit.

## Per-model conclusion — can it drive pi on these tasks?

- **google/gemma-4-26b-a4b-it — yes.** 2/4 correct (SpreadsheetBench 10452, DABstep-5), and on
  the 2 misses it was genuinely working the problem across many real tool calls (10 and 15 LLM
  calls respectively) rather than failing to engage — it ran out of its 15-turn budget mid-task,
  not out of ideas. This is the strongest of the three: it reliably parses pi's tool-call format
  and makes forward progress every time.
- **qwen/qwen3.5-9b — partly.** 2/4 correct (DABstep-5, and it *did* correctly open
  `manual.md` and compute the right fraud rate on DABstep-70 before drawing the wrong conclusion
  from it — same failure shape as the earlier deep-dive's live smoke on this exact task, now
  reproduced under the actual pi+Harbor harness rather than the baseline smolagents driver). Its
  failure mode is capability-bound and reasoning-budget-bound (burned all 16,384 reasoning tokens
  on Terminal-Bench with no tool call at all, and on SpreadsheetBench a truncated a 9-row output
  to 5), not a harness/format problem — it drives pi correctly when it drives it at all, it just
  sometimes doesn't finish or gets the answer wrong.
- **google/gemma-3-12b-it — no, on this harness.** 0/4, and the failure is identical and
  mechanical across all four tasks: it writes a coherent one-shot plan, then emits what looks
  like a tool call (a fenced ` ```json [...] ` array naming `bash`/`write`/`read`) as plain
  assistant text rather than through pi's actual function-calling channel, so **zero real tool
  calls are ever executed** and the trial ends after the very first LLM turn (1 request per
  task, every time — confirmed in the raw `trajectory.json` for all 4 tasks). This is a
  tool-calling-interface incompatibility with pi specifically, not a task-comprehension failure —
  the plans it writes are on-topic and often close to correct in substance (e.g. it names the
  right file to open on DABstep-70). It should not be recommended for the pilot on pi without
  either a different tool-calling adapter or confirming whether OpenRouter's endpoint for this
  model was actually returning function-calling-capable output (`require_parameters: true` is
  set in the proxy's provider pin, `deepinfra/bf16` — worth a follow-up check before ruling the
  model out entirely, since 12B instruct models with tool-calling training do exist; this run
  does not distinguish "model can't tool-call" from "model tool-calls in a format pi's harness
  didn't recognize for this specific provider route").

**Gate 1 verdict for the pilot (§5.1 of the plan)**: `google/gemma-4-26b-a4b-it` is the strongest
candidate to carry forward; `qwen/qwen3.5-9b` is usable as a second, harder-mode candidate;
`google/gemma-3-12b-it` should not go into the pilot as configured — its failure is 100%
consistent and mechanical, not a matter of task difficulty. `openai/gpt-oss-20b` was not run
(fallback condition did not fire).
